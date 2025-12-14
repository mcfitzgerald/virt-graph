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
| `vg:primary_key` | string | Primary key column |

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
| `vg:domain_key` | string | FK column pointing to domain (source) |
| `vg:range_key` | string | FK column pointing to range (target) |
| `vg:domain_class` | string | Name of domain entity class |
| `vg:range_class` | string | Name of range entity class |
| `vg:traversal_complexity` | enum | GREEN, YELLOW, or RED |

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
    vg:traversal_complexity: YELLOW
```

### Traversal Complexity

| Value | Meaning | Handler |
|-------|---------|---------|
| `GREEN` | Direct SQL join | None needed |
| `YELLOW` | Recursive traversal | `traverse()`, `bom_explode()` |
| `RED` | Graph algorithms | `shortest_path()`, `centrality()`, etc. |

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

### Simple FK (GREEN)

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
    vg:traversal_complexity: GREEN
    vg:functional: true              # Each product has one category
```

### Self-Referential Hierarchy (YELLOW)

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
    vg:traversal_complexity: YELLOW
    vg:acyclic: true
    vg:is_hierarchical: true
```

### Junction Table with Attributes (YELLOW)

Many-to-many with edge attributes:

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
    vg:traversal_complexity: YELLOW
    vg:inverse_of: HasComponent
  attributes:
    quantity:
      range: decimal
      description: "Quantity of child part in parent"
```

### Weighted Network (RED)

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
    vg:traversal_complexity: RED
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

## Metamodel Reference

All VG extensions are defined in `ontology/virt_graph.yaml`, which serves as the **single source of truth**. The `OntologyAccessor` reads this file to dynamically validate domain ontologies.

To see the complete metamodel:

```bash
make show-ontology
```

## Next Steps

- [LinkML Format](linkml-format.md) - LinkML basics
- [Creating Ontologies](creating-ontologies.md) - Step-by-step guide
- [Validation](validation.md) - How validation works
