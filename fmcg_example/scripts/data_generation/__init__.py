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

Phase 3 - Bottleneck Elimination:
- LookupCache: Pre-built indices for all FK patterns in generate_data.py
- PooledFaker: Batch Faker sampling wrapper for efficient string generation

Phase 4 - Vectorized Generation:
- POSSalesGenerator: Vectorized POS sales generation (~500K rows)
- OrderLinesGenerator: Vectorized order lines generation (~600K rows)
- ShipmentLegsGenerator: Vectorized shipment legs with delay distributions
- Structured array dtypes and conversion utilities

Future Phases (to be implemented):
- Phase 5: Integration with generate_data.py
"""

from pathlib import Path

from .bottleneck_fixes import LookupCache, PooledFaker
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
from .vectorized import (
    ORDER_LINES_COLUMNS,
    ORDER_LINES_DTYPE,
    POS_SALES_COLUMNS,
    POS_SALES_DTYPE,
    SHIPMENT_LEGS_COLUMNS,
    SHIPMENT_LEGS_DTYPE,
    OrderLinesGenerator,
    POSSalesGenerator,
    ShipmentLegsGenerator,
    VectorizedGenerator,
    apply_promo_effects,
    lumpy_demand,
    structured_to_copy_lines,
    structured_to_dicts,
    zipf_weights,
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
    # Phase 2: Online algorithms
    "WelfordAccumulator",
    "FrequencySketch",
    "CardinalityEstimator",
    "DegreeMonitor",
    # Phase 2: COPY format helpers
    "copy_str",
    "copy_num",
    "copy_bool",
    "copy_date",
    "copy_timestamp",
    "format_copy_value",
    # Phase 3: Bottleneck Elimination
    "LookupCache",
    "PooledFaker",
    # Phase 4: Vectorized Generation
    "VectorizedGenerator",
    "POSSalesGenerator",
    "OrderLinesGenerator",
    "ShipmentLegsGenerator",
    # Phase 4: Dtypes and columns
    "POS_SALES_DTYPE",
    "POS_SALES_COLUMNS",
    "ORDER_LINES_DTYPE",
    "ORDER_LINES_COLUMNS",
    "SHIPMENT_LEGS_DTYPE",
    "SHIPMENT_LEGS_COLUMNS",
    # Phase 4: Utilities
    "zipf_weights",
    "lumpy_demand",
    "apply_promo_effects",
    "structured_to_dicts",
    "structured_to_copy_lines",
    # Paths
    "BENCHMARK_MANIFEST_PATH",
]
