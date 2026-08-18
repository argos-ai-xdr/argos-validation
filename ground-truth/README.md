# ground-truth/

| Carpeta | Contenido |
| --- | --- |
| [`schemas/`](schemas/) | Estructura de los manifiestos de ground truth que consume el harness |
| [`manifests/`](manifests/) | Manifiestos reales (`argos-cyb-01.yaml`, event_ids esperados) + ejemplos de formato IDLAB-05/06 (ver abajo) |

No contiene el dataset real ni etiquetas humanas (ADR-016) — solo los IDs/valores mínimos necesarios para comparar. `ground-truth/manifests/` es de este repositorio (`argos-validation`), distinto de `argos-contracts-scenarios/scenarios/ARGOS-CYB-01/ground-truth/`, que documenta F01-F09 en prosa para humanos; este es el que consume código.

## Laboratorio de detección inteligente (`IDLAB-01..08`, ADR-070)

La reunión externa que originó `ADR-070` proponía "Fases 1-8" para el laboratorio de entrenamiento/validación del detector estadístico — renombradas aquí `IDLAB-01..08` (workstream experimental de `ADR-069`, no una tercera taxonomía de fases paralela a A→L/M/N): cyber-range RKE2/OpenNebula, Wazuh SIEM, sensores, inyección de ataques/caos, baseline nominal, ground truth, detección inteligente, feedback SOC. Ninguno desplegado todavía (`BLOCKED_EXTERNAL`).

**Límite explícito del laboratorio, documentado para no sobre-afirmar**: un RKE2 single-node (el perfil propuesto) **no valida HA real de control-plane** (failover, quorum multi-nodo, recuperación) — sirve para detección funcional, integración de pipeline, recolección de datos y evaluación de modelo, no para afirmar resiliencia de control-plane. Dos perfiles, sin mezclar en el primer MVP:

* `LAB-K8S`: los 3 sistemas monitorizados son workloads/nodos Kubernetes → Chaos Mesh (`ADR-068`).
* `LAB-VM`: los 3 sistemas monitorizados son VMs → mecanismo de caos de infraestructura sin decidir (`TBD`, no se elige una herramienta sin evaluarla).

**Separación de datasets, no aleatoria por fila** (`DE-27`, `evaluators/dataset_integrity`): un split aleatorio puede dejar el mismo ataque sobre el mismo host repartido entre `training` y `test`, inflando artificialmente las métricas. La separación real debe ser por tiempo/escenario/host — `evaluators.dataset_integrity.evaluate` prueba estructuralmente que ningún `(scenario_id, host_id)` aparece a la vez en ambos conjuntos.

### Formato IDLAB-05/06, andamiaje para cuando exista telemetría real

`harness/loaders/detection_ground_truth.py` (`load_nominal_baseline_manifest`, `load_detection_ground_truth_manifest`, `split_records_for_dataset_integrity`) + dos schemas nuevos:

* [`schemas/nominal-baseline-manifest.schema.json`](schemas/nominal-baseline-manifest.schema.json) (IDLAB-05): metadatos de una captura "normal" antes de inyectar ataques. `known_attacks_present` está fijado a `const: false` por schema, no solo por convención. `source_mode` nunca `CANDIDATE` (es telemetría de entrada, no un artefacto de ARGOS).
* [`schemas/detection-ground-truth-manifest.schema.json`](schemas/detection-ground-truth-manifest.schema.json) (IDLAB-06): etiquetas `ATTACK`/`BENIGN` por `(scenario_id, host_id)` con `split` `train`/`test` explícito por registro -- `split_records_for_dataset_integrity` alimenta directamente `evaluators.dataset_integrity.evaluate` (DE-27).

`manifests/idlab-05-nominal-baseline-example.yaml` y `manifests/idlab-06-detection-ground-truth-example.yaml` son EJEMPLOS que demuestran que el formato y el loader funcionan de verdad (probado también end-to-end contra `DE-27`, incluido un control negativo que SÍ detecta fuga) -- **no son telemetría ni etiquetas reales**. Nada de esto se ha ejecutado contra un laboratorio real todavía (`BLOCKED_EXTERNAL`).
