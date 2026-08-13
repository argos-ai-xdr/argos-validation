from __future__ import annotations

import json
import pathlib

from jsonschema import Draft202012Validator

from evaluators.base import Metric
from harness.reporters.markdown_report import render
from harness.reporters.run_summary import build_run_summary

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _sample_summary() -> dict:
    metrics = [
        Metric(name="detection_f1", value=0.9, detail="tp=9 fp=1 fn=0", ac_ids=("AC06",), sample_size=10),
        Metric(name="adversarial_block_rate", value=1.0, detail="4/4 bloqueados", sample_size=4),
    ]
    thresholds = {
        "detection_f1": {"min": 0.85, "critical": False},
        "adversarial_block_rate": {"min": 1.0, "critical": True, "adversarial": True},
    }
    return build_run_summary(run_id="r1", suite_id="s1", mode="golden", metrics=metrics, thresholds=thresholds)


def test_build_run_summary_matches_its_own_schema():
    schema = json.loads((ROOT / "reports/schemas/run_summary.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(_sample_summary()))
    assert not errors, [e.message for e in errors]


def test_markdown_report_renders_without_crashing():
    text = render(_sample_summary())
    assert "s1" in text
    assert "PASS" in text
