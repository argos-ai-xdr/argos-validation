"""chaos: frontera de autorización fail-closed para experimentos de Chaos
Engineering (ADR-068, argos-control). Mismo patrón que
`argos-cyber-tools/mcp_gateway.Gateway.authorize` (R0-01): cualquier
ausencia o inconsistencia deniega, nunca se asume seguro por defecto.

Invariante no negociable (ADR-068): `CHAOS TOOL != SOAR != MCP EXECUTOR !=
production action`. Este módulo NO ejecuta ningún experimento -- solo
decide si un `ChaosExperimentRequest` puede autorizarse. La inyección real
(Chaos Mesh) vive en `argos-platform/chaos/`, fuera de este repositorio;
este es el gate que un orquestador de caos real debería consultar ANTES de
aplicar cualquier `PodChaos`/`NetworkChaos`/etc. -- exactamente como
`mcp_gateway.Gateway.authorize` es el gate que un ejecutor SOAR consulta
antes de aplicar una acción de respuesta real.

Un experimento de caos NUNCA reutiliza autorizaciones productivas de
ARGOS (ninguna `Approval`/`SafetyEnvenlope` de `mcp_gateway` participa
aquí) -- espacio de autorización disjunto a propósito.
"""
from __future__ import annotations

import dataclasses

_MANDATORY_FIELDS = (
    "experiment_id",
    "hypothesis",
    "target",
    "expected_steady_state",
    "blast_radius",
    "duration_seconds",
    "abort_conditions",
    "recovery_procedure",
)


@dataclasses.dataclass(frozen=True)
class ChaosExperimentRequest:
    experiment_id: str
    hypothesis: str
    target: str
    expected_steady_state: str
    blast_radius: str
    duration_seconds: int
    abort_conditions: tuple[str, ...]
    recovery_procedure: str
    environment: str
    chaos_enabled: bool
    namespace: str


@dataclasses.dataclass(frozen=True)
class ChaosAuthorizationResult:
    allowed: bool
    reason: str


class ChaosSafetyGuard:
    """Autoriza (o deniega) un `ChaosExperimentRequest`. `namespace_allowlist`
    y `allowed_environments` son cerrados -- todo lo no listado es DENY, no
    "permitido por omisión" (mismo criterio que
    `policies.target_allowlists` en argos-cyber-tools)."""

    def __init__(
        self,
        *,
        allowed_environments: frozenset[str] = frozenset({"cyber-range", "test", "integration"}),
        namespace_allowlist: frozenset[str] = frozenset({"argos-cyber-range"}),
        max_parallel_experiments: int = 1,
    ) -> None:
        self._allowed_environments = allowed_environments
        self._namespace_allowlist = namespace_allowlist
        self._max_parallel_experiments = max_parallel_experiments
        self._active_experiment_ids: set[str] = set()

    def authorize(self, request: ChaosExperimentRequest) -> ChaosAuthorizationResult:
        for field_name in _MANDATORY_FIELDS:
            value = getattr(request, field_name)
            if value is None or value == "" or value == ():
                return ChaosAuthorizationResult(False, f"campo obligatorio ausente o vacío: {field_name}")

        if not request.chaos_enabled:
            return ChaosAuthorizationResult(False, "chaos_enabled=false -- experimentos de caos deshabilitados")

        if request.environment not in self._allowed_environments:
            return ChaosAuthorizationResult(
                False, f"environment {request.environment!r} fuera de allowed_environments {sorted(self._allowed_environments)}"
            )

        if request.namespace not in self._namespace_allowlist:
            return ChaosAuthorizationResult(
                False, f"namespace {request.namespace!r} fuera de namespace_allowlist {sorted(self._namespace_allowlist)}"
            )

        if request.experiment_id in self._active_experiment_ids:
            return ChaosAuthorizationResult(False, f"experiment_id {request.experiment_id!r} ya está activo (replay)")

        if len(self._active_experiment_ids) >= self._max_parallel_experiments:
            return ChaosAuthorizationResult(
                False,
                f"max_parallel_experiments={self._max_parallel_experiments} alcanzado "
                f"(activos: {sorted(self._active_experiment_ids)})",
            )

        self._active_experiment_ids.add(request.experiment_id)
        return ChaosAuthorizationResult(True, "autorizado")

    def complete_experiment(self, experiment_id: str) -> None:
        """Libera el cupo de `max_parallel_experiments` -- debe llamarse tras
        RECOVER (ver ciclo de vida en ADR-068), nunca antes de confirmar que
        el sistema volvió a steady-state."""
        self._active_experiment_ids.discard(experiment_id)

    def is_active(self, experiment_id: str) -> bool:
        return experiment_id in self._active_experiment_ids
