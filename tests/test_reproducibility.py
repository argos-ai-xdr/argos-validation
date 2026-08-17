from __future__ import annotations

import pathlib

from harness.reproducibility import check_reproducibility, evaluate_reproducibility

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_real_suite_is_reproducible_against_static_fixtures(contracts_path):
    """Integración real: ninguno de los evaluadores existentes usa
    aleatoriedad, así que correr c06 dos veces sobre el mismo checkout de
    fixtures debe coincidir exactamente. Si esto empieza a fallar,
    alguien introdujo no-determinismo real en un evaluador."""
    result = check_reproducibility(
        ROOT / "suites" / "c06" / "suite.yaml",
        ROOT / "thresholds" / "smoke.yaml",
        contracts_path=contracts_path,
    )
    assert result.ok, result.mismatches


def test_evaluate_reproducibility_wraps_ok_as_zero_violation(contracts_path):
    metric = evaluate_reproducibility(
        ROOT / "suites" / "c06" / "suite.yaml",
        ROOT / "thresholds" / "smoke.yaml",
        contracts_path=contracts_path,
    )
    assert metric.value == 0.0
    assert metric.ac_ids == ("AC01",)


def test_check_reproducibility_detects_a_value_that_changed_between_runs(monkeypatch, contracts_path):
    """Simula el caso real que AC01 existe para atrapar: dos ejecuciones
    de la MISMA suite que, por algún no-determinismo real en un
    evaluador, calculan un valor distinto para la misma métrica."""
    calls = {"n": 0}

    def fake_run_suite(suite_path, thresholds_path, contracts_path=None):
        calls["n"] += 1
        value = 1.0 if calls["n"] == 1 else 0.5
        summary = {
            "suite": "fake",
            "mode": "golden",
            "generated_at": f"t{calls['n']}",
            "results": {
                "some_metric": {
                    "metric": {"name": "some_metric", "value": value, "detail": "x", "ac_ids": [], "sample_size": 3},
                    "gate": "PASS",
                    "reason": "dentro de umbral",
                    "critical": False,
                }
            },
            "overall": "PASS",
            "critical_failures": [],
            "warnings": [],
        }
        return summary, []

    monkeypatch.setattr("harness.reproducibility.run_suite", fake_run_suite)

    result = check_reproducibility(pathlib.Path("fake-suite.yaml"), pathlib.Path("fake-thresholds.yaml"))

    assert not result.ok
    assert any("some_metric" in m and "no determinista" in m for m in result.mismatches)


def test_check_reproducibility_ignores_generated_at_which_is_expected_to_differ(monkeypatch):
    """generated_at es un timestamp de CUÁNDO se corrió, no un hecho
    detectado — dos ejecuciones limpias lo tendrán distinto por
    definición y eso NO debe contar como una violación de AC01."""

    def fake_run_suite(suite_path, thresholds_path, contracts_path=None):
        summary = {
            "suite": "fake",
            "mode": "golden",
            "generated_at": "distinto-cada-vez",
            "results": {},
            "overall": "PASS",
            "critical_failures": [],
            "warnings": [],
        }
        return summary, []

    monkeypatch.setattr("harness.reproducibility.run_suite", fake_run_suite)

    result = check_reproducibility(pathlib.Path("fake-suite.yaml"), pathlib.Path("fake-thresholds.yaml"))
    assert result.ok


def test_check_reproducibility_detects_a_metric_that_appears_only_in_one_run(monkeypatch):
    calls = {"n": 0}

    def fake_run_suite(suite_path, thresholds_path, contracts_path=None):
        calls["n"] += 1
        results = {}
        if calls["n"] == 1:
            results["flaky_metric"] = {
                "metric": {"name": "flaky_metric", "value": 1.0, "detail": "x", "ac_ids": [], "sample_size": 1},
                "gate": "PASS",
                "reason": "x",
                "critical": False,
            }
        return {"suite": "fake", "mode": "golden", "generated_at": "t", "results": results, "overall": "PASS", "critical_failures": [], "warnings": []}, []

    monkeypatch.setattr("harness.reproducibility.run_suite", fake_run_suite)

    result = check_reproducibility(pathlib.Path("fake-suite.yaml"), pathlib.Path("fake-thresholds.yaml"))
    assert not result.ok
    assert any("conjunto de métricas difiere" in m for m in result.mismatches)
