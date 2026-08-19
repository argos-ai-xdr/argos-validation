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

**Extensión v2 (2026-08-19, IDLAB-06 ScenarioRun)**: el formato rico de
ground truth (`harness.loaders.detection_ground_truth`) introduce
unidades de fuga que `evaluate()` no cubre -- un `ScenarioRun` completo
(no una fila `scenario_id`/`host_id`) es la unidad atómica de split, así
que además de `evaluate()` (que se mantiene sin cambios, sigue
aplicando vía `scenario_runs_to_legacy_records`) se añaden:

- `evaluate_scenario_run_id_leakage`: mismo `scenario_run_id` en TRAIN y
  TEST -- solo posible si un manifiesto está mal construido (duplicado),
  ya que cada run declara un único `split`; capa de defensa en
  profundidad sobre `_validate_unique_scenario_run_ids` del loader.
- `evaluate_split_group_leakage`: un `split_group` (campaña/ventana
  temporal correlacionada) no puede tener runs en ambos lados.
- `evaluate_event_ref_leakage` / `evaluate_evidence_ref_leakage`: ningún
  `event_ref`/`evidence_ref` observado puede aparecer en ambos lados --
  la fuga más directa a nivel de evento individual.
- `evaluate_label_provenance`: `ground_truth.label_source` nunca puede
  ser el propio detector evaluado ni equivalente -- si no, el sistema
  produciría su propia verdad. El schema (enum cerrado) ya lo impide
  estructuralmente; esto es defensa en profundidad para callers que
  construyen el dict a mano sin pasar por el schema (como estos mismos
  evaluadores se prueban: con dicts crudos, no manifiestos YAML).
- `evaluate_baseline_contamination`: un `NominalBaselineManifest`
  (IDLAB-05) cuyo `contamination_check` indica que SÍ se encontró un
  ataque conocido no es un baseline nominal válido, aunque
  `known_attacks_present` se declarase `false` de partida -- el
  contamination_check es la verificación independiente que atrapa ese
  error.
"""
from __future__ import annotations

from evaluators.base import Metric

_FORBIDDEN_LABEL_SOURCES = frozenset(
    {
        "detector_output",
        "wazuh_alert",
        "argos_investigator_verdict",
        "soc_decision_output",
    }
)


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


def _split_leakage_metric(
    *,
    name: str,
    scenario_runs: list[dict],
    key_fn,
    ac_ids: tuple[str, ...] = ("DE-27",),
) -> Metric:
    """Helper interno: `key_fn(run) -> set[str]` extrae las claves de fuga
    de un `ScenarioRun` (puede devolver un set vacío si el run no declara
    esa dimensión, p.ej. `split_group` ausente). `leakage_rate` = claves
    presentes en TRAIN y TEST simultáneamente, sobre el total de claves
    distintas observadas."""
    train_keys: set[str] = set()
    test_keys: set[str] = set()
    for run in scenario_runs:
        keys = key_fn(run)
        if run["split"] == "TRAIN":
            train_keys |= keys
        elif run["split"] == "TEST":
            test_keys |= keys

    leaked = train_keys & test_keys
    total = len(train_keys | test_keys)
    leakage_rate = len(leaked) / total if total else 0.0

    return Metric(
        name=name,
        value=leakage_rate,
        detail=f"{len(leaked)} clave(s) presentes en TRAIN Y TEST: {sorted(leaked)}",
        ac_ids=ac_ids,
        sample_size=len(scenario_runs),
    )


def evaluate_scenario_run_id_leakage(scenario_runs: list[dict]) -> Metric:
    """El `scenario_run_id` es la unidad atómica de split -- solo puede
    aparecer fugado si el manifiesto está mal construido (duplicado con
    splits distintos). Defensa en profundidad sobre
    `harness.loaders.detection_ground_truth._validate_unique_scenario_run_ids`."""
    return _split_leakage_metric(
        name="dataset_scenario_run_id_leakage_rate",
        scenario_runs=scenario_runs,
        key_fn=lambda r: {r["scenario_run_id"]},
    )


def evaluate_split_group_leakage(scenario_runs: list[dict]) -> Metric:
    """Un `split_group` (campaña/ventana temporal correlacionada) agrupa
    varios `scenario_run_id` que deben viajar juntos al mismo split --
    p.ej. dos ataques de la misma campaña sobre hosts distintos no deben
    quedar repartidos entre TRAIN y TEST. Runs sin `split_group` no
    aportan clave (no se penalizan)."""
    return _split_leakage_metric(
        name="dataset_split_group_leakage_rate",
        scenario_runs=scenario_runs,
        key_fn=lambda r: {r["split_group"]} if r.get("split_group") else set(),
    )


def evaluate_event_ref_leakage(scenario_runs: list[dict]) -> Metric:
    """Ningún `event_ref` observado puede aparecer en ambos lados -- la
    fuga más directa a nivel de evento individual, independiente de que
    los `scenario_run_id` ya sean disjuntos."""
    return _split_leakage_metric(
        name="dataset_event_ref_leakage_rate",
        scenario_runs=scenario_runs,
        key_fn=lambda r: set(r.get("observed", {}).get("event_refs", [])),
    )


def evaluate_evidence_ref_leakage(scenario_runs: list[dict]) -> Metric:
    """Mismo principio que `evaluate_event_ref_leakage` pero sobre
    `observed.evidence_refs` -- evidencia observada específica de un run,
    no la evidencia global de provenance del manifiesto."""
    return _split_leakage_metric(
        name="dataset_evidence_ref_leakage_rate",
        scenario_runs=scenario_runs,
        key_fn=lambda r: set(r.get("observed", {}).get("evidence_refs", [])),
    )


def evaluate_label_provenance(scenario_runs: list[dict]) -> Metric:
    """`ground_truth.label_source` nunca puede ser el propio sistema
    evaluado (`detector_output` o equivalente) -- si no, ARGOS se
    convertiría en el productor de su propia verdad. El schema (enum
    cerrado, ver `detection-ground-truth-manifest.schema.json`) ya lo
    impide estructuralmente; esto es defensa en profundidad para callers
    que construyen el dict a mano sin pasar por el schema."""
    offending = [
        r.get("scenario_run_id", "<sin scenario_run_id>")
        for r in scenario_runs
        if r.get("ground_truth", {}).get("label_source") in _FORBIDDEN_LABEL_SOURCES
    ]
    value = len(offending) / len(scenario_runs) if scenario_runs else 0.0
    return Metric(
        name="dataset_ground_truth_detector_derived_rate",
        value=value,
        detail=f"scenario_run_id con label_source prohibido (derivado del propio detector evaluado): {offending}",
        ac_ids=("DE-27",),
        sample_size=len(scenario_runs),
    )


def evaluate_scenario_runs(scenario_runs: list[dict]) -> tuple[Metric, ...]:
    """Corre TODOS los checks nuevos de nivel `ScenarioRun` -- punto de
    entrada único para `harness.loaders.detection_ground_truth`. No
    incluye `evaluate()` (el check original `scenario_id`/`host_id`),
    que sigue necesitando `scenario_runs_to_legacy_records` para adaptar
    la forma."""
    return (
        evaluate_scenario_run_id_leakage(scenario_runs),
        evaluate_split_group_leakage(scenario_runs),
        evaluate_event_ref_leakage(scenario_runs),
        evaluate_evidence_ref_leakage(scenario_runs),
        evaluate_label_provenance(scenario_runs),
    )


def evaluate_baseline_contamination(nominal_baseline_manifest: dict) -> Metric:
    """Un `NominalBaselineManifest` (IDLAB-05) cuyo `contamination_check`
    indica que SÍ se encontró un ataque conocido (`contamination_status`
    distinto de `CLEAN`/`NOT_PERFORMED`, o `unexpected_attack_markers` no
    vacío) no es un baseline nominal válido -- el schema ya excluye
    `CONTAMINATED` del enum y fuerza `unexpected_attack_markers` vacío
    (`nominal-baseline-manifest.schema.json`), así que en la práctica
    esta función solo puede devolver `1.0` si un caller construye el dict
    a mano sin pasar por el schema (defensa en profundidad, igual patrón
    que `evaluate_label_provenance`)."""
    contamination_check = nominal_baseline_manifest.get("contamination_check", {})
    markers = contamination_check.get("unexpected_attack_markers") or []
    status = contamination_check.get("contamination_status")
    is_contaminated = bool(markers) or status not in ("CLEAN", "NOT_PERFORMED")

    return Metric(
        name="dataset_baseline_contamination_rate",
        value=1.0 if is_contaminated else 0.0,
        detail=f"contamination_status={status!r}, unexpected_attack_markers={markers}",
        ac_ids=("DE-27",),
        sample_size=1,
    )
