"""AC06 (Detección): Detection F1 >= 0.85; eventos críticos perdidos = 0 en
el escenario golden.

Compara los event_id de los fixtures SecurityEvent cargados contra una lista
de event_id esperados (ground truth del escenario). Cálculo real de
precisión/recall/F1 — sin acceso a red, puro en memoria.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric


def evaluate(
    fixtures: list[dict],
    *,
    expected_event_ids: list[str] | None = None,
    contracts_path: pathlib.Path | None = None,  # no usado por este evaluador
) -> Metric:
    expected = set(expected_event_ids or [])
    predicted = {f["event_id"] for f in fixtures if "event_id" in f}

    true_positives = len(predicted & expected)
    false_positives = len(predicted - expected)
    false_negatives = len(expected - predicted)

    if not predicted and not expected:
        precision = recall = f1 = 1.0
    else:
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    missed_critical = [
        f["event_id"]
        for f in fixtures
        if f.get("severity_normalized") == "critical" and f.get("event_id") not in expected and expected
    ]

    return Metric(
        name="detection_f1",
        value=f1,
        detail=(
            f"precision={precision:.3f} recall={recall:.3f} "
            f"tp={true_positives} fp={false_positives} fn={false_negatives} "
            f"missed_critical={missed_critical}"
        ),
        ac_ids=("AC06",),
        sample_size=len(fixtures),
    )
