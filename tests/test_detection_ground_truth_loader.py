"""IDLAB-05/06 (ADR-070): el formato y el loader son reales y probados,
aunque ningún dato de aquí sea telemetría capturada de verdad todavía
(BLOCKED_EXTERNAL, ver ground-truth/README.md).
"""
from __future__ import annotations

import pathlib

import pytest
import yaml

from evaluators import dataset_integrity
from harness.loaders.detection_ground_truth import (
    InvalidGroundTruthManifest,
    load_detection_ground_truth_manifest,
    load_nominal_baseline_manifest,
    split_records_for_dataset_integrity,
)

_MANIFESTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "ground-truth" / "manifests"


def test_loads_the_real_nominal_baseline_example():
    manifest = load_nominal_baseline_manifest(_MANIFESTS_DIR / "idlab-05-nominal-baseline-example.yaml")
    assert manifest["baseline_id"] == "idlab-05-example-001"
    assert manifest["known_attacks_present"] is False
    assert len(manifest["hosts"]) == 3


def test_nominal_baseline_with_known_attacks_present_true_is_rejected(tmp_path):
    bad = {
        "baseline_id": "bad-1",
        "capture_window": {"start": "2026-08-18T00:00:00Z", "end": "2026-08-18T01:00:00Z"},
        "hosts": ["h1"],
        "source_mode": "SYNTHETIC",
        "known_attacks_present": True,  # un baseline "nominal" con ataques no es nominal
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(InvalidGroundTruthManifest):
        load_nominal_baseline_manifest(path)


def test_nominal_baseline_rejects_candidate_source_mode(tmp_path):
    bad = {
        "baseline_id": "bad-2",
        "capture_window": {"start": "2026-08-18T00:00:00Z", "end": "2026-08-18T01:00:00Z"},
        "hosts": ["h1"],
        "source_mode": "CANDIDATE",  # un baseline de entrada nunca es un artefacto de ARGOS
        "known_attacks_present": False,
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(InvalidGroundTruthManifest):
        load_nominal_baseline_manifest(path)


def test_loads_the_real_detection_ground_truth_example():
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    assert manifest["dataset_id"] == "idlab-06-example-001"
    assert len(manifest["records"]) == 5


def test_split_records_separates_by_declared_split_field():
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    train, test = split_records_for_dataset_integrity(manifest)
    assert len(train) == 3
    assert len(test) == 2
    assert {r["scenario_id"] for r in train} == {"S1", "S2"}
    assert {r["scenario_id"] for r in test} == {"S3", "S4"}


def test_end_to_end_example_manifest_has_zero_leakage_through_de27():
    """La prueba real de que IDLAB-06 y DE-27 encajan: el manifiesto de
    ejemplo, cargado y dividido por este loader, produce leakage_rate=0.0
    cuando se pasa DIRECTAMENTE a evaluators.dataset_integrity.evaluate."""
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    train, test = split_records_for_dataset_integrity(manifest)
    metric = dataset_integrity.evaluate(train, test)
    assert metric.value == 0.0


def test_end_to_end_deliberately_leaking_manifest_is_caught_by_de27(tmp_path):
    """Control negativo: un manifiesto que SÍ repite (scenario_id,
    host_id) entre train y test debe producir leakage_rate > 0 cuando
    pasa por el mismo camino real -- confirma que DE-27 detectaría un
    manifiesto IDLAB-06 mal construido, no solo datos sintéticos de test
    unitario aislados."""
    leaking = {
        "dataset_id": "leaking-example",
        "records": [
            {"scenario_id": "S1", "host_id": "h1", "label": "ATTACK", "source_mode": "SYNTHETIC", "split": "train"},
            {"scenario_id": "S1", "host_id": "h1", "label": "ATTACK", "source_mode": "SYNTHETIC", "split": "test"},
        ],
    }
    path = tmp_path / "leaking.yaml"
    path.write_text(yaml.safe_dump(leaking), encoding="utf-8")

    manifest = load_detection_ground_truth_manifest(path)
    train, test = split_records_for_dataset_integrity(manifest)
    metric = dataset_integrity.evaluate(train, test)
    assert metric.value == 1.0
