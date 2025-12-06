"""
Graph estimator module for improved size estimation and runtime guards.

This module provides:
- Intelligent graph sampling with property detection
- Configurable estimation models with damping
- DDL-derived bounds and table statistics
- Runtime guards for safe traversal decisions
"""

from .bounds import TableStats, get_table_bound, get_table_stats
from .guards import GuardResult, check_guards
from .models import EstimationConfig, estimate
from .sampler import GraphSampler, SampleResult

__all__ = [
    # Sampler
    "GraphSampler",
    "SampleResult",
    # Models
    "estimate",
    "EstimationConfig",
    # Bounds
    "get_table_bound",
    "get_table_stats",
    "TableStats",
    # Guards
    "check_guards",
    "GuardResult",
]
