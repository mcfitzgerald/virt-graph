# VG Extensions Reference

VG/SQL extends LinkML with custom annotations using the `vg:` prefix. These annotations map graph concepts to SQL structures and define traversal behavior.

## Abstract Classes and Mixins

Domain ontologies can import `scm_base.yaml` for reusable structural patterns. Abstract classes (`abstract: true`) and mixins (`mixin: true`) do NOT have `instantiates` and are automatically excluded from TBox/RBox. Only concrete children need `instantiates: vg:SQLMappedClass`.

All complex VG annotations (type_discriminator, state_machine, axioms, context, etc.) must use the `>-` JSON string format for compatibility with LinkML's SchemaView.

## Extension Classes

VG defines two extension classes that ontology classes instantiate:

| Extension | Purpose | Used For |
|-----------|---------|----------|
| `vg:SQLMappedClass` | Map entity to SQL table | Entity classes (TBox) |
| `vg:SQLMappedRelationship` | Map relationship to FKs | Relationship classes (RBox) |

```yaml
classes:
  Supplier:
    instantiates:
      - vg:SQLMappedClass        # This is an entity
    # ...

  SuppliesTo:
    instantiates:
      - vg:SQLMappedRelationship # This is a relationship
    # ...
```

## Entity Class Annotations (SQLMappedClass)

### Required Annotations

| Annotation | Type | Description |
|------------|------|-------------|
| `vg:table` | string | SQL table name |
| `vg:primary_key` | string or JSON array | Primary key column(s) - supports composite keys |

```yaml
Supplier:
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: suppliers
    vg:primary_key: id
```

### Optional Annotations

| Annotation | Type | Description |
|------------|------|-------------|
| `vg:identifier` | JSON array | Natural key column(s) |
| `vg:soft_delete_column` | string | Soft delete timestamp column |
| `vg:row_count` | integer | Estimated row count |
| `vg:context` | JSON object | Structured context for AI query generation |

```yaml
Supplier:
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: suppliers
    vg:primary_key: id
    vg:identifier: "[supplier_code]"       # JSON array format
    vg:soft_delete_column: deleted_at
    vg:row_count: 500
```

### Composite Primary Keys

For tables with composite primary keys, use a JSON array:

```yaml
OrderLineItem:
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: order_line_items
    vg:primary_key: '["order_id", "line_number"]'
```

Handlers automatically handle tuple-based node IDs for composite keys.

#### vg:identifier

The natural key used to identify entities (vs. surrogate primary key):

```yaml
# Single column
vg:identifier: "[supplier_code]"

# Composite key
vg:identifier: "[region, store_number]"
```

#### vg:soft_delete_column

Column that marks logically deleted rows:

```yaml
vg:soft_delete_column: deleted_at     # NULL = active, timestamp = deleted
```

Handlers filter out soft-deleted rows during traversal.

## Relationship Class Annotations (SQLMappedRelationship)

### Required Annotations

| Annotation | Type | Description |
|------------|------|-------------|
| `vg:edge_table` | string | Junction/edge table name |
| `vg:domain_key` | string or JSON array | FK column(s) pointing to domain - supports composite keys |
| `vg:range_key` | string or JSON array | FK column(s) pointing to range - supports composite keys |
| `vg:domain_class` | string or JSON array | Name(s) of domain entity class(es) - list for polymorphism |
| `vg:range_class` | string or JSON array | Name(s) of range entity class(es) - list for polymorphism |
| `vg:operation_types` | JSON array | List of supported operation types |

```yaml
SKUSupersedes:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: skus
    vg:domain_key: id
    vg:range_key: supersedes_sku_id
    vg:domain_class: SKU
    vg:range_class: SKU
    vg:operation_types: '["direct_join", "recursive_traversal"]'
```

### Composite Foreign Keys

For relationships with composite keys, use JSON arrays:

```yaml
OrderLineHasProduct:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: order_line_items
    vg:domain_key: '["order_id", "line_number"]'
    vg:range_key: product_id
    vg:domain_class: OrderLineItem
    vg:range_class: Product
    vg:operation_types: "[direct_join]"
```

### Operation Types

| Category | Values | Handler |
|----------|--------|---------|
| Direct | `direct_join` | None needed (SQL) |
| Traversal | `recursive_traversal`, `temporal_traversal` | `traverse()` |
| Aggregation | `path_aggregation`, `hierarchical_aggregation` | `path_aggregate()` |
| Algorithm | `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` | NetworkX-based handlers |

### OWL 2 Role Axioms

Standard OWL 2 axioms for relationship semantics:

| Annotation | Type | Meaning |
|------------|------|---------|
| `vg:transitive` | boolean | R(x,y) ∧ R(y,z) → R(x,z) |
| `vg:symmetric` | boolean | R(x,y) → R(y,x) |
| `vg:asymmetric` | boolean | R(x,y) → ¬R(y,x) |
| `vg:reflexive` | boolean | R(x,x) always holds |
| `vg:irreflexive` | boolean | R(x,x) never holds (no self-loops) |
| `vg:functional` | boolean | At most one range per domain |
| `vg:inverse_functional` | boolean | At most one domain per range |

```yaml
SKUSupersedes:
  annotations:
    vg:asymmetric: true      # If A supersedes B, B doesn't supersede A
    vg:irreflexive: true     # SKU can't supersede itself
    vg:acyclic: true         # No circular supersession chains
```

### VG-Specific Extensions

| Annotation | Type | Description |
|------------|------|-------------|
| `vg:acyclic` | boolean | DAG constraint (no cycles) |
| `vg:is_hierarchical` | boolean | Has tier/level structure |
| `vg:is_weighted` | boolean | Has numeric edge weights |
| `vg:inverse_of` | string | Name of inverse relationship |
| `vg:weight_columns` | JSON array | Weight column definitions |

```yaml
SKUSupersedes:
  annotations:
    vg:acyclic: true          # Alias chain is a DAG

RouteSegmentOrigin:
  annotations:
    vg:is_weighted: true
    vg:weight_columns: '[{"name": "distance_km", "type": "decimal", "unit": "km"}]'
```

#### vg:weight_columns

Define weighted edges for pathfinding:

```yaml
vg:weight_columns: '[
  {"name": "distance_km", "type": "decimal", "unit": "km", "description": "Distance in kilometers"},
  {"name": "cost_usd", "type": "decimal", "unit": "USD", "description": "Shipping cost"},
  {"name": "transit_hours", "type": "integer", "unit": "hours", "description": "Transit time"}
]'
```

Each weight column can be used with `shortest_path(weight_col="distance_km")`.

#### vg:sql_filter

Filter edges during traversal with a SQL WHERE clause:

```yaml
ProductionLineAtPlant:
  annotations:
    vg:sql_filter: "is_active = true"
```

The filter is injected into edge queries, allowing you to exclude inactive or invalid edges without modifying the data. Combines with temporal filtering if both are specified.

**Safety**: Basic SQL injection patterns are detected during validation.

#### vg:edge_attributes

Define non-weight columns to retrieve as edge properties (Property Graph style):

```yaml
SupplierOffersIngredient:
  annotations:
    vg:edge_attributes: '[
      {"name": "unit_cost", "type": "decimal", "description": "Cost per kg from this supplier"},
      {"name": "lead_time_days", "type": "integer", "description": "Supplier lead time in days"},
      {"name": "min_order_qty", "type": "decimal", "description": "Minimum order quantity in kg"}
    ]'
```

Unlike `vg:weight_columns`, edge attributes are informational and returned with edge data but not used for path calculations.

#### vg:type_discriminator

Configure polymorphic relationship target resolution:

```yaml
OwnedBy:
  annotations:
    vg:range_class: '["User", "Organization"]'
    vg:type_discriminator:
      column: owner_type
      mapping:
        user: User
        org: Organization
```

When the relationship targets multiple entity types, the discriminator column determines which type each edge points to. The mapping translates database values to class names.

**Note**: For the "Exclusive Arc" pattern (separate nullable FK columns like `user_id` and `org_id`), map as two separate relationships instead.

#### vg:context (ContextBlock)

Provide structured context for AI-assisted query generation:

```yaml
FormulaHasIngredients:
  annotations:
    vg:context: |
      {
        "business_logic": "BOM explosion semantics — quantity_kg is per-batch requirement. For total requirements, multiply through the hierarchy.",
        "llm_prompt_hint": "Use path_aggregation with operation=multiply for cost rollups",
        "traversal_semantics": {
          "inbound": "what ingredients go into this formula",
          "outbound": "what formulas use this ingredient"
        },
        "examples": [
          "What ingredients does formula F-001 need?",
          "Which formulas use ingredient X?"
        ]
      }
```

| Field | Purpose |
|-------|---------|
| `definition` | Formal business definition or glossary term |
| `business_logic` | Human-readable explanation of behavior |
| `data_quality_notes` | Known data issues, reliability warnings, or scope limitations |
| `llm_prompt_hint` | Hints for AI query construction |
| `traversal_semantics` | What inbound/outbound mean in business terms |
| `examples` | Example natural language queries |

This context helps Claude generate appropriate queries and understand domain semantics.

#### vg:inverse_of

Link inverse relationships:

```yaml
ComponentOf:
  annotations:
    vg:inverse_of: HasComponent

HasComponent:
  annotations:
    vg:inverse_of: ComponentOf
```

### Cardinality

| Annotation | Type | Description |
|------------|------|-------------|
| `vg:cardinality_domain` | string | Cardinality from domain side |
| `vg:cardinality_range` | string | Cardinality from range side |

Notation:
- `"1..1"` - Exactly one (required)
- `"0..1"` - Zero or one (optional)
- `"1..*"` - One or more
- `"0..*"` - Zero or more

```yaml
PlacedBy:
  annotations:
    vg:cardinality_domain: "1..1"   # Each order has exactly one customer
    vg:cardinality_range: "0..*"    # Each customer has zero or more orders
```

### DDL Metadata

Annotations that reflect database constraints:

| Annotation | Type | Description |
|------------|------|-------------|
| `vg:has_self_ref_constraint` | boolean | FK references same table |
| `vg:has_unique_edge_index` | boolean | Unique index on (from, to) |
| `vg:indexed_columns` | JSON array | Which columns are indexed |

```yaml
SuppliesTo:
  annotations:
    vg:has_self_ref_constraint: true
    vg:has_unique_edge_index: true
    vg:indexed_columns: '["seller_id", "buyer_id"]'
```

## Common Patterns

### Simple FK (Direct)

Entity A has a foreign key to entity B:

```yaml
BelongsToCategory:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: products          # FK is in products table
    vg:domain_key: category_id       # The FK column
    vg:range_key: id                 # References categories.id
    vg:domain_class: Product
    vg:range_class: Category
    vg:operation_types: "[direct_join]"
    vg:functional: true              # Each product has one category
```

### Self-Referential Chain (Traversal)

Entity references itself (alias chain, hierarchy):

```yaml
SKUSupersedes:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: skus
    vg:domain_key: id
    vg:range_key: supersedes_sku_id
    vg:domain_class: SKU
    vg:range_class: SKU
    vg:operation_types: '["direct_join", "recursive_traversal"]'
    vg:asymmetric: true
    vg:irreflexive: true
    vg:acyclic: true
```

### Junction Table with Attributes (Aggregation)

Many-to-many with edge attributes (e.g., BOM):

```yaml
FormulaHasIngredients:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: formula_ingredients
    vg:domain_key: formula_id
    vg:range_key: ingredient_id
    vg:domain_class: Formula
    vg:range_class: Ingredient
    vg:operation_types: '["direct_join", "hierarchical_aggregation", "path_aggregation"]'
    vg:edge_attributes: '[
      {"name": "sequence", "type": "integer"},
      {"name": "quantity_kg", "type": "decimal"}
    ]'
```

### Weighted Network (Algorithm)

Edges with weights for pathfinding:

```yaml
RouteSegmentOrigin:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: route_segments
    vg:domain_key: id
    vg:range_key: origin_id
    vg:domain_class: RouteSegment
    vg:range_class: '["Plant", "DistributionCenter", "RetailLocation"]'
    vg:operation_types: '["direct_join", "shortest_path", "centrality", "connected_components", "resilience_analysis"]'
    vg:is_weighted: true
    vg:weight_columns: '[
      {"name": "distance_km", "type": "decimal", "unit": "km"},
      {"name": "transit_time_hours", "type": "decimal", "unit": "hours"}
    ]'
    vg:type_discriminator:
      column: origin_type
      mapping:
        plant: Plant
        dc: DistributionCenter
        retail: RetailLocation
```

### Polymorphic Relationship

Relationship that can target multiple entity types:

```yaml
# Polymorphic ID pattern: owner_id + owner_type
OwnedBy:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: assets
    vg:domain_key: id
    vg:range_key: owner_id
    vg:domain_class: Asset
    vg:range_class: '["User", "Organization"]'
    vg:operation_types: "[direct_join]"
    vg:type_discriminator:
      column: owner_type
      mapping:
        user: User
        org: Organization
```

### Composite Key Relationship

Relationship with composite foreign keys:

```yaml
OrderLineHasProduct:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: order_line_items
    vg:domain_key: '["order_id", "line_number"]'
    vg:range_key: product_id
    vg:domain_class: OrderLineItem
    vg:range_class: Product
    vg:operation_types: "[direct_join]"
```

### Relationship with AI Context

Relationship with rich context for query generation:

```yaml
BatchConsumesIngredient:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: batch_ingredients
    vg:domain_key: batch_id
    vg:range_key: ingredient_id
    vg:domain_class: Batch
    vg:range_class: Ingredient
    vg:operation_types: '["direct_join"]'
    vg:context: |
      {
        "business_logic": "Mass balance — sum of input ingredients should approximate batch output / yield",
        "traversal_semantics": {
          "inbound": "what batches consumed this ingredient",
          "outbound": "what ingredients went into this batch"
        }
      }
```

## Metamodel Reference

All VG extensions are defined in `virt_graph.yaml` (at project root), which serves as the **single source of truth**. The `OntologyAccessor` reads this file to dynamically validate domain ontologies.

To see the complete metamodel:

```bash
poetry run python scripts/show_ontology.py
```

## Axioms (v3.0)

Axioms are SQL-evaluable constraints declared on classes or relationships. Claude checks them via `SELECT COUNT(*) FROM table WHERE NOT (sql_expression)`.

### Axiom Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique name (e.g., `mass_balance`) |
| `description` | Yes | Human-readable explanation |
| `axiom_type` | Yes | One of: `value_range`, `temporal_order`, `conservation`, `conditional`, `referential` |
| `sql_expression` | Yes | SQL boolean expression that should be true for valid rows |
| `severity` | Yes | One of: `error`, `warning`, `info` |

### AxiomType Enum

| Value | Description |
|-------|-------------|
| `value_range` | Column value within expected range |
| `temporal_order` | Temporal ordering constraint |
| `conservation` | Quantity/value conservation |
| `conditional` | Constraint applies when condition met |
| `referential` | Cross-table referential integrity |

### Example (Class Axiom)

```yaml
Shipment:
  annotations:
    vg:axioms: >-
      [
        {
          "name": "temporal_order",
          "description": "Arrival date must be on or after ship date",
          "axiom_type": "temporal_order",
          "sql_expression": "arrival_date >= ship_date OR arrival_date IS NULL",
          "severity": "error"
        }
      ]
```

### Example (Relationship Axiom)

```yaml
FormulaHasIngredients:
  annotations:
    vg:axioms: >-
      [
        {
          "name": "ingredient_quantity_positive",
          "description": "Formula ingredient quantity must be positive",
          "axiom_type": "value_range",
          "sql_expression": "quantity_kg > 0",
          "severity": "error"
        }
      ]
```

### Claude Evaluation Pattern

```python
axioms = ontology.get_class_axioms("Shipment")
for axiom in axioms:
    sql = f"SELECT COUNT(*) FROM shipments WHERE NOT ({axiom['sql_expression']})"
    # Run sql, report violations based on axiom['severity']
```

## State Machines (v3.0)

State machines declare lifecycle states and valid transitions for status-bearing entities. Claude uses these for state distribution queries, transition analysis, and dwell-time calculations.

### StateMachine Fields

| Field | Required | Description |
|-------|----------|-------------|
| `state_column` | Yes | Column containing current state |
| `states` | Yes | All valid state values (minimum 2) |
| `transitions` | Yes | Valid transitions (minimum 1) |
| `initial_state` | No | Starting state for new entities |
| `terminal_states` | No | End-of-lifecycle states |

### StateTransition Fields

| Field | Required | Description |
|-------|----------|-------------|
| `from_state` | Yes | Source state |
| `to_state` | Yes | Target state |
| `guard` | No | SQL boolean expression for conditional transition |
| `description` | No | When/why this transition occurs |

### Example

```yaml
Order:
  annotations:
    vg:state_machine: >-
      {
        "state_column": "status",
        "states": ["pending", "allocated", "shipped", "delivered"],
        "transitions": [
          {"from_state": "pending", "to_state": "allocated", "description": "Inventory reserved"},
          {"from_state": "allocated", "to_state": "shipped", "description": "Shipment dispatched"},
          {"from_state": "shipped", "to_state": "delivered", "description": "Receipt confirmed"}
        ],
        "initial_state": "pending",
        "terminal_states": ["delivered"]
      }
```

### Claude Usage Patterns

```sql
-- State distribution
SELECT status, COUNT(*) FROM orders GROUP BY status;

-- Dwell time (how long orders stay in each state)
-- Requires transaction_sequence_id for temporal ordering
```

## Flow Configuration (v3.0)

Flow configuration declares material, information, or financial flow metadata on relationships. Enables throughput analysis using Little's Law (L = λW), bottleneck detection, and conservation checking.

### FlowConfig Fields

| Field | Required | Description |
|-------|----------|-------------|
| `flow_type` | Yes | One of: `material`, `information`, `financial` |
| `quantity_column` | Yes | Column with flow quantity |
| `timestamp_column` | Yes | Column with flow timestamp |
| `conservation_group` | No | Conservation group name |
| `unit` | No | Unit of measurement |
| `capacity_column` | No | Capacity limit column |

### FlowType Enum

| Value | Description |
|-------|-------------|
| `material` | Physical goods (kg, cases, units) |
| `information` | Data/document flow |
| `financial` | Monetary flow (invoices, payments) |

### Example

```yaml
BatchConsumesIngredient:
  annotations:
    vg:flow_config: >-
      {
        "flow_type": "material",
        "quantity_column": "quantity_kg",
        "timestamp_column": "batch_id",
        "conservation_group": "production_mass_balance",
        "unit": "kg"
      }
```

### Conservation Groups

Relationships in the same conservation group should satisfy quantity conservation (total in ≈ total out). Use `get_conservation_groups()` to discover groups:

```python
groups = ontology.get_conservation_groups()
# {'procure_to_pay': [...], 'order_to_cash': [...], 'production_mass_balance': [...]}
```

### Little's Law (L = λW)

For flow relationships, Claude can compute:
- **λ** (arrival rate): `COUNT(*) / time_window` from the flow table
- **W** (wait time): average time between entry and exit states
- **L** (inventory): predicted WIP from λ × W

## Actions (v3.0)

Actions declare semantic mutations for what-if reasoning. They are **NOT executable** — they document business operations so Claude can reason about causal chains and predict downstream effects.

### Action Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Action name (e.g., `allocate`) |
| `description` | Yes | Business description |
| `preconditions` | No | Conditions for action to occur |
| `effects` | Yes | Changes when action executes |
| `affected_relationships` | No | Relationships affected |

### ActionEffect Fields

| Field | Required | Description |
|-------|----------|-------------|
| `attribute` | Yes | Column being affected |
| `effect_type` | Yes | One of: `set`, `increment`, `trigger_transition` |
| `description` | No | Human-readable effect description |

### Example

```yaml
Order:
  annotations:
    vg:actions: >-
      [
        {
          "name": "allocate",
          "description": "Reserve inventory for order fulfillment",
          "preconditions": ["status = 'pending'", "inventory >= total_cases"],
          "effects": [
            {"attribute": "status", "effect_type": "trigger_transition", "description": "pending -> allocated"}
          ],
          "affected_relationships": ["OrderHasLines"]
        }
      ]
```

## Scenario Parameters (v3.0)

Scenario parameters declare attributes that can be perturbed in what-if analysis. Claude uses these to understand which parameters are meaningful to vary and how changes propagate.

### ScenarioParam Fields

| Field | Required | Description |
|-------|----------|-------------|
| `attribute` | Yes | Column name to perturb |
| `propagation` | Yes | One of: `upstream`, `downstream`, `local` |
| `description` | No | Business meaning of perturbation |
| `default_perturbation` | No | Suggested change (e.g., `+10%`) |

### PropagationDirection Enum

| Value | Description |
|-------|-------------|
| `upstream` | Propagates to suppliers/predecessors |
| `downstream` | Propagates to customers/successors |
| `local` | Affects only the entity itself |

### Example

```yaml
Plant:
  annotations:
    vg:scenario_params: >-
      [
        {
          "attribute": "capacity_tons_per_day",
          "propagation": "downstream",
          "description": "Plant capacity affects production throughput",
          "default_perturbation": "-20%"
        }
      ]
```

### What-If Reasoning

Claude uses scenario params to answer questions like:
- "What if Plant X loses 20% capacity?" → propagate downstream to batches, shipments, orders
- "What if demand increases 30%?" → propagate upstream to plants, POs, suppliers

## Operation Types (Updated for v3.0)

| Category | Operation Types | Handler |
|----------|-----------------|---------|
| **Direct** | `direct_join` | None needed (SQL) |
| **Traversal** | `recursive_traversal`, `temporal_traversal` | `traverse()` |
| **Aggregation** | `path_aggregation`, `hierarchical_aggregation` | `path_aggregate()` |
| **Algorithm** | `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` | NetworkX-based handlers |
| **Kinetic** | `flow_analysis`, `state_analysis`, `scenario_analysis` | Ad-hoc SQL via Claude (handlers planned) |

## Next Steps

- [Ontology System](ontology-system.md) - Core concepts and LinkML format
- [Creating Ontologies](ontology-creation.md) - Step-by-step guide
- [Validation](validation.md) - How validation works
