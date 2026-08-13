"""Resuelve dónde vive el checkout de argos-contracts-scenarios.

Orden de resolución:
1. Variable de entorno ARGOS_CONTRACTS_PATH.
2. Directorio hermano ../argos-contracts-scenarios (convención de argos-ai-xdr).
"""
from __future__ import annotations

import os
import pathlib

CONTRACTS_ENV_VAR = "ARGOS_CONTRACTS_PATH"


class ContractsRepoNotFound(RuntimeError):
    pass


def resolve_contracts_path(start: pathlib.Path | None = None) -> pathlib.Path:
    env_value = os.environ.get(CONTRACTS_ENV_VAR)
    if env_value:
        path = pathlib.Path(env_value).expanduser().resolve()
        if not path.exists():
            raise ContractsRepoNotFound(
                f"{CONTRACTS_ENV_VAR}={env_value!r} no existe"
            )
        return path

    base = (start or pathlib.Path(__file__).resolve().parents[2])
    sibling = (base.parent / "argos-contracts-scenarios").resolve()
    if sibling.exists():
        return sibling

    raise ContractsRepoNotFound(
        "No se encontró argos-contracts-scenarios. Clónalo como hermano de "
        "este repositorio o define la variable de entorno "
        f"{CONTRACTS_ENV_VAR}."
    )
