# VG Extensions Reference

VG/SQL extends LinkML with custom annotations using the `vg:` prefix. These annotations map graph concepts to SQL structures and define traversal behavior.

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
SuppliesTo:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id
    vg:range_key: buyer_id
    vg:domain_class: Supplier
    vg:range_class: Supplier
    vg:operation_types: "[recursive_traversal, temporal_traversal]"
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
SuppliesTo:
  annotations:
    vg:asymmetric: true      # If A supplies B, B doesn't supply A
    vg:irreflexive: true     # Supplier can't supply itself
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
SuppliesTo:
  annotations:
    vg:acyclic: true          # Supply chain is a DAG
    vg:is_hierarchical: true  # Has supplier tiers

ConnectsTo:
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
ConnectsTo:
  annotations:
    vg:sql_filter: "is_active = true AND status != 'suspended'"
```

The filter is injected into edge queries, allowing you to exclude inactive or invalid edges without modifying the data. Combines with temporal filtering if both are specified.

**Safety**: Basic SQL injection patterns are detected during validation.

#### vg:edge_attributes

Define non-weight columns to retrieve as edge properties (Property Graph style):

```yaml
TransportRoute:
  annotations:
    vg:edge_attributes: '[
      {"name": "carrier", "type": "string", "description": "Shipping carrier name"},
      {"name": "scheduled_date", "type": "date", "description": "Scheduled departure"}
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
SuppliesTo:
  annotations:
    vg:context: |
      {
        "definition": "A commercial relationship where one supplier sells to another",
        "business_logic": "Suppliers change tiers based on performance",
        "data_quality_notes": "Historical records before 2020 may be incomplete",
        "llm_prompt_hint": "For 'strategic suppliers', filter tier=1",
        "traversal_semantics": {
          "inbound": "upstream suppliers (who sells to this supplier)",
          "outbound": "downstream buyers (who this supplier sells to)"
        },
        "examples": [
          "Find all upstream suppliers",
          "Who are the tier 1 suppliers?"
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

### Self-Referential Hierarchy (Traversal)

Entity references itself in a hierarchy:

```yaml
ReportsTo:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: employees
    vg:domain_key: manager_id
    vg:range_key: id
    vg:domain_class: Employee
    vg:range_class: Employee
    vg:operation_types: "[recursive_traversal]"
    vg:acyclic: true
    vg:is_hierarchical: true
```

### Junction Table with Attributes (Aggregation)

Many-to-many with edge attributes (e.g., BOM):

```yaml
ComponentOf:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: bill_of_materials
    vg:domain_key: child_part_id
    vg:range_key: parent_part_id
    vg:domain_class: Part
    vg:range_class: Part
    vg:operation_types: "[recursive_traversal, hierarchical_aggregation]"
    vg:inverse_of: HasComponent
  attributes:
    quantity:
      range: decimal
      description: "Quantity of child part in parent"
```

### Weighted Network (Algorithm)

Edges with weights for pathfinding:

```yaml
ConnectsTo:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: transport_routes
    vg:domain_key: origin_facility_id
    vg:range_key: destination_facility_id
    vg:domain_class: Facility
    vg:range_class: Facility
    vg:operation_types: "[shortest_path, centrality, connected_components, resilience_analysis]"
    vg:is_weighted: true
    vg:weight_columns: '[
      {"name": "distance_km", "type": "decimal"},
      {"name": "cost_usd", "type": "decimal"},
      {"name": "transit_hours", "type": "integer"}
    ]'
  attributes:
    distance_km:
      range: decimal
    cost_usd:
      range: decimal
    transit_hours:
      range: integer
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
SuppliesTo:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id
    vg:range_key: buyer_id
    vg:domain_class: Supplier
    vg:range_class: Supplier
    vg:operation_types: "[recursive_traversal]"
    vg:context: |
      {
        "business_logic": "Suppliers change tiers based on performance metrics",
        "llm_prompt_hint": "For 'strategic suppliers', filter tier=1",
        "traversal_semantics": {
          "inbound": "upstream suppliers",
          "outbound": "downstream buyers"
        }
      }
```

## Metamodel Reference

All VG extensions are defined in `virt_graph.yaml` (at project root), which serves as the **single source of truth**. The `OntologyAccessor` reads this file to dynamically validate domain ontologies.

To see the complete metamodel:

```bash
make show-ontology
```

## Next Steps

- [LinkML Format](linkml-format.md) - LinkML basics
- [Creating Ontologies](creating-ontologies.md) - Step-by-step guide
- [Validation](validation.md) - How validation works
