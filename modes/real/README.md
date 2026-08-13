# real

Integraciones disponibles: el harness consulta un despliegue real de `argos-core`/`argos-cyber-tools` (vía las APIs de `argos-contracts-scenarios/openapi/`) en vez de leer fixtures estáticos. Requiere `argos-platform` desplegado (`laboratory` u `osc`) y credenciales de solo lectura (`SECURITY.md`). No implementado todavía — depende de que esos servicios existan (ARG-007 en adelante).

Cuando exista, un check de suite en modo `real` deberá poder declarar de dónde lee (`base_url`) en vez de `(category, contract)`, sin cambiar la interfaz de los evaluadores (`evaluate(fixtures, ...)`): el "cargador" en modo real produce la misma lista de dicts que hoy produce `harness.loaders.fixture_loader` a partir de fixtures.
