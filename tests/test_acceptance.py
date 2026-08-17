from __future__ import annotations

import json
import pathlib

from harness.acceptance import (
    ALL_AC_IDS,
    main,
    run_acceptance,
    seal_report,
    write_acceptance_report,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_real_acceptance_run_covers_all_fourteen_ac_ids(contracts_path):
    """La comprobación que ARG-027 existe para forzar: correr TODAS las
    suites registradas no debe dejar ningún AC01-AC14 sin ninguna métrica
    que lo evalúe. Así se descubrieron AC01/AC02/AC10/AC12 — este test es
    la barrera para que ese tipo de gap no vuelva a colarse en silencio."""
    report = run_acceptance(suites_root=ROOT / "suites", thresholds_path=ROOT / "thresholds" / "acceptance.yaml", contracts_path=contracts_path)

    assert report.missing_ac_ids == ()
    assert set(report.ac_results) == set(ALL_AC_IDS)


def test_real_acceptance_run_reports_the_known_current_state(contracts_path):
    """Estado real conocido hoy: AC03/AC08 (ungrounded_cve_rate) fallan
    contra el umbral de acceptance porque solo hay datos smoke, no
    acceptance-tier calibrados — el runner debe reportarlo tal cual, no
    suavizarlo. AC05/AC11 son PASS_WITH_EXPECTED_BLOCKS (bloqueo
    adversarial correcto), no un PASS liso."""
    report = run_acceptance(suites_root=ROOT / "suites", thresholds_path=ROOT / "thresholds" / "acceptance.yaml", contracts_path=contracts_path)

    assert report.ac_results["AC03"].gate == "FAIL"
    assert report.ac_results["AC08"].gate == "FAIL"
    assert report.ac_results["AC05"].gate == "PASS_WITH_EXPECTED_BLOCKS"
    assert report.overall == "FAIL"
    assert not report.ok


def test_missing_ac_coverage_forces_overall_fail(contracts_path):
    """Si se corre solo un subconjunto de suites que no toca, por
    ejemplo, AC10/AC12 (approval_gate/rollback viven en integration),
    el report debe declarar esos AC sin cobertura y fallar globalmente
    — nunca callar el hueco."""
    report = run_acceptance(
        suites_root=ROOT / "suites",
        thresholds_path=ROOT / "thresholds" / "acceptance.yaml",
        contracts_path=contracts_path,
        suite_ids=("c06",),
    )

    assert "AC10" in report.missing_ac_ids
    assert "AC12" in report.missing_ac_ids
    assert report.overall == "FAIL"
    assert not report.ok


def test_a_real_reproducibility_violation_fails_ac01_within_the_acceptance_run(monkeypatch, contracts_path):
    """Integración end-to-end de AC01 dentro del acceptance runner (no
    solo evaluate_reproducibility en aislamiento, ver test_reproducibility.py):
    si una suite deja de ser determinista, el report debe marcar AC01
    como FAIL y arrastrar overall a FAIL, no quedarse solo en el nivel de
    harness.reproducibility sin propagarse."""
    from evaluators.base import Metric

    def fake_evaluate_reproducibility(suite_path, thresholds_path, *, contracts_path=None):
        return Metric(name="reproducibility_violation", value=1.0, detail="no determinista (simulado)", ac_ids=("AC01",), sample_size=1)

    monkeypatch.setattr("harness.acceptance.evaluate_reproducibility", fake_evaluate_reproducibility)

    report = run_acceptance(
        suites_root=ROOT / "suites",
        thresholds_path=ROOT / "thresholds" / "acceptance.yaml",
        contracts_path=contracts_path,
        suite_ids=("c06",),
    )

    assert report.ac_results["AC01"].gate == "FAIL"
    assert report.ac_results["AC01"].critical is True
    assert report.overall == "FAIL"


def test_seal_changes_if_report_content_changes():
    report_a = {"overall": "PASS", "ac_results": {}}
    report_b = {"overall": "FAIL", "ac_results": {}}

    seal_a = seal_report(report_a)
    seal_b = seal_report(report_b)

    assert seal_a["report_sha256"] != seal_b["report_sha256"]


def test_seal_is_deterministic_for_the_same_content_regardless_of_key_order():
    report_a = {"overall": "PASS", "run_id": "r1"}
    report_b = {"run_id": "r1", "overall": "PASS"}

    assert seal_report(report_a)["report_sha256"] == seal_report(report_b)["report_sha256"]


def test_seal_is_not_a_cryptographic_signature_and_says_so():
    """No debe afirmar una garantía que no existe todavía (sin PKI real)."""
    seal = seal_report({"x": 1})
    assert "no firma criptográfica" in seal["note"] or "no firma criptografica" in seal["note"]


def test_write_acceptance_report_produces_two_real_files_on_disk(contracts_path, tmp_path):
    report = run_acceptance(
        suites_root=ROOT / "suites",
        thresholds_path=ROOT / "thresholds" / "acceptance.yaml",
        contracts_path=contracts_path,
        suite_ids=("c07",),
    )
    report_path, seal_path = write_acceptance_report(report, tmp_path)

    assert report_path.exists()
    assert seal_path.exists()

    written = json.loads(report_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    assert seal["report_sha256"] == seal_report(written)["report_sha256"]


def test_main_cli_runs_end_to_end_and_writes_real_files(contracts_path, tmp_path, capsys):
    """El wrapper main() (argparse, escritura de ficheros, prints por AC,
    código de salida) no tenía ningún test directo — solo run_acceptance()
    estaba probado. Corre contra las suites reales por defecto (mismo
    estado conocido: 14/14 AC cubiertos, overall=FAIL por AC03/AC08)."""
    out_dir = tmp_path / "acceptance_out"
    exit_code = main(["--out-dir", str(out_dir)])

    assert exit_code == 1  # overall=FAIL conocido (AC03/AC08 contra umbral de aceptación)
    assert (out_dir / "acceptance_report.json").exists()
    assert (out_dir / "acceptance_seal.json").exists()

    out = capsys.readouterr().out
    assert "AC01:" in out and "SIN COBERTURA" not in out
    assert "overall=FAIL" in out
