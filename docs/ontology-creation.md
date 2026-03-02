# Creating Ontologies

VG/SQL ontologies are created through an interactive discovery process with Claude, then enriched through four additional phases. This guide covers the full lifecycle.

## Overview

```
Phase 1: Discovery Protocol (4 rounds)  → Structural ontology with entity/relationship classes
Phase 2: Complete FK Coverage            → Map all FKs, identify polymorphism, add context
Phase 3: Kinetic Enrichment              → State machines, flows, axioms, actions, scenario params
Phase 4: Structural Patterns             → Class hierarchy, mixins, enums, imports
Phase 5: Schema Validation               → Cross-reference ontology against live database
```

## Prerequisites

- PostgreSQL database running and accessible
- VG/SQL installed (`poetry install`)
- Claude Code session active

## Starting a Discovery Session

Tell Claude the database connection details:

```
Create an ontology for my database at postgresql://user:pass@localhost:5432/mydb
```

Claude will begin with Phase 1 automatically.

---

## Phase 1: Discovery Protocol

The core 4-round protocol introspects your database and generates the structural ontology.

### Round 1: Schema Introspection

Claude queries `information_schema` to discover tables, FKs, constraints, and patterns.

**SQL Introspection Queries:**

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

-- Check constraints (self-reference prevention, enums)
SELECT table_name, constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_schema = 'public';

-- Unique constraints (natural key candidates)
SELECT tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'UNIQUE';

-- Row counts (fast, from statistics)
SELECT relname AS table_name, reltuples::bigint AS row_count
FROM pg_class
WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace;
```

**Pattern Recognition:**

| Pattern | Interpretation |
|---------|----------------|
| `deleted_at` / `is_active` column | Soft delete enabled |
| `_id` suffix columns | Foreign keys |
| Two FKs to same table | Junction/edge table |
| `code`, `number` unique columns | Natural key candidates |
| `_type` suffix columns | Polymorphism discriminators |
| `status` column with CHECK constraint | State machine candidate |
| Self-referential FK (table → itself) | Recursive traversal candidate |

**Your input:** Review the table summary. Correct misunderstandings about which tables are domain entities vs. infrastructure.

### Round 2: Entity Discovery (TBox)

Claude proposes entity classes for each table:

```yaml
Supplier:
  description: "A supplier in the network"
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
    name:
      range: string
      required: true
```

**Your input:** Review class proposals — rename for clarity, exclude non-domain tables, add descriptions.

### Round 3: Relationship Discovery (RBox)

Claude proposes relationship classes for each FK. This is the most critical round.

**Operation Type Determination:**

| Pattern | Operation Types |
|---------|-----------------|
| Simple FK (A → B) | `direct_join` |
| Self-referential (A → A) | `recursive_traversal` |
| Self-referential + weights | `shortest_path`, `centrality`, etc. |
| Hierarchy with quantities | `path_aggregation`, `hierarchical_aggregation` |

**Example direct relationship:**

```yaml
OrderPlacedByCustomer:
  description: "Order placed by a customer"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: orders
    vg:domain_key: customer_id
    vg:range_key: id
    vg:domain_class: Order
    vg:range_class: Customer
    vg:operation_types: "[direct_join]"
    vg:functional: true
```

**SME Enrichment Questions** (for traversal/algorithm relationships):

1. **Inverse pairs**: "Do users need to traverse in both directions with distinct semantics?"
2. **Traversal semantics**: "What do inbound and outbound mean in business terms?"
3. **Transitivity**: "If A→B and B→C, does A→C hold?"
4. **Symmetry**: "If A→B, does B→A always hold?"

**Your input:** Review relationship proposals — correct operation types, add OWL 2 axioms.

### Round 4: Draft & Validate

Claude writes the complete ontology and runs two-layer validation.

**Layer 1 — LinkML Structure:**
```bash
poetry run linkml-lint --validate-only ontology/my_domain.yaml
```

**Layer 2 — VG Annotations:**
```python
from virt_graph.ontology import OntologyAccessor
from pathlib import Path

ontology = OntologyAccessor(Path("ontology/my_domain.yaml"), validate=True)
```

**Common validation errors:**

| Error | Fix |
|-------|-----|
| "Missing required annotation: vg:table" | Add `vg:table` to entity class |
| "Invalid operation_type: traverse" | Use `recursive_traversal` |
| "Unknown domain_class: supplier" | Match class name exactly: `Supplier` |

---

## Phase 2: Complete FK Coverage

After the initial 4 rounds, go back and ensure every FK column in the DDL is covered.

### Discover Unmapped FKs

Compare ontology relationships against actual FK constraints:

```sql
-- All FKs in the database
SELECT
    tc.table_name,
    kcu.column_name AS fk_column,
    ccu.table_name AS target_table,
    ccu.column_name AS target_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name;
```

Cross-reference against `vg:domain_key` and `vg:range_key` annotations in the ontology. Any FK not covered by a relationship class needs one.

### Identify Polymorphic Relationships

Look for FKs where the target depends on a discriminator column:

```sql
-- FKs where the source table also has a *_type column
SELECT
    tc.table_name,
    kcu.column_name AS fk_column,
    ccu.table_name AS target_table,
    c.column_name AS type_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON tc.constraint_name = ccu.constraint_name
JOIN information_schema.columns c
    ON c.table_name = tc.table_name
    AND c.column_name LIKE '%_type'
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;
```

For polymorphic relationships, add:
- `vg:range_class` as a JSON array of possible target classes
- `vg:type_discriminator` with column and value→class mapping

```yaml
vg:type_discriminator: >-
  {"column": "origin_type", "mapping": {"plant": "Plant", "dc": "DistributionCenter", "retail": "RetailLocation"}}
```

### Add Context Blocks

For complex entities and relationships, add `vg:context` to guide AI query generation:

```yaml
vg:context: >-
  {
    "business_logic": "Batches represent a single production run...",
    "llm_prompt_hint": "When querying batches, always consider the product_type discriminator...",
    "traversal_semantics": {
      "inbound": "What inputs went into this batch?",
      "outbound": "What products did this batch produce?"
    }
  }
```

Context blocks are especially valuable for:
- Entities with non-obvious semantics
- Polymorphic relationships (explain when each target type applies)
- Relationships without clean FK constraints (explain join logic)
- Edge cases in the domain model

### Add Edge Attributes

For junction tables with meaningful columns beyond the FK pair:

```yaml
vg:edge_attributes: >-
  [
    {"name": "quantity_kg", "type": "decimal", "description": "Amount of ingredient in formula"},
    {"name": "sequence", "type": "integer", "description": "Order of ingredient in formula"}
  ]
```

### Add SQL Filters

For relationships that should filter on a condition by default:

```yaml
vg:sql_filter: "is_active = true"
```

---

## Phase 3: Kinetic Enrichment

Add behavioral metadata that describes how entities change over time.

### State Machines

For entities with a `status` column and defined lifecycle:

```yaml
vg:state_machine: >-
  {
    "state_column": "status",
    "states": ["draft", "submitted", "confirmed", "shipped", "received"],
    "initial": "draft",
    "terminal": ["received"],
    "transitions": [
      {"from": "draft", "to": "submitted", "label": "submit"},
      {"from": "submitted", "to": "confirmed", "label": "confirm"},
      {"from": "confirmed", "to": "shipped", "label": "ship"},
      {"from": "shipped", "to": "received", "label": "receive"}
    ]
  }
```

**Discovery approach:** Query for status columns and their distinct values:

```sql
-- Find status columns and their values
SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('status', 'state', 'lifecycle_state')
  AND table_schema = 'public';

-- For each, get distinct values
SELECT DISTINCT status FROM orders ORDER BY status;
```

Then ask the SME about valid transitions.

### Flow Configurations

For relationships that represent material, financial, or information flows:

```yaml
vg:flow_config: >-
  {
    "flow_type": "material",
    "measure_column": "quantity_kg",
    "conservation_group": "production_mass_balance",
    "direction": "domain_to_range"
  }
```

Group flows into conservation groups where inflows must equal outflows (e.g., production mass balance, procure-to-pay).

### Axioms

SQL-evaluable integrity constraints:

```yaml
vg:axioms: >-
  [
    {
      "name": "mass_balance",
      "type": "conservation",
      "severity": "warning",
      "sql_check": "SELECT batch_id FROM batches b WHERE ABS(input_kg - output_kg) > 0.01",
      "description": "Input mass must equal output mass within tolerance"
    }
  ]
```

### Actions

Document mutations for what-if reasoning:

```yaml
vg:actions: >-
  [
    {
      "name": "start_production",
      "description": "Begin production run",
      "effects": [
        {"type": "state_change", "from": "planned", "to": "in_progress"},
        {"type": "create", "target": "MaterialTransaction"}
      ]
    }
  ]
```

### Scenario Parameters

Mark attributes that can be perturbed in what-if analysis:

```yaml
vg:scenario_params: >-
  [
    {"attribute": "capacity_tons_per_day", "type": "numeric", "perturbation": "multiply", "range": [0.5, 1.5]},
    {"attribute": "is_active", "type": "boolean", "perturbation": "toggle"}
  ]
```

---

## Phase 4: Structural Patterns

Refactor the flat ontology into a proper class hierarchy.

### Identify Abstract Patterns

Look for groups of tables that share columns:

```sql
-- Find columns that appear in multiple tables
SELECT column_name, COUNT(DISTINCT table_name) AS table_count,
       array_agg(table_name) AS tables
FROM information_schema.columns
WHERE table_schema = 'public'
GROUP BY column_name
HAVING COUNT(DISTINCT table_name) >= 3
ORDER BY table_count DESC;
```

Common patterns:
- **Location types** → abstract `Location` class
- **Document types** with `status`, `total_amount` → abstract `TransactionDocument`
- **Line items** with `line_number`, `quantity` → abstract `LineItem`

### Create Base Schema

Create a separate `scm_base.yaml` (or domain-appropriate name) with:

```yaml
classes:
  Location:
    abstract: true
    description: "Abstract location in the network"
    attributes:
      name:
        range: string
      is_active:
        range: boolean

  HasActiveFlag:
    mixin: true
    attributes:
      is_active:
        range: boolean
```

### Use Imports

The domain ontology imports the base schema:

```yaml
imports:
  - linkml:types
  - ../../scm_base
```

Then concrete classes use `is_a` and `mixins`:

```yaml
Plant:
  is_a: Location
  mixins:
    - HasActiveFlag
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: plants
    ...
```

### Add Enums

For columns with a fixed set of values:

```yaml
enums:
  LocationType:
    permissible_values:
      plant:
        description: "Manufacturing plant"
      dc:
        description: "Distribution center"
      retail:
        description: "Retail location"
```

---

## Phase 5: Schema Validation

Cross-reference the completed ontology against the live database.

### Run Automated Validation

```bash
# Two-layer ontology validation (LinkML + VG)
poetry run python scripts/validate_ontology.py --all

# Schema match validation (ontology vs live database)
poetry run python scripts/validate_schema_match.py
```

### Validation Checks

| Check | Ontology Source | Database Source |
|-------|----------------|----------------|
| Table exists | `vg:table` per class | `information_schema.tables` |
| Columns exist | `attributes` block | `information_schema.columns` |
| Primary key matches | `vg:primary_key` | `table_constraints` + `key_column_usage` |
| FK existence | `vg:domain_key`/`vg:range_key` | `referential_constraints` |
| Row count plausibility | `vg:row_count` | `SELECT COUNT(*)` |

### Quality Checklist

After validation passes, review:

- [ ] Every FK in the DDL has a corresponding relationship class
- [ ] Polymorphic FKs have `vg:type_discriminator`
- [ ] Self-referential tables have appropriate traversal operation types
- [ ] Weighted edges have `vg:weight_columns`
- [ ] Junction tables with extra columns have `vg:edge_attributes`
- [ ] Stateful entities have `vg:state_machine`
- [ ] Context blocks on complex entities/relationships
- [ ] Row counts are current

---

## Type Mapping Reference

| SQL Type | LinkML Range |
|----------|--------------|
| VARCHAR, TEXT, CHAR | `string` |
| INTEGER, BIGINT, SMALLINT | `integer` |
| NUMERIC, DECIMAL, REAL, DOUBLE | `decimal` |
| BOOLEAN | `boolean` |
| DATE | `date` |
| TIMESTAMP, TIMESTAMPTZ | `datetime` |

## Tips for Good Ontologies

### 1. Be Specific About Semantics

Use domain-specific relationship names, not generic FK patterns:
- `FormulaHasIngredients` not `FormulaToIngredient`
- `BatchProducesProduct` not `BatchProductFK`

### 2. Document Traversal Direction

For traversal relationships, always clarify what inbound/outbound means:
```yaml
description: "SKU supersedes another. Outbound = newer version, Inbound = older version"
```

### 3. Choose Appropriate Operation Types

- Simple FKs → `direct_join` only
- Recursive chains → `recursive_traversal`
- Hierarchies with quantities → `path_aggregation`
- Weighted networks → `shortest_path`, `centrality`, etc.
- Operation types determine handler dispatch

### 4. Include Row Counts

Row counts help with query planning and estimation:
```yaml
vg:row_count: 500
```
Re-query if data volume changes significantly.

## Next Steps

- [VG Extensions](vg-extensions.md) - Complete metamodel annotation reference
- [Validation](validation.md) - Validation details
- [Ontology System](ontology-system.md) - LinkML format and core concepts
