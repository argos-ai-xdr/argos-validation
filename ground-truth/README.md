# ground-truth/

| Carpeta | Contenido |
| --- | --- |
| [`schemas/`](schemas/) | Estructura de los manifiestos de ground truth que consume el harness |
| [`manifests/`](manifests/) | Manifiestos reales (hoy: solo `argos-cyb-01.yaml`, event_ids esperados) |

No contiene el dataset real ni etiquetas humanas (ADR-016) — solo los IDs/valores mínimos necesarios para comparar. `ground-truth/manifests/` es de este repositorio (`argos-validation`), distinto de `argos-contracts-scenarios/scenarios/ARGOS-CYB-01/ground-truth/`, que documenta F01-F09 en prosa para humanos; este es el que consume código.

## Laboratorio de detección inteligente (`IDLAB-01..08`, ADR-070)

La reunión externa que originó `ADR-070` proponía "Fases 1-8" para el laboratorio de entrenamiento/validación del detector estadístico — renombradas aquí `IDLAB-01..08` (workstream experimental de `ADR-069`, no una tercera taxonomía de fases paralela a A→L/M/N): cyber-range RKE2/OpenNebula, Wazuh SIEM, sensores, inyección de ataques/caos, baseline nominal, ground truth, detección inteligente, feedback SOC. Ninguno desplegado todavía (`BLOCKED_EXTERNAL`).

**Límite explícito del laboratorio, documentado para no sobre-afirmar**: un RKE2 single-node (el perfil propuesto) **no valida HA real de control-plane** (failover, quorum multi-nodo, recuperación) — sirve para detección funcional, integración de pipeline, recolección de datos y evaluación de modelo, no para afirmar resiliencia de control-plane. Dos perfiles, sin mezclar en el primer MVP:

* `LAB-K8S`: los 3 sistemas monitorizados son workloads/nodos Kubernetes → Chaos Mesh (`ADR-068`).
* `LAB-VM`: los 3 sistemas monitorizados son VMs → mecanismo de caos de infraestructura sin decidir (`TBD`, no se elige una herramienta sin evaluarla).

**Separación de datasets, no aleatoria por fila** (`DE-27`, `evaluators/dataset_integrity`): un split aleatorio puede dejar el mismo ataque sobre el mismo host repartido entre `training` y `test`, inflando artificialmente las métricas. La separación real debe ser por tiempo/escenario/host — `evaluators.dataset_integrity.evaluate` prueba estructuralmente que ningún `(scenario_id, host_id)` aparece a la vez en ambos conjuntos.
