# reports/

| Carpeta | Contenido |
| --- | --- |
| [`schemas/run_summary.schema.json`](schemas/run_summary.schema.json) | Estructura real que produce `harness.reporters.run_summary.build_run_summary` |
| [`templates/run_summary.md.template`](templates/run_summary.md.template) | Plantilla Markdown (`string.Template`) renderizada por `harness.reporters.markdown_report.render` |

`run_summary.json` en sí (el artefacto de cada ejecución) no se versiona aquí — es la salida de `harness/runner/cli.py`, no una plantilla.
