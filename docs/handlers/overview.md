# Handlers Overview

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

See [Architecture](../concepts/architecture.md) for more on estimation.
