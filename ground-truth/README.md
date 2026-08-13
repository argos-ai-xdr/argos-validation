# ground-truth/

| Carpeta | Contenido |
| --- | --- |
| [`schemas/`](schemas/) | Estructura de los manifiestos de ground truth que consume el harness |
| [`manifests/`](manifests/) | Manifiestos reales (hoy: solo `argos-cyb-01.yaml`, event_ids esperados) |

No contiene el dataset real ni etiquetas humanas (ADR-016) — solo los IDs/valores mínimos necesarios para comparar. `ground-truth/manifests/` es de este repositorio (`argos-validation`), distinto de `argos-contracts-scenarios/scenarios/ARGOS-CYB-01/ground-truth/`, que documenta F01-F09 en prosa para humanos; este es el que consume código.
