"""ReplayCapsule (prompt maestro de arquitectura objetivo §42; ADR-051,
Fase C).

Empaqueta un run_dir ya capturado (p.ej. el sample-run real de
ARGOS-CYB-01) en un manifiesto autocontenido con SHA-256 por archivo, para
poder re-validarlo más tarde de forma determinista sin depender del
estado mutable del directorio original.

Esto es reproducción determinista de un run YA CAPTURADO — reutiliza
harness.checkpoints.validate_run (mismo chequeo de schema/run_id que ya
existía) y añade verificación de integridad de contenido (hash) encima.
No es re-ejecución del pipeline real contra un cluster: eso sería un
Digital Twin, que no existe (ver architecture/v0.6.25-gap-matrix.md §1).
Un ReplayCapsule no regenera evidencia — solo demuestra que la evidencia
ya escrita sigue siendo exactamente la misma, y sigue pasando las mismas
validaciones de schema/trazabilidad.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import pathlib

from harness.checkpoints import CheckpointRunResult, load_checkpoints, validate_run


@dataclasses.dataclass(frozen=True)
class CapsuleFile:
    filename: str
    sha256: str


@dataclasses.dataclass(frozen=True)
class ReplayCapsuleManifest:
    capsule_id: str
    source_run_dir: str
    created_at: str
    checkpoints_source: str
    files: tuple[CapsuleFile, ...]

    def to_dict(self) -> dict:
        return {
            "manifest_version": "argos-validation-replay-capsule.v1",
            "capsule_id": self.capsule_id,
            "source_run_dir": self.source_run_dir,
            "created_at": self.created_at,
            "checkpoints_source": self.checkpoints_source,
            "files": [dataclasses.asdict(f) for f in self.files],
        }


def _sha256_of_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_capsule(run_dir: pathlib.Path, checkpoints_path: pathlib.Path, *, capsule_id: str) -> ReplayCapsuleManifest:
    """Solo incluye archivos que existen de verdad en run_dir. Un archivo de
    checkpoint declarado pero ausente (p.ej. CP00/CP01/CP12 en el
    sample-run real hoy) no se inventa: simplemente no entra en la
    cápsula, y replay() seguirá reportándolo como ausente vía
    checkpoints.validate_run — la cápsula nunca oculta un hueco real."""
    checkpoints = load_checkpoints(checkpoints_path)
    files: list[CapsuleFile] = []
    seen: set[str] = set()
    for cp in checkpoints:
        for ev in cp.get("evidence_files", []):
            filename = ev["filename"]
            if filename in seen:
                continue
            seen.add(filename)
            path = run_dir / filename
            if path.exists():
                files.append(CapsuleFile(filename=filename, sha256=_sha256_of_file(path)))
    return ReplayCapsuleManifest(
        capsule_id=capsule_id,
        source_run_dir=str(run_dir),
        created_at=datetime.datetime.now(datetime.UTC).isoformat(),
        checkpoints_source=str(checkpoints_path),
        files=tuple(files),
    )


def write_capsule(manifest: ReplayCapsuleManifest, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_capsule(path: pathlib.Path) -> ReplayCapsuleManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReplayCapsuleManifest(
        capsule_id=data["capsule_id"],
        source_run_dir=data["source_run_dir"],
        created_at=data["created_at"],
        checkpoints_source=data["checkpoints_source"],
        files=tuple(CapsuleFile(**f) for f in data["files"]),
    )


@dataclasses.dataclass(frozen=True)
class ReplayResult:
    checkpoint_result: CheckpointRunResult
    integrity_violations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.checkpoint_result.ok and not self.integrity_violations


def replay(
    manifest: ReplayCapsuleManifest,
    run_dir: pathlib.Path,
    checkpoints_path: pathlib.Path,
    *,
    contracts_path: pathlib.Path,
) -> ReplayResult:
    """Re-valida run_dir contra los checkpoints (mismo chequeo que
    checkpoints.validate_run) Y verifica que cada archivo listado en el
    manifiesto no cambió desde que se construyó la cápsula — detecta
    manipulación de contenido, no solo huecos o errores de schema."""
    checkpoints = load_checkpoints(checkpoints_path)
    checkpoint_result = validate_run(run_dir, checkpoints, contracts_path=contracts_path)

    integrity_violations: list[str] = []
    for f in manifest.files:
        path = run_dir / f.filename
        if not path.exists():
            integrity_violations.append(f"{f.filename}: presente en la cápsula pero ausente en run_dir")
            continue
        actual = _sha256_of_file(path)
        if actual != f.sha256:
            integrity_violations.append(
                f"{f.filename}: hash no coincide (cápsula={f.sha256[:12]}..., actual={actual[:12]}...)"
            )

    return ReplayResult(checkpoint_result=checkpoint_result, integrity_violations=tuple(integrity_violations))


def main(argv: list[str] | None = None) -> int:
    import argparse

    from harness.loaders.contracts_path import resolve_contracts_path

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="Construir una cápsula a partir de un run_dir real.")
    build_p.add_argument("--run-dir", required=True, type=pathlib.Path)
    build_p.add_argument("--checkpoints", type=pathlib.Path, default=None)
    build_p.add_argument("--capsule-id", required=True)
    build_p.add_argument("--out", required=True, type=pathlib.Path)

    replay_p = sub.add_parser("replay", help="Re-validar un run_dir contra una cápsula existente.")
    replay_p.add_argument("--capsule", required=True, type=pathlib.Path)
    replay_p.add_argument("--run-dir", required=True, type=pathlib.Path)
    replay_p.add_argument("--checkpoints", type=pathlib.Path, default=None)

    args = parser.parse_args(argv)
    contracts_path = resolve_contracts_path()
    default_checkpoints = contracts_path / "scenarios" / "ARGOS-CYB-01" / "checkpoints" / "checkpoints.yaml"

    if args.command == "build":
        checkpoints_path = args.checkpoints or default_checkpoints
        manifest = build_capsule(args.run_dir, checkpoints_path, capsule_id=args.capsule_id)
        write_capsule(manifest, args.out)
        print(f"cápsula {manifest.capsule_id!r} escrita en {args.out} ({len(manifest.files)} archivos)")
        return 0

    checkpoints_path = args.checkpoints or default_checkpoints
    manifest = load_capsule(args.capsule)
    result = replay(manifest, args.run_dir, checkpoints_path, contracts_path=contracts_path)
    for status in result.checkpoint_result.statuses:
        for f in status.files:
            if not f.found:
                print(f"{status.cp_id} ({status.phase}): FALTA {f.filename}")
            elif f.schema_errors:
                print(f"{status.cp_id}: {f.filename} no valida contra {f.contract}: {list(f.schema_errors)}")
    for violation in result.integrity_violations:
        print(f"INTEGRIDAD: {violation}")
    print(f"replay overall={'OK' if result.ok else 'FAIL'}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
