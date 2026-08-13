# Política de seguridad — argos-validation

Ver la política transversal en `argos-control/SECURITY.md`. Específico de este repositorio:

* En modo `real`, este harness puede consultar servicios desplegados de `argos-core`/`argos-cyber-tools`: usa credenciales de solo lectura, nunca las de un aprobador ni las de un ejecutor (segregación de funciones, `argos-control/governance/policies/segregation-of-duties.md`). El harness nunca aprueba ni ejecuta una acción, solo la observa.
* `run_summary.json` y el evidence writer de este repositorio no almacenan chain-of-thought del modelo evaluado (ADR-016) — solo entradas, salidas estructuradas y el veredicto del evaluador.
* `suites/adversarial/` reutiliza los fixtures de `argos-contracts-scenarios/fixtures/adversarial/` (F09): no son exploits reales, ejercitan que el sistema bloquea la solicitud.

## Reporte

Reportar vulnerabilidades o hallazgos vía el issue template `risk.yaml` o `exception.yaml` de `argos-control`, notificando al rol `qa-security-observer`.
