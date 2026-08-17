"""AC01 (Reproducibilidad): dos ejecuciones limpias producen el mismo
conjunto de hechos; diferencias no deterministas justificadas. Único AC de
los 14 marcado "PASS obligatorio" sin más matiz — no admite ni siquiera
la lectura "critical: false" que sí tienen otros.

No encaja en el patrón evaluators.evaluate(fixtures, ...) porque no mide
UN fixture: mide si CORRER la misma suite dos veces sobre el mismo
checkout produce el mismo resultado. Por eso vive en harness/, junto a
checkpoints.py/traceability.py, no en evaluators/.

`run_id`/`generated_at`/`metric.detail` que solo repiten el propio
`run_id` no son "hechos" en el sentido de AC01 — son metadatos de cuándo
se ejecutó, no de qué se encontró; se excluyen a propósito de la
comparación (documentado en `_DETAIL_CONTAINS_RUN_ID`, no una lista
arbitraria). Todo lo demás — `value`, `gate`, `sample_size` de cada
métrica, y el `overall` — debe coincidir exactamente entre ambas
ejecuciones, porque ninguna de las dos tocó el checkout de fixtures.
"""
from __future__ import annotations

import dataclasses
import pathlib

from evaluators.base import Metric
from harness.runner.cli import run_suite


@dataclasses.dataclass(frozen=True)
class ReproducibilityResult:
    suite_id: str
    mismatches: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.mismatches


def check_reproducibility(
    suite_path: pathlib.Path,
    thresholds_path: pathlib.Path,
    *,
    contracts_path: pathlib.Path | None = None,
) -> ReproducibilityResult:
    summary_1, errors_1 = run_suite(suite_path, thresholds_path, contracts_path)
    summary_2, errors_2 = run_suite(suite_path, thresholds_path, contracts_path)

    mismatches: list[str] = []
    if errors_1 != errors_2:
        mismatches.append(f"fixture_errors difieren entre ejecuciones: {errors_1} vs {errors_2}")

    names_1 = set(summary_1["results"])
    names_2 = set(summary_2["results"])
    if names_1 != names_2:
        mismatches.append(f"el conjunto de métricas difiere entre ejecuciones: {sorted(names_1)} vs {sorted(names_2)}")

    for name in sorted(names_1 & names_2):
        r1, r2 = summary_1["results"][name], summary_2["results"][name]
        if r1["metric"]["value"] != r2["metric"]["value"]:
            mismatches.append(f"{name}: value no determinista ({r1['metric']['value']} vs {r2['metric']['value']})")
        if r1["metric"]["sample_size"] != r2["metric"]["sample_size"]:
            mismatches.append(f"{name}: sample_size no determinista ({r1['metric']['sample_size']} vs {r2['metric']['sample_size']})")
        if r1["gate"] != r2["gate"]:
            mismatches.append(f"{name}: gate no determinista ({r1['gate']} vs {r2['gate']})")

    if summary_1["overall"] != summary_2["overall"]:
        mismatches.append(f"overall no determinista: {summary_1['overall']} vs {summary_2['overall']}")

    return ReproducibilityResult(suite_id=summary_1.get("suite", str(suite_path)), mismatches=tuple(mismatches))


def evaluate_reproducibility(
    suite_path: pathlib.Path,
    thresholds_path: pathlib.Path,
    *,
    contracts_path: pathlib.Path | None = None,
) -> Metric:
    """Envoltorio como Metric (AC01 es binario: PASS obligatorio, no una
    tasa) para que encaje en el mismo run_summary/acceptance-report que
    el resto de AC, sin forzar evaluators/ a aceptar una firma distinta."""
    result = check_reproducibility(suite_path, thresholds_path, contracts_path=contracts_path)
    return Metric(
        name="reproducibility_violation",
        value=0.0 if result.ok else 1.0,
        detail=(
            "dos ejecuciones limpias producen el mismo conjunto de hechos"
            if result.ok
            else f"diferencias no deterministas: {list(result.mismatches)}"
        ),
        ac_ids=("AC01",),
        sample_size=1,
    )
