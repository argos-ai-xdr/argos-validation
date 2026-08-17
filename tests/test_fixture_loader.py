from __future__ import annotations

from harness.loaders.fixture_loader import build_registry, load_fixtures, validate_fixture


def test_smoke_fixtures_load_and_validate(contracts_path):
    registry = build_registry(contracts_path)
    contracts = [
        "security-event", "asset-snapshot", "vulnerability-finding", "incident",
        "recommendation", "policy-decision", "approval", "action-result",
        "evidence-manifest", "soc-handover",
    ]
    total = 0
    for contract in contracts:
        fixtures = load_fixtures(contracts_path, "smoke", contract)
        assert fixtures, f"no se encontró ningún fixture smoke para {contract}"
        for fixture in fixtures:
            errors = validate_fixture(contracts_path, registry, fixture)
            assert not errors, f"{fixture.path} inválido: {errors}"
            total += 1
    # Al menos un fixture por contrato en smoke/ — action-result y approval
    # tienen 2 cada uno desde AC12 (action-result-002-rollback.json + su
    # approval correspondiente, ver fixtures/README.md), así que ya no es
    # "exactamente 10".
    assert total == 12


def test_adversarial_fixtures_are_manifest_driven(contracts_path):
    """fixtures/adversarial/ no sigue el patrón categoria/contrato — se
    agrupa por caso de ataque y el manifest.yaml declara el schema real."""
    registry = build_registry(contracts_path)

    policy_decisions = load_fixtures(contracts_path, "adversarial", "policy-decision")
    assert len(policy_decisions) == 2  # tool-poisoning + out-of-range

    recommendations = load_fixtures(contracts_path, "adversarial", "recommendation")
    assert len(recommendations) == 1  # prompt-injection

    vuln_findings = load_fixtures(contracts_path, "adversarial", "vulnerability-finding")
    assert len(vuln_findings) == 1  # fake-cve

    # Todos deben ser schema-válidos (regla del manifest: expect_schema_valid=true)
    for fixture in policy_decisions + recommendations + vuln_findings:
        errors = validate_fixture(contracts_path, registry, fixture)
        assert not errors, f"{fixture.path} debía validar: {errors}"


def test_negative_fixtures_are_manifest_driven_and_invalid(contracts_path):
    registry = build_registry(contracts_path)
    security_events = load_fixtures(contracts_path, "negative", "security-event")
    assert len(security_events) == 1
    errors = validate_fixture(contracts_path, registry, security_events[0])
    assert errors, "el fixture negativo debía fallar la validación"


def test_unknown_contract_returns_empty_list(contracts_path):
    assert load_fixtures(contracts_path, "smoke", "no-existe") == []
