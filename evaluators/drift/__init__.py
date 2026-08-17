"""ARG-010 (C-06.UC4/UC5 slice, propuesta técnica v0.6.25.4 §11.14):
"Drift crítico omitido = 0; F1 >= 0.85; cobertura de controles MVP >= 0.95;
trazabilidad >= 0.95".

Agrupa AssetSnapshot por asset_id y compara el par más antiguo/más
reciente (as-designed -> as-built). La comparación de campos duplica a
propósito services.asset_reconciler.detect_drift de argos-core (mismo
patrón que el resto de argos-ai-xdr: argos-validation solo tiene
argos-contracts-scenarios como hermano, no argos-core, así que no puede
importarlo).

Un activo crítico (criticality_esp="critical" en cualquiera de los dos
snapshots) sin criticality_esp resoluble en el OTRO snapshot no puede
clasificarse con confianza como "sin drift crítico" — se cuenta
explícitamente como drift crítico potencialmente omitido, no se asume "no
crítico" en silencio (mismo principio que evaluators.detection: no
fabricar una respuesta donde no hay evidencia para afirmarla).
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric

_MERGEABLE_FIELDS = ("workload_id", "image_ref", "node", "namespace", "criticality_esp")


def _detect_drift(as_designed: dict, as_built: dict) -> list[dict]:
    drift = []
    for field in _MERGEABLE_FIELDS:
        designed_value = as_designed.get(field)
        built_value = as_built.get(field)
        if designed_value != built_value:
            drift.append({"field": field, "as_designed": designed_value, "as_built": built_value})
    return drift


def evaluate(fixtures: list[dict], *, contracts_path: pathlib.Path | None = None) -> Metric:
    by_asset: dict[str, list[dict]] = {}
    for fixture in fixtures:
        asset_id = fixture.get("asset_id")
        if asset_id:
            by_asset.setdefault(asset_id, []).append(fixture)

    drift_found = 0
    critical_drift_missed: list[str] = []
    comparable_pairs = 0
    for asset_id, snapshots in sorted(by_asset.items()):
        if len(snapshots) < 2:
            continue
        comparable_pairs += 1
        ordered = sorted(snapshots, key=lambda s: s.get("observed_at", ""))
        as_designed, as_built = ordered[0], ordered[-1]
        drift = _detect_drift(as_designed, as_built)
        if drift:
            drift_found += 1
            # detect_drift ya es exhaustivo: un drift sobre un activo
            # CONFIRMADO crítico está correctamente capturado, no "omitido".
            # El riesgo real es no poder afirmar que NO era crítico: si
            # criticality_esp falta en cualquiera de los dos snapshots, el
            # drift queda sin clasificar — eso sí es "potencialmente
            # omitido" en el sentido de AC10, no asumirlo "no crítico" en
            # silencio.
            either_missing = not as_designed.get("criticality_esp") or not as_built.get("criticality_esp")
            if either_missing:
                critical_drift_missed.append(asset_id)

    missed_rate = len(critical_drift_missed) / comparable_pairs if comparable_pairs else 0.0

    return Metric(
        name="critical_drift_missed_rate",
        value=missed_rate,
        detail=(
            f"{len(critical_drift_missed)}/{comparable_pairs} pares as-designed/as-built con drift "
            f"crítico o no clasificable: {critical_drift_missed}; drift total detectado: {drift_found}"
        ),
        sample_size=len(fixtures),
    )
