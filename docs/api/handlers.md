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

#### `estimate_reachable_nodes()` (DEPRECATED)

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
    DEPRECATED: Use virt_graph.estimator module instead.

    This function uses naive exponential extrapolation which can
    over-estimate significantly for DAGs with node sharing.

    Migration:
        from virt_graph.estimator import GraphSampler, estimate
        sampler = GraphSampler(conn, edges_table, from_col, to_col)
        sample = sampler.sample(start_id)
        est = estimate(sample, max_depth)

    Returns:
        Estimated number of reachable nodes
    """
```

> **Note**: See [Estimator API Reference](estimator.md) for the new estimation module.

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
    # Configurable limits (v0.8.0+)
    max_nodes: int | None = None,
    skip_estimation: bool = False,
    estimation_config: EstimationConfig | None = None,
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
        max_nodes: Override default MAX_NODES limit (None = use 10,000)
        skip_estimation: Bypass size check entirely (caller takes responsibility)
        estimation_config: Fine-tune estimation parameters

    Returns:
        dict with nodes, paths, edges, depth_reached, nodes_visited, terminated_at

    Raises:
        SubgraphTooLarge: If estimated traversal would exceed max_nodes limit

    Examples:
        # Normal usage with improved estimation
        result = traverse(conn, "suppliers", "supplier_relationships", ...)

        # Override limit for known-bounded graph
        result = traverse(..., max_nodes=50_000)

        # Skip estimation when you know graph is bounded
        result = traverse(..., skip_estimation=True)
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
    # Configurable limits (v0.8.0+)
    max_nodes: int | None = None,
    skip_estimation: bool = False,
    estimation_config: EstimationConfig | None = None,
) -> dict[str, Any]:
    """
    Explode a Bill of Materials starting from a top-level part.

    Args:
        start_part_id: Top-level part ID
        max_depth: Maximum BOM depth to traverse
        include_quantities: Whether to aggregate quantities
        max_nodes: Override default MAX_NODES limit (None = use 10,000)
        skip_estimation: Bypass size check entirely (caller takes responsibility)
        estimation_config: Fine-tune estimation parameters

    Returns:
        dict with BOM tree structure and aggregated quantities

    Examples:
        # Normal usage with improved estimation
        result = bom_explode(conn, part_id)

        # Override limit for large BOMs
        result = bom_explode(conn, part_id, max_nodes=50_000)

        # Skip estimation for known-bounded BOM
        result = bom_explode(conn, part_id, skip_estimation=True)
    """
```

---

## Module: `virt_graph.handlers.pathfinding`

### Functions

#### `shortest_path()`

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
) -> dict[str, Any]:
    """
    Find shortest path between two nodes using Dijkstra.

    Uses bidirectional search and incremental graph loading
    for efficiency.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes (e.g., "facilities")
        edges_table: Table containing edges (e.g., "transport_routes")
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        start_id: Starting node ID
        end_id: Target node ID
        weight_col: Column for edge weights (None = hop count)
        max_depth: Maximum search depth
        id_column: Name of the ID column

    Returns:
        dict with:
            - path: list of node IDs (None if no path)
            - path_nodes: list of node dicts with details
            - distance: total path weight/length
            - edges: list of edge dicts along path
            - nodes_explored: nodes loaded into graph
            - error: error message if no path found

    Raises:
        SubgraphTooLarge: If search exceeds MAX_NODES
    """
```

#### `all_shortest_paths()`

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
) -> dict[str, Any]:
    """
    Find all shortest paths between two nodes.

    Useful when there are multiple equivalent optimal routes.

    Args:
        max_paths: Maximum number of paths to return

    Returns:
        dict with:
            - paths: list of paths (each is list of node IDs)
            - distance: common distance of all paths
            - path_count: number of paths found
            - nodes_explored: nodes loaded into graph
    """
```

---

## Module: `virt_graph.handlers.network`

### Functions

#### `centrality()`

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
) -> dict[str, Any]:
    """
    Calculate centrality for nodes in the graph.

    WARNING: Loads entire graph into memory. Only use for
    small-medium graphs under MAX_NODES.

    Args:
        centrality_type: Type of centrality:
            - "degree": Number of connections (fast)
            - "betweenness": Bridge nodes (slower)
            - "closeness": Average distance to all (medium)
            - "pagerank": Importance by incoming links (medium)
        top_n: Number of top nodes to return

    Returns:
        dict with:
            - results: list of {node, score} sorted by score desc
            - centrality_type: type calculated
            - graph_stats: nodes, edges, density, connectivity
            - nodes_loaded: total nodes in graph

    Raises:
        SubgraphTooLarge: If graph exceeds MAX_NODES
    """
```

#### `connected_components()`

```python
def connected_components(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    min_size: int = 1,
    id_column: str = "id",
) -> dict[str, Any]:
    """
    Find connected components in the graph.

    Useful for identifying isolated clusters or verifying
    network connectivity.

    Args:
        min_size: Minimum component size to return

    Returns:
        dict with:
            - components: list with node_ids, size, sample_nodes
            - component_count: total number of components
            - largest_component_size: size of largest
            - isolated_nodes: nodes with no connections
            - graph_stats: nodes, edges
    """
```

#### `graph_density()`

```python
def graph_density(
    conn: PgConnection,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    weight_col: str | None = None,
) -> dict[str, Any]:
    """
    Calculate graph density and basic statistics.

    Returns:
        dict with:
            - nodes, edges, density
            - is_directed, is_connected/is_weakly_connected
            - avg_degree, max_degree, min_degree
    """
```

#### `neighbors()`

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
) -> dict[str, Any]:
    """
    Get direct neighbors of a node.

    Args:
        node_id: Node to get neighbors for
        direction: "outbound", "inbound", or "both"

    Returns:
        dict with:
            - neighbors: list of neighbor node dicts
            - outbound_count: outgoing edges
            - inbound_count: incoming edges
            - total_degree: unique neighbors
    """
```
