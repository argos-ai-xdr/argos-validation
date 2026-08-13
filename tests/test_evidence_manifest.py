from __future__ import annotations

from harness.evidence.manifest import build_run_manifest


def test_build_run_manifest_hashes_the_real_file(tmp_path):
    summary_path = tmp_path / "run_summary.json"
    summary_path.write_text('{"a": 1}', encoding="utf-8")

    manifest = build_run_manifest(run_id="r1", run_summary_path=summary_path, inputs=["suites/c06/suite.yaml"])

    assert manifest["run_id"] == "r1"
    assert len(manifest["run_summary_sha256"]) == 64
    assert manifest["inputs"] == ["suites/c06/suite.yaml"]

    # Cambiar el contenido cambia el hash — no es un valor fijo.
    summary_path.write_text('{"a": 2}', encoding="utf-8")
    manifest2 = build_run_manifest(run_id="r1", run_summary_path=summary_path, inputs=[])
    assert manifest2["run_summary_sha256"] != manifest["run_summary_sha256"]
