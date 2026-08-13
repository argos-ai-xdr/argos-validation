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

## Relación con `argos-control/project/acceptance/acceptance-criteria.yaml`

Ese archivo es la fuente única de verdad de AC01-AC14. `thresholds/acceptance.yaml` de este repositorio referencia esos mismos valores — no los redefine con números distintos. `thresholds/smoke.yaml` y `thresholds/validation.yaml` son más permisivos (para CI rápida y para calibración) pero nunca más laxos que "no crítico" para un AC marcado crítico.
