# Supply Chain Tutorial

This tutorial walks through the supply chain proof-of-concept included with VG/SQL. You'll learn how the ontology, handlers, and dispatch work together.

## The Domain

The supply chain domain models:

- **Suppliers** organized in a hierarchical network (tier 1, 2, 3)
- **Parts** with bill-of-materials relationships
- **Facilities** connected by transport routes
- **Products**, orders, shipments, inventory

### Data Scale

| Entity | Count |
|--------|-------|
| Suppliers | 500 |
| Parts | 5,003 |
| Products | 200 |
| Facilities | 50 |
| Customers | 1,000 |
| Orders | 20,000 |
| Supplier relationships | 817 |
| Bill of materials | 14,283 |
| Transport routes | 197 |

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

**GREEN Complexity** (Direct SQL):

| Relationship | Description |
|--------------|-------------|
| `PrimarySupplier` | Part's primary supplier (FK in parts table) |
| `CanSupply` | Which suppliers can provide a part |
| `ContainsComponent` | Products contain parts |
| `PlacedBy` | Order placed by customer |
| `HasCertification` | Supplier's certifications |

**YELLOW Complexity** (Recursive Traversal):

| Relationship | Description |
|--------------|-------------|
| `SuppliesTo` | Supplier network (who sells to whom) |
| `ComponentOf` / `HasComponent` | Bill of materials hierarchy |

**RED Complexity** (Network Algorithms):

| Relationship | Description |
|--------------|-------------|
| `ConnectsTo` | Transport routes with weights (distance, cost, time) |

## Example Queries

### GREEN: Direct SQL

**Q: Which suppliers have ISO9001 certification?**

The `HasCertification` relationship is GREEN—simple FK join:

```sql
SELECT DISTINCT s.supplier_code, s.name, sc.certification_number
FROM suppliers s
JOIN supplier_certifications sc ON s.id = sc.supplier_id
WHERE sc.certification_type = 'ISO9001' AND sc.is_valid = true;
```

Result: 143 suppliers

### YELLOW: Recursive Traversal

**Q: Find all upstream suppliers of Acme Corp**

The `SuppliesTo` relationship is YELLOW—requires recursive traversal:

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

The `ComponentOf` relationship is YELLOW—use `bom_explode()`:

```python
from virt_graph.handlers.traversal import bom_explode

# Find the part ID
cur.execute("SELECT id FROM parts WHERE name = 'Turbo Encabulator'")
part_id = cur.fetchone()[0]

result = bom_explode(
    conn,
    start_part_id=part_id,
    max_depth=20,
    include_quantities=True,
)

print(f"BOM contains {result['total_parts']} unique parts")
print(f"Maximum depth: {result['max_depth']}")

# Show top 10 by quantity
sorted_parts = sorted(result['components'], key=lambda x: x['total_quantity'], reverse=True)
print("\nTop 10 parts by quantity:")
for part in sorted_parts[:10]:
    print(f"  {part['part_name']}: {part['total_quantity']} units")
```

Result: 1,024 unique parts at 8 levels of assembly

### RED: Network Algorithms

**Q: What's the shortest route from Chicago to Los Angeles?**

The `ConnectsTo` relationship is RED—weighted pathfinding:

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
2. **Determines complexity** from the `vg:traversal_complexity` annotation
3. **Generates the appropriate query**:
   - GREEN → Direct SQL
   - YELLOW → Handler call (traverse, bom_explode)
   - RED → Handler call (shortest_path, centrality)
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
poetry run pytest tests/test_bom_explode.py -v
```

## Key Takeaways

1. **Complexity classification matters**: GREEN/YELLOW/RED determines the query strategy
2. **Schema parameterization**: Handlers don't know about "suppliers"—they work with any table/column names
3. **Ontology is the map**: It tells Claude what exists and how to traverse it
4. **Handlers fill SQL gaps**: Recursive traversal and graph algorithms aren't native to SQL

## Next Steps

- [Architecture](../concepts/architecture.md) - How the components work together
- [Complexity Levels](../concepts/complexity-levels.md) - Deep dive on GREEN/YELLOW/RED
- [Creating Ontologies](../ontology/creating-ontologies.md) - Build your own domain ontology
