"""Policy-to-Test (prompt maestro de arquitectura objetivo §43; ADR-051,
Fase C): valida traceability/policy-to-test.yaml.

Mismo estándar que harness/traceability.py: no basta con que el YAML esté
bien formado, cada `tests` debe apuntar a una función que EXISTE de
verdad en el archivo citado (no solo a un archivo que existe) — un
`policy-to-test.yaml` con test_ids inventados sería peor que no tenerlo,
daría una falsa sensación de cobertura.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re

import yaml


class PolicyToTestFileNotFound(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _org_root(start: pathlib.Path | None = None) -> pathlib.Path:
    base = start or pathlib.Path(__file__).resolve().parents[1]
    return base.parent


def load_policy_to_test(path: pathlib.Path) -> dict:
    if not path.exists():
        raise PolicyToTestFileNotFound(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _test_exists(test_ref: str, *, org_root: pathlib.Path) -> str | None:
    """Devuelve un mensaje de error, o None si test_ref es válido.

    Formato esperado: "<repo>/<ruta relativa>.py::<nombre de función>".
    """
    if "::" not in test_ref:
        return f"test_ref {test_ref!r} no tiene el formato '<ruta>.py::<función>'"
    file_part, func_name = test_ref.split("::", 1)
    path = org_root / file_part
    if not path.exists():
        return f"test_ref {test_ref!r}: archivo no existe ({path})"
    content = path.read_text(encoding="utf-8")
    if not re.search(rf"^def {re.escape(func_name)}\(", content, re.MULTILINE):
        return f"test_ref {test_ref!r}: no se encontró 'def {func_name}(' en {file_part}"
    return None


def validate(policy_to_test: dict, *, org_root: pathlib.Path | None = None) -> ValidationResult:
    org_root = org_root or _org_root()
    errors: list[str] = []

    rule_groups = policy_to_test.get("rule_groups", [])
    if not rule_groups:
        errors.append("policy-to-test.yaml no declara ningún rule_group")
        return ValidationResult(errors=errors)

    seen_rule_ids: set[str] = set()
    for group in rule_groups:
        group_id = group.get("id", "<sin id>")
        rules = group.get("rules", [])
        if not rules:
            errors.append(f"{group_id}: rule_group sin ninguna regla")
        for rule in rules:
            rule_id = rule.get("id")
            if not rule_id:
                errors.append(f"{group_id}: regla sin id")
                continue
            if rule_id in seen_rule_ids:
                errors.append(f"rule id duplicado entre rule_groups: {rule_id}")
            seen_rule_ids.add(rule_id)

            tests = rule.get("tests", [])
            if not tests:
                errors.append(f"{rule_id}: sin ningún test asociado")
                continue
            for test_ref in tests:
                error = _test_exists(test_ref, org_root=org_root)
                if error:
                    errors.append(f"{rule_id}: {error}")

    return ValidationResult(errors=errors)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[1] / "traceability" / "policy-to-test.yaml",
    )
    args = parser.parse_args(argv)

    data = load_policy_to_test(args.file)
    result = validate(data)

    for error in result.errors:
        print(f"ERROR: {error}")

    if result.ok:
        print("policy-to-test.yaml OK")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
