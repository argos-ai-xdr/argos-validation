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

### Formato IDLAB-05/06 v2, andamiaje para cuando exista telemetría real

`harness/loaders/detection_ground_truth.py` (`load_nominal_baseline_manifest`, `load_detection_ground_truth_manifest`, `split_scenario_runs_for_dataset_integrity`, `scenario_runs_to_legacy_records`) + dos schemas:

* [`schemas/nominal-baseline-manifest.schema.json`](schemas/nominal-baseline-manifest.schema.json) (IDLAB-05): metadatos de una captura "normal" antes de inyectar ataques -- suficientes para reconstruir qué entorno, configuración (Wazuh/Falco/Cilium con hash), sensores e intervalo produjeron la captura (`environment`, `provenance`, `capture`). `dataset.known_attacks_present` fijado a `const: false` por schema. `contamination_check` es obligatorio (`required: const true`) y `contamination_status` excluye `CONTAMINATED` del enum a propósito -- una captura contaminada nunca llega a ser un `NominalBaselineManifest` válido, ni siquiera si `known_attacks_present` se declaró `false` por error de partida. `source_mode` nunca `CANDIDATE`.
* [`schemas/detection-ground-truth-manifest.schema.json`](schemas/detection-ground-truth-manifest.schema.json) (IDLAB-06): campañas de `scenario_runs` completos (técnica/MITRE, target, ejecución, observables esperados/observados, `ground_truth.label_source` de un enum cerrado que EXCLUYE `detector_output` -- el ground truth nunca puede derivarse del propio sistema evaluado) con `split` `TRAIN`/`TEST` por **`scenario_run_id` completo**, nunca por evento individual.

**`is_example: true`** (en `dataset` para IDLAB-05, a nivel raíz para IDLAB-06) fuerza `source_mode: SYNTHETIC` en todo el manifiesto por schema (`if`/`then`) -- ningún fixture de prueba de este repo puede acabar etiquetado como `REAL`. Los dos manifiestos de ejemplo (`manifests/idlab-05-nominal-baseline-example.yaml`, `manifests/idlab-06-detection-ground-truth-example.yaml`) lo declaran.

**DE-27 extendido** (`evaluators/dataset_integrity`), más allá del check original `(scenario_id, host_id)` (`evaluate`, que se mantiene y se sigue aplicando vía `scenario_runs_to_legacy_records`):

| Función | Qué detecta |
| --- | --- |
| `evaluate_scenario_run_id_leakage` | mismo `scenario_run_id` en TRAIN y TEST (manifiesto mal construido) |
| `evaluate_split_group_leakage` | mismo `split_group` (campaña/ventana temporal correlacionada) en ambos lados |
| `evaluate_event_ref_leakage` | mismo `event_ref` observado en ambos lados |
| `evaluate_evidence_ref_leakage` | mismo `evidence_ref` observado en ambos lados |
| `evaluate_label_provenance` | `ground_truth.label_source` derivado del propio detector (defensa en profundidad sobre el enum del schema) |
| `evaluate_baseline_contamination` | `NominalBaselineManifest` cuyo `contamination_check` indica un ataque conocido |

`manifests/idlab-05-nominal-baseline-example.yaml` y `manifests/idlab-06-detection-ground-truth-example.yaml` son EJEMPLOS que demuestran que el formato v2 y el loader funcionan de verdad (probado end-to-end contra las seis dimensiones de DE-27, incluidos controles negativos que SÍ detectan fuga) -- **no son telemetría ni etiquetas reales**. Nada de esto se ha ejecutado contra un laboratorio real todavía (`BLOCKED_EXTERNAL`).
