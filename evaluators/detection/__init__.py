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

    # event_id que el ground truth exige y que NO aparece entre los fixtures
    # cargados — un falso negativo real. La versión anterior de este campo
    # (`missed_critical`) iteraba `fixtures` (lo detectado) buscando
    # severidad "critical" ausente de `expected`: eso identifica falsos
    # POSITIVOS críticos, no eventos perdidos — un evento crítico que el
    # ground truth exige pero que el pipeline nunca detectó (ni aparece en
    # `fixtures`) siempre daba `missed_critical=[]`, sin importar cuántos
    # eventos críticos se perdieran de verdad. AC06 exige exactamente "0
    # eventos críticos perdidos" — con el bug, esa condición nunca podía
    # violarse, por diseño, no por ausencia de fallos. No se puede filtrar
    # por severidad aquí: un event_id ausente de `fixtures` no tiene
    # severidad conocida por este evaluador (ver ground-truth/schemas/
    # expected-event-ids.schema.json — no la lleva).
    missed_event_ids = sorted(expected - predicted)

    return Metric(
        name="detection_f1",
        value=f1,
        detail=(
            f"precision={precision:.3f} recall={recall:.3f} "
            f"tp={true_positives} fp={false_positives} fn={false_negatives} "
            f"missed_event_ids={missed_event_ids}"
        ),
        ac_ids=("AC06",),
        sample_size=len(fixtures),
    )
