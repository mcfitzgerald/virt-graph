"""
Core handler infrastructure with safety limits and utilities.

This module provides the foundation for all graph operation handlers:
- Non-negotiable safety limits to prevent runaway queries
- Frontier batching utilities for efficient traversal
- Node estimation for proactive size checks

Note: estimate_reachable_nodes is deprecated. Use the estimator module instead.
"""

import warnings
from typing import Any

import psycopg2
from psycopg2.extensions import connection as PgConnection

# === SAFETY LIMITS (Non-negotiable) ===
MAX_DEPTH = 50  # Absolute traversal depth limit
MAX_NODES = 10_000  # Max nodes to visit in single traversal
MAX_RESULTS = 1_000  # Max rows to return
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
    frontier_ids: list[int],
    edge_from_col: str,
    edge_to_col: str,
    direction: str = "outbound",
) -> list[tuple[int, int]]:
    """
    Fetch all edges for a frontier in a SINGLE query.

    This is the mandatory batching pattern - never one query per node.
    Uses PostgreSQL's ANY operator for efficient IN clause with arrays.

    Args:
        conn: Database connection
        edges_table: Table containing edges
        frontier_ids: List of node IDs in current frontier
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        direction: "outbound", "inbound", or "both"

    Returns:
        List of (from_id, to_id) tuples
    """
    if not frontier_ids:
        return []

    results: list[tuple[int, int]] = []

    with conn.cursor() as cur:
        # Set statement timeout for safety
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")

        if direction == "outbound":
            query = f"""
                SELECT {edge_from_col}, {edge_to_col}
                FROM {edges_table}
                WHERE {edge_from_col} = ANY(%s)
            """
            cur.execute(query, (frontier_ids,))
            results = cur.fetchall()

        elif direction == "inbound":
            query = f"""
                SELECT {edge_from_col}, {edge_to_col}
                FROM {edges_table}
                WHERE {edge_to_col} = ANY(%s)
            """
            cur.execute(query, (frontier_ids,))
            results = cur.fetchall()

        else:  # both
            query = f"""
                SELECT {edge_from_col}, {edge_to_col}
                FROM {edges_table}
                WHERE {edge_from_col} = ANY(%s) OR {edge_to_col} = ANY(%s)
            """
            cur.execute(query, (frontier_ids, frontier_ids))
            results = cur.fetchall()

    return results


def fetch_nodes(
    conn: PgConnection,
    nodes_table: str,
    node_ids: list[int],
    columns: list[str] | None = None,
    id_column: str = "id",
) -> list[dict[str, Any]]:
    """
    Fetch node data for a list of node IDs.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes
        node_ids: List of node IDs to fetch
        columns: Columns to return (None = all)
        id_column: Name of the ID column

    Returns:
        List of node dicts with requested columns
    """
    if not node_ids:
        return []

    # Limit results
    if len(node_ids) > MAX_RESULTS:
        node_ids = node_ids[:MAX_RESULTS]

    col_spec = ", ".join(columns) if columns else "*"

    query = f"""
        SELECT {col_spec}
        FROM {nodes_table}
        WHERE {id_column} = ANY(%s)
    """

    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")
        cur.execute(query, (node_ids,))
        col_names = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    return [dict(zip(col_names, row)) for row in rows]


def should_stop(
    conn: PgConnection,
    nodes_table: str,
    node_id: int,
    stop_condition: str,
    id_column: str = "id",
) -> bool:
    """
    Check if a node matches the stop condition.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes
        node_id: Node ID to check
        stop_condition: SQL WHERE clause fragment (e.g., "tier = 3")
        id_column: Name of the ID column

    Returns:
        True if node matches stop condition
    """
    query = f"""
        SELECT 1 FROM {nodes_table}
        WHERE {id_column} = %s AND ({stop_condition})
    """

    with conn.cursor() as cur:
        cur.execute(query, (node_id,))
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
