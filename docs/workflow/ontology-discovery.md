# Ontology Discovery

Ontology discovery is the first phase of the Virtual Graph workflow. It creates a semantic map from your database schema to business concepts.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ONTOLOGY DISCOVERY FLOW                       │
└─────────────────────────────────────────────────────────────────┘

    Round 1              Round 2              Round 3              Round 4
    ┌──────────┐        ┌──────────┐        ┌──────────┐        ┌──────────┐
    │ Schema   │   →    │ Entity   │   →    │ Relation │   →    │ Validate │
    │ Introspect│        │ Classes  │        │ Classes  │        │ & Write  │
    └──────────┘        └──────────┘        └──────────┘        └──────────┘
         │                   │                   │                    │
         ▼                   ▼                   ▼                    ▼
     [PAUSE]             [PAUSE]             [PAUSE]             [PAUSE]
     Human               Human               Human               Human
     Review              Review              Review              Approval
```

## Session Setup

Before starting, ensure you have:

- Database connection string
- Write access to `ontology/` directory
- Reference files:
  - `ontology/virt_graph.yaml` - Metamodel (defines annotations)
  - `ontology/TEMPLATE.yaml` - Template (copy for new ontologies)

```bash
# Start a fresh Claude session with the discovery protocol
cat prompts/ontology_discovery.md
```

## Round 1: Schema Introspection

Query `information_schema` to discover the database structure.

### What to Find

| Element | How to Find |
|---------|-------------|
| Tables & columns | `information_schema.columns` |
| Foreign keys | `information_schema.table_constraints` |
| Self-referential tables | FKs where both columns point to same table |
| Check constraints | `information_schema.check_constraints` |
| Unique constraints | Candidate natural keys |
| Row counts | `pg_class.reltuples` |

### Pattern Recognition

| Pattern | Interpretation |
|---------|----------------|
| `deleted_at` column | Soft delete enabled |
| `_id` suffix columns | Foreign keys |
| Two FKs to same table | Edge/relationship table |
| `is_active`, `status` | Entity state tracking |
| `code`, `number` unique | Natural key candidates |

### Example SQL Queries

```sql
-- Tables and columns
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

-- Foreign keys
SELECT
    tc.table_name AS source_table,
    kcu.column_name AS source_column,
    ccu.table_name AS target_table
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';

-- Row counts
SELECT relname AS table_name, reltuples::bigint AS row_count
FROM pg_class
WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace;
```

**Output**: Table summary with columns, FKs, and patterns identified.

**PAUSE**: Human reviews schema understanding before proceeding.

## Round 2: Entity Class Discovery (TBox)

For each entity table, propose a LinkML class.

### Required Annotations

| Annotation | Description |
|------------|-------------|
| `vg:table` | SQL table name |
| `vg:primary_key` | Primary key column (usually `id`) |

### Optional Annotations

| Annotation | When to Use |
|------------|-------------|
| `vg:identifier` | Natural key as JSON array: `"[code]"` |
| `vg:soft_delete_column` | If `deleted_at` exists |
| `vg:row_count` | From COUNT(*) query |

### Output Format

```yaml
Supplier:
  description: "Companies that provide materials/parts"
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: suppliers
    vg:primary_key: id
    vg:identifier: "[supplier_code]"
    vg:soft_delete_column: deleted_at
    vg:row_count: 500
  attributes:
    name:
      range: string
      required: true
    supplier_code:
      range: string
      required: true
```

**PAUSE**: Human reviews and corrects entity proposals.

## Round 3: Relationship Class Discovery (RBox)

For each FK relationship, propose a relationship class.

### Required Annotations

| Annotation | Description |
|------------|-------------|
| `vg:edge_table` | Table containing the FK |
| `vg:domain_key` | FK column name |
| `vg:range_key` | Target column (usually target table's PK) |
| `vg:domain_class` | Source entity class name |
| `vg:range_class` | Target entity class name |
| `vg:traversal_complexity` | GREEN, YELLOW, or RED |

### Complexity Assignment

```
Is the relationship self-referential (domain_class == range_class)?
├── No → GREEN (simple FK join)
└── Yes → Does it have numeric weight columns?
    ├── Yes → RED (network algorithms)
    └── No → YELLOW (recursive traversal)
```

### Optional Annotations

**OWL 2 Role Axioms**:

| Annotation | When to Set |
|------------|-------------|
| `vg:asymmetric` | A→B implies NOT B→A |
| `vg:irreflexive` | No self-loops (A→A invalid) |
| `vg:transitive` | A→B, B→C implies A→C |
| `vg:functional` | At most one target per source |

**Virtual Graph Extensions**:

| Annotation | When to Set |
|------------|-------------|
| `vg:acyclic` | Graph is a DAG (no cycles) |
| `vg:is_hierarchical` | Has tier/level structure |
| `vg:is_weighted` | Has numeric edge weights |

**Cardinality**:

| Annotation | Values |
|------------|--------|
| `vg:cardinality_domain` | "1..1", "0..1", "1..*", "0..*" |
| `vg:cardinality_range` | "1..1", "0..1", "1..*", "0..*" |

### Output Format

```yaml
SuppliesTo:
  description: "Supplier tier relationship"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    # Required
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id
    vg:range_key: buyer_id
    vg:domain_class: Supplier
    vg:range_class: Supplier
    vg:traversal_complexity: YELLOW
    # OWL 2 axioms
    vg:asymmetric: true
    vg:irreflexive: true
    vg:acyclic: true
    # Cardinality
    vg:cardinality_domain: "0..*"
    vg:cardinality_range: "0..*"
    # Statistics
    vg:row_count: 1500
```

**PAUSE**: Human reviews and corrects relationship proposals.

## Round 4: Validate & Finalize

### Write the Ontology

Create `ontology/{schema_name}.yaml` with:

```yaml
id: https://virt-graph.dev/schemas/{schema_name}
name: {schema_name}
version: "1.0"
description: >-
  {schema_name} domain ontology for Virtual Graph.

prefixes:
  linkml: https://w3id.org/linkml/
  vg: https://virt-graph.dev/

imports:
  - linkml:types

default_range: string

classes:
  # Entity Classes (TBox)
  Supplier:
    # ...

  # Relationship Classes (RBox)
  SuppliesTo:
    # ...
```

### Two-Layer Validation

**Layer 1: LinkML Structure**

```bash
poetry run linkml-lint --validate-only ontology/{schema_name}.yaml
```

Validates:
- YAML syntax
- LinkML schema structure
- Class and attribute definitions

**Layer 2: VG Annotations**

```python
from virt_graph.ontology import OntologyAccessor

# Validates on load (raises OntologyValidationError if invalid)
ontology = OntologyAccessor(Path("ontology/{schema_name}.yaml"))

# Or validate manually:
ontology = OntologyAccessor(path, validate=False)
errors = ontology.validate()
for e in errors:
    print(f"  - {e}")
```

Validates:
- Required VG annotations present
- `traversal_complexity` is GREEN/YELLOW/RED
- `domain_class`/`range_class` reference valid classes

### Run Gate Tests

```bash
poetry run pytest tests/test_gate2_validation.py -v
```

**PAUSE**: Human approves final ontology or requests changes.

## Validation Checklist

- [ ] LinkML lint passes
- [ ] VG annotation validation passes
- [ ] Row counts verified against actual
- [ ] Referential integrity checked
- [ ] DAG validation (for `acyclic: true` relationships)
- [ ] Gate tests pass

## Quick Reference

### Type Mapping (SQL → LinkML)

| SQL Type | LinkML Range |
|----------|--------------|
| VARCHAR, TEXT | `string` |
| INTEGER, BIGINT | `integer` |
| NUMERIC, DECIMAL | `decimal` |
| BOOLEAN | `boolean` |
| DATE | `date` |
| TIMESTAMP | `datetime` |

### Cardinality Notation

| Notation | Meaning |
|----------|---------|
| `1..1` | Exactly one (required) |
| `0..1` | Zero or one (optional) |
| `1..*` | One or more |
| `0..*` | Zero or more |

## Next Steps

Once ontology discovery is complete:

1. Verify with `make validate-ontology`
2. View definitions with `make show-ontology`
3. Proceed to [Pattern Discovery](pattern-discovery.md)
