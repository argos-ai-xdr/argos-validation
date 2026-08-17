# Arquitectura de argos-validation

Este repositorio implementa el rol "QA/Security Observer" de forma automatizable (ver `argos-control/governance/raci/raci.md`): mide, no construye.

## Flujo

```
argos-contracts-scenarios/fixtures/  ─┐
argos-contracts-scenarios/schemas/   ─┼─▶ harness/loaders ─▶ evaluators/* ─▶ harness/reporters ─▶ run_summary.json
argos-control/project/acceptance/    ─┘        (según suites/ y thresholds/)         │
                                                                                       ▼
                                                                          harness/evidence (manifest.json)
```

* `harness/loaders` valida cada fixture contra su schema (reutiliza el mismo patrón de `argos-contracts-scenarios/validators/validate_fixtures.py`: `$ref` cruzado resuelto con `referencing.Registry`) antes de pasarlo a un evaluador — un fixture inválido nunca debe producir una métrica silenciosamente incorrecta.
* Cada `evaluators/<nombre>` implementa una función pura: `(fixtures, ground_truth) -> Metric`. Sin acceso a red salvo en `modes/real/`.
* `harness/reporters` combina las métricas de todos los evaluadores de una suite contra los `thresholds/` correspondientes y produce el resultado `PASS` / `FAIL` / `PASS_WITH_EXPECTED_BLOCKS` por AC.
* `harness/evidence` escribe el manifiesto del run (sin chain-of-thought, ADR-016) — el contenido real de evidencia grande vive fuera de Git (Ceph RGW, ADR-006); este repositorio solo produce el manifiesto.

## Autonomous Validation: test/simulate/replay vs. execute/contain

Prompt maestro de arquitectura objetivo §45 (ADR-051, Fase C): las
acciones de MEDICIÓN (correr una suite, simular un escenario, re-validar
un run pasado) tienen libertad de ejecución automática; las acciones de
IMPACTO REAL sobre el sistema objetivo (`execute`, `contain`) exigen
siempre una `Approval` humana válida (ADR-011). Este repositorio es la
prueba viviente de esa separación, no una declaración aspiracional:

* Ningún módulo de `evaluators/` o `harness/` importa
  `argos-cyber-tools/policies/approval` ni conoce el concepto
  `ApprovalStore`/`approval_id` — verificado por grep, cero resultados.
  Un evaluador no PUEDE bloquearse esperando una aprobación porque no
  tiene ninguna vía de pedirla.
* `harness/checkpoints.validate_run()`, `harness/acceptance.run_acceptance()`
  y `harness/reproducibility.check_reproducibility()` corren de principio
  a fin sin ningún punto de espera humana — su "impacto" se limita a leer
  fixtures/evidencia ya existentes y escribir un `run_summary`/manifiesto
  propios de este repositorio, nunca a mutar el sistema objetivo.
* Los ejecutores que SÍ mutan estado real (`argos-cyber-tools/executors/`)
  viven en un repositorio distinto y pasan siempre por
  `mcp_gateway.Gateway.authorize()`, que exige `current_plan_hash` y una
  `Approval` válida para `execute` — la frontera está en el propio grafo
  de imports entre repos, no solo en un `if` en tiempo de ejecución.

Este principio no crea ningún subsistema nuevo (no hay un "modo
autónomo" configurable en código): documenta un invariante que ya existe
por construcción, para que quede citable en vez de implícito.

## Relación con `argos-control/project/acceptance/acceptance-criteria.yaml`

Ese archivo es la fuente única de verdad de AC01-AC14. `thresholds/acceptance.yaml` de este repositorio referencia esos mismos valores — no los redefine con números distintos. `thresholds/smoke.yaml` y `thresholds/validation.yaml` son más permisivos (para CI rápida y para calibración) pero nunca más laxos que "no crítico" para un AC marcado crítico.
