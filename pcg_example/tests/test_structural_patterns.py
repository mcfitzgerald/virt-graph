"""
Structural Patterns Tests for PCG Ontology

Tests the class hierarchy, inheritance, mixins, and enums introduced
by scm_base.yaml and used in pcg.yaml v3.0.

Covers:
  - scm_base.yaml loads as valid LinkML
  - Abstract class definitions (Location, TransactionDocument, LineItem)
  - is_a chains: Plant -> Location, Order -> TransactionDocument, etc.
  - Mixin application: Supplier has HasActiveFlag + HasName
  - LocationType enum values
  - SchemaView merged view shows inherited attributes on concrete classes
  - Abstract classes excluded from TBox/RBox
"""

from pathlib import Path

import pytest
import yaml
from linkml_runtime.utils.schemaview import SchemaView

ONTOLOGY_PATH = Path(__file__).parent.parent / "ontology" / "pcg.yaml"
SCM_BASE_PATH = Path(__file__).parent.parent / "ontology" / "scm_base.yaml"


@pytest.fixture(scope="module")
def ontology():
    """Load PCG ontology with validation."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from virt_graph.ontology import OntologyAccessor
    return OntologyAccessor(ONTOLOGY_PATH)


@pytest.fixture(scope="module")
def schema_view():
    """Load merged SchemaView for inheritance queries."""
    return SchemaView(str(ONTOLOGY_PATH), merge_imports=True)


@pytest.fixture(scope="module")
def base_yaml():
    """Load raw scm_base.yaml."""
    with open(SCM_BASE_PATH) as f:
        return yaml.safe_load(f)


# =============================================================================
# scm_base.yaml validity
# =============================================================================

class TestBaseSchema:
    """Test that scm_base.yaml is a valid LinkML schema."""

    def test_base_schema_exists(self):
        assert SCM_BASE_PATH.exists(), f"scm_base.yaml not found: {SCM_BASE_PATH}"

    def test_base_schema_valid_yaml(self):
        with open(SCM_BASE_PATH) as f:
            data = yaml.safe_load(f)
        assert data is not None

    def test_base_schema_has_name(self, base_yaml):
        assert base_yaml["name"] == "scm_base"

    def test_base_schema_has_version(self, base_yaml):
        assert base_yaml["version"] == "1.0.0"

    def test_base_schema_loads_as_linkml(self):
        """scm_base.yaml parses as valid LinkML via SchemaView."""
        sv = SchemaView(str(SCM_BASE_PATH))
        assert sv.schema.name == "scm_base"


# =============================================================================
# Abstract classes
# =============================================================================

class TestAbstractClasses:
    """Test abstract class definitions in scm_base.yaml."""

    ABSTRACT_CLASSES = ["Location", "TransactionDocument", "LineItem"]

    @pytest.mark.parametrize("cls_name", ABSTRACT_CLASSES)
    def test_abstract_flag(self, schema_view, cls_name):
        """Abstract classes must have abstract: true."""
        cls = schema_view.get_class(cls_name)
        assert cls is not None, f"Class {cls_name} not found in merged schema"
        assert cls.abstract is True, f"{cls_name} should be abstract"

    @pytest.mark.parametrize("cls_name", ABSTRACT_CLASSES)
    def test_abstract_excluded_from_tbox(self, ontology, cls_name):
        """Abstract classes must NOT appear in TBox."""
        assert cls_name not in ontology.classes

    @pytest.mark.parametrize("cls_name", ABSTRACT_CLASSES)
    def test_abstract_excluded_from_rbox(self, ontology, cls_name):
        """Abstract classes must NOT appear in RBox."""
        assert cls_name not in ontology.roles


class TestMixinClasses:
    """Test mixin class definitions in scm_base.yaml."""

    MIXIN_CLASSES = ["HasActiveFlag", "HasName"]

    @pytest.mark.parametrize("cls_name", MIXIN_CLASSES)
    def test_mixin_flag(self, schema_view, cls_name):
        """Mixin classes must have mixin: true."""
        cls = schema_view.get_class(cls_name)
        assert cls is not None, f"Mixin {cls_name} not found"
        assert cls.mixin is True, f"{cls_name} should be a mixin"

    @pytest.mark.parametrize("cls_name", MIXIN_CLASSES)
    def test_mixin_excluded_from_tbox(self, ontology, cls_name):
        """Mixin classes must NOT appear in TBox."""
        assert cls_name not in ontology.classes


# =============================================================================
# is_a hierarchy
# =============================================================================

class TestIsAHierarchy:
    """Test is_a chains in pcg.yaml."""

    LOCATION_CHILDREN = ["Plant", "DistributionCenter", "RetailLocation"]

    TRANSACTION_DOCUMENT_CHILDREN = [
        "PurchaseOrder", "GoodsReceipt", "WorkOrder", "Batch",
        "Order", "Shipment", "Return", "APInvoice", "ARInvoice",
    ]

    LINE_ITEM_CHILDREN = [
        "PurchaseOrderLine", "GoodsReceiptLine", "OrderLine",
        "ShipmentLine", "ReturnLine", "APInvoiceLine", "ARInvoiceLine",
    ]

    @pytest.mark.parametrize("child", LOCATION_CHILDREN)
    def test_location_child(self, schema_view, child):
        """Location children have is_a: Location."""
        cls = schema_view.get_class(child)
        assert cls.is_a == "Location", f"{child}.is_a should be Location"

    @pytest.mark.parametrize("child", TRANSACTION_DOCUMENT_CHILDREN)
    def test_transaction_document_child(self, schema_view, child):
        """TransactionDocument children have is_a: TransactionDocument."""
        cls = schema_view.get_class(child)
        assert cls.is_a == "TransactionDocument", (
            f"{child}.is_a should be TransactionDocument, got {cls.is_a}"
        )

    @pytest.mark.parametrize("child", LINE_ITEM_CHILDREN)
    def test_line_item_child(self, schema_view, child):
        """LineItem children have is_a: LineItem."""
        cls = schema_view.get_class(child)
        assert cls.is_a == "LineItem", f"{child}.is_a should be LineItem"

    @pytest.mark.parametrize("child", LOCATION_CHILDREN)
    def test_location_children_in_tbox(self, ontology, child):
        """Concrete Location children must still be in TBox."""
        assert child in ontology.classes

    @pytest.mark.parametrize("child", TRANSACTION_DOCUMENT_CHILDREN)
    def test_transaction_doc_children_in_tbox(self, ontology, child):
        """Concrete TransactionDocument children must still be in TBox."""
        assert child in ontology.classes


# =============================================================================
# Mixin application
# =============================================================================

class TestMixinApplication:
    """Test that mixins are applied correctly to concrete classes."""

    HAS_ACTIVE_FLAG_CLASSES = [
        "Supplier", "Ingredient", "BulkIntermediate", "SKU",
        "Channel", "ProductionLine", "ChartOfAccounts",
        # Location children get it through Location
        "Plant", "DistributionCenter", "RetailLocation",
    ]

    HAS_NAME_CLASSES = [
        "Supplier", "Ingredient", "BulkIntermediate", "SKU",
        "Channel", "ChartOfAccounts",
        # Location children get it through Location
        "Plant", "DistributionCenter", "RetailLocation",
    ]

    @pytest.mark.parametrize("cls_name", HAS_ACTIVE_FLAG_CLASSES)
    def test_has_is_active(self, ontology, cls_name):
        """Classes with HasActiveFlag mixin inherit is_active slot."""
        attrs = ontology.get_class_inherited_attributes(cls_name)
        assert "is_active" in attrs, (
            f"{cls_name} should have is_active via HasActiveFlag mixin"
        )

    @pytest.mark.parametrize("cls_name", HAS_NAME_CLASSES)
    def test_has_name(self, ontology, cls_name):
        """Classes with HasName mixin inherit name slot."""
        attrs = ontology.get_class_inherited_attributes(cls_name)
        assert "name" in attrs, (
            f"{cls_name} should have name via HasName mixin"
        )


# =============================================================================
# Slot inheritance
# =============================================================================

class TestSlotInheritance:
    """Test that inherited slots are visible via SchemaView."""

    def test_plant_inherits_name(self, ontology):
        """Plant inherits 'name' from Location -> HasName."""
        attrs = ontology.get_class_inherited_attributes("Plant")
        assert "name" in attrs

    def test_plant_inherits_is_active(self, ontology):
        """Plant inherits 'is_active' from Location -> HasActiveFlag."""
        attrs = ontology.get_class_inherited_attributes("Plant")
        assert "is_active" in attrs

    def test_plant_keeps_local_attrs(self, ontology):
        """Plant keeps its own local attributes."""
        attrs = ontology.get_class_inherited_attributes("Plant")
        assert "plant_code" in attrs
        assert "capacity_tons_per_day" in attrs

    def test_order_inherits_status(self, ontology):
        """Order inherits 'status' from TransactionDocument."""
        attrs = ontology.get_class_inherited_attributes("Order")
        assert "status" in attrs

    def test_order_line_inherits_line_number(self, ontology):
        """OrderLine inherits 'line_number' from LineItem."""
        attrs = ontology.get_class_inherited_attributes("OrderLine")
        assert "line_number" in attrs

    def test_local_attrs_not_lost(self, ontology):
        """Local attributes on Order are preserved alongside inherited ones."""
        attrs = ontology.get_class_inherited_attributes("Order")
        assert "order_number" in attrs
        assert "day" in attrs
        assert "total_cases" in attrs


# =============================================================================
# LocationType enum
# =============================================================================

class TestLocationTypeEnum:
    """Test LocationType enum from scm_base.yaml."""

    def test_enum_exists(self, schema_view):
        """LocationType enum is defined."""
        enum = schema_view.get_enum("LocationType")
        assert enum is not None

    def test_enum_values(self, schema_view):
        """LocationType has plant, dc, retail values."""
        enum = schema_view.get_enum("LocationType")
        values = set(enum.permissible_values.keys())
        assert values == {"plant", "dc", "retail"}

    def test_inventory_uses_location_type(self):
        """Inventory.location_type references LocationType enum."""
        with open(ONTOLOGY_PATH) as f:
            data = yaml.safe_load(f)
        inv_attrs = data["classes"]["Inventory"]["attributes"]
        assert inv_attrs["location_type"]["range"] == "LocationType"

    def test_route_segment_uses_location_type(self):
        """RouteSegment origin_type/destination_type use LocationType enum."""
        with open(ONTOLOGY_PATH) as f:
            data = yaml.safe_load(f)
        rs_attrs = data["classes"]["RouteSegment"]["attributes"]
        assert rs_attrs["origin_type"]["range"] == "LocationType"
        assert rs_attrs["destination_type"]["range"] == "LocationType"

    def test_demand_forecast_uses_location_type(self):
        """DemandForecast.location_type references LocationType enum."""
        with open(ONTOLOGY_PATH) as f:
            data = yaml.safe_load(f)
        df_attrs = data["classes"]["DemandForecast"]["attributes"]
        assert df_attrs["location_type"]["range"] == "LocationType"


# =============================================================================
# Counts unchanged
# =============================================================================

class TestCountsUnchanged:
    """Verify structural changes don't alter TBox/RBox counts."""

    def test_entity_count_unchanged(self, ontology):
        """Still 38 entity classes (abstract classes excluded)."""
        assert len(ontology.classes) == 38

    def test_role_count_unchanged(self, ontology):
        """Still 50 relationships (no relationship changes)."""
        assert len(ontology.roles) == 50
