"""AC04 (Priorización): agreement experto >= 0.75 y evidencia completa >= 0.95.

Este evaluador implementa hoy solo la mitad computable sin datos externos:
'evidencia completa' — fracción de VulnerabilityFinding con kev, epss y
source_ref presentes, que es lo que necesita cualquier fórmula de
priorización para no operar a ciegas.

'Agreement experto' requiere etiquetas humanas de prioridad que no existen
todavía en ningún fixture (S1-S2 las generará). Pasar `expert_labels` como
{finding_id: priority} activa ese segundo cálculo; sin él, la métrica de
agreement se omite explícitamente en el detalle en lugar de inventar un
número.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric

EVIDENCE_FIELDS = ("kev", "epss", "source_ref")


def _priority_score(finding: dict) -> float:
    epss = finding.get("epss", 0.0)
    kev_boost = 2.0 if finding.get("kev") else 1.0
    fix_penalty = 0.5 if finding.get("fix_available") else 1.0
    return epss * kev_boost * fix_penalty


def evaluate(
    fixtures: list[dict],
    *,
    expert_labels: dict[str, float] | None = None,
    contracts_path: pathlib.Path | None = None,
) -> Metric:
    findings = [f for f in fixtures if "cve_id" in f]
    total = len(findings)
    complete = sum(1 for f in findings if all(field in f for field in EVIDENCE_FIELDS))
    evidence_completeness = complete / total if total else 1.0

    agreement_note = "agreement experto no evaluado (sin expert_labels todavía, ver docstring)"
    if expert_labels:
        scored = {f["finding_id"]: _priority_score(f) for f in findings if "finding_id" in f}
        our_rank = sorted(scored, key=lambda k: scored[k], reverse=True)
        expert_rank = sorted(expert_labels, key=lambda k: expert_labels[k], reverse=True)
        agreement_note = f"our_rank={our_rank} expert_rank={expert_rank}"

    return Metric(
        name="prioritization_evidence_completeness",
        value=evidence_completeness,
        detail=f"{complete}/{total} findings con kev/epss/source_ref; {agreement_note}",
        ac_ids=("AC04",),
        sample_size=total,
    )
