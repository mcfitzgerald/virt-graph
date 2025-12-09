# Handlers API Reference

This reference documents all handler functions available in Virtual Graph. Handlers execute graph operations over relational data.

## Module Overview

```
virt_graph.handlers/
├── base.py        # Safety limits, utilities, exceptions
├── traversal.py   # YELLOW: BFS traversal handlers
├── pathfinding.py # RED: Dijkstra shortest path
└── network.py     # RED: Centrality, components, density
```

---

## Safety Limits

All handlers enforce non-negotiable safety limits defined in `base.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_DEPTH` | 50 | Absolute traversal depth limit |
| `MAX_NODES` | 10,000 | Maximum nodes per operation |
| `MAX_RESULTS` | 1,000 | Maximum rows returned |
| `QUERY_TIMEOUT_SEC` | 30 | Per-query timeout |

### Exceptions

```python
class SafetyLimitExceeded(Exception):
    """Raised when a handler would exceed safety limits."""

class SubgraphTooLarge(Exception):
    """Raised when estimated subgraph exceeds MAX_NODES."""
```

---

## Base Module (`virt_graph.handlers.base`)

### `check_limits()`

```python
def check_limits(depth: int, visited_count: int) -> None
```

Check traversal hasn't exceeded safety limits.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `depth` | `int` | Current traversal depth |
| `visited_count` | `int` | Number of nodes visited |

**Raises:** `SafetyLimitExceeded` if limits exceeded.

---

### `fetch_edges_for_frontier()`

```python
def fetch_edges_for_frontier(
    conn: PgConnection,
    edges_table: str,
    frontier_ids: list[int],
    edge_from_col: str,
    edge_to_col: str,
    direction: str = "outbound",
) -> list[tuple[int, int]]
```

Fetch all edges for a frontier in a **single query**. This is the mandatory batching pattern.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `edges_table` | `str` | Edge table name |
| `frontier_ids` | `list[int]` | Node IDs at current depth |
| `edge_from_col` | `str` | Source column |
| `edge_to_col` | `str` | Target column |
| `direction` | `str` | `"outbound"`, `"inbound"`, or `"both"` |

**Returns:** List of `(from_id, to_id)` tuples.

---

### `fetch_nodes()`

```python
def fetch_nodes(
    conn: PgConnection,
    nodes_table: str,
    node_ids: list[int],
    columns: list[str] | None = None,
    id_column: str = "id",
) -> list[dict[str, Any]]
```

Fetch node data for a list of node IDs.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `nodes_table` | `str` | Node table name |
| `node_ids` | `list[int]` | IDs to fetch |
| `columns` | `list[str] \| None` | Columns to return (None = all) |
| `id_column` | `str` | Primary key column name |

**Returns:** List of node dictionaries.

---

### `get_connection()`

```python
def get_connection(
    host: str = "localhost",
    port: int = 5432,
    database: str = "supply_chain",
    user: str = "virt_graph",
    password: str = "dev_password",
) -> PgConnection
```

Get a PostgreSQL connection with standard settings.

---

## Traversal Module (`virt_graph.handlers.traversal`)

### `traverse()`

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
    max_nodes: int | None = None,
    skip_estimation: bool = False,
    estimation_config: EstimationConfig | None = None,
) -> dict[str, Any]
```

Generic graph traversal using iterative frontier-batched BFS.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `nodes_table` | `str` | Table containing nodes |
| `edges_table` | `str` | Table containing edges |
| `edge_from_col` | `str` | Column for edge source |
| `edge_to_col` | `str` | Column for edge target |
| `start_id` | `int` | Starting node ID |
| `direction` | `str` | `"outbound"`, `"inbound"`, or `"both"` |
| `max_depth` | `int` | Maximum traversal depth (clamped to MAX_DEPTH) |
| `stop_condition` | `str \| None` | SQL WHERE fragment for terminal nodes |
| `collect_columns` | `list[str] \| None` | Columns to return from nodes |
| `prefilter_sql` | `str \| None` | SQL WHERE to filter edges |
| `include_start` | `bool` | Include start node in results |
| `id_column` | `str` | Primary key column name |
| `max_nodes` | `int \| None` | Override MAX_NODES limit |
| `skip_estimation` | `bool` | Bypass size check |
| `estimation_config` | `EstimationConfig \| None` | Custom estimation config |

**Returns:**

```python
{
    "nodes": [...],           # List of node dicts
    "paths": {...},           # node_id -> path from start
    "edges": [...],           # List of traversed edges
    "depth_reached": int,     # Actual depth traversed
    "nodes_visited": int,     # Total nodes visited
    "terminated_at": [...],   # Nodes matching stop_condition
}
```

**Raises:** `SubgraphTooLarge` if estimated traversal exceeds limit.

**Example:**

```python
from virt_graph.handlers import traverse

result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,
    direction="inbound",
    max_depth=10,
)
```

---

### `traverse_collecting()`

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

Traverse graph and collect all nodes matching a target condition.

**Parameters:**

Same as `traverse()`, plus:

| Name | Type | Description |
|------|------|-------------|
| `target_condition` | `str` | SQL WHERE for targets (e.g., `"tier = 3"`) |

**Returns:**

```python
{
    "matching_nodes": [...],    # Nodes matching condition
    "matching_paths": {...},    # Paths to matching nodes
    "total_traversed": int,     # All nodes visited
    "depth_reached": int,       # Actual depth
}
```

**Example:**

```python
# Find all tier 3 suppliers upstream of Acme Corp
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

### `bom_explode()`

```python
def bom_explode(
    conn: PgConnection,
    start_part_id: int,
    max_depth: int = 20,
    include_quantities: bool = True,
    max_nodes: int | None = None,
    skip_estimation: bool = False,
    estimation_config: EstimationConfig | None = None,
) -> dict[str, Any]
```

Explode a Bill of Materials starting from a top-level part.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `start_part_id` | `int` | Top-level part ID |
| `max_depth` | `int` | Maximum BOM depth |
| `include_quantities` | `bool` | Aggregate quantities |
| `max_nodes` | `int \| None` | Override MAX_NODES |
| `skip_estimation` | `bool` | Bypass size check |
| `estimation_config` | `EstimationConfig \| None` | Custom config |

**Returns:**

```python
{
    "bom_tree": {...},           # Hierarchical BOM structure
    "total_parts": int,          # Unique parts count
    "max_depth": int,            # Deepest level reached
    "quantities": {...},         # Part ID -> total quantity
}
```

**Example:**

```python
# Explode BOM for a product
result = bom_explode(conn, start_part_id=123, max_depth=10)
```

---

## Pathfinding Module (`virt_graph.handlers.pathfinding`)

### `shortest_path()`

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
    excluded_nodes: list[int] | None = None,
) -> ShortestPathResult
```

Find shortest path between two nodes using Dijkstra's algorithm.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `nodes_table` | `str` | Node table |
| `edges_table` | `str` | Edge table |
| `edge_from_col` | `str` | Source column |
| `edge_to_col` | `str` | Target column |
| `start_id` | `int` | Starting node ID |
| `end_id` | `int` | Target node ID |
| `weight_col` | `str \| None` | Edge weight column (None = hop count) |
| `max_depth` | `int` | Maximum search depth |
| `id_column` | `str` | Primary key column |
| `excluded_nodes` | `list[int] \| None` | Node IDs to route around |

**Returns:**

```python
{
    "path": [1, 5, 12, 25],      # Node IDs (None if no path)
    "path_nodes": [...],         # Full node details
    "distance": 1234.56,         # Total weight/length
    "edges": [...],              # Edges along path
    "nodes_explored": int,       # Nodes loaded
    "excluded_nodes": [...],     # Nodes that were excluded
    "error": str | None,         # Error if no path
}
```

**Raises:** `SubgraphTooLarge` if search exceeds MAX_NODES.

**Example:**

```python
from virt_graph.handlers import shortest_path

# Basic shortest path
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=1,
    end_id=25,
    weight_col="cost_usd",
)

# Route around a specific node (e.g., avoid Denver Hub)
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="cost_usd",
    excluded_nodes=[denver_id],  # Route around Denver
)
```

---

### `all_shortest_paths()`

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
    excluded_nodes: list[int] | None = None,
) -> AllShortestPathsResult
```

Find all shortest paths between two nodes.

**Parameters:**

Same as `shortest_path()`, plus:

| Name | Type | Description |
|------|------|-------------|
| `max_paths` | `int` | Maximum paths to return |

**Returns:**

```python
{
    "paths": [[1,5,25], [1,8,25], ...],  # All optimal paths
    "distance": 1234.56,                  # Common distance
    "path_count": int,                    # Paths found
    "nodes_explored": int,                # Nodes loaded
    "excluded_nodes": [...],              # Nodes that were excluded
    "error": str | None,                  # Error if no paths
}
```

---

## Network Module (`virt_graph.handlers.network`)

### `centrality()`

```python
def centrality(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    centrality_type: str = "degree",
    top_n: int = 10,
    weight_col: str | None = None,
    id_column: str = "id",
) -> dict[str, Any]
```

Calculate centrality for nodes in the graph.

**Warning:** Loads entire graph into memory. Only use for graphs under MAX_NODES.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `nodes_table` | `str` | Node table |
| `edges_table` | `str` | Edge table |
| `edge_from_col` | `str` | Source column |
| `edge_to_col` | `str` | Target column |
| `centrality_type` | `str` | Type: `"degree"`, `"betweenness"`, `"closeness"`, `"pagerank"` |
| `top_n` | `int` | Number of top nodes to return |
| `weight_col` | `str \| None` | Edge weight column |
| `id_column` | `str` | Primary key column |

**Centrality Types:**

| Type | Description | Speed |
|------|-------------|-------|
| `degree` | Number of connections | Fast |
| `betweenness` | Bridge nodes between clusters | Slow |
| `closeness` | Average distance to all nodes | Medium |
| `pagerank` | Importance by incoming links | Medium |

**Returns:**

```python
{
    "results": [
        {"node": {...}, "score": 0.234},
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

**Raises:** `SubgraphTooLarge` if graph exceeds MAX_NODES.

**Example:**

```python
from virt_graph.handlers import centrality

result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10,
)
```

---

### `connected_components()`

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

Find connected components in the graph.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `min_size` | `int` | Minimum component size to return |

**Returns:**

```python
{
    "components": [
        {"node_ids": [...], "size": 45, "sample_nodes": [...]},
        ...
    ],
    "component_count": int,
    "largest_component_size": int,
    "isolated_nodes": int,
    "graph_stats": {...},
}
```

---

### `graph_density()`

```python
def graph_density(
    conn: PgConnection,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    weight_col: str | None = None,
) -> dict[str, Any]
```

Calculate graph density and basic statistics.

**Returns:**

```python
{
    "nodes": 50,
    "edges": 197,
    "density": 0.08,
    "is_directed": True,
    "is_connected": True,           # or is_weakly_connected
    "avg_degree": 3.94,
    "max_degree": 12,
    "min_degree": 1,
}
```

---

### `neighbors()`

```python
def neighbors(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    node_id: int,
    direction: str = "both",
    id_column: str = "id",
) -> dict[str, Any]
```

Get direct neighbors of a node.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `node_id` | `int` | Node to query |
| `direction` | `str` | `"outbound"`, `"inbound"`, or `"both"` |

**Returns:**

```python
{
    "neighbors": [...],       # List of neighbor node dicts
    "outbound_count": int,    # Outgoing edge count
    "inbound_count": int,     # Incoming edge count
    "total_degree": int,      # Unique neighbor count
}
```

---

### `resilience_analysis()`

```python
def resilience_analysis(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    node_to_remove: int,
    id_column: str = "id",
) -> ResilienceResult
```

Analyze network resilience by simulating node removal. Identifies single points of failure.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `nodes_table` | `str` | Node table |
| `edges_table` | `str` | Edge table |
| `edge_from_col` | `str` | Source column |
| `edge_to_col` | `str` | Target column |
| `node_to_remove` | `int` | Node ID to simulate removal |
| `id_column` | `str` | Primary key column |

**Returns:**

```python
{
    "node_removed": int,           # The simulated-removed node
    "node_removed_info": {...},    # Node details
    "disconnected_pairs": [...],   # (node_a, node_b) tuples that lose connectivity
    "components_before": int,      # Connected components before removal
    "components_after": int,       # Connected components after removal
    "component_increase": int,     # New components created
    "isolated_nodes": [...],       # Nodes with degree 0 after removal
    "affected_node_count": int,    # Total affected nodes
    "is_critical": bool,           # True if removal breaks connectivity
    "error": str | None,           # Error message if any
}
```

**Raises:** `SubgraphTooLarge` if graph exceeds MAX_NODES.

**Example:**

```python
from virt_graph.handlers import resilience_analysis

# Check what happens if Denver Hub goes offline
result = resilience_analysis(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_to_remove=denver_id,
)

if result["is_critical"]:
    print(f"Denver Hub is critical! Removing it creates {result['component_increase']} new components")
    print(f"Disconnected pairs: {result['disconnected_pairs']}")
```

---

## Result TypedDicts

All handlers return typed dictionaries for better IDE support:

```python
from virt_graph.handlers import (
    TraverseResult,
    BomExplodeResult,
    ShortestPathResult,
    AllShortestPathsResult,
    CentralityResult,
    ResilienceResult,
)
```

---

## Import Shortcuts

```python
# Import all handlers
from virt_graph.handlers import (
    # Traversal (YELLOW)
    traverse,
    traverse_collecting,
    bom_explode,
    # Pathfinding (RED)
    shortest_path,
    all_shortest_paths,
    # Network (RED)
    centrality,
    connected_components,
    graph_density,
    neighbors,
    resilience_analysis,
    # Utilities
    get_connection,
    # Exceptions
    SafetyLimitExceeded,
    SubgraphTooLarge,
    # Config
    EstimationConfig,
    # Result TypedDicts
    TraverseResult,
    BomExplodeResult,
    ShortestPathResult,
    AllShortestPathsResult,
    CentralityResult,
    ResilienceResult,
)
```

---

## See Also

- [Estimator API Reference](estimator.md) - Size estimation and guards
- [Ontology API Reference](ontology.md) - Schema mapping
- [Traffic Light Routing](../../concepts/architecture.md) - When to use which handler
