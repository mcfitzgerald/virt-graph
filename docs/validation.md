# Ontology Validation

VG/SQL uses multi-layer validation to ensure ontologies are structurally correct (valid LinkML), semantically complete (all VG requirements met), and consistent with the live database.

## Validation Layers

| Layer | Tool | What It Checks |
|-------|------|----------------|
| 1. Structure | `linkml-lint` | YAML syntax, LinkML schema rules |
| 2. Semantics | `OntologyAccessor` | VG annotations, complexity values, class references |
| 3. Schema Match | `validate_schema_match.py` | Ontology vs live database consistency |

All layers should pass for an ontology to be considered valid.

## Quick Validation

### Full Validation (Layers 1 + 2)

```bash
poetry run python scripts/validate_ontology.py --all
```

Or specify a file:

```bash
poetry run python scripts/validate_ontology.py pcg_example/ontology/pcg.yaml
```

### Layer 1 Only (LinkML Structure)

```bash
poetry run linkml-lint --validate-only ontology/my_domain.yaml
```

### Layer 2 Only (VG Annotations)

```bash
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

The `OntologyAccessor` validates VG-specific requirements by reading rules from the metamodel (`virt_graph.yaml` at project root).

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

## Schema Match Validation (Layer 3)

Cross-reference the ontology against a live PostgreSQL database:

```bash
poetry run python scripts/validate_schema_match.py pcg_example/ontology/pcg.yaml
poetry run python scripts/validate_schema_match.py --all
```

### What It Checks

| Check | Ontology Source | Database Source |
|-------|----------------|----------------|
| Table exists | `vg:table` per class | `information_schema.tables` |
| Columns exist | `attributes` block | `information_schema.columns` |
| Primary key matches | `vg:primary_key` | `table_constraints` + `key_column_usage` |
| FK existence | `vg:domain_key`/`vg:range_key` | `referential_constraints` |
| Row count plausibility | `vg:row_count` | `SELECT COUNT(*)` |

The script exits with code 0 on pass, 2 if the database is unavailable, and 1 on failure.

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
$ poetry run python scripts/validate_ontology.py pcg_example/ontology/pcg.yaml

Validating ontology: pcg_example/ontology/pcg.yaml

Layer 1: LinkML Structure
  Running: linkml-lint --validate-only pcg_example/ontology/pcg.yaml
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

Validation rules are not hardcoded in Python. They come from `virt_graph.yaml` (at project root):

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
poetry run pytest pcg_example/tests/ -v
```

## Validation Checklist

After creating or modifying an ontology:

- [ ] `poetry run python scripts/validate_ontology.py --all` passes
- [ ] All entity classes have `vg:table` and `vg:primary_key`
- [ ] All relationship classes have all six required annotations
- [ ] `operation_types` contains valid values (direct_join, recursive_traversal, etc.)
- [ ] `domain_class` and `range_class` reference existing entity classes
- [ ] `poetry run pytest pcg_example/tests/ -v` passes

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
poetry run python scripts/show_ontology.py
```

This displays the metamodel's required fields for SQLMappedClass and SQLMappedRelationship.

## Next Steps

- [Creating Ontologies](ontology-creation.md) - Step-by-step guide
- [VG Extensions](vg-extensions.md) - Complete annotation reference
- [Ontology System](ontology-system.md) - Core concepts and LinkML format
