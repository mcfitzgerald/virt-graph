"""
NetworkX-based pathfinding handlers.

Loads subgraph on-demand using frontier-batched queries.
Implements shortest path algorithms with weighted edges.
Supports composite primary/foreign keys - NetworkX handles tuple nodes natively.
"""

from decimal import Decimal
from typing import Any

import networkx as nx
from psycopg2.extensions import connection as PgConnection

from .base import (
    MAX_DEPTH,
    MAX_NODES,
    NodeId,
    QUERY_TIMEOUT_SEC,
    SubgraphTooLarge,
    fetch_edges_for_frontier,
    fetch_nodes,
)


def shortest_path(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    start_id: NodeId,
    end_id: NodeId,
    weight_col: str | None = None,
    max_depth: int = 20,
    id_column: str | list[str] = "id",
    excluded_nodes: list[NodeId] | None = None,
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> dict[str, Any]:
    """
    Find shortest path between two nodes using Dijkstra.

    Loads only the relevant subgraph (nodes reachable from start within max_depth).
    Uses incremental loading to avoid fetching entire graph.
    Supports composite keys - NetworkX handles tuple nodes natively.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes (e.g., "facilities")
        edges_table: Table containing edges (e.g., "transport_routes")
        edge_from_col: Column(s) for edge source - string or list for composite keys
        edge_to_col: Column(s) for edge target - string or list for composite keys
        start_id: Starting node ID (can be tuple for composite keys)
        end_id: Target node ID (can be tuple for composite keys)
        weight_col: Column for edge weights (e.g., "distance_km", "cost_usd")
                    If None, uses hop count (unweighted shortest path)
        max_depth: Maximum search depth
        id_column: Name(s) of the ID column(s) - string or list for composite keys
        excluded_nodes: Node IDs to exclude from path (route around these nodes)
        soft_delete_column: Column to check for soft-delete (e.g., "deleted_at").
                           If provided, excludes nodes where this column IS NOT NULL.
        sql_filter: SQL WHERE clause to filter edges (e.g., "is_active = true")

    Returns:
        dict with:
            - path: list of node IDs from start to end (None if no path)
            - path_nodes: list of node dicts with details
            - distance: total path weight/length (None if no path)
            - edges: list of edge dicts with weights along the path
            - nodes_explored: number of nodes loaded into graph
            - excluded_nodes: list of node IDs that were excluded
            - error: error message if no path found

    Example:
        >>> # Find route from Chicago to LA avoiding Denver Hub
        >>> result = shortest_path(
        ...     conn,
        ...     nodes_table="facilities",
        ...     edges_table="transport_routes",
        ...     edge_from_col="origin_facility_id",
        ...     edge_to_col="destination_facility_id",
        ...     start_id=chicago_id,
        ...     end_id=la_id,
        ...     weight_col="cost_usd",
        ...     excluded_nodes=[denver_id],
        ... )
        >>> print(f"Route avoiding Denver costs ${result['distance']:.2f}")
    """
    max_depth = min(max_depth, MAX_DEPTH)

    # Set of nodes to exclude (for filtering edges)
    excluded_set = set(excluded_nodes) if excluded_nodes else set()

    # Build subgraph incrementally using bidirectional BFS
    # Start from both ends to reduce nodes loaded
    G = nx.DiGraph()

    # Forward search from start
    forward_frontier = {start_id}
    forward_visited = {start_id}

    # Backward search from end
    backward_frontier = {end_id}
    backward_visited = {end_id}

    # Track if we've found a meeting point
    meeting_point = None

    for depth in range(max_depth):
        if not forward_frontier and not backward_frontier:
            break

        if meeting_point is not None:
            break

        # Check if frontiers meet
        intersection = forward_visited & backward_visited
        if intersection:
            meeting_point = next(iter(intersection))
            break

        # Expand forward frontier
        if forward_frontier:
            edges = _fetch_edges_with_weights(
                conn,
                edges_table,
                list(forward_frontier),
                edge_from_col,
                edge_to_col,
                weight_col,
                "outbound",
                nodes_table=nodes_table,
                node_id_column=id_column,
                soft_delete_column=soft_delete_column,
                sql_filter=sql_filter,
            )

            next_forward = set()
            for from_id, to_id, weight in edges:
                # Skip edges involving excluded nodes
                if from_id in excluded_set or to_id in excluded_set:
                    continue
                G.add_edge(from_id, to_id, weight=weight if weight else 1)
                if to_id not in forward_visited:
                    next_forward.add(to_id)
                    forward_visited.add(to_id)

            forward_frontier = next_forward

        # Expand backward frontier
        if backward_frontier:
            edges = _fetch_edges_with_weights(
                conn,
                edges_table,
                list(backward_frontier),
                edge_from_col,
                edge_to_col,
                weight_col,
                "inbound",
                nodes_table=nodes_table,
                node_id_column=id_column,
                soft_delete_column=soft_delete_column,
                sql_filter=sql_filter,
            )

            next_backward = set()
            for from_id, to_id, weight in edges:
                # Skip edges involving excluded nodes
                if from_id in excluded_set or to_id in excluded_set:
                    continue
                G.add_edge(from_id, to_id, weight=weight if weight else 1)
                if from_id not in backward_visited:
                    next_backward.add(from_id)
                    backward_visited.add(from_id)

            backward_frontier = next_backward

        # Check size limit
        total_nodes = len(forward_visited | backward_visited)
        if total_nodes > MAX_NODES:
            raise SubgraphTooLarge(
                f"Path search loaded {total_nodes} nodes, exceeds limit {MAX_NODES}"
            )

        # Check if frontiers meet after expansion
        intersection = forward_visited & backward_visited
        if intersection:
            meeting_point = next(iter(intersection))
            break

    nodes_explored = len(forward_visited | backward_visited)

    # Check if end node is in graph
    if end_id not in G:
        return {
            "path": None,
            "path_nodes": [],
            "distance": None,
            "edges": [],
            "nodes_explored": nodes_explored,
            "error": f"No path found: target node {end_id} not reachable within depth {max_depth}",
        }

    if start_id not in G:
        return {
            "path": None,
            "path_nodes": [],
            "distance": None,
            "edges": [],
            "nodes_explored": nodes_explored,
            "error": f"No path found: start node {start_id} not in graph",
        }

    # Find shortest path
    try:
        if weight_col:
            path = nx.shortest_path(G, start_id, end_id, weight="weight")
            distance = nx.shortest_path_length(G, start_id, end_id, weight="weight")
        else:
            path = nx.shortest_path(G, start_id, end_id)
            distance = len(path) - 1
    except nx.NetworkXNoPath:
        return {
            "path": None,
            "path_nodes": [],
            "distance": None,
            "edges": [],
            "nodes_explored": nodes_explored,
            "error": "No path found between start and end nodes",
        }

    # Fetch node details for path
    path_nodes = fetch_nodes(
        conn, nodes_table, path, id_column=id_column, soft_delete_column=soft_delete_column
    )

    # Get edge details along path
    path_edges = []
    for i in range(len(path) - 1):
        from_id = path[i]
        to_id = path[i + 1]
        edge_weight = G[from_id][to_id].get("weight", 1)
        path_edges.append({
            "from_id": from_id,
            "to_id": to_id,
            "weight": edge_weight,
        })

    return {
        "path": path,
        "path_nodes": path_nodes,
        "distance": distance,
        "edges": path_edges,
        "nodes_explored": nodes_explored,
        "excluded_nodes": excluded_nodes or [],
        "error": None,
    }


def all_shortest_paths(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    start_id: NodeId,
    end_id: NodeId,
    weight_col: str | None = None,
    max_depth: int = 20,
    max_paths: int = 10,
    id_column: str | list[str] = "id",
    excluded_nodes: list[NodeId] | None = None,
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> dict[str, Any]:
    """
    Find all shortest paths between two nodes.

    Useful when there are multiple equivalent optimal routes.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes
        edges_table: Table containing edges
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        start_id: Starting node ID
        end_id: Target node ID
        weight_col: Column for edge weights (None = hop count)
        max_depth: Maximum search depth
        max_paths: Maximum number of paths to return
        id_column: Name of the ID column
        excluded_nodes: Node IDs to exclude from paths (route around these nodes)
        soft_delete_column: Column to check for soft-delete (e.g., "deleted_at").
                           If provided, excludes nodes where this column IS NOT NULL.

    Returns:
        dict with:
            - paths: list of paths (each path is list of node IDs)
            - distance: common distance of all paths
            - path_count: number of paths found
            - nodes_explored: number of nodes loaded
            - excluded_nodes: list of node IDs that were excluded
    """
    # Set of nodes to exclude (for filtering edges)
    excluded_set = set(excluded_nodes) if excluded_nodes else set()

    # First find one shortest path to get the graph
    result = shortest_path(
        conn,
        nodes_table,
        edges_table,
        edge_from_col,
        edge_to_col,
        start_id,
        end_id,
        weight_col,
        max_depth,
        id_column,
        excluded_nodes,
        soft_delete_column,
        sql_filter,
    )

    if result["path"] is None:
        return {
            "paths": [],
            "distance": None,
            "path_count": 0,
            "nodes_explored": result["nodes_explored"],
            "excluded_nodes": excluded_nodes or [],
            "error": result["error"],
        }

    # Rebuild graph for all paths (we need the full graph)
    G = nx.DiGraph()
    frontier = {start_id}
    visited = {start_id}

    for depth in range(max_depth):
        if not frontier or end_id in visited:
            break

        edges = _fetch_edges_with_weights(
            conn,
            edges_table,
            list(frontier),
            edge_from_col,
            edge_to_col,
            weight_col,
            "outbound",
            nodes_table=nodes_table,
            node_id_column=id_column,
            soft_delete_column=soft_delete_column,
            sql_filter=sql_filter,
        )

        next_frontier = set()
        for from_id, to_id, weight in edges:
            # Skip edges involving excluded nodes
            if from_id in excluded_set or to_id in excluded_set:
                continue
            G.add_edge(from_id, to_id, weight=weight if weight else 1)
            if to_id not in visited:
                next_frontier.add(to_id)
                visited.add(to_id)

        frontier = next_frontier

    try:
        if weight_col:
            all_paths = list(nx.all_shortest_paths(G, start_id, end_id, weight="weight"))
        else:
            all_paths = list(nx.all_shortest_paths(G, start_id, end_id))

        # Limit number of paths
        all_paths = all_paths[:max_paths]
    except nx.NetworkXNoPath:
        return {
            "paths": [],
            "distance": None,
            "path_count": 0,
            "nodes_explored": len(visited),
            "excluded_nodes": excluded_nodes or [],
            "error": "No path found",
        }

    return {
        "paths": all_paths,
        "distance": result["distance"],
        "path_count": len(all_paths),
        "nodes_explored": len(visited),
        "excluded_nodes": excluded_nodes or [],
        "error": None,
    }


def _fetch_edges_with_weights(
    conn: PgConnection,
    edges_table: str,
    frontier_ids: list[NodeId],
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    weight_col: str | None,
    direction: str,
    nodes_table: str | None = None,
    node_id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> list[tuple[NodeId, NodeId, float | None]]:
    """
    Fetch edges with optional weights for the frontier.

    Returns list of (from_id, to_id, weight) tuples.
    Supports composite keys - IDs may be tuples.

    Args:
        conn: Database connection
        edges_table: Table containing edges
        frontier_ids: Node IDs in the current frontier (can be tuples)
        edge_from_col: Column(s) for edge source
        edge_to_col: Column(s) for edge target
        weight_col: Optional column for edge weights
        direction: "outbound" or "inbound"
        nodes_table: Table containing nodes (required for soft-delete filtering)
        node_id_column: ID column(s) in nodes_table
        soft_delete_column: Column to check for soft-delete filtering
        sql_filter: SQL WHERE clause for edge filtering
    """
    if not frontier_ids:
        return []

    # Normalize columns to lists
    from_cols = [edge_from_col] if isinstance(edge_from_col, str) else list(edge_from_col)
    to_cols = [edge_to_col] if isinstance(edge_to_col, str) else list(edge_to_col)
    id_cols = [node_id_column] if isinstance(node_id_column, str) else list(node_id_column)

    is_composite = len(from_cols) > 1 or len(to_cols) > 1

    # Build column select expressions
    from_cols_select = ", ".join(f"e.{c}" for c in from_cols)
    to_cols_select = ", ".join(f"e.{c}" for c in to_cols)
    weight_select = f", e.{weight_col}" if weight_col else ""

    # Build soft-delete join clause if needed
    soft_delete_join = ""
    if soft_delete_column and nodes_table:
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

    # Build sql_filter clause
    sql_filter_clause = ""
    if sql_filter:
        sql_filter_clause = f" AND ({sql_filter})"

    # Build frontier matching clause
    def build_frontier_match(cols: list[str]) -> tuple[str, list]:
        if len(cols) == 1:
            return f"e.{cols[0]} = ANY(%s)", [frontier_ids]
        else:
            col_tuple = f"({', '.join(f'e.{c}' for c in cols)})"
            if frontier_ids and isinstance(frontier_ids[0], tuple):
                values_list = ", ".join(
                    f"({', '.join('%s' for _ in cols)})" for _ in frontier_ids
                )
                flat_ids = [v for tup in frontier_ids for v in tup]
                return f"{col_tuple} IN (VALUES {values_list})", flat_ids
            return f"e.{cols[0]} = ANY(%s)", [frontier_ids]

    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")

        if direction == "outbound":
            frontier_clause, frontier_params = build_frontier_match(from_cols)
        else:
            frontier_clause, frontier_params = build_frontier_match(to_cols)

        query = f"""
            SELECT {from_cols_select}, {to_cols_select}{weight_select}
            FROM {edges_table} e
            {soft_delete_join}
            WHERE {frontier_clause}
            {sql_filter_clause}
        """
        cur.execute(query, frontier_params)
        rows = cur.fetchall()

    # Convert results to proper format
    results: list[tuple[NodeId, NodeId, float | None]] = []
    n_from = len(from_cols)
    n_to = len(to_cols)

    for row in rows:
        if is_composite:
            from_id = tuple(row[:n_from]) if n_from > 1 else row[0]
            to_id = tuple(row[n_from:n_from + n_to]) if n_to > 1 else row[n_from]
        else:
            from_id = row[0]
            to_id = row[1]

        if weight_col:
            weight = float(row[-1]) if isinstance(row[-1], Decimal) else row[-1]
        else:
            weight = None

        results.append((from_id, to_id, weight))

    return results
