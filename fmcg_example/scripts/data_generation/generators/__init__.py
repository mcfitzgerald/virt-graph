"""
Generators Package - Modular level generators for FMCG data generation.

This package contains the base classes and level-specific generators
for the refactored generate_data.py (see effervescent-shimmying-blum.md).

Base Classes:
- GeneratorContext: Shared state dataclass passed to all generators
- BaseLevelGenerator: Abstract base class for level-specific generators

Level Generators (to be added in subsequent phases):
- Level 0: Reference data (divisions, channels, products, etc.)
- Level 1-2: Source data (suppliers, formulas)
- Level 3: Network (locations, DCs)
- Level 4: Product (SKUs, promotions)
- Level 5-7: Manufacturing (POs, batches, inventory)
- Level 8-9: Demand (POS, orders)
- Level 10-11: Fulfillment (shipments)
- Level 12-13: Returns
- Level 14: Monitoring (KPIs)
"""

from .base import BaseLevelGenerator, GeneratorContext

__all__ = [
    "GeneratorContext",
    "BaseLevelGenerator",
]
