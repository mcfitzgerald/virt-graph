"""
NetworkX-based pathfinding handlers.

Loads subgraph on-demand using frontier-batched queries.
Implements shortest path algorithms with weighted edges.
"""

from typing import Any

import networkx as nx
from psycopg2.extensions import connection as PgConnection

from .base import (
    MAX_DEPTH,
    MAX_NODES,
    QUERY_TIMEOUT_SEC,
    SubgraphTooLarge,
    fetch_edges_for_frontier,
    fetch_nodes,
)


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

    Loads only the relevant subgraph (nodes reachable from start within max_depth).
    Uses incremental loading to avoid fetching entire graph.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes (e.g., "facilities")
        edges_table: Table containing edges (e.g., "transport_routes")
        edge_from_col: Column for edge source (e.g., "origin_facility_id")
        edge_to_col: Column for edge target (e.g., "destination_facility_id")
        start_id: Starting node ID
        end_id: Target node ID
        weight_col: Column for edge weights (e.g., "distance_km", "cost_usd")
                    If None, uses hop count (unweighted shortest path)
        max_depth: Maximum search depth
        id_column: Name of the ID column in nodes_table

    Returns:
        dict with:
            - path: list of node IDs from start to end (None if no path)
            - path_nodes: list of node dicts with details
            - distance: total path weight/length (None if no path)
            - edges: list of edge dicts with weights along the path
            - nodes_explored: number of nodes loaded into graph
            - error: error message if no path found

    Example:
        >>> result = shortest_path(
        ...     conn,
        ...     nodes_table="facilities",
        ...     edges_table="transport_routes",
        ...     edge_from_col="origin_facility_id",
        ...     edge_to_col="destination_facility_id",
        ...     start_id=chicago_id,
        ...     end_id=la_id,
        ...     weight_col="cost_usd",
        ... )
        >>> print(f"Cheapest route costs ${result['distance']:.2f}")
    """
    max_depth = min(max_depth, MAX_DEPTH)

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
            )

            next_forward = set()
            for from_id, to_id, weight in edges:
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
            )

            next_backward = set()
            for from_id, to_id, weight in edges:
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
    path_nodes = fetch_nodes(conn, nodes_table, path, id_column=id_column)

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
        "error": None,
    }


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

    Returns:
        dict with:
            - paths: list of paths (each path is list of node IDs)
            - distance: common distance of all paths
            - path_count: number of paths found
            - nodes_explored: number of nodes loaded
    """
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
    )

    if result["path"] is None:
        return {
            "paths": [],
            "distance": None,
            "path_count": 0,
            "nodes_explored": result["nodes_explored"],
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
        )

        next_frontier = set()
        for from_id, to_id, weight in edges:
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
            "error": "No path found",
        }

    return {
        "paths": all_paths,
        "distance": result["distance"],
        "path_count": len(all_paths),
        "nodes_explored": len(visited),
        "error": None,
    }


def _fetch_edges_with_weights(
    conn: PgConnection,
    edges_table: str,
    frontier_ids: list[int],
    edge_from_col: str,
    edge_to_col: str,
    weight_col: str | None,
    direction: str,
) -> list[tuple[int, int, float | None]]:
    """
    Fetch edges with optional weights for the frontier.

    Returns list of (from_id, to_id, weight) tuples.
    """
    if not frontier_ids:
        return []

    weight_select = f", {weight_col}" if weight_col else ""

    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")

        if direction == "outbound":
            query = f"""
                SELECT {edge_from_col}, {edge_to_col}{weight_select}
                FROM {edges_table}
                WHERE {edge_from_col} = ANY(%s)
            """
        else:  # inbound
            query = f"""
                SELECT {edge_from_col}, {edge_to_col}{weight_select}
                FROM {edges_table}
                WHERE {edge_to_col} = ANY(%s)
            """

        cur.execute(query, (frontier_ids,))
        rows = cur.fetchall()

    # Add weight column (or None if not present)
    if weight_col:
        return [(row[0], row[1], row[2]) for row in rows]
    else:
        return [(row[0], row[1], None) for row in rows]
