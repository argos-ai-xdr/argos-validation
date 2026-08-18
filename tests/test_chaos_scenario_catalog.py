from __future__ import annotations

import pathlib

import yaml
from chaos import ChaosExperimentRequest, ChaosSafetyGuard

_CATALOG_PATH = pathlib.Path(__file__).resolve().parents[1] / "chaos" / "scenarios" / "catalog.yaml"


def _load_catalog() -> list[dict]:
    data = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    return data["scenarios"]


def test_catalog_has_twenty_scenarios():
    assert len(_load_catalog()) == 20


def test_all_experiment_ids_are_unique_and_sequential():
    ids = [s["experiment_id"] for s in _load_catalog()]
    assert len(ids) == len(set(ids))
    assert ids == [f"CHAOS-{i:02d}" for i in range(1, 21)]


def test_every_scenario_passes_the_safety_guard_structural_check():
    """Cada escenario del catálogo, si se ejecutase HOY en cyber-range con
    chaos habilitado, pasaría el chequeo estructural de ChaosSafetyGuard
    (todos los campos obligatorios presentes) -- prueba que el catálogo y
    el guard no han divergido, no solo lo afirma en prosa."""
    for scenario in _load_catalog():
        guard = ChaosSafetyGuard()
        request = ChaosExperimentRequest(
            experiment_id=scenario["experiment_id"],
            hypothesis=scenario["hypothesis"],
            target=scenario["target"],
            expected_steady_state=scenario["expected_steady_state"],
            blast_radius=scenario["blast_radius"],
            duration_seconds=scenario["duration_seconds"],
            abort_conditions=tuple(scenario["abort_conditions"]),
            recovery_procedure=scenario["recovery_procedure"],
            environment="cyber-range",
            chaos_enabled=True,
            namespace="argos-cyber-range",
        )
        result = guard.authorize(request)
        assert result.allowed is True, f"{scenario['experiment_id']}: {result.reason}"


def test_every_scenario_declares_at_least_one_quality_gate():
    for scenario in _load_catalog():
        assert scenario.get("quality_gates"), f"{scenario['experiment_id']} sin quality_gates declarados"


def test_status_is_one_of_the_known_values():
    """DESIGNED = declarado, no ejecutado. TESTED_LOCALLY = tiene una
    regresión ejecutable sin clúster real (test_ref obligatorio).
    VALIDATED_IN_TARGET (todavía ninguno) requeriría clúster real."""
    known = {"DESIGNED", "TESTED_LOCALLY", "VALIDATED_IN_TARGET"}
    for scenario in _load_catalog():
        assert scenario["status"] in known, f"{scenario['experiment_id']}: status desconocido {scenario['status']!r}"
        if scenario["status"] in {"TESTED_LOCALLY", "VALIDATED_IN_TARGET"}:
            assert scenario.get("test_ref"), f"{scenario['experiment_id']}: status={scenario['status']} sin test_ref"
