# chaos/

Chaos Engineering & Chaos Monkey Validation Profile (ADR-068, `argos-control`). Frontera de autorización fail-closed para experimentos de fault injection sobre el cyber-range — **nunca** un camino de ejecución productivo.

| Archivo | Contenido |
| --- | --- |
| [`__init__.py`](__init__.py) | `ChaosSafetyGuard`/`ChaosExperimentRequest`/`ChaosAuthorizationResult` — mismo patrón fail-closed que `argos-cyber-tools/mcp_gateway.Gateway.authorize` (R0-01): cualquier campo obligatorio ausente, `chaos_enabled=false`, `environment`/`namespace` fuera de allowlist, o cupo de `max_parallel_experiments` agotado → `DENY`. |
| [`scenarios/catalog.yaml`](scenarios/catalog.yaml) | 20 escenarios (`CHAOS-01..20`) con los campos obligatorios que exige el guard. `status: DESIGNED` (declarado, no ejecutado) salvo `CHAOS-16`/`CHAOS-20`, que tienen una regresión local ejecutable sin clúster real (`status: TESTED_LOCALLY`, ver `test_ref`). |

## Lo que este módulo NO hace

No inyecta ningún fallo real (eso vive en `argos-platform/chaos/`, Chaos Mesh) y no ejecuta ninguna acción de respuesta — es exclusivamente la decisión de "¿se puede autorizar este experimento?", análoga a como `mcp_gateway.Gateway.authorize` decide "¿se puede autorizar esta acción de respuesta?" sin ejecutarla él mismo. Un experimento de caos **nunca** reutiliza autorizaciones productivas de ARGOS (ninguna `Approval`/`SafetyEnvelope` participa aquí).

## Estado real (no afirmar más de lo que hay)

* `ChaosSafetyGuard`: `IMPLEMENTED_LOCALLY_AND_TESTED` (17 tests, `tests/test_chaos_safety_guard.py`).
* Catálogo de 20 escenarios: declarado y probado estructuralmente contra el guard (`tests/test_chaos_scenario_catalog.py`), no ejecutado contra un clúster real — `BLOCKED_EXTERNAL` (mismo bloqueo que `ARG-021`/Shuffle: no hay clúster real disponible en este entorno).
* Quality gates `CH-01..12` (ver `ADR-068`): todos `NOT_EVALUATED` salvo `CH-04`/`CH-07` sobre el camino R0-01 (`CHAOS-16`), que sí tienen prueba local real.
