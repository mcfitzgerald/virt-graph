# Ontology Validation

VG/SQL uses two-layer validation to ensure ontologies are both structurally correct (valid LinkML) and semantically complete (all VG requirements met).

## Two-Layer Validation

| Layer | Tool | What It Checks |
|-------|------|----------------|
| 1. Structure | `linkml-lint` | YAML syntax, LinkML schema rules |
| 2. Semantics | `OntologyAccessor` | VG annotations, complexity values, class references |

Both layers must pass for an ontology to be valid.

## Quick Validation

### Full Validation (Both Layers)

```bash
make validate-ontology
```

Or specify a file:

```bash
poetry run python scripts/validate_ontology.py ontology/my_domain.yaml
```

### Layer 1 Only (LinkML Structure)

```bash
make validate-linkml
# or
poetry run linkml-lint --validate-only ontology/my_domain.yaml
```

### Layer 2 Only (VG Annotations)

```bash
make validate-vg
# or
poetry run python scripts/validate_ontology.py --vg-only ontology/my_domain.yaml
```

## Layer 1: LinkML Structure

Uses the standard LinkML linter to validate:

- YAML syntax is correct
- Required LinkML fields are present (`id`, `name`, `classes`)
- Attribute ranges are valid types
- Class inheritance is valid
- Prefixes are properly defined

### Common Layer 1 Errors

**Invalid YAML syntax**:
```
Error: YAML parse error at line 15
```
Fix: Check indentation, colons, quotes.

**Missing required field**:
```
Error: 'id' is a required property
```
Fix: Add schema ID at top of file:
```yaml
id: https://example.com/schemas/my_domain
```

**Invalid range**:
```
Error: Unknown range 'String'
```
Fix: Use lowercase: `string`, `integer`, `decimal`, etc.

## Layer 2: VG Annotations

The `OntologyAccessor` validates VG-specific requirements by reading rules from the metamodel (`ontology/virt_graph.yaml`).

### What It Checks

**Entity Classes (SQLMappedClass)**:
- Required: `vg:table`, `vg:primary_key`
- Optional fields have correct types

**Relationship Classes (SQLMappedRelationship)**:
- Required: `vg:edge_table`, `vg:domain_key`, `vg:range_key`, `vg:domain_class`, `vg:range_class`, `vg:operation_types`
- `operation_types` contains valid operation type values
- `domain_class` and `range_class` reference existing entity classes

### Common Layer 2 Errors

**Missing required annotation**:
```
ValidationError: class 'Supplier' missing required annotation: vg:table
```
Fix: Add the annotation:
```yaml
annotations:
  vg:table: suppliers
```

**Invalid operation type**:
```
ValidationError: role 'SuppliesTo' has invalid operation_type: traverse
```
Fix: Use valid operation types:
```yaml
vg:operation_types: "[recursive_traversal, temporal_traversal]"
```

**Unknown class reference**:
```
ValidationError: role 'SuppliesTo' references unknown domain_class: supplier
```
Fix: Match the exact class name (case-sensitive):
```yaml
vg:domain_class: Supplier
```

## Programmatic Validation

### Validate on Load (Default)

```python
from virt_graph.ontology import OntologyAccessor

# Raises OntologyValidationError if invalid
ontology = OntologyAccessor("ontology/my_domain.yaml")
```

### Validate Manually

```python
from virt_graph.ontology import OntologyAccessor

# Load without validation
ontology = OntologyAccessor("ontology/my_domain.yaml", validate=False)

# Validate and get errors
errors = ontology.validate()

if errors:
    print(f"Found {len(errors)} validation errors:")
    for error in errors:
        print(f"  - [{error.element_type}] {error.element_name}: {error.message}")
else:
    print("Ontology is valid")
```

### ValidationError Structure

```python
@dataclass
class ValidationError:
    element_type: str    # "class" or "relationship"
    element_name: str    # Name of the class/relationship
    field: str          # Annotation name
    message: str        # Error description
```

## Validation Script

The `scripts/validate_ontology.py` script provides detailed output:

```bash
$ poetry run python scripts/validate_ontology.py ontology/supply_chain.yaml

Validating ontology: ontology/supply_chain.yaml

Layer 1: LinkML Structure
  Running: linkml-lint --validate-only ontology/supply_chain.yaml
  ✓ LinkML structure valid

Layer 2: VG Annotations
  Loading ontology...
  Checking entity classes (TBox)...
    ✓ Supplier
    ✓ Part
    ✓ Product
    ...
  Checking relationship classes (RBox)...
    ✓ SuppliesTo
    ✓ ComponentOf
    ...
  ✓ VG annotations valid

✓ Ontology is valid
```

## Single Source of Truth

Validation rules are not hardcoded in Python. They come from `ontology/virt_graph.yaml`:

```yaml
# From virt_graph.yaml
SQLMappedClass:
  description: "Base class for SQL-mapped entity classes"
  attributes:
    table:
      range: string
      required: true        # ← This makes vg:table required
    primary_key:
      range: string
      required: true        # ← This makes vg:primary_key required
    identifier:
      range: string
      required: false       # ← This is optional
```

If you need to add a new required annotation, add it to the metamodel. The validation will automatically enforce it.

## Running Validation Tests

VG/SQL includes tests that verify ontology validity as part of the test suite:

```bash
# Handler safety tests
poetry run pytest tests/test_handler_safety.py -v

# Ontology validation tests
poetry run pytest tests/test_ontology_validation.py -v

# All tests
make test
```

## Validation Checklist

After creating or modifying an ontology:

- [ ] `make validate-ontology` passes
- [ ] All entity classes have `vg:table` and `vg:primary_key`
- [ ] All relationship classes have all six required annotations
- [ ] `operation_types` contains valid values (direct_join, recursive_traversal, etc.)
- [ ] `domain_class` and `range_class` reference existing entity classes
- [ ] `make test` passes

## Debugging Tips

### See What OntologyAccessor Finds

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor("ontology/my_domain.yaml", validate=False)

# List all entity classes
print("Entity classes:")
for cls in ontology.tbox:
    print(f"  {cls['name']}: {cls.get('table', 'NO TABLE')}")

# List all relationship classes
print("\nRelationship classes:")
for role in ontology.rbox:
    op_types = ontology.get_operation_types(role['name'])
    print(f"  {role['name']}: {op_types}")
```

### Check Metamodel Requirements

```bash
make show-ontology
```

This displays the metamodel's required fields for SQLMappedClass and SQLMappedRelationship.

## Neo4j Graph Validation

After migrating data to Neo4j, use the graph validator to verify the structure matches the ontology:

```bash
# Validate against default ontology
make validate-neo4j

# Validate against custom ontology
poetry run python scripts/validate_neo4j.py path/to/ontology.yaml

# JSON output for CI
poetry run python scripts/validate_neo4j.py --json
```

### What It Checks

| Check | Description |
|-------|-------------|
| Node Labels | All ontology classes exist as Neo4j labels |
| Node Counts | Counts match `row_count` annotations (if present) |
| Relationship Types | All ontology roles exist as Neo4j relationship types |
| Relationship Endpoints | Domain/range match ontology declarations |
| Relationship Counts | Counts match `row_count` annotations (if present) |
| Constraints | Irreflexive (no self-loops), Asymmetric (no bidirectional) |

### Sample Output

```
Neo4j Graph Validation Report
==================================================
Ontology: supply_chain v1.0
Database: bolt://localhost:7687

Node Labels
--------------------------------------------------
  [pass] Supplier: Label 'Supplier' exists
  [pass] Part: Label 'Part' exists
  ...

Summary
--------------------------------------------------
Passed: 67/67 checks
[pass] All validations passed
```

## Next Steps

- [Creating Ontologies](creating-ontologies.md) - Step-by-step guide
- [VG Extensions](vg-extensions.md) - Complete annotation reference
- [LinkML Format](linkml-format.md) - LinkML basics
