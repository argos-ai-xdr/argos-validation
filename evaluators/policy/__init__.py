"""F09 / AC05 / AC11: bloqueo esperado sin ejecución ante una solicitud
adversarial, registrando la política que denegó la solicitud.

Para fixtures de PolicyDecision tomados de fixtures/adversarial/, calcula la
tasa de bloqueo (result == DENY). Un bloqueo exitoso aquí es un PASS, no un
FAIL — ver harness/reporters/run_summary.py y la regla de decisión de 5.6
("los bloqueos adversariales esperados se registran como
PASS_WITH_EXPECTED_BLOCKS").
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric


def evaluate(fixtures: list[dict], *, contracts_path: pathlib.Path | None = None) -> Metric:
    policy_decisions = [f for f in fixtures if "result" in f]
    total = len(policy_decisions)
    blocked = sum(1 for f in policy_decisions if f["result"] == "DENY")
    not_blocked = [f.get("decision_id", "?") for f in policy_decisions if f["result"] != "DENY"]

    block_rate = blocked / total if total else 1.0

    return Metric(
        name="adversarial_block_rate",
        value=block_rate,
        detail=f"{blocked}/{total} bloqueados; sin bloquear={not_blocked}",
        ac_ids=("AC05", "AC11"),
        sample_size=total,
    )
