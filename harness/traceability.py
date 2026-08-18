"""TRACE-01 (propuesta v0.6.25.4, §4.6.1): valida traceability.yaml.

Comprueba SOLO lo que se puede verificar mecánicamente sin ejecutar los
otros 6 repos hermanos:

  - uc_id/gate_id sin duplicados.
  - story_ids referencian IDs reales de
    argos-control/project/backlog/backlog.yaml (localizado vía
    ARGOS_CONTROL_PATH o como hermano, ver harness/loaders/control_path.py;
    si no está disponible, ese check se marca SKIPPED explícitamente en
    vez de fingir que pasó).
  - contract_ids referencian contratos reales (schemas/*/v1.schema.json de
    argos-contracts-scenarios) o están vacíos.
  - test_ids apuntan a una ruta "<repo>/<path relativo>" que EXISTE de
    verdad bajo la raíz de la organización — no solo bien formada.
  - Cero huérfanos: todo ARG-xxx P0 del backlog aparece en algún
    entry.story_ids.
  - Regla dura de gates.md: un entry que contiene alguna story P0 y tiene
    status=BLOCKED bloquea la release candidate (TRACE-01: "UC P0 sin
    cadena completa = BLOCKED").

No verifica que cada test_id colecte con pytest en cada repo — eso
requeriría un entorno con las dependencias de los 7 repos instaladas a la
vez y es responsabilidad del CI de cada uno; este validador comprueba
existencia de archivo/carpeta, no ejecución real de la suite.
"""
from __future__ import annotations

import dataclasses
import pathlib

import yaml

from harness.loaders.control_path import resolve_control_path

_KNOWN_STATUSES = frozenset({"PASS", "PARTIAL", "BLOCKED"})


class TraceabilityFileNotFound(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    errors: list[str]
    warnings: list[str]
    p0_blocked_gates: list[str]

    @property
    def ok(self) -> bool:
        """False si hay cualquier error estructural o un gate P0 bloqueado.

        Los warnings (p.ej. backlog.yaml no disponible para cruzar
        referencias) no impiden un run local sin los repos hermanos
        clonados, pero sí deben mostrarse.
        """
        return not self.errors and not self.p0_blocked_gates


def _org_root(start: pathlib.Path | None = None) -> pathlib.Path:
    """Raíz que contiene los 7 repos hermanos (padre de este checkout)."""
    base = start or pathlib.Path(__file__).resolve().parents[1]
    return base.parent


def load_traceability(path: pathlib.Path) -> dict:
    if not path.exists():
        raise TraceabilityFileNotFound(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_backlog(org_root: pathlib.Path) -> list[dict] | None:
    control_path = resolve_control_path(fallback=org_root / "argos-control")
    if control_path is None:
        return None
    backlog_path = control_path / "project" / "backlog" / "backlog.yaml"
    if not backlog_path.exists():
        return None
    data = yaml.safe_load(backlog_path.read_text(encoding="utf-8")) or {}
    return data.get("items", [])


def _load_contract_ids(org_root: pathlib.Path) -> set[str] | None:
    schemas_dir = org_root / "argos-contracts-scenarios" / "schemas"
    if not schemas_dir.exists():
        return None
    return {f"{d.name}.v1" for d in schemas_dir.iterdir() if d.is_dir()}


def validate(traceability: dict, *, org_root: pathlib.Path | None = None) -> ValidationResult:
    org_root = org_root or _org_root()
    errors: list[str] = []
    warnings: list[str] = []
    p0_blocked_gates: list[str] = []

    entries = traceability.get("entries", [])
    if not entries:
        errors.append("traceability.yaml no declara ningún entry")
        return ValidationResult(errors=errors, warnings=warnings, p0_blocked_gates=p0_blocked_gates)

    backlog_items = _load_backlog(org_root)
    if backlog_items is None:
        warnings.append(
            "argos-control no está disponible como hermano: no se pudo cruzar "
            "story_ids contra project/backlog/backlog.yaml ni comprobar huérfanos P0"
        )
        backlog_by_id: dict[str, dict] = {}
    else:
        backlog_by_id = {item["id"]: item for item in backlog_items}

    known_contract_ids = _load_contract_ids(org_root)
    if known_contract_ids is None:
        warnings.append(
            "argos-contracts-scenarios no está disponible como hermano: no se "
            "pudo validar contract_ids contra los schemas reales"
        )

    seen_uc_ids: set[str] = set()
    seen_gate_ids: set[str] = set()
    referenced_story_ids: set[str] = set()

    for entry in entries:
        uc_id = entry.get("uc_id")
        gate_id = entry.get("gate_id")
        label = uc_id or "<sin uc_id>"

        if not uc_id:
            errors.append("entry sin uc_id")
        elif uc_id in seen_uc_ids:
            errors.append(f"uc_id duplicado: {uc_id}")
        else:
            seen_uc_ids.add(uc_id)

        if gate_id:
            if gate_id in seen_gate_ids:
                errors.append(f"gate_id duplicado: {gate_id}")
            seen_gate_ids.add(gate_id)

        status = entry.get("status")
        if status not in _KNOWN_STATUSES:
            errors.append(f"{label}: status {status!r} inválido, debe ser uno de {sorted(_KNOWN_STATUSES)}")

        story_ids = entry.get("story_ids", [])
        entry_has_p0 = False
        for story_id in story_ids:
            referenced_story_ids.add(story_id)
            if backlog_by_id:
                item = backlog_by_id.get(story_id)
                if item is None:
                    errors.append(f"{label}: story_id {story_id!r} no existe en backlog.yaml")
                elif item.get("priority") == "P0":
                    entry_has_p0 = True
            # Sin backlog disponible no podemos saber la prioridad real:
            # no se asume P0 ni P1 en silencio, se deja fuera del check duro.

        if entry_has_p0 and status == "BLOCKED":
            p0_blocked_gates.append(f"{label} ({gate_id}): contiene story(s) P0 y status=BLOCKED")

        for contract_id in entry.get("contract_ids", []):
            if known_contract_ids is not None and contract_id not in known_contract_ids:
                errors.append(f"{label}: contract_id {contract_id!r} no corresponde a ningún schema real")

        for test_id in entry.get("test_ids", []):
            candidate = org_root / test_id
            if not candidate.exists():
                errors.append(f"{label}: test_id {test_id!r} no existe en disco ({candidate})")

    if backlog_by_id:
        p0_ids = {item["id"] for item in backlog_by_id.values() if item.get("priority") == "P0"}
        orphan_p0 = sorted(p0_ids - referenced_story_ids)
        if orphan_p0:
            errors.append(f"story_ids P0 huérfanas (sin ningún entry en traceability.yaml): {orphan_p0}")

    return ValidationResult(errors=errors, warnings=warnings, p0_blocked_gates=p0_blocked_gates)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1] / "traceability.yaml")
    args = parser.parse_args(argv)

    traceability = load_traceability(args.file)
    result = validate(traceability)

    for warning in result.warnings:
        print(f"AVISO: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}")
    for blocked in result.p0_blocked_gates:
        print(f"P0 BLOCKED: {blocked}")

    if result.ok:
        print("traceability.yaml OK")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
