"""Resuelve dónde vive el checkout de argos-control vía la variable de
entorno ARGOS_CONTROL_PATH (CI: checkout hermano en _control/, ver
.github/workflows/ci.yaml y
argos-control/.github/workflows/reusable-python-ci.yaml).

Solo la variable de entorno: a diferencia de contracts_path.py, este
resolver NO intenta un fallback "hermano por convención" propio, porque
harness/traceability._load_backlog ya tiene su propio fallback
(org_root / "argos-control") y es el único caller — mezclar ambos aquí
haría imposible distinguir "sin argos-control disponible" (aislamiento
deliberado en tests/test_traceability.py, que siempre pasa org_root
explícito) de "argos-control real vía checkout de CI" (org_root
defaulteado). Ver harness/traceability.py:validate() para dónde se
decide cuál aplica.
"""
from __future__ import annotations

import os
import pathlib

CONTROL_ENV_VAR = "ARGOS_CONTROL_PATH"


def resolve_control_path_from_env() -> pathlib.Path | None:
    env_value = os.environ.get(CONTROL_ENV_VAR)
    if not env_value:
        return None
    path = pathlib.Path(env_value).expanduser().resolve()
    return path if path.exists() else None
