from __future__ import annotations

import pathlib

import pytest
import yaml

from harness.traceability import load_traceability, validate

pytestmark = pytest.mark.filterwarnings("ignore")


def _write_backlog(org_root: pathlib.Path, items: list[dict]) -> None:
    backlog_dir = org_root / "argos-control" / "project" / "backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    (backlog_dir / "backlog.yaml").write_text(yaml.safe_dump({"items": items}), encoding="utf-8")


def _write_contracts(org_root: pathlib.Path, contract_names: list[str]) -> None:
    schemas_dir = org_root / "argos-contracts-scenarios" / "schemas"
    for name in contract_names:
        (schemas_dir / name).mkdir(parents=True, exist_ok=True)


def _write_test_file(org_root: pathlib.Path, relative_path: str) -> None:
    path = org_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# fixture\n", encoding="utf-8")


@pytest.fixture
def org_root(tmp_path: pathlib.Path) -> pathlib.Path:
    _write_backlog(
        tmp_path,
        [
            {"id": "ARG-001", "priority": "P0"},
            {"id": "ARG-002", "priority": "P1"},
        ],
    )
    _write_contracts(tmp_path, ["asset-snapshot"])
    _write_test_file(tmp_path, "argos-core/tests/unit/test_thing.py")
    return tmp_path


def _base_entry(**overrides: object) -> dict:
    entry: dict[str, object] = {
        "uc_id": "G2",
        "gate_id": "G2",
        "story_ids": ["ARG-001"],
        "contract_ids": ["asset-snapshot.v1"],
        "test_ids": ["argos-core/tests/unit/test_thing.py"],
        "metric_ids": [],
        "status": "PASS",
    }
    entry.update(overrides)
    return entry


def test_well_formed_entry_validates_clean(org_root):
    traceability = {"entries": [_base_entry()]}
    result = validate(traceability, org_root=org_root)
    assert result.errors == []
    assert result.warnings == []
    assert result.p0_blocked_gates == []
    assert result.ok


def test_unknown_story_id_is_an_error(org_root):
    traceability = {"entries": [_base_entry(story_ids=["ARG-999"])]}
    result = validate(traceability, org_root=org_root)
    assert any("ARG-999" in e for e in result.errors)
    assert not result.ok


def test_unknown_contract_id_is_an_error(org_root):
    traceability = {"entries": [_base_entry(contract_ids=["not-a-real-contract.v1"])]}
    result = validate(traceability, org_root=org_root)
    assert any("not-a-real-contract.v1" in e for e in result.errors)


def test_missing_test_file_is_an_error(org_root):
    traceability = {"entries": [_base_entry(test_ids=["argos-core/tests/unit/nope.py"])]}
    result = validate(traceability, org_root=org_root)
    assert any("nope.py" in e for e in result.errors)


def test_duplicate_uc_id_is_an_error(org_root):
    traceability = {"entries": [_base_entry(), _base_entry(gate_id="G2b")]}
    result = validate(traceability, org_root=org_root)
    assert any("duplicado" in e for e in result.errors)


def test_p0_story_with_blocked_status_blocks_the_release_candidate(org_root):
    """Regla dura de TRACE-01: 'UC P0 sin cadena completa = BLOCKED' debe
    bloquear la release candidate, no quedar como un warning ignorable."""
    traceability = {"entries": [_base_entry(status="BLOCKED")]}
    result = validate(traceability, org_root=org_root)
    assert result.errors == []  # estructuralmente válido
    assert len(result.p0_blocked_gates) == 1
    assert not result.ok  # pero bloquea igual


def test_p1_only_story_with_blocked_status_does_not_block(org_root):
    """Un gate BLOCKED es aceptable si ninguna de sus stories es P0 —
    p.ej. una feature P1 que aún no existe no debe frenar la release."""
    traceability = {
        "entries": [
            _base_entry(),  # cubre ARG-001 (P0) para no disparar el check de huérfanas
            _base_entry(uc_id="G2b", gate_id="G2b", story_ids=["ARG-002"], status="BLOCKED"),
        ]
    }
    result = validate(traceability, org_root=org_root)
    assert result.errors == []
    assert result.p0_blocked_gates == []
    assert result.ok


def test_orphan_p0_story_not_referenced_by_any_entry_is_an_error(org_root):
    _write_backlog(
        org_root,
        [
            {"id": "ARG-001", "priority": "P0"},
            {"id": "ARG-777", "priority": "P0"},
        ],
    )
    traceability = {"entries": [_base_entry()]}  # solo referencia ARG-001
    result = validate(traceability, org_root=org_root)
    assert any("ARG-777" in e for e in result.errors)


def test_invalid_status_value_is_an_error(org_root):
    traceability = {"entries": [_base_entry(status="DONE")]}
    result = validate(traceability, org_root=org_root)
    assert any("DONE" in e for e in result.errors)


def test_empty_entries_is_an_error_not_a_silent_pass(org_root):
    result = validate({"entries": []}, org_root=org_root)
    assert result.errors
    assert not result.ok


def test_no_sibling_repos_available_produces_warnings_not_false_pass(tmp_path):
    """Sin argos-control/argos-contracts-scenarios clonados como hermanos,
    el validador no debe fingir que las referencias son correctas —
    debe avisar explícitamente qué no pudo comprobar."""
    traceability = {"entries": [_base_entry(test_ids=[])]}
    result = validate(traceability, org_root=tmp_path)
    assert len(result.warnings) == 2  # backlog y contratos, ambos ausentes
    assert result.errors == []  # sin catálogo real no se inventan errores de cruce


def test_real_traceability_file_matches_the_known_project_state():
    """Integración contra el traceability.yaml real del repo: valida limpio
    salvo el único bloqueo P0 conocido y documentado (G7 depende de G6,
    que a su vez tiene gaps reales sin construir — ARG-023/025/026)."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    org_root = repo_root.parent
    if not (org_root / "argos-control" / "project" / "backlog" / "backlog.yaml").exists():
        pytest.skip("argos-control no está disponible como hermano")

    traceability = load_traceability(repo_root / "traceability.yaml")
    result = validate(traceability, org_root=org_root)

    assert result.errors == []
    assert result.warnings == []
    assert result.p0_blocked_gates == ["G7 (G7): contiene story(s) P0 y status=BLOCKED"]
