# harness/

| Módulo | Rol |
| --- | --- |
| [`loaders/`](loaders/) | Resuelve el checkout de `argos-contracts-scenarios`, construye el registry de schemas y carga/valida fixtures |
| [`runner/cli.py`](runner/cli.py) | Orquesta una suite: carga checks, valida fixtures, invoca evaluadores, aplica thresholds |
| [`reporters/run_summary.py`](reporters/run_summary.py) | Compara `Metric` contra `thresholds/*.yaml` y construye `run_summary.json` |
| [`evidence/manifest.py`](evidence/manifest.py) | Manifiesto del propio run (no el `EvidenceManifest` del XDR) |
| [`traceability.py`](traceability.py) | TRACE-01: valida `../traceability.yaml` (UC/gate → story → contrato → test → métrica → evidencia) contra el estado real de los repos hermanos |
| [`reporters/evidence_panel.py`](reporters/evidence_panel.py) | ARG-026: índice HTML offline por run/CP/AC sobre los `run_summary.json`/`evidence_manifest.json` ya escritos — sin JS ni analítica, la reconstrucción del evidence pack no depende de este panel |
| [`checkpoints.py`](checkpoints.py) | ARG-023: valida un directorio de run contra `argos-contracts-scenarios/scenarios/ARGOS-CYB-01/checkpoints/checkpoints.yaml` — evidencia CP00-CP13 presente, schema real donde hay contrato v1, y un único `run_id` coherente en todos los checkpoints (trazabilidad end-to-end) |
| [`reproducibility.py`](reproducibility.py) | AC01: corre la misma suite dos veces sobre el mismo checkout y compara `value`/`gate`/`sample_size` métrica por métrica (ignora `generated_at`, que se espera que difiera) |
| [`acceptance.py`](acceptance.py) | ARG-027: acceptance runner AC01-AC14 — corre todas las suites contra `thresholds/acceptance.yaml`, agrega por AC (peor gate entre suites), exige cobertura de los 14 y sella el reporte con sha256 |

Ejecución: `python -m harness.runner.cli --suite suites/c06/suite.yaml --thresholds thresholds/smoke.yaml`.

Añadir `--check-trace` bloquea el run si `traceability.yaml` no valida o si algún
gate con story(s) P0 está en `status=BLOCKED` — "la release candidata se
bloquea si traceability.yaml no valida" (propuesta v0.6.25.4, §4.6.1). También
se puede validar de forma independiente: `python -m harness.traceability`.

Panel de evidencia: `python -m harness.reporters.evidence_panel --root <dir con
runs> --out reports/evidence_panel.html` escanea recursivamente `run_summary.json`
y sus `evidence_manifest.json` hermanos y genera un índice HTML estático
(sin servidor, sin JS) por run/CP/AC con estado, métricas, decisiones, hashes
y enlaces a los artefactos.

Checkpoints CP00-CP13: `python -m harness.checkpoints --run-dir <dir con la
evidencia de un run>` (ver también
`../argos-contracts-scenarios/scenarios/ARGOS-CYB-01/expected/sample-run/`
para un ejemplo real ensamblado desde `fixtures/smoke/`).

Acceptance runner (ARG-027): `python -m harness.acceptance --out-dir
acceptance_out` corre las 7 suites registradas contra `thresholds/acceptance.yaml`,
escribe `acceptance_report.json` (por AC01-AC14) + `acceptance_seal.json`
(sha256 sobre el contenido — detecta manipulación posterior, no es una
firma criptográfica con clave real, no existe PKI todavía) y sale con
código 1 si algún AC queda sin cobertura o el resultado global no es
PASS/PASS_WITH_EXPECTED_BLOCKS.
