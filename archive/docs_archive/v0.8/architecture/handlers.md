# Handlers

Handlers are schema-parameterized functions that execute graph operations efficiently over relational data.

## Design Principles

### Schema Parameterization

Handlers take table and column names as parameters:

```python
traverse(
    nodes_table="suppliers",        # Any table
    edges_table="supplier_relationships",  # Any edge table
    edge_from_col="seller_id",      # Any FK column
    edge_to_col="buyer_id",         # Any FK column
    ...
)
```

This makes handlers reusable across different schemas.

### Frontier Batching

All traversal uses batched queries:

```python
# One query per depth level
edges = fetch_edges_for_frontier(
    conn, edges_table,
    list(frontier),  # All nodes at current depth
    edge_from_col, edge_to_col, direction
)
```

**Never** one query per node.

### Safety Guards

Every handler enforces limits:

```python
def traverse(...):
    # Estimate size before starting
    estimated = estimate_reachable_nodes(...)
    if estimated > MAX_NODES:
        raise SubgraphTooLarge(...)

    # Check limits at each depth
    for depth in range(max_depth):
        check_limits(depth, len(visited))
        ...
```

## Available Handlers

### `traverse()`

Generic BFS traversal for YELLOW queries.

```python
def traverse(
    conn,
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
) -> dict
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conn` | Connection | Database connection |
| `nodes_table` | str | Table containing nodes |
| `edges_table` | str | Table containing edges |
| `edge_from_col` | str | Column for edge source |
| `edge_to_col` | str | Column for edge target |
| `start_id` | int | Starting node ID |
| `direction` | str | "outbound", "inbound", or "both" |
| `max_depth` | int | Maximum traversal depth |
| `stop_condition` | str | SQL WHERE fragment for terminal nodes |
| `collect_columns` | list | Columns to return from nodes |
| `prefilter_sql` | str | SQL WHERE to filter edges |
| `include_start` | bool | Include start node in results |
| `id_column` | str | Name of ID column |

**Returns:**

```python
{
    "nodes": [...],           # List of node dicts
    "paths": {node_id: [...]},  # Path from start to each node
    "edges": [(from, to), ...], # Traversed edges
    "depth_reached": int,     # Actual max depth
    "nodes_visited": int,     # Total nodes visited
    "terminated_at": [...],   # Nodes matching stop_condition
}
```

### `traverse_collecting()`

Find all nodes matching a condition.

```python
def traverse_collecting(
    conn,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    target_condition: str,
    direction: str = "outbound",
    max_depth: int = 10,
    ...
) -> dict
```

**Returns:**

```python
{
    "matching_nodes": [...],     # Nodes matching condition
    "matching_paths": {...},     # Paths to matching nodes
    "total_traversed": int,      # Total nodes visited
    "depth_reached": int,
}
```

### `bom_explode()`

Specialized BOM traversal with quantity aggregation.

```python
def bom_explode(
    conn,
    start_part_id: int,
    max_depth: int = 20,
    include_quantities: bool = True,
) -> dict
```

**Returns:**

```python
{
    "nodes": [...],
    "paths": {...},
    "quantities": {part_id: total_qty, ...},  # Aggregated quantities
    ...
}
```

## Utility Functions

### `fetch_edges_for_frontier()`

Batch fetch edges for a set of nodes.

```python
def fetch_edges_for_frontier(
    conn,
    edges_table: str,
    frontier_ids: list[int],
    edge_from_col: str,
    edge_to_col: str,
    direction: str = "outbound",
) -> list[tuple[int, int]]
```

### `fetch_nodes()`

Batch fetch node data.

```python
def fetch_nodes(
    conn,
    nodes_table: str,
    node_ids: list[int],
    columns: list[str] | None = None,
    id_column: str = "id",
) -> list[dict]
```

### `estimate_reachable_nodes()`

Estimate traversal size before executing.

```python
def estimate_reachable_nodes(
    conn,
    edges_table: str,
    start_id: int,
    max_depth: int,
    edge_from_col: str,
    edge_to_col: str,
    direction: str = "outbound",
) -> int
```

### `check_limits()`

Verify traversal is within bounds.

```python
def check_limits(depth: int, visited_count: int) -> None
```

Raises `SafetyLimitExceeded` if limits exceeded.

## Exceptions

### `SafetyLimitExceeded`

Raised when traversal exceeds MAX_DEPTH or MAX_NODES.

```python
from virt_graph.handlers import SafetyLimitExceeded

try:
    result = traverse(...)
except SafetyLimitExceeded as e:
    print(f"Limit exceeded: {e}")
```

### `SubgraphTooLarge`

Raised proactively when estimated size exceeds limits.

```python
from virt_graph.handlers import SubgraphTooLarge

try:
    result = traverse(...)
except SubgraphTooLarge as e:
    print(f"Graph too large: {e}")
    # Suggest adding filters or reducing depth
```
