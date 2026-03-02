# Ontology Building Guide

A practical guide for building a VG/SQL ontology from scratch against any relational database. Based on lessons learned building the PCG reference ontology (38 classes, 50 relationships, 395M rows).

This complements [Creating Ontologies](ontology-creation.md) (the 5-phase protocol) with the practical mechanics of what to do, what order to do it in, and what goes wrong.

## The Process at a Glance

```
1. Map the schema          → one class per table, one relationship per FK
2. Verify against data     → query actual values, fix mismatches
3. Classify operations     → direct_join, traversal, pathfinding, aggregation
4. Write context blocks    → teach the AI what everything MEANS
5. Add behavioral metadata → state machines, axioms, flows, scenarios
6. Validate and test       → two-layer validation + live DB cross-reference
```

Each step feeds the next. Don't try to do it all in one pass — iterate.

---

## Step 1: Map the Schema

### Input: Your DDL or live database

Start with the DDL file if you have one. If not, introspect the live database:

```sql
-- All tables and columns
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

-- All foreign keys
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

-- Primary keys
SELECT tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'PRIMARY KEY'
ORDER BY tc.table_name;

-- Row counts (fast estimate from statistics)
SELECT relname AS table_name, reltuples::bigint AS row_count
FROM pg_class
WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace
ORDER BY reltuples DESC;
```

### Output: One class per table

For each table, create a class:

```yaml
Supplier:
  description: "Raw material and ingredient supplier"
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: suppliers
    vg:primary_key: id
    vg:identifier: supplier_code    # natural key for display
  attributes:
    supplier_code:
      range: string
    country:
      range: string
    tier:
      range: integer
```

**Rules:**
- Class names are PascalCase singular (`Supplier`, not `suppliers`)
- `vg:table` is the exact SQL table name
- `vg:primary_key` is `id` for simple PKs, `'["col1", "col2"]'` for composites
- `vg:identifier` is the human-readable natural key (code, number, etc.)
- Only list attributes you want the AI to know about — not every column

**Type mapping:**

| SQL Type | LinkML Range |
|----------|--------------|
| VARCHAR, TEXT | `string` |
| INTEGER, BIGINT | `integer` |
| NUMERIC, DECIMAL | `decimal` |
| BOOLEAN | `boolean` |
| DATE | `date` |

### Output: One relationship per FK

For each foreign key, create a relationship:

```yaml
POFromSupplier:
  description: "Purchase order placed with a supplier"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: purchase_orders      # table where the FK lives
    vg:domain_key: id                   # PK of the "from" side
    vg:range_key: supplier_id           # FK column pointing to target
    vg:domain_class: PurchaseOrder      # "from" class
    vg:range_class: Supplier            # "to" class
    vg:operation_types: '["direct_join"]'
    vg:functional: true                 # each PO has exactly one supplier
```

**Naming convention:** Use semantic names that describe the business meaning:
- `POFromSupplier` not `PurchaseOrderSupplierFK`
- `BatchProducesProduct` not `BatchProductIdRelation`
- `FormulaHasIngredients` not `FormulaIngredientJoin`

**Junction tables** (many-to-many through a separate table):

```yaml
SupplierOffersIngredient:
  annotations:
    vg:edge_table: supplier_ingredients   # the junction table
    vg:domain_key: supplier_id            # FK to domain class
    vg:range_key: ingredient_id           # FK to range class
    vg:domain_class: Supplier
    vg:range_class: Ingredient
    vg:operation_types: '["direct_join"]'
```

**Composite PK line items** (parent → child):

```yaml
OrderHasLines:
  annotations:
    vg:edge_table: order_lines
    vg:domain_key: order_id                        # FK to parent
    vg:range_key: '["order_id", "line_number"]'    # composite PK of child
    vg:domain_class: Order
    vg:range_class: OrderLine
    vg:operation_types: '["direct_join"]'
```

### Watch for implicit FKs

Many databases have columns named `*_id` that aren't declared as SQL foreign key constraints. You still need to create relationship classes for these. Query for them:

```sql
-- Columns ending in _id that aren't FK-constrained
SELECT c.table_name, c.column_name
FROM information_schema.columns c
LEFT JOIN (
    SELECT tc.table_name, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
) fk ON fk.table_name = c.table_name AND fk.column_name = c.column_name
WHERE c.column_name LIKE '%_id'
  AND c.table_schema = 'public'
  AND fk.column_name IS NULL
ORDER BY c.table_name;
```

---

## Step 2: Verify Against Data

This is where most ontology bugs live. The schema tells you the structure; only the data tells you the truth.

### Check type discriminator values

If your schema has `*_type` columns alongside `*_id` columns, the ID is probably polymorphic. Query the actual values:

```sql
-- What values does the type column actually contain?
SELECT origin_type, COUNT(*) FROM route_segments GROUP BY origin_type ORDER BY COUNT(*) DESC;
SELECT location_type, COUNT(*) FROM inventory GROUP BY location_type ORDER BY COUNT(*) DESC;
```

**The PCG lesson:** The ontology originally declared `{dc: DistributionCenter, retail: RetailLocation}` but the actual data had `{rdc: DistributionCenter, customer_dc: DistributionCenter, store: RetailLocation}`. This caused every polymorphic join to fail silently. Always query the data.

Map each observed value to a class:

```yaml
vg:type_discriminator: >-
  {"column": "origin_type", "mapping": {
    "plant": "Plant",
    "rdc": "DistributionCenter",
    "customer_dc": "DistributionCenter",
    "supplier": "Supplier"
  }}
```

Note that multiple discriminator values can map to the same class (like `rdc` and `customer_dc` both mapping to `DistributionCenter`).

### Check status column values

For every table with a `status` column:

```sql
SELECT status, COUNT(*) FROM orders GROUP BY status;
SELECT status, COUNT(*) FROM purchase_orders GROUP BY status;
SELECT status, COUNT(*) FROM work_orders GROUP BY status;
```

**The PCG lesson:** The ontology declared `["pending", "allocated", "shipped", "delivered"]` for orders, but 100% of orders had `status = 'CLOSED'`. The lifecycle model was aspirational, not observed. Document this with a `data_note`:

```yaml
vg:state_machine: >-
  {
    "state_column": "status",
    "states": ["pending", "allocated", "shipped", "delivered"],
    "initial_state": "pending",
    "terminal_states": ["delivered"],
    "data_note": "Current data: all orders have status=CLOSED. Full lifecycle retained as business process model."
  }
```

### Find polymorphic columns without discriminators

Some columns point to different tables depending on the value, with no explicit type column. Query for these:

```sql
-- Check if an ID column's values span multiple tables
SELECT MIN(source_id), MAX(source_id) FROM orders;
SELECT MIN(id), MAX(id) FROM channels;
SELECT MIN(id), MAX(id) FROM retail_locations;
```

**The PCG lesson:** `orders.source_id` points to `channels` (IDs 1-7) OR `retail_locations` (IDs 67+). No discriminator column exists — the only way to know is to check ID ranges. Document this in the context block, not the type_discriminator.

### Find zero/null columns

Check if columns that should have data are actually populated:

```sql
-- Find columns where every value is zero or null
SELECT 'order_lines.unit_price' AS column_path,
       COUNT(*) AS total_rows,
       COUNT(CASE WHEN unit_price != 0 THEN 1 END) AS non_zero
FROM order_lines;
```

**The PCG lesson:** `order_lines.unit_price` is zero across all 61.9M rows. Revenue lives exclusively in `ar_invoice_lines`. Without this knowledge, the AI generates queries against the wrong table.

### Verify table subtypes

If one table contains logically distinct subtypes:

```sql
SELECT type, COUNT(*) FROM distribution_centers GROUP BY type;
```

**The PCG lesson:** `distribution_centers` contains both RDCs (6 rows, type='rdc') and customer DCs (56 rows, type='customer_dc'). These behave differently in the supply chain but share a table. Document this in the context block.

---

## Step 3: Classify Operations

Every relationship needs `vg:operation_types` to tell the AI how to query it.

### Decision tree

```
Is it a simple FK lookup?
  → ["direct_join"]

Is it self-referential (table points to itself)?
  → ["direct_join", "recursive_traversal"]

Does it form a hierarchy with quantities to roll up?
  → ["direct_join", "hierarchical_aggregation", "path_aggregation"]

Is it a weighted network (distances, costs, times)?
  → ["direct_join", "shortest_path", "centrality", "connected_components", "resilience_analysis"]
```

**Most relationships are just `["direct_join"]`.** The interesting ones are the exceptions.

### When to add graph operation types

Only add traversal/algorithm operation types when the relationship actually forms a graph pattern:

| Pattern | Example | Operation Types |
|---------|---------|-----------------|
| Simple FK | order → customer | `direct_join` only |
| Self-referential chain | sku → supersedes_sku | `direct_join`, `recursive_traversal` |
| BOM/hierarchy with quantities | formula → ingredients | `direct_join`, `path_aggregation`, `hierarchical_aggregation` |
| Transport/routing network | route_segment origin/dest | `direct_join`, `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` |

### Add OWL 2 axioms for graph relationships

For non-trivial graph relationships, add structural constraints:

```yaml
# Self-referential chain (SKU replacement)
vg:asymmetric: true     # if A supersedes B, B doesn't supersede A
vg:irreflexive: true    # a SKU can't supersede itself
vg:acyclic: true        # no circular replacement chains

# Simple FK
vg:functional: true     # each order has exactly one customer
```

### Add edge weights for pathfinding

If a relationship supports `shortest_path`:

```yaml
vg:is_weighted: true
vg:weight_columns: >-
  [
    {"name": "distance_km", "type": "decimal", "unit": "km", "description": "Segment distance"},
    {"name": "transit_time_hours", "type": "decimal", "unit": "hours", "description": "Transit time"}
  ]
```

### Add edge attributes for junction tables

If a junction table has meaningful columns beyond the two FKs:

```yaml
vg:edge_attributes: >-
  [
    {"name": "unit_cost", "type": "decimal", "description": "Cost per kg from this supplier"},
    {"name": "lead_time_days", "type": "integer", "description": "Supplier lead time in days"},
    {"name": "min_order_qty", "type": "decimal", "description": "Minimum order quantity in kg"}
  ]
```

---

## Step 4: Write Context Blocks

Context blocks are what make the ontology useful for AI query generation. Without them, the AI knows the schema structure but not the business meaning.

### The principle

The ontology is the virtual twin's "brain." Each context block should answer: **"If an AI needs to write a SQL query involving this entity, what does it need to know that isn't obvious from the column names?"**

### Template for class context

```yaml
vg:context: >-
  {
    "business_logic": "What this entity IS, its role in the domain, key business rules, data volumes, known subtypes or special patterns.",
    "llm_prompt_hint": "Practical query guidance — which columns matter, common joins, gotchas, what NOT to do, where the real data lives."
  }
```

### Template for relationship context

```yaml
vg:context: >-
  {
    "business_logic": "What this connection MEANS in business terms.",
    "traversal_semantics": {
      "inbound": "what it means to traverse TO the domain class (e.g., 'what suppliers offer this ingredient')",
      "outbound": "what it means to traverse FROM the domain class (e.g., 'what ingredients this supplier offers')"
    },
    "llm_prompt_hint": "How to join, what to watch out for, common aggregations."
  }
```

### What makes a good context block

**Good:** Specific, actionable, based on data reality.

```yaml
vg:context: >-
  {
    "business_logic": "SOURCE OF TRUTH FOR REVENUE ($38.3B total). This is where actual revenue lives — NOT in order_lines (which have zero unit_price). channel column enables direct revenue-by-channel analysis.",
    "llm_prompt_hint": "For revenue analysis: SUM(total_amount) or join ar_invoice_lines for SKU-level detail. Use channel column for revenue-by-channel (do NOT try to derive from orders). Status values in data: disputed, open, partial."
  }
```

**Bad:** Generic, restates the schema, no actionable guidance.

```yaml
vg:context: >-
  {
    "business_logic": "This table stores AR invoice data.",
    "llm_prompt_hint": "Join on invoice_id."
  }
```

### What to include in class context

| Include | Example |
|---------|---------|
| Data volumes | "50 suppliers", "3,817 retail endpoints" |
| Key business rules | "tier column (1-3) drives procurement strategy" |
| Data quality issues | "12% of suppliers have -ALT suffix duplicates" |
| Which columns are unreliable | "unit_price is ALWAYS ZERO — revenue is in AR invoices" |
| Polymorphism details | "source_id points to channels (1-7) OR retail_locations (67+)" |
| Column semantics | "day is integer 1-365, not a date" |
| State machine reality | "all status=CLOSED in current data" |
| Common FK joins | "supplier_id FK appears on purchase_orders and ap_invoices" |

### What to include in relationship context

| Include | Example |
|---------|---------|
| Traversal direction meaning | "inbound = what suppliers offer this ingredient" |
| Cardinality notes | "Functional — each PO has exactly one supplier" |
| Join gotchas | "join key is account_code (VARCHAR), NOT id (INTEGER)" |
| Polymorphism warnings | "Only valid when source_id <= 7" |
| Common aggregations | "For supplier spend: SUM(total_amount) GROUP BY supplier_id" |

### Coverage target

**Every class and every relationship should have a context block.** In the PCG ontology, going from 12/88 to 88/88 context coverage was the single biggest improvement for AI query generation. Partial coverage means the AI has blind spots on 84% of the schema.

### Priority order for writing context

If you can't do everything at once, prioritize:

1. **Entities with data quality issues** — where the AI will get wrong answers without guidance
2. **Polymorphic relationships** — where the wrong table join produces silent failures
3. **Revenue/metric sources of truth** — where there are multiple tables that LOOK like they have the right data
4. **High-traffic entities** — the tables that appear in most queries
5. **Everything else** — even simple entities benefit from brief context

---

## Step 5: Add Behavioral Metadata

### State machines

For entities with a `status` or `state` column:

```yaml
vg:state_machine: >-
  {
    "state_column": "status",
    "states": ["open", "received", "closed"],
    "transitions": [
      {"from_state": "open", "to_state": "received", "description": "Goods receipt confirmed"},
      {"from_state": "received", "to_state": "closed", "description": "Invoice matched and paid"}
    ],
    "initial_state": "open",
    "terminal_states": ["closed"],
    "data_note": "Current data: all POs have status=CLOSED."
  }
```

**Always query actual status values** (Step 2) and include a `data_note`. The business process model and the data reality are often different.

### Axioms

SQL-evaluable constraints that should hold true:

```yaml
vg:axioms: >-
  [
    {
      "name": "gl_balance",
      "description": "Total debits must equal total credits per day",
      "axiom_type": "conservation",
      "sql_expression": "ABS(SUM(debit_amount) - SUM(credit_amount)) < 0.01",
      "severity": "error"
    }
  ]
```

Valid axiom types: `value_range`, `temporal_order`, `conservation`, `conditional`, `referential`.

### Scenario parameters

Attributes that can be perturbed for what-if analysis:

```yaml
vg:scenario_params: >-
  [
    {"attribute": "capacity_tons_per_day", "propagation": "downstream", "description": "Plant capacity affects production throughput", "default_perturbation": "-20%"}
  ]
```

### Flow configurations

For relationships that represent material, financial, or information flows:

```yaml
vg:flow_config: >-
  {
    "flow_type": "material",
    "quantity_column": "quantity_kg",
    "timestamp_column": "batch_id",
    "conservation_group": "production_mass_balance",
    "unit": "kg"
  }
```

Group related flows into conservation groups where total in should approximately equal total out.

---

## Step 6: Validate and Test

### Run two-layer validation

```bash
# Layer 1: LinkML structure
# Layer 2: VG annotation rules (required fields, valid enums, class references)
poetry run python scripts/validate_ontology.py --all
```

### Run schema match validation (if live DB available)

```bash
# Cross-references ontology against live database
poetry run python scripts/validate_schema_match.py --all
```

### Run existing tests

```bash
poetry run pytest pcg_example/tests/ -v
```

### Common validation errors

| Error | Cause | Fix |
|-------|-------|-----|
| `invalid axiom_type 'uniqueness'` | Not a valid enum value | Use `referential`, `value_range`, `conservation`, `conditional`, or `temporal_order` |
| `Missing required annotation: vg:table` | Class missing SQL mapping | Add `vg:table: tablename` |
| `Unknown domain_class: supplier` | Case mismatch | Use `Supplier` (PascalCase, matching class name) |
| `Invalid operation_type: traverse` | Wrong enum value | Use `recursive_traversal` |

---

## Structural Patterns (Optional but Recommended)

### Class hierarchy with a base schema

If multiple tables share common columns, factor them into a base schema:

**`base.yaml`** (domain-agnostic patterns):

```yaml
classes:
  Location:
    abstract: true
    description: "Abstract location"
    attributes:
      name: { range: string }
      is_active: { range: boolean }

  HasActiveFlag:
    mixin: true
    attributes:
      is_active: { range: boolean }
```

**`domain.yaml`** (imports base):

```yaml
imports:
  - linkml:types
  - base

classes:
  Plant:
    is_a: Location
    mixins: [HasActiveFlag]
    instantiates: [vg:SQLMappedClass]
    annotations:
      vg:table: plants
      vg:primary_key: id
```

### When to use hierarchy

- **Abstract classes** (`is_a`): when tables share structural patterns (Location types, Document types, Line items)
- **Mixins**: when tables share optional traits (soft delete, display name)
- **Enums**: when a column has a fixed set of valid values used across tables

### When NOT to use hierarchy

- Don't force hierarchy where it doesn't exist naturally
- Don't create a base schema with a single child — just use the concrete class
- Abstract classes should NOT have VG annotations (no `vg:table`)

---

## Checklist Before You Ship

```
Schema mapping
  [ ] Every table has a class with vg:table and vg:primary_key
  [ ] Every FK (explicit and implicit) has a relationship class
  [ ] Composite PKs use JSON array format

Data reality
  [ ] Type discriminator values verified against actual data
  [ ] Status column values verified against actual data
  [ ] Polymorphic columns documented (even without discriminators)
  [ ] Zero/null columns identified and warned about in context

Operations
  [ ] Simple FKs have operation_types: ["direct_join"]
  [ ] Self-refs have recursive_traversal
  [ ] Networks have shortest_path/centrality/etc.
  [ ] Hierarchies with quantities have path_aggregation

Context
  [ ] Every class has a vg:context block
  [ ] Every relationship has a vg:context block
  [ ] Data quality gotchas documented in llm_prompt_hint
  [ ] Revenue/metric sources of truth explicitly stated
  [ ] Polymorphic join logic explained

Behavioral
  [ ] State machines on entities with status columns
  [ ] data_note on every state machine with observed values
  [ ] Axioms for key business constraints
  [ ] Flow configs for material/financial flows

Validation
  [ ] poetry run python scripts/validate_ontology.py --all passes
  [ ] poetry run python scripts/validate_schema_match.py --all passes (if DB available)
  [ ] All tests pass
```

---

## File Structure

```
your_project/
├── ontology/
│   ├── base.yaml              # Reusable structural patterns (optional)
│   └── domain.yaml            # Domain ontology (the main file)
├── schema.sql                 # DDL for reference
└── tests/
    └── test_ontology.py       # Validation tests
```

The metamodel (`virt_graph.yaml`) and `OntologyAccessor` are provided by the `virt-graph` package. Your domain ontology imports them via `instantiates: [vg:SQLMappedClass]`.
