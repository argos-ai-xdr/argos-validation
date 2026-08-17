"""Manifiesto de evidencia del propio run de validación (5.8).

No es el contrato EvidenceManifest v1 del XDR (ese lo emite argos-core/
evidence-writer para una ejecución del sistema); este manifiesto documenta
la ejecución de argos-validation en sí: qué run_summary produjo, con qué
hash, contra qué inputs. Nunca incluye chain-of-thought (ADR-016).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib


def sha256_of_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_run_manifest(
    *,
    run_id: str,
    run_summary_path: pathlib.Path,
    inputs: list[str],
    classification: str = "internal",
) -> dict:
    return {
        "manifest_version": "argos-validation-run-manifest.v1",
        "run_id": run_id,
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "run_summary_sha256": sha256_of_file(run_summary_path),
        "inputs": inputs,
        "classification": classification,
    }


def write_manifest(manifest: dict, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
