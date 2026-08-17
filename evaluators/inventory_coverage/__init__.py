"""AC02 (Inventario): cobertura de activos >= 0.95; ningún activo crítico
conocido omitido; trazabilidad >= 0.95.

Compara los `asset_id` de los fixtures AssetSnapshot cargados contra una
lista de activos esperados (ground truth del escenario,
ground-truth/manifests/argos-cyb-01.yaml) que lleva su propia
`criticality_esp` — necesaria PRECISAMENTE porque un activo omitido no
tiene snapshot del que leer su criticidad; sin guardarla en el ground
truth, "ningún activo crítico conocido omitido" nunca podría detectar el
caso que existe para prevenir.

AC02 es `critical: false` en acceptance-criteria.yaml (a diferencia de
AC01/AC10/AC12) — por eso esto se reporta como un único `asset_coverage`
con la omisión crítica visible en `detail`, en vez de inventar un segundo
gate `critical: true` que el documento no pide.

Sin `expected_assets` (mismo principio que evaluators.human_agreement):
lanza NotImplementedError en vez de simular una cobertura del 100% contra
una lista vacía — "no evaluable" y "cobertura perfecta" no son lo mismo.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric

_CRITICAL_LEVELS = frozenset({"high", "critical"})


def evaluate(
    fixtures: list[dict],
    *,
    expected_assets: list[dict] | None = None,
    contracts_path: pathlib.Path | None = None,  # no usado por este evaluador
) -> Metric:
    if not expected_assets:
        raise NotImplementedError(
            "inventory_coverage requiere expected_assets (ground-truth/manifests/); "
            "no se debe invocar este evaluador desde una suite sin ese ground truth."
        )

    found = {f["asset_id"] for f in fixtures if "asset_id" in f}
    missing = [a for a in expected_assets if a["asset_id"] not in found]
    total = len(expected_assets)
    coverage = (total - len(missing)) / total if total else 1.0

    critical_missing = sorted(
        a["asset_id"] for a in missing if a.get("criticality_esp") in _CRITICAL_LEVELS
    )

    return Metric(
        name="asset_coverage",
        value=coverage,
        detail=(
            f"{total - len(missing)}/{total} activos esperados presentes; "
            f"faltantes={sorted(a['asset_id'] for a in missing)}; "
            f"criticos_omitidos={critical_missing}"
        ),
        ac_ids=("AC02",),
        sample_size=total,
    )
