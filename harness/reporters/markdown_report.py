"""Renderiza run_summary.json a un informe Markdown offline legible
(documento maestro v0.5, 5.8: "Informe HTML offline"; aquí Markdown como
paso previo — cualquier visor lo convierte a HTML sin dependencias nuevas).
"""
from __future__ import annotations

import pathlib
import string

TEMPLATE_PATH = pathlib.Path(__file__).resolve().parents[2] / "reports" / "templates" / "run_summary.md.template"


def render(summary: dict) -> str:
    template = string.Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    gate_rows = "\n".join(
        f"* **{name}**: {r['gate']} — {r['reason']} (`{r['metric']['value']}`, muestra={r['metric']['sample_size']})"
        for name, r in summary["results"].items()
    )
    critical_failures = "\n".join(f"* {name}" for name in summary["critical_failures"]) or "Ninguno."
    warnings = "\n".join(f"* {name}" for name in summary["warnings"]) or "Ninguno."
    return template.substitute(
        suite=summary["suite"],
        mode=summary["mode"],
        run_id=summary["run_id"],
        generated_at=summary["generated_at"],
        overall=summary["overall"],
        gate_rows=gate_rows,
        critical_failures=critical_failures,
        warnings=warnings,
    )
