from __future__ import annotations

from evaluators.base import Metric
from harness.reporters.run_summary import (
    build_run_summary,
    evaluate_against_thresholds,
    overall_result,
)


def test_pass_gate():
    metrics = [Metric(name="m1", value=0.9, detail="")]
    thresholds = {"m1": {"min": 0.85, "critical": False}}
    results = evaluate_against_thresholds(metrics, thresholds)
    assert results["m1"]["gate"] == "PASS"


def test_fail_gate_min():
    metrics = [Metric(name="m1", value=0.5, detail="")]
    thresholds = {"m1": {"min": 0.85, "critical": True}}
    results = evaluate_against_thresholds(metrics, thresholds)
    assert results["m1"]["gate"] == "FAIL"
    assert results["m1"]["critical"] is True


def test_fail_gate_max():
    metrics = [Metric(name="m1", value=0.5, detail="")]
    thresholds = {"m1": {"max": 0.1, "critical": False}}
    results = evaluate_against_thresholds(metrics, thresholds)
    assert results["m1"]["gate"] == "FAIL"


def test_adversarial_pass_is_expected_blocks():
    metrics = [Metric(name="block_rate", value=1.0, detail="")]
    thresholds = {"block_rate": {"min": 1.0, "critical": True, "adversarial": True}}
    results = evaluate_against_thresholds(metrics, thresholds)
    assert results["block_rate"]["gate"] == "PASS_WITH_EXPECTED_BLOCKS"


def test_missing_threshold_is_critical_fail():
    metrics = [Metric(name="unbudgeted", value=1.0, detail="")]
    results = evaluate_against_thresholds(metrics, thresholds={})
    assert results["unbudgeted"]["gate"] == "FAIL"
    assert results["unbudgeted"]["critical"] is True


def test_overall_result_pass():
    results = {"a": {"gate": "PASS"}, "b": {"gate": "PASS"}}
    assert overall_result(results) == "PASS"


def test_overall_result_pass_with_expected_blocks():
    results = {"a": {"gate": "PASS"}, "b": {"gate": "PASS_WITH_EXPECTED_BLOCKS"}}
    assert overall_result(results) == "PASS_WITH_EXPECTED_BLOCKS"


def test_overall_result_fail_if_any_fails():
    results = {"a": {"gate": "PASS"}, "b": {"gate": "FAIL"}}
    assert overall_result(results) == "FAIL"


def test_overall_result_empty_is_fail():
    assert overall_result({}) == "FAIL"


def test_build_run_summary_separates_critical_and_warnings():
    metrics = [
        Metric(name="critical_one", value=0.1, detail=""),
        Metric(name="warn_one", value=0.1, detail=""),
        Metric(name="ok_one", value=1.0, detail=""),
    ]
    thresholds = {
        "critical_one": {"min": 0.9, "critical": True},
        "warn_one": {"min": 0.9, "critical": False},
        "ok_one": {"min": 0.9, "critical": False},
    }
    summary = build_run_summary(run_id="r1", suite_id="s1", mode="golden", metrics=metrics, thresholds=thresholds)
    assert summary["critical_failures"] == ["critical_one"]
    assert summary["warnings"] == ["warn_one"]
    assert summary["overall"] == "FAIL"
