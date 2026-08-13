"""Carga schemas y fixtures desde el checkout de argos-contracts-scenarios.

Reutiliza el mismo patrón que
argos-contracts-scenarios/validators/validate_fixtures.py: un
referencing.Registry construido a partir de los ficheros *.schema.json para
que los $ref relativos entre el envelope y los 10 contratos resuelvan.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

# negative/ y adversarial/ no organizan sus fixtures por carpeta de contrato
# (a diferencia de smoke/ y validation/): agrupan por caso de ataque/negativo
# y declaran a qué schema pertenece cada archivo en su manifest.yaml. Ver
# argos-contracts-scenarios/fixtures/{negative,adversarial}/manifest.yaml.
MANIFEST_DRIVEN_CATEGORIES = {"negative", "adversarial"}


@dataclasses.dataclass(frozen=True)
class Fixture:
    contract: str
    category: str
    path: pathlib.Path
    data: dict


def build_registry(contracts_path: pathlib.Path) -> Registry:
    schemas_dir = contracts_path / "schemas"
    envelope_path = contracts_path / "envelope" / "v1" / "argos-envelope.schema.json"
    resources = []
    for path in list(schemas_dir.rglob("*.schema.json")) + [envelope_path]:
        data = json.loads(path.read_text(encoding="utf-8"))
        resources.append((path.as_uri(), Resource.from_contents(data)))
    return Registry().with_resources(resources)


def validator_for(contracts_path: pathlib.Path, registry: Registry, contract: str) -> Draft202012Validator:
    schema_path = contracts_path / "schemas" / contract / "v1.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"No existe schemas/{contract}/v1.schema.json en {contracts_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema = {**schema, "$id": schema_path.as_uri()}
    return Draft202012Validator(schema, registry=registry)


def _load_folder_fixtures(contracts_path: pathlib.Path, category: str, contract: str) -> list[Fixture]:
    contract_dir = contracts_path / "fixtures" / category / contract
    if not contract_dir.exists():
        return []
    fixtures = []
    for path in sorted(contract_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        fixtures.append(Fixture(contract=contract, category=category, path=path, data=data))
    return fixtures


def _load_manifest_fixtures(contracts_path: pathlib.Path, category: str, contract: str) -> list[Fixture]:
    manifest_path = contracts_path / "fixtures" / category / "manifest.yaml"
    if not manifest_path.exists():
        return []
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    fixtures = []
    for case in manifest.get("cases", []):
        if case["schema"] != contract:
            continue
        path = contracts_path / "fixtures" / category / case["fixture"]
        data = json.loads(path.read_text(encoding="utf-8"))
        fixtures.append(Fixture(contract=contract, category=category, path=path, data=data))
    return fixtures


def load_fixtures(contracts_path: pathlib.Path, category: str, contract: str) -> list[Fixture]:
    """category: smoke | validation | negative | adversarial."""
    if category in MANIFEST_DRIVEN_CATEGORIES:
        return _load_manifest_fixtures(contracts_path, category, contract)
    return _load_folder_fixtures(contracts_path, category, contract)


def validate_fixture(contracts_path: pathlib.Path, registry: Registry, fixture: Fixture) -> list[str]:
    """Devuelve la lista de mensajes de error del schema (vacía si es válido)."""
    validator = validator_for(contracts_path, registry, fixture.contract)
    return [e.message for e in validator.iter_errors(fixture.data)]
