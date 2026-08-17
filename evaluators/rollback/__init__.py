"""AC12 (Rollback): rollback success = 1.00 y estado posterior coincide
con baseline salvo artefactos de auditoría.

Un ActionResult con `status=rolled_back` afirma que una contención previa
se revirtió; `verification.passed` es la única evidencia disponible en el
propio contrato de que el estado posterior realmente coincide con el
baseline (ver schemas/action-result/v1.schema.json: "Resultado de la
verificación posterior a la ejecución (AC11-AC12)"). Un rollback marcado
`rolled_back` sin verificación, o con `verification.passed=false`,
no puede contar como éxito — sería afirmar una restauración que nadie
comprobó.

Sin ActionResult `rolled_back` en la muestra: no hay nada que evaluar
todavía (ningún rollback fue intentado), value=1.0 con sample_size=0 —
vacuo, no "probado y perfecto", igual que evaluators.resilience con
idempotency_key ausente.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric


def evaluate(fixtures: list[dict], *, contracts_path: pathlib.Path | None = None) -> Metric:
    rollbacks = [f for f in fixtures if f.get("status") == "rolled_back"]
    total = len(rollbacks)

    unverified: list[str] = []
    for rb in rollbacks:
        verification = rb.get("verification") or {}
        if verification.get("passed") is not True:
            unverified.append(rb.get("action_id", "?"))

    success_rate = (total - len(unverified)) / total if total else 1.0

    return Metric(
        name="rollback_success_rate",
        value=success_rate,
        detail=f"{total - len(unverified)}/{total} rollbacks con verification.passed=true; sin verificar o fallidos={unverified}",
        ac_ids=("AC12",),
        sample_size=total,
    )
