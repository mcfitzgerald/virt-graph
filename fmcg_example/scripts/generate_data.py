#!/usr/bin/env python3
"""
Generate synthetic FMCG supply chain data for Prism Consumer Goods.

Spec: magical-launching-forest.md Phase 4

Target data volumes (~4M rows across ~60 tables):

DOMAIN A - SOURCE (~200K rows):
- 50 ingredients (ING-xxx codes, CAS numbers)
- 200 suppliers (tiered: 40 T1, 80 T2, 80 T3)
- 400 supplier-ingredient links with lead times, MOQs
- 500 certifications (ISO, GMP, Halal, Kosher, RSPO)
- 25,000 purchase orders
- 75,000 purchase order lines
- 20,000 goods receipts
- 60,000 goods receipt lines

DOMAIN B - TRANSFORM (~150K rows):
- 7 plants (Tennessee, Texas, Brazil, China, India, Poland, Turkey)
- 35 production lines (~5 per plant)
- 150 formulas (recipes for ~50 products x 3 variants)
- 1,500 formula ingredients (avg 10 ingredients per formula)
- 50,000 work orders
- 150,000 work order materials
- 50,000 batches (production lots)
- 150,000 batch ingredients
- 50,000 batch cost ledger entries

DOMAIN C - PRODUCT (~10K rows):
- 3 products (PrismWhite, ClearWave, AquaPure)
- 20 packaging types
- 2,000 SKUs (product x packaging x size x region explosion)
- 2,000 SKU costs
- 500 SKU substitute links

DOMAIN D - ORDER (~600K rows):
- 4 channels (B&M Large, B&M Dist, Ecom, DTC)
- 100 promotions (with temporal effectivity and hangover)
- 200,000 orders
- 600,000 order lines

DOMAIN E - FULFILL (~800K rows):
- 5 divisions (NAM, LATAM, APAC, EUR, AFR-EUR)
- 25 distribution centers
- 20 ports
- 100 retail accounts (archetypes)
- 10,000 retail locations (stores)
- 180,000 shipments
- 540,000 shipment lines (with batch_fraction for splitting)
- 50,000 inventory records
- 5,000 pick waves

DOMAIN E2 - LOGISTICS (~50K rows):
- 20 carriers
- 100 carrier contracts (temporal effectivity)
- 1,000 carrier rates
- 200 route segments (atomic legs)
- 50 routes (composed, multi-leg)
- 500 route segment assignments
- 180,000 shipment legs

DOMAIN E3 - ESG (~200K rows):
- 100 emission factors
- 180,000 shipment emissions
- 200 supplier ESG scores
- 50 sustainability targets
- 100 modal shift opportunities

DOMAIN F - PLAN (~600K rows):
- 500,000 POS sales (52 weeks x ~10K stores x ~10 SKUs per store)
- 100,000 demand forecasts
- 10,000 forecast accuracy records
- 5,000 consensus adjustments
- 25,000 replenishment params
- 50,000 demand allocations
- 10,000 capacity plans
- 10,000 supply plans
- 5,000 plan exceptions

DOMAIN G - RETURN (~20K rows):
- 10,000 returns
- 30,000 return lines
- 30,000 disposition logs
- 10,000 RMA authorizations

DOMAIN H - ORCHESTRATE (~500K rows):
- 50 KPI thresholds (Desmet Triangle)
- 50,000 KPI actuals
- 500,000 OSA metrics
- 100 business rules
- 500 risk events
- 50,000 audit log entries

NAMED ENTITIES (Deterministic Testing - Section 4.8):
- B-2024-RECALL-001: Contaminated Sorbitol batch -> 500 stores
- ACCT-MEGA-001: MegaMart (4,500 stores, 25% of orders)
- SUP-PALM-MY-001: Single-source Palm Oil supplier (SPOF)
- DC-NAM-CHI-001: Bottleneck DC Chicago (2,000 stores, 40% NAM volume)
- PROMO-BF-2024: Black Friday 2024 (3x demand, bullwhip)
- LANE-SH-LA-001: Seasonal Shanghai->LA (50% capacity Jan-Feb)
- ING-PALM-001: Palm Oil (60-120 day lead time, 50% OT)
- ING-SORB-001: Sorbitol (single supplier, all toothpaste)
- ING-PEPP-001: Peppermint Oil (Q2-Q3 only, 3x price Q1)

DATA GENERATION PRINCIPLES (Section 4):
- Barabasi-Albert preferential attachment for network topology
- Zipf distribution for SKU popularity (80/20 Pareto rule)
- Lumpy demand with promo spikes and post-promo hangover
- Temporal flickering for seasonal routes and carrier contracts
- FMCG benchmarks: 8-12 inventory turns, 95%+ OTIF, 92-95% OSA

Implementation Status: SCAFFOLD
TODO: Implement data generation logic after schema.sql is complete
"""

import math
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

# TODO: Uncomment after Poetry dependencies verified
# import numpy as np
# from faker import Faker

# Output path
OUTPUT_PATH = Path(__file__).parent.parent / "postgres" / "seed.sql"

# Seed for reproducibility
RANDOM_SEED = 42


# =============================================================================
# SQL Formatting Helpers
# =============================================================================

def sql_str(val: str | None) -> str:
    """Escape string for SQL INSERT statements."""
    if val is None:
        return "NULL"
    return "'" + val.replace("'", "''") + "'"


def sql_num(val: float | int | Decimal | None) -> str:
    """Format number for SQL."""
    if val is None:
        return "NULL"
    return str(val)


def sql_bool(val: bool | None) -> str:
    """Format boolean for SQL."""
    if val is None:
        return "NULL"
    return "true" if val else "false"


def sql_date(val: date | None) -> str:
    """Format date for SQL INSERT statements."""
    if val is None:
        return "NULL"
    return f"'{val.isoformat()}'"


def sql_timestamp(val: datetime | None) -> str:
    """Format timestamp for SQL INSERT statements."""
    if val is None:
        return "NULL"
    return f"'{val.isoformat()}'"


# =============================================================================
# COPY Format Helpers (PostgreSQL bulk loading - 10x faster than INSERT)
# =============================================================================

def copy_str(val: str | None) -> str:
    """Format string for COPY format (tab-separated, \\N for NULL)."""
    if val is None:
        return "\\N"
    # Escape tabs, newlines, backslashes
    return val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


def copy_num(val: float | int | Decimal | None) -> str:
    """Format number for COPY format."""
    if val is None:
        return "\\N"
    return str(val)


def copy_bool(val: bool | None) -> str:
    """Format boolean for COPY format."""
    if val is None:
        return "\\N"
    return "t" if val else "f"


def copy_date(val: date | None) -> str:
    """Format date for COPY format."""
    if val is None:
        return "\\N"
    return val.isoformat()


def copy_timestamp(val: datetime | None) -> str:
    """Format timestamp for COPY format."""
    if val is None:
        return "\\N"
    return val.isoformat()


# =============================================================================
# Distribution Helpers (Section 4 - "Ant Colony" Realism)
# =============================================================================

def zipf_weights(n: int, s: float = 0.8) -> list[float]:
    """
    Generate Zipf-like weights for Pareto distribution.

    Section 4.2: Top 20% of SKUs = 80% of Revenue

    Args:
        n: Number of items
        s: Zipf exponent (0.8 gives roughly 80/20 split)

    Returns:
        List of weights summing to 1.0
    """
    weights = [1.0 / (i + 1) ** s for i in range(n)]
    total = sum(weights)
    return [w / total for w in weights]


def barabasi_albert_attachment(
    existing_degrees: list[int],
    m: int = 1
) -> list[int]:
    """
    Barabasi-Albert preferential attachment.

    Section 4.1: "Rich get richer" - big DCs get more stores.

    Args:
        existing_degrees: Current degree count for each node
        m: Number of connections to make

    Returns:
        Indices of nodes to connect to
    """
    # Add 1 to avoid division by zero for new nodes
    weights = [d + 1 for d in existing_degrees]
    total = sum(weights)
    probs = [w / total for w in weights]

    # TODO: Use numpy.random.choice when implemented
    # return list(np.random.choice(len(weights), size=m, replace=False, p=probs))

    # Fallback: simple weighted selection
    selected = []
    for _ in range(m):
        r = random.random()
        cumulative = 0
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative and i not in selected:
                selected.append(i)
                break
    return selected


def lumpy_demand(
    base_demand: float,
    week: int,
    is_promo_week: bool = False,
    is_post_promo_week: bool = False,
    noise_std: float = 0.15
) -> float:
    """
    Generate lumpy demand with seasonality, noise, and promo effects.

    Section 4.4: Real demand is lumpy, not smooth sine waves.

    Args:
        base_demand: Base weekly demand
        week: Week of year (1-52)
        is_promo_week: True if promotion is active
        is_post_promo_week: True if week after promo (hangover)
        noise_std: Standard deviation of Gaussian noise

    Returns:
        Adjusted demand value
    """
    # Seasonality: ~30% variation following annual cycle
    seasonality = 1.0 + 0.3 * math.sin(2 * math.pi * week / 52)

    # Random noise
    noise = random.gauss(0, noise_std)

    # Promotion effect with HANGOVER
    if is_promo_week:
        promo_effect = 2.5  # 150% lift during promo
    elif is_post_promo_week:
        promo_effect = 0.7  # 30% DIP after promo (hangover)
    else:
        promo_effect = 1.0

    return max(0, base_demand * (seasonality + noise) * promo_effect)


# =============================================================================
# Named Entity Generators (Section 4.8)
# =============================================================================

def create_named_entities() -> dict[str, Any]:
    """
    Create deterministic named entities for testing.

    Returns dict with entity codes mapped to their special properties.
    """
    return {
        # Contaminated batch for recall trace testing
        "B-2024-RECALL-001": {
            "type": "batch",
            "ingredient": "ING-SORB-001",
            "affected_stores": 500,
            "status": "QUALITY_HOLD",
        },

        # MegaMart hot node (hub stress test)
        "ACCT-MEGA-001": {
            "type": "retail_account",
            "store_count": 4500,
            "order_share": 0.25,  # 25% of all orders
            "channel": "B&M Large",
        },

        # Single-source Palm Oil (SPOF detection)
        "SUP-PALM-MY-001": {
            "type": "supplier",
            "ingredient": "ING-PALM-001",
            "is_sole_source": True,
            "country": "Malaysia",
        },

        # Bottleneck DC Chicago (centrality testing)
        "DC-NAM-CHI-001": {
            "type": "distribution_center",
            "stores_served": 2000,
            "volume_share": 0.40,  # 40% of NAM volume
            "division": "NAM",
        },

        # Black Friday 2024 (bullwhip effect)
        "PROMO-BF-2024": {
            "type": "promotion",
            "lift_multiplier": 3.0,
            "hangover_multiplier": 0.6,
            "week": 47,
        },

        # Seasonal ocean lane (temporal routing)
        "LANE-SH-LA-001": {
            "type": "route_segment",
            "origin": "Shanghai",
            "destination": "Los Angeles",
            "seasonal_capacity": {
                1: 0.50, 2: 0.50,  # Jan-Feb: 50% capacity
                12: 0.75,  # Dec: 75% capacity
            },
        },

        # Problem ingredients
        "ING-PALM-001": {
            "type": "ingredient",
            "name": "Palm Oil",
            "lead_time_range": (60, 120),  # 2-4 months
            "on_time_rate": 0.50,
        },
        "ING-SORB-001": {
            "type": "ingredient",
            "name": "Sorbitol",
            "supplier_count": 1,  # Single qualified supplier
            "product_coverage": 1.0,  # All toothpaste
        },
        "ING-PEPP-001": {
            "type": "ingredient",
            "name": "Peppermint Oil",
            "available_quarters": [2, 3],  # Q2-Q3 only
            "off_season_price_multiplier": 3.0,
        },
    }


# =============================================================================
# Generator Classes (Stubs)
# =============================================================================

class DivisionGenerator:
    """Generate 5 global divisions."""

    DIVISIONS = [
        {"code": "NAM", "name": "North America", "hq": "Knoxville, TN"},
        {"code": "LATAM", "name": "Latin America", "hq": "São Paulo"},
        {"code": "APAC", "name": "Asia Pacific", "hq": "Singapore"},
        {"code": "EUR", "name": "Europe", "hq": "Paris"},
        {"code": "AFR-EUR", "name": "Africa & Middle East", "hq": "Dubai"},
    ]

    def generate(self) -> list[dict]:
        # TODO: Implement full generation
        return self.DIVISIONS


class PlantGenerator:
    """Generate 7 manufacturing plants."""

    PLANTS = [
        {"code": "PLANT-NAM-TN", "name": "Tennessee Plant", "division": "NAM", "country": "USA"},
        {"code": "PLANT-NAM-TX", "name": "Texas Plant", "division": "NAM", "country": "USA"},
        {"code": "PLANT-LATAM-BR", "name": "Brazil Plant", "division": "LATAM", "country": "Brazil"},
        {"code": "PLANT-APAC-CN", "name": "China Plant", "division": "APAC", "country": "China"},
        {"code": "PLANT-APAC-IN", "name": "India Plant", "division": "APAC", "country": "India"},
        {"code": "PLANT-EUR-PL", "name": "Poland Plant", "division": "EUR", "country": "Poland"},
        {"code": "PLANT-AFR-TR", "name": "Turkey Plant", "division": "AFR-EUR", "country": "Turkey"},
    ]

    def generate(self) -> list[dict]:
        # TODO: Implement full generation
        return self.PLANTS


class ProductGenerator:
    """Generate 3 product families."""

    PRODUCTS = [
        {
            "code": "PROD-PW",
            "name": "PrismWhite",
            "category": "Oral Care",
            "description": "Premium toothpaste line",
        },
        {
            "code": "PROD-CW",
            "name": "ClearWave",
            "category": "Home Care",
            "description": "Dish soap and cleaning products",
        },
        {
            "code": "PROD-AP",
            "name": "AquaPure",
            "category": "Personal Care",
            "description": "Body wash and shower products",
        },
    ]

    def generate(self) -> list[dict]:
        # TODO: Implement full generation
        return self.PRODUCTS


class ChannelGenerator:
    """Generate 4 sales channels."""

    CHANNELS = [
        {"code": "B2M-LARGE", "name": "B&M Large Retail", "volume_share": 0.40},
        {"code": "B2M-DIST", "name": "B&M Distributor", "volume_share": 0.30},
        {"code": "ECOM", "name": "E-commerce", "volume_share": 0.20},
        {"code": "DTC", "name": "Direct to Consumer", "volume_share": 0.10},
    ]

    def generate(self) -> list[dict]:
        # TODO: Implement full generation
        return self.CHANNELS


# =============================================================================
# Main Generator Orchestration
# =============================================================================

class FMCGDataGenerator:
    """
    Orchestrates generation of all FMCG data.

    Generation order follows dependency graph:
    1. Reference data (divisions, plants, channels, products)
    2. Master data (ingredients, suppliers, SKUs, locations)
    3. Transactional data (orders, batches, shipments)
    4. Metrics data (OSA, KPIs, forecasts)
    """

    def __init__(self, seed: int = RANDOM_SEED):
        random.seed(seed)
        # TODO: np.random.seed(seed)
        # TODO: Faker.seed(seed)

        self.named_entities = create_named_entities()
        self.generated_data: dict[str, list] = {}

    def generate_all(self) -> None:
        """Generate all data in dependency order."""
        print("=" * 60)
        print("Prism Consumer Goods - Data Generation")
        print("=" * 60)
        print()
        print("Status: SCAFFOLD - Not yet implemented")
        print()
        print("Prerequisites:")
        print("  1. Complete Phase 2: schema.sql with ~60 tables")
        print("  2. Install dependencies: poetry install")
        print()
        print("Generation Order:")
        print("  1. Reference data (divisions, plants, channels)")
        print("  2. Master data (ingredients, suppliers, SKUs)")
        print("  3. Transactional data (orders, batches, shipments)")
        print("  4. Metrics data (OSA, KPIs, forecasts)")
        print()
        print("Target: ~4M rows total")
        print()
        print("Reference: magical-launching-forest.md Phase 4")

    def write_sql(self, output_path: Path = OUTPUT_PATH) -> None:
        """Write generated data to SQL file."""
        # TODO: Implement after generate_all() is complete
        raise NotImplementedError("SQL generation pending Phase 4 implementation")


def main():
    """Generate FMCG data and write to seed.sql."""
    generator = FMCGDataGenerator()
    generator.generate_all()


if __name__ == "__main__":
    main()
