# Query Examples

Step-by-step walkthroughs of graph-like queries over the supply chain data, organized by complexity route.

## GREEN Queries: Direct SQL

GREEN queries use simple SQL with joins. No handlers needed.

### Query 1: Find a Supplier

```
Question: "Find Acme Corp in the database"
Route: GREEN
```

**SQL:**
```sql
SELECT id, supplier_code, name, tier, country
FROM suppliers
WHERE name = 'Acme Corp';
```

**Result:**
```
 id |  supplier_code  |   name    | tier | country
----+-----------------+-----------+------+---------
 42 | SUPP-042        | Acme Corp |    1 | USA
```

### Query 2: Parts from a Supplier

```
Question: "What parts can Acme Corp supply?"
Route: GREEN (simple join through part_suppliers)
```

**SQL:**
```sql
SELECT p.part_number, p.description, ps.unit_cost
FROM suppliers s
JOIN part_suppliers ps ON s.id = ps.supplier_id
JOIN parts p ON ps.part_id = p.id
WHERE s.name = 'Acme Corp'
AND ps.is_approved = true
ORDER BY p.part_number
LIMIT 10;
```

### Query 3: Orders from a Facility

```
Question: "Recent orders shipped from Chicago Warehouse"
Route: GREEN
```

**SQL:**
```sql
SELECT o.order_number, o.order_date, o.status, o.total_amount
FROM orders o
JOIN facilities f ON o.shipping_facility_id = f.id
WHERE f.name = 'Chicago Warehouse'
AND o.status != 'cancelled'
ORDER BY o.order_date DESC
LIMIT 10;
```

## YELLOW Queries: Recursive Traversal

YELLOW queries require the `traverse()` handler for recursive relationships.

### Query 4: Upstream Suppliers

```
Question: "Find all upstream suppliers for Acme Corp"
Route: YELLOW
Pattern: tier_traversal (upstream_all)
```

**Step 1: Find Acme Corp's ID**
```sql
SELECT id FROM suppliers WHERE name = 'Acme Corp';
-- Returns: 42
```

**Step 2: Traverse upstream**
```python
from virt_graph.handlers import get_connection, traverse

conn = get_connection()

result = traverse(
    conn,
    nodes_table='suppliers',
    edges_table='supplier_relationships',
    edge_from_col='seller_id',
    edge_to_col='buyer_id',
    start_id=42,  # Acme Corp
    direction='inbound',  # Upstream = who supplies TO Acme
    max_depth=10,
)

print(f"Found {result['nodes_visited']} upstream suppliers")
print(f"Max depth: {result['depth_reached']}")
for node in result['nodes'][:5]:
    print(f"  {node['name']} (tier {node['tier']})")
```

**Result:**
```
Found 4 upstream suppliers
Max depth: 2
  GlobalTech Industries (tier 2)
  Pacific Components (tier 3)
  Eastern Electronics (tier 3)
  Summit Materials (tier 3)
```

### Query 5: Tier 3 Suppliers

```
Question: "Find all tier 3 suppliers for Acme Corp"
Route: YELLOW
Pattern: tier_traversal (upstream_by_tier)
```

**Using traverse_collecting:**
```python
from virt_graph.handlers.traversal import traverse_collecting

result = traverse_collecting(
    conn,
    nodes_table='suppliers',
    edges_table='supplier_relationships',
    edge_from_col='seller_id',
    edge_to_col='buyer_id',
    start_id=42,  # Acme Corp
    target_condition="tier = 3",
    direction='inbound',
    max_depth=10,
)

print(f"Found {len(result['matching_nodes'])} tier 3 suppliers")
```

### Query 6: BOM Explosion

```
Question: "Full parts list for the Turbo Encabulator"
Route: YELLOW
Pattern: bom_explosion
```

**Step 1: Find the product's top-level part**
```sql
SELECT pc.part_id, p.part_number
FROM products prod
JOIN product_components pc ON prod.id = pc.product_id
JOIN parts p ON pc.part_id = p.id
WHERE prod.name = 'Turbo Encabulator';
```

**Step 2: Explode BOM**
```python
from virt_graph.handlers.traversal import bom_explode

result = bom_explode(
    conn,
    start_part_id=789,  # Top-level part ID
    max_depth=20,
    include_quantities=True,
)

print(f"Total components: {result['nodes_visited']}")
print(f"BOM depth: {result['depth_reached']}")
for part in result['nodes'][:5]:
    qty = result['quantities'].get(part['id'], 1)
    print(f"  {part['part_number']}: qty={qty}")
```

**Safety Note:**

Large BOMs may hit the MAX_NODES limit (10,000):

```python
from virt_graph.handlers import SubgraphTooLarge

try:
    result = bom_explode(conn, start_part_id=789, max_depth=50)
except SubgraphTooLarge as e:
    print(f"BOM too large: {e}")
    print("Consider: reducing max_depth, filtering by category")
```

### Query 7: Supply Chain Depth

```
Question: "What is the depth of Acme Corp's supply chain?"
Route: YELLOW
Pattern: tier_traversal (depth_analysis)
```

```python
result = traverse(
    conn,
    nodes_table='suppliers',
    edges_table='supplier_relationships',
    edge_from_col='seller_id',
    edge_to_col='buyer_id',
    start_id=42,
    direction='inbound',
    max_depth=20,
)

print(f"Supply chain depth: {result['depth_reached']} tiers")
print(f"Total suppliers in chain: {result['nodes_visited']}")
```

## RED Queries: Network Algorithms

RED queries use NetworkX handlers for pathfinding and centrality analysis.

### Query 8: Cheapest Route

```
Question: "What's the cheapest route from Chicago Warehouse to LA Distribution Center?"
Route: RED
Pattern: shortest_path (cheapest)
```

**Step 1: Find facility IDs**
```sql
SELECT id, name FROM facilities
WHERE name IN ('Chicago Warehouse', 'LA Distribution Center');
```

**Step 2: Find shortest path**
```python
from virt_graph.handlers.pathfinding import shortest_path

result = shortest_path(
    conn,
    nodes_table='facilities',
    edges_table='transport_routes',
    edge_from_col='origin_facility_id',
    edge_to_col='destination_facility_id',
    start_id=1,   # Chicago
    end_id=25,    # LA
    weight_col='cost_usd',
    max_depth=20,
)

print(f"Total cost: ${result['distance']:.2f}")
print(f"Path: {' → '.join(n['name'] for n in result['path_nodes'])}")
```

**Result:**
```
Total cost: $2,450.00
Path: Chicago Warehouse → Dallas Hub → Phoenix DC → LA Distribution Center
```

### Query 9: Fastest Route

```
Question: "Fastest route from Chicago to LA?"
Route: RED
Pattern: shortest_path (fastest)
```

```python
result = shortest_path(
    conn,
    nodes_table='facilities',
    edges_table='transport_routes',
    edge_from_col='origin_facility_id',
    edge_to_col='destination_facility_id',
    start_id=1,
    end_id=25,
    weight_col='transit_time_hours',  # Different weight
    max_depth=20,
)

print(f"Total time: {result['distance']:.1f} hours")
```

### Query 10: Critical Facility

```
Question: "Which facility is most critical to the transport network?"
Route: RED
Pattern: centrality (betweenness)
```

```python
from virt_graph.handlers.network import centrality

result = centrality(
    conn,
    nodes_table='facilities',
    edges_table='transport_routes',
    edge_from_col='origin_facility_id',
    edge_to_col='destination_facility_id',
    centrality_type='betweenness',
    top_n=10,
)

print("Most critical facilities (by betweenness):")
for facility in result['rankings']:
    print(f"  {facility['name']}: {facility['score']:.4f}")
```

**Interpretation:**

- **Betweenness centrality** measures how often a node appears on shortest paths
- High betweenness = critical chokepoint
- Disruption would affect many routes

### Query 11: Isolated Facilities

```
Question: "Are there any facilities not connected to the main network?"
Route: RED
Pattern: components
```

```python
from virt_graph.handlers.network import connected_components

result = connected_components(
    conn,
    nodes_table='facilities',
    edges_table='transport_routes',
    edge_from_col='origin_facility_id',
    edge_to_col='destination_facility_id',
    min_size=1,  # Include singletons
)

if len(result['components']) > 1:
    print(f"Found {len(result['components'])} separate networks!")
    for i, comp in enumerate(result['components']):
        print(f"  Network {i+1}: {len(comp)} facilities")
else:
    print("All facilities are connected")
```

## Safety Limits

All handlers enforce non-negotiable limits:

| Limit | Value | Purpose |
|-------|-------|---------|
| `MAX_DEPTH` | 50 | Prevent infinite recursion |
| `MAX_NODES` | 10,000 | Prevent memory exhaustion |
| `MAX_RESULTS` | 1,000 | Limit result set size |
| `QUERY_TIMEOUT` | 30s | Prevent long-running queries |

### Handling Large Traversals

When a query would exceed limits:

```python
from virt_graph.handlers import SubgraphTooLarge

try:
    result = traverse(conn, ..., max_depth=50)
except SubgraphTooLarge as e:
    print(f"Query too large: estimated {e.estimated_nodes} nodes")
    # Options:
    # 1. Add filters (category, date range)
    # 2. Reduce max_depth
    # 3. Use sampling
```

### Overriding Limits (Advanced)

For trusted queries, limits can be adjusted:

```python
result = traverse(
    conn,
    ...,
    max_nodes=50000,      # Override default 10K limit
    skip_estimation=True, # Skip pre-traversal size check
)
```

**Warning:** Only use overrides when you understand the data size.

## Query Comparison

| Query Type | Route | Handler | Typical Latency |
|------------|-------|---------|-----------------|
| Simple lookup | GREEN | SQL | 1-5ms |
| Join (2 tables) | GREEN | SQL | 1-5ms |
| Upstream suppliers | YELLOW | traverse | 2-10ms |
| BOM explosion | YELLOW | bom_explode | 2-50ms |
| Shortest path | RED | shortest_path | 2-20ms |
| Centrality | RED | centrality | 10-100ms |

## Next Steps

Compare Virtual Graph performance against Neo4j:

1. [**Benchmarks**](benchmark.md) - Run the full benchmark suite
