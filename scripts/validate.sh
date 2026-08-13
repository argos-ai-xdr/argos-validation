#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import json
import pathlib
import sys

import yaml

root = pathlib.Path(".")
errors = []

for path in root.rglob("*.y*ml"):
    if "/.git/" in str(path):
        continue
    try:
        list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except yaml.YAMLError as exc:
        errors.append(f"{path}: YAML inválido: {exc}")

for path in root.rglob("*.json"):
    if "/.git/" in str(path):
        continue
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: JSON inválido: {exc}")

required = {"name", "domain", "criticality", "owner", "backup_owner", "classification", "lifecycle"}
repo_yaml = root / "repository.yaml"
if not repo_yaml.exists():
    errors.append("repository.yaml no existe")
else:
    data = yaml.safe_load(repo_yaml.read_text(encoding="utf-8")) or {}
    missing = required - data.keys()
    if missing:
        errors.append(f"repository.yaml: faltan claves {sorted(missing)}")

if errors:
    print("VALIDACIÓN FALLIDA:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("validate (YAML/JSON/repository.yaml) OK")
PY

if command -v ruff >/dev/null 2>&1; then
  ruff check .
else
  echo "aviso: ruff no instalado, se omite lint de Python" >&2
fi
