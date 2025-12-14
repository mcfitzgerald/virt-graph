# Ontology Discovery Protocol (LinkML)

You are starting an interactive ontology discovery session. Follow the 4-round protocol below, pausing after each round for human review before proceeding.

**Begin with Round 1: Schema Introspection.**

---

## Session Setup

**Database**: `{{connection_string}}`
**Schema Name**: `{{schema_name}}`
**Output**: `ontology/{{schema_name}}.yaml`
**Metamodel**: `ontology/virt_graph.yaml` (single source of truth for extensions and validation rules)

**Validation** (two-layer):
1. Structure: `poetry run linkml-lint --validate-only ontology/{{schema_name}}.yaml`
2. Semantics: `OntologyAccessor("ontology/{{schema_name}}.yaml", validate=True)`

---

## Discovery Protocol (4 Rounds)

### Round 1: Schema Introspection

Query `information_schema` to discover:
- All tables with columns and data types
- Foreign key relationships
- Self-referential tables (where both FK columns point to same table)
- Check constraints (especially self-reference prevention)
- Unique constraints (natural key candidates)

**Pattern recognition**:
| Pattern | Interpretation |
|---------|----------------|
| `deleted_at` column | Soft delete enabled |
| `_id` suffix columns | Foreign keys |
| Two FKs to same table | Edge/relationship table |
| `is_active`, `status` columns | Entity state tracking |
| `code`, `number` unique columns | Natural key candidates |

Present findings as a table summary. **Pause for human review.**

---

### Round 2: Entity Class Discovery (TBox)

For each entity table, propose a LinkML class with `instantiates: [vg:SQLMappedClass]`.

> **Note**: Required and optional annotations are defined in `ontology/virt_graph.yaml` (SQLMappedClass).
> Validation rules are derived from the metamodel automatically.

**Required annotations** (as defined in virt_graph.yaml SQLMappedClass):
| Annotation | How to determine |
|------------|------------------|
| `vg:table` | SQL table name |
| `vg:primary_key` | Usually `id` |

**Optional annotations**:
| Annotation | How to determine |
|------------|------------------|
| `vg:identifier` | Natural key columns as JSON array: `"[code, name]"` |
| `vg:soft_delete_column` | Column name if `deleted_at` exists |
| `vg:row_count` | Query `COUNT(*)` |

**Attribute ranges**: `string`, `integer`, `decimal`, `boolean`, `date`, `datetime`

**Output format** for each entity:

```yaml
ClassName:
  description: "Human-readable description"
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: table_name
    vg:primary_key: id
    vg:identifier: "[natural_key]"
    vg:soft_delete_column: deleted_at
    vg:row_count: 1000
  attributes:
    column_name:
      range: string
      required: true
      description: "Column description"
```

Present class proposals as a structured list. **Pause for human corrections.**

---

### Round 3: Relationship Class Discovery (RBox)

For each FK relationship, propose a LinkML class with `instantiates: [vg:SQLMappedRelationship]`.

> **Note**: Required and optional annotations are defined in `ontology/virt_graph.yaml` (SQLMappedRelationship).
> Valid `traversal_complexity` values (GREEN, YELLOW, RED) come from the TraversalComplexity enum in the metamodel.

**Required annotations** (as defined in virt_graph.yaml SQLMappedRelationship):
| Annotation | How to determine |
|------------|------------------|
| `vg:edge_table` | Table containing the FK (or junction table) |
| `vg:domain_key` | FK column name |
| `vg:range_key` | Target column (usually `id` of target table) |
| `vg:domain_class` | Class name of source entity |
| `vg:range_class` | Class name of target entity |
| `vg:traversal_complexity` | See complexity rules below |

**Complexity rules**:
| Pattern | Complexity | Reason |
|---------|------------|--------|
| Simple FK join (A → B) | GREEN | Direct SQL query |
| Self-referential (A → A) | YELLOW | Requires recursive BFS traversal |
| Self-referential + weight columns | RED | Requires NetworkX algorithms |

**Optional annotations**:

*OWL 2 Role Axioms*:
| Annotation | When to set |
|------------|-------------|
| `vg:transitive` | R(x,y) ∧ R(y,z) → R(x,z) |
| `vg:symmetric` | R(x,y) → R(y,x) |
| `vg:asymmetric` | R(x,y) → ¬R(y,x) |
| `vg:reflexive` | R(x,x) always valid |
| `vg:irreflexive` | R(x,x) never valid (no self-loops) |
| `vg:functional` | At most one target per source |
| `vg:inverse_functional` | At most one source per target |

*Virtual Graph Extensions*:
| Annotation | When to set |
|------------|-------------|
| `vg:acyclic` | Graph has no cycles (DAG) |
| `vg:is_hierarchical` | Has tier/level structure |
| `vg:is_weighted` | Has numeric edge weight columns |
| `vg:inverse_of` | Name of inverse relationship |

*Cardinality*:
| Annotation | Values |
|------------|--------|
| `vg:cardinality_domain` | "1..1", "0..1", "1..*", "0..*" |
| `vg:cardinality_range` | "1..1", "0..1", "1..*", "0..*" |

*DDL Metadata*:
| Annotation | When to set |
|------------|-------------|
| `vg:has_self_ref_constraint` | CHECK constraint prevents domain_key = range_key |
| `vg:has_unique_edge_index` | UNIQUE index on (domain_key, range_key) |
| `vg:indexed_columns` | JSON array of indexed columns |

*Weight Columns* (for RED complexity):
| Annotation | Format |
|------------|--------|
| `vg:weight_columns` | JSON array: `'[{"name": "distance", "type": "decimal"}]'` |

*Statistics*:
| Annotation | How to determine |
|------------|------------------|
| `vg:row_count` | Query `COUNT(*)` on edge table |

**Property hints for self-referential tables**:
- Almost always: `asymmetric: true`, `irreflexive: true`
- For DAG structures (hierarchies, BOMs): `acyclic: true`
- For tiered structures: `is_hierarchical: true`
- For weighted graphs: `is_weighted: true` + `weight_columns`

**Output format** for each relationship:

```yaml
RelationshipName:
  description: "Human-readable description"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    # Required
    vg:edge_table: junction_table
    vg:domain_key: source_id
    vg:range_key: target_id
    vg:domain_class: SourceClass
    vg:range_class: TargetClass
    vg:traversal_complexity: YELLOW
    # OWL 2 axioms
    vg:asymmetric: true
    vg:irreflexive: true
    vg:acyclic: true
    # Cardinality
    vg:cardinality_domain: "0..*"
    vg:cardinality_range: "0..*"
    # DDL metadata
    vg:has_self_ref_constraint: true
    vg:has_unique_edge_index: true
    vg:indexed_columns: "[source_id, target_id]"
    # Statistics
    vg:row_count: 5000
  attributes:
    # Edge properties (if any)
    weight:
      range: decimal
      description: "Edge weight"
```

Present role proposals. **Pause for human corrections.**

---

### Round 4: Draft, Validate & Finalize

1. **Write complete ontology** to `ontology/{{schema_name}}.yaml`
   - Follow the metamodel in `ontology/virt_graph.yaml` (defines SQLMappedClass, SQLMappedRelationship)
   - Include schema header with metadata:
     ```yaml
     id: https://virt-graph.dev/schemas/{{schema_name}}
     name: {{schema_name}}
     version: "1.0"
     description: >-
       {{schema_name}} domain ontology for Virtual Graph.
       Generated via 4-round interactive discovery protocol.

     prefixes:
       linkml: https://w3id.org/linkml/
       vg: https://virt-graph.dev/

     imports:
       - linkml:types

     default_range: string

     annotations:
       vg:database_type: postgresql
       vg:database_version: "14"
       vg:connection_string: "{{connection_string}}"
     ```
   - Include all row counts from queries
   - Group classes: Entity Classes (TBox) first, then Relationship Classes (RBox)

2. **Two-layer validation**:

   **Layer 1 - LinkML Structure** (validates YAML/schema syntax):
   ```bash
   poetry run linkml-lint --validate-only ontology/{{schema_name}}.yaml
   ```
   - Validates YAML syntax is correct
   - Validates LinkML schema structure (classes, attributes, etc.)
   - Does NOT validate VG-specific annotation requirements

   **Layer 2 - VG Annotations** (validates semantic requirements):
   ```python
   from virt_graph.ontology import OntologyAccessor

   # This raises OntologyValidationError if validation fails
   ontology = OntologyAccessor(Path("ontology/{{schema_name}}.yaml"))

   # Or validate manually and inspect errors:
   ontology = OntologyAccessor(Path("ontology/{{schema_name}}.yaml"), validate=False)
   errors = ontology.validate()
   for e in errors:
       print(f"  - {e}")
   ```
   - Validates required VG annotations are present
   - Validates `traversal_complexity` values are GREEN/YELLOW/RED
   - Validates `domain_class`/`range_class` reference valid entity classes

3. **Fix any validation errors** and re-validate

4. **Run gate tests**:
   ```bash
   poetry run pytest tests/test_gate2_validation.py -v
   ```

5. Human approves or requests changes

---

## Validation Checklist

After writing the ontology, validate:

- [ ] **LinkML lint passes**: `poetry run linkml-lint --validate-only ontology/{{schema_name}}.yaml`
- [ ] **VG annotations valid**: `OntologyAccessor(path, validate=True)` succeeds
- [ ] **Row counts verified**: Query actual counts, compare to `vg:row_count` fields
- [ ] **Referential integrity**: Check for orphaned FKs (`LEFT JOIN WHERE NULL`)
- [ ] **DAG validation**: For `vg:acyclic: true` roles, verify no cycles (recursive CTE with path tracking)
- [ ] **Weight ranges**: For `vg:is_weighted: true`, check weight columns have valid values
- [ ] **Gate tests pass**: `poetry run pytest tests/test_gate2_validation.py -v`

---

## Quick Reference

### Traversal Complexity Decision Tree

```
Is relationship self-referential (domain_class == range_class)?
├── No → GREEN (simple FK join)
└── Yes → Does it have numeric weight columns for optimization?
    ├── Yes → RED (network algorithms via NetworkX)
    └── No → YELLOW (recursive traversal via traverse())
```

### OWL 2 Properties Quick Reference

| Property | Definition | Symbol |
|----------|------------|--------|
| `transitive` | A→B, B→C implies A→C | R(x,y) ∧ R(y,z) → R(x,z) |
| `symmetric` | A→B implies B→A | R(x,y) → R(y,x) |
| `asymmetric` | A→B implies NOT B→A | R(x,y) → ¬R(y,x) |
| `reflexive` | A→A is valid | R(x,x) ⊤ |
| `irreflexive` | A→A is NOT valid | R(x,x) ⊥ |
| `functional` | At most one target per source | |
| `inverse_functional` | At most one source per target | |

### Virtual Graph Extensions

| Property | Meaning | Use Case |
|----------|---------|----------|
| `acyclic` | Graph has no cycles (DAG) | BOMs, hierarchies |
| `is_hierarchical` | Has tier/level structure | Supplier tiers |
| `is_weighted` | Has numeric edge weights | Transport routes |

### Cardinality Notation

| Notation | Meaning |
|----------|---------|
| `1..1` | Exactly one (required) |
| `0..1` | Zero or one (optional) |
| `1..*` | One or more |
| `0..*` | Zero or more |

### Type Mapping (SQL → LinkML)

| SQL Type | LinkML Range |
|----------|--------------|
| VARCHAR, TEXT, CHAR | `string` |
| INTEGER, BIGINT, SMALLINT | `integer` |
| NUMERIC, DECIMAL, REAL, DOUBLE | `decimal` |
| BOOLEAN | `boolean` |
| DATE | `date` |
| TIMESTAMP, TIMESTAMPTZ | `datetime` |

---

## Example: Starting a New Discovery Session

When given a new database connection, begin with:

```
I'll start the ontology discovery process for this database.

**Session Setup**
- Database: `postgresql://user:pass@host:5432/mydb`
- Schema Name: `mydb`
- Output: `ontology/mydb.yaml`

## Round 1: Schema Introspection

Let me query the information_schema to understand the database structure...
```

Then execute the appropriate SQL queries:

```sql
-- Tables and columns
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

-- Foreign keys
SELECT
    tc.table_name AS source_table,
    kcu.column_name AS source_column,
    ccu.table_name AS target_table,
    ccu.column_name AS target_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';

-- Check constraints
SELECT table_name, constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_schema = 'public';

-- Unique constraints
SELECT tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'UNIQUE';

-- Row counts
SELECT relname AS table_name, reltuples::bigint AS row_count
FROM pg_class
WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace;
```
