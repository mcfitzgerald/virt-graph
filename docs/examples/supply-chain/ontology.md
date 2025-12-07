# Supply Chain Ontology

This guide tours the `ontology/supply_chain.yaml` file, explaining how the ontology maps domain concepts to SQL and enables graph-like queries.

## Ontology Overview

The supply chain ontology defines:

- **9 Entity Classes (TBox)** - What things exist (Supplier, Part, Facility, etc.)
- **15 Relationship Classes (RBox)** - How things connect (SuppliesTo, ComponentOf, etc.)

```yaml
# ontology/supply_chain.yaml header
id: https://virt-graph.dev/schemas/supply_chain
name: supply_chain
version: "1.0"
description: >-
  Supply chain domain ontology for Virtual Graph.
  Models suppliers, parts, products, facilities, customers, orders,
  shipments, and their relationships.
```

## Entity Classes (TBox)

Entity classes map domain concepts to database tables. Each class uses `vg:SQLMappedClass` to define its SQL mapping.

### Example: Supplier

```yaml
Supplier:
  description: "Organization that provides parts or services"
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: suppliers           # SQL table name
    vg:primary_key: id            # Primary key column
    vg:identifier: "[supplier_code]"  # Human-readable identifier
    vg:soft_delete_column: deleted_at  # Soft delete support
    vg:row_count: 500             # Approximate row count (for estimation)
  attributes:
    supplier_code:
      range: string
      required: true
    name:
      range: string
      required: true
    tier:
      range: integer
      required: true
      description: "Supply chain tier (1, 2, or 3)"
    # ... additional attributes
```

### Key Annotations

| Annotation | Purpose | Example |
|------------|---------|---------|
| `vg:table` | Maps class to SQL table | `suppliers` |
| `vg:primary_key` | Identifies unique rows | `id` |
| `vg:identifier` | Human-readable template | `[supplier_code]` |
| `vg:row_count` | Guides size estimation | `500` |
| `vg:soft_delete_column` | Excludes deleted rows | `deleted_at` |

### All Entity Classes

| Class | Table | Row Count | Description |
|-------|-------|-----------|-------------|
| Supplier | `suppliers` | 500 | Supply chain organizations |
| Part | `parts` | 5,003 | Components and materials |
| Product | `products` | 200 | Finished goods (SKUs) |
| Facility | `facilities` | 50 | Physical locations |
| Customer | `customers` | 1,000 | Order-placing entities |
| Order | `orders` | 20,000 | Purchase orders |
| Shipment | `shipments` | 7,995 | Goods in transit |
| Inventory | `inventory` | 10,056 | Stock positions |
| SupplierCertification | `supplier_certifications` | 721 | Quality certifications |

## Relationship Classes (RBox)

Relationship classes define how entities connect. Each uses `vg:SQLMappedRelationship` and includes a **traversal complexity** annotation that determines which handler to use.

### Complexity Levels

| Level | Color | Handler | Use Case |
|-------|-------|---------|----------|
| Simple | GREEN | Direct SQL | FK joins, 1-2 hops |
| Recursive | YELLOW | `traverse()` | Hierarchies, networks |
| Network | RED | NetworkX | Weighted pathfinding, centrality |

### Example: YELLOW - SuppliesTo

```yaml
SuppliesTo:
  description: "Supplier sells to another supplier (tiered network)"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id      # FK from source
    vg:range_key: buyer_id        # FK to target
    vg:domain_class: Supplier
    vg:range_class: Supplier
    vg:traversal_complexity: YELLOW
    vg:asymmetric: true           # A→B doesn't imply B→A
    vg:irreflexive: true          # No self-loops
    vg:acyclic: true              # No cycles (DAG)
    vg:is_hierarchical: true      # Forms a hierarchy
    vg:row_count: 817
```

This relationship:
- Connects suppliers to other suppliers (tiered network)
- Uses `seller_id → buyer_id` as the edge direction
- Is marked YELLOW because it requires recursive traversal
- Is acyclic (suppliers flow from tier 3 → tier 1)

### Example: RED - ConnectsTo

```yaml
ConnectsTo:
  description: "Transport route connecting facilities (weighted network)"
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
      {"name": "distance_km", "type": "decimal", "unit": "km"},
      {"name": "transit_time_hours", "type": "decimal", "unit": "hours"},
      {"name": "cost_usd", "type": "decimal", "unit": "usd"}
    ]'
```

This relationship:
- Connects facilities via transport routes
- Has multiple weight options (cost, time, distance)
- Is marked RED because pathfinding requires NetworkX

### Example: GREEN - CanSupply

```yaml
CanSupply:
  description: "Supplier is approved to supply a part"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: part_suppliers
    vg:domain_key: supplier_id
    vg:range_key: part_id
    vg:domain_class: Supplier
    vg:range_class: Part
    vg:traversal_complexity: GREEN
    vg:row_count: 7582
```

This relationship:
- Simple many-to-many between suppliers and parts
- GREEN because a single JOIN suffices
- No recursion needed

### All Relationships

#### YELLOW (Recursive Traversal)

| Relationship | Edge Table | Domain → Range | Rows |
|--------------|------------|----------------|------|
| SuppliesTo | `supplier_relationships` | Supplier → Supplier | 817 |
| ComponentOf | `bill_of_materials` | Part → Part | 14,283 |
| HasComponent | `bill_of_materials` | Part → Part | 14,283 |

#### RED (Network Algorithms)

| Relationship | Edge Table | Domain → Range | Weights |
|--------------|------------|----------------|---------|
| ConnectsTo | `transport_routes` | Facility → Facility | cost, time, distance |

#### GREEN (Simple Joins)

| Relationship | Edge Table | Domain → Range |
|--------------|------------|----------------|
| PrimarySupplier | `parts` | Part → Supplier |
| CanSupply | `part_suppliers` | Supplier → Part |
| ContainsComponent | `product_components` | Product → Part |
| PlacedBy | `orders` | Order → Customer |
| ShipsFrom | `orders` | Order → Facility |
| OrderContains | `order_items` | Order → Product |
| InventoryAt | `inventory` | Inventory → Facility |
| InventoryOf | `inventory` | Inventory → Part |
| HasCertification | `supplier_certifications` | Supplier → Certification |
| ForOrder | `shipments` | Shipment → Order |
| OriginatesAt | `shipments` | Shipment → Facility |

## Using the Ontology

### Programmatic Access

Use `OntologyAccessor` to query the ontology:

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor()  # Validates on load

# Get table for a class
table = ontology.get_class_table("Supplier")  # "suppliers"

# Get FK columns for a relationship
domain_key, range_key = ontology.get_role_keys("SuppliesTo")
# ("seller_id", "buyer_id")

# Get complexity for routing
complexity = ontology.get_role_complexity("ConnectsTo")  # "RED"
```

### Command Line

```bash
# View all entity classes
make show-tbox

# View all relationships
make show-rbox

# Validate the ontology
make validate-ontology
```

## Ontology Design Principles

### 1. Explicit Complexity

Every relationship declares its traversal complexity:
- Prevents accidental expensive operations
- Guides LLM to correct handler selection
- Enables query cost estimation

### 2. Bidirectional Relationships

Some relationships have explicit inverses:
- `ComponentOf` ↔ `HasComponent` (same edge table, swapped keys)
- Enables natural language queries in either direction
- "What components make up X?" vs "Where is X used?"

### 3. Property Annotations

Relationships declare graph properties:
- `vg:acyclic: true` - No cycles (safe for unlimited depth)
- `vg:is_hierarchical: true` - Tree-like structure
- `vg:asymmetric: true` - Directed relationship

These properties guide handler configuration and safety checks.

### 4. Row Count Estimates

Every class and relationship includes `vg:row_count`:
- Enables pre-traversal size estimation
- Guards against runaway queries
- Helps with query planning

## Next Steps

Now that you understand the ontology:

1. [**Query Patterns**](patterns.md) - Learn how patterns use ontology bindings
2. [**Query Examples**](queries.md) - See the ontology in action
