# LinkML Migration Plan

## Overview

Migrate Virtual Graph ontology format from custom TBox/RBox YAML to **LinkML-compliant schema with Virtual Graph extensions**. This enables:

1. **Schema validation** via `linkml-validate`
2. **Tooling interop** - generate JSON-Schema, SQL DDL, Python dataclasses
3. **Standards compliance** - while preserving our DL semantics
4. **Generic discovery** - works for any relational database

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LinkML Schema (source of truth)                  │
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐ │
│  │ virt_graph.yaml  │    │ supply_chain.yaml│    │ other_db.yaml │ │
│  │ (metamodel ext)  │    │ (domain schema)  │    │ (future)      │ │
│  └────────┬─────────┘    └────────┬─────────┘    └───────────────┘ │
│           │                       │                                  │
│           └───────────┬───────────┘                                  │
│                       ▼                                              │
│              linkml-validate                                         │
└─────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │     OntologyAccessor (Python) │
        │  - Maintains existing API     │
        │  - Reads LinkML format        │
        │  - Derives TBox/RBox views    │
        └───────────────────────────────┘
```

## File Structure

```
ontology/
├── virt_graph.yaml          # NEW: VG metamodel extension (defines vg: annotations)
├── TEMPLATE.yaml            # UPDATE: LinkML-compliant template
├── supply_chain.yaml        # UPDATE: Migrate to LinkML format
└── schemas/                 # NEW: Generated artifacts
    ├── supply_chain.schema.json   # Generated JSON-Schema
    └── supply_chain.sql           # Generated DDL (reference)
```

## Phase 1: Define Virtual Graph Metamodel Extension

Create `ontology/virt_graph.yaml` - our annotation vocabulary:

```yaml
id: https://virt-graph.dev/metamodel
name: virt_graph_metamodel
prefixes:
  linkml: https://w3id.org/linkml/
  vg: https://virt-graph.dev/

classes:
  # Extension class for entity tables (TBox)
  SQLMappedClass:
    class_uri: vg:SQLMappedClass
    description: "Extension for classes that map to SQL tables"
    attributes:
      table:
        range: string
        description: "SQL table name"
      primary_key:
        range: string
        description: "Primary key column"
      identifier:
        range: string
        multivalued: true
        description: "Natural key columns"
      soft_delete_column:
        range: string
        description: "Soft delete timestamp column"
      row_count:
        range: integer
        description: "Estimated row count"

  # Extension class for relationships (RBox)
  SQLMappedRelationship:
    class_uri: vg:SQLMappedRelationship
    description: "Extension for classes representing relationships"
    attributes:
      # SQL mapping
      edge_table:
        range: string
        description: "Edge/junction table name"
      domain_key:
        range: string
        description: "FK column pointing to domain"
      range_key:
        range: string
        description: "FK column pointing to range"
      domain_class:
        range: string
        description: "Domain class name"
      range_class:
        range: string
        description: "Range class name"

      # Traversal
      traversal_complexity:
        range: TraversalComplexity
        description: "GREEN/YELLOW/RED complexity"

      # OWL 2 axioms
      transitive:
        range: boolean
      symmetric:
        range: boolean
      asymmetric:
        range: boolean
      reflexive:
        range: boolean
      irreflexive:
        range: boolean
      functional:
        range: boolean
      inverse_functional:
        range: boolean

      # Virtual Graph extensions
      acyclic:
        range: boolean
        description: "DAG constraint"
      is_hierarchical:
        range: boolean
      is_weighted:
        range: boolean
      inverse_of:
        range: string
        description: "Name of inverse relationship"

      # Cardinality
      cardinality_domain:
        range: string
        description: "e.g., '0..*'"
      cardinality_range:
        range: string

      # DDL metadata
      has_self_ref_constraint:
        range: boolean
      has_unique_edge_index:
        range: boolean
      indexed_columns:
        range: string
        multivalued: true

      # Weight columns for RED complexity
      weight_columns:
        range: WeightColumn
        multivalued: true
        inlined_as_list: true

      row_count:
        range: integer

  WeightColumn:
    class_uri: vg:WeightColumn
    attributes:
      name:
        range: string
        required: true
      type:
        range: string
        required: true

enums:
  TraversalComplexity:
    permissible_values:
      GREEN:
        description: "Simple FK join, direct SQL"
      YELLOW:
        description: "Recursive traversal, uses traverse() handler"
      RED:
        description: "Network algorithm, uses NetworkX"
```

## Phase 2: Migrate Supply Chain Ontology

Convert `supply_chain.yaml` to LinkML format:

```yaml
id: https://virt-graph.dev/schemas/supply_chain
name: supply_chain
version: "2.1"
prefixes:
  linkml: https://w3id.org/linkml/
  vg: https://virt-graph.dev/
  sc: https://virt-graph.dev/schemas/supply_chain/

imports:
  - linkml:types
  - virt_graph  # Our metamodel extension

default_range: string

# Database connection (as schema-level annotation)
annotations:
  vg:database_type: postgresql
  vg:database_version: "14"
  vg:connection_string: "postgresql://virt_graph:dev_password@localhost:5432/supply_chain"

classes:
  # ============================================================
  # ENTITY CLASSES (TBox)
  # ============================================================

  Supplier:
    description: "Organizations that supply parts and materials, organized in tiers (1-3)"
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: suppliers
      vg:primary_key: id
      vg:identifier: "[supplier_code]"
      vg:soft_delete_column: deleted_at
      vg:row_count: 500
    attributes:
      supplier_code:
        range: string
        required: true
        description: "Unique supplier identifier"
      name:
        range: string
        required: true
        description: "Supplier company name"
      tier:
        range: integer
        required: true
        description: "Supply chain tier (1=direct, 2=tier2, 3=raw materials)"
        annotations:
          vg:allowed_values: "[1, 2, 3]"
      country:
        range: string
      city:
        range: string
      contact_email:
        range: string
      credit_rating:
        range: string
      is_active:
        range: boolean
      created_at:
        range: datetime
      updated_at:
        range: datetime

  Part:
    description: "Physical components and raw materials used in manufacturing"
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: parts
      vg:primary_key: id
      vg:identifier: "[part_number]"
      vg:soft_delete_column: deleted_at
      vg:row_count: 5003
    attributes:
      part_number:
        range: string
        required: true
      description:
        range: string
      category:
        range: string
      unit_cost:
        range: decimal
      weight_kg:
        range: decimal
      lead_time_days:
        range: integer
      is_critical:
        range: boolean
      min_stock_level:
        range: integer

  # ... (other entity classes: Product, Facility, Customer, Order, Shipment, SupplierCertification)

  # ============================================================
  # RELATIONSHIP CLASSES (RBox)
  # ============================================================

  SuppliesTo:
    description: "Supplier sells to another supplier (tiered supply network)"
    instantiates:
      - vg:SQLMappedRelationship
    annotations:
      # SQL mapping
      vg:edge_table: supplier_relationships
      vg:domain_key: seller_id
      vg:range_key: buyer_id
      vg:domain_class: Supplier
      vg:range_class: Supplier

      # Traversal
      vg:traversal_complexity: YELLOW

      # OWL 2 axioms
      vg:asymmetric: true
      vg:irreflexive: true
      vg:acyclic: true
      vg:is_hierarchical: true

      # Cardinality
      vg:cardinality_domain: "0..*"
      vg:cardinality_range: "0..*"

      # DDL metadata
      vg:has_self_ref_constraint: true
      vg:has_unique_edge_index: true
      vg:indexed_columns: "[seller_id, buyer_id]"

      vg:row_count: 817
    attributes:
      relationship_type:
        range: string
      contract_start_date:
        range: date
      contract_end_date:
        range: date
      is_primary:
        range: boolean

  ComponentOf:
    description: "Part is a component of another part (BOM hierarchy)"
    instantiates:
      - vg:SQLMappedRelationship
    annotations:
      vg:edge_table: bill_of_materials
      vg:domain_key: child_part_id
      vg:range_key: parent_part_id
      vg:domain_class: Part
      vg:range_class: Part
      vg:traversal_complexity: YELLOW
      vg:asymmetric: true
      vg:irreflexive: true
      vg:acyclic: true
      vg:inverse_of: HasComponent
      vg:cardinality_domain: "0..*"
      vg:cardinality_range: "0..*"
      vg:has_self_ref_constraint: true
      vg:has_unique_edge_index: true
      vg:row_count: 14283
    attributes:
      quantity:
        range: integer
      unit:
        range: string
      is_optional:
        range: boolean
      assembly_sequence:
        range: integer

  ConnectsTo:
    description: "Transport route connects two facilities"
    instantiates:
      - vg:SQLMappedRelationship
    annotations:
      vg:edge_table: transport_routes
      vg:domain_key: origin_facility_id
      vg:range_key: destination_facility_id
      vg:domain_class: Facility
      vg:range_class: Facility
      vg:traversal_complexity: RED
      vg:irreflexive: true
      vg:is_weighted: true
      vg:cardinality_domain: "0..*"
      vg:cardinality_range: "0..*"
      vg:has_self_ref_constraint: true
      vg:row_count: 197
      # Weight columns as JSON array
      vg:weight_columns: '[{"name": "distance_km", "type": "decimal"}, {"name": "cost_usd", "type": "decimal"}, {"name": "transit_time_hours", "type": "decimal"}]'
    attributes:
      transport_mode:
        range: string
      distance_km:
        range: decimal
      cost_usd:
        range: decimal
      transit_time_hours:
        range: decimal
      capacity_tons:
        range: decimal
      is_active:
        range: boolean

  # ... (other relationship classes: Provides, CanSupply, etc.)
```

## Phase 3: Update OntologyAccessor

Modify `src/virt_graph/ontology.py` to:

1. Read LinkML format
2. Maintain backward-compatible API
3. Derive TBox/RBox views programmatically
4. **Validate VG-specific annotations** (since LinkML's `instantiates` validation is not yet implemented)

### Background: Why Custom Validation?

Per [LinkML documentation](https://linkml.io/linkml/schemas/annotations.html):

> "this is not yet supported in the current LinkML validator, so using `instantiates` indicates your intent, but does not yet enforce validation."

This means:
- `linkml-lint --validate-only` validates **schema structure** (valid YAML, correct LinkML syntax)
- But it does **NOT** validate that classes with `instantiates: [vg:SQLMappedClass]` have the required VG annotations

We must implement custom validation in `OntologyAccessor` to enforce VG annotation requirements.

### Implementation

```python
"""
Ontology accessor for LinkML format with Virtual Graph extensions.

Provides a stable API abstracting over the LinkML structure,
presenting logical TBox (classes) and RBox (roles) views.

Includes custom validation for VG-specific annotations since LinkML's
`instantiates` validation is not yet implemented.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class ValidationError:
    """A validation error for a schema element."""
    element_type: str  # "class" or "relationship"
    element_name: str
    field: str
    message: str

    def __str__(self):
        return f"{self.element_type} '{self.element_name}': {self.field} - {self.message}"


class OntologyValidationError(Exception):
    """Raised when ontology fails VG annotation validation."""
    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        message = f"Ontology validation failed with {len(errors)} error(s):\n"
        message += "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


class OntologyAccessor:
    """
    Abstraction layer for LinkML ontology with VG extensions.

    Automatically distinguishes:
    - Entity classes (instantiates vg:SQLMappedClass) → TBox
    - Relationship classes (instantiates vg:SQLMappedRelationship) → RBox

    Validates VG-specific annotations on construction.
    """

    VG_ENTITY = "vg:SQLMappedClass"
    VG_RELATIONSHIP = "vg:SQLMappedRelationship"

    # Required annotations for each extension type
    ENTITY_REQUIRED = {"table", "primary_key"}
    RELATIONSHIP_REQUIRED = {
        "edge_table", "domain_key", "range_key",
        "domain_class", "range_class", "traversal_complexity"
    }
    VALID_COMPLEXITIES = {"GREEN", "YELLOW", "RED"}

    def __init__(self, ontology_path: Optional[Path] = None, validate: bool = True):
        """
        Load and optionally validate a LinkML ontology with VG extensions.

        Args:
            ontology_path: Path to ontology YAML file
            validate: If True, validate VG annotations on load (default: True)

        Raises:
            OntologyValidationError: If validation is enabled and fails
        """
        if ontology_path is None:
            ontology_path = (
                Path(__file__).parent.parent.parent / "ontology" / "supply_chain.yaml"
            )
        with open(ontology_path) as f:
            self._data = yaml.safe_load(f)

        # Build TBox/RBox indices
        self._tbox = {}
        self._rbox = {}
        self._index_classes()

        # Validate VG annotations
        if validate:
            errors = self.validate()
            if errors:
                raise OntologyValidationError(errors)

    def _index_classes(self):
        """Partition classes into TBox (entities) and RBox (relationships)."""
        for name, cls in self._data.get("classes", {}).items():
            instantiates = cls.get("instantiates", [])
            if self.VG_RELATIONSHIP in instantiates:
                self._rbox[name] = cls
            elif self.VG_ENTITY in instantiates:
                self._tbox[name] = cls
            # Classes without VG instantiates are ignored or could be base classes

    def _get_annotation(self, cls: dict, key: str, default=None):
        """Get a vg: annotation value."""
        annotations = cls.get("annotations", {})
        # Try with vg: prefix first, then without
        return annotations.get(f"vg:{key}", annotations.get(key, default))

    def _get_all_annotations(self, cls: dict) -> set[str]:
        """Get all annotation keys (stripped of vg: prefix)."""
        annotations = cls.get("annotations", {})
        result = set()
        for key in annotations:
            if key.startswith("vg:"):
                result.add(key[3:])  # Strip vg: prefix
            else:
                result.add(key)
        return result

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate(self) -> list[ValidationError]:
        """
        Validate VG-specific annotations for all classes.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        errors.extend(self._validate_entities())
        errors.extend(self._validate_relationships())
        return errors

    def _validate_entities(self) -> list[ValidationError]:
        """Validate SQLMappedClass annotations."""
        errors = []
        for name, cls in self._tbox.items():
            present = self._get_all_annotations(cls)
            missing = self.ENTITY_REQUIRED - present
            for field in missing:
                errors.append(ValidationError(
                    element_type="class",
                    element_name=name,
                    field=field,
                    message=f"required annotation 'vg:{field}' is missing"
                ))
        return errors

    def _validate_relationships(self) -> list[ValidationError]:
        """Validate SQLMappedRelationship annotations."""
        errors = []
        for name, cls in self._rbox.items():
            present = self._get_all_annotations(cls)

            # Check required fields
            missing = self.RELATIONSHIP_REQUIRED - present
            for field in missing:
                errors.append(ValidationError(
                    element_type="relationship",
                    element_name=name,
                    field=field,
                    message=f"required annotation 'vg:{field}' is missing"
                ))

            # Validate traversal_complexity value
            complexity = self._get_annotation(cls, "traversal_complexity")
            if complexity and complexity not in self.VALID_COMPLEXITIES:
                errors.append(ValidationError(
                    element_type="relationship",
                    element_name=name,
                    field="traversal_complexity",
                    message=f"invalid value '{complexity}', must be one of {self.VALID_COMPLEXITIES}"
                ))

            # Validate domain_class references a known entity
            domain_class = self._get_annotation(cls, "domain_class")
            if domain_class and domain_class not in self._tbox:
                errors.append(ValidationError(
                    element_type="relationship",
                    element_name=name,
                    field="domain_class",
                    message=f"references unknown class '{domain_class}'"
                ))

            # Validate range_class references a known entity
            range_class = self._get_annotation(cls, "range_class")
            if range_class and range_class not in self._tbox:
                errors.append(ValidationError(
                    element_type="relationship",
                    element_name=name,
                    field="range_class",
                    message=f"references unknown class '{range_class}'"
                ))

        return errors

    # =========================================================================
    # TBox: Classes (Entity Tables)
    # =========================================================================

    @property
    def classes(self) -> dict:
        return self._tbox

    def get_class_table(self, name: str) -> str:
        return self._get_annotation(self._tbox[name], "table")

    def get_class_pk(self, name: str) -> str:
        return self._get_annotation(self._tbox[name], "primary_key")

    def get_class_identifier(self, name: str) -> list[str]:
        """Get natural key columns (may be JSON string or list)."""
        value = self._get_annotation(self._tbox[name], "identifier", [])
        if isinstance(value, str):
            # Handle JSON array string: "[col1, col2]"
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [value]
        return value

    def get_class_soft_delete_column(self, name: str) -> Optional[str]:
        return self._get_annotation(self._tbox[name], "soft_delete_column")

    def get_class_row_count(self, name: str) -> Optional[int]:
        return self._get_annotation(self._tbox[name], "row_count")

    # =========================================================================
    # RBox: Roles (Relationships)
    # =========================================================================

    @property
    def roles(self) -> dict:
        return self._rbox

    def get_role_table(self, name: str) -> str:
        return self._get_annotation(self._rbox[name], "edge_table")

    def get_role_keys(self, name: str) -> tuple[str, str]:
        cls = self._rbox[name]
        return (
            self._get_annotation(cls, "domain_key"),
            self._get_annotation(cls, "range_key")
        )

    def get_role_domain_class(self, name: str) -> str:
        return self._get_annotation(self._rbox[name], "domain_class")

    def get_role_range_class(self, name: str) -> str:
        return self._get_annotation(self._rbox[name], "range_class")

    def get_role_complexity(self, name: str) -> str:
        return self._get_annotation(self._rbox[name], "traversal_complexity")

    def get_role_row_count(self, name: str) -> Optional[int]:
        return self._get_annotation(self._rbox[name], "row_count")

    # OWL 2 axiom getters
    def is_role_transitive(self, name: str) -> bool:
        return self._get_annotation(self._rbox[name], "transitive", False)

    def is_role_symmetric(self, name: str) -> bool:
        return self._get_annotation(self._rbox[name], "symmetric", False)

    def is_role_asymmetric(self, name: str) -> bool:
        return self._get_annotation(self._rbox[name], "asymmetric", False)

    def is_role_acyclic(self, name: str) -> bool:
        return self._get_annotation(self._rbox[name], "acyclic", False)

    def is_role_weighted(self, name: str) -> bool:
        return self._get_annotation(self._rbox[name], "is_weighted", False)

    def get_role_weight_columns(self, name: str) -> list[dict]:
        """Get weight columns (may be JSON string or list)."""
        value = self._get_annotation(self._rbox[name], "weight_columns", [])
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return value

    def get_role_inverse(self, name: str) -> Optional[str]:
        return self._get_annotation(self._rbox[name], "inverse_of")

    # =========================================================================
    # Schema-level metadata
    # =========================================================================

    @property
    def name(self) -> str:
        return self._data.get("name", "unknown")

    @property
    def version(self) -> str:
        return self._data.get("version", "0.0")

    @property
    def database(self) -> dict:
        """Get database connection info from schema annotations."""
        annotations = self._data.get("annotations", {})
        return {
            "type": annotations.get("vg:database_type", "postgresql"),
            "version": annotations.get("vg:database_version"),
            "connection": annotations.get("vg:connection_string"),
        }
```

### Validation Behavior

The `OntologyAccessor` validates on construction by default:

```python
# This will raise OntologyValidationError if validation fails
ontology = OntologyAccessor()

# Skip validation (e.g., for partial schemas during development)
ontology = OntologyAccessor(validate=False)

# Validate manually and handle errors
ontology = OntologyAccessor(validate=False)
errors = ontology.validate()
if errors:
    for e in errors:
        print(f"  - {e}")
```

### Error Messages

Example validation errors:

```
OntologyValidationError: Ontology validation failed with 3 error(s):
  - class 'Supplier': table - required annotation 'vg:table' is missing
  - relationship 'SuppliesTo': domain_class - references unknown class 'Supplir'
  - relationship 'ConnectsTo': traversal_complexity - invalid value 'BLUE', must be one of {'GREEN', 'YELLOW', 'RED'}
```

### Two-Layer Validation Strategy

1. **LinkML Schema Validation** (structure):
   ```bash
   poetry run linkml-lint --validate-only ontology/supply_chain.yaml
   ```
   - Validates YAML syntax
   - Validates LinkML schema structure (classes, attributes, etc.)
   - Does NOT validate VG-specific annotations

2. **VG Annotation Validation** (semantics):
   ```python
   from virt_graph.ontology import OntologyAccessor
   ontology = OntologyAccessor()  # Raises if invalid
   ```
   - Validates required VG annotations are present
   - Validates traversal_complexity values
   - Validates domain_class/range_class references

## Phase 4: Update Discovery Protocol

Rewrite `prompts/ontology_discovery.md` to be:

1. **Database-agnostic** - parameterized connection string
2. **LinkML-native** - outputs valid LinkML YAML
3. **Validation-integrated** - runs `linkml-validate` at end

Key changes:

```markdown
# Ontology Discovery Protocol (LinkML)

## Session Setup

**Database**: `{{connection_string}}`  # Parameterized
**Output**: `ontology/{{schema_name}}.yaml`
**Metamodel**: `ontology/virt_graph.yaml`
**Validation**: `linkml-validate -s ontology/virt_graph.yaml ontology/{{schema_name}}.yaml`

## Round 1: Schema Introspection
(unchanged - query information_schema)

## Round 2: Entity Class Discovery (was "TBox")

For each entity table, generate a LinkML class:

```yaml
ClassName:
  description: "..."
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: table_name
    vg:primary_key: id
    vg:identifier: "[natural_key]"
    vg:row_count: N
  attributes:
    column_name:
      range: string|integer|decimal|boolean|date|datetime
      required: true|false
```

## Round 3: Relationship Class Discovery (was "RBox")

For each FK relationship, generate a LinkML class:

```yaml
RelationshipName:
  description: "..."
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: junction_table
    vg:domain_key: fk_column
    vg:range_key: id
    vg:domain_class: SourceClass
    vg:range_class: TargetClass
    vg:traversal_complexity: GREEN|YELLOW|RED
    # OWL 2 axioms...
  attributes:
    # Edge properties if any
```

## Round 4: Validate & Finalize

1. Write complete ontology to `ontology/{{schema_name}}.yaml`
2. Run validation:
   ```bash
   poetry run linkml-validate -s ontology/virt_graph.yaml ontology/{{schema_name}}.yaml
   ```
3. Fix any validation errors
4. Run gate tests
```

## Phase 5: Add LinkML Dependency & Tooling

### pyproject.toml

```toml
dependencies = [
    # ... existing ...
    "linkml>=1.7",
]
```

### Makefile / Scripts

```bash
# Validate ontology
validate-ontology:
    poetry run linkml-validate -s ontology/virt_graph.yaml ontology/supply_chain.yaml

# Generate JSON-Schema (for external tools)
gen-jsonschema:
    poetry run gen-json-schema ontology/supply_chain.yaml > ontology/schemas/supply_chain.schema.json

# Generate SQL DDL (reference)
gen-sql:
    poetry run gen-sqla ontology/supply_chain.yaml > ontology/schemas/supply_chain.sql
```

## Phase 6: Update Tests

Add LinkML validation to gate tests:

```python
# tests/test_gate2_validation.py

def test_ontology_linkml_valid():
    """Ontology must pass LinkML validation."""
    from linkml.validator import validate

    # Load schema
    schema_path = Path("ontology/supply_chain.yaml")
    metamodel_path = Path("ontology/virt_graph.yaml")

    # Validate
    result = subprocess.run(
        ["poetry", "run", "linkml-validate", "-s", str(metamodel_path), str(schema_path)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"LinkML validation failed: {result.stderr}"
```

## Migration Checklist

### Phase 1: Metamodel Extension ✅ COMPLETE
- [x] Create `ontology/virt_graph.yaml` with SQLMappedClass and SQLMappedRelationship
- [x] Test metamodel is valid LinkML: `linkml-lint --validate-only ontology/virt_graph.yaml`
- [x] Add `linkml>=1.7` to dependencies
- [x] Update Python requirement to `>=3.12,<4.0`

### Phase 2: Migrate Supply Chain ✅ COMPLETE
- [x] Convert `supply_chain.yaml` to LinkML format
- [x] Preserve all existing data (row counts, DDL annotations, etc.)
- [x] Validate structure: `linkml-lint --validate-only ontology/supply_chain.yaml`
- [x] Update TEMPLATE.yaml to LinkML format
- [x] Archive old TBox/RBox format to `archive/supply_chain_tbox_rbox.yaml`

### Phase 3: Update OntologyAccessor ✅ COMPLETE
- [x] Modify `src/virt_graph/ontology.py` to read LinkML format
- [x] Implement custom VG annotation validation (see Phase 3 docs above)
- [x] Add `ValidationError` and `OntologyValidationError` classes
- [x] Maintain backward-compatible API (snake_case role aliases)
- [x] All existing tests pass

### Phase 4: Update Discovery Protocol ✅ COMPLETE
- [x] Rewrite `prompts/ontology_discovery.md` for LinkML output
- [x] Make database-agnostic (parameterized: `{{connection_string}}`, `{{schema_name}}`)
- [x] Add two-layer validation step (linkml-lint + OntologyAccessor)

### Phase 5: Tooling ✅ COMPLETE
- [x] Add `linkml>=1.7` to dependencies (done in Phase 1)
- [x] Create validation scripts (Makefile targets)
- [x] Update CLAUDE.md with new commands

### Phase 6: Tests & Documentation ✅ COMPLETE
- [x] Add LinkML structure validation test (`linkml-lint`)
- [x] Add VG annotation validation test (`OntologyAccessor.validate()`)
- [x] Update docs/
- [x] Archive old TBox/RBox format files to `archive/`

## Rollback Plan

If issues arise:
1. Keep `ontology/supply_chain.yaml.bak` (original format)
2. OntologyAccessor can detect format version and handle both
3. Discovery prompt has both templates available

## Success Criteria

1. `linkml-validate` passes on all ontology files
2. All existing tests pass (API unchanged)
3. Discovery protocol produces valid LinkML for any PostgreSQL database
4. TBox/RBox views derivable from LinkML schema
