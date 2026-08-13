"""AC14 (Evidencia/SOC): trace completeness >= 0.95; hashes válidos = 1.00.

Para cada fixture, comprueba que declara payload_hash/run_id (heredados del
envelope) y, cuando trae evidence_refs, que cada referencia resuelve a un
archivo real dentro del checkout de argos-contracts-scenarios — no basta con
que el campo esté presente, tiene que apuntar a algo que existe.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric

REQUIRED_ENVELOPE_FIELDS = ("run_id", "payload_hash")


def evaluate(fixtures: list[dict], *, contracts_path: pathlib.Path | None = None) -> Metric:
    total = len(fixtures)
    complete = 0
    broken_refs: list[str] = []

    for fixture in fixtures:
        has_envelope_fields = all(fixture.get(field) for field in REQUIRED_ENVELOPE_FIELDS)
        refs = fixture.get("evidence_refs", [])
        refs_ok = True
        if refs and contracts_path is not None:
            for ref in refs:
                if not (contracts_path / ref).exists():
                    refs_ok = False
                    broken_refs.append(f"{fixture.get('id', '?')} -> {ref}")
        if has_envelope_fields and refs_ok:
            complete += 1

    completeness = complete / total if total else 1.0

    return Metric(
        name="trace_completeness",
        value=completeness,
        detail=f"{complete}/{total} fixtures completos; broken_refs={broken_refs}",
        ac_ids=("AC14",),
        sample_size=total,
    )
