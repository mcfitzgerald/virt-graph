"""
Data Generation Module - Performance-optimized utilities for FMCG data generation.

This module provides foundational classes for the O(N) refactor of generate_data.py.
See robust-frolicking-coral.md for the full performance architecture plan.

Phase 1 - Foundation Classes:
- StaticDataPool: Pre-generated Faker data for O(1) vectorized sampling
- LookupIndex: Generic O(1) lookup index for grouped data
- LookupBuilder: Factory for building lookup indices from row dicts

Future Phases (to be implemented):
- Phase 2: StreamingWriter, RealismMonitor, BenchmarkManifest
- Phase 3: Vectorized generators, risk events, quirks injection
"""

from .lookup_builder import LookupBuilder, LookupIndex
from .static_pool import StaticDataPool

__all__ = [
    "StaticDataPool",
    "LookupIndex",
    "LookupBuilder",
]
