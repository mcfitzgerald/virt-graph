"""
Core handler infrastructure with safety limits and utilities.

This module provides the foundation for all graph operation handlers:
- Non-negotiable safety limits to prevent runaway queries
- Frontier batching utilities for efficient traversal
- Node estimation for proactive size checks
- TypedDict definitions for handler return types
- Support for composite primary/foreign keys

Note: estimate_reachable_nodes is deprecated. Use the estimator module instead.
"""

import warnings
from datetime import datetime
from decimal import Decimal
from typing import Any, TypedDict, Union

import psycopg2
from psycopg2.extensions import connection as PgConnection

# Type alias for node IDs - can be single value or tuple for composite keys
NodeId = Union[int, tuple[Any, ...]]


# === TYPED RESULT DICTIONARIES ===
# These provide IDE support and documentation for handler return types


class TraverseResult(TypedDict):
    """Result type for traverse() and traverse_collecting()."""

    nodes: list[dict[str, Any]]
    """List of node dicts with all columns from the nodes table."""

    paths: dict[int, list[int]]
    """Map of node_id to path (list of IDs from start node)."""

    edges: list[tuple[int, int]]
    """List of (from_id, to_id) tuples traversed."""

    depth_reached: int
    """Actual max depth encountered during traversal."""

    nodes_visited: int
    """Total unique nodes visited."""

    terminated_at: list[int]
    """Node IDs where traversal stopped due to stop_condition."""


class PathAggregateResult(TypedDict):
    """Result type for path_aggregate()."""

    nodes: list[dict[str, Any]]
    """Node data with aggregated values included."""

    aggregated_values: dict[int, float]
    """Map of node_id to aggregated value."""

    operation: str
    """Aggregation operation performed (sum/max/min/multiply/count)."""

    value_column: str
    """Column that was aggregated."""

    max_depth: int
    """Deepest level reached during traversal."""

    nodes_visited: int
    """Total unique nodes visited."""


class ShortestPathResult(TypedDict):
    """Result type for shortest_path()."""

    path: list[int] | None
    """List of node IDs from start to end, or None if no path found."""

    path_nodes: list[dict[str, Any]]
    """Node dicts with details for each node in the path."""

    distance: float | int | None
    """Total path weight/length, or None if no path found."""

    edges: list[dict[str, Any]]
    """Edge dicts with from_id, to_id, and weight for path edges."""

    nodes_explored: int
    """Number of nodes loaded into graph during search."""

    excluded_nodes: list[int]
    """Node IDs that were excluded from the search."""

    error: str | None
    """Error message if no path found, None otherwise."""


class AllShortestPathsResult(TypedDict):
    """Result type for all_shortest_paths()."""

    paths: list[list[int]]
    """List of paths, each path is a list of node IDs."""

    distance: float | int | None
    """Common distance of all shortest paths."""

    path_count: int
    """Number of paths found."""

    nodes_explored: int
    """Number of nodes loaded into graph."""

    excluded_nodes: list[int]
    """Node IDs that were excluded from the search."""

    error: str | None
    """Error message if no paths found."""


class CentralityResult(TypedDict):
    """Result type for centrality()."""

    results: list[dict[str, Any]]
    """List of {node: dict, score: float} sorted by score descending."""

    centrality_type: str
    """Type of centrality calculated (degree, betweenness, etc.)."""

    graph_stats: dict[str, Any]
    """Basic graph statistics (nodes, edges, density, etc.)."""

    nodes_loaded: int
    """Total nodes in graph."""


class ResilienceResult(TypedDict):
    """Result type for resilience_analysis()."""

    node_removed: int
    """The node ID that was simulated as removed."""

    node_removed_info: dict[str, Any]
    """Details of the removed node."""

    disconnected_pairs: list[tuple[int, int]]
    """Pairs of nodes that lose connectivity after removal."""

    components_before: int
    """Number of connected components before removal."""

    components_after: int
    """Number of connected components after removal."""

    component_increase: int
    """How many new components were created."""

    isolated_nodes: list[int]
    """Nodes that become completely disconnected."""

    affected_node_count: int
    """Total nodes affected by the removal."""

    is_critical: bool
    """True if removal increases components or isolates nodes."""

    error: str | None
    """Error message if any."""


# === SAFETY LIMITS (Non-negotiable) ===
MAX_DEPTH = 50  # Absolute traversal depth limit
MAX_NODES = 10_000  # Max nodes to visit in single traversal
MAX_RESULTS = 100_000  # Max rows to return (covers demo DB's largest table ~60K)
QUERY_TIMEOUT_SEC = 30  # Per-query timeout


class SafetyLimitExceeded(Exception):
    """Raised when a handler would exceed safety limits."""

    pass


class SubgraphTooLarge(Exception):
    """Raised when estimated subgraph exceeds MAX_NODES."""

    pass


def check_limits(depth: int, visited_count: int) -> None:
    """
    Check traversal hasn't exceeded safety limits.

    Args:
        depth: Current traversal depth
        visited_count: Number of nodes visited so far

    Raises:
        SafetyLimitExceeded: If limits are exceeded
    """
    if depth > MAX_DEPTH:
        raise SafetyLimitExceeded(f"Traversal depth {depth} exceeds limit {MAX_DEPTH}")
    if visited_count > MAX_NODES:
        raise SafetyLimitExceeded(f"Visited {visited_count} nodes, exceeds limit {MAX_NODES}")


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

    Estimate reachable node count using sampling.

    This function uses naive exponential extrapolation which can over-estimate
    significantly for DAGs with node sharing. The new estimator module provides:
    - Adaptive damping based on detected graph properties
    - Table bounds to cap estimates
    - Configurable estimation parameters

    Args:
        conn: Database connection
        edges_table: Table containing edges
        start_id: Starting node ID
        max_depth: Maximum traversal depth requested
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        direction: "outbound", "inbound", or "both"

    Returns:
        Estimated number of reachable nodes
    """
    warnings.warn(
        "estimate_reachable_nodes is deprecated. "
        "Use virt_graph.estimator.estimate() with GraphSampler for better accuracy.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Delegate to new estimator for backwards compatibility
    from ..estimator import GraphSampler, estimate, get_table_bound

    sampler = GraphSampler(conn, edges_table, edge_from_col, edge_to_col, direction)
    sample = sampler.sample(start_id, depth=min(3, max_depth))
    table_bound = get_table_bound(conn, edges_table, edge_from_col, edge_to_col)

    return estimate(sample, max_depth, table_bound)


def fetch_edges_for_frontier(
    conn: PgConnection,
    edges_table: str,
    frontier_ids: list[NodeId],
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    direction: str = "outbound",
    nodes_table: str | None = None,
    node_id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    # Temporal filtering
    valid_at: datetime | None = None,
    temporal_start_col: str | None = None,
    temporal_end_col: str | None = None,
    # Edge filtering
    sql_filter: str | None = None,
) -> list[tuple[NodeId, NodeId]]:
    """
    Fetch all edges for a frontier in a SINGLE query.

    This is the mandatory batching pattern - never one query per node.
    Uses PostgreSQL's ANY operator for efficient IN clause with arrays.
    Supports composite keys by accepting lists of column names.

    Args:
        conn: Database connection
        edges_table: Table containing edges
        frontier_ids: List of node IDs in current frontier (can be tuples for composite keys)
        edge_from_col: Column(s) for edge source - string or list for composite keys
        edge_to_col: Column(s) for edge target - string or list for composite keys
        direction: "outbound", "inbound", or "both"
        nodes_table: Table containing nodes (required for soft-delete filtering)
        node_id_column: ID column(s) in nodes_table - string or list for composite keys
        soft_delete_column: Column to check for soft-delete (e.g., "deleted_at").
                           If provided, filters out edges to/from soft-deleted nodes.
        valid_at: Point in time for temporal filtering. Only edges valid at this
                  time will be returned.
        temporal_start_col: Column containing edge start/effective date.
                           Required if valid_at is provided.
        temporal_end_col: Column containing edge end/expiry date.
                         Required if valid_at is provided.
        sql_filter: SQL WHERE clause to filter edges (e.g., "is_active = true").
                   Injected into the query for edge-level filtering.

    Returns:
        List of (from_id, to_id) tuples. For composite keys, each ID is a tuple.
    """
    if not frontier_ids:
        return []

    # Normalize columns to lists for composite key support
    from_cols = [edge_from_col] if isinstance(edge_from_col, str) else list(edge_from_col)
    to_cols = [edge_to_col] if isinstance(edge_to_col, str) else list(edge_to_col)
    id_cols = [node_id_column] if isinstance(node_id_column, str) else list(node_id_column)

    # Check if using composite keys
    is_composite = len(from_cols) > 1 or len(to_cols) > 1

    # Build column select expressions
    from_cols_select = ", ".join(f"e.{c}" for c in from_cols)
    to_cols_select = ", ".join(f"e.{c}" for c in to_cols)

    # Build soft-delete join clause if needed
    soft_delete_join = ""
    if soft_delete_column and nodes_table:
        # For composite keys, need to match all columns
        from_join_conds = " AND ".join(
            f"e.{fc} = n_from.{ic}" for fc, ic in zip(from_cols, id_cols)
        )
        to_join_conds = " AND ".join(
            f"e.{tc} = n_to.{ic}" for tc, ic in zip(to_cols, id_cols)
        )
        soft_delete_join = f"""
            JOIN {nodes_table} n_from ON {from_join_conds}
                AND n_from.{soft_delete_column} IS NULL
            JOIN {nodes_table} n_to ON {to_join_conds}
                AND n_to.{soft_delete_column} IS NULL
        """

    # Build temporal filter clause if needed
    temporal_filter = ""
    temporal_params: list = []
    if valid_at is not None and temporal_start_col and temporal_end_col:
        temporal_filter = f"""
            AND (e.{temporal_start_col} IS NULL OR e.{temporal_start_col} <= %s)
            AND (e.{temporal_end_col} IS NULL OR e.{temporal_end_col} >= %s)
        """
        temporal_params = [valid_at, valid_at]

    # Build sql_filter clause if provided
    sql_filter_clause = ""
    if sql_filter:
        sql_filter_clause = f" AND ({sql_filter})"

    # Build frontier matching clause
    def build_frontier_match(cols: list[str], alias: str = "e") -> tuple[str, list]:
        """Build WHERE clause for matching frontier IDs."""
        if len(cols) == 1:
            # Simple case: single column
            return f"{alias}.{cols[0]} = ANY(%s)", [frontier_ids]
        else:
            # Composite case: use row value comparison
            # Convert frontier tuples to proper format for PostgreSQL
            col_tuple = f"({', '.join(f'{alias}.{c}' for c in cols)})"
            # Build VALUES list for composite key matching
            if frontier_ids and isinstance(frontier_ids[0], tuple):
                values_list = ", ".join(
                    f"({', '.join('%s' for _ in cols)})" for _ in frontier_ids
                )
                flat_ids = [v for tup in frontier_ids for v in tup]
                return f"{col_tuple} IN (VALUES {values_list})", flat_ids
            else:
                # Single value frontier_ids, wrap in tuple
                values_list = ", ".join(
                    f"({', '.join('%s' for _ in cols)})" for _ in frontier_ids
                )
                # Each frontier_id becomes a single-element tuple
                flat_ids = [fid for fid in frontier_ids]
                return f"{alias}.{cols[0]} = ANY(%s)", [frontier_ids]

    with conn.cursor() as cur:
        # Set statement timeout for safety
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")

        # Build and execute query based on direction
        if direction == "outbound":
            frontier_clause, frontier_params = build_frontier_match(from_cols)
            query = f"""
                SELECT {from_cols_select}, {to_cols_select}
                FROM {edges_table} e
                {soft_delete_join}
                WHERE {frontier_clause}
                {temporal_filter}
                {sql_filter_clause}
            """
            cur.execute(query, frontier_params + temporal_params)
        elif direction == "inbound":
            frontier_clause, frontier_params = build_frontier_match(to_cols)
            query = f"""
                SELECT {from_cols_select}, {to_cols_select}
                FROM {edges_table} e
                {soft_delete_join}
                WHERE {frontier_clause}
                {temporal_filter}
                {sql_filter_clause}
            """
            cur.execute(query, frontier_params + temporal_params)
        else:  # both
            from_clause, from_params = build_frontier_match(from_cols)
            to_clause, to_params = build_frontier_match(to_cols)
            query = f"""
                SELECT {from_cols_select}, {to_cols_select}
                FROM {edges_table} e
                {soft_delete_join}
                WHERE ({from_clause} OR {to_clause})
                {temporal_filter}
                {sql_filter_clause}
            """
            cur.execute(query, from_params + to_params + temporal_params)

        rows = cur.fetchall()

    # Convert results to proper format
    results: list[tuple[NodeId, NodeId]] = []
    n_from = len(from_cols)
    n_to = len(to_cols)

    for row in rows:
        if is_composite:
            # Extract tuples for composite keys
            from_id = tuple(row[:n_from]) if n_from > 1 else row[0]
            to_id = tuple(row[n_from:n_from + n_to]) if n_to > 1 else row[n_from]
        else:
            from_id = row[0]
            to_id = row[1]
        results.append((from_id, to_id))

    return results


def fetch_nodes(
    conn: PgConnection,
    nodes_table: str,
    node_ids: list[NodeId],
    columns: list[str] | None = None,
    id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch node data for a list of node IDs.

    Supports composite keys by accepting lists of column names and tuple IDs.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes
        node_ids: List of node IDs to fetch (can be tuples for composite keys)
        columns: Columns to return (None = all)
        id_column: Name(s) of the ID column(s) - string or list for composite keys
        soft_delete_column: Column to check for soft-delete (e.g., "deleted_at").
                           If provided, only returns nodes where this column IS NULL.
        order_by: Column to order results by (e.g., "step_sequence" for work order steps).
                  Use "column_name DESC" for descending order.

    Returns:
        List of node dicts with requested columns, ordered if order_by specified
    """
    if not node_ids:
        return []

    # Limit results
    if len(node_ids) > MAX_RESULTS:
        node_ids = node_ids[:MAX_RESULTS]

    # Normalize id_column to list
    id_cols = [id_column] if isinstance(id_column, str) else list(id_column)
    is_composite = len(id_cols) > 1

    col_spec = ", ".join(columns) if columns else "*"

    # Build WHERE clause for composite or simple keys
    if is_composite:
        # Composite key: use row value comparison
        col_tuple = f"({', '.join(id_cols)})"
        if node_ids and isinstance(node_ids[0], tuple):
            values_list = ", ".join(
                f"({', '.join('%s' for _ in id_cols)})" for _ in node_ids
            )
            flat_ids = [v for tup in node_ids for v in tup]
            where_clause = f"{col_tuple} IN (VALUES {values_list})"
            params = flat_ids
        else:
            # Single values, wrap each in tuple
            values_list = ", ".join(f"(%s)" for _ in node_ids)
            where_clause = f"{id_cols[0]} IN (VALUES {values_list})"
            params = node_ids
    else:
        where_clause = f"{id_cols[0]} = ANY(%s)"
        params = [node_ids]

    query = f"""
        SELECT {col_spec}
        FROM {nodes_table}
        WHERE {where_clause}
    """
    if soft_delete_column:
        query += f" AND {soft_delete_column} IS NULL"
    if order_by:
        query += f" ORDER BY {order_by}"

    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")
        if is_composite:
            cur.execute(query, params)
        else:
            cur.execute(query, tuple(params))
        col_names = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    nodes = []
    for row in rows:
        node = dict(zip(col_names, row))
        # Convert Decimal to float for numeric fields (prevents TypeError in calculations)
        for key, value in node.items():
            if isinstance(value, Decimal):
                node[key] = float(value)
        nodes.append(node)

    return nodes


def should_stop(
    conn: PgConnection,
    nodes_table: str,
    node_id: NodeId,
    stop_condition: str,
    id_column: str | list[str] = "id",
) -> bool:
    """
    Check if a node matches the stop condition.

    Supports composite keys by accepting lists of column names and tuple IDs.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes
        node_id: Node ID to check (can be tuple for composite keys)
        stop_condition: SQL WHERE clause fragment (e.g., "tier = 3")
        id_column: Name(s) of the ID column(s) - string or list for composite keys

    Returns:
        True if node matches stop condition
    """
    # Normalize id_column to list
    id_cols = [id_column] if isinstance(id_column, str) else list(id_column)
    is_composite = len(id_cols) > 1

    if is_composite:
        # Build composite key match
        conditions = " AND ".join(f"{col} = %s" for col in id_cols)
        params = node_id if isinstance(node_id, tuple) else (node_id,)
    else:
        conditions = f"{id_cols[0]} = %s"
        params = (node_id,)

    query = f"""
        SELECT 1 FROM {nodes_table}
        WHERE {conditions} AND ({stop_condition})
    """

    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone() is not None


def get_connection(
    host: str = "localhost",
    port: int = 5432,
    database: str = "supply_chain",
    user: str = "virt_graph",
    password: str = "dev_password",
) -> PgConnection:
    """
    Get a PostgreSQL connection with standard settings.

    Args:
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password

    Returns:
        PostgreSQL connection
    """
    return psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )
