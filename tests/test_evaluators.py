from __future__ import annotations

import pytest

from evaluators import (
    detection,
    hallucination,
    human_agreement,
    policy,
    prioritization,
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
