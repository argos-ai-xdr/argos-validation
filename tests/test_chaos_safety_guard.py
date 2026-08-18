from __future__ import annotations

import pytest

from chaos import ChaosExperimentRequest, ChaosSafetyGuard


def _request(**overrides: object) -> ChaosExperimentRequest:
    base: dict[str, object] = {
        "experiment_id": "CHAOS-01-run-1",
        "hypothesis": "Un pod de argos-core puede matarse sin corromper estado ni perder eventos en vuelo",
        "target": "deployment/argos-core",
        "expected_steady_state": "correlator sigue produciendo Incident v1 dentro de 30s",
        "blast_radius": "1 pod, namespace argos-cyber-range",
        "duration_seconds": 60,
        "abort_conditions": ("error_rate>0.5", "manual_abort"),
        "recovery_procedure": "kubectl rollout restart deployment/argos-core",
        "environment": "cyber-range",
        "chaos_enabled": True,
        "namespace": "argos-cyber-range",
    }
    base.update(overrides)
    return ChaosExperimentRequest(**base)  # type: ignore[arg-type]


def test_valid_experiment_is_authorized():
    guard = ChaosSafetyGuard()
    result = guard.authorize(_request())
    assert result.allowed is True


def test_chaos_disabled_is_denied():
    guard = ChaosSafetyGuard()
    result = guard.authorize(_request(chaos_enabled=False))
    assert result.allowed is False
    assert "chaos_enabled" in result.reason


@pytest.mark.parametrize("environment", ["production", "staging", "prod-eu-1"])
def test_non_validation_environment_is_denied(environment):
    guard = ChaosSafetyGuard()
    result = guard.authorize(_request(environment=environment))
    assert result.allowed is False
    assert "environment" in result.reason


def test_namespace_outside_allowlist_is_denied():
    guard = ChaosSafetyGuard()
    result = guard.authorize(_request(namespace="production-payments"))
    assert result.allowed is False
    assert "namespace" in result.reason


@pytest.mark.parametrize(
    "field,empty_value",
    [
        ("experiment_id", ""),
        ("hypothesis", ""),
        ("target", ""),
        ("expected_steady_state", ""),
        ("blast_radius", ""),
        ("recovery_procedure", ""),
        ("abort_conditions", ()),
    ],
)
def test_missing_mandatory_field_is_denied(field, empty_value):
    guard = ChaosSafetyGuard()
    result = guard.authorize(_request(**{field: empty_value}))
    assert result.allowed is False
    assert field in result.reason


def test_max_parallel_experiments_is_enforced():
    guard = ChaosSafetyGuard(max_parallel_experiments=1)
    first = guard.authorize(_request(experiment_id="exp-1"))
    second = guard.authorize(_request(experiment_id="exp-2"))
    assert first.allowed is True
    assert second.allowed is False
    assert "max_parallel_experiments" in second.reason


def test_completing_an_experiment_frees_the_slot():
    guard = ChaosSafetyGuard(max_parallel_experiments=1)
    guard.authorize(_request(experiment_id="exp-1"))
    guard.complete_experiment("exp-1")
    second = guard.authorize(_request(experiment_id="exp-2"))
    assert second.allowed is True


def test_same_experiment_id_cannot_be_authorized_twice_while_active():
    """Anti-replay: un experiment_id ya activo no puede volver a
    autorizarse -- evita que un reintento accidental duplique el
    experimento sobre el mismo target mientras el primero sigue en curso."""
    guard = ChaosSafetyGuard(max_parallel_experiments=5)
    first = guard.authorize(_request(experiment_id="exp-1"))
    second = guard.authorize(_request(experiment_id="exp-1"))
    assert first.allowed is True
    assert second.allowed is False
    assert "replay" in second.reason


def test_production_action_never_reuses_this_authorization_space():
    """Prueba estructural del invariante de ADR-068: ChaosAuthorizationResult
    no expone ningún campo (downstream_credential, approval, etc.) que un
    ejecutor de mcp_gateway pudiera consumir como si fuera una autorización
    real -- son tipos disjuntos a propósito."""
    guard = ChaosSafetyGuard()
    result = guard.authorize(_request())
    assert set(vars(result).keys()) == {"allowed", "reason"}
