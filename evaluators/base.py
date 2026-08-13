"""Tipo común devuelto por todos los evaluadores.

Cada evaluador expone una función pura ``evaluate(...) -> Metric``. Ningún
evaluador decide PASS/FAIL por sí mismo contra un umbral externo — eso lo hace
``harness.reporters.run_summary`` comparando ``Metric.value`` contra
``thresholds/*.yaml``. El evaluador solo calcula el valor y explica cómo.
"""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Metric:
    name: str
    value: float
    detail: str
    ac_ids: tuple[str, ...] = ()
    sample_size: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "detail": self.detail,
            "ac_ids": list(self.ac_ids),
            "sample_size": self.sample_size,
        }
