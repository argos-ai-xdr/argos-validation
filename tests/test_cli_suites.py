from __future__ import annotations

import pathlib

import pytest

from harness.runner.cli import main, run_suite

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


def test_check_trace_blocks_the_run_on_the_known_real_p0_gap(monkeypatch, tmp_path, capsys):
    """TRACE-01: 'la release candidata se bloquea si traceability.yaml no
    valida'. G7 (ARG-027/ARG-028, ambas P0) está honestamente en
    status=BLOCKED en el traceability.yaml real del repo (no existe
    orquestador AC01-AC14 ni evidence pack firmado todavía) — --check-trace
    debe frenar el run ANTES de tocar ninguna suite, no solo avisar."""
    monkeypatch.chdir(tmp_path)
    exit_code = main(
        [
            "--suite",
            str(ROOT / "suites" / "c06" / "suite.yaml"),
            "--thresholds",
            str(ROOT / "thresholds" / "smoke.yaml"),
            "--check-trace",
        ]
    )
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "TRACE P0 BLOCKED" in out
    assert "release candidate bloqueada" in out
    assert not (tmp_path / "run_summary.json").exists()
