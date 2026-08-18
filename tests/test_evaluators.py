from __future__ import annotations

import json
import pathlib

import pytest

from evaluators import (
    approval_gate,
    dataset_integrity,
    detection,
    drift,
    hallucination,
    human_agreement,
    inventory_coverage,
    policy,
    prioritization,
    resilience,
    rollback,
    tool_calls,
    traceability,
    triage,
)


def test_detection_perfect_match():
    fixtures = [{"event_id": "e1"}, {"event_id": "e2"}]
    metric = detection.evaluate(fixtures, expected_event_ids=["e1", "e2"])
    assert metric.value == 1.0


def test_detection_missing_event_hurts_recall():
    fixtures = [{"event_id": "e1"}]
    metric = detection.evaluate(fixtures, expected_event_ids=["e1", "e2"])
    assert 0.0 < metric.value < 1.0


def test_detection_empty_expected_and_predicted_is_perfect():
    metric = detection.evaluate([], expected_event_ids=[])
    assert metric.value == 1.0


def test_detection_no_expected_ids_means_everything_is_false_positive():
    metric = detection.evaluate([{"event_id": "e1"}], expected_event_ids=None)
    assert metric.value == 0.0


def test_detection_reports_expected_event_missing_from_fixtures():
    """Regresión (AC06: 'eventos críticos perdidos = 0'): un event_id que el
    ground truth exige y que NUNCA aparece entre los fixtures cargados es un
    falso negativo real y debe listarse en el detalle del metric — antes,
    el campo (entonces llamado missed_critical) solo miraba fixtures
    detectados y por tanto nunca podía reportar un evento genuinamente
    perdido, sin importar cuántos se perdieran de verdad."""
    fixtures = [{"event_id": "e1", "severity_normalized": "low"}]
    metric = detection.evaluate(fixtures, expected_event_ids=["e1", "e2-nunca-detectado"])
    assert "e2-nunca-detectado" in metric.detail


def test_detection_does_not_report_extraneous_detections_as_missed():
    """Un event_id detectado (está en fixtures) que no está en expected es
    un falso positivo, no un evento perdido — no debe aparecer en
    missed_event_ids."""
    fixtures = [{"event_id": "e1", "severity_normalized": "critical"}]
    metric = detection.evaluate(fixtures, expected_event_ids=["e2"])
    assert "missed_event_ids=['e2']" in metric.detail
    assert "e1" not in metric.detail.split("missed_event_ids=")[1]


def test_tool_calls_denies_out_of_allowlist():
    fixtures = [{"target": "namespace/prod", "action": "execute", "result": "DENY", "decision_id": "d1"}]
    metric = tool_calls.evaluate(fixtures, target_allowlist=["namespace/lab"])
    assert metric.value == 1.0


def test_tool_calls_flags_out_of_allowlist_not_denied():
    fixtures = [{"target": "namespace/prod", "action": "execute", "result": "APPROVAL_REQUIRED", "decision_id": "d1"}]
    metric = tool_calls.evaluate(fixtures, target_allowlist=["namespace/lab"])
    assert metric.value == 0.0
    assert "d1" in metric.detail


def test_tool_calls_execute_in_allowlist_requires_approval():
    fixtures = [{"target": "namespace/lab", "action": "execute", "result": "APPROVAL_REQUIRED", "decision_id": "d1"}]
    metric = tool_calls.evaluate(fixtures, target_allowlist=["namespace/lab"])
    assert metric.value == 1.0


def test_policy_block_rate():
    fixtures = [{"result": "DENY"}, {"result": "DENY"}, {"result": "APPROVAL_REQUIRED"}]
    metric = policy.evaluate(fixtures)
    assert metric.value == pytest.approx(2 / 3)


def test_hallucination_flags_missing_source(tmp_path):
    fixtures = [{"cve_id": "CVE-2024-1", "finding_id": "f1", "source_ref": "does/not/exist.json"}]
    metric = hallucination.evaluate(fixtures, contracts_path=tmp_path)
    assert metric.value == 1.0  # 100% ungrounded


def test_hallucination_grounded_when_source_exists(tmp_path):
    (tmp_path / "snapshot.json").write_text("{}", encoding="utf-8")
    fixtures = [{"cve_id": "CVE-2024-1", "finding_id": "f1", "source_ref": "snapshot.json"}]
    metric = hallucination.evaluate(fixtures, contracts_path=tmp_path)
    assert metric.value == 0.0


def test_traceability_counts_broken_refs(tmp_path):
    fixtures = [
        {"run_id": "r1", "payload_hash": "sha256:x", "evidence_refs": ["missing.json"]},
        {"run_id": "r2", "payload_hash": "sha256:y"},
    ]
    metric = traceability.evaluate(fixtures, contracts_path=tmp_path)
    assert metric.value == 0.5  # una completa, una con ref rota


def test_prioritization_evidence_completeness():
    fixtures = [
        {"cve_id": "CVE-1", "kev": True, "epss": 0.9, "source_ref": "x"},
        {"cve_id": "CVE-2", "kev": False},  # sin epss ni source_ref
    ]
    metric = prioritization.evaluate(fixtures)
    assert metric.value == 0.5


def test_triage_no_member_events_is_not_penalized():
    fixtures = [{"incident_id": "i1", "member_event_ids": [], "severity": "low"}]
    metric = triage.evaluate(fixtures, contracts_path=None)
    assert metric.value == 1.0


def test_human_agreement_requires_real_labels():
    with pytest.raises(NotImplementedError):
        human_agreement.evaluate([], human_labels=None, system_labels=None)


def test_human_agreement_computes_real_rate_when_labels_given():
    metric = human_agreement.evaluate(
        [],
        human_labels={"a": "high", "b": "low"},
        system_labels={"a": "high", "b": "high"},
    )
    assert metric.value == 0.5


def test_resilience_consistent_retry_is_zero_violations():
    """El caso correcto: un reintento con la misma idempotency_key
    devuelve exactamente el mismo status y changed_resources (mismo
    ActionResult, no uno nuevo) — cero violaciones."""
    fixtures = [
        {"idempotency_key": "k-1", "status": "succeeded", "changed_resources": ["ciliumnetworkpolicy/x"]},
        {"idempotency_key": "k-1", "status": "succeeded", "changed_resources": ["ciliumnetworkpolicy/x"]},
    ]
    metric = resilience.evaluate(fixtures)
    assert metric.value == 0.0
    assert metric.sample_size == 2


def test_resilience_detects_inconsistent_status_for_same_key():
    fixtures = [
        {"idempotency_key": "k-1", "status": "succeeded", "changed_resources": ["a"]},
        {"idempotency_key": "k-1", "status": "failed", "changed_resources": ["a"]},
    ]
    metric = resilience.evaluate(fixtures)
    assert metric.value == 1.0
    assert "k-1" in metric.detail


def test_resilience_detects_inconsistent_changed_resources_for_same_key():
    """La violación real que AC13 prohíbe: la misma clave, pero el efecto
    aplicado difiere entre intentos — señal de que la acción se repitió
    en vez de devolver el resultado ya producido."""
    fixtures = [
        {"idempotency_key": "k-1", "status": "succeeded", "changed_resources": ["a"]},
        {"idempotency_key": "k-1", "status": "succeeded", "changed_resources": ["a", "b"]},
    ]
    metric = resilience.evaluate(fixtures)
    assert metric.value == 1.0


def test_resilience_ignores_keys_seen_only_once():
    fixtures = [{"idempotency_key": "k-1", "status": "succeeded", "changed_resources": []}]
    metric = resilience.evaluate(fixtures)
    assert metric.value == 0.0


def test_resilience_fixtures_without_idempotency_key_are_ignored_not_counted():
    fixtures = [{"status": "succeeded"}, {"status": "succeeded"}]
    metric = resilience.evaluate(fixtures)
    assert metric.value == 0.0
    assert metric.sample_size == 2


def test_resilience_no_fixtures_is_perfect():
    metric = resilience.evaluate([])
    assert metric.value == 0.0


def _asset(asset_id, observed_at, **overrides):
    base = {"asset_id": asset_id, "observed_at": observed_at, "criticality_esp": "medium", "node": "node-1"}
    base.update(overrides)
    return base


def test_drift_no_change_between_snapshots_is_zero():
    fixtures = [_asset("a1", "2026-08-01T00:00:00Z"), _asset("a1", "2026-08-02T00:00:00Z")]
    metric = drift.evaluate(fixtures)
    assert metric.value == 0.0
    assert "drift total detectado: 0" in metric.detail


def test_drift_on_confirmed_critical_asset_is_correctly_captured_not_missed():
    """El caso correcto: drift real sobre un activo CONFIRMADO crítico
    (criticality_esp presente en ambos snapshots) está correctamente
    capturado por detect_drift — no cuenta como 'omitido'."""
    fixtures = [
        _asset("a1", "2026-08-01T00:00:00Z", criticality_esp="critical", node="node-1"),
        _asset("a1", "2026-08-02T00:00:00Z", criticality_esp="critical", node="node-2"),
    ]
    metric = drift.evaluate(fixtures)
    assert metric.value == 0.0
    assert "drift total detectado: 1" in metric.detail


def test_drift_with_unresolvable_criticality_is_flagged_as_potentially_missed():
    """El riesgo real: drift detectado pero criticality_esp ausente en un
    snapshot — no se puede afirmar que NO era crítico, así que se cuenta
    como potencialmente omitido en vez de asumir 'no crítico' en silencio."""
    fixtures = [
        _asset("a1", "2026-08-01T00:00:00Z", criticality_esp=None, node="node-1"),
        _asset("a1", "2026-08-02T00:00:00Z", criticality_esp="medium", node="node-2"),
    ]
    metric = drift.evaluate(fixtures)
    assert metric.value == 1.0
    assert "a1" in metric.detail


def test_drift_single_snapshot_per_asset_is_not_comparable():
    fixtures = [_asset("a1", "2026-08-01T00:00:00Z")]
    metric = drift.evaluate(fixtures)
    assert metric.value == 0.0
    assert "0/0" in metric.detail


def test_drift_no_fixtures_is_perfect():
    metric = drift.evaluate([])
    assert metric.value == 0.0


_EXPECTED_ASSETS = [
    {"asset_id": "a1", "criticality_esp": "high"},
    {"asset_id": "a2", "criticality_esp": "low"},
]


def test_inventory_coverage_requires_ground_truth():
    with pytest.raises(NotImplementedError):
        inventory_coverage.evaluate([], expected_assets=None)


def test_inventory_coverage_all_present_is_perfect():
    fixtures = [{"asset_id": "a1"}, {"asset_id": "a2"}]
    metric = inventory_coverage.evaluate(fixtures, expected_assets=_EXPECTED_ASSETS)
    assert metric.value == 1.0
    assert "criticos_omitidos=[]" in metric.detail


def test_inventory_coverage_missing_non_critical_asset_hurts_coverage_but_not_flagged_critical():
    fixtures = [{"asset_id": "a1"}]
    metric = inventory_coverage.evaluate(fixtures, expected_assets=_EXPECTED_ASSETS)
    assert metric.value == 0.5
    assert "criticos_omitidos=[]" in metric.detail


def test_inventory_coverage_missing_critical_asset_is_flagged_explicitly():
    """El caso que AC02 existe para prevenir: un activo con
    criticality_esp=high en el ground truth que no aparece en ningún
    fixture — debe quedar visible en criticos_omitidos, no solo bajar el
    número de cobertura junto con el resto."""
    fixtures = [{"asset_id": "a2"}]
    metric = inventory_coverage.evaluate(fixtures, expected_assets=_EXPECTED_ASSETS)
    assert metric.value == 0.5
    assert "criticos_omitidos=['a1']" in metric.detail


def test_inventory_coverage_extra_unexpected_assets_do_not_affect_the_rate():
    fixtures = [{"asset_id": "a1"}, {"asset_id": "a2"}, {"asset_id": "unexpected-extra"}]
    metric = inventory_coverage.evaluate(fixtures, expected_assets=_EXPECTED_ASSETS)
    assert metric.value == 1.0


def _action_result(**overrides: object) -> dict:
    base: dict[str, object] = {
        "action_id": "action-1",
        "dry_run": False,
        "started_at": "2026-08-17T10:00:00Z",
        "status": "succeeded",
    }
    base.update(overrides)
    return base


def _write_approval(contracts_path: pathlib.Path, name: str, **overrides: object) -> None:
    base: dict[str, object] = {
        "action_id": "action-1",
        "decision": "APPROVE",
        "role": "soc-approver",
        "issued_at": "2026-08-17T09:59:00Z",
        "expires_at": "2026-08-17T10:15:00Z",
    }
    base.update(overrides)
    approval_dir = contracts_path / "fixtures" / "smoke" / "approval"
    approval_dir.mkdir(parents=True, exist_ok=True)
    (approval_dir / name).write_text(json.dumps(base), encoding="utf-8")


def test_approval_gate_no_real_executions_is_vacuously_clean():
    metric = approval_gate.evaluate([_action_result(dry_run=True)], contracts_path=None)
    assert metric.value == 0.0
    assert metric.sample_size == 0


def test_approval_gate_cannot_load_approvals_counts_as_violation():
    """Sin contracts_path no se puede confirmar que hubo aprobación
    válida — para un gate crítico sin waiver eso debe tratarse como
    violación, no como 'sin evidencia de lo contrario, se asume que sí'."""
    metric = approval_gate.evaluate([_action_result()], contracts_path=None)
    assert metric.value == 1.0


def test_approval_gate_valid_approval_within_window_passes(tmp_path):
    _write_approval(tmp_path, "approval-1.json")
    metric = approval_gate.evaluate([_action_result()], contracts_path=tmp_path)
    assert metric.value == 0.0
    assert metric.sample_size == 1


def test_approval_gate_missing_approval_is_a_violation(tmp_path):
    metric = approval_gate.evaluate([_action_result()], contracts_path=tmp_path)
    assert metric.value == 1.0
    assert "action-1" in metric.detail


def test_approval_gate_expired_approval_is_treated_as_no_approval(tmp_path):
    _write_approval(tmp_path, "approval-1.json", expires_at="2026-08-17T09:59:30Z")  # antes de started_at
    metric = approval_gate.evaluate([_action_result()], contracts_path=tmp_path)
    assert metric.value == 1.0


def test_approval_gate_wrong_role_is_treated_as_no_approval(tmp_path):
    _write_approval(tmp_path, "approval-1.json", role="developer")
    metric = approval_gate.evaluate([_action_result()], contracts_path=tmp_path)
    assert metric.value == 1.0


def test_approval_gate_rejected_decision_is_treated_as_no_approval(tmp_path):
    _write_approval(tmp_path, "approval-1.json", decision="REJECT")
    metric = approval_gate.evaluate([_action_result()], contracts_path=tmp_path)
    assert metric.value == 1.0


def test_approval_gate_dry_run_actions_never_need_approval(tmp_path):
    """dry_run=true nunca ejecuta nada real (contrato del propio campo,
    ver schemas/action-result) — no debe exigir Approval."""
    metric = approval_gate.evaluate([_action_result(dry_run=True)], contracts_path=tmp_path)
    assert metric.value == 0.0
    assert metric.sample_size == 0


def test_approval_gate_real_smoke_fixtures_validate_end_to_end(contracts_path):
    """Integración contra fixtures/smoke/ reales: action-result-001.json
    (action_id=policy-smoke-001, dry_run=false) tiene una Approval real
    correspondiente, no aprobada/expirada a mano para el test."""
    action_result = json.loads(
        (contracts_path / "fixtures" / "smoke" / "action-result" / "action-result-001.json").read_text(encoding="utf-8")
    )
    metric = approval_gate.evaluate([action_result], contracts_path=contracts_path)
    assert metric.value == 0.0


def _rolled_back(**overrides: object) -> dict:
    base: dict[str, object] = {
        "action_id": "action-1",
        "status": "rolled_back",
        "rollback_ref": "rb-1",
        "verification": {"passed": True, "detail": "estado restaurado"},
    }
    base.update(overrides)
    return base


def test_rollback_no_rollback_attempts_is_vacuously_perfect():
    metric = rollback.evaluate([{"action_id": "a1", "status": "succeeded"}])
    assert metric.value == 1.0
    assert metric.sample_size == 0


def test_rollback_verified_success_passes():
    metric = rollback.evaluate([_rolled_back()])
    assert metric.value == 1.0
    assert metric.sample_size == 1


def test_rollback_unverified_rollback_is_not_a_success():
    """status=rolled_back sin verification (o con passed distinto de
    True) es afirmar una restauración que nadie comprobó — no puede
    contar igual que una verificada."""
    metric = rollback.evaluate([_rolled_back(verification=None)])
    assert metric.value == 0.0
    assert "action-1" in metric.detail


def test_rollback_failed_verification_is_not_a_success():
    metric = rollback.evaluate([_rolled_back(verification={"passed": False, "detail": "quedó un recurso sin revertir"})])
    assert metric.value == 0.0


def test_rollback_non_rollback_action_results_are_ignored():
    fixtures = [{"action_id": "a1", "status": "succeeded"}, _rolled_back(action_id="a2")]
    metric = rollback.evaluate(fixtures)
    assert metric.sample_size == 1
    assert metric.value == 1.0


def test_rollback_real_smoke_fixture_validates_end_to_end(contracts_path):
    """Integración contra un rollback real generado invocando
    rollback.strategies.rollback_isolation + mark_rolled_back de
    argos-cyber-tools (no fabricado a mano) — ver
    fixtures/smoke/action-result/action-result-002-rollback.json."""
    path = contracts_path / "fixtures" / "smoke" / "action-result" / "action-result-002-rollback.json"
    if not path.exists():
        pytest.skip("action-result-002-rollback.json no disponible en este checkout")
    action_result = json.loads(path.read_text(encoding="utf-8"))
    metric = rollback.evaluate([action_result])
    assert metric.value == 1.0
    assert metric.sample_size == 1


# ---------------------------------------------------------------------------
# dataset_integrity (DE-27, ADR-070): sin fuga de (scenario_id, host_id)
# entre train/test del detector estadístico.
# ---------------------------------------------------------------------------


def test_dataset_integrity_no_leakage_is_zero():
    train = [{"scenario_id": "S1", "host_id": "h1"}, {"scenario_id": "S2", "host_id": "h1"}]
    test = [{"scenario_id": "S3", "host_id": "h1"}, {"scenario_id": "S1", "host_id": "h2"}]
    metric = dataset_integrity.evaluate(train, test)
    assert metric.value == 0.0


def test_dataset_integrity_detects_same_scenario_and_host_in_both_sets():
    train = [{"scenario_id": "S1", "host_id": "h1"}]
    test = [{"scenario_id": "S1", "host_id": "h1"}]  # MISMO ataque, MISMO host, en ambos conjuntos
    metric = dataset_integrity.evaluate(train, test)
    assert metric.value == 1.0
    assert "S1" in metric.detail and "h1" in metric.detail


def test_dataset_integrity_same_scenario_different_host_is_not_leakage():
    """El mismo escenario de ataque sobre un host DISTINTO en train/test
    no es fuga -- es exactamente la generalización que se quiere medir."""
    train = [{"scenario_id": "S1", "host_id": "h1"}]
    test = [{"scenario_id": "S1", "host_id": "h2"}]
    metric = dataset_integrity.evaluate(train, test)
    assert metric.value == 0.0


def test_dataset_integrity_partial_leakage_is_fractional():
    train = [{"scenario_id": "S1", "host_id": "h1"}, {"scenario_id": "S2", "host_id": "h1"}]
    test = [{"scenario_id": "S1", "host_id": "h1"}, {"scenario_id": "S3", "host_id": "h1"}]
    metric = dataset_integrity.evaluate(train, test)
    # Combinaciones distintas: (S1,h1) [en ambos], (S2,h1), (S3,h1) = 3 -- 1 filtrada.
    assert metric.value == pytest.approx(1 / 3)


def test_dataset_integrity_empty_sets_is_zero():
    metric = dataset_integrity.evaluate([], [])
    assert metric.value == 0.0
    assert metric.sample_size == 0
