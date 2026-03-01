"""
Ontology Validation Tests for Prism Consumer Goods (PCG)

Structural validation of pcg.yaml ontology:
  - File exists, valid YAML, loads with OntologyAccessor
  - All 38 classes have required annotations
  - All relationships have operation_types, domain_class, range_class
  - Composite keys declared correctly
  - Version and database metadata correct
"""

from pathlib import Path

import pytest
import yaml

ONTOLOGY_PATH = Path(__file__).parent.parent / "ontology" / "pcg.yaml"


@pytest.fixture(scope="module")
def ontology():
    """Load PCG ontology with validation."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from virt_graph.ontology import OntologyAccessor
    return OntologyAccessor(ONTOLOGY_PATH)


@pytest.fixture(scope="module")
def raw_yaml():
    """Load raw YAML for structure checks."""
    with open(ONTOLOGY_PATH) as f:
        return yaml.safe_load(f)


class TestOntologyStructure:
    """Test basic ontology file structure."""

    def test_ontology_file_exists(self):
        assert ONTOLOGY_PATH.exists(), f"Ontology not found: {ONTOLOGY_PATH}"

    def test_ontology_valid_yaml(self):
        with open(ONTOLOGY_PATH) as f:
            data = yaml.safe_load(f)
        assert data is not None

    def test_ontology_has_required_prefixes(self, raw_yaml):
        prefixes = raw_yaml.get("prefixes", {})
        assert "linkml" in prefixes
        assert "vg" in prefixes

    def test_ontology_name(self, ontology):
        assert ontology.name == "pcg"

    def test_ontology_version(self, ontology):
        assert ontology.version == "1.0.0"

    def test_database_type(self, ontology):
        db = ontology.database
        assert db["type"] == "postgresql"


class TestEntityClasses:
    """Test all 38 entity classes have required annotations."""

    EXPECTED_CLASS_COUNT = 38

    def test_class_count(self, ontology):
        assert len(ontology.classes) == self.EXPECTED_CLASS_COUNT

    def test_all_classes_have_table(self, ontology):
        for name in ontology.classes:
            table = ontology.get_class_table(name)
            assert table is not None, f"Class {name} missing vg:table"

    def test_all_classes_have_primary_key(self, ontology):
        for name in ontology.classes:
            pk = ontology.get_class_pk(name)
            assert pk and len(pk) > 0, f"Class {name} missing vg:primary_key"

    def test_all_classes_unique_tables(self, ontology):
        """Each class maps to a unique table (no duplicates in TBox)."""
        tables = [ontology.get_class_table(name) for name in ontology.classes]
        # Some tables may be shared (e.g., embedded FK), but for PCG they're unique
        assert len(tables) == len(set(tables)), f"Duplicate tables found: {[t for t in tables if tables.count(t) > 1]}"


class TestRelationships:
    """Test all relationships have required annotations."""

    EXPECTED_ROLE_COUNT = 30

    def test_role_count(self, ontology):
        assert len(ontology.roles) == self.EXPECTED_ROLE_COUNT

    def test_all_roles_have_operation_types(self, ontology):
        for name in ontology.roles:
            op_types = ontology.get_operation_types(name)
            assert len(op_types) > 0, f"Role {name} missing operation_types"

    def test_all_roles_have_domain_range(self, ontology):
        for name in ontology.roles:
            domain = ontology.get_role_domain(name)
            range_class = ontology.get_role_range(name)
            assert domain is not None, f"Role {name} missing domain_class"
            assert range_class is not None, f"Role {name} missing range_class"

    def test_all_roles_domain_class_exists(self, ontology):
        for name in ontology.roles:
            for dc in ontology.get_role_domain_classes(name):
                assert dc in ontology.classes, f"Role {name}: domain_class '{dc}' not a known entity"

    def test_all_roles_range_class_exists(self, ontology):
        for name in ontology.roles:
            for rc in ontology.get_role_range_classes(name):
                assert rc in ontology.classes, f"Role {name}: range_class '{rc}' not a known entity"


class TestCompositeKeys:
    """Test composite key declarations match schema.sql."""

    COMPOSITE_KEY_CLASSES = {
        "PurchaseOrderLine": ["po_id", "line_number"],
        "GoodsReceiptLine": ["gr_id", "line_number"],
        "FormulaIngredient": ["formula_id", "ingredient_id", "sequence"],
        "OrderLine": ["order_id", "line_number"],
        "ShipmentLine": ["shipment_id", "line_number"],
        "ReturnLine": ["return_id", "line_number"],
        "DispositionLog": ["return_id", "return_line_number"],
        "APInvoiceLine": ["invoice_id", "line_number"],
        "ARInvoiceLine": ["invoice_id", "line_number"],
    }

    @pytest.mark.parametrize("class_name,expected_keys", COMPOSITE_KEY_CLASSES.items())
    def test_composite_key(self, ontology, class_name, expected_keys):
        pk = ontology.get_class_pk(class_name)
        assert pk == expected_keys, f"{class_name}: expected PK {expected_keys}, got {pk}"

    @pytest.mark.parametrize("class_name", COMPOSITE_KEY_CLASSES.keys())
    def test_has_composite_key(self, ontology, class_name):
        assert ontology.has_composite_key(class_name, is_class=True)


class TestSimpleKeys:
    """Test simple primary key classes."""

    SIMPLE_KEY_CLASSES = [
        "Supplier", "Ingredient", "Plant", "Formula", "WorkOrder",
        "Batch", "SKU", "Order", "Shipment", "APInvoice", "ARInvoice",
    ]

    @pytest.mark.parametrize("class_name", SIMPLE_KEY_CLASSES)
    def test_simple_pk(self, ontology, class_name):
        pk = ontology.get_class_pk(class_name)
        assert pk == ["id"], f"{class_name}: expected PK ['id'], got {pk}"
        assert not ontology.has_composite_key(class_name, is_class=True)
