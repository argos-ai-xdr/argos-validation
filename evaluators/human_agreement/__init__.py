"""Judge-human agreement (umbral provisional del bootstrap de argos-ai-xdr:
>= 0.70). No corresponde a un único AC literal del documento maestro v0.5;
mide si el juicio automatizado (p. ej. un LLM-judge sobre Recommendation)
coincide con la revisión humana.

Nota de nombre: evaluators/human_agreement/ (con guion bajo) en vez de
'human-agreement' por la misma razón que evaluators/tool_calls/ — ver
evaluators/README.md.

No hay ground truth humano todavía en ningún fixture (pendiente de S1-S2,
donde SOC Analyst/Approver etiquetará una muestra real). Esta función
implementa el cálculo de acuerdo en sí (correcto y testeable con datos
sintéticos) para que esté listo en cuanto exista `human_labels/manifest.yaml`
en ../../ground-truth/manifests/; hasta entonces, se llama con
`human_labels=None` y el harness debe omitir este check en vez de simular un
número.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric


def evaluate(
    fixtures: list[dict],
    *,
    human_labels: dict[str, str] | None = None,
    system_labels: dict[str, str] | None = None,
    contracts_path: pathlib.Path | None = None,
) -> Metric:
    if not human_labels or not system_labels:
        raise NotImplementedError(
            "human_agreement requiere human_labels y system_labels reales; "
            "no existen todavía (ver ground-truth/manifests/). No se debe "
            "invocar este evaluador desde una suite hasta que existan."
        )

    common_ids = set(human_labels) & set(system_labels)
    if not common_ids:
        return Metric(
            name="judge_human_agreement",
            value=0.0,
            detail="sin IDs en común entre human_labels y system_labels",
            sample_size=0,
        )

    agreements = sum(1 for i in common_ids if human_labels[i] == system_labels[i])
    agreement_rate = agreements / len(common_ids)

    return Metric(
        name="judge_human_agreement",
        value=agreement_rate,
        detail=f"{agreements}/{len(common_ids)} etiquetas coinciden",
        sample_size=len(common_ids),
    )
