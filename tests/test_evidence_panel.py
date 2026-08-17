from __future__ import annotations

import json
import pathlib

from evaluators.base import Metric
from harness.evidence.manifest import build_run_manifest, sha256_of_file, write_manifest
from harness.reporters.evidence_panel import build_panel, discover_runs, render_html
from harness.reporters.run_summary import build_run_summary


def _write_run(run_dir: pathlib.Path, *, run_id: str, suite_id: str, with_manifest: bool = True) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics = [Metric(name="detection_f1", value=0.9, detail="9/10", ac_ids=("AC06",), sample_size=10)]
    summary = build_run_summary(
        run_id=run_id,
        suite_id=suite_id,
        mode="golden",
        metrics=metrics,
        thresholds={"detection_f1": {"min": 0.85, "critical": False}},
    )
    summary_path = run_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    if with_manifest:
        manifest = build_run_manifest(run_id=run_id, run_summary_path=summary_path, inputs=["x"])
        write_manifest(manifest, run_dir / "evidence_manifest.json")


def test_discover_runs_finds_every_run_summary_recursively(tmp_path):
    _write_run(tmp_path / "c06", run_id="run-1", suite_id="c06")
    _write_run(tmp_path / "c07", run_id="run-2", suite_id="c07")

    records = discover_runs(tmp_path)

    assert {r.summary["run_id"] for r in records} == {"run-1", "run-2"}


def test_discover_runs_tolerates_a_missing_manifest(tmp_path):
    """Un run incompleto (sin evidence_manifest.json todavía) no debe
    tumbar el índice entero — se muestra como incompleto, no se oculta."""
    _write_run(tmp_path / "c06", run_id="run-1", suite_id="c06", with_manifest=False)

    records = discover_runs(tmp_path)

    assert len(records) == 1
    assert records[0].manifest is None


def test_panel_hash_matches_the_real_file_on_disk(tmp_path):
    """El hash mostrado en el panel debe ser el hash REAL del
    run_summary.json que hay en disco, no un valor derivado o
    recalculado de otra forma — si alguien edita el fichero a mano, el
    hash del manifest (fijado en el momento del run) debe seguir siendo
    el que corresponde al contenido ORIGINAL, y el panel debe mostrarlo
    tal cual, sin recalcular."""
    _write_run(tmp_path / "c06", run_id="run-1", suite_id="c06")
    records = discover_runs(tmp_path)
    real_hash = sha256_of_file(tmp_path / "c06" / "run_summary.json")

    assert records[0].manifest["run_summary_sha256"] == real_hash


def test_render_html_links_are_relative_and_resolve_from_the_panel_location(tmp_path):
    _write_run(tmp_path / "c06", run_id="run-1", suite_id="c06")
    records = discover_runs(tmp_path)

    out_dir = tmp_path  # panel escrito en la raíz que se escaneó
    page = render_html(records, panel_dir=out_dir)

    assert 'href="c06/run_summary.json"' in page
    assert 'href="c06/evidence_manifest.json"' in page
    assert (out_dir / "c06" / "run_summary.json").exists()


def test_render_html_shows_ac_ids_and_gate_decision(tmp_path):
    _write_run(tmp_path / "c06", run_id="run-1", suite_id="c06")
    records = discover_runs(tmp_path)

    page = render_html(records, panel_dir=tmp_path)

    assert "AC06" in page
    assert "detection_f1" in page
    assert "gate-pass" in page


def test_render_html_escapes_untrusted_metric_text():
    """detail/reason de una Metric vienen de datos de fixture, no de
    código de confianza — no deben poder inyectar HTML/JS en el panel."""
    metrics = [Metric(name="x", value=1.0, detail="<script>alert(1)</script>", ac_ids=(), sample_size=1)]
    summary = build_run_summary(run_id="r", suite_id="s", mode="golden", metrics=metrics, thresholds={"x": {"min": 0.0, "critical": False}})
    from harness.reporters.evidence_panel import RunRecord

    record = RunRecord(
        run_dir=pathlib.Path("."),
        summary_path=pathlib.Path("run_summary.json"),
        summary=summary,
        manifest_path=None,
        manifest=None,
    )
    page = render_html([record], panel_dir=pathlib.Path("."))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_no_runs_produces_a_valid_empty_panel_not_a_crash(tmp_path):
    page = render_html([], panel_dir=tmp_path)
    assert "No hay runs indexados" in page


def test_build_panel_writes_the_file_and_returns_the_indexed_records(tmp_path):
    _write_run(tmp_path / "runs" / "c06", run_id="run-1", suite_id="c06")
    out = tmp_path / "reports" / "evidence_panel.html"

    records = build_panel(tmp_path / "runs", out=out)

    assert out.exists()
    assert len(records) == 1
    # El link se calcula contra el DIRECTORIO DEL PANEL (reports/), no
    # contra la raíz escaneada (runs/) — como son directorios hermanos,
    # no existe una ruta relativa corta y debe caer al path completo en
    # vez de fingir uno relativo roto (href="c06/run_summary.json").
    assert 'href="c06/run_summary.json"' not in out.read_text(encoding="utf-8")
