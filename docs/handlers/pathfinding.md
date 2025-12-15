# Pathfinding Handlers

The pathfinding module provides handlers for finding optimal paths through weighted graphs. These are algorithm operations that load subgraphs into NetworkX.

## Overview

| Handler | Purpose |
|---------|---------|
| `shortest_path()` | Find the single shortest/cheapest path between two nodes |
| `all_shortest_paths()` | Find all paths of equal minimum length |

## shortest_path()

Find the shortest (or cheapest) path between two nodes using Dijkstra's algorithm.

### Signature

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

### Result Structure

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

## all_shortest_paths()

Find all paths of equal minimum length between two nodes.

### Signature

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

### Result Structure

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

## Algorithm: Bidirectional BFS

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

## Weight Handling

Weights are converted from SQL types to Python floats:

```python
# Decimal columns work automatically
weight_col="cost_usd"      # Decimal(10,2) → float

# Integer columns work too
weight_col="transit_hours" # Integer → float
```

Missing or NULL weights are treated as infinite (path avoided).

## Memory Considerations

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

## Error Cases

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

## Next Steps

- [Network Handlers](network.md) - Centrality, components, resilience
- [Traversal Handlers](traversal.md) - BFS traversal without weights
- [Complexity Levels](../concepts/complexity-levels.md) - When to use pathfinding
