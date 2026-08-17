from __future__ import annotations

import json
import pathlib

import pytest
import yaml

from harness.replay_capsule import build_capsule, load_capsule, main, replay, write_capsule

pytestmark = pytest.mark.filterwarnings("ignore")

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


def _write_checkpoints(path: pathlib.Path) -> pathlib.Path:
    checkpoints = [
        {"id": "CP02", "phase": "Descubrimiento", "evidence_files": [{"filename": "asset_diff.json", "contract": "asset-snapshot"}]},
    ]
    checkpoints_path = path / "checkpoints.yaml"
    checkpoints_path.write_text(yaml.safe_dump({"checkpoints": checkpoints}), encoding="utf-8")
    return checkpoints_path


def test_build_and_replay_clean_capsule_is_ok(contracts_path, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "asset_diff.json").write_text(json.dumps(ASSET_SNAPSHOT), encoding="utf-8")
    checkpoints_path = _write_checkpoints(tmp_path)

    manifest = build_capsule(run_dir, checkpoints_path, capsule_id="cap-001")
    assert manifest.capsule_id == "cap-001"
    assert len(manifest.files) == 1

    result = replay(manifest, run_dir, checkpoints_path, contracts_path=contracts_path)
    assert result.ok
    assert result.integrity_violations == ()


def test_replay_detects_a_file_mutated_after_capsule_was_built(contracts_path, tmp_path):
    """El núcleo de ReplayCapsule: un archivo que sigue existiendo y sigue
    validando su schema, pero cuyo CONTENIDO cambió tras capturarse la
    cápsula, debe reportarse como violación de integridad — el schema
    check por sí solo no lo detectaría (el archivo mutado puede seguir
    siendo un asset-snapshot v1 perfectamente válido, solo que distinto)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "asset_diff.json").write_text(json.dumps(ASSET_SNAPSHOT), encoding="utf-8")
    checkpoints_path = _write_checkpoints(tmp_path)

    manifest = build_capsule(run_dir, checkpoints_path, capsule_id="cap-002")

    mutated = {**ASSET_SNAPSHOT, "node": "node-DIFERENTE"}
    (run_dir / "asset_diff.json").write_text(json.dumps(mutated), encoding="utf-8")

    result = replay(manifest, run_dir, checkpoints_path, contracts_path=contracts_path)
    assert not result.ok
    assert result.checkpoint_result.ok  # sigue siendo un asset-snapshot v1 válido
    assert len(result.integrity_violations) == 1
    assert "asset_diff.json" in result.integrity_violations[0]


def test_replay_detects_a_file_deleted_after_capsule_was_built(contracts_path, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "asset_diff.json").write_text(json.dumps(ASSET_SNAPSHOT), encoding="utf-8")
    checkpoints_path = _write_checkpoints(tmp_path)

    manifest = build_capsule(run_dir, checkpoints_path, capsule_id="cap-003")
    (run_dir / "asset_diff.json").unlink()

    result = replay(manifest, run_dir, checkpoints_path, contracts_path=contracts_path)
    assert not result.ok
    assert not result.checkpoint_result.ok  # falta también como checkpoint
    assert any("ausente en run_dir" in v for v in result.integrity_violations)


def test_capsule_never_invents_a_file_that_does_not_exist_in_run_dir(tmp_path):
    """Un checkpoint declarado sin evidencia real en disco (p.ej. CP00 en
    el sample-run real) no debe aparecer en la cápsula — build_capsule no
    fabrica un archivo ni un hash de la nada."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()  # vacío a propósito
    checkpoints_path = _write_checkpoints(tmp_path)

    manifest = build_capsule(run_dir, checkpoints_path, capsule_id="cap-004")
    assert manifest.files == ()


def test_write_and_load_capsule_roundtrip(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "asset_diff.json").write_text(json.dumps(ASSET_SNAPSHOT), encoding="utf-8")
    checkpoints_path = _write_checkpoints(tmp_path)

    manifest = build_capsule(run_dir, checkpoints_path, capsule_id="cap-005")
    out_path = tmp_path / "capsule.json"
    write_capsule(manifest, out_path)

    loaded = load_capsule(out_path)
    assert loaded == manifest


def test_the_real_argos_cyb_01_sample_run_replays_with_no_integrity_violations(contracts_path):
    """Integración contra el sample-run real: una cápsula construida sobre
    él y re-reproducida en el mismo directorio no debe reportar ninguna
    violación de integridad (nada mutó). El checkpoint_result sigue
    fallando en CP00/CP01/CP12 -- ese es un gap real y conocido (exige un
    cyber-range real), no algo que ReplayCapsule deba ocultar."""
    checkpoints_path = contracts_path / "scenarios" / "ARGOS-CYB-01" / "checkpoints" / "checkpoints.yaml"
    run_dir = contracts_path / "scenarios" / "ARGOS-CYB-01" / "expected" / "sample-run"
    if not checkpoints_path.exists() or not run_dir.exists():
        pytest.skip("checkpoints.yaml o expected/sample-run no disponibles en este checkout")

    manifest = build_capsule(run_dir, checkpoints_path, capsule_id="cap-argos-cyb-01-sample")
    # 11 checkpoints con evidencia real hoy, pero CP13 aporta 2 archivos
    # (handover.json + manifest.json) -> 12 archivos en la cápsula.
    assert len(manifest.files) == 12

    result = replay(manifest, run_dir, checkpoints_path, contracts_path=contracts_path)
    assert result.integrity_violations == ()
    requires_real_cluster = {"CP00", "CP01", "CP12"}
    failing = {s.cp_id for s in result.checkpoint_result.statuses if not s.ok}
    assert failing == requires_real_cluster


def test_main_cli_build_then_replay_round_trip(contracts_path, tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "asset_diff.json").write_text(json.dumps(ASSET_SNAPSHOT), encoding="utf-8")
    checkpoints_path = _write_checkpoints(tmp_path)
    capsule_path = tmp_path / "capsule.json"

    exit_code = main(
        ["build", "--run-dir", str(run_dir), "--checkpoints", str(checkpoints_path), "--capsule-id", "cli-cap", "--out", str(capsule_path)]
    )
    assert exit_code == 0
    assert capsule_path.exists()
    assert "cli-cap" in capsys.readouterr().out

    exit_code = main(
        ["replay", "--capsule", str(capsule_path), "--run-dir", str(run_dir), "--checkpoints", str(checkpoints_path)]
    )
    assert exit_code == 0
    assert "replay overall=OK" in capsys.readouterr().out


def test_main_cli_replay_reports_integrity_violation_and_exits_1(contracts_path, tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "asset_diff.json").write_text(json.dumps(ASSET_SNAPSHOT), encoding="utf-8")
    checkpoints_path = _write_checkpoints(tmp_path)
    capsule_path = tmp_path / "capsule.json"

    main(["build", "--run-dir", str(run_dir), "--checkpoints", str(checkpoints_path), "--capsule-id", "cli-cap", "--out", str(capsule_path)])
    capsys.readouterr()

    (run_dir / "asset_diff.json").write_text(json.dumps({**ASSET_SNAPSHOT, "node": "tampered"}), encoding="utf-8")

    exit_code = main(
        ["replay", "--capsule", str(capsule_path), "--run-dir", str(run_dir), "--checkpoints", str(checkpoints_path)]
    )
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "INTEGRIDAD" in out
    assert "replay overall=FAIL" in out
