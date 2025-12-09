# Handler Cookbook

This cookbook provides practical patterns for using Virtual Graph handlers. Each pattern is shown with generic syntax and concrete supply chain examples.

## Quick Reference

| Handler | Use Case | Complexity |
|---------|----------|------------|
| `traverse()` | Multi-hop graph traversal | YELLOW |
| `traverse_collecting()` | Traverse and filter by condition | YELLOW |
| `bom_explode()` | Hierarchical BOM explosion | YELLOW |
| `shortest_path()` | Optimal path between two nodes | RED |
| `all_shortest_paths()` | Multiple optimal paths | RED |
| `centrality()` | Node importance ranking | RED |
| `connected_components()` | Graph clustering | RED |
| `resilience_analysis()` | Impact of node removal | RED |
| `neighbors()` | Direct connections only | RED |
| `graph_density()` | Network statistics | RED |

---

## YELLOW Handlers: Recursive Traversal

### traverse() - Generic Pattern

```python
from virt_graph.handlers import traverse

result = traverse(
    conn,
    nodes_table="{nodes_table}",       # Table containing nodes
    edges_table="{edges_table}",       # Table containing edges
    edge_from_col="{from_column}",     # FK column for edge source
    edge_to_col="{to_column}",         # FK column for edge target
    start_id={start_node_id},          # Starting node ID
    direction="outbound",              # "inbound", "outbound", or "both"
    max_depth=10,                      # How many hops to traverse
    include_start=False,               # Include starting node in results?
    stop_condition=None,               # SQL WHERE clause to stop at
    max_nodes=10000,                   # Override default limit
)
```

**Returns `TraverseResult`:**
```python
{
    "nodes": [...],           # List of node dicts with all columns
    "paths": {id: [path]},    # Map node_id → path from start
    "edges": [(from, to)],    # Traversed edges
    "depth_reached": int,     # Actual max depth found
    "nodes_visited": int,     # Total unique nodes
    "terminated_at": [...],   # IDs where stop_condition matched
}
```

### traverse() - Direction Semantics

The `direction` parameter controls which way edges are followed:

| Direction | Follows | Use Case |
|-----------|---------|----------|
| `"outbound"` | edge_from → edge_to | Find downstream/children |
| `"inbound"` | edge_to → edge_from | Find upstream/parents |
| `"both"` | Both directions | Find all connected nodes |

**Example: Upstream vs Downstream**

```python
# Find all UPSTREAM suppliers (who sells TO this company)
# Edge direction: seller_id → buyer_id
# "inbound" means: find nodes where edge points TO our start node
upstream = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=company_id,
    direction="inbound",   # Follow edges arriving at start
    max_depth=10,
)

# Find all DOWNSTREAM customers (who this company sells TO)
downstream = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=company_id,
    direction="outbound",  # Follow edges leaving start
    max_depth=10,
)
```

### traverse() - Stop Conditions

Stop traversal when reaching nodes matching a SQL condition:

```python
# Stop when reaching tier 1 suppliers
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=tier3_supplier_id,
    direction="outbound",
    max_depth=10,
    stop_condition="tier = 1",  # SQL WHERE clause
    include_start=True,
)

# Access where traversal stopped
tier1_nodes = [n for n in result['nodes'] if n['id'] in result['terminated_at']]

# Access the path to each terminus
for node in tier1_nodes:
    path = result['paths'].get(node['id'], [])
    print(f"Path to {node['name']}: {len(path)} hops")
```

### traverse() - Nodes at Exact Distance

Filter results to find nodes at a specific hop count:

```python
result = traverse(
    conn,
    nodes_table="{nodes_table}",
    edges_table="{edges_table}",
    edge_from_col="{from_col}",
    edge_to_col="{to_col}",
    start_id=start_id,
    direction="both",
    max_depth=2,
    include_start=True,
)

# Filter to exactly 2 hops (path includes start, so length = 3)
exactly_2_hops = [
    n for n in result['nodes']
    if len(result['paths'].get(n['id'], [])) == 3
]
```

### traverse_collecting() - Filter During Traversal

Collect only nodes matching a condition while continuing traversal:

```python
from virt_graph.handlers import traverse_collecting

result = traverse_collecting(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=start_id,
    direction="inbound",
    max_depth=10,
    target_condition="tier = 2",  # Only collect tier 2 suppliers
)
# Result contains only tier 2 suppliers, but traversal continued through them
```

### bom_explode() - Hierarchical Explosion

Specialized handler for bill-of-materials with quantity aggregation:

```python
from virt_graph.handlers import bom_explode

result = bom_explode(
    conn,
    start_part_id=part_id,
    max_depth=20,
    include_quantities=True,  # Aggregate quantities along paths
    max_nodes=10000,
)
```

**Returns `BomExplodeResult`:**
```python
{
    "components": [...],     # Parts with depth and quantity info
    "total_parts": int,      # Unique part count
    "max_depth": int,        # Deepest BOM level
    "nodes_visited": int,    # Total nodes processed
}
```

**Common BOM Patterns:**

```python
# Full BOM explosion with cost rollup
result = bom_explode(conn, start_part_id=product_part_id, max_depth=20, include_quantities=True)

total_cost = sum(
    float(comp.get('unit_cost', 0) or 0) * comp.get('quantity', 1)
    for comp in result['components']
)

# Find leaf components (no children)
leaf_parts = [c for c in result['components'] if c.get('is_leaf', False)]

# Find deepest path
max_depth = result['max_depth']
```

### Where-Used Analysis (Reverse BOM)

Find all assemblies that use a component:

```python
# Traverse UP the BOM hierarchy (child → parent)
result = traverse(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="child_part_id",    # FROM child
    edge_to_col="parent_part_id",     # TO parent
    start_id=component_id,
    direction="outbound",             # Follow child→parent direction
    max_depth=10,
    include_start=False,
)

# result['nodes'] contains all assemblies using this component
print(f"Used in {len(result['nodes'])} assemblies")
```

---

## RED Handlers: Network Algorithms

### shortest_path() - Optimal Route

Find the optimal path between two nodes:

```python
from virt_graph.handlers import shortest_path

result = shortest_path(
    conn,
    nodes_table="{nodes_table}",
    edges_table="{edges_table}",
    edge_from_col="{from_col}",
    edge_to_col="{to_col}",
    start_id=start_id,
    end_id=end_id,
    weight_col="distance_km",     # Column for edge weight (or None for hop count)
    max_depth=20,
    excluded_nodes=None,          # Node IDs to route around
)
```

**Returns `ShortestPathResult`:**
```python
{
    "path": [1, 5, 8, 12],         # Node IDs from start to end
    "path_nodes": [...],          # Full node details
    "distance": 3388.3,           # Total weight
    "edges": [...],               # Edge details
    "nodes_explored": int,        # Graph size
    "excluded_nodes": [],         # What was excluded
    "error": None,                # Error if no path
}
```

**Different Weight Types:**

```python
# By distance (km, miles, etc.)
by_distance = shortest_path(conn, ..., weight_col="distance_km")

# By cost (currency)
by_cost = shortest_path(conn, ..., weight_col="cost_usd")

# By time (hours, minutes)
by_time = shortest_path(conn, ..., weight_col="transit_time_hours")

# By hop count (unweighted)
by_hops = shortest_path(conn, ..., weight_col=None)
```

### shortest_path() - Avoiding Nodes

Route around specific nodes (e.g., failed facilities):

```python
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="distance_km",
    excluded_nodes=[denver_id, seattle_id],  # Route around these
)

# Result path will not include Denver or Seattle
assert denver_id not in result['path']
```

### all_shortest_paths() - Multiple Routes

Find multiple optimal paths (k-shortest paths):

```python
from virt_graph.handlers import all_shortest_paths

result = all_shortest_paths(
    conn,
    nodes_table="{nodes_table}",
    edges_table="{edges_table}",
    edge_from_col="{from_col}",
    edge_to_col="{to_col}",
    start_id=start_id,
    end_id=end_id,
    weight_col="cost_usd",
    max_paths=5,                  # Return up to 5 paths
    excluded_nodes=None,
)
```

**Returns `AllShortestPathsResult`:**
```python
{
    "paths": [[1,5,8], [1,3,8]],   # Multiple path options
    "distance": 2500.0,            # Common optimal distance
    "path_count": 2,               # Number found
    "nodes_explored": int,
    "excluded_nodes": [],
    "error": None,
}
```

### centrality() - Node Importance

Rank nodes by various centrality measures:

```python
from virt_graph.handlers import centrality

result = centrality(
    conn,
    nodes_table="{nodes_table}",
    edges_table="{edges_table}",
    edge_from_col="{from_col}",
    edge_to_col="{to_col}",
    centrality_type="betweenness",  # Type of centrality
    top_n=10,                       # Return top N nodes
)
```

**Returns `CentralityResult`:**
```python
{
    "results": [
        {"node": {...}, "score": 0.2327},
        {"node": {...}, "score": 0.1854},
    ],
    "centrality_type": "betweenness",
    "graph_stats": {"nodes": 50, "edges": 120, "density": 0.05},
    "nodes_loaded": 50,
}
```

**Centrality Types:**

| Type | Measures | Use Case |
|------|----------|----------|
| `"degree"` | Connection count | Most connected hubs |
| `"betweenness"` | Bridge importance | Chokepoints, bottlenecks |
| `"closeness"` | Average distance to all | Central location |
| `"pagerank"` | Recursive importance | Flow importance |

```python
# Find most connected nodes (hubs)
hubs = centrality(conn, ..., centrality_type="degree", top_n=5)

# Find chokepoints (critical bridges)
chokepoints = centrality(conn, ..., centrality_type="betweenness", top_n=5)

# Find best-positioned nodes (lowest average distance)
central = centrality(conn, ..., centrality_type="closeness", top_n=5)

# Find most important by network flow
important = centrality(conn, ..., centrality_type="pagerank", top_n=5)
```

### connected_components() - Graph Clusters

Find isolated subgraphs:

```python
from virt_graph.handlers import connected_components

result = connected_components(
    conn,
    nodes_table="{nodes_table}",
    edges_table="{edges_table}",
    edge_from_col="{from_col}",
    edge_to_col="{to_col}",
    min_size=1,  # Minimum component size to return
)
```

**Returns:**
```python
{
    "components": [
        {"id": 0, "size": 48, "nodes": [1, 2, 3, ...]},
        {"id": 1, "size": 2, "nodes": [49, 50]},
    ],
    "total_components": 2,
    "largest_component_size": 48,
    "isolated_nodes": [],
}
```

**Common Patterns:**

```python
# Check if network is fully connected
result = connected_components(conn, ..., min_size=1)
is_connected = result['total_components'] == 1

# Find isolated nodes
isolated = result.get('isolated_nodes', [])
if isolated:
    print(f"Warning: {len(isolated)} isolated nodes found")
```

### resilience_analysis() - Node Removal Impact

Simulate removing a node to analyze network resilience:

```python
from virt_graph.handlers import resilience_analysis

result = resilience_analysis(
    conn,
    nodes_table="{nodes_table}",
    edges_table="{edges_table}",
    edge_from_col="{from_col}",
    edge_to_col="{to_col}",
    node_to_remove=critical_hub_id,
)
```

**Returns `ResilienceResult`:**
```python
{
    "node_removed": 5,
    "node_removed_info": {"name": "Denver Hub", ...},
    "disconnected_pairs": [(2, 8), (3, 8)],  # Pairs losing connectivity
    "components_before": 1,
    "components_after": 3,
    "component_increase": 2,
    "isolated_nodes": [12, 15],
    "affected_node_count": 4,
    "is_critical": True,
    "error": None,
}
```

**Use Case: Find Critical Infrastructure**

```python
# Find most critical node by betweenness
top_critical = centrality(conn, ..., centrality_type="betweenness", top_n=1)
critical_id = top_critical['results'][0]['node']['id']

# Analyze impact of its removal
impact = resilience_analysis(conn, ..., node_to_remove=critical_id)

if impact['is_critical']:
    print(f"Removing this node creates {impact['component_increase']} new components")
    print(f"Disconnected pairs: {len(impact['disconnected_pairs'])}")
```

### neighbors() - Direct Connections

Get immediate neighbors without full traversal:

```python
from virt_graph.handlers import neighbors

result = neighbors(
    conn,
    nodes_table="{nodes_table}",
    edges_table="{edges_table}",
    edge_from_col="{from_col}",
    edge_to_col="{to_col}",
    node_id=center_id,
    direction="both",  # "inbound", "outbound", or "both"
)
# Returns {"neighbors": [...], "count": N}
```

---

## Mixed Patterns: Combining Complexities

Many real queries combine GREEN (SQL), YELLOW (traversal), and RED (algorithms).

### Pattern: Traversal + Aggregation

```python
# YELLOW: Get all nodes in network
result = traverse(conn, ..., start_id=start_id, direction="inbound", max_depth=10)
node_ids = [n['id'] for n in result['nodes']]

# GREEN: Aggregate data for those nodes
cur.execute("""
    SELECT SUM(inventory_value)
    FROM inventory
    WHERE facility_id = ANY(%s)
""", (node_ids,))
total_value = cur.fetchone()[0]
```

### Pattern: Lookup + BOM + Check

```python
# GREEN: Find product
cur.execute("SELECT id FROM products WHERE name = %s", (product_name,))
product_id = cur.fetchone()[0]

# Get product's top-level parts
cur.execute("SELECT part_id, quantity FROM product_components WHERE product_id = %s", (product_id,))
top_parts = cur.fetchall()

# YELLOW: Explode BOM for each
shortages = []
for part_id, qty in top_parts:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=True)

    for comp in result['components']:
        needed = comp['quantity'] * qty * build_quantity

        # GREEN: Check inventory
        cur.execute("""
            SELECT COALESCE(SUM(quantity_on_hand - quantity_reserved), 0)
            FROM inventory WHERE part_id = %s
        """, (comp['id'],))
        available = cur.fetchone()[0]

        if available < needed:
            shortages.append((comp['part_number'], needed, available))
```

### Pattern: Centrality + Business Metrics

```python
# RED: Get network centrality
result = centrality(conn, ..., centrality_type="degree", top_n=50)

# GREEN: Enrich with business data
for item in result['results']:
    node_id = item['node']['id']
    degree_score = item['score']

    cur.execute("""
        SELECT COALESCE(SUM(quantity_on_hand * unit_cost), 0)
        FROM inventory i
        JOIN parts p ON i.part_id = p.id
        WHERE i.facility_id = %s
    """, (node_id,))
    inventory_value = float(cur.fetchone()[0])

    # Combined criticality score
    criticality = degree_score * (inventory_value / 1_000_000)
    item['criticality'] = criticality

# Sort by combined score
result['results'].sort(key=lambda x: x.get('criticality', 0), reverse=True)
```

---

## Safety and Performance

### Configurable Limits

Override default limits when needed:

```python
# Increase node limit for large graphs
result = traverse(conn, ..., max_nodes=50000)

# Skip size estimation (you take responsibility)
result = traverse(conn, ..., skip_estimation=True)

# Custom estimation config
from virt_graph.estimator import EstimationConfig
result = traverse(conn, ..., estimation_config=EstimationConfig(
    damping_factor=0.7,
    safety_margin=1.2,
))
```

### Default Safety Limits

| Limit | Default | Purpose |
|-------|---------|---------|
| `MAX_DEPTH` | 50 | Prevent infinite recursion |
| `MAX_NODES` | 10,000 | Prevent memory exhaustion |
| `MAX_RESULTS` | 1,000 | Limit response size |
| `QUERY_TIMEOUT` | 30s | Prevent runaway queries |

### Size Estimation

Check before large traversals:

```python
from virt_graph.estimator import check_guards, GraphSampler

sampler = GraphSampler(conn, edges_table, edge_from_col, edge_to_col)
sample = sampler.sample(start_id, depth=5)
result = check_guards(sample, max_depth=20, max_nodes=10000)

if result.safe_to_proceed:
    # Run traversal
    pass
elif result.recommendation == "switch_to_networkx":
    # Use RED handlers instead
    pass
else:
    # Abort or reduce scope
    pass
```

---

## Error Handling

All handlers return structured errors rather than raising exceptions for expected conditions:

```python
result = shortest_path(conn, ..., start_id=a, end_id=b)

if result['error']:
    print(f"No path found: {result['error']}")
elif result['path'] is None:
    print("No path exists between these nodes")
else:
    print(f"Path found: {len(result['path'])} hops, {result['distance']} total weight")
```

For safety limit violations, handlers raise exceptions:

```python
from virt_graph.handlers.base import SafetyLimitExceeded, SubgraphTooLarge

try:
    result = traverse(conn, ..., max_depth=100)
except SafetyLimitExceeded as e:
    print(f"Safety limit exceeded: {e}")
except SubgraphTooLarge as e:
    print(f"Graph too large: {e}")
```
