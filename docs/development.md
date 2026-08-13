# Desarrollo en argos-validation

## Requisitos

* Python >= 3.11.
* `argos-contracts-scenarios` clonado como hermano de este repositorio:

```text
argos-ai-xdr/
├── argos-validation/          (este repositorio)
└── argos-contracts-scenarios/
```

Si tu checkout no sigue esa estructura, exporta `ARGOS_CONTRACTS_PATH` apuntando al checkout real:

```bash
export ARGOS_CONTRACTS_PATH=/ruta/a/argos-contracts-scenarios
```

## Comandos

```bash
make bootstrap   # pip install -e ".[dev]" + pre-commit install
make validate    # ruff + mypy + YAML/JSON de este repo
make test        # pytest (incluye tests que leen fixtures de argos-contracts-scenarios)
```

Ejecutar una suite manualmente:

```bash
python -m harness.runner.cli --suite suites/c06/suite.yaml --mode golden --thresholds thresholds/smoke.yaml
```

## Cómo añadir un evaluador

1. Crear `evaluators/<nombre>/__init__.py` con una función pura documentada (qué AC implementa, qué fixtures espera).
2. Añadir su import y su umbral a la suite correspondiente en `suites/`.
3. Añadir un test en `tests/` con un caso que pase y uno que falle el umbral.

## Antes de abrir un PR

1. `make validate` y `make test` sin errores.
2. El PR enlaza una historia `ARG-###`.
3. Si el cambio toca `thresholds/`, incluye la justificación (ver `CONTRIBUTING.md`).
