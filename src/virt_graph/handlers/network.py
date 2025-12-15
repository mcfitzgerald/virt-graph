"""
NetworkX-based network analysis handlers.

Provides centrality calculations, connected components, and other
graph-level analytics. These operations typically require loading
larger portions of the graph.
Supports composite primary/foreign keys - NetworkX handles tuple nodes natively.
"""

from decimal import Decimal
from typing import Any, Literal

import networkx as nx
from psycopg2.extensions import connection as PgConnection

from .base import (
    MAX_NODES,
    MAX_RESULTS,
    NodeId,
    QUERY_TIMEOUT_SEC,
    SubgraphTooLarge,
    fetch_nodes,
)


def centrality(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    centrality_type: Literal["degree", "betweenness", "closeness", "pagerank"] = "degree",
    top_n: int = 10,
    weight_col: str | None = None,
    id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> dict[str, Any]:
    """
    Calculate centrality for nodes in the graph.

    Returns top N most central nodes with their scores.

    WARNING: Loads entire graph into memory. Only use for small-medium graphs.
    Will raise SubgraphTooLarge if graph exceeds MAX_NODES.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes (e.g., "facilities")
        edges_table: Table containing edges (e.g., "transport_routes")
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        centrality_type: Type of centrality to calculate:
            - "degree": Number of connections (fast)
            - "betweenness": Bridge nodes between clusters (slower)
            - "closeness": Average distance to all nodes (medium)
            - "pagerank": Importance based on incoming links (medium)
        top_n: Number of top nodes to return (default 10)
        weight_col: Column for edge weights (used by some centrality measures)
        id_column: Name of the ID column in nodes_table
        soft_delete_column: Column to check for soft-delete (e.g., "deleted_at").
                           If provided, excludes nodes where this column IS NOT NULL.

    Returns:
        dict with:
            - results: list of {node: dict, score: float} sorted by score desc
            - centrality_type: type of centrality calculated
            - graph_stats: basic graph statistics
            - nodes_loaded: total nodes in graph

    Example:
        >>> result = centrality(
        ...     conn,
        ...     nodes_table="facilities",
        ...     edges_table="transport_routes",
        ...     edge_from_col="origin_facility_id",
        ...     edge_to_col="destination_facility_id",
        ...     centrality_type="betweenness",
        ... )
        >>> print(f"Most critical facility: {result['results'][0]['node']['name']}")
    """
    # Load full graph
    G = _load_full_graph(
        conn, edges_table, edge_from_col, edge_to_col, weight_col,
        nodes_table=nodes_table, node_id_column=id_column, soft_delete_column=soft_delete_column,
        sql_filter=sql_filter
    )

    node_count = G.number_of_nodes()
    edge_count = G.number_of_edges()

    if node_count > MAX_NODES:
        raise SubgraphTooLarge(
            f"Graph has {node_count:,} nodes, exceeds limit {MAX_NODES:,}. "
            "Consider filtering to a subgraph."
        )

    # Calculate centrality based on type
    if centrality_type == "degree":
        scores = nx.degree_centrality(G)
    elif centrality_type == "betweenness":
        # Use weight if available for betweenness
        if weight_col:
            scores = nx.betweenness_centrality(G, weight="weight")
        else:
            scores = nx.betweenness_centrality(G)
    elif centrality_type == "closeness":
        scores = nx.closeness_centrality(G)
    elif centrality_type == "pagerank":
        scores = nx.pagerank(G)
    else:
        raise ValueError(f"Unknown centrality type: {centrality_type}")

    # Sort and get top N
    sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_nodes = sorted_nodes[:min(top_n, MAX_RESULTS)]

    # Fetch node details
    node_ids = [node_id for node_id, _ in top_nodes]
    nodes_data = fetch_nodes(
        conn, nodes_table, node_ids, id_column=id_column, soft_delete_column=soft_delete_column
    )

    # Create lookup for node data
    node_lookup = {n[id_column]: n for n in nodes_data}

    # Build results
    results = []
    for node_id, score in top_nodes:
        node_data = node_lookup.get(node_id, {id_column: node_id})
        results.append({
            "node": node_data,
            "score": score,
        })

    return {
        "results": results,
        "centrality_type": centrality_type,
        "graph_stats": {
            "nodes": node_count,
            "edges": edge_count,
            "density": nx.density(G),
            "is_connected": nx.is_weakly_connected(G) if G.is_directed() else nx.is_connected(G),
        },
        "nodes_loaded": node_count,
    }


def connected_components(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    min_size: int = 1,
    id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> dict[str, Any]:
    """
    Find connected components in the graph.

    Useful for identifying isolated clusters or verifying network connectivity.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes
        edges_table: Table containing edges
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        min_size: Minimum component size to return (default 1)
        id_column: Name of the ID column
        soft_delete_column: Column to check for soft-delete (e.g., "deleted_at").
                           If provided, excludes nodes where this column IS NOT NULL.

    Returns:
        dict with:
            - components: list of components, each with:
                - node_ids: set of node IDs in component
                - size: number of nodes
                - sample_nodes: first few node details
            - component_count: total number of components
            - largest_component_size: size of largest component
            - isolated_nodes: nodes with no connections
    """
    G = _load_full_graph(
        conn, edges_table, edge_from_col, edge_to_col,
        nodes_table=nodes_table, node_id_column=id_column, soft_delete_column=soft_delete_column,
        sql_filter=sql_filter
    )

    if G.number_of_nodes() > MAX_NODES:
        raise SubgraphTooLarge(
            f"Graph has {G.number_of_nodes():,} nodes, exceeds limit {MAX_NODES:,}"
        )

    # Get weakly connected components for directed graph
    if G.is_directed():
        components = list(nx.weakly_connected_components(G))
    else:
        components = list(nx.connected_components(G))

    # Filter by min_size and sort by size descending
    components = [c for c in components if len(c) >= min_size]
    components.sort(key=len, reverse=True)

    # Build results with sample nodes
    results = []
    for component in components[:MAX_RESULTS]:
        node_ids = list(component)
        sample_ids = node_ids[:5]  # Sample first 5 nodes
        sample_nodes = fetch_nodes(
            conn, nodes_table, sample_ids, id_column=id_column, soft_delete_column=soft_delete_column
        )

        results.append({
            "node_ids": node_ids,
            "size": len(node_ids),
            "sample_nodes": sample_nodes,
        })

    # Find isolated nodes (degree 0)
    isolated = list(nx.isolates(G))

    return {
        "components": results,
        "component_count": len(components),
        "largest_component_size": len(components[0]) if components else 0,
        "isolated_nodes": isolated,
        "graph_stats": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
        },
    }


def graph_density(
    conn: PgConnection,
    edges_table: str,
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    weight_col: str | None = None,
    nodes_table: str | None = None,
    node_id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> dict[str, Any]:
    """
    Calculate graph density and basic statistics.

    Useful for understanding graph structure without fetching node details.

    Args:
        conn: Database connection
        edges_table: Table containing edges
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        weight_col: Optional weight column
        nodes_table: Table containing nodes (required for soft-delete filtering)
        node_id_column: ID column in nodes_table
        soft_delete_column: Column to check for soft-delete filtering

    Returns:
        dict with graph statistics
    """
    G = _load_full_graph(
        conn, edges_table, edge_from_col, edge_to_col, weight_col,
        nodes_table=nodes_table, node_id_column=node_id_column, soft_delete_column=soft_delete_column,
        sql_filter=sql_filter
    )

    if G.number_of_nodes() > MAX_NODES:
        raise SubgraphTooLarge(
            f"Graph has {G.number_of_nodes():,} nodes, exceeds limit {MAX_NODES:,}"
        )

    stats = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": nx.density(G),
        "is_directed": G.is_directed(),
    }

    if G.is_directed():
        stats["is_weakly_connected"] = nx.is_weakly_connected(G)
        if nx.is_weakly_connected(G):
            stats["is_strongly_connected"] = nx.is_strongly_connected(G)
    else:
        stats["is_connected"] = nx.is_connected(G)

    # Degree statistics
    degrees = [d for _, d in G.degree()]
    if degrees:
        stats["avg_degree"] = sum(degrees) / len(degrees)
        stats["max_degree"] = max(degrees)
        stats["min_degree"] = min(degrees)

    return stats


def neighbors(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    node_id: NodeId,
    direction: Literal["outbound", "inbound", "both"] = "both",
    id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> dict[str, Any]:
    """
    Get direct neighbors of a node.

    Simple single-hop query useful for exploring graph structure.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes
        edges_table: Table containing edges
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        node_id: Node to get neighbors for
        direction: Direction to look for neighbors
        id_column: Name of the ID column
        soft_delete_column: Column to check for soft-delete (e.g., "deleted_at").
                           If provided, excludes nodes where this column IS NOT NULL.

    Returns:
        dict with:
            - neighbors: list of neighbor node dicts
            - outbound_count: number of outgoing edges
            - inbound_count: number of incoming edges
    """
    outbound_ids = []
    inbound_ids = []

    # Build soft-delete join clause if needed
    soft_delete_join_out = ""
    soft_delete_join_in = ""
    if soft_delete_column:
        soft_delete_join_out = f"""
            JOIN {nodes_table} n ON e.{edge_to_col} = n.{id_column}
                AND n.{soft_delete_column} IS NULL
        """
        soft_delete_join_in = f"""
            JOIN {nodes_table} n ON e.{edge_from_col} = n.{id_column}
                AND n.{soft_delete_column} IS NULL
        """

    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")

        if direction in ("outbound", "both"):
            if soft_delete_column:
                cur.execute(
                    f"SELECT e.{edge_to_col} FROM {edges_table} e {soft_delete_join_out} WHERE e.{edge_from_col} = %s",
                    (node_id,),
                )
            else:
                cur.execute(
                    f"SELECT {edge_to_col} FROM {edges_table} WHERE {edge_from_col} = %s",
                    (node_id,),
                )
            outbound_ids = [row[0] for row in cur.fetchall()]

        if direction in ("inbound", "both"):
            if soft_delete_column:
                cur.execute(
                    f"SELECT e.{edge_from_col} FROM {edges_table} e {soft_delete_join_in} WHERE e.{edge_to_col} = %s",
                    (node_id,),
                )
            else:
                cur.execute(
                    f"SELECT {edge_from_col} FROM {edges_table} WHERE {edge_to_col} = %s",
                    (node_id,),
                )
            inbound_ids = [row[0] for row in cur.fetchall()]

    # Combine unique neighbor IDs
    all_neighbor_ids = list(set(outbound_ids + inbound_ids))

    # Fetch neighbor details
    neighbors_data = fetch_nodes(
        conn, nodes_table, all_neighbor_ids, id_column=id_column, soft_delete_column=soft_delete_column
    )

    return {
        "neighbors": neighbors_data,
        "outbound_count": len(outbound_ids),
        "inbound_count": len(inbound_ids),
        "total_degree": len(all_neighbor_ids),
    }


def resilience_analysis(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    node_to_remove: NodeId,
    id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> dict[str, Any]:
    """
    Analyze network resilience by simulating node removal.

    Calculates which node pairs lose connectivity if a specific node is removed.
    Useful for identifying single points of failure in supply chains or transport networks.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes (e.g., "facilities")
        edges_table: Table containing edges (e.g., "transport_routes")
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        node_to_remove: Node ID to simulate removal of
        id_column: Name of the ID column
        soft_delete_column: Column to check for soft-delete (e.g., "deleted_at").
                           If provided, excludes nodes where this column IS NOT NULL.

    Returns:
        dict with:
            - node_removed: the node ID that was simulated as removed
            - node_removed_info: dict with node details
            - disconnected_pairs: list of (node_a, node_b) tuples that lose connectivity
            - components_before: number of connected components before removal
            - components_after: number of connected components after removal
            - component_increase: how many new components were created
            - isolated_nodes: nodes that become completely disconnected
            - affected_node_count: total nodes affected by the removal
            - is_critical: True if removal increases components or isolates nodes

    Example:
        >>> # Check what happens if Denver Hub goes offline
        >>> result = resilience_analysis(
        ...     conn,
        ...     nodes_table="facilities",
        ...     edges_table="transport_routes",
        ...     edge_from_col="origin_facility_id",
        ...     edge_to_col="destination_facility_id",
        ...     node_to_remove=denver_id,
        ... )
        >>> print(f"Removing hub creates {result['component_increase']} new components")
        >>> print(f"Disconnected pairs: {result['disconnected_pairs']}")
    """
    # Load full graph
    G = _load_full_graph(
        conn, edges_table, edge_from_col, edge_to_col,
        nodes_table=nodes_table, node_id_column=id_column, soft_delete_column=soft_delete_column,
        sql_filter=sql_filter
    )

    if G.number_of_nodes() > MAX_NODES:
        raise SubgraphTooLarge(
            f"Graph has {G.number_of_nodes():,} nodes, exceeds limit {MAX_NODES:,}"
        )

    # Check if node exists in graph
    if node_to_remove not in G:
        return {
            "node_removed": node_to_remove,
            "node_removed_info": {},
            "disconnected_pairs": [],
            "components_before": 0,
            "components_after": 0,
            "component_increase": 0,
            "isolated_nodes": [],
            "affected_node_count": 0,
            "is_critical": False,
            "error": f"Node {node_to_remove} not found in graph",
        }

    # Get node info
    node_info = fetch_nodes(
        conn, nodes_table, [node_to_remove], id_column=id_column, soft_delete_column=soft_delete_column
    )
    node_info_dict = node_info[0] if node_info else {}

    # Analyze before removal
    components_before = nx.number_weakly_connected_components(G)

    # Get neighbors of the node (these might become disconnected)
    predecessors = list(G.predecessors(node_to_remove))
    successors = list(G.successors(node_to_remove))
    all_neighbors = list(set(predecessors + successors))

    # Create graph without the node
    G_removed = G.copy()
    G_removed.remove_node(node_to_remove)

    components_after = nx.number_weakly_connected_components(G_removed)
    component_increase = components_after - components_before

    # Find disconnected pairs (pairs of neighbors that can no longer reach each other)
    disconnected_pairs = []
    if component_increase > 0 and len(all_neighbors) > 1:
        # Get the components after removal
        component_map = {}
        for i, comp in enumerate(nx.weakly_connected_components(G_removed)):
            for node in comp:
                component_map[node] = i

        # Check which neighbor pairs are now in different components
        for i, n1 in enumerate(all_neighbors):
            for n2 in all_neighbors[i + 1:]:
                if n1 in component_map and n2 in component_map:
                    if component_map[n1] != component_map[n2]:
                        disconnected_pairs.append((n1, n2))

    # Find isolated nodes (degree 0 after removal)
    isolated_nodes = [n for n in G_removed.nodes() if G_removed.degree(n) == 0]

    # Calculate affected nodes
    affected_nodes = set()
    for pair in disconnected_pairs:
        affected_nodes.add(pair[0])
        affected_nodes.add(pair[1])
    affected_nodes.update(isolated_nodes)

    return {
        "node_removed": node_to_remove,
        "node_removed_info": node_info_dict,
        "disconnected_pairs": disconnected_pairs,
        "components_before": components_before,
        "components_after": components_after,
        "component_increase": component_increase,
        "isolated_nodes": isolated_nodes,
        "affected_node_count": len(affected_nodes),
        "is_critical": component_increase > 0 or len(isolated_nodes) > 0,
        "error": None,
    }


def _load_full_graph(
    conn: PgConnection,
    edges_table: str,
    edge_from_col: str | list[str],
    edge_to_col: str | list[str],
    weight_col: str | None = None,
    nodes_table: str | None = None,
    node_id_column: str | list[str] = "id",
    soft_delete_column: str | None = None,
    sql_filter: str | None = None,
) -> nx.DiGraph:
    """
    Load entire graph from edge table.

    Creates a directed graph (DiGraph) by default since most relationships
    in our ontology are directional. NetworkX handles tuple nodes natively
    for composite key support.

    Args:
        conn: Database connection
        edges_table: Table containing edges
        edge_from_col: Column(s) for edge source
        edge_to_col: Column(s) for edge target
        weight_col: Optional column for edge weights
        nodes_table: Table containing nodes (required for soft-delete filtering)
        node_id_column: ID column(s) in nodes_table
        soft_delete_column: Column to check for soft-delete filtering
        sql_filter: SQL WHERE clause for edge filtering
    """
    G = nx.DiGraph()

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
        sql_filter_clause = f"WHERE ({sql_filter})" if not soft_delete_join else f"AND ({sql_filter})"

    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")

        query = f"""
            SELECT {from_cols_select}, {to_cols_select}{weight_select}
            FROM {edges_table} e
            {soft_delete_join}
            {sql_filter_clause}
        """
        cur.execute(query)
        rows = cur.fetchall()

    # Convert results to proper format
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
            # Convert Decimal to float for weights
            weight = float(row[-1]) if isinstance(row[-1], Decimal) else row[-1]
            G.add_edge(from_id, to_id, weight=weight)
        else:
            G.add_edge(from_id, to_id)

    return G
