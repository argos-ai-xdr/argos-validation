"""ARG-027: "Acceptance runner AC01-AC14, ARR/G7, reportes firmados y
validación inmutable de RC 0.7" (propuesta v0.6.25.4 §16, changelog 0.6.8
"rectificación ARG-027 de DRR a ARR/G7").

Corre TODAS las suites relevantes contra thresholds/acceptance.yaml en un
solo run, agrega los resultados por `AC01`..`AC14` (una Metric puede
cubrir más de un AC, p. ej. `ungrounded_cve_rate` cubre AC03 y AC08— la
regla de agregación es "el peor gate entre todas las suites que
contribuyen a ese AC"), y aplica la regla dura que motivó todo esto: si
algún AC01-14 termina con CERO métricas contribuyendo, el acceptance
report es inválido — no se puede declarar una release candidate aceptada
sin haber evaluado los 14 criterios. Así se descubrieron AC01/AC02/AC10/
AC12: ningún suite.yaml existente los tocaba y nadie lo había forzado a
comprobar.

"Reportes firmados": sin una PKI/clave de firma real todavía, esto sella
el reporte con sha256 sobre su propio contenido — detecta manipulación
posterior, no sustituye una firma criptográfica con clave real. Se
documenta así explícitamente para no afirmar una garantía que no existe
(mismo principio que argos-smartops SOC_MODE=SOC_EMULATED).

No decide si G7 puede declararse PASS — eso depende también de G6 (ver
traceability.yaml), que tiene sus propios gaps (ARG-023/025) ajenos a
este runner. Este módulo solo responde con precisión "¿qué dicen las 14
AC hoy, evaluadas de verdad?", que es lo que ARG-027 pide automatizar.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import pathlib

from harness.loaders.contracts_path import resolve_contracts_path
from harness.reproducibility import evaluate_reproducibility
from harness.runner.cli import load_thresholds, run_suite

ALL_AC_IDS = tuple(f"AC{n:02d}" for n in range(1, 15))

# Toda suite que declara checks contra thresholds/acceptance.yaml — si se
# añade una suite nueva y no se registra aquí, sus métricas simplemente no
# cuentan para el acceptance report (más seguro que adivinar un glob).
ACCEPTANCE_SUITE_IDS = ("c06", "c07", "c08", "argos-cyb-01", "integration", "regression", "adversarial")

_GATE_SEVERITY = {"FAIL": 2, "PASS_WITH_EXPECTED_BLOCKS": 1, "PASS": 0}


@dataclasses.dataclass(frozen=True)
class ACResult:
    ac_id: str
    gate: str
    critical: bool
    contributing: tuple[dict, ...]


@dataclasses.dataclass(frozen=True)
class AcceptanceReport:
    run_id: str
    generated_at: str
    suite_summaries: dict
    ac_results: dict
    missing_ac_ids: tuple[str, ...]
    overall: str

    @property
    def ok(self) -> bool:
        return not self.missing_ac_ids and self.overall in ("PASS", "PASS_WITH_EXPECTED_BLOCKS")

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "suite_summaries": self.suite_summaries,
            "ac_results": {
                ac_id: {"gate": r.gate, "critical": r.critical, "contributing": list(r.contributing)}
                for ac_id, r in self.ac_results.items()
            },
            "missing_ac_ids": list(self.missing_ac_ids),
            "overall": self.overall,
        }


def _worst_gate(gates: list[str]) -> str:
    return max(gates, key=lambda g: _GATE_SEVERITY.get(g, 2))


def run_acceptance(
    *,
    suites_root: pathlib.Path,
    thresholds_path: pathlib.Path,
    contracts_path: pathlib.Path | None = None,
    suite_ids: tuple[str, ...] = ACCEPTANCE_SUITE_IDS,
) -> AcceptanceReport:
    contracts_path = contracts_path or resolve_contracts_path()
    thresholds = load_thresholds(thresholds_path)

    suite_summaries: dict[str, dict] = {}
    contributions: dict[str, list[dict]] = {ac_id: [] for ac_id in ALL_AC_IDS}

    for suite_id in suite_ids:
        suite_path = suites_root / suite_id / "suite.yaml"
        summary, fixture_errors = run_suite(suite_path, thresholds_path, contracts_path)
        suite_summaries[suite_id] = {**summary, "fixture_errors": fixture_errors}
        for metric_name, result in summary["results"].items():
            for ac_id in result["metric"].get("ac_ids", []):
                if ac_id not in contributions:
                    continue  # AC fuera de AC01-14 (p. ej. ARG-010) no entra en este report
                contributions[ac_id].append(
                    {
                        "suite": suite_id,
                        "metric_name": metric_name,
                        "value": result["metric"]["value"],
                        "gate": result["gate"],
                        "critical": result["critical"],
                    }
                )

    # AC01 (Reproducibilidad) no viene de ningún metric_name de suite —
    # se corre directo contra cada suite incluida en este report.
    repro_contributions = []
    for suite_id in suite_ids:
        suite_path = suites_root / suite_id / "suite.yaml"
        metric = evaluate_reproducibility(suite_path, thresholds_path, contracts_path=contracts_path)
        rule = thresholds.get("reproducibility_violation", {"max": 0.0, "critical": True})
        gate = "FAIL" if metric.value > rule.get("max", 0.0) else "PASS"
        repro_contributions.append({"suite": suite_id, "metric_name": "reproducibility_violation", "value": metric.value, "gate": gate, "critical": True})
    contributions["AC01"] = repro_contributions

    ac_results: dict[str, ACResult] = {}
    missing: list[str] = []
    for ac_id in ALL_AC_IDS:
        entries = contributions[ac_id]
        if not entries:
            missing.append(ac_id)
            continue
        ac_results[ac_id] = ACResult(
            ac_id=ac_id,
            gate=_worst_gate([e["gate"] for e in entries]),
            critical=any(e["critical"] for e in entries),
            contributing=tuple(entries),
        )

    if missing:
        overall = "FAIL"
    else:
        gates = [r.gate for r in ac_results.values()]
        overall = _worst_gate(gates) if gates else "FAIL"

    run_id = f"acceptance-{datetime.datetime.now(datetime.UTC):%Y%m%dT%H%M%SZ}"
    return AcceptanceReport(
        run_id=run_id,
        generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
        suite_summaries=suite_summaries,
        ac_results=ac_results,
        missing_ac_ids=tuple(missing),
        overall=overall,
    )


def seal_report(report_dict: dict) -> dict:
    """Sella el contenido con sha256 — detecta manipulación posterior del
    JSON en disco. NO es una firma criptográfica con clave real (no
    existe todavía ninguna PKI en este proyecto); "reportes firmados" en
    el sentido del documento se resuelve con esto hasta que exista una."""
    canonical = json.dumps(report_dict, sort_keys=True, ensure_ascii=False)
    return {
        "seal_version": "argos-validation-acceptance-seal.v1",
        "algorithm": "sha256-content-hash",
        "note": "hash-seal, no firma criptográfica con clave real (pendiente de PKI)",
        "report_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def write_acceptance_report(report: AcceptanceReport, out_dir: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dict = report.to_dict()
    report_path = out_dir / "acceptance_report.json"
    report_path.write_text(json.dumps(report_dict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    seal = seal_report(report_dict)
    seal_path = out_dir / "acceptance_seal.json"
    seal_path.write_text(json.dumps(seal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path, seal_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    root = pathlib.Path(__file__).resolve().parents[1]
    parser.add_argument("--suites-root", type=pathlib.Path, default=root / "suites")
    parser.add_argument("--thresholds", type=pathlib.Path, default=root / "thresholds" / "acceptance.yaml")
    parser.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("acceptance_out"))
    args = parser.parse_args(argv)

    report = run_acceptance(suites_root=args.suites_root, thresholds_path=args.thresholds)
    report_path, seal_path = write_acceptance_report(report, args.out_dir)

    print(f"acceptance run_id={report.run_id} overall={report.overall}")
    for ac_id in ALL_AC_IDS:
        if ac_id in report.missing_ac_ids:
            print(f"  {ac_id}: SIN COBERTURA (ninguna métrica lo evalúa)")
            continue
        r = report.ac_results[ac_id]
        print(f"  {ac_id}: {r.gate} (crítico={r.critical}, {len(r.contributing)} contribución(es))")
    print(f"report={report_path} seal={seal_path}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
