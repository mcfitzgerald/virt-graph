"""
Runtime guards for graph traversal safety.

Provides decision logic for whether to proceed with traversal
and what strategy to use.
"""

from dataclasses import dataclass
from typing import Literal

from .bounds import TableStats
from .models import EstimationConfig, estimate
from .sampler import SampleResult


@dataclass
class GuardResult:
    """Result of runtime guard checks."""

    safe_to_proceed: bool
    recommended_action: Literal[
        "traverse",  # Safe to proceed with BFS
        "aggregate",  # Use COUNT instead of traversal
        "switch_networkx",  # Load to NetworkX for algorithm
        "abort",  # Too large, require filter
        "warn_and_proceed",  # Over limit but can proceed with caution
    ]
    reason: str | None
    estimated_nodes: int | None
    warnings: list[str]


def check_guards(
    sample: SampleResult,
    max_depth: int,
    max_nodes: int = 10_000,
    stats: TableStats | None = None,
    table_bound: int | None = None,
    estimation_config: EstimationConfig | None = None,
) -> GuardResult:
    """
    Runtime decision logic for traversal safety.

    Checks:
    1. Scout Check: Hub detected? → Abort
    2. Structure Check: Junction table? → Aggregate instead
    3. Volume Check: Estimate vs limits

    Args:
        sample: Results from GraphSampler
        max_depth: Maximum traversal depth
        max_nodes: Node limit (default 10,000)
        stats: Optional table stats for structural checks
        table_bound: Optional upper bound from table
        estimation_config: Optional estimation config

    Returns:
        GuardResult with recommendation
    """
    warnings: list[str] = []
    estimated = estimate(sample, max_depth, table_bound, estimation_config)

    # 1. Scout Check: Hub detected
    if sample.hub_detected:
        return GuardResult(
            safe_to_proceed=False,
            recommended_action="abort",
            reason=(
                f"Hub node detected with expansion factor {sample.max_expansion_factor:.1f}x. "
                "Add filters to reduce scope or increase hub_threshold in sampler."
            ),
            estimated_nodes=estimated,
            warnings=warnings,
        )

    # 2. Structure Check: Junction table (if stats available)
    if stats and stats.is_junction:
        warnings.append(
            "Junction table detected (composite PK). Consider using COUNT aggregation."
        )
        # Don't abort, just warn - junction tables are often fine for traversal

    # 3. Structure Check: Cycles detected
    if sample.has_cycles:
        warnings.append(
            "Possible cycles detected in graph. NetworkX may handle this better."
        )
        # For cycles, we might want to switch to NetworkX which handles visited sets better
        # But don't abort - our BFS also handles visited

    # 4. Volume Check: Terminated early
    if sample.terminated:
        return GuardResult(
            safe_to_proceed=True,
            recommended_action="traverse",
            reason=f"Graph terminated at depth {len(sample.level_sizes) - 1} with {sample.visited_count} nodes.",
            estimated_nodes=sample.visited_count,
            warnings=warnings,
        )

    # 5. Volume Check: Estimate vs limit
    if estimated > max_nodes:
        # Check if table bound is actually smaller
        if table_bound and table_bound < max_nodes:
            warnings.append(
                f"Estimate ({estimated:,}) exceeds limit but table bound ({table_bound:,}) is smaller."
            )
            return GuardResult(
                safe_to_proceed=True,
                recommended_action="warn_and_proceed",
                reason=f"Table bound ({table_bound:,}) is below limit despite high estimate.",
                estimated_nodes=min(estimated, table_bound),
                warnings=warnings,
            )

        # Over limit
        return GuardResult(
            safe_to_proceed=False,
            recommended_action="abort",
            reason=(
                f"Estimated {estimated:,} nodes exceeds limit of {max_nodes:,}. "
                "Consider: max_nodes=N to increase limit, or skip_estimation=True to bypass."
            ),
            estimated_nodes=estimated,
            warnings=warnings,
        )

    # 6. Volume Check: Safe to proceed
    return GuardResult(
        safe_to_proceed=True,
        recommended_action="traverse",
        reason=f"Estimated {estimated:,} nodes within limit of {max_nodes:,}.",
        estimated_nodes=estimated,
        warnings=warnings,
    )


def should_use_networkx(
    sample: SampleResult,
    stats: TableStats | None = None,
    algorithm: str | None = None,
) -> tuple[bool, str | None]:
    """
    Determine if NetworkX should be used instead of SQL-based traversal.

    Args:
        sample: Sampling results
        stats: Optional table stats
        algorithm: Algorithm being used (e.g., "shortest_path", "centrality")

    Returns:
        Tuple of (should_use_networkx, reason)
    """
    # Algorithms that always need NetworkX
    networkx_algorithms = {"shortest_path", "centrality", "pagerank", "betweenness"}
    if algorithm and algorithm.lower() in networkx_algorithms:
        return True, f"Algorithm '{algorithm}' requires NetworkX."

    # Cycles strongly suggest NetworkX
    if sample.has_cycles:
        return True, "Cycles detected; NetworkX handles cycle detection better."

    # High density suggests matrix operations
    if stats and stats.density and stats.density > 0.5:
        return True, f"High density ({stats.density:.2f}) suggests matrix operations."

    return False, None


def check_size_estimate(
    sample: SampleResult,
    max_depth: int,
    max_nodes: int,
    table_bound: int | None = None,
    config: EstimationConfig | None = None,
) -> tuple[int, bool, str]:
    """
    Quick check if estimated size is within limits.

    Simpler interface than full check_guards for common case.

    Args:
        sample: Sampling results
        max_depth: Maximum depth
        max_nodes: Node limit
        table_bound: Optional table bound
        config: Optional estimation config

    Returns:
        Tuple of (estimated, is_safe, message)
    """
    estimated = estimate(sample, max_depth, table_bound, config)

    if sample.terminated:
        return sample.visited_count, True, f"Exact: {sample.visited_count} nodes"

    if estimated <= max_nodes:
        return estimated, True, f"Safe: ~{estimated:,} nodes (limit: {max_nodes:,})"

    if table_bound and table_bound <= max_nodes:
        return table_bound, True, f"Capped: table bound {table_bound:,} <= limit"

    return (
        estimated,
        False,
        f"Unsafe: ~{estimated:,} nodes exceeds limit {max_nodes:,}",
    )
