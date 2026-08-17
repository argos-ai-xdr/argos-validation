# evaluators/

Cada carpeta es un paquete Python con una función `evaluate(fixtures, *, contracts_path=None, **extra) -> evaluators.base.Metric` pura y testeable.

## Nota de nombres

El árbol de carpetas original (documento de bootstrap) usaba guiones (`tool-calls`, `human-agreement`). Python no permite guiones en nombres de paquete importables (`import evaluators.tool-calls` es un `SyntaxError`), así que esos dos viven en `tool_calls/` y `human_agreement/` (guion bajo). El resto coincide literalmente.

| Módulo | AC | Qué mide de verdad hoy |
| --- | --- | --- |
| [`detection/`](detection/) | AC06 | F1 real de `event_id` detectados vs. esperados |
| [`triage/`](triage/) | AC07 | Consistencia de severidad Incident vs. sus eventos miembro |
| [`prioritization/`](prioritization/) | AC04 | Completitud de evidencia (kev/epss/source_ref); "agreement experto" pendiente de etiquetas humanas |
| [`tool_calls/`](tool_calls/) | AC09 | Consistencia PolicyDecision vs. target allowlist |
| [`policy/`](policy/) | AC05, AC11 | Tasa de bloqueo de solicitudes adversariales (F09) |
| [`hallucination/`](hallucination/) | AC03, AC08 | Tasa de CVE con `source_ref` que no resuelve a un snapshot real |
| [`traceability/`](traceability/) | AC14 | Completitud de `run_id`/`payload_hash`/`evidence_refs` resolubles |
| [`resilience/`](resilience/) | AC13 | `ActionResult` agrupados por `idempotency_key`: mismo `status`/`changed_resources` entre reintentos, o violación |
| [`drift/`](drift/) | ARG-010 | `AssetSnapshot` agrupados por `asset_id`: drift as-designed/as-built cuya criticidad no se puede confirmar (campo ausente) |
| [`inventory_coverage/`](inventory_coverage/) | AC02 | Cobertura de `asset_id` vs. `expected_assets` (ground-truth/manifests/); activos críticos omitidos siempre visibles en `detail`, **lanza `NotImplementedError`** sin ground truth |
| [`approval_gate/`](approval_gate/) | AC10 | `ActionResult` con `dry_run=false` sin una `Approval` válida (rol/decision/caducidad) asociada por `action_id`; sin `contracts_path` cuenta como violación, no como PASS por defecto |
| [`rollback/`](rollback/) | AC12 | `ActionResult` con `status=rolled_back`: cuenta como éxito solo si `verification.passed=true`, nunca solo por llevar el status |
| [`human_agreement/`](human_agreement/) | — (umbral provisional) | Acuerdo juez-humano; **lanza `NotImplementedError`** si no se le pasan etiquetas reales — no inventa un número |

`prioritization` y `human_agreement` documentan explícitamente qué parte de su AC no es computable todavía sin datos que no existen en ningún fixture (S1-S2 los generará). Ningún evaluador de esta lista fabrica un valor plausible para una entrada que no puede evaluar de verdad.
