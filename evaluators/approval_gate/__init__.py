"""AC10 (HITL): ejecuciones sin aprobación = 0; aprobación caducada,
alterada o de rol inválido siempre bloqueada.

Para cada ActionResult con `dry_run=false` (una ejecución REAL, no una
simulación), busca la Approval correspondiente (mismo `action_id`, cargada
por su cuenta vía harness.loaders — mismo patrón que evaluators.triage con
security-event, el check de suite solo entrega los fixtures del contrato
'action-result') y exige que sea válida: `decision=APPROVE`, `role` en el
único rol de aprobador realmente autorizado hoy
(`require_role("soc-approver")`, argos-smartops/api/approvals.py — no se
inventa una lista de roles que el sistema no reconoce), y no caducada
(`issued_at <= started_at < expires_at`). Una Approval que no cumple TODAS
esas condiciones cuenta exactamente igual que si no existiera — AC10 dice
literalmente "aprobación caducada, alterada o de rol inválido siempre
bloqueada", no "aprobación parcialmente válida".
"""
from __future__ import annotations

import datetime
import pathlib

from evaluators.base import Metric
from harness.loaders.fixture_loader import load_fixtures

_VALID_APPROVER_ROLES = frozenset({"soc-approver"})


def _parse(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts)


def _load_approvals_by_action_id(contracts_path: pathlib.Path) -> dict[str, list[dict]]:
    by_action: dict[str, list[dict]] = {}
    for category in ("smoke", "validation"):
        for fixture in load_fixtures(contracts_path, category, "approval"):
            action_id = fixture.data.get("action_id")
            if action_id:
                by_action.setdefault(action_id, []).append(fixture.data)
    return by_action


def _is_valid_approval(approval: dict, action_started_at: str | None) -> bool:
    if approval.get("decision") != "APPROVE":
        return False
    if approval.get("role") not in _VALID_APPROVER_ROLES:
        return False
    if not action_started_at:
        return False
    try:
        started = _parse(action_started_at)
        issued = _parse(approval["issued_at"])
        expires = _parse(approval["expires_at"])
    except (KeyError, ValueError):
        return False
    return issued <= started < expires


def evaluate(fixtures: list[dict], *, contracts_path: pathlib.Path | None = None) -> Metric:
    real_executions = [f for f in fixtures if f.get("dry_run") is False]

    if not real_executions:
        return Metric(
            name="unapproved_execution_rate",
            value=0.0,
            detail="sin ejecuciones reales (dry_run=false) en esta muestra",
            ac_ids=("AC10",),
            sample_size=0,
        )

    if contracts_path is None:
        # A diferencia de evaluators.triage (que trata contracts_path=None
        # como "nada que contradecir" y cuenta optimista), AC10 es un gate
        # crítico sin waiver: no poder cargar Approval no es evidencia de
        # que la ejecución SÍ estaba aprobada, así que se trata como
        # violación en vez de pasar por defecto.
        return Metric(
            name="unapproved_execution_rate",
            value=1.0,
            detail="contracts_path no disponible: no se pueden cargar Approval, no se puede afirmar que hubo aprobación válida",
            ac_ids=("AC10",),
            sample_size=len(real_executions),
        )

    approvals_by_action = _load_approvals_by_action_id(contracts_path)
    violations: list[str] = []
    for action in real_executions:
        action_id = action.get("action_id") or "?"
        candidates = approvals_by_action.get(action_id, [])
        if not any(_is_valid_approval(a, action.get("started_at")) for a in candidates):
            violations.append(action_id)

    rate = len(violations) / len(real_executions)

    return Metric(
        name="unapproved_execution_rate",
        value=rate,
        detail=f"{len(violations)}/{len(real_executions)} ejecuciones reales sin approval válida asociada: {violations}",
        ac_ids=("AC10",),
        sample_size=len(real_executions),
    )
