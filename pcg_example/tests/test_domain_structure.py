"""
Tests for SCOR-DS aligned domain structure of the PCG ontology.

Validates:
- All classes and relationships have domain assignments
- Domain values are valid (procurement, supply, demand, orchestrate)
- Expected counts per domain
- Cross-domain relationships are properly flagged
- Subdomain assignments exist for all classes
- Orchestrate summary includes expected kinetic elements
"""

import pytest

VALID_DOMAINS = {"procurement", "supply", "demand", "orchestrate"}

EXPECTED_DOMAIN_COUNTS = {
    "procurement": {"classes": 10, "roles": 14},
    "supply": {"classes": 11, "roles": 13},
    "demand": {"classes": 17, "roles": 28},
    "orchestrate": {"classes": 3, "roles": 2},
}

EXPECTED_CROSS_DOMAIN = {
    "POAtPlant", "GRFromShipment", "GRAtPlant",
    "FormulaHasIngredients", "BatchConsumesIngredient",
    "OrderLineForSKU", "ShipmentFromOrigin", "ShipmentToDestination",
    "ShipmentLineForSKU", "InventoryForSKU", "InventoryAtLocation",
    "DemandForecastForSKU", "ReturnLineForSKU", "ReturnToDC",
    "ARInvoiceLineForSKU", "InvoiceVarianceForAPInvoice",
    "PromoEventForSKU", "DeductionForSKU",
}


class TestClassDomains:
    """Every class must have a valid domain and subdomain."""

    def test_all_classes_have_domain(self, ontology):
        missing = [n for n in ontology.classes if not ontology.get_class_domain(n)]
        assert missing == [], f"Classes missing domain: {missing}"

    def test_all_domains_valid(self, ontology):
        invalid = [
            (n, ontology.get_class_domain(n))
            for n in ontology.classes
            if ontology.get_class_domain(n) not in VALID_DOMAINS
        ]
        assert invalid == [], f"Invalid domains: {invalid}"

    def test_all_classes_have_subdomain(self, ontology):
        missing = [n for n in ontology.classes if not ontology.get_class_subdomain(n)]
        assert missing == [], f"Classes missing subdomain: {missing}"

    def test_class_counts_per_domain(self, ontology):
        domains = ontology.get_all_domains()
        for domain, expected in EXPECTED_DOMAIN_COUNTS.items():
            actual = len(domains[domain]["classes"])
            assert actual == expected["classes"], (
                f"{domain}: expected {expected['classes']} classes, got {actual}"
            )

    def test_total_classes(self, ontology):
        total = sum(v["classes"] for v in EXPECTED_DOMAIN_COUNTS.values())
        assert len(ontology.classes) == total


class TestRelationshipDomains:
    """Every relationship must have a valid domain; cross-domain must be flagged."""

    def test_all_roles_have_domain(self, ontology):
        missing = [n for n in ontology.roles if not ontology.get_role_domain_category(n)]
        assert missing == [], f"Roles missing domain: {missing}"

    def test_all_role_domains_valid(self, ontology):
        invalid = [
            (n, ontology.get_role_domain_category(n))
            for n in ontology.roles
            if ontology.get_role_domain_category(n) not in VALID_DOMAINS
        ]
        assert invalid == [], f"Invalid role domains: {invalid}"

    def test_role_counts_per_domain(self, ontology):
        domains = ontology.get_all_domains()
        for domain, expected in EXPECTED_DOMAIN_COUNTS.items():
            actual = len(domains[domain]["roles"])
            assert actual == expected["roles"], (
                f"{domain}: expected {expected['roles']} roles, got {actual}"
            )

    def test_total_roles(self, ontology):
        total = sum(v["roles"] for v in EXPECTED_DOMAIN_COUNTS.values())
        assert len(ontology.roles) == total

    def test_cross_domain_set(self, ontology):
        actual = set(ontology.get_cross_domain_roles())
        assert actual == EXPECTED_CROSS_DOMAIN

    def test_cross_domain_count(self, ontology):
        assert len(ontology.get_cross_domain_roles()) == 18


class TestDomainIntegrity:
    """Domain structure should be internally consistent."""

    def test_four_domains_exist(self, ontology):
        domains = ontology.get_all_domains()
        assert set(domains.keys()) == VALID_DOMAINS

    def test_no_orphan_classes(self, ontology):
        """Every class in a domain should appear exactly once across all domains."""
        domains = ontology.get_all_domains()
        all_in_domains = set()
        for info in domains.values():
            for cls in info["classes"]:
                assert cls not in all_in_domains, f"{cls} appears in multiple domains"
                all_in_domains.add(cls)
        assert all_in_domains == set(ontology.classes.keys())

    def test_no_orphan_roles(self, ontology):
        """Every role in a domain should appear exactly once across all domains."""
        domains = ontology.get_all_domains()
        all_in_domains = set()
        for info in domains.values():
            for role in info["roles"]:
                assert role not in all_in_domains, f"{role} appears in multiple domains"
                all_in_domains.add(role)
        assert all_in_domains == set(ontology.roles.keys())

    def test_orchestrate_has_financial_entities(self, ontology):
        """Orchestrate domain should contain financial cross-cutting entities."""
        fin = ontology.get_financial_entities()
        assert len(fin) > 0
        for name in fin:
            assert ontology.get_class_domain(name) in {"orchestrate", "procurement", "demand"}

    def test_orchestrate_summary_has_state_machines(self, ontology):
        summary = ontology.get_orchestrate_summary()
        assert len(summary.get("state_machines", [])) > 0

    def test_orchestrate_summary_has_flow_configs(self, ontology):
        summary = ontology.get_orchestrate_summary()
        assert len(summary.get("flow_configs", [])) > 0

    def test_orchestrate_summary_has_conservation_groups(self, ontology):
        summary = ontology.get_orchestrate_summary()
        assert len(summary.get("conservation_groups", {})) > 0
