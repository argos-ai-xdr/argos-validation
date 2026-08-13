# tests

Pruebas de este propio harness (no del XDR), 41 casos. Requieren `argos-contracts-scenarios` como hermano o `ARGOS_CONTRACTS_PATH` (ver `../docs/development.md`) — los tests que lo necesitan se saltan automáticamente (`pytest.skip`) si no lo encuentran, no fallan en falso.

| Archivo | Cubre |
| --- | --- |
| `test_fixture_loader.py` | Carga y validación de fixtures, incluida la ruta manifest-driven de `adversarial`/`negative` |
| `test_evaluators.py` | Los 8 evaluadores, con casos sintéticos que pasan y que fallan |
| `test_run_summary.py` | Lógica de gates: PASS/FAIL/PASS_WITH_EXPECTED_BLOCKS, críticos vs. avisos |
| `test_cli_suites.py` | Integración: cada suite real de `../suites/` corre de punta a punta |
| `test_report_schema.py` | `run_summary.json` real valida contra `../reports/schemas/run_summary.schema.json`; el renderer Markdown no crashea |
| `test_evidence_manifest.py` | El manifiesto de evidencia del run hashea el contenido real, no un valor fijo |

Ejecutar: `make test` o `pytest`.
