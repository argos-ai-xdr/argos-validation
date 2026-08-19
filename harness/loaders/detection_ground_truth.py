"""IDLAB-05/06 (ADR-070, argos-control): carga y valida manifiestos de
baseline nominal (IDLAB-05) y ground truth de detección (IDLAB-06) --
formato LOCAL de este harness (mismo criterio que
`ground-truth/manifests/argos-cyb-01.yaml`), no un contrato cross-repo
de `argos-contracts-scenarios`.

**Esto es la infraestructura para cuando exista un laboratorio IDLAB
real -- ningún dato de aquí es telemetría capturada de verdad todavía**
(`BLOCKED_EXTERNAL`, sin OpenNebula/Wazuh/sensores reales desplegados,
ver `ground-truth/README.md`). Los manifiestos de ejemplo en
`ground-truth/manifests/idlab-05-*`/`idlab-06-*` demuestran el formato
v2 (environment/provenance/contamination_check/ScenarioRun completos),
no afirman una captura real -- `is_example: true` lo fuerza por schema
(nunca `source_mode: REAL`).

`split_scenario_runs_for_dataset_integrity` es el punto de unión real
con `evaluators.dataset_integrity` (DE-27): un manifiesto IDLAB-06
declara el split `TRAIN`/`TEST` POR `scenario_run_id` COMPLETO -- todos
sus `event_refs`/`evidence_refs` viajan al mismo lado, nunca se
recalcula por evento individual aquí ni en ningún otro sitio.
"""
from __future__ import annotations

import json
import pathlib

import yaml
from jsonschema import Draft202012Validator

_SCHEMAS_DIR = pathlib.Path(__file__).resolve().parents[2] / "ground-truth" / "schemas"


class InvalidGroundTruthManifest(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(f"Manifiesto de ground truth inválido: {errors}")
        self.errors = errors


def _validate(data: dict, *, schema_name: str) -> dict:
    schema = json.loads((_SCHEMAS_DIR / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = [e.message for e in validator.iter_errors(data)]
    if errors:
        raise InvalidGroundTruthManifest(errors)
    return data


def _validate_unique_scenario_run_ids(data: dict) -> None:
    """No expresable en JSON Schema puro (no hay 'unique by property' para
    arrays): un scenario_run_id duplicado rompería la unidad atómica de
    split que DE-27 asume (evaluate_scenario_run_id_leakage compara
    CONJUNTOS de ids por split -- un duplicado con splits distintos se
    perdería en silencio en vez de fallar aquí, en la carga)."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for run in data.get("scenario_runs", []):
        run_id = run.get("scenario_run_id")
        if run_id in seen:
            duplicates.append(run_id)
        seen.add(run_id)
    if duplicates:
        raise InvalidGroundTruthManifest([f"scenario_run_id duplicado: {d!r}" for d in duplicates])


def load_nominal_baseline_manifest(path: pathlib.Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _validate(data, schema_name="nominal-baseline-manifest.schema.json")


def load_detection_ground_truth_manifest(path: pathlib.Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    validated = _validate(data, schema_name="detection-ground-truth-manifest.schema.json")
    _validate_unique_scenario_run_ids(validated)
    return validated


def split_scenario_runs_for_dataset_integrity(manifest: dict) -> tuple[list[dict], list[dict]]:
    """`manifest` ya validado por `load_detection_ground_truth_manifest`.
    Devuelve `(train_runs, test_runs)`: los ScenarioRun completos,
    particionados por `split`. Uso:

    - `scenario_runs_to_legacy_records(train_runs)`/`(test_runs)` +
      `evaluators.dataset_integrity.evaluate` reproduce el check DE-27
      ORIGINAL `(scenario_id, host_id)` sobre el formato v2 -- no se
      sustituye, se complementa.
    - `evaluators.dataset_integrity.evaluate_scenario_runs(manifest["scenario_runs"])`
      corre los checks NUEVOS (scenario_run_id/split_group/event_ref/
      evidence_ref/label_provenance), que necesitan la lista completa con
      el campo `split` de cada item, no este tuple ya particionado.
    """
    runs = manifest["scenario_runs"]
    train = [r for r in runs if r["split"] == "TRAIN"]
    test = [r for r in runs if r["split"] == "TEST"]
    return train, test


def scenario_runs_to_legacy_records(scenario_runs: list[dict]) -> list[dict]:
    """Adapta ScenarioRun v2 (`target.target_id` anidado) a la forma plana
    `{scenario_id, host_id}` que espera el `evaluate()` original de
    `evaluators.dataset_integrity` -- ese check sigue aplicando tal cual
    sobre el nuevo formato."""
    return [{"scenario_id": r["scenario_id"], "host_id": r["target"]["target_id"]} for r in scenario_runs]
