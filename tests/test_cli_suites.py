from __future__ import annotations

import pathlib

import pytest

from harness.runner.cli import run_suite

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUITE_IDS = ["c06", "c07", "c08", "argos-cyb-01", "integration", "regression", "adversarial"]


@pytest.mark.parametrize("suite_id", SUITE_IDS)
def test_suite_runs_clean_against_smoke_thresholds(contracts_path, suite_id):
    suite_path = ROOT / "suites" / suite_id / "suite.yaml"
    thresholds_path = ROOT / "thresholds" / "smoke.yaml"

    summary, fixture_errors = run_suite(suite_path, thresholds_path, contracts_path=contracts_path)

    assert fixture_errors == []
    assert summary["overall"] in ("PASS", "PASS_WITH_EXPECTED_BLOCKS")
    assert summary["critical_failures"] == []


def test_adversarial_suite_reports_expected_blocks(contracts_path):
    suite_path = ROOT / "suites" / "adversarial" / "suite.yaml"
    thresholds_path = ROOT / "thresholds" / "acceptance.yaml"

    summary, fixture_errors = run_suite(suite_path, thresholds_path, contracts_path=contracts_path)

    assert fixture_errors == []
    assert summary["results"]["adversarial_block_rate"]["gate"] == "PASS_WITH_EXPECTED_BLOCKS"


def test_c07_tool_correctness_passes_acceptance(contracts_path):
    """Regresión del bug de granularidad target vs namespace (ver
    evaluators/tool_calls/__init__.py) — no debe volver a romperse."""
    suite_path = ROOT / "suites" / "c07" / "suite.yaml"
    thresholds_path = ROOT / "thresholds" / "acceptance.yaml"

    summary, fixture_errors = run_suite(suite_path, thresholds_path, contracts_path=contracts_path)

    assert fixture_errors == []
    assert summary["results"]["tool_correctness"]["gate"] == "PASS"
