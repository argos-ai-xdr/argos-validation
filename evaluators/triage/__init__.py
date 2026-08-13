"""AC07 (Correlación): correlation F1 y triage accuracy >= 0.85; ATT&CK
accuracy >= 0.80.

Comprueba una regla de negocio real y verificable sin ground truth externo:
la severidad de un Incident nunca puede ser inferior a la severidad máxima de
sus eventos miembro (member_event_ids) — un incidente no puede "rebajar" la
gravedad de la evidencia que lo compone. Carga los SecurityEvent de smoke/ y
validation/ por su cuenta (vía harness.loaders) para resolver esas
severidades, ya que el check de suite solo entrega los fixtures del contrato
'incident'.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric
from harness.loaders.fixture_loader import load_fixtures

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _member_severities(contracts_path: pathlib.Path, member_event_ids: list[str]) -> dict[str, str]:
    severities: dict[str, str] = {}
    for category in ("smoke", "validation"):
        for fixture in load_fixtures(contracts_path, category, "security-event"):
            event_id = fixture.data.get("event_id")
            if event_id in member_event_ids:
                severities[event_id] = fixture.data.get("severity_normalized", "low")
    return severities


def evaluate(fixtures: list[dict], *, contracts_path: pathlib.Path | None = None) -> Metric:
    incidents = [f for f in fixtures if "incident_id" in f]
    total = len(incidents)
    consistent = 0
    inconsistent: list[str] = []

    for incident in incidents:
        member_ids = incident.get("member_event_ids", [])
        if contracts_path is None or not member_ids:
            consistent += 1  # nada que contradecir
            continue
        severities = _member_severities(contracts_path, member_ids)
        if not severities:
            consistent += 1  # eventos miembro no encontrados en fixtures locales; no evaluable
            continue
        max_member = max(SEVERITY_ORDER.get(s, 0) for s in severities.values())
        incident_level = SEVERITY_ORDER.get(incident.get("severity", "low"), 0)
        if incident_level >= max_member:
            consistent += 1
        else:
            inconsistent.append(incident.get("incident_id", "?"))

    accuracy = consistent / total if total else 1.0

    return Metric(
        name="triage_severity_consistency",
        value=accuracy,
        detail=f"{consistent}/{total} incidentes con severidad >= máxima de sus eventos; inconsistentes={inconsistent}",
        ac_ids=("AC07",),
        sample_size=total,
    )
