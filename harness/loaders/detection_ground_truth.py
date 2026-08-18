"""IDLAB-05/06 (ADR-070, argos-control): carga y valida manifiestos de
baseline nominal (IDLAB-05) y ground truth de detección (IDLAB-06) --
formato LOCAL de este harness (mismo criterio que
`ground-truth/manifests/argos-cyb-01.yaml`), no un contrato cross-repo
de `argos-contracts-scenarios`.

**Esto es la infraestructura para cuando exista un laboratorio IDLAB
real -- ningún dato de aquí es telemetría capturada de verdad todavía**
(`BLOCKED_EXTERNAL`, sin OpenNebula/Wazuh/sensores reales desplegados,
ver `ground-truth/README.md`). Los manifiestos de ejemplo en
`ground-truth/manifests/idlab-05-*`/`idlab-06-*` demuestran el formato,
no afirman una captura real.

`split_records_for_dataset_integrity` es el punto de unión real con
`evaluators.dataset_integrity.evaluate` (DE-27): un manifiesto IDLAB-06
declara el split `train`/`test` POR REGISTRO (escenario+host), nunca se
recalcula aleatoriamente por fila aquí ni en ningún otro sitio.
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


def load_nominal_baseline_manifest(path: pathlib.Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _validate(data, schema_name="nominal-baseline-manifest.schema.json")


def load_detection_ground_truth_manifest(path: pathlib.Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _validate(data, schema_name="detection-ground-truth-manifest.schema.json")


def split_records_for_dataset_integrity(manifest: dict) -> tuple[list[dict], list[dict]]:
    """`manifest` ya validado por `load_detection_ground_truth_manifest`.
    Devuelve `(train_records, test_records)` -- exactamente la forma que
    espera `evaluators.dataset_integrity.evaluate(train, test)`."""
    train = [r for r in manifest["records"] if r["split"] == "train"]
    test = [r for r in manifest["records"] if r["split"] == "test"]
    return train, test
