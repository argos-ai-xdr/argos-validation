"""IDLAB-05/06 v2 (ADR-070): el formato ScenarioRun y el loader son
reales y probados, aunque ningún dato de aquí sea telemetría capturada
de verdad todavía (BLOCKED_EXTERNAL, ver ground-truth/README.md).
"""
from __future__ import annotations

import copy
import pathlib

import pytest
import yaml

from evaluators import dataset_integrity
from harness.loaders.detection_ground_truth import (
    InvalidGroundTruthManifest,
    load_detection_ground_truth_manifest,
    load_nominal_baseline_manifest,
    scenario_runs_to_legacy_records,
    split_scenario_runs_for_dataset_integrity,
)

_MANIFESTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "ground-truth" / "manifests"


def _load_raw(name: str) -> dict:
    return yaml.safe_load((_MANIFESTS_DIR / name).read_text(encoding="utf-8"))


def _write_and_expect_invalid(tmp_path, data: dict, loader) -> InvalidGroundTruthManifest:
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(InvalidGroundTruthManifest) as excinfo:
        loader(path)
    return excinfo.value


# ---------------------------------------------------------------------------
# Formato base: carga limpia de los ejemplos reales del repo.
# ---------------------------------------------------------------------------


def test_loads_the_real_nominal_baseline_example():
    manifest = load_nominal_baseline_manifest(_MANIFESTS_DIR / "idlab-05-nominal-baseline-example.yaml")
    assert manifest["manifest_id"] == "idlab-05-example-001"
    assert manifest["dataset"]["known_attacks_present"] is False
    assert len(manifest["environment"]["monitored_targets"]) == 3


def test_loads_the_real_detection_ground_truth_example():
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    assert manifest["manifest_id"] == "idlab-06-example-001"
    assert len(manifest["scenario_runs"]) == 5


def test_split_scenario_runs_separates_by_declared_split_field():
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    train, test = split_scenario_runs_for_dataset_integrity(manifest)
    assert len(train) == 3
    assert len(test) == 2
    assert {r["scenario_id"] for r in train} == {"S1", "S2"}
    assert {r["scenario_id"] for r in test} == {"S3", "S4"}


# ---------------------------------------------------------------------------
# "clean fixture -> leakage_rate = 0.0" / "valid multi-scenario dataset ->
# PASS" / "valid temporal separation -> PASS": el ejemplo real, cargado y
# dividido por este loader, no tiene fuga en NINGUNA dimensión (legacy
# scenario_id/host_id NI las nuevas scenario_run_id/split_group/
# event_ref/evidence_ref/label_provenance) -- y sus TRAIN runs (07:05-
# 07:30) preceden por completo a sus TEST runs (08:05-08:20).
# ---------------------------------------------------------------------------


def test_end_to_end_example_manifest_has_zero_leakage_through_legacy_de27():
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    train, test = split_scenario_runs_for_dataset_integrity(manifest)
    metric = dataset_integrity.evaluate(scenario_runs_to_legacy_records(train), scenario_runs_to_legacy_records(test))
    assert metric.value == 0.0


def test_end_to_end_example_manifest_has_zero_leakage_on_every_scenario_run_check():
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    metrics = dataset_integrity.evaluate_scenario_runs(manifest["scenario_runs"])
    assert {m.name: m.value for m in metrics} == {
        "dataset_scenario_run_id_leakage_rate": 0.0,
        "dataset_split_group_leakage_rate": 0.0,
        "dataset_event_ref_leakage_rate": 0.0,
        "dataset_evidence_ref_leakage_rate": 0.0,
        "dataset_ground_truth_detector_derived_rate": 0.0,
    }


def test_valid_multi_scenario_dataset_has_distinct_split_groups_per_side():
    """S1/S2 (train) comparten split_group=campaign-alpha; S3/S4 (test)
    comparten campaign-beta -- ningún split_group cruza train/test."""
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    train, test = split_scenario_runs_for_dataset_integrity(manifest)
    assert {r["split_group"] for r in train} == {"campaign-alpha"}
    assert {r["split_group"] for r in test} == {"campaign-beta"}


def test_valid_temporal_separation_train_precedes_test():
    manifest = load_detection_ground_truth_manifest(_MANIFESTS_DIR / "idlab-06-detection-ground-truth-example.yaml")
    train, test = split_scenario_runs_for_dataset_integrity(manifest)
    latest_train_start = max(r["execution"]["started_at"] for r in train)
    earliest_test_start = min(r["execution"]["started_at"] for r in test)
    assert latest_train_start < earliest_test_start


def test_baseline_contamination_check_passes_clean_on_the_real_example():
    baseline = load_nominal_baseline_manifest(_MANIFESTS_DIR / "idlab-05-nominal-baseline-example.yaml")
    metric = dataset_integrity.evaluate_baseline_contamination(baseline)
    assert metric.value == 0.0


# ---------------------------------------------------------------------------
# "intentionally contaminated fixture -> leakage_rate = 1.0" / "same event
# in TRAIN/TEST -> INVALID": construidos a mano, sin pasar por el schema,
# igual que test_evaluators.py -- confirman que los evaluadores detectan
# la fuga por sí mismos, no solo que el schema la rechaza.
# ---------------------------------------------------------------------------


def test_end_to_end_deliberately_leaking_manifest_is_caught_by_legacy_de27(tmp_path):
    """Manifiesto IDLAB-06 REAL (pasa el schema, scenario_run_id/
    event_refs/split_group todos distintos) que SÍ repite (scenario_id,
    target_id) entre train y test -- confirma que el check legacy sigue
    aplicando sobre el formato v2 aunque los checks nuevos no vean nada
    raro (control negativo: distinto de los tests de fuga a nivel de
    scenario_run_id/event_ref/split_group, que SÍ están cubiertos por
    los checks nuevos)."""
    leaking = copy.deepcopy(_load_raw("idlab-06-detection-ground-truth-example.yaml"))
    train_run = next(r for r in leaking["scenario_runs"] if r["split"] == "TRAIN")
    test_run = next(r for r in leaking["scenario_runs"] if r["split"] == "TEST")
    test_run["scenario_id"] = train_run["scenario_id"]
    test_run["target"]["target_id"] = train_run["target"]["target_id"]

    path = tmp_path / "leaking.yaml"
    path.write_text(yaml.safe_dump(leaking), encoding="utf-8")
    manifest = load_detection_ground_truth_manifest(path)

    train, test = split_scenario_runs_for_dataset_integrity(manifest)
    metric = dataset_integrity.evaluate(scenario_runs_to_legacy_records(train), scenario_runs_to_legacy_records(test))
    assert metric.value > 0.0

    # Los checks nuevos no ven fuga: scenario_run_id/event_ref/evidence_ref/
    # split_group siguen siendo todos distintos -- es SOLO la combinación
    # (scenario_id, target_id) la que se repite.
    new_metrics = dataset_integrity.evaluate_scenario_runs(manifest["scenario_runs"])
    assert all(m.value == 0.0 for m in new_metrics)


def test_same_event_ref_in_train_and_test_is_caught_by_de27():
    """Dos scenario_run_id DISTINTOS (estructuralmente válidos) que
    comparten un event_ref observado -- la fuga más directa a nivel de
    evento individual, ver evaluate_event_ref_leakage."""
    scenario_runs = [
        {"scenario_run_id": "run-a", "split": "TRAIN", "observed": {"event_refs": ["shared-event"]}},
        {"scenario_run_id": "run-b", "split": "TEST", "observed": {"event_refs": ["shared-event"]}},
    ]
    metric = dataset_integrity.evaluate_event_ref_leakage(scenario_runs)
    assert metric.value == 1.0


def test_same_evidence_ref_in_train_and_test_is_caught_by_de27():
    scenario_runs = [
        {"scenario_run_id": "run-a", "split": "TRAIN", "observed": {"evidence_refs": ["shared-evidence"]}},
        {"scenario_run_id": "run-b", "split": "TEST", "observed": {"evidence_refs": ["shared-evidence"]}},
    ]
    metric = dataset_integrity.evaluate_evidence_ref_leakage(scenario_runs)
    assert metric.value == 1.0


def test_same_split_group_in_train_and_test_is_caught_by_de27():
    scenario_runs = [
        {"scenario_run_id": "run-a", "split": "TRAIN", "split_group": "campaign-x"},
        {"scenario_run_id": "run-b", "split": "TEST", "split_group": "campaign-x"},
    ]
    metric = dataset_integrity.evaluate_split_group_leakage(scenario_runs)
    assert metric.value == 1.0


def test_label_source_matching_detector_output_is_caught_even_bypassing_schema():
    """Defensa en profundidad: el schema ya lo prohíbe (enum cerrado),
    pero evaluate_label_provenance detecta el mismo problema en dicts
    crudos construidos sin pasar por el loader."""
    scenario_runs = [
        {"scenario_run_id": "run-a", "ground_truth": {"label_source": "detector_output"}},
    ]
    metric = dataset_integrity.evaluate_label_provenance(scenario_runs)
    assert metric.value == 1.0
    assert "run-a" in metric.detail


# ---------------------------------------------------------------------------
# Rechazos estructurales (schema): construidos por mutación sobre los
# ejemplos reales del repo, no sobre dicts inventados desde cero -- para
# que cada INVALID pruebe una única desviación del formato real.
# ---------------------------------------------------------------------------


def test_nominal_baseline_with_known_attacks_present_true_is_rejected(tmp_path):
    bad = copy.deepcopy(_load_raw("idlab-05-nominal-baseline-example.yaml"))
    bad["dataset"]["known_attacks_present"] = True
    _write_and_expect_invalid(tmp_path, bad, load_nominal_baseline_manifest)


def test_nominal_baseline_rejects_candidate_source_mode(tmp_path):
    bad = copy.deepcopy(_load_raw("idlab-05-nominal-baseline-example.yaml"))
    bad["dataset"]["source_mode"] = "CANDIDATE"
    _write_and_expect_invalid(tmp_path, bad, load_nominal_baseline_manifest)


def test_known_attack_inside_nominal_baseline_is_rejected(tmp_path):
    """contamination_check detecta un ataque que known_attacks_present no
    había declarado -- CONTAMINATED está excluido del enum a propósito
    (igual criterio que known_attacks_present: const false)."""
    bad = copy.deepcopy(_load_raw("idlab-05-nominal-baseline-example.yaml"))
    bad["contamination_check"]["contamination_status"] = "CONTAMINATED"
    bad["contamination_check"]["unexpected_attack_markers"] = ["suspicious-marker"]
    error = _write_and_expect_invalid(tmp_path, bad, load_nominal_baseline_manifest)
    assert any("CONTAMINATED" in e for e in error.errors)


def test_synthetic_fixture_marked_real_is_rejected_for_nominal_baseline(tmp_path):
    """is_example: true (todos los ejemplos de este repo) fuerza
    source_mode=SYNTHETIC por schema -- ningún fixture de prueba puede
    acabar etiquetado como REAL."""
    bad = copy.deepcopy(_load_raw("idlab-05-nominal-baseline-example.yaml"))
    assert bad["dataset"]["is_example"] is True
    bad["dataset"]["source_mode"] = "REAL"
    _write_and_expect_invalid(tmp_path, bad, load_nominal_baseline_manifest)


def test_scenario_run_split_across_train_and_test_is_rejected(tmp_path):
    """El split se declara POR scenario_run_id completo, nunca por evento
    individual: un scenario_run_id duplicado con splits distintos
    representaría exactamente esa fuga, así que se rechaza en la carga."""
    bad = copy.deepcopy(_load_raw("idlab-06-detection-ground-truth-example.yaml"))
    duplicate = copy.deepcopy(bad["scenario_runs"][0])
    duplicate["split"] = "TEST"
    bad["scenario_runs"].append(duplicate)
    error = _write_and_expect_invalid(tmp_path, bad, load_detection_ground_truth_manifest)
    assert any("duplicado" in e for e in error.errors)


def test_missing_environment_ref_is_rejected(tmp_path):
    bad = copy.deepcopy(_load_raw("idlab-06-detection-ground-truth-example.yaml"))
    del bad["environment_ref"]
    _write_and_expect_invalid(tmp_path, bad, load_detection_ground_truth_manifest)


def test_missing_configuration_hashes_is_rejected(tmp_path):
    bad = copy.deepcopy(_load_raw("idlab-06-detection-ground-truth-example.yaml"))
    del bad["provenance"]["configuration_hashes"]
    _write_and_expect_invalid(tmp_path, bad, load_detection_ground_truth_manifest)


def test_ground_truth_derived_from_detector_is_rejected(tmp_path):
    bad = copy.deepcopy(_load_raw("idlab-06-detection-ground-truth-example.yaml"))
    bad["scenario_runs"][0]["ground_truth"]["label_source"] = "detector_output"
    _write_and_expect_invalid(tmp_path, bad, load_detection_ground_truth_manifest)


def test_unknown_split_is_rejected(tmp_path):
    bad = copy.deepcopy(_load_raw("idlab-06-detection-ground-truth-example.yaml"))
    bad["scenario_runs"][0]["split"] = "VALIDATION"
    _write_and_expect_invalid(tmp_path, bad, load_detection_ground_truth_manifest)


def test_synthetic_fixture_marked_real_is_rejected_for_detection_ground_truth(tmp_path):
    bad = copy.deepcopy(_load_raw("idlab-06-detection-ground-truth-example.yaml"))
    assert bad["is_example"] is True
    bad["scenario_runs"][0]["source_mode"] = "REAL"
    _write_and_expect_invalid(tmp_path, bad, load_detection_ground_truth_manifest)
