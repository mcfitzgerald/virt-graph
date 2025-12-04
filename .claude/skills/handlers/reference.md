# Handler Interface Reference

Complete documentation for all Virtual Graph handlers.

## Traversal Handlers

### traverse()

Generic graph traversal using iterative frontier-batched BFS.

**Location:** `src/virt_graph/handlers/traversal.py`

**Signature:**
```python
def traverse(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    direction: str = "outbound",
    max_depth: int = 10,
    stop_condition: str | None = None,
    collect_columns: list[str] | None = None,
    prefilter_sql: str | None = None,
    include_start: bool = True,
    id_column: str = "id",
) -> dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conn` | Connection | PostgreSQL database connection |
| `nodes_table` | str | Table containing nodes (e.g., "suppliers") |
| `edges_table` | str | Table containing edges (e.g., "supplier_relationships") |
| `edge_from_col` | str | Column for edge source (e.g., "seller_id") |
| `edge_to_col` | str | Column for edge target (e.g., "buyer_id") |
| `start_id` | int | Starting node ID |
| `direction` | str | "outbound", "inbound", or "both" |
| `max_depth` | int | Maximum traversal depth (clamped to MAX_DEPTH=50) |
| `stop_condition` | str | SQL WHERE fragment for terminal nodes (e.g., "tier = 3") |
| `collect_columns` | list | Columns to return from nodes (None = all) |
| `prefilter_sql` | str | SQL WHERE to filter edges (e.g., "is_active = true") |
| `include_start` | bool | Whether to include start node in results |
| `id_column` | str | Name of ID column in nodes_table |

**Returns:**
```python
{
    "nodes": [                    # List of reached node dicts
        {"id": 1, "name": "...", ...},
        ...
    ],
    "paths": {                    # Dict mapping node_id → path from start
        42: [42],
        55: [42, 55],
        ...
    },
    "edges": [                    # List of traversed edge tuples
        (42, 55),
        (55, 78),
        ...
    ],
    "depth_reached": 3,           # Actual max depth encountered
    "nodes_visited": 28,          # Total nodes visited
    "terminated_at": [99, 101],   # Nodes where stop_condition matched
}
```

**Direction semantics:**
- `"outbound"`: Follow edges in their natural direction (from→to)
- `"inbound"`: Follow edges backwards (to→from)
- `"both"`: Follow edges in both directions (undirected traversal)

**Example:**
```python
# Find all upstream suppliers from Acme Corp
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,  # Acme Corp
    direction="inbound",  # upstream
    max_depth=10,
)
```

---

### traverse_collecting()

Traverse graph and collect all nodes matching a target condition.

**Signature:**
```python
def traverse_collecting(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    target_condition: str,
    direction: str = "outbound",
    max_depth: int = 10,
    collect_columns: list[str] | None = None,
    id_column: str = "id",
) -> dict[str, Any]
```

**Additional Parameter:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `target_condition` | str | SQL WHERE clause for target nodes (e.g., "tier = 3") |

**Returns:**
```python
{
    "matching_nodes": [...],      # Only nodes matching target_condition
    "matching_paths": {...},      # Paths to matching nodes
    "total_traversed": 50,        # Total nodes visited during search
    "depth_reached": 3,
}
```

**Difference from `traverse`:**
- `traverse` with `stop_condition`: Stops expansion at matching nodes but includes all visited
- `traverse_collecting`: Returns only nodes matching condition (filters result)

**Example:**
```python
# Find all tier 3 suppliers reachable from Acme Corp
result = traverse_collecting(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,
    target_condition="tier = 3",
    direction="inbound",
)
```

---

### bom_explode()

Explode a Bill of Materials with quantity aggregation.

**Signature:**
```python
def bom_explode(
    conn: PgConnection,
    start_part_id: int,
    max_depth: int = 20,
    include_quantities: bool = True,
) -> dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_part_id` | int | Top-level part ID to explode |
| `max_depth` | int | Maximum BOM depth |
| `include_quantities` | bool | Whether to aggregate quantities along paths |

**Returns:**
```python
{
    "nodes": [...],               # All component parts
    "paths": {...},               # Path from top-level to each component
    "quantities": {               # Aggregated quantities (if include_quantities)
        789: 1,                   # Start part
        123: 4,                   # 4 of this part needed
        456: 8,                   # 8 of this part needed
        ...
    },
    "depth_reached": 12,
    "nodes_visited": 342,
}
```

**Note:** This is a convenience wrapper around `traverse` with BOM-specific settings. The quantity aggregation multiplies quantities along the path.

---

## Pathfinding Handlers

### shortest_path()

Find shortest path between two nodes using Dijkstra.

**Location:** `src/virt_graph/handlers/pathfinding.py`

**Signature:**
```python
def shortest_path(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    end_id: int,
    weight_col: str | None = None,
    max_depth: int = 20,
    id_column: str = "id",
) -> dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_id` | int | Starting node ID |
| `end_id` | int | Target node ID |
| `weight_col` | str | Column for edge weights (None = hop count) |

**Returns:**
```python
{
    "path": [1, 12, 18, 25],       # Node IDs in order (None if no path)
    "path_nodes": [                # Full node details
        {"id": 1, "name": "Chicago Warehouse", ...},
        ...
    ],
    "distance": 2450.00,           # Total path weight (None if no path)
    "edges": [                     # Edge details with weights
        {"from_id": 1, "to_id": 12, "weight": 800.00},
        ...
    ],
    "nodes_explored": 35,          # Nodes loaded into memory
    "error": None,                 # Error message if no path
}
```

**Weight column options:**
- `None`: Unweighted (minimize hop count)
- `"cost_usd"`: Minimize total cost
- `"distance_km"`: Minimize total distance
- `"transit_time_hours"`: Minimize transit time

**Example:**
```python
# Find cheapest route
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=1,   # Chicago
    end_id=25,    # LA
    weight_col="cost_usd",
)
print(f"Cheapest route costs ${result['distance']:.2f}")
```

---

### all_shortest_paths()

Find all paths with equal optimal weight.

**Signature:**
```python
def all_shortest_paths(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    end_id: int,
    weight_col: str | None = None,
    max_depth: int = 20,
    max_paths: int = 10,
    id_column: str = "id",
) -> dict[str, Any]
```

**Additional Parameter:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_paths` | int | Maximum number of paths to return |

**Returns:**
```python
{
    "paths": [                     # List of all optimal paths
        [1, 12, 25],
        [1, 18, 25],
        ...
    ],
    "distance": 2450.00,           # Common optimal distance
    "path_count": 3,
    "nodes_explored": 40,
    "error": None,
}
```

---

## Network Analysis Handlers

### centrality()

Calculate centrality for nodes in the graph.

**Location:** `src/virt_graph/handlers/network.py`

**Signature:**
```python
def centrality(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    centrality_type: Literal["degree", "betweenness", "closeness", "pagerank"] = "degree",
    top_n: int = 10,
    weight_col: str | None = None,
    id_column: str = "id",
) -> dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `centrality_type` | str | Type of centrality measure |
| `top_n` | int | Number of top nodes to return |
| `weight_col` | str | Weight column (used by some centrality measures) |

**Centrality Types:**

| Type | Meaning | Complexity | Use Case |
|------|---------|------------|----------|
| `"degree"` | Number of connections | O(n) | Finding busy hubs |
| `"betweenness"` | Bridge nodes | O(n*m) | Finding chokepoints |
| `"closeness"` | Average distance to all | O(n*m) | Optimal placement |
| `"pagerank"` | Incoming link importance | O(iterations) | Flow analysis |

**Returns:**
```python
{
    "results": [
        {
            "node": {"id": 12, "name": "Dallas Hub", ...},
            "score": 0.42,
        },
        ...
    ],
    "centrality_type": "betweenness",
    "graph_stats": {
        "nodes": 50,
        "edges": 197,
        "density": 0.08,
        "is_connected": True,
    },
    "nodes_loaded": 50,
}
```

**Warning:** Loads entire graph into memory. Only use for graphs under MAX_NODES (10,000).

---

### connected_components()

Find connected components in the graph.

**Signature:**
```python
def connected_components(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    min_size: int = 1,
    id_column: str = "id",
) -> dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `min_size` | int | Minimum component size to include |

**Returns:**
```python
{
    "components": [
        {
            "node_ids": [1, 2, 3, ..., 48],
            "size": 48,
            "sample_nodes": [{"name": "Chicago Warehouse"}, ...],
        },
        ...
    ],
    "component_count": 2,
    "largest_component_size": 48,
    "isolated_nodes": [],          # Nodes with degree 0
    "graph_stats": {...},
}
```

---

### graph_density()

Calculate graph density and statistics without fetching node details.

**Signature:**
```python
def graph_density(
    conn: PgConnection,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    weight_col: str | None = None,
) -> dict[str, Any]
```

**Returns:**
```python
{
    "nodes": 50,
    "edges": 197,
    "density": 0.08,
    "is_directed": True,
    "is_weakly_connected": True,
    "is_strongly_connected": False,
    "avg_degree": 7.88,
    "max_degree": 15,
    "min_degree": 2,
}
```

---

### neighbors()

Get direct neighbors of a node (single-hop).

**Signature:**
```python
def neighbors(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    node_id: int,
    direction: Literal["outbound", "inbound", "both"] = "both",
    id_column: str = "id",
) -> dict[str, Any]
```

**Returns:**
```python
{
    "neighbors": [
        {"id": 12, "name": "Dallas Hub", ...},
        ...
    ],
    "outbound_count": 5,
    "inbound_count": 3,
    "total_degree": 8,
}
```

---

## Safety Infrastructure

### Limits (from `base.py`)

```python
MAX_DEPTH = 50           # Absolute traversal depth limit
MAX_NODES = 10_000       # Max nodes to visit in single traversal
MAX_RESULTS = 1_000      # Max rows to return
QUERY_TIMEOUT_SEC = 30   # Per-query timeout
```

### Exceptions

```python
class SafetyLimitExceeded(Exception):
    """Raised when a handler would exceed safety limits."""
    pass

class SubgraphTooLarge(Exception):
    """Raised when estimated subgraph exceeds MAX_NODES."""
    pass
```

### Utility Functions

```python
# Check traversal limits
check_limits(depth: int, visited_count: int) -> None

# Estimate reachable nodes (sampling-based)
estimate_reachable_nodes(conn, edges_table, start_id, max_depth,
                         edge_from_col, edge_to_col, direction) -> int

# Batch fetch edges for frontier (ONE query per depth level)
fetch_edges_for_frontier(conn, edges_table, frontier_ids,
                         edge_from_col, edge_to_col, direction) -> list[tuple]

# Fetch node data
fetch_nodes(conn, nodes_table, node_ids, columns=None, id_column="id") -> list[dict]

# Check stop condition
should_stop(conn, nodes_table, node_id, condition, id_column="id") -> bool
```

---

## Implementation Notes

### Frontier Batching (Mandatory)

All traversals use frontier-batched BFS:
- **One query per depth level**, not per node
- Prevents N+1 query explosion
- Essential for scalability

```python
# CORRECT: Batch query for entire frontier
edges = fetch_edges_for_frontier(conn, edges_table, list(frontier), ...)

# WRONG: Individual queries per node
for node in frontier:
    edges = get_edges_for_node(conn, node)  # N+1 problem!
```

### Hybrid SQL/Python

- Python orchestrates traversal logic
- SQL handles filtering and batched data retrieval
- Never bulk-load entire tables into Python

### Size Estimation

Before full traversal, handlers estimate reachable nodes:
- Uses sampling (first 3 levels)
- Extrapolates to estimate total
- Raises `SubgraphTooLarge` if estimate exceeds limit
