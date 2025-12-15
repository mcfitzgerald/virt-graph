"""
Graph operation handlers.

This package provides schema-parameterized handlers for graph operations:
- traversal: BFS/DFS with configurable stop conditions
- pathfinding: Dijkstra shortest path via NetworkX
- network: Centrality, connected components

For estimation configuration, import from virt_graph.estimator:
    from virt_graph.estimator import EstimationConfig
"""

from .base import (
    MAX_DEPTH,
    MAX_NODES,
    MAX_RESULTS,
    QUERY_TIMEOUT_SEC,
    SafetyLimitExceeded,
    SubgraphTooLarge,
    check_limits,
    estimate_reachable_nodes,  # DEPRECATED - use virt_graph.estimator
    fetch_edges_for_frontier,
    fetch_nodes,
    # Result TypedDicts for type hints
    AllShortestPathsResult,
    CentralityResult,
    PathAggregateResult,
    ResilienceResult,
    ShortestPathResult,
    TraverseResult,
)
from .network import (
    centrality,
    connected_components,
    graph_density,
    neighbors,
    resilience_analysis,
)
from .pathfinding import (
    all_shortest_paths,
    shortest_path,
)
from .traversal import (
    path_aggregate,
    traverse,
    traverse_collecting,
)

# Re-export EstimationConfig for convenience
from ..estimator import EstimationConfig

__all__ = [
    # Constants
    "MAX_DEPTH",
    "MAX_NODES",
    "MAX_RESULTS",
    "QUERY_TIMEOUT_SEC",
    # Exceptions
    "SafetyLimitExceeded",
    "SubgraphTooLarge",
    # Base functions
    "check_limits",
    "estimate_reachable_nodes",  # DEPRECATED
    "fetch_edges_for_frontier",
    "fetch_nodes",
    # Result TypedDicts
    "TraverseResult",
    "PathAggregateResult",
    "ShortestPathResult",
    "AllShortestPathsResult",
    "CentralityResult",
    "ResilienceResult",
    # Estimation config
    "EstimationConfig",
    # Traversal handlers
    "traverse",
    "traverse_collecting",
    "path_aggregate",
    # Pathfinding handlers
    "shortest_path",
    "all_shortest_paths",
    # Network handlers
    "centrality",
    "connected_components",
    "graph_density",
    "neighbors",
    "resilience_analysis",
]
