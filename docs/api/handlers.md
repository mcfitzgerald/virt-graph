# Handlers API Reference

::: virt_graph.handlers

## Module: `virt_graph.handlers.base`

### Constants

```python
MAX_DEPTH = 50          # Absolute traversal depth limit
MAX_NODES = 10_000      # Max nodes to visit in single traversal
MAX_RESULTS = 1_000     # Max rows to return
QUERY_TIMEOUT_SEC = 30  # Per-query timeout
```

### Exceptions

#### `SafetyLimitExceeded`

```python
class SafetyLimitExceeded(Exception):
    """Raised when a handler would exceed safety limits."""
    pass
```

#### `SubgraphTooLarge`

```python
class SubgraphTooLarge(Exception):
    """Raised when estimated subgraph exceeds MAX_NODES."""
    pass
```

### Functions

#### `check_limits()`

```python
def check_limits(depth: int, visited_count: int) -> None:
    """
    Check traversal hasn't exceeded safety limits.

    Args:
        depth: Current traversal depth
        visited_count: Number of nodes visited so far

    Raises:
        SafetyLimitExceeded: If limits are exceeded
    """
```

#### `estimate_reachable_nodes()`

```python
def estimate_reachable_nodes(
    conn: PgConnection,
    edges_table: str,
    start_id: int,
    max_depth: int,
    edge_from_col: str,
    edge_to_col: str,
    direction: str = "outbound",
) -> int:
    """
    Estimate reachable node count using sampling.

    Samples first 3 levels and extrapolates based on
    average branching factor.

    Returns:
        Estimated number of reachable nodes
    """
```

#### `fetch_edges_for_frontier()`

```python
def fetch_edges_for_frontier(
    conn: PgConnection,
    edges_table: str,
    frontier_ids: list[int],
    edge_from_col: str,
    edge_to_col: str,
    direction: str = "outbound",
) -> list[tuple[int, int]]:
    """
    Fetch all edges for a frontier in a SINGLE query.

    This is the mandatory batching pattern.

    Returns:
        List of (from_id, to_id) tuples
    """
```

#### `fetch_nodes()`

```python
def fetch_nodes(
    conn: PgConnection,
    nodes_table: str,
    node_ids: list[int],
    columns: list[str] | None = None,
    id_column: str = "id",
) -> list[dict[str, Any]]:
    """
    Fetch node data for a list of node IDs.

    Returns:
        List of node dicts with requested columns
    """
```

#### `get_connection()`

```python
def get_connection(
    host: str = "localhost",
    port: int = 5432,
    database: str = "supply_chain",
    user: str = "virt_graph",
    password: str = "dev_password",
) -> PgConnection:
    """
    Get a PostgreSQL connection with standard settings.
    """
```

---

## Module: `virt_graph.handlers.traversal`

### Functions

#### `traverse()`

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
) -> dict[str, Any]:
    """
    Generic graph traversal using iterative frontier-batched BFS.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes (e.g., "suppliers")
        edges_table: Table containing edges (e.g., "supplier_relationships")
        edge_from_col: Column for edge source (e.g., "seller_id")
        edge_to_col: Column for edge target (e.g., "buyer_id")
        start_id: Starting node ID
        direction: "outbound", "inbound", or "both"
        max_depth: Maximum traversal depth (clamped to MAX_DEPTH)
        stop_condition: SQL WHERE clause fragment to mark terminal nodes
        collect_columns: Columns to return from nodes table
        prefilter_sql: SQL WHERE clause to filter edges
        include_start: Whether to include start node in results
        id_column: Name of the ID column in nodes_table

    Returns:
        dict with nodes, paths, edges, depth_reached, nodes_visited, terminated_at

    Raises:
        SubgraphTooLarge: If estimated traversal would exceed MAX_NODES
    """
```

#### `traverse_collecting()`

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
) -> dict[str, Any]:
    """
    Traverse graph and collect all nodes matching a target condition.

    Args:
        target_condition: SQL WHERE clause for target nodes (e.g., "tier = 3")

    Returns:
        dict with matching_nodes, matching_paths, total_traversed, depth_reached
    """
```

#### `bom_explode()`

```python
def bom_explode(
    conn: PgConnection,
    start_part_id: int,
    max_depth: int = 20,
    include_quantities: bool = True,
) -> dict[str, Any]:
    """
    Explode a Bill of Materials starting from a top-level part.

    Args:
        start_part_id: Top-level part ID
        max_depth: Maximum BOM depth to traverse
        include_quantities: Whether to aggregate quantities

    Returns:
        dict with BOM tree structure and aggregated quantities
    """
```
