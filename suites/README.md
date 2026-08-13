# suites/

Cada `suite.yaml` lista `checks`: qué evaluador corre contra qué `(category, contract)` de `argos-contracts-scenarios/fixtures/`, con qué `metric_name` (para casar con `thresholds/*.yaml`) y qué `extra` (argumentos propios del evaluador, p. ej. `expected_event_ids`).

| Suite | Corresponde a |
| --- | --- |
| [`c06/`](c06/suite.yaml) | Inventario, vulnerabilidades, priorización |
| [`c07/`](c07/suite.yaml) | Exposición, RBAC, ruta de ataque (solo lo evaluable como PolicyDecision hoy) |
| [`c08/`](c08/suite.yaml) | Detección, correlación, Incident v1 |
| [`argos-cyb-01/`](argos-cyb-01/suite.yaml) | Escenario completo, IDs específicos del escenario |
| [`integration/`](integration/suite.yaml) | Coherencia cruzada entre contratos, sin atarse a IDs de un escenario |
| [`regression/`](regression/suite.yaml) | Igual que arriba pero sobre `fixtures/validation/` (congelado) |
| [`adversarial/`](adversarial/suite.yaml) | F09 — bloqueo esperado, no evaluación de calidad |

Ejecutar: `python -m harness.runner.cli --suite suites/c06/suite.yaml --thresholds thresholds/smoke.yaml`.
