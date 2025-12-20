"""
Generators Package - Modular level generators for FMCG data generation.

This package contains the base classes and level-specific generators
for the refactored generate_data.py (see effervescent-shimmying-blum.md).

Base Classes:
- GeneratorContext: Shared state dataclass passed to all generators
- BaseLevelGenerator: Abstract base class for level-specific generators

Level Generators:
- Level0Generator: Reference data (divisions, channels, products, etc.)
- Level 1-2: Source data (suppliers, formulas) [TODO]
- Level 3: Network (locations, DCs) [TODO]
- Level 4: Product (SKUs, promotions) [TODO]
- Level 5-7: Manufacturing (POs, batches, inventory) [TODO]
- Level 8-9: Demand (POS, orders) [TODO]
- Level 10-11: Fulfillment (shipments) [TODO]
- Level 12-13: Returns [TODO]
- Level14Generator: Monitoring (KPIs)
"""

from .base import BaseLevelGenerator, GeneratorContext
from .level_0_reference import Level0Generator
from .level_14_monitoring import Level14Generator

__all__ = [
    # Base classes
    "GeneratorContext",
    "BaseLevelGenerator",
    # Level generators
    "Level0Generator",
    "Level14Generator",
]
