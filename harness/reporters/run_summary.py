"""Construye run_summary.json (documento maestro v0.5, 5.8) a partir de las
Metric producidas por los evaluadores y los thresholds de la suite.

Regla de decisión (5.6): ningún criterio marcado `critical: true` admite
waiver. Un bloqueo esperado (fixture de fixtures/adversarial/) se declara
aparte como PASS_WITH_EXPECTED_BLOCKS, nunca como FAIL.
"""
from __future__ import annotations

import datetime
import json
import pathlib

from evaluators.base import Metric

GateResult = str  # "PASS" | "FAIL" | "PASS_WITH_EXPECTED_BLOCKS"


def _gate_for_metric(metric: Metric, rule: dict) -> tuple[GateResult, str]:
    if "min" in rule and metric.value < rule["min"]:
        return "FAIL", f"{metric.value} < min {rule['min']}"
    if "max" in rule and metric.value > rule["max"]:
        return "FAIL", f"{metric.value} > max {rule['max']}"
    if rule.get("adversarial"):
        return "PASS_WITH_EXPECTED_BLOCKS", "bloqueo adversarial esperado, dentro de umbral"
    return "PASS", "dentro de umbral"


def evaluate_against_thresholds(metrics: list[Metric], thresholds: dict) -> dict:
    """thresholds: {metric_name: {min|max: float, critical: bool, adversarial: bool}}.

    'adversarial: true' marca un umbral cuyo PASS representa un bloqueo
    exitoso (regla 5.6: se registra como PASS_WITH_EXPECTED_BLOCKS, no como
    un PASS ordinario, para que quede visible en el reporte que el sistema
    encontró y rechazó una entrada maliciosa a propósito).
    """
    results = {}
    for metric in metrics:
        rule = thresholds.get(metric.name)
        if rule is None:
            results[metric.name] = {
                "metric": metric.to_dict(),
                "gate": "FAIL",
                "reason": f"no hay threshold definido para '{metric.name}'",
                "critical": True,
            }
            continue
        gate, reason = _gate_for_metric(metric, rule)
        results[metric.name] = {
            "metric": metric.to_dict(),
            "gate": gate,
            "reason": reason,
            "critical": bool(rule.get("critical", False)),
        }
    return results


def overall_result(results: dict) -> GateResult:
    """PASS solo si todo pasa. Si algún crítico falla -> FAIL.
    Si solo fallan no críticos -> FAIL igualmente (visibilidad), pero el
    llamador puede distinguir por 'critical' en cada entrada para decidir si
    bloquea el gate G0-G7 correspondiente."""
    if not results:
        return "FAIL"
    passing = {"PASS", "PASS_WITH_EXPECTED_BLOCKS"}
    if all(r["gate"] in passing for r in results.values()):
        return "PASS" if all(r["gate"] == "PASS" for r in results.values()) else "PASS_WITH_EXPECTED_BLOCKS"
    return "FAIL"


def build_run_summary(
    *,
    run_id: str,
    suite_id: str,
    mode: str,
    metrics: list[Metric],
    thresholds: dict,
) -> dict:
    results = evaluate_against_thresholds(metrics, thresholds)
    critical_failures = [name for name, r in results.items() if r["gate"] == "FAIL" and r["critical"]]
    warnings = [name for name, r in results.items() if r["gate"] == "FAIL" and not r["critical"]]
    return {
        "run_id": run_id,
        "suite": suite_id,
        "mode": mode,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "results": results,
        "overall": overall_result(results),
        "critical_failures": critical_failures,
        "warnings": warnings,
    }


def write_run_summary(summary: dict, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
