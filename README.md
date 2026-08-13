# argos-validation

Evaluación independiente de `argos-ai-xdr`: mide calidad, seguridad, trazabilidad y reproducibilidad del sistema. No contiene lógica productiva que sea evaluada por el propio repositorio — eso vive en `argos-core`/`argos-cyber-tools`/`argos-smartops`.

Parte de la organización [`argos-ai-xdr`](https://github.com/argos-ai-xdr). Arquitectura autoritativa y ADR en [`argos-control`](https://github.com/argos-ai-xdr/argos-control). Contratos y fixtures en [`argos-contracts-scenarios`](https://github.com/argos-ai-xdr/argos-contracts-scenarios).

## Contenido

| Carpeta | Contenido |
| --- | --- |
| `harness/` | `runner/` (orquesta una suite), `loaders/` (fixtures + schemas), `reporters/` (`run_summary.json`), `evidence/` (manifiesto de evidencia del run) |
| `evaluators/` | Un módulo por métrica: detection, triage, prioritization, tool-calls, policy, hallucination, traceability, human-agreement |
| `suites/` | Qué evaluadores + fixtures + thresholds aplican por caso: `c06/`, `c07/`, `c08/`, `argos-cyb-01/`, `integration/`, `regression/`, `adversarial/` |
| `thresholds/` | Tres niveles de rigor: `smoke.yaml`, `validation.yaml`, `acceptance.yaml` |
| `ground-truth/` | Schemas y manifiestos de ground truth (no el dataset real, ver ADR-016) |
| `modes/` | `golden/`, `mock/`, `real/`, `adversarial/` — qué dependencias están simuladas en cada modo |
| `reports/` | Plantillas y schema de `run_summary.json` |
| `tests/` | Pruebas de este propio harness (no del XDR) |

## Cómo se relaciona con los demás repositorios

`argos-validation` **lee** fixtures y schemas de `argos-contracts-scenarios` (nunca los reescribe) y **evalúa** contra los criterios AC01-AC14 definidos en `argos-control/project/acceptance/acceptance-criteria.yaml`. No ejecuta el XDR: en modo `golden`/`mock` evalúa fixtures fijos; en modo `real` se conecta a un despliegue de `argos-platform` corriendo `argos-core`/`argos-cyber-tools`.

Para desarrollo local, este repositorio espera encontrar `argos-contracts-scenarios` clonado como directorio hermano (`../argos-contracts-scenarios`) o en la ruta que indique la variable `ARGOS_CONTRACTS_PATH`. Ver `docs/development.md`.

## Reglas comunes de la organización

* Rama principal: `main`. Sin rama permanente `develop`.
* Pull request obligatorio; revisión de `CODEOWNERS`; checks de CI obligatorios.
* Prohibido push directo, force-push y borrado de `main`.
* Un gate crítico rojo bloquea la promoción (ver `argos-control/governance/gates/gates.md`).
* No se mezclan smoke y validation sets; `validation/` de `argos-contracts-scenarios` nunca se usa para ajustar umbrales.
* Ningún dataset real, evidencia generada ni secreto en Git.
