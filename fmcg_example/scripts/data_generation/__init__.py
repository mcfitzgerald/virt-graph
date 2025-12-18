"""
Data Generation Module - Performance-optimized utilities for FMCG data generation.

This module provides foundational classes for the O(N) refactor of generate_data.py.
See robust-frolicking-coral.md for the full performance architecture plan.

Phase 1 - Foundation Classes:
- StaticDataPool: Pre-generated Faker data for O(1) vectorized sampling
- LookupIndex: Generic O(1) lookup index for grouped data
- LookupBuilder: Factory for building lookup indices from row dicts

Phase 2 - Streaming Validation Architecture:
- StreamingWriter: Memory-efficient streaming output with FK-aware management
- DependencyTracker: FK dependency graph for safe table memory purging
- RealismMonitor: Online streaming validation with O(1) space algorithms
- StochasticMode: Enum for normal vs disrupted distribution modes
- WelfordAccumulator: Online mean/variance computation
- FrequencySketch: Approximate frequency counting
- CardinalityEstimator: Unique element counting
- DegreeMonitor: Network hub concentration tracking

Future Phases (to be implemented):
- Phase 3: Bottleneck elimination with lookup integration
- Phase 4: Vectorized generators for high-volume tables
- Phase 5: Integration with generate_data.py
"""

from pathlib import Path

from .lookup_builder import LookupBuilder, LookupIndex
from .realism_monitor import (
    CardinalityEstimator,
    DegreeMonitor,
    FrequencySketch,
    RealismMonitor,
    RealismViolationError,
    StochasticMode,
    WelfordAccumulator,
)
from .static_pool import StaticDataPool
from .streaming_writer import (
    DependencyTracker,
    StreamingWriter,
    copy_bool,
    copy_date,
    copy_num,
    copy_str,
    copy_timestamp,
    format_copy_value,
)

# Path to default benchmark manifest
BENCHMARK_MANIFEST_PATH = Path(__file__).parent / "benchmark_manifest.json"

__all__ = [
    # Phase 1: Foundation
    "StaticDataPool",
    "LookupIndex",
    "LookupBuilder",
    # Phase 2: Streaming Validation
    "StreamingWriter",
    "DependencyTracker",
    "RealismMonitor",
    "RealismViolationError",
    "StochasticMode",
    # Online algorithms
    "WelfordAccumulator",
    "FrequencySketch",
    "CardinalityEstimator",
    "DegreeMonitor",
    # COPY format helpers
    "copy_str",
    "copy_num",
    "copy_bool",
    "copy_date",
    "copy_timestamp",
    "format_copy_value",
    # Paths
    "BENCHMARK_MANIFEST_PATH",
]
