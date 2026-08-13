"""Orquesta la ejecución de una suite: carga fixtures, valida su schema,
llama a cada evaluador y produce run_summary.json + el manifiesto de run.

Uso:
    python -m harness.runner.cli --suite suites/c06/suite.yaml \
        --thresholds thresholds/smoke.yaml --out /tmp/run_summary.json
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import importlib
import pathlib
import sys

import yaml

from evaluators.base import Metric
from harness.evidence.manifest import build_run_manifest, write_manifest
from harness.loaders.contracts_path import resolve_contracts_path
from harness.loaders.fixture_loader import build_registry, load_fixtures, validate_fixture
from harness.reporters.run_summary import build_run_summary, write_run_summary


@dataclasses.dataclass
class CheckSpec:
    evaluator: str
    contract: str
    category: str
    metric_name: str
    extra: dict


def load_suite(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_thresholds(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("thresholds", {})


def _import_evaluate(dotted: str):
    module = importlib.import_module(dotted)
    if not hasattr(module, "evaluate"):
        raise AttributeError(f"{dotted} no expone una función evaluate(...)")
    return module.evaluate


def run_suite(
    suite_path: pathlib.Path,
    thresholds_path: pathlib.Path,
    contracts_path: pathlib.Path | None = None,
) -> tuple[dict, list[str]]:
    """Devuelve (run_summary, fixture_validation_errors)."""
    suite = load_suite(suite_path)
    thresholds = load_thresholds(thresholds_path)
    contracts_path = contracts_path or resolve_contracts_path()
    registry = build_registry(contracts_path)

    metrics: list[Metric] = []
    fixture_errors: list[str] = []

    for raw_check in suite.get("checks", []):
        check = CheckSpec(
            evaluator=raw_check["evaluator"],
            contract=raw_check["contract"],
            category=raw_check["category"],
            metric_name=raw_check.get("metric_name", raw_check["evaluator"]),
            extra=raw_check.get("extra", {}),
        )
        fixtures = load_fixtures(contracts_path, check.category, check.contract)
        for fixture in fixtures:
            errors = validate_fixture(contracts_path, registry, fixture)
            if errors:
                fixture_errors.append(f"{fixture.path}: {errors}")

        evaluate_fn = _import_evaluate(check.evaluator)
        metric = evaluate_fn([f.data for f in fixtures], contracts_path=contracts_path, **check.extra)
        # Permite que la suite renombre la métrica para que coincida con
        # thresholds/*.yaml sin acoplar el nombre al evaluador.
        metrics.append(dataclasses.replace(metric, name=check.metric_name))

    run_id = f"local-{datetime.datetime.now(datetime.UTC):%Y%m%dT%H%M%SZ}"
    summary = build_run_summary(
        run_id=run_id,
        suite_id=suite.get("id", suite_path.stem),
        mode=suite.get("mode", "golden"),
        metrics=metrics,
        thresholds=thresholds,
    )
    return summary, fixture_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=pathlib.Path)
    parser.add_argument("--thresholds", required=True, type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("run_summary.json"))
    parser.add_argument("--manifest-out", type=pathlib.Path, default=pathlib.Path("evidence_manifest.json"))
    args = parser.parse_args(argv)

    summary, fixture_errors = run_suite(args.suite, args.thresholds)

    if fixture_errors:
        print("FIXTURES INVÁLIDOS (no deberían pasar el schema de argos-contracts-scenarios):")
        for e in fixture_errors:
            print(f"  - {e}")

    write_run_summary(summary, args.out)
    manifest = build_run_manifest(
        run_id=summary["run_id"],
        run_summary_path=args.out,
        inputs=[str(args.suite), str(args.thresholds)],
    )
    write_manifest(manifest, args.manifest_out)

    print(f"suite={summary['suite']} mode={summary['mode']} overall={summary['overall']}")
    for name, result in summary["results"].items():
        print(f"  {name}: {result['gate']} ({result['reason']})")

    if fixture_errors or summary["critical_failures"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
