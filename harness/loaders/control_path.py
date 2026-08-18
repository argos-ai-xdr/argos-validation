"""Resuelve dónde vive el checkout de argos-control.

Orden de resolución (mismo patrón que contracts_path.py):
1. Variable de entorno ARGOS_CONTROL_PATH (CI: checkout hermano en
   _control/, ver .github/workflows/ci.yaml y
   argos-control/.github/workflows/reusable-python-ci.yaml).
2. `fallback` que pase el caller -- en harness/traceability.py es
   `org_root / "argos-control"`, lo que preserva el comportamiento de
   tests/test_traceability.py (construye un org_root de tmp_path con
   "argos-control" como subdirectorio literal, sin variables de entorno).
"""
from __future__ import annotations

import os
import pathlib

CONTROL_ENV_VAR = "ARGOS_CONTROL_PATH"


def resolve_control_path(*, fallback: pathlib.Path) -> pathlib.Path | None:
    """Devuelve la ruta al checkout de argos-control, o None si no está
    disponible -- a diferencia de contracts_path.resolve_contracts_path(),
    no lanza: los callers de este módulo (harness/traceability.py) ya
    tratan "no disponible" como warning, no como error fatal (TRACE-01
    solo puede cruzar story_ids si el backlog real está accesible, pero
    un checkout local sin los 7 repos hermanos sigue siendo un uso
    legítimo)."""
    env_value = os.environ.get(CONTROL_ENV_VAR)
    if env_value:
        path = pathlib.Path(env_value).expanduser().resolve()
        return path if path.exists() else None

    return fallback if fallback.exists() else None
