# Handlers Reference

VG/SQL handlers are schema-parameterized Python functions that enable graph operations over relational data. They accept table and column names as arguments, making them reusable across any schema.

## Handler Summary

| Handler | Module | Category | Description |
|---------|--------|----------|-------------|
| `traverse()` | traversal | Traversal | BFS/DFS traversal with direction control |
| `traverse_collecting()` | traversal | Traversal | Traverse while collecting matching nodes |
| `path_aggregate()` | traversal | Aggregation | Aggregate values along paths (SUM/MAX/MIN/multiply) |
| `shortest_path()` | pathfinding | Algorithm | Dijkstra weighted shortest path |
| `all_shortest_paths()` | pathfinding | Algorithm | All shortest paths between two nodes |
| `centrality()` | network | Algorithm | Degree/betweenness/closeness/PageRank |
| `connected_components()` | network | Algorithm | Find connected subgraphs |
| `graph_density()` | network | Algorithm | Calculate graph density statistics |
| `neighbors()` | network | Algorithm | Direct neighbors of a node |
| `resilience_analysis()` | network | Algorithm | Impact analysis of node removal |

## Common Parameters

All handlers share a common pattern for schema parameterization:

```python
result = handler(
    conn,                    # Database connection
    nodes_table="...",       # Node/entity table name
    edges_table="...",       # Edge/relationship table name
    edge_from_col="...",     # FK column for edge source
    edge_to_col="...",       # FK column for edge target
    # ... handler-specific parameters
)
```

## Traversal and Aggregation Handlers

These handlers use frontier-batched BFS for recursive traversal without loading the full graph into memory.

### traverse()

Multi-hop traversal from a starting node.

```python
from virt_graph.handlers.traversal import traverse

result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=123,
    direction="inbound",  # "inbound", "outbound", or "both"
    max_depth=10,
    include_start=False,
)

# Result structure:
{
    "nodes": [...],           # All discovered nodes
    "total_count": 45,        # Total nodes found
    "depth_reached": 3,       # Maximum depth explored
    "frontier_batches": 4,    # Number of BFS iterations
}
```

### traverse_collecting()

Traverse while collecting nodes that match a condition.

```python
from virt_graph.handlers.traversal import traverse_collecting

result = traverse_collecting(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=123,
    target_condition="tier = 3",  # SQL WHERE clause
    direction="inbound",
    max_depth=10,
)

# Result structure:
{
    "matching_nodes": [...],     # Nodes matching condition
    "matching_paths": {...},     # Paths to each matching node
    "total_traversed": 45,       # Total nodes explored
    "depth_reached": 3,
}
```

### path_aggregate()

Aggregate values along paths (e.g., BOM explosion, cost rollups).

```python
from virt_graph.handlers.traversal import path_aggregate

result = path_aggregate(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="parent_part_id",
    edge_to_col="child_part_id",
    start_id=456,
    value_col="quantity",
    operation="multiply",           # sum, max, min, multiply, count
    max_depth=20,
)

# Result structure:
{
    "aggregates": [...],            # Aggregated values per node
    "total_nodes": 1024,            # Count of unique nodes
    "max_depth": 8,                 # Deepest level reached
    "nodes_visited": 2048,          # Total nodes traversed
}
```

## Algorithm Handlers

These handlers load a subgraph into NetworkX for graph algorithms. Use the Estimator module for pre-flight size checks.

### shortest_path()

Find the shortest path between two nodes (Dijkstra algorithm).

```python
from virt_graph.handlers.pathfinding import shortest_path

result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=1,
    end_id=50,
    weight_col="distance_km",      # Optional: use edge weights
    excluded_nodes=[10, 20],       # Optional: nodes to avoid
)

# Result structure:
{
    "path": [1, 5, 23, 50],        # Node IDs in path order
    "path_nodes": [...],          # Full node data for each
    "distance": 3388.3,           # Total path weight
    "edges": [...],               # Edge data along path
    "nodes_explored": 45,
    "error": None,
}
```

### all_shortest_paths()

Find all shortest paths (equal length) between two nodes.

```python
from virt_graph.handlers.pathfinding import all_shortest_paths

result = all_shortest_paths(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=1,
    end_id=50,
    max_paths=10,                  # Limit number of paths
)

# Result structure:
{
    "paths": [[1, 5, 50], [1, 8, 50], ...],
    "distance": 2,
    "path_count": 3,
    "nodes_explored": 45,
}
```

### centrality()

Calculate node centrality scores.

```python
from virt_graph.handlers.network import centrality

result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",  # degree, betweenness, closeness, pagerank
    top_n=10,
)

# Result structure:
{
    "results": [
        {"node": {...}, "score": 0.2327},
        {"node": {...}, "score": 0.1854},
        ...
    ],
    "centrality_type": "betweenness",
    "graph_stats": {"nodes": 50, "edges": 200, "density": 0.08},
    "nodes_loaded": 50,
}
```

### connected_components()

Find connected subgraphs.

```python
from virt_graph.handlers.network import connected_components

result = connected_components(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    min_size=5,                    # Filter small components
)

# Result structure:
{
    "components": [
        {"component_id": 0, "size": 45, "sample_nodes": [...]},
        {"component_id": 1, "size": 5, "sample_nodes": [...]},
    ],
    "component_count": 2,
    "largest_component_size": 45,
    "isolated_nodes": 0,
}
```

### neighbors()

Get direct neighbors of a node.

```python
from virt_graph.handlers.network import neighbors

result = neighbors(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_id=123,
    direction="both",              # inbound, outbound, or both
)

# Result structure:
{
    "neighbors": [...],            # Full node data
    "outbound_count": 5,
    "inbound_count": 3,
    "total_degree": 8,
}
```

### resilience_analysis()

Analyze impact of removing a node.

```python
from virt_graph.handlers.network import resilience_analysis

result = resilience_analysis(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_to_remove=hub_id,
)

# Result structure:
{
    "node_removed": 123,
    "node_removed_info": {...},
    "disconnected_pairs": 156,
    "components_before": 1,
    "components_after": 3,
    "component_increase": 2,
    "isolated_nodes": 2,
    "affected_node_count": 15,
    "is_critical": True,
}
```

## Pre-flight Estimation

For algorithm handlers that load graphs into memory, use the Estimator to check sizes first:

```python
from virt_graph.estimator import Estimator

estimator = Estimator(conn)

# Check if operation is safe
estimate = estimator.estimate_subgraph(
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
)

if estimate["is_safe"]:
    result = shortest_path(...)
else:
    print(f"Warning: {estimate['node_count']} nodes, {estimate['edge_count']} edges")
```

See [Architecture](architecture.md) for more on estimation.

---

## Traversal Handler Details

The traversal module provides handlers for recursive graph traversal over relational data. These handlers support `recursive_traversal`, `temporal_traversal`, `path_aggregation`, and `hierarchical_aggregation` operation types.

### traverse() — Full Signature

```python
from virt_graph.handlers.traversal import traverse

result = traverse(
    conn,                          # Database connection
    nodes_table,                   # Node/entity table name
    edges_table,                   # Edge/relationship table name
    edge_from_col,                 # FK column for edge source
    edge_to_col,                   # FK column for edge target
    start_id,                      # Starting node ID
    direction="outbound",          # "inbound", "outbound", or "both"
    max_depth=10,                  # Maximum traversal depth
    stop_condition=None,           # SQL WHERE clause for terminal nodes
    collect_columns=None,          # Extra columns to collect from edges
    prefilter_sql=None,            # SQL WHERE clause to filter edges
    include_start=True,            # Include starting node in results
    max_nodes=None,                # Override default node limit
    skip_estimation=False,         # Skip size estimation
    estimation_config=None,        # Custom estimation parameters
    soft_delete_column=None,       # Column name for soft deletes
)
```

### Direction Explained

```
     A ──sells_to──▶ B ──sells_to──▶ C

Direction from B's perspective:
- "outbound": B → C (who does B sell to?)
- "inbound":  A → B (who sells to B?)
- "both":     A ↔ B ↔ C (all connections)
```

### traverse() Result Structure

```python
{
    "nodes": [                    # All discovered nodes
        {"id": 1, "name": "Acme", ...},
        {"id": 2, "name": "Bolt Co", ...},
    ],
    "paths": {                    # Path from start to each node
        2: [1, 2],               # Node 2 reached via: start → 1 → 2
        3: [1, 2, 3],
    },
    "edges": [                    # All traversed edges
        {"from": 1, "to": 2, ...},
    ],
    "depth_reached": 3,           # Maximum depth explored
    "nodes_visited": 45,          # Total nodes encountered
    "terminated_at": None,        # Stop condition node, if hit
}
```

### Example: Find Upstream Suppliers

```python
# "Find all suppliers that feed into Acme Corp"
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",      # Who sells
    edge_to_col="buyer_id",         # To whom
    start_id=acme_id,
    direction="inbound",            # Follow edges pointing TO Acme
    max_depth=10,
    include_start=False,            # Don't include Acme itself
)

print(f"Found {len(result['nodes'])} upstream suppliers")
for node in result['nodes']:
    depth = len(result['paths'][node['id']]) - 1
    print(f"  Tier {depth}: {node['name']}")
```

### Example: Find Downstream with Stop Condition

```python
# "Find all buyers of Acme, but stop at tier-3 suppliers"
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="outbound",           # Follow edges FROM Acme
    max_depth=10,
    stop_condition="tier = 3",      # Stop when hitting tier-3
)

if result['terminated_at']:
    print(f"Stopped at tier-3 supplier: {result['terminated_at']}")
```

### traverse_collecting() — Full Signature

```python
from virt_graph.handlers.traversal import traverse_collecting

result = traverse_collecting(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    start_id,
    target_condition,              # SQL WHERE clause for matching nodes
    direction="outbound",
    max_depth=10,
    max_nodes=None,
    skip_estimation=False,
    soft_delete_column=None,
)
```

### traverse_collecting() Result Structure

```python
{
    "matching_nodes": [...],       # Nodes matching the condition
    "matching_paths": {            # Paths to each matching node
        5: [1, 3, 5],
        8: [1, 2, 8],
    },
    "total_traversed": 45,         # Total nodes explored
    "depth_reached": 4,
}
```

### Example: Find All ISO-Certified Upstream Suppliers

```python
# "Find all ISO9001-certified suppliers in Acme's supply chain"
result = traverse_collecting(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    target_condition="id IN (SELECT supplier_id FROM supplier_certifications WHERE certification_type = 'ISO9001')",
    direction="inbound",
    max_depth=10,
)

print(f"Found {len(result['matching_nodes'])} certified suppliers")
```

### path_aggregate() — Full Signature

```python
from virt_graph.handlers.traversal import path_aggregate

result = path_aggregate(
    conn,                          # Database connection
    nodes_table,                   # Node/entity table name
    edges_table,                   # Edge/relationship table name
    edge_from_col,                 # FK column for edge source
    edge_to_col,                   # FK column for edge target
    start_id,                      # Starting node ID
    value_col,                     # Column containing values to aggregate
    operation="sum",               # "sum", "max", "min", "multiply", "count"
    direction="outbound",          # "inbound" or "outbound"
    max_depth=20,                  # Maximum traversal depth
    max_nodes=None,                # Override node limit
    skip_estimation=False,
    soft_delete_column=None,
)
```

### Aggregation Operations

| Operation | Description | Use Case |
|-----------|-------------|----------|
| `sum` | Sum values at each depth | Cost rollups |
| `max` | Maximum value along path | Critical path duration |
| `min` | Minimum value along path | Bottleneck detection |
| `multiply` | Multiply quantities through hierarchy | BOM explosion |
| `count` | Count nodes at each depth | Network analysis |

### The Diamond Problem

Hierarchical structures often have shared components:

```
        Product A
        /       \
   Assy B      Assy C
   (qty: 2)    (qty: 1)
       \        /
        Part D
        (qty: 3 in B, 5 in C)

Total Part D needed: (2 × 3) + (1 × 5) = 11
```

`path_aggregate()` with `operation="multiply"` handles this correctly using a recursive CTE that aggregates quantities across all paths.

### path_aggregate() Result Structure

```python
{
    "aggregates": [
        {
            "node_id": 123,
            "depth": 3,
            "aggregated_value": 48.0,  # Based on operation
        },
        ...
    ],
    "total_nodes": 1024,               # Unique nodes count
    "max_depth": 8,                    # Deepest level reached
    "nodes_visited": 2048,             # Total nodes traversed
}
```

### Example: BOM Explosion

```python
# "What parts do we need to build a Turbo Encabulator?"
result = path_aggregate(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="parent_part_id",
    edge_to_col="child_part_id",
    start_id=turbo_encabulator_id,
    value_col="quantity",
    operation="multiply",              # Propagate quantities through hierarchy
    max_depth=20,
)

print(f"BOM contains {result['total_nodes']} unique parts")
print(f"Maximum assembly depth: {result['max_depth']}")

# Group by depth level
from collections import defaultdict
by_depth = defaultdict(list)
for agg in result['aggregates']:
    by_depth[agg['depth']].append(agg)

for depth in sorted(by_depth.keys()):
    print(f"\nLevel {depth}: {len(by_depth[depth])} parts")
```

### Example: Cost Rollup

```python
# "Sum costs along the supply chain"
result = path_aggregate(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=end_customer_id,
    value_col="unit_price",
    operation="sum",                   # Sum costs
    direction="inbound",
    max_depth=10,
)
```

### Algorithm: Frontier-Batched BFS

All traversal handlers use the same core algorithm:

```python
# Pseudocode
visited = {start_id}
frontier = [start_id]
depth = 0

while frontier and depth < max_depth and len(visited) < max_nodes:
    # Single query for entire frontier
    query = """
        SELECT * FROM edges
        WHERE from_col = ANY(%s)  -- All frontier nodes at once
    """
    new_edges = execute(query, [frontier])

    # Build next frontier
    next_frontier = []
    for edge in new_edges:
        if edge.to_id not in visited:
            visited.add(edge.to_id)
            next_frontier.append(edge.to_id)

    frontier = next_frontier
    depth += 1
```

Key properties:
- **One query per depth level**, not one per node
- Uses PostgreSQL `= ANY(ARRAY[...])` for efficient IN clause
- Tracks visited nodes to avoid cycles
- Bounded by `max_depth` and `max_nodes`

### Safety Limits

Default limits (from `base.py`):

| Limit | Default | Purpose |
|-------|---------|---------|
| `MAX_DEPTH` | 50 | Absolute depth ceiling |
| `MAX_NODES` | 10,000 | Maximum nodes to visit |
| `MAX_RESULTS` | 100,000 | Maximum rows returned |
| `QUERY_TIMEOUT_SEC` | 30 | Per-query timeout |

Override per-call:

```python
result = traverse(
    ...,
    max_depth=5,        # Shallower than default
    max_nodes=100,      # Fewer nodes
)
```

### Traversal Pre-flight Estimation

For potentially large traversals, the handler automatically samples:

```python
# Estimation happens by default
result = traverse(conn, ..., skip_estimation=False)

# Skip if you know the graph is small
result = traverse(conn, ..., skip_estimation=True)

# Custom estimation config
from virt_graph.estimator import EstimationConfig

config = EstimationConfig(
    base_damping=0.85,
    safety_margin=1.5,
)
result = traverse(conn, ..., estimation_config=config)
```

---

## Pathfinding Handler Details

The pathfinding module provides handlers for finding optimal paths through weighted graphs. These are algorithm operations that load subgraphs into NetworkX.

### shortest_path() — Full Signature

```python
from virt_graph.handlers.pathfinding import shortest_path

result = shortest_path(
    conn,                          # Database connection
    nodes_table,                   # Node/entity table name
    edges_table,                   # Edge/relationship table name
    edge_from_col,                 # FK column for edge source
    edge_to_col,                   # FK column for edge target
    start_id,                      # Starting node ID
    end_id,                        # Target node ID
    weight_col=None,               # Edge weight column (optional)
    max_depth=50,                  # Maximum path length
    excluded_nodes=None,           # Node IDs to avoid
    soft_delete_column=None,       # Column for soft deletes
)
```

### shortest_path() Result Structure

```python
{
    "path": [1, 5, 23, 50],        # Node IDs in path order
    "path_nodes": [                # Full node data
        {"id": 1, "name": "Chicago", ...},
        {"id": 5, "name": "Denver", ...},
        {"id": 23, "name": "Phoenix", ...},
        {"id": 50, "name": "Los Angeles", ...},
    ],
    "distance": 3388.3,            # Total path weight (or hop count)
    "edges": [                     # Edge data along path
        {"from": 1, "to": 5, "distance_km": 1500, ...},
        {"from": 5, "to": 23, "distance_km": 900, ...},
        {"from": 23, "to": 50, "distance_km": 988.3, ...},
    ],
    "nodes_explored": 45,          # Nodes loaded during search
    "excluded_nodes": [],          # Nodes that were excluded
    "error": None,                 # Error message if no path found
}
```

### Example: Shortest Route by Distance

```python
# "What's the shortest route from Chicago to Los Angeles?"
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

if result["path"]:
    print(f"Route: {' → '.join(n['name'] for n in result['path_nodes'])}")
    print(f"Total distance: {result['distance']:,.1f} km")
    print(f"Hops: {len(result['path']) - 1}")
else:
    print(f"No path found: {result['error']}")
```

### Example: Cheapest Route by Cost

```python
# "What's the cheapest shipping route?"
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="cost_usd",         # Use cost instead of distance
)

print(f"Total cost: ${result['distance']:,.2f}")
```

### Example: Avoid Specific Nodes

```python
# "Route from Chicago to LA avoiding Denver"
denver_id = 5

result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="distance_km",
    excluded_nodes=[denver_id],    # Skip Denver
)
```

### Unweighted Paths

If `weight_col` is not specified, the handler finds the path with fewest hops:

```python
# "Shortest path by number of transfers"
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    # No weight_col → minimize hops
)

print(f"Minimum transfers: {len(result['path']) - 1}")
```

### all_shortest_paths() — Full Signature

```python
from virt_graph.handlers.pathfinding import all_shortest_paths

result = all_shortest_paths(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    start_id,
    end_id,
    max_paths=10,                  # Limit number of paths returned
    weight_col=None,               # Edge weight column (optional)
    max_depth=50,
    soft_delete_column=None,
)
```

### all_shortest_paths() Result Structure

```python
{
    "paths": [
        [1, 5, 50],                # Path 1
        [1, 8, 50],                # Path 2 (same length)
        [1, 12, 50],               # Path 3 (same length)
    ],
    "path_nodes": [                # Full node data for all paths
        [{"id": 1, ...}, {"id": 5, ...}, {"id": 50, ...}],
        [{"id": 1, ...}, {"id": 8, ...}, {"id": 50, ...}],
        ...
    ],
    "distance": 2,                 # Path length (shared by all)
    "path_count": 3,               # Number of paths found
    "nodes_explored": 45,
}
```

### Example: Alternative Routes

```python
# "What are all the 2-hop routes from Chicago to LA?"
result = all_shortest_paths(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    max_paths=5,
)

print(f"Found {result['path_count']} routes of length {result['distance']}")
for i, path_nodes in enumerate(result['path_nodes'], 1):
    route = ' → '.join(n['name'] for n in path_nodes)
    print(f"  Route {i}: {route}")
```

### Pathfinding Algorithm: Bidirectional BFS

The pathfinding handlers use an optimized approach:

```
Step 1: Bidirectional BFS to find relevant subgraph

        Start ──────────────▶ ◀────────────── End
               Forward BFS      Backward BFS

        Meet in middle → subgraph identified

Step 2: Load subgraph into NetworkX

Step 3: Run Dijkstra on in-memory graph
```

This is more efficient than loading the entire graph because it only fetches nodes reachable from both start and end within the depth limit.

### Why Not Pure SQL?

SQL can do recursive CTEs, but:
- No native Dijkstra implementation
- Complex to handle multiple weight columns
- Hard to return all equal-length paths
- NetworkX has battle-tested implementations

The trade-off: load subgraph into memory, get reliable algorithms.

### Weight Handling

Weights are converted from SQL types to Python floats:

```python
# Decimal columns work automatically
weight_col="cost_usd"      # Decimal(10,2) → float

# Integer columns work too
weight_col="transit_hours" # Integer → float
```

Missing or NULL weights are treated as infinite (path avoided).

### Pathfinding Memory Considerations

Pathfinding loads the relevant subgraph into memory. For large graphs:

1. **Use depth limits**:
   ```python
   result = shortest_path(..., max_depth=10)  # Limit search radius
   ```

2. **Check size first**:
   ```python
   from virt_graph.estimator import GraphSampler

   sampler = GraphSampler(conn, "transport_routes", "origin_facility_id", "destination_facility_id")
   sample = sampler.sample(start_id, depth=3)

   if sample.estimated_total > 50000:
       print("Warning: Large graph")
   ```

3. **Exclude irrelevant nodes**:
   ```python
   result = shortest_path(..., excluded_nodes=irrelevant_ids)
   ```

### Pathfinding Error Cases

The handler returns errors in the result rather than raising exceptions:

```python
result = shortest_path(...)

if result["error"]:
    print(f"Failed: {result['error']}")
    # Common errors:
    # - "No path exists between start and end"
    # - "Start node not found"
    # - "End node not found"
else:
    print(f"Path found: {result['path']}")
```

---

## Network Handler Details

The network module provides handlers for graph-wide analysis algorithms. These are algorithm operations that load the full graph into NetworkX.

### centrality() — Full Signature

```python
from virt_graph.handlers.network import centrality

result = centrality(
    conn,                          # Database connection
    nodes_table,                   # Node/entity table name
    edges_table,                   # Edge/relationship table name
    edge_from_col,                 # FK column for edge source
    edge_to_col,                   # FK column for edge target
    centrality_type="betweenness", # Algorithm to use
    top_n=10,                      # Number of results to return
    weight_col=None,               # Edge weight column (optional)
    id_column="id",                # Node ID column name
    soft_delete_column=None,
)
```

### Centrality Types

| Type | Measures | Best For |
|------|----------|----------|
| `degree` | Number of connections | Finding highly connected nodes |
| `betweenness` | How often node is on shortest paths | Finding bridges/gatekeepers |
| `closeness` | Average distance to all other nodes | Finding central locations |
| `pagerank` | Importance based on incoming links | Finding influential nodes |

### centrality() Result Structure

```python
{
    "results": [
        {"node": {"id": 1, "name": "New York Factory", ...}, "score": 0.2327},
        {"node": {"id": 5, "name": "Chicago Hub", ...}, "score": 0.1854},
        ...
    ],
    "centrality_type": "betweenness",
    "graph_stats": {
        "nodes": 50,
        "edges": 197,
        "density": 0.08,
    },
    "nodes_loaded": 50,
}
```

### Example: Find Most Central Facility

```python
# "Which facility is most central to our logistics network?"
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10,
)

print("Top 10 most central facilities:")
for item in result['results']:
    print(f"  {item['node']['name']}: {item['score']:.4f}")
```

### Example: Find Hub Suppliers

```python
# "Which suppliers have the most connections?"
result = centrality(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    centrality_type="degree",
    top_n=10,
)
```

### Example: Weighted Centrality

```python
# "Which facility handles the most shipping volume?"
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    weight_col="volume",           # Weight by shipping volume
    top_n=5,
)
```

### connected_components() — Full Signature

```python
from virt_graph.handlers.network import connected_components

result = connected_components(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    min_size=1,                    # Minimum component size to return
    id_column="id",
    soft_delete_column=None,
)
```

### connected_components() Result Structure

```python
{
    "components": [
        {
            "component_id": 0,
            "size": 45,
            "node_ids": [1, 2, 3, ...],
            "sample_nodes": [          # First few nodes with details
                {"id": 1, "name": "Acme", ...},
                ...
            ],
        },
        {
            "component_id": 1,
            "size": 5,
            "node_ids": [46, 47, 48, 49, 50],
            "sample_nodes": [...],
        },
    ],
    "component_count": 2,
    "largest_component_size": 45,
    "isolated_nodes": 0,               # Nodes with no connections
    "nodes_loaded": 50,
}
```

### Example: Find Isolated Supplier Networks

```python
# "Are there disconnected supplier networks?"
result = connected_components(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    min_size=2,                    # Ignore singletons
)

if result['component_count'] > 1:
    print(f"Warning: {result['component_count']} disconnected networks")
    for comp in result['components']:
        print(f"  Component {comp['component_id']}: {comp['size']} suppliers")
else:
    print("All suppliers are connected")
```

### graph_density() — Full Signature

```python
from virt_graph.handlers.network import graph_density

result = graph_density(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    id_column="id",
    soft_delete_column=None,
)
```

### graph_density() Result Structure

```python
{
    "nodes": 50,
    "edges": 197,
    "density": 0.0804,             # edges / possible_edges
    "avg_degree": 7.88,            # average connections per node
    "is_connected": True,          # single component?
    "components": 1,
    "diameter": 5,                 # longest shortest path (if connected)
}
```

### Example: Network Health Check

```python
result = graph_density(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
)

print(f"Network has {result['nodes']} facilities, {result['edges']} routes")
print(f"Density: {result['density']:.2%}")
print(f"Average connections per facility: {result['avg_degree']:.1f}")
print(f"Connected: {result['is_connected']}")
```

### neighbors() — Full Signature

```python
from virt_graph.handlers.network import neighbors

result = neighbors(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    node_id,                       # Node to find neighbors of
    direction="both",              # "inbound", "outbound", or "both"
    id_column="id",
    soft_delete_column=None,
)
```

### neighbors() Result Structure

```python
{
    "neighbors": [
        {"id": 5, "name": "Denver", "direction": "outbound", ...},
        {"id": 8, "name": "Detroit", "direction": "inbound", ...},
        ...
    ],
    "outbound_count": 3,           # Nodes this node connects TO
    "inbound_count": 5,            # Nodes that connect to THIS node
    "total_degree": 8,             # Total connections
}
```

### Example: Direct Connections

```python
# "What facilities connect directly to Chicago?"
result = neighbors(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_id=chicago_id,
    direction="both",
)

print(f"Chicago has {result['total_degree']} direct connections")
print(f"  Ships to: {result['outbound_count']} facilities")
print(f"  Receives from: {result['inbound_count']} facilities")
```

### resilience_analysis() — Full Signature

```python
from virt_graph.handlers.network import resilience_analysis

result = resilience_analysis(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    node_to_remove,                # Node ID to simulate removing
    id_column="id",
    soft_delete_column=None,
)
```

### resilience_analysis() Result Structure

```python
{
    "node_removed": 5,
    "node_removed_info": {"id": 5, "name": "Chicago Hub", ...},
    "disconnected_pairs": 156,     # Node pairs that can no longer reach each other
    "components_before": 1,
    "components_after": 3,
    "component_increase": 2,
    "isolated_nodes": 2,           # Nodes with no remaining connections
    "affected_node_count": 15,     # Nodes whose connectivity changed
    "is_critical": True,           # True if removal splits the graph
}
```

### Example: Single Point of Failure Analysis

```python
# "What happens if our Chicago hub goes offline?"
result = resilience_analysis(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_to_remove=chicago_id,
)

if result['is_critical']:
    print(f"CRITICAL: Removing {result['node_removed_info']['name']} would:")
    print(f"  - Split network into {result['components_after']} pieces")
    print(f"  - Disconnect {result['disconnected_pairs']} facility pairs")
    print(f"  - Isolate {result['isolated_nodes']} facilities completely")
else:
    print("This node is not a single point of failure")
```

### Example: Find All Critical Nodes

```python
# "Which facilities are single points of failure?"
from virt_graph.handlers.network import centrality, resilience_analysis

# Start with most central nodes (likely candidates)
central = centrality(conn, ..., centrality_type="betweenness", top_n=10)

critical_nodes = []
for item in central['results']:
    node_id = item['node']['id']
    analysis = resilience_analysis(conn, ..., node_to_remove=node_id)
    if analysis['is_critical']:
        critical_nodes.append({
            'node': item['node'],
            'disconnected_pairs': analysis['disconnected_pairs'],
        })

print(f"Found {len(critical_nodes)} critical nodes")
```

### Network Memory Warning

All network handlers load the **full graph** into memory. This is unavoidable for algorithms like centrality and connected components that need global visibility.

#### Mitigation Strategies

1. **Check size first**:
   ```python
   result = graph_density(conn, ...)
   if result['nodes'] > 10000:
       print(f"Warning: {result['nodes']} nodes will be loaded")
   ```

2. **Use soft deletes** to exclude inactive nodes:
   ```python
   result = centrality(conn, ..., soft_delete_column="deleted_at")
   ```

3. **Consider sampling** for very large graphs (not yet implemented in VG/SQL).

## Next Steps

- [Architecture](architecture.md) - System design and estimation
- [Ontology System](ontology-system.md) - Understanding operation types
- [VG Extensions](vg-extensions.md) - Annotation reference
