"""AC03 (fake/hallucinated CVE rate <= 0.01) y AC08 (grounding CTI:
inventados = 0).

Para cada VulnerabilityFinding, comprueba que source_ref apunta a un snapshot
real dentro del checkout de argos-contracts-scenarios (../../snapshots/ o un
fixture existente). Un finding cuyo source_ref no resuelve a nada real se
cuenta como "no fundamentado" — exactamente el caso de
fixtures/adversarial/fake-cve/, que apunta deliberadamente a una ruta
inexistente.
"""
from __future__ import annotations

import pathlib

from evaluators.base import Metric


def evaluate(fixtures: list[dict], *, contracts_path: pathlib.Path | None = None) -> Metric:
    findings = [f for f in fixtures if "cve_id" in f]
    total = len(findings)
    ungrounded: list[str] = []

    for finding in findings:
        source_ref = finding.get("source_ref", "")
        grounded = bool(source_ref) and contracts_path is not None and (contracts_path / source_ref).exists()
        if not grounded:
            ungrounded.append(finding.get("finding_id", "?"))

    ungrounded_rate = len(ungrounded) / total if total else 0.0

    return Metric(
        name="ungrounded_cve_rate",
        value=ungrounded_rate,
        detail=f"{len(ungrounded)}/{total} sin source_ref resoluble: {ungrounded}",
        ac_ids=("AC03", "AC08"),
        sample_size=total,
    )
