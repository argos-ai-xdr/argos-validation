# adversarial

Entradas maliciosas y controles esperados. Es el modo declarado por `suites/adversarial/suite.yaml`, que consume `argos-contracts-scenarios/fixtures/adversarial/` (F09). A diferencia de `golden`, un resultado "malo" aquí (bloqueo exitoso) es el resultado correcto — ver `evaluators/policy/` y la regla `PASS_WITH_EXPECTED_BLOCKS` en `harness/reporters/run_summary.py`.
