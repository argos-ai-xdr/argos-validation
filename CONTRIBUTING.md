# Contribuir a argos-validation

1. Toda historia debe existir como issue `ARG-###` (ver `argos-control/project/backlog/backlog.yaml`). Primeras historias: ARG-006 (harness, thresholds, report y producer/consumer tests), ARG-024 (suite adversarial F09, regresión y expected blocks), ARG-027 (automatizar AC01-AC14, DRR y release candidate).
2. Rama de trabajo: `feat/ARG-###-descripcion-corta`, `fix/...`.
3. Pull request obligatorio contra `main`. Sin push directo, force-push ni borrado de `main`.
4. Un evaluador nuevo:
   - vive en `evaluators/<nombre>/`, expone una función pura testeable (input: fixtures/ground truth; output: métrica + detalle), sin efectos secundarios;
   - declara en su docstring qué AC de `argos-control/project/acceptance/acceptance-criteria.yaml` implementa;
   - tiene pruebas en `tests/` con al menos un caso que pase el umbral y uno que lo incumpla.
5. Cambiar un umbral en `thresholds/`: requiere justificación en el PR (qué datos de S1-S2 lo motivan) y no puede relajar un gate marcado crítico en `argos-control/governance/gates/gates.md` sin una excepción aprobada.
6. `validation/` de `argos-contracts-scenarios` nunca se usa para ajustar un evaluador o un umbral — solo `smoke/` y datos propios de `modes/mock`.
7. `make validate` y `make test` deben pasar antes de abrir el PR.
