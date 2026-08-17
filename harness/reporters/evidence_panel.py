"""ARG-026 (P1, confirmado prioritario — propuesta v0.6.25.4, §15.16):
panel operativo mínimo de evidencia.

"Slice: índice por run/CP/AC, estado, métricas, decisiones, hashes y
acceso a artefactos; no exige analítica avanzada" — por eso esto es HTML
estático sin JS ni gráficas, generado a partir de los `run_summary.json` +
`evidence_manifest.json` que `harness.runner.cli` YA escribe en disco, uno
por directorio de run. No inventa una fuente de verdad nueva.

"La reconstrucción offline del evidence pack no depende de la
disponibilidad del panel": este módulo SOLO lee y presenta artefactos que
ya existen — si el panel nunca se genera, o el HTML se pierde, cada
run_summary.json/evidence_manifest.json sigue siendo completo y
autocontenido por sí solo (misma garantía que evidence/manifest.py). El
panel es una vista de conveniencia, nunca la única copia.
"""
from __future__ import annotations

import dataclasses
import datetime
import html
import json
import pathlib


@dataclasses.dataclass(frozen=True)
class RunRecord:
    run_dir: pathlib.Path
    summary_path: pathlib.Path
    summary: dict
    manifest_path: pathlib.Path | None
    manifest: dict | None


def discover_runs(root: pathlib.Path) -> list[RunRecord]:
    """Un run = un run_summary.json en disco. evidence_manifest.json es
    opcional (algún caller de run_suite podría no haberlo escrito) — su
    ausencia se muestra en el panel, nunca se oculta ni aborta el índice
    entero por un run incompleto."""
    records = []
    for summary_path in sorted(root.glob("**/run_summary.json")):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        manifest_path = summary_path.parent / "evidence_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
        records.append(
            RunRecord(
                run_dir=summary_path.parent,
                summary_path=summary_path,
                summary=summary,
                manifest_path=manifest_path if manifest_path.exists() else None,
                manifest=manifest,
            )
        )
    return records


def _ac_ids_for(summary: dict) -> list[str]:
    ids: set[str] = set()
    for result in summary.get("results", {}).values():
        ids.update(result.get("metric", {}).get("ac_ids", []))
    return sorted(ids)


def _relative(path: pathlib.Path, panel_dir: pathlib.Path) -> str:
    try:
        return str(path.relative_to(panel_dir)).replace("\\", "/")
    except ValueError:
        # El artefacto vive fuera del árbol del panel (p.ej. --out apuntó
        # a otro sitio): mejor un link roto visible que ocultar el hash.
        return str(path).replace("\\", "/")


def _metric_rows(record: RunRecord) -> str:
    rows = []
    for name, result in sorted(record.summary.get("results", {}).items()):
        metric = result.get("metric", {})
        ac_ids = ", ".join(metric.get("ac_ids", [])) or "—"
        rows.append(
            "<tr>"
            f"<td>{html.escape(ac_ids)}</td>"
            f"<td>{html.escape(name)}</td>"
            f"<td>{html.escape(str(metric.get('value')))}</td>"
            f"<td class=\"gate-{html.escape(result.get('gate', 'FAIL').lower())}\">{html.escape(result.get('gate', '?'))}</td>"
            f"<td>{html.escape(result.get('reason', ''))}</td>"
            f"<td>{'sí' if result.get('critical') else 'no'}</td>"
            f"<td>{html.escape(metric.get('detail', ''))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _run_section(record: RunRecord, panel_dir: pathlib.Path) -> str:
    summary = record.summary
    ac_ids = ", ".join(_ac_ids_for(summary)) or "—"
    summary_href = _relative(record.summary_path, panel_dir)
    if record.manifest is not None and record.manifest_path is not None:
        manifest_href = _relative(record.manifest_path, panel_dir)
        run_hash = html.escape(record.manifest.get("run_summary_sha256", "?"))
        manifest_link = f'<a href="{html.escape(manifest_href)}">evidence_manifest.json</a>'
    else:
        run_hash = "PENDIENTE — evidence_manifest.json no encontrado junto a este run_summary.json"
        manifest_link = "no disponible"

    return f"""
    <section class="run">
      <h2>{html.escape(summary.get('suite', '?'))} — {html.escape(summary.get('run_id', '?'))}</h2>
      <table class="meta">
        <tr><th>Modo</th><td>{html.escape(summary.get('mode', '?'))}</td></tr>
        <tr><th>Generado</th><td>{html.escape(summary.get('generated_at', '?'))}</td></tr>
        <tr><th>AC cubiertos</th><td>{html.escape(ac_ids)}</td></tr>
        <tr><th>Resultado global</th><td class="gate-{html.escape(summary.get('overall', 'fail').lower())}">{html.escape(summary.get('overall', '?'))}</td></tr>
        <tr><th>run_summary sha256</th><td><code>{run_hash}</code></td></tr>
        <tr><th>Artefactos</th><td><a href="{html.escape(summary_href)}">run_summary.json</a> · {manifest_link}</td></tr>
      </table>
      <table class="metrics">
        <thead><tr><th>AC</th><th>Métrica</th><th>Valor</th><th>Decisión</th><th>Razón</th><th>Crítico</th><th>Detalle</th></tr></thead>
        <tbody>
{_metric_rows(record)}
        </tbody>
      </table>
    </section>"""


_CSS = """
body { font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; background: #fff; }
h1 { font-size: 1.4rem; }
section.run { border: 1px solid #ccc; border-radius: 6px; padding: 1rem; margin-bottom: 1.5rem; }
table { border-collapse: collapse; width: 100%; margin-bottom: 0.75rem; }
table.meta th { text-align: left; width: 12rem; color: #555; }
table.metrics th, table.metrics td { border-bottom: 1px solid #eee; padding: 0.3rem 0.5rem; text-align: left; }
td.gate-pass { color: #0a7d24; font-weight: 600; }
td.gate-pass_with_expected_blocks { color: #0a5f7d; font-weight: 600; }
td.gate-fail { color: #b3261e; font-weight: 600; }
code { background: #f5f5f5; padding: 0.1rem 0.3rem; border-radius: 3px; }
"""


def render_html(records: list[RunRecord], *, panel_dir: pathlib.Path, generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.datetime.now(datetime.UTC).isoformat()
    sections = "\n".join(_run_section(r, panel_dir) for r in records) or "<p>No hay runs indexados todavía.</p>"
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>ARGOS — panel operativo de evidencia</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Panel operativo de evidencia (ARG-026)</h1>
<p>Generado {html.escape(generated_at)}. Índice de solo lectura sobre run_summary.json/evidence_manifest.json
ya existentes en disco — la reconstrucción offline del evidence pack no depende de este panel.</p>
{sections}
</body>
</html>
"""


def build_panel(root: pathlib.Path, *, out: pathlib.Path) -> list[RunRecord]:
    records = discover_runs(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(records, panel_dir=out.parent), encoding="utf-8")
    return records


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."), help="Raíz donde buscar run_summary.json (recursivo)")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("reports/evidence_panel.html"))
    args = parser.parse_args(argv)

    records = build_panel(args.root, out=args.out)
    print(f"panel escrito en {args.out} ({len(records)} run(s) indexados)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
