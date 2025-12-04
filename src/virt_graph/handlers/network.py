"""
NetworkX-based network analysis handlers.

Provides centrality calculations, connected components, and other
graph-level analytics. These operations typically require loading
larger portions of the graph.
"""

from typing import Any, Literal

import networkx as nx
from psycopg2.extensions import connection as PgConnection

from .base import (
    MAX_NODES,
    MAX_RESULTS,
    QUERY_TIMEOUT_SEC,
    SubgraphTooLarge,
    fetch_nodes,
)


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
    G = _load_full_graph(conn, edges_table, edge_from_col, edge_to_col, weight_col)

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
    nodes_data = fetch_nodes(conn, nodes_table, node_ids, id_column=id_column)

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
    edge_from_col: str,
    edge_to_col: str,
    min_size: int = 1,
    id_column: str = "id",
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
    G = _load_full_graph(conn, edges_table, edge_from_col, edge_to_col)

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
        sample_nodes = fetch_nodes(conn, nodes_table, sample_ids, id_column=id_column)

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
    edge_from_col: str,
    edge_to_col: str,
    weight_col: str | None = None,
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

    Returns:
        dict with graph statistics
    """
    G = _load_full_graph(conn, edges_table, edge_from_col, edge_to_col, weight_col)

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
    edge_from_col: str,
    edge_to_col: str,
    node_id: int,
    direction: Literal["outbound", "inbound", "both"] = "both",
    id_column: str = "id",
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

    Returns:
        dict with:
            - neighbors: list of neighbor node dicts
            - outbound_count: number of outgoing edges
            - inbound_count: number of incoming edges
    """
    outbound_ids = []
    inbound_ids = []

    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")

        if direction in ("outbound", "both"):
            cur.execute(
                f"SELECT {edge_to_col} FROM {edges_table} WHERE {edge_from_col} = %s",
                (node_id,),
            )
            outbound_ids = [row[0] for row in cur.fetchall()]

        if direction in ("inbound", "both"):
            cur.execute(
                f"SELECT {edge_from_col} FROM {edges_table} WHERE {edge_to_col} = %s",
                (node_id,),
            )
            inbound_ids = [row[0] for row in cur.fetchall()]

    # Combine unique neighbor IDs
    all_neighbor_ids = list(set(outbound_ids + inbound_ids))

    # Fetch neighbor details
    neighbors_data = fetch_nodes(
        conn, nodes_table, all_neighbor_ids, id_column=id_column
    )

    return {
        "neighbors": neighbors_data,
        "outbound_count": len(outbound_ids),
        "inbound_count": len(inbound_ids),
        "total_degree": len(all_neighbor_ids),
    }


def _load_full_graph(
    conn: PgConnection,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    weight_col: str | None = None,
) -> nx.DiGraph:
    """
    Load entire graph from edge table.

    Creates a directed graph (DiGraph) by default since most relationships
    in our ontology are directional.
    """
    G = nx.DiGraph()

    weight_select = f", {weight_col}" if weight_col else ""

    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{QUERY_TIMEOUT_SEC * 1000}'")
        cur.execute(f"""
            SELECT {edge_from_col}, {edge_to_col}{weight_select}
            FROM {edges_table}
        """)
        rows = cur.fetchall()

    for row in rows:
        from_id, to_id = row[0], row[1]
        if weight_col:
            G.add_edge(from_id, to_id, weight=row[2])
        else:
            G.add_edge(from_id, to_id)

    return G
