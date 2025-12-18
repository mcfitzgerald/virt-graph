# Supply Chain Tutorial

This tutorial walks through the supply chain proof-of-concept included with VG/SQL. You'll learn how the ontology, handlers, and dispatch work together.

## The Domain

The supply chain domain models:

- **Suppliers** organized in a hierarchical network (tier 1, 2, 3)
- **Parts** with bill-of-materials relationships
- **Facilities** connected by transport routes
- **Products**, orders, shipments, inventory

### Data Scale

| Entity | Count | Notes |
|--------|-------|-------|
| Orders | 80,000 | Customer orders |
| Order Items | 239,985 | Composite key (order_id, line_number) |
| Shipments | 45,737 | 70% fulfillment, 20% transfer, 10% replenishment |
| Bill of Materials | 42,706 | With effectivity dates |
| Inventory | 30,054 | Part × Facility |
| Parts | 15,008 | 5-level BOM hierarchy |
| Customers | 5,000 | Retail, wholesale, enterprise |
| Suppliers | 1,000 | Tiered (T1/T2/T3) |
| Supplier Relationships | 1,690 | ~10% inactive/suspended |
| Transport Routes | 411 | ~5% seasonal/suspended |
| Facilities | 100 | Warehouses, factories, DCs |
| Products | 500 | Finished goods |
| **Total** | **~488K** | |

## Setup

```bash
# Install dependencies
make install

# Start PostgreSQL
make db-up

# Verify data
PGPASSWORD=dev_password psql -h localhost -U virt_graph -d supply_chain -c "SELECT COUNT(*) FROM suppliers;"
```

## The Ontology

The supply chain ontology is at `ontology/supply_chain.yaml`. It defines:

### Entity Classes (TBox)

| Class | Table | Description |
|-------|-------|-------------|
| `Supplier` | suppliers | Companies in the supply network |
| `Part` | parts | Components and assemblies |
| `Product` | products | Finished goods |
| `Facility` | facilities | Warehouses, factories |
| `Customer` | customers | End customers |
| `Order` | orders | Customer orders |
| `Shipment` | shipments | Delivery records |
| `Inventory` | inventory | Stock levels |
| `SupplierCertification` | supplier_certifications | Quality certifications |

### Relationship Classes (RBox)

**Direct (SQL joins)**:

| Relationship | Description |
|--------------|-------------|
| `PrimarySupplier` | Part's primary supplier (FK in parts table) |
| `CanSupply` | Which suppliers can provide a part |
| `ContainsComponent` | Products contain parts |
| `PlacedBy` | Order placed by customer |
| `HasCertification` | Supplier's certifications |

**Traversal (recursive operations)**:

| Relationship | Description |
|--------------|-------------|
| `SuppliesTo` | Supplier network (who sells to whom) |
| `ComponentOf` / `HasComponent` | Bill of materials hierarchy |

**Algorithm (network operations)**:

| Relationship | Description |
|--------------|-------------|
| `ConnectsTo` | Transport routes with weights (distance, cost, time) |

## Example Queries

### Direct SQL

**Q: Which suppliers have ISO9001 certification?**

The `HasCertification` relationship supports `direct_join`—simple FK join:

```sql
SELECT DISTINCT s.supplier_code, s.name, sc.certification_number
FROM suppliers s
JOIN supplier_certifications sc ON s.id = sc.supplier_id
WHERE sc.certification_type = 'ISO9001' AND sc.is_valid = true;
```

Result: 143 suppliers

### Recursive Traversal

**Q: Find all upstream suppliers of Acme Corp**

The `SuppliesTo` relationship supports `recursive_traversal`—requires the `traverse()` handler:

```python
from virt_graph.handlers.traversal import traverse
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='supply_chain',
    user='virt_graph',
    password='dev_password'
)

# First, find Acme's ID
cur = conn.cursor()
cur.execute("SELECT id FROM suppliers WHERE name = 'Acme Corp'")
acme_id = cur.fetchone()[0]

# Traverse upstream (who sells TO Acme)
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",      # Follow edges pointing TO Acme
    max_depth=10,
    include_start=False,
)

print(f"Found {len(result['nodes'])} upstream suppliers")
print(f"Depth reached: {result['depth_reached']}")

# Group by tier
from collections import defaultdict
by_tier = defaultdict(list)
for node in result['nodes']:
    tier = node.get('tier', 'unknown')
    by_tier[tier].append(node['name'])

for tier in sorted(by_tier.keys()):
    print(f"Tier {tier}: {len(by_tier[tier])} suppliers")
```

Result: 33 upstream suppliers across tiers 2 and 3

**Q: What's the full BOM for the Turbo Encabulator?**

The `ComponentOf` relationship supports `hierarchical_aggregation`—use `path_aggregate()` with `operation="multiply"`:

```python
from virt_graph.handlers.traversal import path_aggregate

# Find the part ID
cur.execute("SELECT id FROM parts WHERE name = 'Turbo Encabulator'")
part_id = cur.fetchone()[0]

result = path_aggregate(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="parent_part_id",
    edge_to_col="child_part_id",
    start_id=part_id,
    value_col="quantity",
    operation="multiply",              # Propagate quantities through hierarchy
    max_depth=20,
)

print(f"BOM contains {result['total_nodes']} unique parts")
print(f"Maximum depth: {result['max_depth']}")

# Show top 10 by aggregated quantity
sorted_aggs = sorted(result['aggregates'], key=lambda x: x['aggregated_value'], reverse=True)
print("\nTop 10 parts by quantity:")
for agg in sorted_aggs[:10]:
    print(f"  Node {agg['node_id']}: {agg['aggregated_value']} units")
```

Result: 1,024 unique parts at 8 levels of assembly

### Network Algorithms

**Q: What's the shortest route from Chicago to Los Angeles?**

The `ConnectsTo` relationship supports `shortest_path`—weighted pathfinding:

```python
from virt_graph.handlers.pathfinding import shortest_path

# Find facility IDs
cur.execute("SELECT id FROM facilities WHERE name LIKE '%Chicago%'")
chicago_id = cur.fetchone()[0]
cur.execute("SELECT id FROM facilities WHERE name LIKE '%Los Angeles%'")
la_id = cur.fetchone()[0]

result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="distance_km",
)

if result['path']:
    print(f"Route: {' → '.join(n['name'] for n in result['path_nodes'])}")
    print(f"Total distance: {result['distance']:,.1f} km")
    print(f"Hops: {len(result['path']) - 1}")
else:
    print(f"No route found: {result['error']}")
```

Result: 3,388.3 km, 3 hops

**Q: Which facility is most central to the logistics network?**

Use `centrality()` for network analysis:

```python
from virt_graph.handlers.network import centrality

result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10,
)

print(f"Top 10 most central facilities (betweenness centrality):")
for item in result['results']:
    print(f"  {item['node']['name']}: {item['score']:.4f}")

print(f"\nGraph stats: {result['graph_stats']['nodes']} nodes, {result['graph_stats']['edges']} edges")
```

Result: New York Factory (score=0.2327)

**Q: What happens if the Chicago hub goes offline?**

Use `resilience_analysis()`:

```python
from virt_graph.handlers.network import resilience_analysis

result = resilience_analysis(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_to_remove=chicago_id,
)

print(f"Removing {result['node_removed_info']['name']}:")
print(f"  Disconnected pairs: {result['disconnected_pairs']}")
print(f"  Components before: {result['components_before']}")
print(f"  Components after: {result['components_after']}")
print(f"  Is critical: {result['is_critical']}")
```

## The Dispatch Pattern

When you ask Claude a natural language question, it:

1. **Reads the ontology** to understand available entities and relationships
2. **Checks operation types** from the `vg:operation_types` annotation
3. **Generates the appropriate query**:
   - `direct_join` → Direct SQL
   - `recursive_traversal`, `path_aggregation` → Handler call (traverse, path_aggregate)
   - `shortest_path`, `centrality` → Handler call (shortest_path, centrality)
4. **Executes and returns results**

All queries are generated on-the-fly—no templates.

## Viewing the Ontology

```bash
# Show TBox/RBox summary
make show-ontology

# Or read directly
cat ontology/supply_chain.yaml
```

## Testing

```bash
# Run all tests (includes supply chain examples)
make test

# Run specific handler tests
poetry run pytest tests/test_traversal.py -v
poetry run pytest tests/test_pathfinding.py -v
poetry run pytest tests/test_network.py -v
poetry run pytest tests/test_bom_explode.py -v  # Tests path_aggregate for BOM use case
```

## Key Takeaways

1. **Operation types determine strategy**: `vg:operation_types` tells Claude which handler to use
2. **Schema parameterization**: Handlers don't know about "suppliers"—they work with any table/column names
3. **Ontology is the map**: It tells Claude what exists and how to traverse it
4. **Handlers fill SQL gaps**: Recursive traversal and graph algorithms aren't native to SQL

## Next Steps

- [Architecture](../concepts/architecture.md) - How the components work together
- [Ontology System](../concepts/ontology.md) - Deep dive on operation types
- [Creating Ontologies](../ontology/creating-ontologies.md) - Build your own domain ontology
