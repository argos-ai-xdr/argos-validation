"""ARG-023: integración CP00-CP13 y trazabilidad end-to-end (documento
maestro v0.5, §5.4; los 14 checkpoints se mantienen sin cambios hasta
v0.6.25.4).

Valida un directorio de "run" real contra la secuencia de checkpoints
declarada en
argos-contracts-scenarios/scenarios/ARGOS-CYB-01/checkpoints/checkpoints.yaml
(campo `evidence_files`, añadido para este validador): evidencia mínima
presente, validación de schema real donde el checkpoint declara un
contrato v1, y un único run_id coherente encadenado a través de TODOS los
checkpoints que sí llevan contrato — "trazabilidad end-to-end" significa
exactamente eso: no basta con que cada pieza pase su propio test, tienen
que pertenecer de verdad al MISMO run.

Checkpoints sin contrato (CP00, CP01, CP04, CP05, CP12) son artefactos
internos: no hay uno de los 10 contratos v1 cerrados que los cubra (mismo
principio que argos-cyber-tools/graph o argos-core/services/dmz_detector).
Este validador solo comprueba que el archivo existe para esos — nunca
inventa un schema ni un run_id donde no hay contrato del que extraerlo.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib

import yaml

from harness.loaders.fixture_loader import build_registry, validator_for


@dataclasses.dataclass(frozen=True)
class EvidenceFileStatus:
    filename: str
    contract: str | None
    found: bool
    schema_errors: tuple[str, ...]
    run_id: str | None


@dataclasses.dataclass(frozen=True)
class CheckpointStatus:
    cp_id: str
    phase: str
    files: tuple[EvidenceFileStatus, ...]

    @property
    def ok(self) -> bool:
        return all(f.found and not f.schema_errors for f in self.files)


@dataclasses.dataclass(frozen=True)
class CheckpointRunResult:
    statuses: tuple[CheckpointStatus, ...]

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(s.cp_id for s in self.statuses for f in s.files if not f.found)

    @property
    def schema_invalid(self) -> tuple[str, ...]:
        return tuple(s.cp_id for s in self.statuses if any(f.schema_errors for f in s.files))

    @property
    def run_ids_seen(self) -> tuple[str, ...]:
        ids = {f.run_id for s in self.statuses for f in s.files if f.run_id}
        return tuple(sorted(ids))

    @property
    def trace_consistent(self) -> bool:
        """Todos los checkpoints con contrato (y por tanto con run_id
        extraíble) deben compartir el mismo run_id. Más de uno significa
        que el 'run end-to-end' en realidad mezcla ejecuciones distintas
        — justo lo que 'trazabilidad end-to-end' exige detectar, no
        asumir."""
        return len(self.run_ids_seen) <= 1

    @property
    def ok(self) -> bool:
        return not self.missing and not self.schema_invalid and self.trace_consistent


def load_checkpoints(path: pathlib.Path) -> list[dict]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("checkpoints", [])


def _validate_json_file(
    path: pathlib.Path, contract: str | None, *, contracts_path: pathlib.Path, registry
) -> tuple[list[str], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"JSON inválido: {exc}"], None
    run_id = data.get("run_id") if isinstance(data, dict) else None
    if contract is None:
        return [], run_id
    validator = validator_for(contracts_path, registry, contract)
    return [e.message for e in validator.iter_errors(data)], run_id


def _validate_ndjson_file(
    path: pathlib.Path, contract: str, *, contracts_path: pathlib.Path, registry
) -> tuple[list[str], str | None]:
    validator = validator_for(contracts_path, registry, contract)
    errors: list[str] = []
    run_ids: set[str] = set()
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return ["events.ndjson está vacío"], None
    for i, line in enumerate(lines):
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"línea {i}: JSON inválido: {exc}")
            continue
        errors.extend(f"línea {i}: {e.message}" for e in validator.iter_errors(data))
        if isinstance(data, dict) and data.get("run_id"):
            run_ids.add(data["run_id"])
    if len(run_ids) > 1:
        errors.append(f"events.ndjson mezcla run_id distintos dentro del mismo archivo: {sorted(run_ids)}")
    return errors, (next(iter(run_ids)) if len(run_ids) == 1 else None)


def validate_run(run_dir: pathlib.Path, checkpoints: list[dict], *, contracts_path: pathlib.Path) -> CheckpointRunResult:
    registry = build_registry(contracts_path)
    statuses = []
    for cp in checkpoints:
        file_statuses = []
        for ev in cp.get("evidence_files", []):
            filename = ev["filename"]
            contract = ev.get("contract")
            path = run_dir / filename
            if not path.exists():
                file_statuses.append(EvidenceFileStatus(filename=filename, contract=contract, found=False, schema_errors=(), run_id=None))
                continue
            if ev.get("format") == "ndjson":
                errors, run_id = _validate_ndjson_file(path, contract, contracts_path=contracts_path, registry=registry)
            else:
                errors, run_id = _validate_json_file(path, contract, contracts_path=contracts_path, registry=registry)
            file_statuses.append(EvidenceFileStatus(filename=filename, contract=contract, found=True, schema_errors=tuple(errors), run_id=run_id))
        statuses.append(CheckpointStatus(cp_id=cp["id"], phase=cp.get("phase", ""), files=tuple(file_statuses)))
    return CheckpointRunResult(statuses=tuple(statuses))


def main(argv: list[str] | None = None) -> int:
    import argparse

    from harness.loaders.contracts_path import resolve_contracts_path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=pathlib.Path)
    parser.add_argument("--checkpoints", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    contracts_path = resolve_contracts_path()
    checkpoints_path = args.checkpoints or (
        contracts_path / "scenarios" / "ARGOS-CYB-01" / "checkpoints" / "checkpoints.yaml"
    )
    result = validate_run(args.run_dir, load_checkpoints(checkpoints_path), contracts_path=contracts_path)

    for status in result.statuses:
        for f in status.files:
            if not f.found:
                print(f"{status.cp_id} ({status.phase}): FALTA {f.filename}")
            elif f.schema_errors:
                print(f"{status.cp_id}: {f.filename} no valida contra {f.contract}: {list(f.schema_errors)}")
            else:
                print(f"{status.cp_id}: {f.filename} OK" + (f" (run_id={f.run_id})" if f.run_id else ""))

    if not result.trace_consistent:
        print(f"TRAZABILIDAD ROTA: el run mezcla run_id distintos entre checkpoints: {result.run_ids_seen}")

    print(f"overall={'OK' if result.ok else 'FAIL'}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
