"""DE-27 (ADR-070, argos-control): ningún `(scenario_id, host_id)` puede
aparecer a la vez en el conjunto de entrenamiento y en el de test del
detector estadístico (`DetectionModelManifest v1`) -- un split ALEATORIO
por fila puede dejar el MISMO ataque sobre el MISMO host repartido entre
`training` y `test`, inflando artificialmente precision/recall (el
modelo "reconoce" un caso que ya vio, no generaliza). La separación debe
ser por tiempo/escenario/host, nunca por fila.

Mismo patrón que el resto de `evaluators/*`: función pura `evaluate(...)
-> Metric`, no decide PASS/FAIL por sí misma (eso lo hace
`harness.reporters.run_summary` contra `thresholds/*.yaml`).
"""
from __future__ import annotations

from evaluators.base import Metric


def evaluate(train_records: list[dict], test_records: list[dict]) -> Metric:
    """Cada record necesita `scenario_id` y `host_id` (p. ej. una fila del
    índice de `ground-truth/manifests/`). `leakage_rate` = combinaciones
    `(scenario_id, host_id)` presentes en AMBOS conjuntos, sobre el total
    de combinaciones distintas observadas -- 0.0 es el único valor
    aceptable (DE-27 es crítico)."""
    train_keys = {(r["scenario_id"], r["host_id"]) for r in train_records}
    test_keys = {(r["scenario_id"], r["host_id"]) for r in test_records}
    leaked = train_keys & test_keys

    total_keys = len(train_keys | test_keys)
    leakage_rate = len(leaked) / total_keys if total_keys else 0.0

    return Metric(
        name="dataset_scenario_host_leakage_rate",
        value=leakage_rate,
        detail=f"{len(leaked)} combinaciones (scenario_id, host_id) presentes en train Y test: {sorted(leaked)}",
        ac_ids=("DE-27",),
        sample_size=len(train_records) + len(test_records),
    )
