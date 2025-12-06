"""
Graph sampling with automatic property detection.

Samples a graph to detect structural properties (convergence, cycles, hubs)
that inform estimation and traversal strategy selection.
"""

from dataclasses import dataclass
from typing import Literal

from psycopg2.extensions import connection as PgConnection


@dataclass
class SampleResult:
    """Results from graph sampling with auto-detected properties."""

    # Basic metrics
    visited_count: int
    level_sizes: list[int]
    terminated: bool  # Hit empty frontier before depth limit

    # Auto-detected properties (free from sampling)
    growth_trend: Literal["increasing", "stable", "decreasing"]
    convergence_ratio: float  # visited/total_edges_seen (1.0 = tree, <1 = DAG with sharing)
    has_cycles: bool  # Same node reachable via different paths (in sampling)

    # Hub detection
    max_expansion_factor: float  # Largest level-to-level jump
    hub_detected: bool  # expansion_factor > threshold

    # Raw data for custom analysis
    edges_seen: int  # Total edges encountered during sampling


class GraphSampler:
    """
    Samples a graph structure and detects properties automatically.

    Use this to make informed decisions about traversal strategy
    before committing to a full traversal.
    """

    def __init__(
        self,
        conn: PgConnection,
        edges_table: str,
        from_col: str,
        to_col: str,
        direction: str = "outbound",
        hub_threshold: float = 50.0,
    ):
        """
        Initialize sampler.

        Args:
            conn: Database connection
            edges_table: Table containing edges
            from_col: Column for edge source
            to_col: Column for edge target
            direction: "outbound", "inbound", or "both"
            hub_threshold: Expansion factor threshold for hub detection
        """
        self.conn = conn
        self.edges_table = edges_table
        self.from_col = from_col
        self.to_col = to_col
        self.direction = direction
        self.hub_threshold = hub_threshold

    def sample(self, start_id: int, depth: int = 5) -> SampleResult:
        """
        Sample graph and detect properties automatically.

        Performs BFS for `depth` levels and collects metrics to
        characterize the graph structure.

        Args:
            start_id: Starting node ID
            depth: Number of levels to sample (default 5)

        Returns:
            SampleResult with detected properties
        """
        frontier = {start_id}
        visited = {start_id}
        level_sizes = [1]  # Level 0 has 1 node
        total_edges_seen = 0
        expansion_factors: list[float] = []
        terminated = False

        for _ in range(depth):
            if not frontier:
                terminated = True
                break

            edges = self._fetch_edges(list(frontier))
            total_edges_seen += len(edges)

            next_frontier: set[int] = set()
            for from_id, to_id in edges:
                target = self._get_target(from_id, to_id, frontier)
                if target is not None and target not in visited:
                    next_frontier.add(target)
                    visited.add(target)

            # Calculate expansion factor
            if frontier:
                expansion = len(next_frontier) / len(frontier) if frontier else 0.0
                expansion_factors.append(expansion)

            level_sizes.append(len(next_frontier))
            frontier = next_frontier

        # If frontier is empty after depth levels, we terminated
        if not frontier:
            terminated = True

        # Detect properties from collected metrics
        growth_trend = self._detect_growth_trend(level_sizes)
        convergence_ratio = self._compute_convergence_ratio(len(visited), total_edges_seen)
        max_expansion = max(expansion_factors) if expansion_factors else 0.0
        hub_detected = max_expansion > self.hub_threshold

        # Cycle detection: if convergence_ratio < 1.0 significantly, nodes are shared
        # This is a heuristic - true cycle detection requires path tracking
        has_cycles = convergence_ratio < 0.9 and not terminated

        return SampleResult(
            visited_count=len(visited),
            level_sizes=level_sizes,
            terminated=terminated,
            growth_trend=growth_trend,
            convergence_ratio=convergence_ratio,
            has_cycles=has_cycles,
            max_expansion_factor=max_expansion,
            hub_detected=hub_detected,
            edges_seen=total_edges_seen,
        )

    def _fetch_edges(self, frontier_ids: list[int]) -> list[tuple[int, int]]:
        """Fetch edges for frontier nodes."""
        if not frontier_ids:
            return []

        with self.conn.cursor() as cur:
            if self.direction == "outbound":
                query = f"""
                    SELECT {self.from_col}, {self.to_col}
                    FROM {self.edges_table}
                    WHERE {self.from_col} = ANY(%s)
                """
                cur.execute(query, (frontier_ids,))
            elif self.direction == "inbound":
                query = f"""
                    SELECT {self.from_col}, {self.to_col}
                    FROM {self.edges_table}
                    WHERE {self.to_col} = ANY(%s)
                """
                cur.execute(query, (frontier_ids,))
            else:  # both
                query = f"""
                    SELECT {self.from_col}, {self.to_col}
                    FROM {self.edges_table}
                    WHERE {self.from_col} = ANY(%s) OR {self.to_col} = ANY(%s)
                """
                cur.execute(query, (frontier_ids, frontier_ids))

            return cur.fetchall()

    def _get_target(
        self, from_id: int, to_id: int, frontier: set[int]
    ) -> int | None:
        """Get target node based on direction."""
        if self.direction == "outbound":
            return to_id
        elif self.direction == "inbound":
            return from_id
        else:  # both
            if from_id in frontier:
                return to_id
            elif to_id in frontier:
                return from_id
            return None

    def _detect_growth_trend(
        self, level_sizes: list[int]
    ) -> Literal["increasing", "stable", "decreasing"]:
        """Detect overall growth trend from level sizes."""
        if len(level_sizes) < 3:
            return "stable"

        # Compare early vs late growth rates
        # Skip level 0 (always 1) and use levels 1-end
        sizes = level_sizes[1:]  # Exclude start node
        if len(sizes) < 2:
            return "stable"

        # Calculate growth rates between consecutive levels
        growth_rates: list[float] = []
        for i in range(1, len(sizes)):
            if sizes[i - 1] > 0:
                growth_rates.append(sizes[i] / sizes[i - 1])
            else:
                growth_rates.append(0.0)

        if not growth_rates:
            return "stable"

        # Compare first half vs second half average growth
        mid = len(growth_rates) // 2
        if mid == 0:
            return "stable"

        early_avg = sum(growth_rates[:mid]) / mid
        late_avg = sum(growth_rates[mid:]) / len(growth_rates[mid:])

        if late_avg > early_avg * 1.2:
            return "increasing"
        elif late_avg < early_avg * 0.8:
            return "decreasing"
        return "stable"

    def _compute_convergence_ratio(self, visited: int, edges_seen: int) -> float:
        """
        Compute convergence ratio.

        For a tree, visited = edges + 1, so ratio ~ 1.0
        For a DAG with node sharing, ratio < 1.0
        """
        if edges_seen == 0:
            return 1.0
        # In a tree: visited = edges + 1
        # ratio = visited / (edges + 1)
        expected_tree_nodes = edges_seen + 1
        return visited / expected_tree_nodes if expected_tree_nodes > 0 else 1.0
