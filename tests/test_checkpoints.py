from __future__ import annotations

import json
import pathlib

import pytest

from harness.checkpoints import load_checkpoints, validate_run

pytestmark = pytest.mark.filterwarnings("ignore")


def _write(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


ASSET_SNAPSHOT = {
    "id": "01J0TEST0000000000000001",
    "schema_version": "1.0.0",
    "observed_at": "2026-08-17T09:00:00Z",
    "producer": "test",
    "classification": "internal",
    "run_id": "run-test-001",
    "payload_hash": "sha256:" + "0" * 64,
    "asset_id": "asset-x",
    "workload_id": "deployment/x",
    "image_ref": "registry/x@sha256:" + "1" * 64,
    "node": "node-1",
    "namespace": "argos-cyber-range",
    "criticality_esp": "high",
}


def test_checkpoint_with_valid_evidence_and_matching_run_id_passes(contracts_path, tmp_path):
    checkpoints = [
        {"id": "CP02", "phase": "Descubrimiento", "evidence_files": [{"filename": "asset_diff.json", "contract": "asset-snapshot"}]},
    ]
    _write(tmp_path / "asset_diff.json", ASSET_SNAPSHOT)

    result = validate_run(tmp_path, checkpoints, contracts_path=contracts_path)

    assert result.ok
    assert result.missing == ()
    assert result.schema_invalid == ()
    assert result.run_ids_seen == ("run-test-001",)


def test_missing_evidence_file_is_reported_not_silently_skipped(contracts_path, tmp_path):
    checkpoints = [
        {"id": "CP02", "phase": "Descubrimiento", "evidence_files": [{"filename": "asset_diff.json", "contract": "asset-snapshot"}]},
    ]
    result = validate_run(tmp_path, checkpoints, contracts_path=contracts_path)

    assert not result.ok
    assert result.missing == ("CP02",)


def test_evidence_that_fails_its_contract_schema_is_reported(contracts_path, tmp_path):
    checkpoints = [
        {"id": "CP02", "phase": "Descubrimiento", "evidence_files": [{"filename": "asset_diff.json", "contract": "asset-snapshot"}]},
    ]
    broken = {**ASSET_SNAPSHOT}
    del broken["asset_id"]  # campo obligatorio del schema real
    _write(tmp_path / "asset_diff.json", broken)

    result = validate_run(tmp_path, checkpoints, contracts_path=contracts_path)

    assert not result.ok
    assert result.schema_invalid == ("CP02",)


def test_internal_checkpoint_without_contract_only_checks_presence(contracts_path, tmp_path):
    """CP00/01/04/05/12 no tienen uno de los 10 contratos v1 — el
    validador no debe inventar un schema, solo comprobar que el archivo
    existe (cualquier JSON vale, incluso uno sin run_id)."""
    checkpoints = [{"id": "CP00", "phase": "Reset", "evidence_files": [{"filename": "baseline_manifest.json", "contract": None}]}]
    _write(tmp_path / "baseline_manifest.json", {"anything": "goes"})

    result = validate_run(tmp_path, checkpoints, contracts_path=contracts_path)

    assert result.ok


def test_mismatched_run_id_across_checkpoints_breaks_trace_consistency(contracts_path, tmp_path):
    """El núcleo de ARG-023: dos checkpoints que en teoría pertenecen al
    mismo run pero en la práctica traen run_id distintos deben marcar la
    trazabilidad como rota, no pasar en silencio."""
    checkpoints = [
        {"id": "CP02", "phase": "Descubrimiento", "evidence_files": [{"filename": "asset_diff.json", "contract": "asset-snapshot"}]},
        {"id": "CP03", "phase": "Vulnerabilidad", "evidence_files": [{"filename": "vulnerability_findings.json", "contract": "vulnerability-finding"}]},
    ]
    _write(tmp_path / "asset_diff.json", ASSET_SNAPSHOT)
    finding = {**ASSET_SNAPSHOT, "run_id": "run-DIFFERENT-002"}
    _write(tmp_path / "vulnerability_findings.json", finding)

    result = validate_run(tmp_path, checkpoints, contracts_path=contracts_path)

    assert not result.trace_consistent
    assert not result.ok
    assert set(result.run_ids_seen) == {"run-test-001", "run-DIFFERENT-002"}


def test_ndjson_checkpoint_validates_every_line_against_the_schema(contracts_path, tmp_path):
    security_event = {
        "id": "01J0TEST0000000000000002",
        "schema_version": "1.0.0",
        "observed_at": "2026-08-17T09:00:00Z",
        "producer": "test",
        "classification": "internal",
        "run_id": "run-test-001",
        "payload_hash": "sha256:" + "0" * 64,
        "native_ref": "wazuh://alert/1",
        "event_id": "evt-test-001",
        "source": "wazuh",
        "asset_id": "asset-x",
        "severity_native": "critical",
        "severity_normalized": "critical",
    }
    (tmp_path / "events.ndjson").write_text(json.dumps(security_event) + "\n" + json.dumps(security_event) + "\n", encoding="utf-8")
    checkpoints = [{"id": "CP06", "phase": "Telemetría", "evidence_files": [{"filename": "events.ndjson", "contract": "security-event", "format": "ndjson"}]}]

    result = validate_run(tmp_path, checkpoints, contracts_path=contracts_path)

    assert result.ok
    assert result.run_ids_seen == ("run-test-001",)


def test_ndjson_with_mixed_run_ids_is_flagged_within_a_single_file(contracts_path, tmp_path):
    base = {
        "id": "01J0TEST0000000000000003",
        "schema_version": "1.0.0",
        "observed_at": "2026-08-17T09:00:00Z",
        "producer": "test",
        "classification": "internal",
        "payload_hash": "sha256:" + "0" * 64,
        "native_ref": "wazuh://alert/1",
        "event_id": "evt-test-002",
        "source": "wazuh",
        "asset_id": "asset-x",
        "severity_native": "critical",
        "severity_normalized": "critical",
    }
    line1 = {**base, "run_id": "run-a"}
    line2 = {**base, "run_id": "run-b"}
    (tmp_path / "events.ndjson").write_text(json.dumps(line1) + "\n" + json.dumps(line2) + "\n", encoding="utf-8")
    checkpoints = [{"id": "CP06", "phase": "Telemetría", "evidence_files": [{"filename": "events.ndjson", "contract": "security-event", "format": "ndjson"}]}]

    result = validate_run(tmp_path, checkpoints, contracts_path=contracts_path)

    assert not result.ok
    assert result.schema_invalid == ("CP06",)


def test_the_real_argos_cyb_01_sample_run_validates_the_nine_contract_backed_checkpoints(contracts_path):
    """Integración contra el sample-run real ensamblado a partir de
    fixtures/smoke/ (todos con run_id=run-smoke-001) — prueba que ARG-023
    funciona de verdad, no solo con datos sintéticos de test. Los 5
    checkpoints sin contrato v1 (CP00/01/04/05/12) siguen siendo un gap
    real y conocido: no hay artefacto que capturarles todavía."""
    checkpoints_path = contracts_path / "scenarios" / "ARGOS-CYB-01" / "checkpoints" / "checkpoints.yaml"
    run_dir = contracts_path / "scenarios" / "ARGOS-CYB-01" / "expected" / "sample-run"
    if not checkpoints_path.exists() or not run_dir.exists():
        pytest.skip("checkpoints.yaml o expected/sample-run no disponibles en este checkout")

    result = validate_run(run_dir, load_checkpoints(checkpoints_path), contracts_path=contracts_path)

    contract_backed = {"CP02", "CP03", "CP06", "CP07", "CP08", "CP09", "CP10", "CP11", "CP13"}
    internal_only = {"CP00", "CP01", "CP04", "CP05", "CP12"}

    failing = {s.cp_id for s in result.statuses if not s.ok}
    assert failing == internal_only  # gap conocido, no oculto
    assert result.run_ids_seen == ("run-smoke-001",)

    passing = {s.cp_id for s in result.statuses if s.ok}
    assert passing == contract_backed
