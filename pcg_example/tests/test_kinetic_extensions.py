"""
Kinetic Extension Validation Tests for PCG Ontology

Tests for metamodel v3.0 features:
  - Axiom validation (class and relationship level)
  - State machine validation (states, transitions, guards)
  - Flow configuration validation
  - Action validation (effects, affected_relationships)
  - Scenario parameter validation
  - Kinetic operation types
  - Negative test cases using inline YAML fixtures
"""

import sys
import textwrap
import tempfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from virt_graph.ontology import OntologyAccessor, OntologyValidationError

ONTOLOGY_PATH = Path(__file__).parent.parent / "ontology" / "pcg.yaml"


@pytest.fixture(scope="module")
def ontology():
    """Load PCG ontology with validation."""
    return OntologyAccessor(ONTOLOGY_PATH)


def _make_ontology(yaml_str: str, validate: bool = True) -> OntologyAccessor:
    """Create an OntologyAccessor from inline YAML."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str)
        f.flush()
        return OntologyAccessor(Path(f.name), validate=validate)


def _minimal_ontology(extra_classes: str = "") -> str:
    """Return minimal valid ontology YAML with optional extra classes."""
    return textwrap.dedent(f"""\
        id: https://test.dev/test
        name: test
        version: "1.0"
        prefixes:
          linkml: https://w3id.org/linkml/
          vg: https://virt-graph.dev/
        imports:
          - linkml:types
        default_range: string
        classes:
          TestEntity:
            instantiates:
              - vg:SQLMappedClass
            annotations:
              vg:table: test_table
              vg:primary_key: id
        {extra_classes}
    """)


class TestAxiomValidation:
    """Test axiom loading and validation."""

    def test_class_axioms_load(self, ontology):
        """Axioms load from entity class (Batch has yield_range)."""
        axioms = ontology.get_class_axioms("Batch")
        assert len(axioms) >= 1
        names = [a["name"] for a in axioms]
        assert "yield_range" in names

    def test_relationship_axioms_load(self, ontology):
        """Axioms load from relationship (FormulaHasIngredients)."""
        axioms = ontology.get_role_axioms("FormulaHasIngredients")
        assert len(axioms) >= 1
        names = [a["name"] for a in axioms]
        assert "ingredient_quantity_positive" in names

    def test_axiom_has_required_fields(self, ontology):
        """Each axiom has name, description, axiom_type, sql_expression, severity."""
        for cls_name in ontology.classes:
            for axiom in ontology.get_class_axioms(cls_name):
                for field in ("name", "description", "axiom_type", "sql_expression", "severity"):
                    assert field in axiom, f"Axiom in {cls_name} missing '{field}'"

    def test_invalid_axiom_severity_rejected(self):
        """Axiom with invalid severity value fails validation."""
        yaml_str = _minimal_ontology("""
          BadEntity:
            instantiates:
              - vg:SQLMappedClass
            annotations:
              vg:table: bad_table
              vg:primary_key: id
              vg:axioms: '[{"name": "test", "description": "test", "axiom_type": "value_range", "sql_expression": "x > 0", "severity": "catastrophic"}]'
        """)
        with pytest.raises(OntologyValidationError, match="severity"):
            _make_ontology(yaml_str)

    def test_invalid_axiom_type_rejected(self):
        """Axiom with invalid axiom_type value fails validation."""
        yaml_str = _minimal_ontology("""
          BadEntity:
            instantiates:
              - vg:SQLMappedClass
            annotations:
              vg:table: bad_table
              vg:primary_key: id
              vg:axioms: '[{"name": "test", "description": "test", "axiom_type": "quantum_entanglement", "sql_expression": "x > 0", "severity": "error"}]'
        """)
        with pytest.raises(OntologyValidationError, match="axiom_type"):
            _make_ontology(yaml_str)

    def test_sql_injection_in_axiom_detected(self):
        """Axiom with SQL injection pattern is rejected."""
        yaml_str = _minimal_ontology("""
          BadEntity:
            instantiates:
              - vg:SQLMappedClass
            annotations:
              vg:table: bad_table
              vg:primary_key: id
              vg:axioms: '[{"name": "test", "description": "test", "axiom_type": "value_range", "sql_expression": "1=1; DROP TABLE users", "severity": "error"}]'
        """)
        with pytest.raises(OntologyValidationError, match="dangerous pattern"):
            _make_ontology(yaml_str)


class TestStateMachineValidation:
    """Test state machine loading and validation."""

    EXPECTED_SM_CLASSES = [
        "PurchaseOrder", "GoodsReceipt", "WorkOrder", "Batch",
        "Order", "Shipment", "Return", "APInvoice", "ARInvoice",
    ]

    def test_get_classes_with_state_machines(self, ontology):
        sm_classes = ontology.get_classes_with_state_machines()
        for expected in self.EXPECTED_SM_CLASSES:
            assert expected in sm_classes, f"Missing state machine for {expected}"

    def test_state_machine_count(self, ontology):
        assert len(ontology.get_classes_with_state_machines()) == 9

    def test_order_state_machine_structure(self, ontology):
        """Order has pending->allocated->shipped->delivered lifecycle."""
        sm = ontology.get_class_state_machine("Order")
        assert sm is not None
        assert sm["state_column"] == "status"
        assert set(sm["states"]) == {"pending", "allocated", "shipped", "delivered"}
        assert sm["initial_state"] == "pending"
        assert sm["terminal_states"] == ["delivered"]
        assert len(sm["transitions"]) == 3

    def test_ar_invoice_has_multiple_terminal_states(self, ontology):
        """AR invoice can end as paid or bad_debt."""
        sm = ontology.get_class_state_machine("ARInvoice")
        assert set(sm["terminal_states"]) == {"paid", "bad_debt"}

    def test_invalid_transition_state_rejected(self):
        """State machine with transition referencing undeclared state fails."""
        yaml_str = _minimal_ontology("""
          BadEntity:
            instantiates:
              - vg:SQLMappedClass
            annotations:
              vg:table: bad_table
              vg:primary_key: id
              vg:state_machine: '{"state_column": "status", "states": ["open", "closed"], "transitions": [{"from_state": "open", "to_state": "archived"}]}'
        """)
        with pytest.raises(OntologyValidationError, match="not in declared states"):
            _make_ontology(yaml_str)

    def test_sql_injection_in_guard_detected(self):
        """State machine with SQL injection in guard is rejected."""
        yaml_str = _minimal_ontology("""
          BadEntity:
            instantiates:
              - vg:SQLMappedClass
            annotations:
              vg:table: bad_table
              vg:primary_key: id
              vg:state_machine: '{"state_column": "status", "states": ["open", "closed"], "transitions": [{"from_state": "open", "to_state": "closed", "guard": "1=1; DROP TABLE users"}]}'
        """)
        with pytest.raises(OntologyValidationError, match="dangerous pattern"):
            _make_ontology(yaml_str)

    def test_class_without_state_machine_returns_none(self, ontology):
        sm = ontology.get_class_state_machine("Supplier")
        assert sm is None


class TestFlowConfigValidation:
    """Test flow configuration loading and validation."""

    def test_flow_config_loads(self, ontology):
        fc = ontology.get_role_flow_config("BatchConsumesIngredient")
        assert fc is not None
        assert fc["flow_type"] == "material"
        assert fc["quantity_column"] == "quantity_kg"
        assert fc["conservation_group"] == "production_mass_balance"

    def test_get_roles_with_flow_config(self, ontology):
        roles = ontology.get_roles_with_flow_config()
        assert len(roles) == 10
        assert "BatchConsumesIngredient" in roles
        assert "APPaymentForInvoice" in roles

    def test_conservation_groups(self, ontology):
        groups = ontology.get_conservation_groups()
        assert "procure_to_pay" in groups
        assert "order_to_cash" in groups
        assert "production_mass_balance" in groups
        assert len(groups) == 3

    def test_invalid_flow_type_rejected(self):
        """Flow config with invalid flow_type fails validation."""
        yaml_str = _minimal_ontology("""
          BadRel:
            instantiates:
              - vg:SQLMappedRelationship
            annotations:
              vg:edge_table: test_edges
              vg:domain_key: a_id
              vg:range_key: b_id
              vg:domain_class: TestEntity
              vg:range_class: TestEntity
              vg:operation_types: '["direct_join"]'
              vg:flow_config: '{"flow_type": "quantum", "quantity_column": "qty", "timestamp_column": "ts"}'
        """)
        with pytest.raises(OntologyValidationError, match="flow_type"):
            _make_ontology(yaml_str)

    def test_role_without_flow_config_returns_none(self, ontology):
        fc = ontology.get_role_flow_config("POFromSupplier")
        assert fc is None


class TestActionValidation:
    """Test action loading and validation."""

    def test_batch_actions_load(self, ontology):
        actions = ontology.get_class_actions("Batch")
        assert len(actions) == 2
        names = [a["name"] for a in actions]
        assert "start_production" in names
        assert "complete_production" in names

    def test_action_has_effects(self, ontology):
        actions = ontology.get_class_actions("Order")
        for action in actions:
            assert "effects" in action
            assert len(action["effects"]) >= 1

    def test_invalid_effect_type_rejected(self):
        """Action with invalid effect_type fails validation."""
        yaml_str = _minimal_ontology("""
          BadEntity:
            instantiates:
              - vg:SQLMappedClass
            annotations:
              vg:table: bad_table
              vg:primary_key: id
              vg:actions: '[{"name": "test", "description": "test", "effects": [{"attribute": "x", "effect_type": "teleport"}]}]'
        """)
        with pytest.raises(OntologyValidationError, match="effect_type"):
            _make_ontology(yaml_str)

    def test_class_without_actions_returns_empty(self, ontology):
        actions = ontology.get_class_actions("Supplier")
        assert actions == []


class TestScenarioParamValidation:
    """Test scenario parameter loading and validation."""

    def test_order_scenario_params(self, ontology):
        params = ontology.get_class_scenario_params("Order")
        assert len(params) == 1
        assert params[0]["attribute"] == "total_cases"
        assert params[0]["propagation"] == "downstream"

    def test_plant_scenario_params(self, ontology):
        params = ontology.get_class_scenario_params("Plant")
        assert len(params) == 1
        assert params[0]["attribute"] == "capacity_tons_per_day"

    def test_invalid_propagation_rejected(self):
        """Scenario param with invalid propagation fails validation."""
        yaml_str = _minimal_ontology("""
          BadEntity:
            instantiates:
              - vg:SQLMappedClass
            annotations:
              vg:table: bad_table
              vg:primary_key: id
              vg:scenario_params: '[{"attribute": "x", "propagation": "sideways"}]'
        """)
        with pytest.raises(OntologyValidationError, match="propagation"):
            _make_ontology(yaml_str)

    def test_class_without_scenario_params_returns_empty(self, ontology):
        params = ontology.get_class_scenario_params("Channel")
        assert params == []


class TestKineticOperationTypes:
    """Test kinetic operation type enums."""

    def test_kinetic_operation_types_valid(self, ontology):
        """flow_analysis, state_analysis, scenario_analysis are valid operation types."""
        for op in ("flow_analysis", "state_analysis", "scenario_analysis"):
            cat = ontology.get_operation_category(op)
            assert cat == "kinetic", f"{op} should be category 'kinetic', got '{cat}'"

    def test_existing_operation_types_unchanged(self, ontology):
        """Existing operation types still map to correct categories."""
        assert ontology.get_operation_category("direct_join") == "direct"
        assert ontology.get_operation_category("recursive_traversal") == "traversal"
        assert ontology.get_operation_category("shortest_path") == "algorithm"
        assert ontology.get_operation_category("path_aggregation") == "aggregation"


class TestMetamodelCacheReset:
    """Test metamodel cache reset for test isolation."""

    def test_reset_and_reload(self):
        OntologyAccessor._reset_metamodel_cache()
        assert not OntologyAccessor._metamodel_loaded
        o = OntologyAccessor(ONTOLOGY_PATH)
        assert OntologyAccessor._metamodel_loaded
        assert len(o.classes) == 38
