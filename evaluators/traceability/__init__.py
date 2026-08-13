"""AC14 (Evidencia/SOC): trace completeness >= 0.95; hashes válidos = 1.00.

Para cada fixture, comprueba que declara payload_hash/run_id (heredados del
envelope) y, cuando trae evidence_refs, que cada referencia resuelve a un
archivo real dentro del checkout de argos-contracts-scenarios — no basta con
que el campo esté presente, tiene que apuntar a algo que existe.

Limitación conocida (sin resolver, decisión de arquitectura cross-repo —
ver evaluators/tool_calls/__init__.py para el mismo patrón de nota):
evidence_refs tiene TRES interpretaciones distintas hoy, no una:
  - El schema del envelope (argos-contracts-scenarios/envelope/v1/) lo
    documenta como "referencias a artefactos en el evidence store (Ceph
    RGW/OpenSearch)".
  - argos-core/services/correlator lo puebla con el "id" de envelope de
    cada SecurityEvent miembro — una referencia a OTRO MENSAJE, no a un
    artefacto de evidence store.
  - El fixture smoke real (fixtures/smoke/incident/incident-001.json) usa
    una ruta de archivo relativa al propio checkout
    ("fixtures/smoke/security-event/wazuh-alert-001.json").
Esta función solo valida la tercera convención (ruta de archivo bajo
contracts_path). Contra un Incident real producido por el correlator de
argos-core, cada evidence_ref (un id de envelope, no una ruta) se
reportaría como "roto" — nunca detectado porque el único test de este
evaluador usa una ref sintética tipo "missing.json", no la salida real de
argos-core. Requiere decidir cuál de las tres interpretaciones es la
autoritativa antes de tocar el código (afecta a argos-core y a los schemas
de argos-contracts-scenarios, no solo a este evaluador).
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
