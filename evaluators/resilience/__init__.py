"""AC13 (Resiliencia): reanudación tras interrupción sin acción duplicada;
idempotency violations = 0. PASS crítico.

Agrupa los ActionResult por idempotency_key. Un reintento tras
interrupción real (ARG-021, IdempotencyStore de argos-cyber-tools) debe
devolver EXACTAMENTE el mismo resultado — mismo status y mismos
changed_resources — que el intento original; si dos ActionResult con la
MISMA idempotency_key difieren, el efecto se repitió o varió entre
intentos, justo la violación que AC13 prohíbe con tolerancia cero. No
mide "¿se reintentó?" (eso ya lo prueba
argos-cyber-tools/tests/idempotency/ contra el código real) — mide "¿los
resultados observados en la evidencia son consistentes con que nunca hubo
una violación?", que es lo que un evaluador de fixtures puede comprobar
sin re-ejecutar nada.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric


def evaluate(fixtures: list[dict], *, contracts_path: pathlib.Path | None = None) -> Metric:
    by_key: dict[str, list[dict]] = {}
    for fixture in fixtures:
        key = fixture.get("idempotency_key")
        if key:
            by_key.setdefault(key, []).append(fixture)

    violations: list[str] = []
    for key, group in sorted(by_key.items()):
        if len(group) < 2:
            continue
        statuses = {g.get("status") for g in group}
        changed_resources = {tuple(sorted(g.get("changed_resources", []))) for g in group}
        if len(statuses) > 1 or len(changed_resources) > 1:
            violations.append(key)

    total_keys = len(by_key)
    violation_rate = len(violations) / total_keys if total_keys else 0.0

    return Metric(
        name="idempotency_violation_rate",
        value=violation_rate,
        detail=f"{len(violations)}/{total_keys} idempotency_key con resultados inconsistentes entre reintentos: {violations}",
        ac_ids=("AC13",),
        sample_size=len(fixtures),
    )
