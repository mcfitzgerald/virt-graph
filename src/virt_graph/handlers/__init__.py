"""
Graph operation handlers.

This package provides schema-parameterized handlers for graph operations:
- traversal: BFS/DFS with configurable stop conditions
- pathfinding: Dijkstra shortest path via NetworkX
- network: Centrality, connected components
"""

from .base import (
    MAX_DEPTH,
    MAX_NODES,
    MAX_RESULTS,
    QUERY_TIMEOUT_SEC,
    SafetyLimitExceeded,
    SubgraphTooLarge,
    check_limits,
    estimate_reachable_nodes,
    fetch_edges_for_frontier,
    fetch_nodes,
)
from .traversal import traverse

__all__ = [
    # Constants
    "MAX_DEPTH",
    "MAX_NODES",
    "MAX_RESULTS",
    "QUERY_TIMEOUT_SEC",
    # Exceptions
    "SafetyLimitExceeded",
    "SubgraphTooLarge",
    # Functions
    "check_limits",
    "estimate_reachable_nodes",
    "fetch_edges_for_frontier",
    "fetch_nodes",
    "traverse",
]
