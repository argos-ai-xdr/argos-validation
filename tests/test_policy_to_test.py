from __future__ import annotations

import pathlib

import pytest

from harness.policy_to_test import load_policy_to_test, main, validate


def _write_test_file(org_root: pathlib.Path, relative_path: str, func_name: str) -> None:
    path = org_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"def {func_name}():\n    pass\n", encoding="utf-8")


@pytest.fixture
def org_root(tmp_path: pathlib.Path) -> pathlib.Path:
    _write_test_file(tmp_path, "argos-core/tests/unit/test_thing.py", "test_the_rule")
    return tmp_path


def _base_policy(**overrides: object) -> dict:
    policy: dict[str, object] = {
        "rule_groups": [
            {
                "id": "group-1",
                "rules": [
                    {
                        "id": "R1",
                        "description": "algo",
                        "tests": ["argos-core/tests/unit/test_thing.py::test_the_rule"],
                    }
                ],
            }
        ]
    }
    policy.update(overrides)
    return policy


def test_well_formed_policy_validates_clean(org_root):
    result = validate(_base_policy(), org_root=org_root)
    assert result.errors == []
    assert result.ok


def test_missing_test_file_is_an_error(org_root):
    policy = {
        "rule_groups": [
            {"id": "g", "rules": [{"id": "R1", "tests": ["argos-core/tests/unit/nope.py::test_x"]}]}
        ]
    }
    result = validate(policy, org_root=org_root)
    assert any("nope.py" in e for e in result.errors)
    assert not result.ok


def test_function_not_present_in_file_is_an_error(org_root):
    policy = {
        "rule_groups": [
            {
                "id": "g",
                "rules": [
                    {"id": "R1", "tests": ["argos-core/tests/unit/test_thing.py::test_does_not_exist"]}
                ],
            }
        ]
    }
    result = validate(policy, org_root=org_root)
    assert any("test_does_not_exist" in e for e in result.errors)


def test_test_ref_without_double_colon_is_an_error(org_root):
    policy = {"rule_groups": [{"id": "g", "rules": [{"id": "R1", "tests": ["argos-core/tests/unit/test_thing.py"]}]}]}
    result = validate(policy, org_root=org_root)
    assert any("formato" in e for e in result.errors)


def test_rule_without_tests_is_an_error(org_root):
    policy = {"rule_groups": [{"id": "g", "rules": [{"id": "R1", "tests": []}]}]}
    result = validate(policy, org_root=org_root)
    assert any("sin ningún test" in e for e in result.errors)


def test_rule_group_without_rules_is_an_error(org_root):
    policy = {"rule_groups": [{"id": "g", "rules": []}]}
    result = validate(policy, org_root=org_root)
    assert any("sin ninguna regla" in e for e in result.errors)


def test_duplicate_rule_id_across_groups_is_an_error(org_root):
    policy = {
        "rule_groups": [
            {"id": "g1", "rules": [{"id": "R1", "tests": ["argos-core/tests/unit/test_thing.py::test_the_rule"]}]},
            {"id": "g2", "rules": [{"id": "R1", "tests": ["argos-core/tests/unit/test_thing.py::test_the_rule"]}]},
        ]
    }
    result = validate(policy, org_root=org_root)
    assert any("duplicado" in e for e in result.errors)


def test_empty_rule_groups_is_an_error_not_a_silent_pass(org_root):
    result = validate({"rule_groups": []}, org_root=org_root)
    assert result.errors
    assert not result.ok


def test_real_policy_to_test_file_matches_the_known_project_state():
    """Integración contra traceability/policy-to-test.yaml real, contra los
    archivos de test reales de argos-core/argos-cyber-tools (hermanos)."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    org_root = repo_root.parent
    if not (org_root / "argos-core" / "tests" / "unit" / "test_policy_adapter.py").exists():
        pytest.skip("argos-core no está disponible como hermano")
    if not (org_root / "argos-cyber-tools" / "tests" / "anti-replay" / "test_approval_anti_replay.py").exists():
        pytest.skip("argos-cyber-tools no está disponible como hermano")

    data = load_policy_to_test(repo_root / "traceability" / "policy-to-test.yaml")
    result = validate(data, org_root=org_root)

    assert result.errors == []
    assert result.ok


def test_main_cli_exits_0_against_the_real_file(capsys):
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    org_root = repo_root.parent
    if not (org_root / "argos-core" / "tests" / "unit" / "test_policy_adapter.py").exists():
        pytest.skip("argos-core no está disponible como hermano")
    if not (org_root / "argos-cyber-tools" / "tests" / "anti-replay" / "test_approval_anti_replay.py").exists():
        pytest.skip("argos-cyber-tools no está disponible como hermano")

    exit_code = main(["--file", str(repo_root / "traceability" / "policy-to-test.yaml")])
    assert exit_code == 0
    assert "policy-to-test.yaml OK" in capsys.readouterr().out
