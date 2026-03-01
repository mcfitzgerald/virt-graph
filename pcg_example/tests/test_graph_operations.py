"""
Graph Operations Coverage Tests for PCG Ontology v2.0

Tests that the ontology correctly declares the virtual twin graph structure:
  - Transport network (route_segments) declares algorithm operation types
  - SKU alias chain declares recursive_traversal
  - Polymorphic relationships have type_discriminator
  - Weighted relationships have weight_columns
  - Context blocks present on key entities and relationships
  - Edge attributes present on junction table relationships
  - Operation type coverage across the 11 available types
  - OWL 2 role axiom declarations
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from virt_graph.ontology import OntologyAccessor

ONTOLOGY_PATH = Path(__file__).parent.parent / "ontology" / "pcg.yaml"


@pytest.fixture(scope="module")
def ontology():
    """Load PCG ontology with validation."""
    return OntologyAccessor(ONTOLOGY_PATH)


class TestTransportNetwork:
    """Test route_segments declared as weighted transport graph."""

    def test_route_segment_origin_has_algorithm_ops(self, ontology):
        ops = ontology.get_operation_types("RouteSegmentOrigin")
        for op in ("shortest_path", "centrality", "connected_components", "resilience_analysis"):
            assert op in ops, f"RouteSegmentOrigin missing {op}"

    def test_route_segment_destination_has_algorithm_ops(self, ontology):
        ops = ontology.get_operation_types("RouteSegmentDestination")
        for op in ("shortest_path", "centrality", "connected_components", "resilience_analysis"):
            assert op in ops, f"RouteSegmentDestination missing {op}"

    def test_route_segment_origin_is_weighted(self, ontology):
        wc = ontology.get_role_weight_columns("RouteSegmentOrigin")
        assert len(wc) >= 2
        names = [w["name"] for w in wc]
        assert "distance_km" in names
        assert "transit_time_hours" in names

    def test_route_segment_destination_is_weighted(self, ontology):
        wc = ontology.get_role_weight_columns("RouteSegmentDestination")
        assert len(wc) >= 2

    def test_route_segment_origin_is_polymorphic(self, ontology):
        assert ontology.is_role_polymorphic("RouteSegmentOrigin")
        disc = ontology.get_role_type_discriminator("RouteSegmentOrigin")
        assert disc is not None
        assert disc["column"] == "origin_type"

    def test_route_segment_destination_is_polymorphic(self, ontology):
        assert ontology.is_role_polymorphic("RouteSegmentDestination")
        disc = ontology.get_role_type_discriminator("RouteSegmentDestination")
        assert disc is not None
        assert disc["column"] == "destination_type"


class TestSKUAliasChain:
    """Test SKU supersession as recursive traversal."""

    def test_sku_supersedes_has_recursive_traversal(self, ontology):
        ops = ontology.get_operation_types("SKUSupersedes")
        assert "recursive_traversal" in ops

    def test_sku_supersedes_is_acyclic(self, ontology):
        raw = ontology._rbox["SKUSupersedes"]
        acyclic = ontology._get_annotation(raw, "acyclic")
        assert acyclic in (True, "true", "True")

    def test_sku_supersedes_is_asymmetric(self, ontology):
        raw = ontology._rbox["SKUSupersedes"]
        asym = ontology._get_annotation(raw, "asymmetric")
        assert asym in (True, "true", "True")

    def test_sku_supersedes_is_irreflexive(self, ontology):
        raw = ontology._rbox["SKUSupersedes"]
        irr = ontology._get_annotation(raw, "irreflexive")
        assert irr in (True, "true", "True")

    def test_sku_supersedes_is_self_referential(self, ontology):
        domain = ontology.get_role_domain("SKUSupersedes")
        range_cls = ontology.get_role_range("SKUSupersedes")
        assert domain == "SKU"
        assert range_cls == "SKU"


class TestPolymorphicRelationships:
    """Test polymorphic relationships with type_discriminator."""

    DISCRIMINATED_ROLES = {
        "BatchProducesProduct": ("product_type", {"finished_good": "SKU", "bulk_intermediate": "BulkIntermediate"}),
        "FormulaForProduct": ("bom_level", {0: "SKU", 1: "BulkIntermediate"}),
        "InventoryAtLocation": ("location_type", {"plant": "Plant", "dc": "DistributionCenter", "retail": "RetailLocation"}),
        "RouteSegmentOrigin": ("origin_type", {"plant": "Plant", "dc": "DistributionCenter", "retail": "RetailLocation"}),
        "RouteSegmentDestination": ("destination_type", {"plant": "Plant", "dc": "DistributionCenter", "retail": "RetailLocation"}),
    }

    def test_at_least_5_type_discriminators(self, ontology):
        td_roles = [r for r in ontology.roles if ontology.get_role_type_discriminator(r)]
        assert len(td_roles) >= 5, f"Expected >= 5 type_discriminator roles, got {len(td_roles)}: {td_roles}"

    @pytest.mark.parametrize("role_name", DISCRIMINATED_ROLES.keys())
    def test_type_discriminator_column(self, ontology, role_name):
        disc = ontology.get_role_type_discriminator(role_name)
        expected_col, _ = self.DISCRIMINATED_ROLES[role_name]
        assert disc is not None, f"{role_name} missing type_discriminator"
        assert disc["column"] == expected_col

    @pytest.mark.parametrize("role_name", DISCRIMINATED_ROLES.keys())
    def test_type_discriminator_mapping(self, ontology, role_name):
        disc = ontology.get_role_type_discriminator(role_name)
        _, expected_mapping = self.DISCRIMINATED_ROLES[role_name]
        # Values in mapping should reference valid entity classes
        for val in disc["mapping"].values():
            assert val in ontology.classes, f"{role_name} discriminator maps to unknown class '{val}'"

    def test_shipment_polymorphic_without_discriminator(self, ontology):
        """Shipment origin/destination are polymorphic but lack clean discriminator."""
        for role in ("ShipmentFromOrigin", "ShipmentToDestination"):
            assert ontology.is_role_polymorphic(role)
            range_classes = ontology.get_role_range_classes(role)
            assert len(range_classes) >= 3


class TestContextBlocks:
    """Test context blocks on key entities and relationships."""

    ENTITY_CONTEXT_CLASSES = ["Batch", "Order", "Shipment", "Inventory", "RouteSegment", "GLJournal"]
    ROLE_CONTEXT_ROLES = ["FormulaHasIngredients", "BatchConsumesIngredient", "RouteSegmentOrigin", "RouteSegmentDestination"]

    @pytest.mark.parametrize("class_name", ENTITY_CONTEXT_CLASSES)
    def test_entity_has_context(self, ontology, class_name):
        ctx = ontology.get_class_context(class_name)
        assert ctx is not None, f"Class {class_name} missing context block"

    @pytest.mark.parametrize("role_name", ROLE_CONTEXT_ROLES)
    def test_role_has_context(self, ontology, role_name):
        ctx = ontology.get_role_context(role_name)
        assert ctx is not None, f"Role {role_name} missing context block"

    def test_at_least_5_entity_contexts(self, ontology):
        count = sum(1 for c in ontology.classes if ontology.get_class_context(c))
        assert count >= 5, f"Expected >= 5 entity contexts, got {count}"

    def test_at_least_3_role_contexts(self, ontology):
        count = sum(1 for r in ontology.roles if ontology.get_role_context(r))
        assert count >= 3, f"Expected >= 3 role contexts, got {count}"


class TestEdgeAttributes:
    """Test edge attributes on junction table relationships."""

    EDGE_ATTRIBUTE_ROLES = {
        "SupplierOffersIngredient": ["unit_cost", "lead_time_days", "min_order_qty"],
        "FormulaHasIngredients": ["sequence", "quantity_kg"],
        "BatchConsumesIngredient": ["quantity_kg"],
    }

    @pytest.mark.parametrize("role_name,expected_attrs", EDGE_ATTRIBUTE_ROLES.items())
    def test_edge_attributes_present(self, ontology, role_name, expected_attrs):
        ea = ontology.get_role_edge_attributes(role_name)
        attr_names = [a["name"] for a in ea]
        for attr in expected_attrs:
            assert attr in attr_names, f"{role_name} missing edge attribute '{attr}'"

    def test_at_least_3_roles_with_edge_attributes(self, ontology):
        count = sum(1 for r in ontology.roles if ontology.get_role_edge_attributes(r))
        assert count >= 3, f"Expected >= 3 roles with edge_attributes, got {count}"


class TestOperationTypeCoverage:
    """Test operation type coverage across the ontology."""

    def test_at_least_8_operation_types_used(self, ontology):
        all_ops = set()
        for r in ontology.roles:
            all_ops.update(ontology.get_operation_types(r))
        assert len(all_ops) >= 8, f"Expected >= 8 operation types, got {len(all_ops)}: {all_ops}"

    def test_direct_join_present(self, ontology):
        roles_with_dj = [r for r in ontology.roles if "direct_join" in ontology.get_operation_types(r)]
        assert len(roles_with_dj) > 0

    def test_recursive_traversal_present(self, ontology):
        roles = [r for r in ontology.roles if "recursive_traversal" in ontology.get_operation_types(r)]
        assert len(roles) >= 1, "No roles with recursive_traversal"

    def test_shortest_path_present(self, ontology):
        roles = [r for r in ontology.roles if "shortest_path" in ontology.get_operation_types(r)]
        assert len(roles) >= 1, "No roles with shortest_path"

    def test_centrality_present(self, ontology):
        roles = [r for r in ontology.roles if "centrality" in ontology.get_operation_types(r)]
        assert len(roles) >= 1, "No roles with centrality"

    def test_hierarchical_aggregation_present(self, ontology):
        roles = [r for r in ontology.roles if "hierarchical_aggregation" in ontology.get_operation_types(r)]
        assert len(roles) >= 1, "No roles with hierarchical_aggregation"

    def test_path_aggregation_present(self, ontology):
        roles = [r for r in ontology.roles if "path_aggregation" in ontology.get_operation_types(r)]
        assert len(roles) >= 1, "No roles with path_aggregation"


class TestNewRelationships:
    """Test the new relationships added in v2.0."""

    NEW_RELATIONSHIPS = [
        "GRFromShipment", "GRAtPlant", "OrderFromChannel", "OrderForRetailLocation",
        "InventoryForSKU", "InventoryAtLocation", "DemandForecastForSKU",
        "ReturnFromRetailLocation", "DispositionForReturn", "APInvoiceLineForIngredient",
        "ARInvoiceLineForSKU", "ARInvoiceForCustomer", "GLJournalToAccount",
        "SKUSupersedes", "BatchProducesProduct", "FormulaForProduct",
        "RouteSegmentOrigin", "RouteSegmentDestination",
        "ShipmentFromOrigin", "ShipmentToDestination",
    ]

    @pytest.mark.parametrize("role_name", NEW_RELATIONSHIPS)
    def test_new_relationship_exists(self, ontology, role_name):
        assert role_name in ontology.roles, f"Expected relationship {role_name} not found"

    def test_total_relationship_count(self, ontology):
        assert len(ontology.roles) == 50

    def test_functional_relationships(self, ontology):
        """New functional relationships correctly declared."""
        functional_roles = [
            "GRFromShipment", "GRAtPlant", "OrderFromChannel", "OrderForRetailLocation",
            "ReturnFromRetailLocation", "DispositionForReturn", "ARInvoiceForCustomer",
            "BatchProducesProduct", "FormulaForProduct",
            "RouteSegmentOrigin", "RouteSegmentDestination",
            "ShipmentFromOrigin", "ShipmentToDestination",
        ]
        for role in functional_roles:
            raw = ontology._rbox[role]
            func = ontology._get_annotation(raw, "functional")
            assert func in (True, "true", "True"), f"{role} should be functional"
