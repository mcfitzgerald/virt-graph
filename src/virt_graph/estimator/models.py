"""
Estimation models for graph size prediction.

Provides configurable estimation with damping factors that adapt
to detected graph properties.
"""

from dataclasses import dataclass

from .sampler import SampleResult


@dataclass
class EstimationConfig:
    """Configuration for estimation behavior."""

    # Damping parameters
    base_damping: float = 0.85  # Universal damping baseline
    convergence_multiplier: float = 0.8  # Extra damping for convergent graphs
    decreasing_trend_multiplier: float = 0.7  # Extra damping for shrinking frontiers

    # Safety parameters
    safety_margin: float = 1.2  # Multiply estimate by this for safety
    min_safety_margin: float = 1.05  # Minimum margin even for terminated graphs

    # Sampling parameters
    sample_depth: int = 5  # Levels to sample

    # Thresholds
    convergence_threshold: float = 0.95  # Below this, apply convergence damping
    stable_growth_threshold: float = 0.2  # Growth rate change < this is "stable"


def estimate(
    sample: SampleResult,
    max_depth: int,
    table_bound: int | None = None,
    config: EstimationConfig | None = None,
) -> int:
    """
    Estimate reachable nodes with configurable model.

    Uses sampling results and detected properties to produce
    an accurate estimate that won't over- or under-estimate.

    Args:
        sample: Results from GraphSampler.sample()
        max_depth: Maximum depth of planned traversal
        table_bound: Upper bound from table size (caps estimate)
        config: Estimation configuration

    Returns:
        Estimated number of reachable nodes
    """
    config = config or EstimationConfig()

    # If sampling terminated (empty frontier), we have exact count
    if sample.terminated:
        # Still apply minimal safety margin for terminated graphs
        estimate_val = int(sample.visited_count * config.min_safety_margin)
        if table_bound:
            estimate_val = min(estimate_val, table_bound)
        return estimate_val

    # Compute adaptive damping based on detected properties
    damping = _compute_damping(sample, config)

    # Extrapolate from sampled levels
    estimate_val = _damped_extrapolation(
        sample.level_sizes,
        max_depth,
        damping,
        sample.visited_count,
    )

    # Apply safety margin
    estimate_val = int(estimate_val * config.safety_margin)

    # Cap at table bound if provided
    if table_bound:
        estimate_val = min(estimate_val, table_bound)

    return estimate_val


def _compute_damping(sample: SampleResult, config: EstimationConfig) -> float:
    """
    Compute adaptive damping factor based on graph properties.

    The damping factor reduces the extrapolated growth rate to
    account for real-world graph properties like convergence.
    """
    damping = config.base_damping

    # Apply convergence damping if graph shows node sharing
    if sample.convergence_ratio < config.convergence_threshold:
        # More convergence = more damping
        # convergence_ratio of 0.5 means half the nodes are shared
        convergence_factor = sample.convergence_ratio
        damping *= config.convergence_multiplier * convergence_factor + (
            1 - config.convergence_multiplier
        )

    # Apply extra damping for decreasing growth trends
    if sample.growth_trend == "decreasing":
        damping *= config.decreasing_trend_multiplier

    # Clamp to reasonable range
    return max(0.3, min(damping, 1.0))


def _damped_extrapolation(
    level_sizes: list[int],
    max_depth: int,
    damping: float,
    visited_so_far: int,
) -> int:
    """
    Extrapolate from sampled levels using damped growth.

    Uses geometric mean of observed growth rates, damped by
    the computed damping factor.
    """
    if len(level_sizes) < 2:
        return visited_so_far

    # Calculate growth rates from sampled levels
    growth_rates: list[float] = []
    for i in range(1, len(level_sizes)):
        if level_sizes[i - 1] > 0:
            rate = level_sizes[i] / level_sizes[i - 1]
            growth_rates.append(rate)

    if not growth_rates or all(r == 0 for r in growth_rates):
        return visited_so_far

    # Use the recent growth rate (last observed) as base
    # This is more predictive than average for convergent graphs
    recent_rate = growth_rates[-1] if growth_rates[-1] > 0 else sum(growth_rates) / len(
        growth_rates
    )

    # Apply damping
    damped_rate = recent_rate * damping

    # If damped rate <= 1, growth will terminate naturally
    if damped_rate <= 1.0:
        # Geometric series sum: a / (1 - r) for |r| < 1
        if damped_rate < 1.0:
            remaining_estimate = int(
                level_sizes[-1] * damped_rate / (1 - damped_rate)
            )
        else:
            remaining_estimate = level_sizes[-1] * (max_depth - len(level_sizes) + 1)
        return visited_so_far + remaining_estimate

    # Extrapolate remaining levels with damping
    sample_depth = len(level_sizes) - 1  # Level 0 is start
    remaining_depth = max_depth - sample_depth
    if remaining_depth <= 0:
        return visited_so_far

    estimated = visited_so_far
    current_level_size = level_sizes[-1]

    for _ in range(remaining_depth):
        current_level_size = int(current_level_size * damped_rate)
        if current_level_size == 0:
            break
        estimated += current_level_size

        # Apply increasing damping as we go deeper (convergence effect)
        damped_rate *= damping

    return estimated


def estimate_with_early_termination_check(
    sample: SampleResult,
    max_depth: int,
    max_nodes: int,
    table_bound: int | None = None,
    config: EstimationConfig | None = None,
) -> tuple[int, bool]:
    """
    Estimate and check if it exceeds limits.

    Returns both the estimate and whether it's safe to proceed.

    Args:
        sample: Sampling results
        max_depth: Maximum depth
        max_nodes: Node limit
        table_bound: Table size bound
        config: Configuration

    Returns:
        Tuple of (estimated_nodes, is_safe_to_proceed)
    """
    estimated = estimate(sample, max_depth, table_bound, config)
    return estimated, estimated <= max_nodes
