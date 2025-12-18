#!/usr/bin/env python3
"""
Generate synthetic FMCG supply chain data for Prism Consumer Goods.

Spec: magical-launching-forest.md Phase 4
Detailed Plan: jolly-sauteeing-fern.md

Target data volumes (~7.5M rows across 67 tables):

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

Implementation Status: Step 1 - CLI and Setup Complete
"""

import argparse
import math
import random
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
from faker import Faker

# Phase 5: Data Generation Performance Module Integration
from data_generation import (
    BENCHMARK_MANIFEST_PATH,
    DependencyTracker,
    LookupBuilder,
    LookupCache,
    PooledFaker,
    RealismMonitor,
    RealismViolationError,
    StaticDataPool,
    StochasticMode,
    StreamingWriter,
    # Vectorized generators
    POSSalesGenerator,
    OrderLinesGenerator,
    structured_to_dicts,
    zipf_weights as np_zipf_weights,
)

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
    m: int = 1,
    rng: np.random.Generator | None = None
) -> list[int]:
    """
    Barabasi-Albert preferential attachment.

    Section 4.1: "Rich get richer" - big DCs get more stores.

    Args:
        existing_degrees: Current degree count for each node
        m: Number of connections to make
        rng: numpy random generator (uses global if None)

    Returns:
        Indices of nodes to connect to
    """
    if rng is None:
        rng = np.random.default_rng()

    # Add 1 to avoid division by zero for new nodes
    weights = np.array([d + 1 for d in existing_degrees], dtype=float)
    probs = weights / weights.sum()

    # Use numpy for efficient weighted selection
    m = min(m, len(weights))  # Can't select more than available
    selected = rng.choice(len(weights), size=m, replace=False, p=probs)
    return selected.tolist()


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
# Reference Data Constants
# =============================================================================

# Hardcoded divisions (5 global)
DIVISIONS = [
    {"code": "NAM", "name": "North America", "hq_city": "Knoxville", "hq_country": "USA", "president": "Sarah Chen", "revenue_target": 5_000_000_000},
    {"code": "LATAM", "name": "Latin America", "hq_city": "São Paulo", "hq_country": "Brazil", "president": "Carlos Rodriguez", "revenue_target": 2_500_000_000},
    {"code": "APAC", "name": "Asia Pacific", "hq_city": "Singapore", "hq_country": "Singapore", "president": "Wei Zhang", "revenue_target": 4_000_000_000},
    {"code": "EUR", "name": "Europe", "hq_city": "Paris", "hq_country": "France", "president": "Marie Dubois", "revenue_target": 2_000_000_000},
    {"code": "AFR-EUR", "name": "Africa & Middle East", "hq_city": "Dubai", "hq_country": "UAE", "president": "Ahmed Hassan", "revenue_target": 1_500_000_000},
]

# Hardcoded channels (4 types)
CHANNELS = [
    {"code": "B2M-LARGE", "name": "B&M Large Retail", "channel_type": "bm_large", "volume_pct": 40, "margin_pct": 18, "payment_days": 45},
    {"code": "B2M-DIST", "name": "B&M Distributor", "channel_type": "bm_distributor", "volume_pct": 30, "margin_pct": 22, "payment_days": 30},
    {"code": "ECOM", "name": "E-commerce", "channel_type": "ecommerce", "volume_pct": 20, "margin_pct": 25, "payment_days": 15},
    {"code": "DTC", "name": "Direct to Consumer", "channel_type": "dtc", "volume_pct": 10, "margin_pct": 35, "payment_days": 0},
]

# Hardcoded products (3 product families)
PRODUCTS = [
    {"code": "PROD-PW", "name": "PrismWhite", "brand": "PrismWhite", "category": "oral_care", "subcategory": "toothpaste", "launch_date": "2015-01-15"},
    {"code": "PROD-CW", "name": "ClearWave", "brand": "ClearWave", "category": "home_care", "subcategory": "dish_soap", "launch_date": "2012-06-01"},
    {"code": "PROD-AP", "name": "AquaPure", "brand": "AquaPure", "category": "personal_care", "subcategory": "body_wash", "launch_date": "2018-03-20"},
]

# Hardcoded plants (7 manufacturing facilities)
PLANTS = [
    {"code": "PLT-NAM-TN", "name": "Tennessee Plant", "division": "NAM", "country": "USA", "city": "Memphis", "capacity_tons": 500, "lat": 35.1495, "lon": -90.0490},
    {"code": "PLT-NAM-TX", "name": "Texas Plant", "division": "NAM", "country": "USA", "city": "Houston", "capacity_tons": 400, "lat": 29.7604, "lon": -95.3698},
    {"code": "PLT-LATAM-BR", "name": "Brazil Plant", "division": "LATAM", "country": "Brazil", "city": "São Paulo", "capacity_tons": 350, "lat": -23.5505, "lon": -46.6333},
    {"code": "PLT-APAC-CN", "name": "China Plant", "division": "APAC", "country": "China", "city": "Suzhou", "capacity_tons": 600, "lat": 31.2989, "lon": 120.5853},
    {"code": "PLT-APAC-IN", "name": "India Plant", "division": "APAC", "country": "India", "city": "Mumbai", "capacity_tons": 350, "lat": 19.0760, "lon": 72.8777},
    {"code": "PLT-EUR-PL", "name": "Poland Plant", "division": "EUR", "country": "Poland", "city": "Łódź", "capacity_tons": 300, "lat": 51.7592, "lon": 19.4560},
    {"code": "PLT-AFR-TR", "name": "Turkey Plant", "division": "AFR-EUR", "country": "Turkey", "city": "Istanbul", "capacity_tons": 250, "lat": 41.0082, "lon": 28.9784},
]

# Hardcoded DCs (25 distribution centers)
DCS = [
    # NAM (8 DCs)
    {"code": "DC-NAM-CHI-001", "name": "Chicago Hub", "division": "NAM", "country": "USA", "city": "Chicago", "dc_type": "national", "capacity_cases": 2_000_000, "lat": 41.8781, "lon": -87.6298},
    {"code": "DC-NAM-ATL-001", "name": "Atlanta DC", "division": "NAM", "country": "USA", "city": "Atlanta", "dc_type": "regional", "capacity_cases": 800_000, "lat": 33.7490, "lon": -84.3880},
    {"code": "DC-NAM-DAL-001", "name": "Dallas DC", "division": "NAM", "country": "USA", "city": "Dallas", "dc_type": "regional", "capacity_cases": 700_000, "lat": 32.7767, "lon": -96.7970},
    {"code": "DC-NAM-LAX-001", "name": "Los Angeles DC", "division": "NAM", "country": "USA", "city": "Los Angeles", "dc_type": "regional", "capacity_cases": 900_000, "lat": 34.0522, "lon": -118.2437},
    {"code": "DC-NAM-SEA-001", "name": "Seattle DC", "division": "NAM", "country": "USA", "city": "Seattle", "dc_type": "regional", "capacity_cases": 400_000, "lat": 47.6062, "lon": -122.3321},
    {"code": "DC-NAM-NYC-001", "name": "New York Metro DC", "division": "NAM", "country": "USA", "city": "Newark", "dc_type": "regional", "capacity_cases": 600_000, "lat": 40.7357, "lon": -74.1724},
    {"code": "DC-NAM-TOR-001", "name": "Toronto DC", "division": "NAM", "country": "Canada", "city": "Toronto", "dc_type": "regional", "capacity_cases": 500_000, "lat": 43.6532, "lon": -79.3832},
    {"code": "DC-NAM-ECM-001", "name": "E-commerce Fulfillment", "division": "NAM", "country": "USA", "city": "Indianapolis", "dc_type": "ecommerce", "capacity_cases": 300_000, "lat": 39.7684, "lon": -86.1581},
    # LATAM (4 DCs)
    {"code": "DC-LATAM-SP-001", "name": "São Paulo DC", "division": "LATAM", "country": "Brazil", "city": "São Paulo", "dc_type": "national", "capacity_cases": 600_000, "lat": -23.5505, "lon": -46.6333},
    {"code": "DC-LATAM-MEX-001", "name": "Mexico City DC", "division": "LATAM", "country": "Mexico", "city": "Mexico City", "dc_type": "regional", "capacity_cases": 400_000, "lat": 19.4326, "lon": -99.1332},
    {"code": "DC-LATAM-BA-001", "name": "Buenos Aires DC", "division": "LATAM", "country": "Argentina", "city": "Buenos Aires", "dc_type": "regional", "capacity_cases": 250_000, "lat": -34.6037, "lon": -58.3816},
    {"code": "DC-LATAM-LIM-001", "name": "Lima DC", "division": "LATAM", "country": "Peru", "city": "Lima", "dc_type": "cross_dock", "capacity_cases": 150_000, "lat": -12.0464, "lon": -77.0428},
    # APAC (6 DCs)
    {"code": "DC-APAC-SHA-001", "name": "Shanghai DC", "division": "APAC", "country": "China", "city": "Shanghai", "dc_type": "national", "capacity_cases": 800_000, "lat": 31.2304, "lon": 121.4737},
    {"code": "DC-APAC-GZ-001", "name": "Guangzhou DC", "division": "APAC", "country": "China", "city": "Guangzhou", "dc_type": "regional", "capacity_cases": 500_000, "lat": 23.1291, "lon": 113.2644},
    {"code": "DC-APAC-MUM-001", "name": "Mumbai DC", "division": "APAC", "country": "India", "city": "Mumbai", "dc_type": "national", "capacity_cases": 400_000, "lat": 19.0760, "lon": 72.8777},
    {"code": "DC-APAC-SIN-001", "name": "Singapore Hub", "division": "APAC", "country": "Singapore", "city": "Singapore", "dc_type": "regional", "capacity_cases": 350_000, "lat": 1.3521, "lon": 103.8198},
    {"code": "DC-APAC-SYD-001", "name": "Sydney DC", "division": "APAC", "country": "Australia", "city": "Sydney", "dc_type": "regional", "capacity_cases": 250_000, "lat": -33.8688, "lon": 151.2093},
    {"code": "DC-APAC-TYO-001", "name": "Tokyo DC", "division": "APAC", "country": "Japan", "city": "Tokyo", "dc_type": "regional", "capacity_cases": 300_000, "lat": 35.6762, "lon": 139.6503},
    # EUR (4 DCs)
    {"code": "DC-EUR-AMS-001", "name": "Amsterdam Hub", "division": "EUR", "country": "Netherlands", "city": "Amsterdam", "dc_type": "national", "capacity_cases": 500_000, "lat": 52.3676, "lon": 4.9041},
    {"code": "DC-EUR-LON-001", "name": "London DC", "division": "EUR", "country": "UK", "city": "London", "dc_type": "regional", "capacity_cases": 350_000, "lat": 51.5074, "lon": -0.1278},
    {"code": "DC-EUR-PAR-001", "name": "Paris DC", "division": "EUR", "country": "France", "city": "Paris", "dc_type": "regional", "capacity_cases": 300_000, "lat": 48.8566, "lon": 2.3522},
    {"code": "DC-EUR-WAR-001", "name": "Warsaw DC", "division": "EUR", "country": "Poland", "city": "Warsaw", "dc_type": "cross_dock", "capacity_cases": 200_000, "lat": 52.2297, "lon": 21.0122},
    # AFR-EUR (3 DCs)
    {"code": "DC-AFR-DXB-001", "name": "Dubai Hub", "division": "AFR-EUR", "country": "UAE", "city": "Dubai", "dc_type": "national", "capacity_cases": 400_000, "lat": 25.2048, "lon": 55.2708},
    {"code": "DC-AFR-JNB-001", "name": "Johannesburg DC", "division": "AFR-EUR", "country": "South Africa", "city": "Johannesburg", "dc_type": "regional", "capacity_cases": 250_000, "lat": -26.2041, "lon": 28.0473},
    {"code": "DC-AFR-CAI-001", "name": "Cairo DC", "division": "AFR-EUR", "country": "Egypt", "city": "Cairo", "dc_type": "regional", "capacity_cases": 200_000, "lat": 30.0444, "lon": 31.2357},
]

# Key ports for logistics
PORTS = [
    {"code": "USCHI", "name": "Chicago Intermodal", "port_type": "rail", "country": "USA", "city": "Chicago", "lat": 41.8781, "lon": -87.6298},
    {"code": "USLAX", "name": "Los Angeles", "port_type": "ocean", "country": "USA", "city": "Los Angeles", "lat": 33.7405, "lon": -118.2609},
    {"code": "USNYC", "name": "New York/New Jersey", "port_type": "ocean", "country": "USA", "city": "Newark", "lat": 40.6688, "lon": -74.1490},
    {"code": "BRSSZ", "name": "Santos", "port_type": "ocean", "country": "Brazil", "city": "Santos", "lat": -23.9609, "lon": -46.3337},
    {"code": "CNSHA", "name": "Shanghai", "port_type": "ocean", "country": "China", "city": "Shanghai", "lat": 31.2304, "lon": 121.4737},
    {"code": "CNGUZ", "name": "Guangzhou/Nansha", "port_type": "ocean", "country": "China", "city": "Guangzhou", "lat": 22.7531, "lon": 113.6087},
    {"code": "INNSA", "name": "Nhava Sheva", "port_type": "ocean", "country": "India", "city": "Mumbai", "lat": 18.9491, "lon": 72.9426},
    {"code": "SGSIN", "name": "Singapore", "port_type": "ocean", "country": "Singapore", "city": "Singapore", "lat": 1.2650, "lon": 103.8200},
    {"code": "NLRTM", "name": "Rotterdam", "port_type": "ocean", "country": "Netherlands", "city": "Rotterdam", "lat": 51.9489, "lon": 4.1431},
    {"code": "DEHAM", "name": "Hamburg", "port_type": "ocean", "country": "Germany", "city": "Hamburg", "lat": 53.5461, "lon": 9.9660},
    {"code": "GBFXT", "name": "Felixstowe", "port_type": "ocean", "country": "UK", "city": "Felixstowe", "lat": 51.9613, "lon": 1.3280},
    {"code": "TRIST", "name": "Istanbul", "port_type": "ocean", "country": "Turkey", "city": "Istanbul", "lat": 41.0020, "lon": 28.9870},
    {"code": "AEDXB", "name": "Jebel Ali", "port_type": "ocean", "country": "UAE", "city": "Dubai", "lat": 25.0055, "lon": 55.0572},
    {"code": "JPYOK", "name": "Yokohama", "port_type": "ocean", "country": "Japan", "city": "Yokohama", "lat": 35.4521, "lon": 139.6381},
    {"code": "AUSYD", "name": "Sydney", "port_type": "ocean", "country": "Australia", "city": "Sydney", "lat": -33.8675, "lon": 151.2004},
    {"code": "MXVER", "name": "Veracruz", "port_type": "ocean", "country": "Mexico", "city": "Veracruz", "lat": 19.1738, "lon": -96.1342},
    {"code": "ARBUE", "name": "Buenos Aires", "port_type": "ocean", "country": "Argentina", "city": "Buenos Aires", "lat": -34.5771, "lon": -58.3728},
    {"code": "ZADUR", "name": "Durban", "port_type": "ocean", "country": "South Africa", "city": "Durban", "lat": -29.8679, "lon": 31.0496},
    # Air hubs
    {"code": "USORD", "name": "Chicago O'Hare", "port_type": "air", "country": "USA", "city": "Chicago", "lat": 41.9742, "lon": -87.9073},
    {"code": "CNSHS", "name": "Shanghai Pudong", "port_type": "air", "country": "China", "city": "Shanghai", "lat": 31.1434, "lon": 121.8052},
]

# Carriers
CARRIERS = [
    # Trucking
    {"code": "CAR-TRUK-001", "name": "Swift Transport", "carrier_type": "trucking", "scac": "SWFT", "country": "USA", "sustainability": "B", "otd": 0.94},
    {"code": "CAR-TRUK-002", "name": "JB Hunt", "carrier_type": "trucking", "scac": "JBHU", "country": "USA", "sustainability": "B", "otd": 0.95},
    {"code": "CAR-TRUK-003", "name": "Schneider", "carrier_type": "trucking", "scac": "SNLU", "country": "USA", "sustainability": "A", "otd": 0.96},
    {"code": "CAR-TRUK-004", "name": "Werner", "carrier_type": "trucking", "scac": "WERN", "country": "USA", "sustainability": "B", "otd": 0.93},
    # LTL
    {"code": "CAR-LTL-001", "name": "Old Dominion", "carrier_type": "ltl", "scac": "ODFL", "country": "USA", "sustainability": "B", "otd": 0.97},
    {"code": "CAR-LTL-002", "name": "Estes Express", "carrier_type": "ltl", "scac": "EXLA", "country": "USA", "sustainability": "C", "otd": 0.92},
    # Rail
    {"code": "CAR-RAIL-001", "name": "Union Pacific", "carrier_type": "rail", "scac": "UP", "country": "USA", "sustainability": "A", "otd": 0.88},
    {"code": "CAR-RAIL-002", "name": "BNSF Railway", "carrier_type": "rail", "scac": "BNSF", "country": "USA", "sustainability": "A", "otd": 0.90},
    {"code": "CAR-RAIL-003", "name": "CSX", "carrier_type": "rail", "scac": "CSXT", "country": "USA", "sustainability": "A", "otd": 0.87},
    # Ocean
    {"code": "CAR-OCEAN-001", "name": "Maersk Line", "carrier_type": "ocean", "scac": "MAEU", "country": "Denmark", "sustainability": "A", "otd": 0.85},
    {"code": "CAR-OCEAN-002", "name": "MSC", "carrier_type": "ocean", "scac": "MSCU", "country": "Switzerland", "sustainability": "B", "otd": 0.83},
    {"code": "CAR-OCEAN-003", "name": "CMA CGM", "carrier_type": "ocean", "scac": "CMDU", "country": "France", "sustainability": "B", "otd": 0.84},
    {"code": "CAR-OCEAN-004", "name": "Hapag-Lloyd", "carrier_type": "ocean", "scac": "HLCU", "country": "Germany", "sustainability": "A", "otd": 0.86},
    {"code": "CAR-OCEAN-005", "name": "COSCO", "carrier_type": "ocean", "scac": "COSU", "country": "China", "sustainability": "C", "otd": 0.82},
    # Parcel
    {"code": "CAR-PARC-001", "name": "FedEx", "carrier_type": "parcel", "scac": "FXFE", "country": "USA", "sustainability": "A", "otd": 0.97},
    {"code": "CAR-PARC-002", "name": "UPS", "carrier_type": "parcel", "scac": "UPSS", "country": "USA", "sustainability": "A", "otd": 0.96},
    {"code": "CAR-PARC-003", "name": "DHL", "carrier_type": "parcel", "scac": "DHLX", "country": "Germany", "sustainability": "A", "otd": 0.95},
    # 3PL
    {"code": "CAR-3PL-001", "name": "XPO Logistics", "carrier_type": "3pl", "scac": "XPOL", "country": "USA", "sustainability": "B", "otd": 0.93},
    {"code": "CAR-3PL-002", "name": "DHL Supply Chain", "carrier_type": "3pl", "scac": "DHSC", "country": "Germany", "sustainability": "A", "otd": 0.94},
    {"code": "CAR-3PL-003", "name": "Kuehne+Nagel", "carrier_type": "3pl", "scac": "KNIG", "country": "Switzerland", "sustainability": "A", "otd": 0.95},
]

# FMCG Ingredients (50 typical ingredients)
INGREDIENTS = [
    # Problem ingredients (named entities)
    {"code": "ING-PALM-001", "name": "Palm Oil", "category": "surfactant", "cas": "8002-75-3", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    {"code": "ING-SORB-001", "name": "Sorbitol", "category": "humectant", "cas": "50-70-4", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-PEPP-001", "name": "Peppermint Oil", "category": "flavor", "cas": "8006-90-4", "storage": "refrigerated", "hazmat": None, "shelf_days": 365},
    # Common surfactants
    {"code": "ING-SLES-001", "name": "Sodium Laureth Sulfate", "category": "surfactant", "cas": "9004-82-4", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-CAPB-001", "name": "Cocamidopropyl Betaine", "category": "surfactant", "cas": "61789-40-0", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-LABS-001", "name": "Linear Alkylbenzene Sulfonate", "category": "surfactant", "cas": "68411-30-3", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    # Abrasives (toothpaste)
    {"code": "ING-SICA-001", "name": "Silica (Abrasive)", "category": "abrasive", "cas": "7631-86-9", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-CALC-001", "name": "Calcium Carbonate", "category": "abrasive", "cas": "471-34-1", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-DICA-001", "name": "Dicalcium Phosphate", "category": "abrasive", "cas": "7757-93-9", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    # Humectants
    {"code": "ING-GLYC-001", "name": "Glycerin", "category": "humectant", "cas": "56-81-5", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-PROP-001", "name": "Propylene Glycol", "category": "humectant", "cas": "57-55-6", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-XYLI-001", "name": "Xylitol", "category": "humectant", "cas": "87-99-0", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    # Flavors and fragrances
    {"code": "ING-SPEA-001", "name": "Spearmint Oil", "category": "flavor", "cas": "8008-79-5", "storage": "refrigerated", "hazmat": None, "shelf_days": 365},
    {"code": "ING-MENT-001", "name": "Menthol", "category": "flavor", "cas": "89-78-1", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-CINN-001", "name": "Cinnamon Flavor", "category": "flavor", "cas": "104-55-2", "storage": "ambient", "hazmat": "flammable", "shelf_days": 365},
    {"code": "ING-LEMO-001", "name": "Lemon Fragrance", "category": "fragrance", "cas": "8008-56-8", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    {"code": "ING-LAVN-001", "name": "Lavender Oil", "category": "fragrance", "cas": "8000-28-0", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    {"code": "ING-VANI-001", "name": "Vanilla Fragrance", "category": "fragrance", "cas": "121-33-5", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    # Active ingredients (toothpaste)
    {"code": "ING-FLUO-001", "name": "Sodium Fluoride", "category": "active", "cas": "7681-49-4", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-STRN-001", "name": "Strontium Chloride", "category": "active", "cas": "10476-85-4", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-TRIC-001", "name": "Triclosan", "category": "active", "cas": "3380-34-5", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    # Thickeners and binders
    {"code": "ING-CMC-001", "name": "Carboxymethyl Cellulose", "category": "thickener", "cas": "9004-32-4", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-XANT-001", "name": "Xanthan Gum", "category": "thickener", "cas": "11138-66-2", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-CARB-001", "name": "Carbomer", "category": "thickener", "cas": "9003-01-4", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    # Preservatives
    {"code": "ING-SODB-001", "name": "Sodium Benzoate", "category": "preservative", "cas": "532-32-1", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-METH-001", "name": "Methylparaben", "category": "preservative", "cas": "99-76-3", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-PHON-001", "name": "Phenoxyethanol", "category": "preservative", "cas": "122-99-6", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    # Colorants
    {"code": "ING-TIO2-001", "name": "Titanium Dioxide", "category": "colorant", "cas": "13463-67-7", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-FDC1-001", "name": "FD&C Blue #1", "category": "colorant", "cas": "3844-45-9", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-FDC5-001", "name": "FD&C Yellow #5", "category": "colorant", "cas": "1934-21-0", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    # pH adjusters
    {"code": "ING-CITR-001", "name": "Citric Acid", "category": "ph_adjuster", "cas": "77-92-9", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-SODH-001", "name": "Sodium Hydroxide", "category": "ph_adjuster", "cas": "1310-73-2", "storage": "ambient", "hazmat": "corrosive", "shelf_days": 1095},
    # Solvents
    {"code": "ING-WATR-001", "name": "Purified Water", "category": "solvent", "cas": "7732-18-5", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    {"code": "ING-ETHA-001", "name": "Ethanol", "category": "solvent", "cas": "64-17-5", "storage": "ambient", "hazmat": "flammable", "shelf_days": 730},
    {"code": "ING-ISOP-001", "name": "Isopropyl Alcohol", "category": "solvent", "cas": "67-63-0", "storage": "ambient", "hazmat": "flammable", "shelf_days": 730},
    # Emulsifiers
    {"code": "ING-STEA-001", "name": "Stearic Acid", "category": "emulsifier", "cas": "57-11-4", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-CETE-001", "name": "Cetyl Alcohol", "category": "emulsifier", "cas": "36653-82-4", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    {"code": "ING-POLY-001", "name": "Polysorbate 20", "category": "emulsifier", "cas": "9005-64-5", "storage": "ambient", "hazmat": None, "shelf_days": 730},
    # Moisturizers
    {"code": "ING-SHEA-001", "name": "Shea Butter", "category": "moisturizer", "cas": "91080-23-8", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    {"code": "ING-ALOE-001", "name": "Aloe Vera Extract", "category": "moisturizer", "cas": "8001-97-6", "storage": "refrigerated", "hazmat": None, "shelf_days": 365},
    {"code": "ING-COCO-001", "name": "Coconut Oil", "category": "moisturizer", "cas": "8001-31-8", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    {"code": "ING-JOJO-001", "name": "Jojoba Oil", "category": "moisturizer", "cas": "61789-91-1", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    # Specialty
    {"code": "ING-VITA-001", "name": "Vitamin E (Tocopherol)", "category": "antioxidant", "cas": "59-02-9", "storage": "refrigerated", "hazmat": None, "shelf_days": 365},
    {"code": "ING-VITC-001", "name": "Vitamin C (Ascorbic Acid)", "category": "antioxidant", "cas": "50-81-7", "storage": "refrigerated", "hazmat": None, "shelf_days": 365},
    {"code": "ING-TEA-001", "name": "Tea Tree Oil", "category": "antibacterial", "cas": "68647-73-4", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    {"code": "ING-EUCA-001", "name": "Eucalyptus Oil", "category": "antibacterial", "cas": "8000-48-4", "storage": "ambient", "hazmat": None, "shelf_days": 365},
    {"code": "ING-ZINC-001", "name": "Zinc Oxide", "category": "active", "cas": "1314-13-2", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-SALT-001", "name": "Sodium Chloride", "category": "viscosity_modifier", "cas": "7647-14-5", "storage": "ambient", "hazmat": None, "shelf_days": 1095},
    {"code": "ING-ENZY-001", "name": "Enzyme Blend", "category": "active", "cas": None, "storage": "refrigerated", "hazmat": None, "shelf_days": 180},
]

# Packaging types for FMCG
PACKAGING_TYPES = [
    # Toothpaste tubes
    {"code": "PKG-TUBE-50", "name": "50ml Tube", "container": "tube", "size": 50, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 24},
    {"code": "PKG-TUBE-100", "name": "100ml Tube", "container": "tube", "size": 100, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 12},
    {"code": "PKG-TUBE-150", "name": "150ml Tube", "container": "tube", "size": 150, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 12},
    {"code": "PKG-TUBE-200", "name": "200ml Tube", "container": "tube", "size": 200, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 6},
    # Dish soap bottles
    {"code": "PKG-BOTL-250", "name": "250ml Bottle", "container": "bottle", "size": 250, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 24},
    {"code": "PKG-BOTL-500", "name": "500ml Bottle", "container": "bottle", "size": 500, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 12},
    {"code": "PKG-BOTL-750", "name": "750ml Bottle", "container": "bottle", "size": 750, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 12},
    {"code": "PKG-BOTL-1L", "name": "1L Bottle", "container": "bottle", "size": 1000, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 6},
    # Body wash bottles
    {"code": "PKG-PUMP-250", "name": "250ml Pump Bottle", "container": "bottle", "size": 250, "unit": "ml", "material": "plastic", "recyclable": False, "per_case": 24},
    {"code": "PKG-PUMP-500", "name": "500ml Pump Bottle", "container": "bottle", "size": 500, "unit": "ml", "material": "plastic", "recyclable": False, "per_case": 12},
    {"code": "PKG-PUMP-750", "name": "750ml Pump Bottle", "container": "bottle", "size": 750, "unit": "ml", "material": "plastic", "recyclable": False, "per_case": 8},
    # Travel/trial sizes
    {"code": "PKG-SACHET-10", "name": "10ml Sachet", "container": "pouch", "size": 10, "unit": "ml", "material": "plastic", "recyclable": False, "per_case": 100},
    {"code": "PKG-TRIAL-30", "name": "30ml Trial", "container": "tube", "size": 30, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 48},
    # Refills
    {"code": "PKG-REFILL-1L", "name": "1L Refill Pouch", "container": "pouch", "size": 1000, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 12},
    {"code": "PKG-REFILL-2L", "name": "2L Refill Pouch", "container": "pouch", "size": 2000, "unit": "ml", "material": "plastic", "recyclable": True, "per_case": 6},
    # Premium
    {"code": "PKG-GLASS-200", "name": "200ml Glass Bottle", "container": "bottle", "size": 200, "unit": "ml", "material": "glass", "recyclable": True, "per_case": 12},
]

# KPI Thresholds (Desmet Triangle)
KPI_THRESHOLDS = [
    # Service KPIs
    {"code": "KPI-OTIF", "name": "On-Time In-Full", "category": "service", "desmet": "service", "unit": "percent", "direction": "higher", "target": 97.0, "warning": 95.0, "critical": 93.0},
    {"code": "KPI-CFR", "name": "Case Fill Rate", "category": "service", "desmet": "service", "unit": "percent", "direction": "higher", "target": 98.5, "warning": 97.0, "critical": 95.0},
    {"code": "KPI-OSA", "name": "On-Shelf Availability", "category": "service", "desmet": "service", "unit": "percent", "direction": "higher", "target": 95.0, "warning": 93.0, "critical": 90.0},
    {"code": "KPI-POF", "name": "Perfect Order Fulfillment", "category": "service", "desmet": "service", "unit": "percent", "direction": "higher", "target": 92.0, "warning": 88.0, "critical": 85.0},
    {"code": "KPI-FCST", "name": "Forecast Accuracy (MAPE)", "category": "service", "desmet": "service", "unit": "percent", "direction": "lower", "target": 25.0, "warning": 30.0, "critical": 35.0},
    # Cost KPIs
    {"code": "KPI-COGS", "name": "COGS % of Revenue", "category": "cost", "desmet": "cost", "unit": "percent", "direction": "lower", "target": 45.0, "warning": 48.0, "critical": 52.0},
    {"code": "KPI-LCPC", "name": "Landed Cost per Case", "category": "cost", "desmet": "cost", "unit": "USD", "direction": "lower", "target": 8.50, "warning": 9.50, "critical": 11.00},
    {"code": "KPI-FRT", "name": "Freight % of Revenue", "category": "cost", "desmet": "cost", "unit": "percent", "direction": "lower", "target": 6.0, "warning": 7.5, "critical": 9.0},
    {"code": "KPI-WHS", "name": "Warehousing Cost per Case", "category": "cost", "desmet": "cost", "unit": "USD", "direction": "lower", "target": 0.85, "warning": 1.00, "critical": 1.25},
    {"code": "KPI-SCRAP", "name": "Scrap Rate", "category": "cost", "desmet": "cost", "unit": "percent", "direction": "lower", "target": 1.0, "warning": 2.0, "critical": 3.0},
    # Cash KPIs
    {"code": "KPI-INV", "name": "Inventory Turns", "category": "cash", "desmet": "cash", "unit": "turns", "direction": "higher", "target": 10.0, "warning": 8.0, "critical": 6.0},
    {"code": "KPI-DOS", "name": "Days of Supply", "category": "cash", "desmet": "cash", "unit": "days", "direction": "lower", "target": 35.0, "warning": 45.0, "critical": 60.0},
    {"code": "KPI-DSO", "name": "Days Sales Outstanding", "category": "cash", "desmet": "cash", "unit": "days", "direction": "lower", "target": 30.0, "warning": 40.0, "critical": 50.0},
    {"code": "KPI-OBSOL", "name": "Obsolete Inventory %", "category": "cash", "desmet": "cash", "unit": "percent", "direction": "lower", "target": 0.5, "warning": 1.0, "critical": 2.0},
    {"code": "KPI-CCC", "name": "Cash Conversion Cycle", "category": "cash", "desmet": "cash", "unit": "days", "direction": "lower", "target": 45.0, "warning": 60.0, "critical": 75.0},
    # Quality KPIs
    {"code": "KPI-QUAL", "name": "First Pass Quality", "category": "quality", "desmet": None, "unit": "percent", "direction": "higher", "target": 99.0, "warning": 98.0, "critical": 96.0},
    {"code": "KPI-RET", "name": "Customer Return Rate", "category": "quality", "desmet": None, "unit": "percent", "direction": "lower", "target": 0.5, "warning": 1.0, "critical": 2.0},
    {"code": "KPI-COMPL", "name": "Customer Complaints per Million", "category": "quality", "desmet": None, "unit": "count", "direction": "lower", "target": 5.0, "warning": 10.0, "critical": 20.0},
    # Sustainability KPIs
    {"code": "KPI-CO2", "name": "CO2 per Case (Scope 3)", "category": "sustainability", "desmet": None, "unit": "kg_co2", "direction": "lower", "target": 0.25, "warning": 0.35, "critical": 0.50},
    {"code": "KPI-RECYCLE", "name": "Packaging Recyclability", "category": "sustainability", "desmet": None, "unit": "percent", "direction": "higher", "target": 80.0, "warning": 65.0, "critical": 50.0},
]

# Business Rules
BUSINESS_RULES = [
    {"code": "BR-ALLOC-001", "name": "Strategic Account Priority", "category": "allocation", "rule_type": "priority", "priority": 10, "condition": "account.is_strategic = true", "action": "allocate_first"},
    {"code": "BR-ALLOC-002", "name": "FIFO Inventory Allocation", "category": "allocation", "rule_type": "constraint", "priority": 20, "condition": "inventory.batch_date", "action": "allocate_oldest_first"},
    {"code": "BR-ALLOC-003", "name": "Promotional Demand Reserve", "category": "allocation", "rule_type": "constraint", "priority": 15, "condition": "promotion.is_active = true", "action": "reserve_promo_qty"},
    {"code": "BR-FULFILL-001", "name": "Minimum Order Quantity", "category": "fulfillment", "rule_type": "threshold", "priority": 50, "condition": "order.qty < 10", "action": "reject_order"},
    {"code": "BR-FULFILL-002", "name": "Ship Complete Only", "category": "fulfillment", "rule_type": "constraint", "priority": 30, "condition": "order.ship_complete = true", "action": "hold_partial"},
    {"code": "BR-FULFILL-003", "name": "Direct Ship Threshold", "category": "fulfillment", "rule_type": "threshold", "priority": 40, "condition": "order.qty > 1000", "action": "direct_ship_eligible"},
    {"code": "BR-INV-001", "name": "Safety Stock Days", "category": "inventory", "rule_type": "calculation", "priority": 25, "condition": "always", "action": "ss_days = 14"},
    {"code": "BR-INV-002", "name": "Shelf Life Minimum", "category": "inventory", "rule_type": "threshold", "priority": 30, "condition": "batch.remaining_shelf_life < 90", "action": "flag_short_dated"},
    {"code": "BR-INV-003", "name": "Auto Replenishment Trigger", "category": "inventory", "rule_type": "threshold", "priority": 35, "condition": "inventory.qty < reorder_point", "action": "create_transfer_order"},
    {"code": "BR-PROMO-001", "name": "Promo Lift Application", "category": "promotion", "rule_type": "calculation", "priority": 20, "condition": "promotion.is_active = true", "action": "apply_lift_multiplier"},
    {"code": "BR-PROMO-002", "name": "Promo Hangover Adjustment", "category": "promotion", "rule_type": "calculation", "priority": 21, "condition": "promotion.ended_within_7_days", "action": "apply_hangover_multiplier"},
    {"code": "BR-CREDIT-001", "name": "Credit Hold Check", "category": "credit", "rule_type": "constraint", "priority": 5, "condition": "account.credit_balance > credit_limit", "action": "hold_order"},
    {"code": "BR-CREDIT-002", "name": "Payment Terms Validation", "category": "credit", "rule_type": "constraint", "priority": 10, "condition": "account.past_due > 60", "action": "require_prepayment"},
    {"code": "BR-PRICE-001", "name": "Trade Discount Application", "category": "pricing", "rule_type": "calculation", "priority": 15, "condition": "account.has_trade_agreement", "action": "apply_discount"},
    {"code": "BR-PRICE-002", "name": "Volume Tier Pricing", "category": "pricing", "rule_type": "calculation", "priority": 20, "condition": "order.qty >= volume_break", "action": "apply_tier_price"},
]


# =============================================================================
# Main Generator Orchestration
# =============================================================================

# Target row counts by level (from jolly-sauteeing-fern.md)
TARGET_ROW_COUNTS = {
    0: 1_200,       # divisions, channels, products, packaging_types, ports, carriers, etc.
    1: 500,         # suppliers, plants, production_lines, carrier_contracts, route_segments
    2: 6_000,       # supplier_ingredients, certifications, formulas, formula_ingredients, etc.
    3: 10_000,      # retail_accounts, retail_locations, distribution_centers
    4: 20_000,      # skus, sku_costs, sku_substitutes, promotions, etc.
    5: 80_000,      # purchase_orders, goods_receipts, work_orders, etc.
    6: 550_000,     # purchase_order_lines, goods_receipt_lines, batches, etc.
    7: 700_000,     # batch_ingredients, inventory
    8: 2_500_000,   # pos_sales, demand_forecasts, orders, etc. (LARGEST)
    9: 1_000_000,   # order_lines, order_allocations, supply_plans, etc.
    10: 730_000,    # pick_wave_orders, shipments, shipment_legs
    11: 540_000,    # shipment_lines
    12: 140_000,    # rma_authorizations, returns, return_lines
    13: 100_000,    # disposition_logs
    14: 1_000_000,  # kpi_actuals, osa_metrics, risk_events, audit_log
}


class FMCGDataGenerator:
    """
    Orchestrates generation of all FMCG data using level-based dependencies.

    Generation follows 15 levels (0-14) based on FK dependencies.
    See jolly-sauteeing-fern.md for level definitions.
    """

    def __init__(self, seed: int = RANDOM_SEED):
        """
        Initialize generator with reproducible random state.

        Args:
            seed: Random seed for reproducibility
        """
        # Initialize random state for reproducibility
        self.seed = seed
        random.seed(seed)
        self.rng = np.random.default_rng(seed)
        self.fake = Faker()
        Faker.seed(seed)

        # Named entities for deterministic testing
        self.named_entities = create_named_entities()

        # Current generation year
        self.base_year = 2024

        # Track which levels have been generated
        self.generated_levels: set[int] = set()

        # =================================================================
        # ID Tracking for Referential Integrity
        # =================================================================
        # These dicts map entity codes/names to their database IDs
        # Used to maintain FK relationships across tables

        # Level 0: Reference data
        self.division_ids: dict[str, int] = {}      # code -> id
        self.channel_ids: dict[str, int] = {}       # code -> id
        self.product_ids: dict[str, int] = {}       # code -> id
        self.packaging_type_ids: dict[str, int] = {}  # code -> id
        self.port_ids: dict[str, int] = {}          # code -> id
        self.carrier_ids: dict[str, int] = {}       # code -> id
        self.emission_factor_ids: dict[str, int] = {}  # mode+fuel -> id
        self.kpi_threshold_ids: dict[str, int] = {}  # code -> id
        self.business_rule_ids: dict[str, int] = {}  # code -> id
        self.ingredient_ids: dict[str, int] = {}    # code -> id

        # Level 1: Master data
        self.supplier_ids: dict[str, int] = {}      # code -> id
        self.plant_ids: dict[str, int] = {}         # code -> id
        self.production_line_ids: dict[str, int] = {}  # code -> id
        self.carrier_contract_ids: dict[str, int] = {}  # contract_number -> id
        self.route_segment_ids: dict[str, int] = {}  # code -> id

        # Level 2: Relationships and formulas
        self.supplier_ingredient_ids: dict[tuple, int] = {}  # (supplier_id, ingredient_id) -> id
        self.certification_ids: dict[str, int] = {}  # cert_code -> id
        self.formula_ids: dict[str, int] = {}       # code -> id
        self.carrier_rate_ids: dict[str, int] = {}  # code -> id
        self.route_ids: dict[str, int] = {}         # code -> id

        # Level 3: Locations
        self.retail_account_ids: dict[str, int] = {}  # code -> id
        self.retail_location_ids: dict[str, int] = {}  # code -> id
        self.dc_ids: dict[str, int] = {}            # code -> id

        # Level 4: SKUs and promotions
        self.sku_ids: dict[str, int] = {}           # code -> id
        self.promotion_ids: dict[str, int] = {}     # code -> id

        # Level 5: Orders/POs
        self.purchase_order_ids: dict[str, int] = {}  # po_number -> id
        self.goods_receipt_ids: dict[str, int] = {}  # gr_number -> id
        self.work_order_ids: dict[str, int] = {}    # wo_number -> id

        # Level 6-7: Manufacturing
        self.batch_ids: dict[str, int] = {}         # batch_number -> id
        self.inventory_ids: dict[tuple, int] = {}   # (location_type, location_id, sku_id) -> id

        # Level 8-9: Demand and orders
        self.order_ids: dict[str, int] = {}         # order_number -> id
        self.demand_forecast_ids: dict[tuple, int] = {}  # (sku_id, location_id, period) -> id
        self.pick_wave_ids: dict[str, int] = {}     # wave_number -> id

        # Level 10-11: Shipments
        self.shipment_ids: dict[str, int] = {}      # shipment_number -> id

        # Level 12-13: Returns
        self.rma_ids: dict[str, int] = {}           # rma_number -> id
        self.return_ids: dict[str, int] = {}        # return_number -> id

        # =================================================================
        # Generated Data Storage (in-memory for validation)
        # =================================================================
        # Each key is a table name, value is list of row dicts

        self.data: dict[str, list[dict]] = {}

        # Initialize all table lists
        self._init_data_tables()

        # =================================================================
        # Phase 5: Performance Module Integration
        # =================================================================

        # StaticDataPool: Pre-generated Faker data for O(1) vectorized sampling
        self.pool = StaticDataPool(seed=seed)

        # PooledFaker: Batch Faker sampling wrapper
        self.pooled_faker = PooledFaker(seed=seed)

        # DependencyTracker: FK dependency graph for safe table memory purging
        self.dep_tracker = DependencyTracker()

        # RealismMonitor: Online streaming validation with O(1) space algorithms
        self.realism_monitor = RealismMonitor(manifest_path=BENCHMARK_MANIFEST_PATH)

        # LookupCache: Pre-built indices for FK lookups (built lazily per level)
        self.lookup_cache: LookupCache | None = None

        # StochasticMode: Normal (Poisson) vs Disrupted (Gamma) for chaos injection
        self.stochastic_mode = StochasticMode.NORMAL

        # Performance tracking
        self._level_times: dict[int, float] = {}
        self._level_rows: dict[int, int] = {}

    def _init_data_tables(self) -> None:
        """Initialize empty lists for all 67 tables."""
        tables = [
            # Level 0
            "divisions", "channels", "products", "packaging_types", "ports",
            "carriers", "emission_factors", "kpi_thresholds", "business_rules",
            "ingredients",
            # Level 1
            "suppliers", "plants", "production_lines", "carrier_contracts",
            "route_segments",
            # Level 2
            "supplier_ingredients", "certifications", "formulas",
            "formula_ingredients", "carrier_rates", "routes",
            "route_segment_assignments",
            # Level 3
            "retail_accounts", "retail_locations", "distribution_centers",
            # Level 4
            "skus", "sku_costs", "sku_substitutes", "promotions",
            "promotion_skus", "promotion_accounts",
            # Level 5
            "purchase_orders", "goods_receipts", "work_orders",
            "supplier_esg_scores", "sustainability_targets",
            "modal_shift_opportunities",
            # Level 6
            "purchase_order_lines", "goods_receipt_lines",
            "work_order_materials", "batches", "batch_cost_ledger",
            # Level 7
            "batch_ingredients", "inventory",
            # Level 8
            "pos_sales", "demand_forecasts", "forecast_accuracy",
            "consensus_adjustments", "orders", "replenishment_params",
            "demand_allocation", "capacity_plans",
            # Level 9
            "order_lines", "order_allocations", "supply_plans",
            "plan_exceptions", "pick_waves",
            # Level 10
            "pick_wave_orders", "shipments", "shipment_legs",
            # Level 11
            "shipment_lines",
            # Level 12
            "rma_authorizations", "returns", "return_lines",
            # Level 13
            "disposition_logs",
            # Level 14
            "kpi_actuals", "osa_metrics", "risk_events", "audit_log",
        ]
        for table in tables:
            self.data[table] = []

    def _build_lookup_cache(self, level: int) -> None:
        """
        Build lookup indices for FK relationships needed at a given level.

        This is called at the start of each level that needs FK lookups.
        Indices are built lazily from already-generated data.

        Args:
            level: The generation level about to start
        """
        if level == 6:
            # Level 6 needs: PO lines by PO ID, formula ingredients by formula ID
            self.lookup_cache = LookupCache(self.data)
            # These methods exist on LookupCache:
            # - po_lines_by_po_id
            # - formula_ings_by_formula_id

        elif level == 8:
            # Level 8 needs: retail locations by account ID
            # Rebuild cache with latest data
            self.lookup_cache = LookupCache(self.data)

        elif level == 9:
            # Level 9 needs: order lines by order ID
            self.lookup_cache = LookupCache(self.data)

    def _report_level_stats(self, level: int, elapsed: float) -> None:
        """Report statistics for a completed level."""
        level_row_count = 0
        level_tables = self._get_level_tables(level)
        for table in level_tables:
            level_row_count += len(self.data.get(table, []))

        self._level_times[level] = elapsed
        self._level_rows[level] = level_row_count

        rows_per_sec = level_row_count / elapsed if elapsed > 0 else 0
        print(f"    ⏱  {elapsed:.2f}s ({rows_per_sec:,.0f} rows/sec)")

    def _get_level_tables(self, level: int) -> list[str]:
        """Get the list of tables for a given level."""
        level_tables = {
            0: ["divisions", "channels", "products", "packaging_types", "ports",
                "carriers", "emission_factors", "kpi_thresholds", "business_rules",
                "ingredients"],
            1: ["suppliers", "plants", "production_lines", "carrier_contracts",
                "route_segments"],
            2: ["supplier_ingredients", "certifications", "formulas",
                "formula_ingredients", "carrier_rates", "routes",
                "route_segment_assignments"],
            3: ["retail_accounts", "retail_locations", "distribution_centers"],
            4: ["skus", "sku_costs", "sku_substitutes", "promotions",
                "promotion_skus", "promotion_accounts"],
            5: ["purchase_orders", "goods_receipts", "work_orders",
                "supplier_esg_scores", "sustainability_targets",
                "modal_shift_opportunities"],
            6: ["purchase_order_lines", "goods_receipt_lines",
                "work_order_materials", "batches", "batch_cost_ledger"],
            7: ["batch_ingredients", "inventory"],
            8: ["pos_sales", "demand_forecasts", "forecast_accuracy",
                "consensus_adjustments", "orders", "replenishment_params",
                "demand_allocation", "capacity_plans"],
            9: ["order_lines", "order_allocations", "supply_plans",
                "plan_exceptions", "pick_waves"],
            10: ["pick_wave_orders", "shipments", "shipment_legs"],
            11: ["shipment_lines"],
            12: ["rma_authorizations", "returns", "return_lines"],
            13: ["disposition_logs"],
            14: ["kpi_actuals", "osa_metrics", "risk_events", "audit_log"],
        }
        return level_tables.get(level, [])

    # =========================================================================
    # Level Generators (Stubs - to be implemented in Steps 2-7)
    # =========================================================================

    def _generate_level_0(self) -> None:
        """
        Level 0: Reference/Master data with no FK dependencies.

        Tables: divisions, channels, products, packaging_types, ports,
                carriers, emission_factors, kpi_thresholds, business_rules,
                ingredients
        """
        print("  Level 0: Reference data (divisions, channels, products...)")
        now = datetime.now()

        # --- DIVISIONS ---
        for i, div in enumerate(DIVISIONS, 1):
            self.division_ids[div["code"]] = i
            self.data["divisions"].append({
                "id": i,
                "division_code": div["code"],
                "name": div["name"],
                "headquarters_city": div["hq_city"],
                "headquarters_country": div["hq_country"],
                "president": div["president"],
                "revenue_target": div["revenue_target"],
                "currency": "USD",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

        # --- CHANNELS ---
        for i, ch in enumerate(CHANNELS, 1):
            self.channel_ids[ch["code"]] = i
            self.data["channels"].append({
                "id": i,
                "channel_code": ch["code"],
                "name": ch["name"],
                "channel_type": ch["channel_type"],
                "volume_percent": ch["volume_pct"],
                "margin_percent": ch["margin_pct"],
                "payment_terms_days": ch["payment_days"],
                "description": f"{ch['name']} sales channel",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

        # --- PRODUCTS ---
        for i, prod in enumerate(PRODUCTS, 1):
            self.product_ids[prod["code"]] = i
            self.data["products"].append({
                "id": i,
                "product_code": prod["code"],
                "name": prod["name"],
                "brand": prod["brand"],
                "category": prod["category"],
                "subcategory": prod["subcategory"],
                "description": f"{prod['brand']} - Premium {prod['subcategory'].replace('_', ' ')}",
                "launch_date": date.fromisoformat(prod["launch_date"]),
                "discontinue_date": None,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

        # --- PACKAGING TYPES ---
        for i, pkg in enumerate(PACKAGING_TYPES, 1):
            self.packaging_type_ids[pkg["code"]] = i
            case_weight = (pkg["size"] * pkg["per_case"] / 1000) * 1.1  # ~10% packaging weight
            self.data["packaging_types"].append({
                "id": i,
                "packaging_code": pkg["code"],
                "name": pkg["name"],
                "container_type": pkg["container"],
                "size_value": pkg["size"],
                "size_unit": pkg["unit"],
                "material": pkg["material"],
                "is_recyclable": pkg["recyclable"],
                "units_per_case": pkg["per_case"],
                "case_weight_kg": round(case_weight, 3),
                "case_dimensions_cm": "40x30x25",
                "created_at": now,
                "updated_at": now,
            })

        # --- PORTS ---
        for i, port in enumerate(PORTS, 1):
            self.port_ids[port["code"]] = i
            teu = random.randint(500_000, 20_000_000) if port["port_type"] == "ocean" else None
            self.data["ports"].append({
                "id": i,
                "port_code": port["code"],
                "name": port["name"],
                "port_type": port["port_type"],
                "country": port["country"],
                "city": port["city"],
                "latitude": port["lat"],
                "longitude": port["lon"],
                "timezone": self.fake.timezone(),
                "handling_capacity_teu": teu,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

        # --- CARRIERS ---
        for i, car in enumerate(CARRIERS, 1):
            self.carrier_ids[car["code"]] = i
            self.data["carriers"].append({
                "id": i,
                "carrier_code": car["code"],
                "name": car["name"],
                "carrier_type": car["carrier_type"],
                "scac_code": car["scac"],
                "headquarters_country": car["country"],
                "service_regions": None,  # Array type
                "sustainability_rating": car["sustainability"],
                "on_time_delivery_rate": car["otd"],
                "damage_rate": round(random.uniform(0.001, 0.02), 4),
                "is_preferred": car["otd"] >= 0.95,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

        # --- EMISSION FACTORS ---
        emission_id = 1
        modes = [
            ("truck", "diesel", 0.062, 0.0000894),
            ("truck", "electric", 0.020, 0.0000290),
            ("rail", "diesel", 0.022, 0.0000318),
            ("rail", "electric", 0.008, 0.0000116),
            ("ocean", "hfo", 0.008, 0.0000116),
            ("ocean", "lng", 0.006, 0.0000087),
            ("air", "jet_fuel", 0.500, 0.000725),
            ("last_mile", "diesel", 0.150, 0.000217),
            ("last_mile", "electric", 0.050, 0.0000725),
            ("intermodal", "diesel", 0.035, 0.0000507),
        ]
        for mode, fuel, co2_km, co2_ton_km in modes:
            self.emission_factor_ids[f"{mode}_{fuel}"] = emission_id
            self.data["emission_factors"].append({
                "id": emission_id,
                "transport_mode": mode,
                "fuel_type": fuel,
                "carrier_id": None,
                "co2_kg_per_km": co2_km,
                "co2_kg_per_ton_km": co2_ton_km,
                "source": "GLEC Framework 2.0",
                "effective_from": date(2024, 1, 1),
                "effective_to": None,
                "created_at": now,
            })
            emission_id += 1

        # --- KPI THRESHOLDS ---
        for i, kpi in enumerate(KPI_THRESHOLDS, 1):
            self.kpi_threshold_ids[kpi["code"]] = i
            self.data["kpi_thresholds"].append({
                "id": i,
                "kpi_code": kpi["code"],
                "kpi_name": kpi["name"],
                "kpi_category": kpi["category"],
                "desmet_dimension": kpi["desmet"],
                "unit": kpi["unit"],
                "direction": kpi["direction"],
                "target_value": kpi["target"],
                "warning_threshold": kpi["warning"],
                "critical_threshold": kpi["critical"],
                "industry_benchmark": kpi["target"] * 0.95,
                "scope": "global",
                "effective_from": date(2024, 1, 1),
                "effective_to": None,
                "created_at": now,
                "updated_at": now,
            })

        # --- BUSINESS RULES ---
        for i, rule in enumerate(BUSINESS_RULES, 1):
            self.business_rule_ids[rule["code"]] = i
            self.data["business_rules"].append({
                "id": i,
                "rule_code": rule["code"],
                "rule_name": rule["name"],
                "rule_category": rule["category"],
                "rule_type": rule["rule_type"],
                "scope": "global",
                "scope_id": None,
                "condition_expression": rule["condition"],
                "action_expression": rule["action"],
                "priority": rule["priority"],
                "is_active": True,
                "effective_from": date(2024, 1, 1),
                "effective_to": None,
                "created_by": "System",
                "approved_by": "Admin",
                "created_at": now,
                "updated_at": now,
            })

        # --- INGREDIENTS ---
        for i, ing in enumerate(INGREDIENTS, 1):
            self.ingredient_ids[ing["code"]] = i
            temp_min = 2 if ing["storage"] == "refrigerated" else 15
            temp_max = 8 if ing["storage"] == "refrigerated" else 30
            self.data["ingredients"].append({
                "id": i,
                "ingredient_code": ing["code"],
                "name": ing["name"],
                "cas_number": ing["cas"],
                "category": ing["category"],
                "purity_percent": round(random.uniform(95, 99.9), 2),
                "storage_temp_min_c": temp_min,
                "storage_temp_max_c": temp_max,
                "storage_conditions": ing["storage"],
                "shelf_life_days": ing["shelf_days"],
                "hazmat_class": ing["hazmat"],
                "unit_of_measure": "kg",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

        self.generated_levels.add(0)
        print(f"    Generated: {len(self.data['divisions'])} divisions, {len(self.data['channels'])} channels, "
              f"{len(self.data['products'])} products, {len(self.data['ingredients'])} ingredients")

    def _generate_level_1(self) -> None:
        """
        Level 1: Master data with Level 0 dependencies.

        Tables: suppliers, plants, production_lines, carrier_contracts,
                route_segments
        """
        print("  Level 1: Master data (suppliers, plants, production_lines...)")
        now = datetime.now()

        # --- SUPPLIERS (200: 40 T1, 80 T2, 80 T3) ---
        supplier_id = 1
        regions = ["NAM", "LATAM", "APAC", "EUR", "AFR-EUR"]
        countries_by_region = {
            "NAM": ["USA", "Canada", "Mexico"],
            "LATAM": ["Brazil", "Argentina", "Colombia", "Chile"],
            "APAC": ["China", "India", "Japan", "South Korea", "Thailand", "Malaysia"],
            "EUR": ["Germany", "France", "UK", "Poland", "Italy", "Spain"],
            "AFR-EUR": ["Turkey", "UAE", "South Africa", "Egypt", "Saudi Arabia"],
        }

        # Named entity: Single-source Palm Oil supplier
        self.supplier_ids["SUP-PALM-MY-001"] = supplier_id
        self.data["suppliers"].append({
            "id": supplier_id,
            "supplier_code": "SUP-PALM-MY-001",
            "name": "Malaysian Palm Plantations",
            "tier": 1,
            "country": "Malaysia",
            "city": "Kuala Lumpur",
            "region": "APAC",
            "contact_email": "supply@mpp.com.my",
            "contact_phone": "+60-3-1234-5678",
            "payment_terms_days": 60,
            "currency": "USD",
            "qualification_status": "qualified",
            "qualification_date": date(2020, 1, 15),
            "risk_score": 0.75,  # High risk - single source
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
        supplier_id += 1

        # Generate tier distribution: 39 more T1, 80 T2, 80 T3
        tier_counts = [(1, 39), (2, 80), (3, 80)]
        for tier, count in tier_counts:
            for _ in range(count):
                region = random.choice(regions)
                country = random.choice(countries_by_region[region])
                code = f"SUP-{tier}_{supplier_id:03d}"
                self.supplier_ids[code] = supplier_id
                self.data["suppliers"].append({
                    "id": supplier_id,
                    "supplier_code": code,
                    "name": self.fake.company(),
                    "tier": tier,
                    "country": country,
                    "city": self.fake.city(),
                    "region": region,
                    "contact_email": self.fake.email(),
                    "contact_phone": self.fake.phone_number()[:20],
                    "payment_terms_days": [30, 45, 60][tier - 1],
                    "currency": "USD",
                    "qualification_status": random.choices(
                        ["qualified", "probation", "pending"],
                        weights=[85, 10, 5]
                    )[0],
                    "qualification_date": self.fake.date_between(start_date="-3y", end_date="today"),
                    "risk_score": round(random.uniform(0.1, 0.6) + (tier - 1) * 0.15, 2),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                })
                supplier_id += 1

        # --- PLANTS ---
        for i, plt in enumerate(PLANTS, 1):
            div_id = self.division_ids[plt["division"]]
            self.plant_ids[plt["code"]] = i
            self.data["plants"].append({
                "id": i,
                "plant_code": plt["code"],
                "name": plt["name"],
                "division_id": div_id,
                "country": plt["country"],
                "city": plt["city"],
                "address": f"{random.randint(100, 9999)} Industrial Parkway",
                "latitude": plt["lat"],
                "longitude": plt["lon"],
                "timezone": self.fake.timezone(),
                "capacity_tons_per_day": plt["capacity_tons"],
                "operating_hours_per_day": 16,
                "operating_days_per_week": 6,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

        # --- PRODUCTION LINES (5 per plant = 35 total) ---
        line_id = 1
        line_types = ["mixing", "filling", "packaging", "labeling", "quality"]
        for plant_code, plant_id in self.plant_ids.items():
            for lt in line_types:
                code = f"LINE-{plant_code[-5:]}-{lt[:3].upper()}"
                self.production_line_ids[code] = line_id
                capacity = random.randint(500, 2000)
                self.data["production_lines"].append({
                    "id": line_id,
                    "line_code": code,
                    "name": f"{lt.title()} Line {line_id}",
                    "plant_id": plant_id,
                    "line_type": lt,
                    "product_family": None,  # Flexible
                    "capacity_units_per_hour": capacity,
                    "setup_time_minutes": random.randint(15, 45),
                    "changeover_time_minutes": random.randint(30, 90),
                    "oee_target": round(random.uniform(0.80, 0.90), 4),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                })
                line_id += 1

        # --- CARRIER CONTRACTS (~100) ---
        contract_id = 1
        contract_types = ["annual", "spot", "dedicated", "volume_commitment"]
        carrier_ids = list(self.carrier_ids.values())

        for _ in range(100):
            carrier_id = random.choice(carrier_ids)
            start = self.fake.date_between(start_date="-1y", end_date="+3m")
            end = start + timedelta(days=random.choice([90, 180, 365]))
            contract_num = f"CTR-{self.base_year}-{contract_id:04d}"
            self.carrier_contract_ids[contract_num] = contract_id
            self.data["carrier_contracts"].append({
                "id": contract_id,
                "contract_number": contract_num,
                "carrier_id": carrier_id,
                "contract_type": random.choice(contract_types),
                "effective_from": start,
                "effective_to": end,
                "min_volume_commitment": random.randint(1000, 50000) if random.random() > 0.3 else None,
                "volume_unit": "cases",
                "status": "active" if end > date.today() else "expired",
                "notes": None,
                "created_at": now,
                "updated_at": now,
            })
            contract_id += 1

        # --- ROUTE SEGMENTS (~200) ---
        segment_id = 1

        # Named entity: Seasonal Shanghai->LA lane
        self.route_segment_ids["LANE-SH-LA-001"] = segment_id
        sha_port_id = self.port_ids["CNSHA"]
        lax_port_id = self.port_ids["USLAX"]
        self.data["route_segments"].append({
            "id": segment_id,
            "segment_code": "LANE-SH-LA-001",
            "origin_type": "port",
            "origin_id": sha_port_id,
            "destination_type": "port",
            "destination_id": lax_port_id,
            "transport_mode": "ocean",
            "distance_km": 10500,
            "distance_miles": 6524,
            "transit_time_hours": 336,  # 14 days
            "is_seasonal": True,
            "seasonal_months": [3, 4, 5, 6, 7, 8, 9, 10, 11],  # Mar-Nov full capacity
            "capacity_reduction_percent": 50,  # 50% reduction Jan-Feb
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
        segment_id += 1

        # Generate Plant->DC, DC->DC, and Port routes
        plant_ids = list(self.plant_ids.values())
        dc_data = {dc["code"]: (self.dc_ids.get(dc["code"]), dc) for dc in DCS if dc["code"] in self.dc_ids or True}
        port_ids = list(self.port_ids.values())

        # We don't have DC IDs yet (Level 3), so generate generic segments
        modes = ["truck", "rail", "ocean", "air", "intermodal", "last_mile"]
        for _ in range(199):  # 199 more to get ~200 total
            mode = random.choices(modes, weights=[40, 15, 20, 5, 15, 5])[0]
            code = f"SEG-{mode[:3].upper()}-{segment_id:04d}"
            self.route_segment_ids[code] = segment_id

            # Pick random origin/dest types
            origin_type = random.choice(["plant", "dc", "port"])
            dest_type = random.choice(["dc", "port"])

            # Use placeholder IDs (will be properly linked in Level 2/3)
            origin_id = random.randint(1, 30)
            dest_id = random.randint(1, 30)

            distance = random.randint(50, 15000) if mode == "ocean" else random.randint(50, 2000)
            transit = distance / (800 if mode == "air" else 80 if mode == "truck" else 40 if mode == "ocean" else 60)

            self.data["route_segments"].append({
                "id": segment_id,
                "segment_code": code,
                "origin_type": origin_type,
                "origin_id": origin_id,
                "destination_type": dest_type,
                "destination_id": dest_id,
                "transport_mode": mode,
                "distance_km": round(distance, 2),
                "distance_miles": round(distance * 0.621371, 2),
                "transit_time_hours": round(transit, 2),
                "is_seasonal": random.random() < 0.1,
                "seasonal_months": None,
                "capacity_reduction_percent": None,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })
            segment_id += 1

        self.generated_levels.add(1)
        print(f"    Generated: {len(self.data['suppliers'])} suppliers, {len(self.data['plants'])} plants, "
              f"{len(self.data['production_lines'])} lines, {len(self.data['route_segments'])} segments")

    def _generate_level_2(self) -> None:
        """
        Level 2: Relationships and formulas.

        Tables: supplier_ingredients, certifications, formulas,
                formula_ingredients, carrier_rates, routes,
                route_segment_assignments
        """
        print("  Level 2: Relationships (supplier_ingredients, formulas...)")
        now = datetime.now()

        # --- SUPPLIER_INGREDIENTS (~400 links with preferential attachment) ---
        si_id = 1
        ingredient_ids = list(self.ingredient_ids.values())
        supplier_ids = list(self.supplier_ids.values())

        # Track supplier degrees for preferential attachment
        supplier_degrees = {sid: 0 for sid in supplier_ids}

        # Named SPOFs: Palm Oil and Sorbitol single-source
        palm_ing_id = self.ingredient_ids["ING-PALM-001"]
        sorb_ing_id = self.ingredient_ids["ING-SORB-001"]
        palm_sup_id = self.supplier_ids["SUP-PALM-MY-001"]

        # Palm Oil - ONLY from SUP-PALM-MY-001 (SPOF)
        self.supplier_ingredient_ids[(palm_sup_id, palm_ing_id)] = si_id
        self.data["supplier_ingredients"].append({
            "id": si_id,
            "supplier_id": palm_sup_id,
            "ingredient_id": palm_ing_id,
            "supplier_part_number": "MPP-PALM-001",
            "unit_cost": 1.25,
            "currency": "USD",
            "lead_time_days": 90,  # Long lead time (problem ingredient)
            "min_order_qty": 10000,
            "order_multiple": 1000,
            "is_preferred": True,
            "is_approved": True,
            "approval_date": date(2020, 2, 1),
            "contract_start_date": date(2024, 1, 1),
            "contract_end_date": date(2025, 12, 31),
            "on_time_delivery_rate": 0.50,  # Poor OTD (problem ingredient)
            "quality_acceptance_rate": 0.97,
            "created_at": now,
            "updated_at": now,
        })
        supplier_degrees[palm_sup_id] += 1
        si_id += 1

        # Sorbitol - single source (pick a random T1 supplier)
        sorb_supplier_id = random.choice([sid for sid in supplier_ids if sid != palm_sup_id])
        self.supplier_ingredient_ids[(sorb_supplier_id, sorb_ing_id)] = si_id
        self.data["supplier_ingredients"].append({
            "id": si_id,
            "supplier_id": sorb_supplier_id,
            "ingredient_id": sorb_ing_id,
            "supplier_part_number": f"SORB-{sorb_supplier_id:03d}",
            "unit_cost": 2.50,
            "currency": "USD",
            "lead_time_days": 21,
            "min_order_qty": 5000,
            "order_multiple": 500,
            "is_preferred": True,
            "is_approved": True,
            "approval_date": date(2021, 6, 15),
            "contract_start_date": date(2024, 1, 1),
            "contract_end_date": date(2025, 12, 31),
            "on_time_delivery_rate": 0.94,
            "quality_acceptance_rate": 0.99,
            "created_at": now,
            "updated_at": now,
        })
        supplier_degrees[sorb_supplier_id] += 1
        si_id += 1

        # Generate ~400 more supplier-ingredient links using preferential attachment
        for ing_id in ingredient_ids:
            if ing_id in [palm_ing_id, sorb_ing_id]:
                continue  # Already handled

            # How many suppliers for this ingredient? (1-5, weighted toward 2-3)
            num_suppliers = random.choices([1, 2, 3, 4, 5], weights=[5, 35, 40, 15, 5])[0]

            # Select suppliers using preferential attachment
            selected = barabasi_albert_attachment(
                [supplier_degrees.get(sid, 0) for sid in supplier_ids],
                m=num_suppliers,
                rng=self.rng
            )

            for idx in selected:
                sup_id = supplier_ids[idx]
                if (sup_id, ing_id) in self.supplier_ingredient_ids:
                    continue

                self.supplier_ingredient_ids[(sup_id, ing_id)] = si_id
                is_preferred = len([s for s in selected if supplier_ids[s] == sup_id]) == 1 and idx == selected[0]
                self.data["supplier_ingredients"].append({
                    "id": si_id,
                    "supplier_id": sup_id,
                    "ingredient_id": ing_id,
                    "supplier_part_number": f"ING-{sup_id:03d}-{ing_id:03d}",
                    "unit_cost": round(random.uniform(0.5, 15.0), 4),
                    "currency": "USD",
                    "lead_time_days": random.randint(7, 45),
                    "min_order_qty": random.choice([100, 500, 1000, 5000]),
                    "order_multiple": random.choice([50, 100, 500]),
                    "is_preferred": is_preferred,
                    "is_approved": True,
                    "approval_date": self.fake.date_between(start_date="-2y", end_date="today"),
                    "contract_start_date": date(2024, 1, 1),
                    "contract_end_date": date(2025, 12, 31),
                    "on_time_delivery_rate": round(random.uniform(0.85, 0.99), 4),
                    "quality_acceptance_rate": round(random.uniform(0.95, 0.999), 4),
                    "created_at": now,
                    "updated_at": now,
                })
                supplier_degrees[sup_id] += 1
                si_id += 1

        # --- CERTIFICATIONS (~500) ---
        cert_id = 1
        cert_types = ["ISO9001", "ISO14001", "GMP", "Halal", "Kosher", "RSPO", "FSC", "FSSC22000"]
        cert_bodies = ["SGS", "Bureau Veritas", "TÜV", "DNV", "Lloyd's Register", "Intertek"]

        for sup_id in supplier_ids:
            # Each supplier gets 2-4 certifications
            num_certs = random.randint(2, 4)
            chosen_certs = random.sample(cert_types, num_certs)
            for cert_type in chosen_certs:
                issue = self.fake.date_between(start_date="-2y", end_date="-6m")
                expiry = issue + timedelta(days=random.choice([365, 730, 1095]))
                cert_code = f"CERT-{sup_id:03d}-{cert_type}"
                self.certification_ids[cert_code] = cert_id
                self.data["certifications"].append({
                    "id": cert_id,
                    "supplier_id": sup_id,
                    "certification_type": cert_type,
                    "certification_body": random.choice(cert_bodies),
                    "certificate_number": f"{cert_type}-{self.fake.bothify('???###')}",
                    "issue_date": issue,
                    "expiry_date": expiry,
                    "scope": f"Manufacturing and supply of {random.choice(['chemicals', 'ingredients', 'raw materials'])}",
                    "is_valid": expiry > date.today(),
                    "created_at": now,
                    "updated_at": now,
                })
                cert_id += 1

        # --- FORMULAS (~150: 50 per product family x 3 variants) ---
        formula_id = 1
        product_formulas = {
            "PROD-PW": {"category": "oral_care", "batch_size": 500, "mix_time": 45, "cure_time": 2},
            "PROD-CW": {"category": "home_care", "batch_size": 1000, "mix_time": 30, "cure_time": 0},
            "PROD-AP": {"category": "personal_care", "batch_size": 750, "mix_time": 40, "cure_time": 1},
        }

        for prod_code, prod_info in product_formulas.items():
            prod_id = self.product_ids[prod_code]
            variants = ["Original", "Fresh", "Sensitive", "Whitening", "Premium"] if prod_code == "PROD-PW" else \
                       ["Original", "Lemon", "Antibacterial", "Eco", "Concentrated"] if prod_code == "PROD-CW" else \
                       ["Original", "Moisturizing", "Energizing", "Sensitive", "Luxury"]

            for variant in variants:
                for version in [1, 2, 3]:  # 3 versions each
                    code = f"FRM-{prod_code[-2:]}-{variant[:3].upper()}-V{version}"
                    self.formula_ids[code] = formula_id
                    self.data["formulas"].append({
                        "id": formula_id,
                        "formula_code": code,
                        "name": f"{prod_code.replace('PROD-', '')} {variant} Formula V{version}",
                        "product_id": prod_id,
                        "version": version,
                        "status": "approved" if version < 3 else "draft",
                        "batch_size_kg": prod_info["batch_size"],
                        "yield_percent": round(random.uniform(96, 99), 2),
                        "mix_time_minutes": prod_info["mix_time"] + random.randint(-5, 5),
                        "cure_time_hours": prod_info["cure_time"],
                        "effective_from": date(2024, 1, 1) if version == 1 else None,
                        "effective_to": None,
                        "approved_by": "R&D Director" if version < 3 else None,
                        "approved_date": date(2024, 1, 15) if version < 3 else None,
                        "notes": None,
                        "created_at": now,
                        "updated_at": now,
                    })
                    formula_id += 1

        # --- FORMULA_INGREDIENTS (~1500: ~10 ingredients per formula) ---
        # Map ingredient categories to products
        prod_ingredients = {
            "PROD-PW": ["abrasive", "humectant", "flavor", "active", "thickener", "preservative", "colorant", "ph_adjuster", "surfactant", "solvent"],
            "PROD-CW": ["surfactant", "fragrance", "preservative", "colorant", "ph_adjuster", "thickener", "solvent", "antibacterial"],
            "PROD-AP": ["surfactant", "moisturizer", "fragrance", "preservative", "colorant", "ph_adjuster", "emulsifier", "thickener", "antioxidant", "solvent"],
        }

        # Group ingredients by category
        ing_by_category = {}
        for ing in INGREDIENTS:
            cat = ing["category"]
            if cat not in ing_by_category:
                ing_by_category[cat] = []
            ing_by_category[cat].append(self.ingredient_ids[ing["code"]])

        for formula_code, formula_id_val in self.formula_ids.items():
            # Determine product
            prod_code = "PROD-" + formula_code.split("-")[1]
            categories = prod_ingredients.get(prod_code, ["surfactant", "preservative", "solvent"])

            sequence = 1
            batch_size = next(f["batch_size_kg"] for f in self.data["formulas"] if f["id"] == formula_id_val)
            remaining_pct = 100.0

            for cat in categories:
                if cat not in ing_by_category or not ing_by_category[cat]:
                    continue

                ing_id = random.choice(ing_by_category[cat])

                # Water is typically 60-80% of personal care products
                if cat == "solvent":
                    pct = min(remaining_pct, random.uniform(40, 70))
                else:
                    pct = min(remaining_pct, random.uniform(1, 15))

                remaining_pct -= pct
                qty = batch_size * pct / 100

                self.data["formula_ingredients"].append({
                    "formula_id": formula_id_val,
                    "ingredient_id": ing_id,
                    "sequence": sequence,
                    "quantity_kg": round(qty, 4),
                    "quantity_percent": round(pct, 2),
                    "is_active": True,
                    "tolerance_percent": 2.0,
                    "notes": None,
                    "created_at": now,
                })
                sequence += 1

        # --- CARRIER RATES (~1000) ---
        rate_id = 1
        contract_ids = list(self.carrier_contract_ids.values())
        transport_modes = ["ftl", "ltl", "rail", "ocean_fcl", "ocean_lcl", "air", "parcel", "intermodal"]

        for _ in range(1000):
            contract_id = random.choice(contract_ids)
            mode = random.choice(transport_modes)
            rate_code = f"RATE-{rate_id:05d}"
            self.carrier_rate_ids[rate_code] = rate_id

            # Weight breaks
            weight_min = random.choice([0, 100, 500, 1000, 5000])
            weight_max = weight_min + random.choice([100, 500, 1000, 5000, 10000])

            self.data["carrier_rates"].append({
                "id": rate_id,
                "contract_id": contract_id,
                "origin_type": random.choice(["plant", "dc", "city"]),
                "origin_code": f"LOC-{random.randint(1, 100):03d}",
                "destination_type": random.choice(["dc", "city", "region"]),
                "destination_code": f"LOC-{random.randint(1, 100):03d}",
                "transport_mode": mode,
                "weight_break_min_kg": weight_min,
                "weight_break_max_kg": weight_max,
                "rate_per_kg": round(random.uniform(0.05, 0.50), 4) if mode != "air" else round(random.uniform(1.0, 5.0), 4),
                "rate_per_case": round(random.uniform(0.5, 5.0), 4),
                "rate_per_pallet": round(random.uniform(20, 100), 2),
                "rate_per_shipment": round(random.uniform(100, 2000), 2) if mode in ["ftl", "ocean_fcl"] else None,
                "fuel_surcharge_percent": round(random.uniform(5, 20), 2),
                "currency": "USD",
                "transit_days": random.randint(1, 30),
                "effective_from": date(2024, 1, 1),
                "effective_to": date(2024, 12, 31),
                "created_at": now,
            })
            rate_id += 1

        # --- ROUTES (~50) ---
        route_id = 1
        for _ in range(50):
            code = f"ROUTE-{route_id:03d}"
            self.route_ids[code] = route_id
            self.data["routes"].append({
                "id": route_id,
                "route_code": code,
                "name": f"Route {route_id}",
                "origin_type": random.choice(["plant", "dc"]),
                "origin_id": random.randint(1, 25),
                "destination_type": random.choice(["dc", "port"]),
                "destination_id": random.randint(1, 25),
                "total_distance_km": round(random.uniform(100, 5000), 2),
                "total_transit_hours": round(random.uniform(4, 120), 2),
                "total_segments": random.randint(1, 4),
                "is_preferred": random.random() < 0.2,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })
            route_id += 1

        # --- ROUTE_SEGMENT_ASSIGNMENTS (~150) ---
        segment_ids = list(self.route_segment_ids.values())
        for route_code, route_id_val in self.route_ids.items():
            num_segments = self.data["routes"][route_id_val - 1]["total_segments"]
            chosen_segments = random.sample(segment_ids, min(num_segments, len(segment_ids)))
            for seq, seg_id in enumerate(chosen_segments, 1):
                self.data["route_segment_assignments"].append({
                    "route_id": route_id_val,
                    "segment_id": seg_id,
                    "sequence": seq,
                    "created_at": now,
                })

        self.generated_levels.add(2)
        print(f"    Generated: {len(self.data['supplier_ingredients'])} supplier_ingredients, "
              f"{len(self.data['formulas'])} formulas, {len(self.data['carrier_rates'])} rates")

    def _generate_level_3(self) -> None:
        """
        Level 3: Locations (retail accounts, stores, DCs).

        Tables: retail_accounts, retail_locations, distribution_centers
        """
        print("  Level 3: Locations (retail_accounts, retail_locations, DCs...)")
        now = datetime.now()

        # --- DISTRIBUTION CENTERS (25 from DCS constant) ---
        for i, dc in enumerate(DCS, 1):
            div_id = self.division_ids[dc["division"]]
            self.dc_ids[dc["code"]] = i
            self.data["distribution_centers"].append({
                "id": i,
                "dc_code": dc["code"],
                "name": dc["name"],
                "division_id": div_id,
                "dc_type": dc["dc_type"],
                "country": dc["country"],
                "city": dc["city"],
                "address": f"{random.randint(1, 9999)} Logistics Way",
                "latitude": dc["lat"],
                "longitude": dc["lon"],
                "capacity_cases": dc["capacity_cases"],
                "capacity_pallets": dc["capacity_cases"] // 50,
                "operating_hours": "06:00-22:00",
                "is_temperature_controlled": random.random() < 0.3,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

        # --- RETAIL ACCOUNTS (~100 with hub concentration) ---
        account_id = 1
        account_types = {
            "bm_large": ["megamart", "valueclub", "urbanessential"],
            "bm_distributor": ["regional_grocer", "indie_retail"],
            "ecommerce": ["digital_first", "omni_retailer"],
            "dtc": ["prism_direct"],
        }

        # Named entity: MegaMart (ACCT-MEGA-001) - hot node with 4,500 stores
        mega_div_id = self.division_ids["NAM"]
        mega_channel_id = self.channel_ids["B2M-LARGE"]
        self.retail_account_ids["ACCT-MEGA-001"] = account_id
        self.data["retail_accounts"].append({
            "id": account_id,
            "account_code": "ACCT-MEGA-001",
            "name": "MegaMart Corporation",
            "account_type": "megamart",
            "channel_id": mega_channel_id,
            "division_id": mega_div_id,
            "parent_account_id": None,
            "headquarters_country": "USA",
            "headquarters_city": "Bentonville",
            "store_count": 4500,
            "annual_volume_cases": 50_000_000,
            "payment_terms_days": 60,
            "credit_limit": 100_000_000,
            "is_strategic": True,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
        account_id += 1

        # Track account degrees for store allocation (preferential attachment)
        account_degrees = {1: 0}  # MegaMart starts with 0

        # Generate ~99 more accounts across divisions and channels
        for channel_code, channel_id in self.channel_ids.items():
            types = account_types.get(channel_code.replace("B2M-", "").lower(), ["regional_grocer"])
            num_accounts = 25 if channel_code == "B2M-LARGE" else 30 if channel_code == "B2M-DIST" else 20 if channel_code == "ECOM" else 10

            for _ in range(num_accounts):
                if account_id > 100:
                    break

                div_code = random.choice(list(self.division_ids.keys()))
                div_id = self.division_ids[div_code]
                acct_type = random.choice(types)
                code = f"ACCT-{acct_type[:4].upper()}-{account_id:03d}"

                store_count = random.randint(5, 500) if acct_type not in ["megamart", "valueclub"] else random.randint(500, 2000)
                volume = store_count * random.randint(5000, 20000)

                self.retail_account_ids[code] = account_id
                self.data["retail_accounts"].append({
                    "id": account_id,
                    "account_code": code,
                    "name": self.fake.company() + " " + random.choice(["Stores", "Retail", "Markets", "Grocers", ""]),
                    "account_type": acct_type,
                    "channel_id": channel_id,
                    "division_id": div_id,
                    "parent_account_id": None,
                    "headquarters_country": random.choice(["USA", "UK", "Germany", "France", "Brazil", "China", "India"]),
                    "headquarters_city": self.fake.city(),
                    "store_count": store_count,
                    "annual_volume_cases": volume,
                    "payment_terms_days": random.choice([30, 45, 60]),
                    "credit_limit": volume * 2,
                    "is_strategic": random.random() < 0.15,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                })
                account_degrees[account_id] = 0
                account_id += 1

        # --- RETAIL LOCATIONS (~10,000 with preferential attachment) ---
        location_id = 1
        store_formats = ["hypermarket", "supermarket", "convenience", "pharmacy", "drugstore"]
        dc_ids_list = list(self.dc_ids.values())
        account_ids_list = list(self.retail_account_ids.values())

        # MegaMart gets 4,500 stores (named entity requirement)
        mega_account_id = self.retail_account_ids["ACCT-MEGA-001"]
        us_cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
                     "Austin", "Jacksonville", "Fort Worth", "Columbus", "Charlotte", "Seattle", "Denver", "Boston", "Detroit", "Nashville"]

        for i in range(4500):
            code = f"LOC-MEGA-{location_id:05d}"
            self.retail_location_ids[code] = location_id
            city = random.choice(us_cities)
            # Assign to nearest NAM DC
            nam_dcs = [dc_id for dc_code, dc_id in self.dc_ids.items() if dc_code.startswith("DC-NAM")]
            primary_dc = random.choice(nam_dcs)

            self.data["retail_locations"].append({
                "id": location_id,
                "location_code": code,
                "name": f"MegaMart #{location_id}",
                "retail_account_id": mega_account_id,
                "store_format": random.choices(store_formats[:3], weights=[40, 50, 10])[0],
                "country": "USA",
                "city": city,
                "address": f"{random.randint(1, 9999)} {self.fake.street_name()}",
                "postal_code": self.fake.zipcode(),
                "latitude": round(random.uniform(25, 48), 6),
                "longitude": round(random.uniform(-122, -71), 6),
                "timezone": "America/New_York",
                "square_meters": random.randint(2000, 15000),
                "weekly_traffic": random.randint(5000, 50000),
                "primary_dc_id": primary_dc,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })
            account_degrees[mega_account_id] += 1
            location_id += 1

        # Generate ~5,500 more stores for other accounts (preferential attachment)
        remaining = 10000 - 4500
        for _ in range(remaining):
            # Preferential attachment to accounts
            selected_idx = barabasi_albert_attachment(
                [account_degrees.get(aid, 0) for aid in account_ids_list],
                m=1,
                rng=self.rng
            )[0]
            acct_id = account_ids_list[selected_idx]

            # Get account's division
            acct = next(a for a in self.data["retail_accounts"] if a["id"] == acct_id)
            div_id = acct["division_id"]

            # Find DCs in same division
            div_dcs = [dc["id"] for dc in self.data["distribution_centers"] if dc["division_id"] == div_id]
            primary_dc = random.choice(div_dcs) if div_dcs else random.choice(dc_ids_list)

            code = f"LOC-{acct_id:03d}-{location_id:05d}"
            self.retail_location_ids[code] = location_id

            country = acct.get("headquarters_country", "USA")
            self.data["retail_locations"].append({
                "id": location_id,
                "location_code": code,
                "name": f"Store #{location_id}",
                "retail_account_id": acct_id,
                "store_format": random.choice(store_formats),
                "country": country,
                "city": self.fake.city(),
                "address": f"{random.randint(1, 9999)} {self.fake.street_name()}",
                "postal_code": self.fake.zipcode() if country == "USA" else self.fake.postcode(),
                "latitude": round(random.uniform(-40, 60), 6),
                "longitude": round(random.uniform(-120, 140), 6),
                "timezone": self.fake.timezone(),
                "square_meters": random.randint(200, 5000),
                "weekly_traffic": random.randint(500, 20000),
                "primary_dc_id": primary_dc,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })
            account_degrees[acct_id] = account_degrees.get(acct_id, 0) + 1
            location_id += 1

        self.generated_levels.add(3)
        print(f"    Generated: {len(self.data['distribution_centers'])} DCs, "
              f"{len(self.data['retail_accounts'])} accounts, {len(self.data['retail_locations'])} locations")

    def _generate_level_4(self) -> None:
        """
        Level 4: SKU explosion and promotions.

        Tables: skus, sku_costs, sku_substitutes, promotions,
                promotion_skus, promotion_accounts
        """
        print("  Level 4: SKUs and promotions...")
        now = datetime.now()

        # --- SKUs (~2000: product × packaging × region explosion) ---
        sku_id = 1
        regions = ["NAM", "LATAM", "APAC", "EUR", "AFR-EUR", "GLOBAL"]
        languages = {"NAM": "en", "LATAM": "es", "APAC": "zh", "EUR": "en", "AFR-EUR": "fr", "GLOBAL": "en"}

        # SKU matrix: product × packaging × region (subset for realistic count)
        product_packaging = {
            "PROD-PW": ["PKG-TUBE-50", "PKG-TUBE-100", "PKG-TUBE-150", "PKG-TUBE-200", "PKG-TRIAL-30"],
            "PROD-CW": ["PKG-BOTL-250", "PKG-BOTL-500", "PKG-BOTL-750", "PKG-BOTL-1L", "PKG-REFILL-1L"],
            "PROD-AP": ["PKG-PUMP-250", "PKG-PUMP-500", "PKG-PUMP-750", "PKG-BOTL-250", "PKG-SACHET-10"],
        }

        for prod_code, pkg_codes in product_packaging.items():
            prod_id = self.product_ids[prod_code]
            prod_info = next(p for p in PRODUCTS if p["code"] == prod_code)
            brand = prod_info["brand"]

            # Get formulas for this product
            prod_formulas = [fid for fc, fid in self.formula_ids.items() if fc.split("-")[1] == prod_code[-2:]]

            for pkg_code in pkg_codes:
                pkg_id = self.packaging_type_ids[pkg_code]
                pkg_info = next(p for p in PACKAGING_TYPES if p["code"] == pkg_code)

                for region in regions:
                    # Skip some region/product combos to get realistic ~2000 SKUs
                    if region in ["AFR-EUR"] and prod_code == "PROD-AP":
                        continue  # Body wash not sold in Africa

                    lang = languages[region]
                    formula_id = random.choice(prod_formulas) if prod_formulas else None

                    code = f"SKU-{brand[:2].upper()}-{pkg_info['container'][:2].upper()}-{pkg_info['size']}{pkg_info['unit'][:1]}-{region}"
                    if code in self.sku_ids:
                        code = f"{code}-{sku_id}"

                    self.sku_ids[code] = sku_id

                    # Price based on size
                    base_price = pkg_info["size"] * 0.02 + random.uniform(1, 5)
                    shelf_life = 730 if prod_code == "PROD-PW" else 365

                    self.data["skus"].append({
                        "id": sku_id,
                        "sku_code": code,
                        "name": f"{brand} {pkg_info['name']} ({region})",
                        "product_id": prod_id,
                        "packaging_id": pkg_id,
                        "formula_id": formula_id,
                        "region": region,
                        "language": lang,
                        "upc": f"0{random.randint(10000000000, 99999999999)}",
                        "ean": f"{random.randint(1000000000000, 9999999999999)}",
                        "list_price": round(base_price, 2),
                        "currency": "USD",
                        "shelf_life_days": shelf_life,
                        "min_order_qty": pkg_info["per_case"],
                        "is_active": True,
                        "launch_date": date(2022, 1, 1),
                        "discontinue_date": None,
                        "created_at": now,
                        "updated_at": now,
                    })
                    sku_id += 1

        # Generate more SKUs to reach ~2000 (variants, promotional packs)
        while sku_id <= 2000:
            prod_code = random.choice(list(product_packaging.keys()))
            prod_id = self.product_ids[prod_code]
            prod_info = next(p for p in PRODUCTS if p["code"] == prod_code)
            brand = prod_info["brand"]
            pkg_code = random.choice(product_packaging[prod_code])
            pkg_id = self.packaging_type_ids[pkg_code]
            pkg_info = next(p for p in PACKAGING_TYPES if p["code"] == pkg_code)
            region = random.choice(regions)
            prod_formulas = [fid for fc, fid in self.formula_ids.items() if fc.split("-")[1] == prod_code[-2:]]

            variant = random.choice(["PROMO", "MULTI", "VALUE", "LTD", "CLUB"])
            code = f"SKU-{brand[:2].upper()}-{variant}-{sku_id:04d}"
            self.sku_ids[code] = sku_id

            self.data["skus"].append({
                "id": sku_id,
                "sku_code": code,
                "name": f"{brand} {variant.title()} Pack {pkg_info['name']}",
                "product_id": prod_id,
                "packaging_id": pkg_id,
                "formula_id": random.choice(prod_formulas) if prod_formulas else None,
                "region": region,
                "language": languages[region],
                "upc": f"0{random.randint(10000000000, 99999999999)}",
                "ean": f"{random.randint(1000000000000, 9999999999999)}",
                "list_price": round(random.uniform(3, 25), 2),
                "currency": "USD",
                "shelf_life_days": random.choice([365, 730]),
                "min_order_qty": pkg_info["per_case"],
                "is_active": True,
                "launch_date": self.fake.date_between(start_date="-2y", end_date="today"),
                "discontinue_date": None,
                "created_at": now,
                "updated_at": now,
            })
            sku_id += 1

        # --- SKU_COSTS (~2000: one per SKU) ---
        cost_types = ["material", "labor", "overhead", "packaging", "freight"]
        for sku in self.data["skus"]:
            base_cost = sku["list_price"] * 0.45  # ~45% COGS
            for cost_type in cost_types:
                pct = {"material": 0.50, "labor": 0.15, "overhead": 0.15, "packaging": 0.12, "freight": 0.08}[cost_type]
                self.data["sku_costs"].append({
                    "sku_id": sku["id"],
                    "cost_type": cost_type,
                    "cost_amount": round(base_cost * pct, 4),
                    "currency": "USD",
                    "effective_from": date(2024, 1, 1),
                    "effective_to": None,
                    "created_at": now,
                    "updated_at": now,
                })

        # --- SKU_SUBSTITUTES (~500: equivalency groups) ---
        # Group SKUs by product and size class for substitution
        sku_list = list(self.data["skus"])
        for _ in range(500):
            # Pick two random SKUs from same product
            prod_id = random.choice(list(self.product_ids.values()))
            prod_skus = [s for s in sku_list if s["product_id"] == prod_id]
            if len(prod_skus) < 2:
                continue
            sku1, sku2 = random.sample(prod_skus, 2)
            self.data["sku_substitutes"].append({
                "sku_id": sku1["id"],
                "substitute_sku_id": sku2["id"],
                "priority": random.randint(1, 5),
                "substitution_ratio": round(random.uniform(0.8, 1.2), 2),
                "is_bidirectional": random.random() < 0.7,
                "effective_from": date(2024, 1, 1),
                "effective_to": None,
                "created_at": now,
            })

        # --- PROMOTIONS (~100 including PROMO-BF-2024) ---
        promo_id = 1
        promo_types = ["price_discount", "bogo", "display", "feature", "tpr"]

        # Named entity: Black Friday 2024 (PROMO-BF-2024)
        self.promotion_ids["PROMO-BF-2024"] = promo_id
        self.data["promotions"].append({
            "id": promo_id,
            "promo_code": "PROMO-BF-2024",
            "name": "Black Friday 2024 Mega Sale",
            "promo_type": "price_discount",
            "start_date": date(2024, 11, 25),  # Week 48 start
            "end_date": date(2024, 12, 1),     # Week 48 end
            "lift_multiplier": 3.0,            # 3x demand spike
            "hangover_multiplier": 0.60,       # 40% drop post-promo
            "hangover_weeks": 2,
            "discount_percent": 25.0,
            "trade_spend_budget": 5_000_000,
            "status": "completed",
            "notes": "Annual Black Friday event - highest volume week",
            "created_at": now,
            "updated_at": now,
        })
        promo_id += 1

        # Generate 99 more promotions throughout the year
        for _ in range(99):
            code = f"PROMO-{self.base_year}-{promo_id:03d}"
            self.promotion_ids[code] = promo_id

            promo_type = random.choice(promo_types)
            start = self.fake.date_between(start_date=date(self.base_year, 1, 1), end_date=date(self.base_year, 12, 15))
            duration = random.choice([7, 14, 21, 28])
            end = start + timedelta(days=duration)

            lift = random.uniform(1.3, 2.5)
            hangover = random.uniform(0.60, 0.85)

            self.data["promotions"].append({
                "id": promo_id,
                "promo_code": code,
                "name": f"{random.choice(['Spring', 'Summer', 'Fall', 'Winter', 'Holiday', 'Back to School', 'Clearance'])} {promo_type.replace('_', ' ').title()}",
                "promo_type": promo_type,
                "start_date": start,
                "end_date": end,
                "lift_multiplier": round(lift, 2),
                "hangover_multiplier": round(hangover, 2),
                "hangover_weeks": random.randint(1, 3),
                "discount_percent": round(random.uniform(10, 40), 1) if promo_type == "price_discount" else None,
                "trade_spend_budget": round(random.uniform(50000, 500000), 2),
                "status": "completed" if end < date.today() else "active" if start <= date.today() else "planned",
                "notes": None,
                "created_at": now,
                "updated_at": now,
            })
            promo_id += 1

        # --- PROMOTION_SKUS (link promotions to SKUs) ---
        sku_ids_list = list(self.sku_ids.values())
        for promo in self.data["promotions"]:
            # Each promotion applies to 5-50 SKUs
            num_skus = random.randint(5, 50)
            promo_skus = random.sample(sku_ids_list, min(num_skus, len(sku_ids_list)))
            for sku_id in promo_skus:
                self.data["promotion_skus"].append({
                    "promo_id": promo["id"],
                    "sku_id": sku_id,
                    "specific_discount_percent": round(random.uniform(10, 40), 1) if random.random() < 0.3 else None,
                    "specific_lift_multiplier": round(random.uniform(1.2, 2.0), 2) if random.random() < 0.2 else None,
                    "created_at": now,
                })

        # --- PROMOTION_ACCOUNTS (link promotions to retail accounts) ---
        account_ids_list = list(self.retail_account_ids.values())
        for promo in self.data["promotions"]:
            # Each promotion runs at 10-50 accounts
            num_accounts = random.randint(10, 50)
            promo_accounts = random.sample(account_ids_list, min(num_accounts, len(account_ids_list)))
            for acct_id in promo_accounts:
                self.data["promotion_accounts"].append({
                    "promo_id": promo["id"],
                    "retail_account_id": acct_id,
                    "trade_spend_allocation": round(promo["trade_spend_budget"] / len(promo_accounts), 2),
                    "created_at": now,
                })

        self.generated_levels.add(4)
        print(f"    Generated: {len(self.data['skus'])} SKUs, {len(self.data['promotions'])} promotions, "
              f"{len(self.data['promotion_skus'])} promo-SKU links")

    def _generate_level_5(self) -> None:
        """
        Level 5: Procurement and work orders.

        Tables: purchase_orders, goods_receipts, work_orders,
                supplier_esg_scores, sustainability_targets,
                modal_shift_opportunities
        """
        print("  Level 5: Procurement (POs, work_orders...)")
        now = datetime.now()

        # --- PURCHASE ORDERS (~25,000) ---
        supplier_ids = list(self.supplier_ids.values())
        plant_ids = list(self.plant_ids.values())
        po_statuses = ["draft", "submitted", "confirmed", "shipped", "partial", "received", "cancelled"]
        incoterms_list = ["FOB", "CIF", "DDP", "EXW", "FCA"]

        for po_id in range(1, 25001):
            po_number = f"PO-{self.base_year}-{po_id:06d}"
            self.purchase_order_ids[po_number] = po_id

            order_date = self.fake.date_between(start_date=date(self.base_year, 1, 1), end_date=date(self.base_year, 12, 15))
            lead_time = random.randint(7, 60)
            requested_date = order_date + timedelta(days=lead_time)
            promised_date = requested_date + timedelta(days=random.randint(-3, 7))

            # Weight status toward received for older POs
            days_ago = (date.today() - order_date).days
            if days_ago > 60:
                status = random.choices(po_statuses, weights=[0, 0, 5, 5, 10, 75, 5])[0]
            elif days_ago > 30:
                status = random.choices(po_statuses, weights=[0, 5, 10, 20, 20, 40, 5])[0]
            else:
                status = random.choices(po_statuses, weights=[5, 15, 30, 25, 15, 5, 5])[0]

            self.data["purchase_orders"].append({
                "id": po_id,
                "po_number": po_number,
                "supplier_id": random.choice(supplier_ids),
                "plant_id": random.choice(plant_ids),
                "order_date": order_date,
                "requested_date": requested_date,
                "promised_date": promised_date,
                "status": status,
                "total_amount": None,  # Calculated from lines
                "currency": "USD",
                "incoterms": random.choice(incoterms_list),
                "notes": None,
                "created_by": self.fake.name(),
                "created_at": now,
                "updated_at": now,
            })

        # --- GOODS RECEIPTS (~20,000: ~80% of POs receive goods) ---
        received_pos = [po for po in self.data["purchase_orders"] if po["status"] in ["received", "partial", "shipped"]]
        gr_id = 1
        for po in received_pos[:20000]:
            gr_number = f"GR-{self.base_year}-{gr_id:06d}"
            self.goods_receipt_ids[gr_number] = gr_id

            receipt_date = po["promised_date"] + timedelta(days=random.randint(-5, 10))
            variance_pct = round(random.uniform(-5, 5), 2)

            self.data["goods_receipts"].append({
                "id": gr_id,
                "gr_number": gr_number,
                "po_id": po["id"],
                "receipt_date": receipt_date,
                "received_by": self.fake.name(),
                "status": "complete" if po["status"] == "received" else "partial",
                "total_quantity_variance_percent": variance_pct,
                "quality_status": random.choices(["approved", "pending", "rejected"], weights=[85, 10, 5])[0],
                "storage_location": f"WH-{random.randint(1, 10):02d}",
                "notes": None,
                "created_at": now,
                "updated_at": now,
            })
            gr_id += 1

        # --- WORK ORDERS (~50,000) ---
        formula_ids = list(self.formula_ids.values())
        line_ids = list(self.production_line_ids.values())
        wo_statuses = ["planned", "released", "in_progress", "completed", "cancelled", "on_hold"]

        for wo_id in range(1, 50001):
            wo_number = f"WO-{self.base_year}-{wo_id:06d}"
            self.work_order_ids[wo_number] = wo_id

            formula_id = random.choice(formula_ids)
            formula = next(f for f in self.data["formulas"] if f["id"] == formula_id)
            plant_id = random.choice(plant_ids)

            # Find lines in this plant
            plant_lines = [lid for lc, lid in self.production_line_ids.items()
                         if any(l["plant_id"] == plant_id and l["id"] == lid for l in self.data["production_lines"])]
            line_id = random.choice(plant_lines) if plant_lines else random.choice(line_ids)

            planned_start = self.fake.date_between(start_date=date(self.base_year, 1, 1), end_date=date(self.base_year, 12, 20))
            duration_days = random.randint(1, 5)
            planned_end = planned_start + timedelta(days=duration_days)

            # Status based on date
            days_ago = (date.today() - planned_end).days
            if days_ago > 30:
                status = random.choices(wo_statuses, weights=[0, 0, 5, 90, 3, 2])[0]
            elif days_ago > 0:
                status = random.choices(wo_statuses, weights=[0, 5, 15, 70, 5, 5])[0]
            else:
                status = random.choices(wo_statuses, weights=[30, 25, 20, 10, 5, 10])[0]

            planned_qty = formula["batch_size_kg"] * random.randint(1, 10)
            actual_qty = round(planned_qty * random.uniform(0.95, 1.02), 2) if status == "completed" else None

            self.data["work_orders"].append({
                "id": wo_id,
                "wo_number": wo_number,
                "formula_id": formula_id,
                "plant_id": plant_id,
                "production_line_id": line_id,
                "planned_quantity_kg": planned_qty,
                "actual_quantity_kg": actual_qty,
                "planned_start_date": planned_start,
                "planned_end_date": planned_end,
                "actual_start_datetime": datetime.combine(planned_start, datetime.min.time()) if status in ["in_progress", "completed"] else None,
                "actual_end_datetime": datetime.combine(planned_end, datetime.min.time()) if status == "completed" else None,
                "status": status,
                "priority": random.randint(1, 5),
                "notes": None,
                "created_by": self.fake.name(),
                "created_at": now,
                "updated_at": now,
            })

        # --- SUPPLIER_ESG_SCORES (~200: one per supplier) ---
        for sup in self.data["suppliers"]:
            self.data["supplier_esg_scores"].append({
                "id": sup["id"],
                "supplier_id": sup["id"],
                "assessment_date": self.fake.date_between(start_date="-1y", end_date="today"),
                "environmental_score": round(random.uniform(50, 100), 1),
                "social_score": round(random.uniform(50, 100), 1),
                "governance_score": round(random.uniform(50, 100), 1),
                "overall_score": round(random.uniform(50, 100), 1),
                "carbon_intensity_kg_per_unit": round(random.uniform(0.1, 2.0), 3),
                "renewable_energy_percent": round(random.uniform(10, 80), 1),
                "water_usage_liters_per_unit": round(random.uniform(1, 50), 1),
                "waste_diverted_percent": round(random.uniform(40, 95), 1),
                "assessor": random.choice(["EcoVadis", "CDP", "Internal Audit"]),
                "notes": None,
                "created_at": now,
                "updated_at": now,
            })

        # --- SUSTAINABILITY_TARGETS (~50) ---
        target_types = ["carbon_reduction", "renewable_energy", "water_reduction", "waste_reduction", "packaging_recyclability"]
        for st_id in range(1, 51):
            self.data["sustainability_targets"].append({
                "id": st_id,
                "target_code": f"SUST-{self.base_year}-{st_id:03d}",
                "target_type": random.choice(target_types),
                "baseline_year": 2020,
                "target_year": random.choice([2025, 2030, 2035]),
                "baseline_value": round(random.uniform(50, 100), 1),
                "target_value": round(random.uniform(10, 50), 1),
                "current_value": round(random.uniform(30, 80), 1),
                "unit": random.choice(["percent", "kg_co2", "liters", "tons"]),
                "scope": random.choice(["scope_1", "scope_2", "scope_3", "all_scopes"]),
                "notes": None,
                "created_at": now,
                "updated_at": now,
            })

        # --- MODAL_SHIFT_OPPORTUNITIES (~100) ---
        for ms_id in range(1, 101):
            current_mode = random.choice(["truck", "air"])
            target_mode = "rail" if current_mode == "truck" else random.choice(["truck", "ocean"])
            self.data["modal_shift_opportunities"].append({
                "id": ms_id,
                "opportunity_code": f"MODAL-{ms_id:03d}",
                "route_id": random.choice(list(self.route_ids.values())),
                "current_mode": current_mode,
                "target_mode": target_mode,
                "annual_volume_cases": random.randint(10000, 500000),
                "current_cost_per_case": round(random.uniform(1, 10), 2),
                "target_cost_per_case": round(random.uniform(0.5, 8), 2),
                "current_co2_per_case": round(random.uniform(0.2, 2.0), 3),
                "target_co2_per_case": round(random.uniform(0.05, 1.0), 3),
                "transit_time_delta_hours": random.randint(-48, 72),
                "implementation_cost": round(random.uniform(10000, 500000), 2),
                "payback_months": random.randint(6, 36),
                "status": random.choice(["identified", "evaluating", "approved", "implementing", "completed"]),
                "notes": None,
                "created_at": now,
                "updated_at": now,
            })

        self.generated_levels.add(5)
        print(f"    Generated: {len(self.data['purchase_orders'])} POs, {len(self.data['goods_receipts'])} GRs, "
              f"{len(self.data['work_orders'])} WOs")

    def _generate_level_6(self) -> None:
        """
        Level 6: PO/WO lines and batches.

        Tables: purchase_order_lines, goods_receipt_lines,
                work_order_materials, batches, batch_cost_ledger

        Phase 5 Optimization: Uses LookupBuilder for O(1) FK lookups.
        """
        print("  Level 6: Manufacturing (PO lines, batches...)")
        level_start = time.time()
        now = datetime.now()
        ingredient_ids = list(self.ingredient_ids.values())

        # Pre-generate LOT numbers efficiently using NumPy vectorization
        lot_batch_size = 210000  # Max LOT numbers we'll need
        letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        digits = list("0123456789")
        lot_letters = self.rng.choice(letters, size=(lot_batch_size, 3))
        lot_digits = self.rng.choice(digits, size=(lot_batch_size, 3))
        lot_numbers = [
            f"LOT-{''.join(lot_letters[i])}{''.join(lot_digits[i])}"
            for i in range(lot_batch_size)
        ]
        lot_idx = 0

        # --- PURCHASE_ORDER_LINES (~75,000: ~3 lines per PO) ---
        po_line_count = 0
        for po in self.data["purchase_orders"]:
            num_lines = random.randint(1, 5)
            for line_num in range(1, num_lines + 1):
                ing_id = random.choice(ingredient_ids)
                qty = random.randint(100, 10000)
                unit_cost = round(random.uniform(0.5, 20), 4)
                self.data["purchase_order_lines"].append({
                    "po_id": po["id"],
                    "line_number": line_num,
                    "ingredient_id": ing_id,
                    "quantity": qty,
                    "unit_of_measure": "kg",
                    "unit_cost": unit_cost,
                    "extended_cost": round(qty * unit_cost, 2),
                    "requested_date": po["requested_date"],
                    "promised_date": po["promised_date"],
                    "status": po["status"],
                    "notes": None,
                    "created_at": now,
                })
                po_line_count += 1
                if po_line_count >= 75000:
                    break
            if po_line_count >= 75000:
                break

        # --- GOODS_RECEIPT_LINES (~60,000: ~3 lines per GR) ---
        # Phase 5: Build O(1) lookup index for PO lines by PO ID (replaces O(N) scan)
        po_lines_idx = LookupBuilder.build_po_lines_by_po_id(self.data["purchase_order_lines"])

        gr_line_count = 0
        for gr in self.data["goods_receipts"]:
            # O(1) lookup replaces O(N) list comprehension
            po_lines = po_lines_idx.get(gr["po_id"])
            for pl in po_lines:
                received_qty = round(pl["quantity"] * random.uniform(0.95, 1.05), 2)
                accepted_qty = round(received_qty * random.uniform(0.97, 1.0), 2)
                self.data["goods_receipt_lines"].append({
                    "gr_id": gr["id"],
                    "po_line_po_id": pl["po_id"],
                    "po_line_number": pl["line_number"],
                    "received_quantity": received_qty,
                    "accepted_quantity": accepted_qty,
                    "rejected_quantity": round(received_qty - accepted_qty, 2),
                    "lot_number": lot_numbers[lot_idx % lot_batch_size],
                    "expiry_date": gr["receipt_date"] + timedelta(days=random.randint(180, 730)),
                    "storage_location": gr["storage_location"],
                    "quality_status": gr["quality_status"],
                    "notes": None,
                    "created_at": now,
                })
                lot_idx += 1
                gr_line_count += 1
                if gr_line_count >= 60000:
                    break
            if gr_line_count >= 60000:
                break

        # --- WORK_ORDER_MATERIALS (~150,000: ~3 materials per WO) ---
        # Phase 5: Build O(1) lookup indices (replaces O(N) scans)
        formulas_idx = LookupBuilder.build_unique(self.data["formulas"], "id")
        formula_ings_idx = LookupBuilder.build_formula_ings_by_formula_id(self.data["formula_ingredients"])

        wo_mat_count = 0
        for wo in self.data["work_orders"]:
            # O(1) lookup replaces O(N) next() scan
            formula = formulas_idx.get(wo["formula_id"])
            if not formula:
                continue
            # O(1) lookup replaces O(N) list comprehension
            formula_ings = formula_ings_idx.get(wo["formula_id"])

            for fi in formula_ings[:5]:  # Limit to 5 key materials per WO
                planned_qty = fi["quantity_kg"] * (wo["planned_quantity_kg"] / formula["batch_size_kg"])
                actual_qty = round(planned_qty * random.uniform(0.98, 1.03), 4) if wo["status"] == "completed" else None
                self.data["work_order_materials"].append({
                    "wo_id": wo["id"],
                    "ingredient_id": fi["ingredient_id"],
                    "sequence": fi["sequence"],
                    "planned_quantity_kg": round(planned_qty, 4),
                    "actual_quantity_kg": actual_qty,
                    "unit_cost": round(random.uniform(0.5, 15), 4),
                    "lot_number": lot_numbers[lot_idx % lot_batch_size] if wo["status"] == "completed" else None,
                    "notes": None,
                    "created_at": now,
                })
                lot_idx += 1
                wo_mat_count += 1
                if wo_mat_count >= 150000:
                    break
            if wo_mat_count >= 150000:
                break

        # --- BATCHES (~50,000: one per completed/in-progress WO) ---
        batch_id = 1
        completed_wos = [wo for wo in self.data["work_orders"] if wo["status"] in ["completed", "in_progress"]]
        qc_statuses = ["pending", "approved", "rejected", "hold", "quarantine"]

        # Named entity: B-2024-RECALL-001 (contaminated Sorbitol batch)
        recall_wo = completed_wos[0] if completed_wos else self.data["work_orders"][0]
        self.batch_ids["B-2024-RECALL-001"] = batch_id
        self.data["batches"].append({
            "id": batch_id,
            "batch_number": "B-2024-RECALL-001",
            "wo_id": recall_wo["id"],
            "formula_id": recall_wo["formula_id"],
            "plant_id": recall_wo["plant_id"],
            "production_line_id": recall_wo["production_line_id"],
            "quantity_kg": recall_wo["actual_quantity_kg"] or recall_wo["planned_quantity_kg"],
            "yield_percent": 97.5,
            "production_date": date(2024, 3, 15),
            "expiry_date": date(2025, 3, 15),
            "qc_status": "hold",  # QUALITY_HOLD for recall testing
            "qc_release_date": None,
            "qc_notes": "RECALL: Sorbitol contamination detected - all downstream orders affected",
            "is_contaminated": True,
            "contamination_notes": "ING-SORB-001 batch lot affected by supplier quality issue",
            "created_at": now,
            "updated_at": now,
        })
        batch_id += 1

        # Generate remaining batches
        for wo in completed_wos[1:50000]:
            batch_num = f"B-{self.base_year}-{batch_id:06d}"
            self.batch_ids[batch_num] = batch_id

            prod_date = wo["planned_start_date"] + timedelta(days=random.randint(0, 3))
            expiry = prod_date + timedelta(days=random.choice([365, 548, 730]))

            self.data["batches"].append({
                "id": batch_id,
                "batch_number": batch_num,
                "wo_id": wo["id"],
                "formula_id": wo["formula_id"],
                "plant_id": wo["plant_id"],
                "production_line_id": wo["production_line_id"],
                "quantity_kg": wo["actual_quantity_kg"] or round(wo["planned_quantity_kg"] * random.uniform(0.95, 1.02), 2),
                "yield_percent": round(random.uniform(95, 99.5), 2),
                "production_date": prod_date,
                "expiry_date": expiry,
                "qc_status": random.choices(qc_statuses, weights=[5, 88, 2, 3, 2])[0],
                "qc_release_date": prod_date + timedelta(days=random.randint(1, 5)) if random.random() > 0.1 else None,
                "qc_notes": None,
                "is_contaminated": False,
                "contamination_notes": None,
                "created_at": now,
                "updated_at": now,
            })
            batch_id += 1

        # --- BATCH_COST_LEDGER (~50,000: one per batch) ---
        cost_categories = ["material", "labor", "overhead", "quality", "scrap"]
        for batch in self.data["batches"]:
            batch_cost = round(batch["quantity_kg"] * random.uniform(2, 10), 2)
            for cat in cost_categories:
                pct = {"material": 0.55, "labor": 0.20, "overhead": 0.15, "quality": 0.05, "scrap": 0.05}[cat]
                self.data["batch_cost_ledger"].append({
                    "batch_id": batch["id"],
                    "cost_category": cat,
                    "amount": round(batch_cost * pct, 4),
                    "currency": "USD",
                    "cost_date": batch["production_date"],
                    "gl_account": f"5{['100', '200', '300', '400', '500'][cost_categories.index(cat)]}-00",
                    "notes": None,
                    "created_at": now,
                })

        self.generated_levels.add(6)
        level_elapsed = time.time() - level_start
        print(f"    Generated: {len(self.data['purchase_order_lines'])} PO lines, "
              f"{len(self.data['batches'])} batches, {len(self.data['work_order_materials'])} WO materials")
        self._report_level_stats(6, level_elapsed)

    def _generate_level_7(self) -> None:
        """
        Level 7: Batch consumption and inventory.

        Tables: batch_ingredients, inventory

        Phase 5 Optimization: Uses LookupBuilder for O(1) FK lookups.
        """
        print("  Level 7: Batch ingredients and inventory...")
        level_start = time.time()
        now = datetime.now()

        # Phase 5: Build O(1) lookup indices (replaces O(N) scans)
        formulas_idx = LookupBuilder.build_unique(self.data["formulas"], "id")
        formula_ings_idx = LookupBuilder.build_formula_ings_by_formula_id(self.data["formula_ingredients"])

        # --- BATCH_INGREDIENTS (~150,000: actual consumption per batch) ---
        bi_count = 0
        for batch in self.data["batches"]:
            # O(1) lookups replace O(N) scans
            formula_ings = formula_ings_idx.get(batch["formula_id"])
            formula = formulas_idx.get(batch["formula_id"])
            if not formula:
                continue

            scale_factor = batch["quantity_kg"] / formula["batch_size_kg"]

            for fi in formula_ings:
                planned_qty = fi["quantity_kg"] * scale_factor
                # Actual consumption varies slightly from planned
                actual_qty = round(planned_qty * random.uniform(0.97, 1.04), 4)
                scrap = round(max(0, actual_qty - planned_qty) * random.uniform(0, 0.5), 4)

                self.data["batch_ingredients"].append({
                    "batch_id": batch["id"],
                    "ingredient_id": fi["ingredient_id"],
                    "sequence": fi["sequence"],
                    "planned_quantity_kg": round(planned_qty, 4),
                    "actual_quantity_kg": actual_qty,
                    "scrap_quantity_kg": scrap,
                    "lot_number": f"LOT-{self.fake.bothify('???###')}",
                    "notes": None,
                    "created_at": now,
                })
                bi_count += 1
                if bi_count >= 150000:
                    break
            if bi_count >= 150000:
                break

        # --- INVENTORY (~50,000: SKU × location combinations) ---
        # Phase 5: Build O(1) lookup for batches by ID
        batches_idx = LookupBuilder.build_unique(self.data["batches"], "id")

        sku_ids = list(self.sku_ids.values())
        dc_ids = list(self.dc_ids.values())
        batch_ids = list(self.batch_ids.values())
        inv_id = 1

        # Generate inventory at DCs for popular SKUs
        for dc_id in dc_ids:
            # Each DC holds 200-500 SKUs
            num_skus = random.randint(200, min(500, len(sku_ids)))
            dc_skus = random.sample(sku_ids, num_skus)

            for sku_id in dc_skus:
                # Multiple batches per SKU at each DC
                num_lots = random.randint(1, 4)
                available_batches = random.sample(batch_ids, min(num_lots, len(batch_ids)))

                for batch_id in available_batches:
                    # O(1) lookup replaces O(N) next() scan
                    batch = batches_idx.get(batch_id)
                    if not batch:
                        continue

                    qty_cases = random.randint(10, 2000)
                    self.inventory_ids[(dc_id, sku_id, batch_id)] = inv_id
                    self.data["inventory"].append({
                        "id": inv_id,
                        "location_type": "dc",
                        "location_id": dc_id,
                        "sku_id": sku_id,
                        "batch_id": batch_id,
                        "quantity_cases": qty_cases,
                        "quantity_eaches": qty_cases * 12,  # Assumed 12 per case
                        "lot_number": batch["batch_number"],
                        "expiry_date": batch["expiry_date"],
                        "receipt_date": batch["production_date"] + timedelta(days=random.randint(1, 14)),
                        "aging_bucket": random.choice(["0-30", "31-60", "61-90", "90+"]),
                        "quality_status": "available",
                        "is_allocated": random.random() < 0.3,
                        "allocated_quantity": random.randint(0, qty_cases // 2) if random.random() < 0.3 else 0,
                        "created_at": now,
                        "updated_at": now,
                    })
                    inv_id += 1
                    if inv_id > 50000:
                        break
                if inv_id > 50000:
                    break
            if inv_id > 50000:
                break

        self.generated_levels.add(7)
        level_elapsed = time.time() - level_start
        print(f"    Generated: {len(self.data['batch_ingredients'])} batch_ingredients, "
              f"{len(self.data['inventory'])} inventory records")
        self._report_level_stats(7, level_elapsed)

    def _generate_level_8(self) -> None:
        """
        Level 8: Demand signals and orders (LARGEST).

        Tables: pos_sales (~2M), demand_forecasts, forecast_accuracy,
                consensus_adjustments, orders, replenishment_params,
                demand_allocation, capacity_plans

        Phase 5 Optimization: Uses LookupBuilder for O(1) FK lookups.
        """
        print("  Level 8: Demand and orders (LARGEST - pos_sales, orders...)")
        level_start = time.time()
        now = datetime.now()

        # Get references
        location_ids = list(self.retail_location_ids.values())
        sku_ids = list(self.sku_ids.values())
        account_ids = list(self.retail_account_ids.values())
        channel_ids = list(self.channel_ids.values())
        promo_ids = list(self.promotion_ids.values())
        dc_ids = list(self.dc_ids.values())

        # Create SKU popularity ranks using Zipf distribution (for 80/20 rule)
        num_skus = len(sku_ids)
        sku_popularity = {}
        zipf_ranks = self.rng.zipf(1.5, size=num_skus)
        for i, sid in enumerate(sku_ids):
            sku_popularity[sid] = zipf_ranks[i]

        # Get Black Friday promo dates
        bf_promo = next((p for p in self.data["promotions"] if p["promo_code"] == "PROMO-BF-2024"), None)
        bf_week = 48  # Week 48 is Black Friday week

        # --- POS_SALES (~500,000) - Phase 5 Vectorized Generation ---
        # Build promo SKU set ONCE (avoids O(N²) list comprehension in loop)
        bf_promo_sku_ids: set[int] = set()
        bf_promo_id: int | None = None
        if bf_promo:
            bf_promo_id = bf_promo["id"]
            bf_promo_sku_ids = {
                ps["sku_id"] for ps in self.data["promotion_skus"]
                if ps["promo_id"] == bf_promo_id
            }

        # Build SKU prices dict ONCE (avoids O(N) linear search per row)
        sku_prices = {s["id"]: float(s["list_price"]) for s in self.data["skus"]}

        # Configure vectorized generator
        pos_gen = POSSalesGenerator(seed=self.seed)
        pos_gen.configure(
            sku_ids=sku_ids,
            location_ids=location_ids,
            sku_prices=sku_prices,
            promo_sku_ids=bf_promo_sku_ids,
            promo_weeks={bf_week} if bf_promo else set(),
            hangover_weeks={bf_week + 1} if bf_promo else set(),
        )

        # Set promo effects from the actual promotion
        if bf_promo:
            pos_gen.promo_lift = float(bf_promo.get("lift_multiplier", 2.5))
            pos_gen.promo_hangover = float(bf_promo.get("hangover_multiplier", 0.7))

        # Generate 500K rows vectorized (~1 second vs 10+ minutes)
        pos_sales_array = pos_gen.generate_batch(500000, promo_id=bf_promo_id)
        pos_sales_dicts = structured_to_dicts(pos_sales_array)

        # Convert promo_id=0 to None (NULL in DB) for non-promotional rows
        for row in pos_sales_dicts:
            if row["promo_id"] == 0:
                row["promo_id"] = None

        self.data["pos_sales"] = pos_sales_dicts

        # --- DEMAND_FORECASTS (~100,000) ---
        forecast_id = 1
        forecast_versions = [f"{self.base_year}-W{w:02d}-STAT" for w in range(1, 53)]
        location_types = ["dc", "account", "division"]

        for _ in range(100000):
            self.data["demand_forecasts"].append({
                "id": forecast_id,
                "forecast_version": random.choice(forecast_versions),
                "sku_id": random.choice(sku_ids),
                "location_type": random.choice(location_types),
                "location_id": random.randint(1, 100),
                "forecast_date": self.fake.date_between(start_date=date(self.base_year, 1, 1),
                                                        end_date=date(self.base_year, 12, 31)),
                "forecast_week": random.randint(1, 52),
                "statistical_forecast": random.randint(100, 10000),
                "consensus_forecast": random.randint(100, 10000),
                "final_forecast": random.randint(100, 10000),
                "forecast_unit": "cases",
                "confidence_level": round(random.uniform(0.7, 0.95), 2),
                "created_at": now,
                "updated_at": now,
            })
            forecast_id += 1

        # --- FORECAST_ACCURACY (~10,000) ---
        for fa_id in range(1, 10001):
            actual = random.randint(100, 5000)
            forecast = random.randint(80, 5500)
            mape = abs(actual - forecast) / actual * 100 if actual > 0 else 0
            self.data["forecast_accuracy"].append({
                "id": fa_id,
                "forecast_id": random.randint(1, min(100000, forecast_id - 1)),
                "actual_demand": actual,
                "forecast_demand": forecast,
                "mape": round(mape, 2),
                "bias": round((forecast - actual) / actual * 100, 2) if actual > 0 else 0,
                "tracking_signal": round(random.uniform(-3, 3), 2),
                "period_date": self.fake.date_between(start_date=date(self.base_year, 1, 1),
                                                      end_date=date(self.base_year, 12, 31)),
                "created_at": now,
            })

        # --- CONSENSUS_ADJUSTMENTS (~5,000) ---
        for ca_id in range(1, 5001):
            self.data["consensus_adjustments"].append({
                "id": ca_id,
                "forecast_id": random.randint(1, min(100000, forecast_id - 1)),
                "adjustment_type": random.choice(["manual", "event", "promotion", "phase_in", "phase_out"]),
                "adjustment_percent": round(random.uniform(-30, 50), 1),
                "adjustment_units": random.randint(-500, 2000),
                "reason": random.choice(["Promotional lift", "New store opening", "Weather impact",
                                        "Competitor action", "Supply constraint", "Category reset"]),
                "adjusted_by": self.fake.name(),
                "adjustment_date": self.fake.date_between(start_date=date(self.base_year, 1, 1),
                                                          end_date=date(self.base_year, 12, 31)),
                "is_approved": random.random() > 0.1,
                "approved_by": self.fake.name() if random.random() > 0.1 else None,
                "notes": None,
                "created_at": now,
            })

        # --- ORDERS (~200,000) ---
        # Phase 5: Build O(1) lookup indices (replaces O(N) scans)
        locations_by_account_idx = LookupBuilder.build_locations_by_account_id(self.data["retail_locations"])
        accounts_idx = LookupBuilder.build_unique(self.data["retail_accounts"], "id")

        # Pre-compute location ID lists per account for O(1) random selection
        location_ids_by_account: dict[int, list[int]] = {}
        for acct_id in account_ids:
            locs = locations_by_account_idx.get(acct_id)
            location_ids_by_account[acct_id] = [loc["id"] for loc in locs] if locs else location_ids

        order_id = 1
        order_statuses = ["pending", "confirmed", "allocated", "picking", "shipped", "delivered", "cancelled"]
        order_types = ["standard", "rush", "backorder", "promotional"]
        mega_account_id = self.retail_account_ids.get("ACCT-MEGA-001", 1)

        # Pre-compute MegaMart locations once (not inside loop!)
        mega_locs = location_ids_by_account.get(mega_account_id, location_ids)

        for _ in range(200000):
            order_num = f"ORD-{self.base_year}-{order_id:07d}"
            self.order_ids[order_num] = order_id

            # 25% of orders go to MegaMart (hub concentration)
            if random.random() < 0.25:
                acct_id = mega_account_id
                # O(1) lookup replaces O(N) list comprehension
                loc_id = random.choice(mega_locs) if mega_locs else random.choice(location_ids)
            else:
                acct_id = random.choice(account_ids)
                # O(1) lookup replaces O(N) list comprehension
                acct_locs = location_ids_by_account.get(acct_id, location_ids)
                loc_id = random.choice(acct_locs) if acct_locs else random.choice(location_ids)

            # O(1) lookup replaces O(N) next() scan
            acct = accounts_idx.get(acct_id)
            channel_id = acct["channel_id"] if acct else random.choice(channel_ids)

            order_date = self.fake.date_between(start_date=date(self.base_year, 1, 1),
                                                end_date=date(self.base_year, 12, 15))
            lead_time = random.randint(2, 14)

            # Check if promotional order
            promo_id_val = None
            order_type = random.choices(order_types, weights=[70, 10, 10, 10])[0]
            if order_type == "promotional":
                # For promotional orders, just pick a random promo (simpler than date filtering)
                # This maintains promotional distribution while avoiding O(N) scan
                promo_id_val = random.choice(promo_ids) if promo_ids else None

            self.data["orders"].append({
                "id": order_id,
                "order_number": order_num,
                "retail_account_id": acct_id,
                "retail_location_id": loc_id,
                "channel_id": channel_id,
                "order_date": order_date,
                "requested_delivery_date": order_date + timedelta(days=lead_time),
                "promised_delivery_date": order_date + timedelta(days=lead_time + random.randint(-1, 3)),
                "actual_delivery_date": order_date + timedelta(days=lead_time + random.randint(-2, 5)) if random.random() > 0.2 else None,
                "status": random.choices(order_statuses, weights=[5, 10, 10, 10, 15, 45, 5])[0],
                "order_type": order_type,
                "promo_id": promo_id_val,
                "total_cases": None,  # Calculated from lines
                "total_amount": None,
                "currency": "USD",
                "notes": None,
                "created_at": now,
                "updated_at": now,
            })
            order_id += 1

        # --- REPLENISHMENT_PARAMS (~25,000: SKU × DC combinations) ---
        rp_id = 1
        for dc_id in dc_ids:
            for sku_id in random.sample(sku_ids, min(1000, len(sku_ids))):
                self.data["replenishment_params"].append({
                    "id": rp_id,
                    "sku_id": sku_id,
                    "location_type": "dc",
                    "location_id": dc_id,
                    "safety_stock_days": random.randint(7, 21),
                    "reorder_point": random.randint(50, 500),
                    "reorder_quantity": random.randint(100, 2000),
                    "max_stock": random.randint(1000, 10000),
                    "lead_time_days": random.randint(3, 14),
                    "review_period_days": random.choice([1, 7, 14]),
                    "service_level_target": round(random.uniform(0.95, 0.99), 2),
                    "created_at": now,
                    "updated_at": now,
                })
                rp_id += 1
                if rp_id > 25000:
                    break
            if rp_id > 25000:
                break

        # --- DEMAND_ALLOCATION (~50,000) ---
        for da_id in range(1, 50001):
            self.data["demand_allocation"].append({
                "id": da_id,
                "forecast_id": random.randint(1, min(100000, forecast_id - 1)),
                "sku_id": random.choice(sku_ids),
                "source_dc_id": random.choice(dc_ids),
                "destination_type": random.choice(["account", "dc", "location"]),
                "destination_id": random.randint(1, 100),
                "allocated_quantity": random.randint(10, 1000),
                "allocation_date": self.fake.date_between(start_date=date(self.base_year, 1, 1),
                                                          end_date=date(self.base_year, 12, 31)),
                "priority": random.randint(1, 10),
                "allocation_rule": random.choice(["fair_share", "priority", "historical", "committed"]),
                "status": random.choice(["pending", "confirmed", "released", "completed"]),
                "created_at": now,
                "updated_at": now,
            })

        # --- CAPACITY_PLANS (~10,000) ---
        for cp_id in range(1, 10001):
            self.data["capacity_plans"].append({
                "id": cp_id,
                "plan_code": f"CAP-{self.base_year}-{cp_id:05d}",
                "plant_id": random.choice(list(self.plant_ids.values())),
                "production_line_id": random.choice(list(self.production_line_ids.values())),
                "planning_period": self.fake.date_between(start_date=date(self.base_year, 1, 1),
                                                          end_date=date(self.base_year, 12, 31)),
                "available_hours": random.randint(100, 180),
                "planned_hours": random.randint(80, 160),
                "utilization_percent": round(random.uniform(60, 95), 1),
                "bottleneck_flag": random.random() < 0.1,
                "overtime_hours": random.randint(0, 40),
                "notes": None,
                "created_at": now,
                "updated_at": now,
            })

        self.generated_levels.add(8)
        level_elapsed = time.time() - level_start
        print(f"    Generated: {len(self.data['pos_sales'])} pos_sales, {len(self.data['orders'])} orders, "
              f"{len(self.data['demand_forecasts'])} forecasts")
        self._report_level_stats(8, level_elapsed)

    def _generate_level_9(self) -> None:
        """
        Level 9: Order lines and planning.

        Tables: order_lines, order_allocations, supply_plans,
                plan_exceptions, pick_waves

        Key patterns:
        - Order lines: Channel-based distribution (DTC: 1-4, B2M Large: 50-200)
        - Allocations: ATP for fulfilled orders, links to batches/DCs
        - Pick waves: Daily waves per DC (10-50 orders each)
        - Supply plans: Weekly SKU/destination plans
        - Plan exceptions: Gaps when demand > capacity
        """
        print("  Level 9: Order lines and planning...")
        now = datetime.now()

        # Get references
        sku_ids = list(self.sku_ids.values())
        dc_ids = list(self.dc_ids.values())
        plant_ids = list(self.plant_ids.values())
        supplier_ids = list(self.supplier_ids.values())

        # Build channel lookup: channel_id -> channel_type
        channel_type_by_id: dict[int, str] = {}
        for ch in self.data["channels"]:
            channel_type_by_id[ch["id"]] = ch["channel_type"]

        # Build SKU price lookup
        sku_price_by_id: dict[int, float] = {}
        for sku in self.data["skus"]:
            sku_price_by_id[sku["id"]] = float(sku["list_price"])

        # Create SKU popularity weights using Zipf (reuse pattern from Level 8)
        num_skus = len(sku_ids)
        zipf_weights_list = zipf_weights(num_skus, s=0.8)
        sku_weights = dict(zip(sku_ids, zipf_weights_list))

        # Lines per order by channel type (realistic B2B patterns)
        lines_per_order_range = {
            "dtc": (1, 4),           # Consumers buy few items
            "ecommerce": (3, 15),    # Mixed baskets
            "bm_distributor": (15, 80),   # Medium stores restocking
            "bm_large": (50, 200),        # MegaMart/big box restocking
        }

        # Order status to line status mapping
        order_to_line_status = {
            "pending": "open",
            "confirmed": "open",
            "allocated": "allocated",
            "picking": "allocated",
            "shipped": "shipped",
            "delivered": "shipped",
            "cancelled": "cancelled",
        }

        # =====================================================================
        # ORDER_LINES (~600K rows) - Phase 5 Vectorized Generation
        # =====================================================================
        print("    Generating order_lines (vectorized)...")

        # Build order arrays for vectorized generation
        n_orders = len(self.data["orders"])
        order_ids_arr = np.array([o["id"] for o in self.data["orders"]], dtype=np.int64)
        order_statuses_arr = np.array([o["status"] for o in self.data["orders"]])
        order_is_promo_arr = np.array([o["promo_id"] is not None for o in self.data["orders"]], dtype=bool)
        order_channel_ids = np.array([o["channel_id"] for o in self.data["orders"]], dtype=np.int64)

        # Map channel_id to channel_type for each order
        order_channel_types = np.array([
            channel_type_by_id.get(cid, "bm_distributor") for cid in order_channel_ids
        ])

        # Determine lines per order based on channel type (vectorized)
        lines_per_order = np.zeros(n_orders, dtype=np.int32)
        for ch_type, (min_l, max_l) in lines_per_order_range.items():
            mask = order_channel_types == ch_type
            count = mask.sum()
            if count > 0:
                lines_per_order[mask] = self.rng.integers(min_l, max_l + 1, size=count)
        # Default for any unmatched
        default_mask = lines_per_order == 0
        if default_mask.any():
            lines_per_order[default_mask] = self.rng.integers(5, 21, size=default_mask.sum())

        # Cap at number of SKUs available
        lines_per_order = np.minimum(lines_per_order, len(sku_ids))

        # Configure and run vectorized generator
        order_lines_gen = OrderLinesGenerator(seed=self.seed)
        order_lines_gen.configure(
            sku_ids=sku_ids,
            order_ids=order_ids_arr,
            sku_prices=sku_price_by_id,
        )

        # Generate all order lines vectorized
        order_lines_array = order_lines_gen.generate_for_orders(
            order_ids=order_ids_arr,
            lines_per_order=lines_per_order,
            order_statuses=order_statuses_arr,
            order_is_promo=order_is_promo_arr,
        )

        # Convert to dicts
        order_lines_dicts = structured_to_dicts(order_lines_array)
        self.data["order_lines"] = order_lines_dicts

        print(f"      Generated {len(order_lines_dicts):,} order_lines")

        # =====================================================================
        # ORDER_ALLOCATIONS (~350K rows)
        # =====================================================================
        print("    Generating order_allocations...")

        # Only allocate orders that are in allocation-worthy statuses
        allocatable_statuses = {"allocated", "picking", "shipped", "delivered"}

        # Get released batches for allocation (QC approved)
        released_batches = [b for b in self.data["batches"] if b["qc_status"] == "released"]
        batch_ids_list = [b["id"] for b in released_batches] if released_batches else [1]

        # Build O(1) lookup for order_lines by order_id (avoids O(N²) scan)
        order_lines_by_order = LookupBuilder.build(
            self.data["order_lines"], key_field="order_id"
        )

        allocation_id = 1
        allocation_count = 0

        for order in self.data["orders"]:
            if order["status"] not in allocatable_statuses:
                continue

            order_id = order["id"]

            # O(1) lookup instead of O(N) scan
            order_lines_for_order = order_lines_by_order.get(order_id, [])

            # Determine allocation status from order status
            if order["status"] == "delivered":
                alloc_status = "shipped"
            elif order["status"] == "shipped":
                alloc_status = "shipped"
            elif order["status"] == "picking":
                alloc_status = "picked"
            else:
                alloc_status = "allocated"

            for ol in order_lines_for_order:
                line_num = ol["line_number"]
                qty_cases = ol["quantity_cases"]

                # 70% single allocation, 30% split between 2-3 allocations
                if random.random() < 0.70:
                    # Single allocation
                    dc_id = random.choice(dc_ids)
                    batch_id = random.choice(batch_ids_list)

                    self.data["order_allocations"].append({
                        "id": allocation_id,
                        "order_id": order_id,
                        "order_line_number": line_num,
                        "dc_id": dc_id,
                        "batch_id": batch_id,
                        "allocated_cases": qty_cases,
                        "allocation_date": now - timedelta(days=random.randint(1, 30)),
                        "expiry_date": now + timedelta(days=random.randint(7, 30)),
                        "status": alloc_status,
                        "created_at": now,
                    })
                    allocation_id += 1
                    allocation_count += 1
                else:
                    # Split allocation (2-3 allocations)
                    num_splits = random.randint(2, 3)
                    remaining = qty_cases

                    for split_idx in range(num_splits):
                        if split_idx == num_splits - 1:
                            split_qty = remaining
                        else:
                            split_qty = random.randint(1, max(1, remaining - (num_splits - split_idx - 1)))
                            remaining -= split_qty

                        if split_qty <= 0:
                            continue

                        dc_id = random.choice(dc_ids)
                        batch_id = random.choice(batch_ids_list)

                        self.data["order_allocations"].append({
                            "id": allocation_id,
                            "order_id": order_id,
                            "order_line_number": line_num,
                            "dc_id": dc_id,
                            "batch_id": batch_id,
                            "allocated_cases": split_qty,
                            "allocation_date": now - timedelta(days=random.randint(1, 30)),
                            "expiry_date": now + timedelta(days=random.randint(7, 30)),
                            "status": alloc_status,
                            "created_at": now,
                        })
                        allocation_id += 1
                        allocation_count += 1

        print(f"      Generated {allocation_count:,} order_allocations")

        # =====================================================================
        # PICK_WAVES (~25K rows)
        # =====================================================================
        print("    Generating pick_waves...")

        wave_id = 1
        wave_types = ["standard", "rush", "replenishment"]
        wave_type_weights = [85, 10, 5]
        wave_statuses = ["planned", "released", "picking", "packing", "staged", "loaded", "completed"]
        wave_status_weights = [5, 5, 5, 5, 5, 5, 70]

        # Generate ~3 waves per DC per day for 300 operating days
        for dc_id in dc_ids:
            num_waves_for_dc = random.randint(800, 1200)  # ~3/day * 300 days

            for wave_idx in range(num_waves_for_dc):
                wave_num = f"WAVE-{dc_id:03d}-{self.base_year}-{wave_id:06d}"
                wave_type = random.choices(wave_types, weights=wave_type_weights)[0]
                wave_status = random.choices(wave_statuses, weights=wave_status_weights)[0]

                # Wave date spread across the year
                wave_date = self.fake.date_between(
                    start_date=date(self.base_year, 1, 1),
                    end_date=date(self.base_year, 12, 31)
                )

                # Orders per wave based on type
                if wave_type == "rush":
                    total_orders = random.randint(3, 10)
                elif wave_type == "replenishment":
                    total_orders = random.randint(20, 100)
                else:
                    total_orders = random.randint(10, 50)

                # Estimate lines and cases
                total_lines = total_orders * random.randint(5, 30)
                total_cases = total_lines * random.randint(5, 20)

                # Timing
                start_hour = random.randint(6, 18)
                duration_hours = random.uniform(1, 4)
                start_time = datetime.combine(wave_date, datetime.min.time()) + timedelta(hours=start_hour)
                end_time = start_time + timedelta(hours=duration_hours) if wave_status == "completed" else None

                self.pick_wave_ids[wave_num] = wave_id
                self.data["pick_waves"].append({
                    "id": wave_id,
                    "wave_number": wave_num,
                    "dc_id": dc_id,
                    "wave_date": wave_date,
                    "wave_type": wave_type,
                    "status": wave_status,
                    "total_orders": total_orders,
                    "total_lines": total_lines,
                    "total_cases": total_cases,
                    "start_time": start_time,
                    "end_time": end_time,
                    "created_at": now,
                    "updated_at": now,
                })
                wave_id += 1

        print(f"      Generated {wave_id - 1:,} pick_waves")

        # =====================================================================
        # SUPPLY_PLANS (~50K rows)
        # =====================================================================
        print("    Generating supply_plans...")

        plan_id = 1
        source_types = ["production", "procurement", "transfer"]
        source_type_weights = [70, 20, 10]
        plan_statuses = ["planned", "committed", "in_progress", "completed"]
        plan_status_weights = [40, 30, 20, 10]

        # Generate weekly plans for 52 weeks
        for week_num in range(1, 53):
            plan_version = f"{self.base_year}-W{week_num:02d}-STAT"
            week_start = date(self.base_year, 1, 1) + timedelta(weeks=week_num - 1)
            week_end = week_start + timedelta(days=6)

            # ~1000 SKU-destination combinations per week
            sampled_skus = random.sample(sku_ids, min(200, len(sku_ids)))
            sampled_dcs = random.sample(dc_ids, min(5, len(dc_ids)))

            for sku_id in sampled_skus:
                for dest_dc_id in sampled_dcs:
                    source_type = random.choices(source_types, weights=source_type_weights)[0]

                    # Determine source_id based on source_type
                    if source_type == "production":
                        source_id = random.choice(plant_ids)
                    elif source_type == "procurement":
                        source_id = random.choice(supplier_ids) if supplier_ids else 1
                    else:  # transfer
                        other_dcs = [d for d in dc_ids if d != dest_dc_id]
                        source_id = random.choice(other_dcs) if other_dcs else dest_dc_id

                    # Planned quantity based on demand forecasts
                    planned_qty = random.randint(100, 5000)
                    # Committed is 40-90% of planned
                    committed_qty = int(planned_qty * random.uniform(0.4, 0.9))

                    plan_status = random.choices(plan_statuses, weights=plan_status_weights)[0]

                    self.data["supply_plans"].append({
                        "id": plan_id,
                        "plan_version": plan_version,
                        "sku_id": sku_id,
                        "source_type": source_type,
                        "source_id": source_id,
                        "destination_type": "dc",
                        "destination_id": dest_dc_id,
                        "period_start": week_start,
                        "period_end": week_end,
                        "planned_quantity_cases": planned_qty,
                        "committed_quantity_cases": committed_qty,
                        "status": plan_status,
                        "created_at": now,
                        "updated_at": now,
                    })
                    plan_id += 1

                    # Limit to ~50K total
                    if plan_id > 50000:
                        break
                if plan_id > 50000:
                    break
            if plan_id > 50000:
                break

        print(f"      Generated {plan_id - 1:,} supply_plans")

        # =====================================================================
        # PLAN_EXCEPTIONS (~20K rows)
        # =====================================================================
        print("    Generating plan_exceptions...")

        exception_id = 1
        exception_types = [
            "demand_spike", "capacity_shortage", "material_shortage",
            "lead_time_violation", "inventory_excess", "supply_disruption"
        ]
        exception_type_weights = [40, 25, 15, 10, 7, 3]

        severities = ["low", "medium", "high", "critical"]
        severity_weights = [60, 25, 12, 3]

        exception_statuses = ["open", "acknowledged", "resolving", "resolved", "accepted"]
        exception_status_weights = [30, 20, 20, 20, 10]

        # Root causes and actions by exception type
        root_causes = {
            "demand_spike": ["Promotional lift exceeded forecast", "Competitor stockout", "Viral social media"],
            "capacity_shortage": ["Planned maintenance", "Equipment failure", "Labor shortage"],
            "material_shortage": ["Supplier delay", "Quality rejection", "Single-source constraint"],
            "lead_time_violation": ["Port congestion", "Customs delay", "Carrier capacity"],
            "inventory_excess": ["Forecast overestimate", "Promotion cancelled", "Seasonal slowdown"],
            "supply_disruption": ["Natural disaster", "Supplier bankruptcy", "Geopolitical event"],
        }

        recommended_actions = {
            "demand_spike": ["Expedite production", "Reallocate from other DCs", "Authorize overtime"],
            "capacity_shortage": ["Shift to alternate plant", "Use co-packer", "Delay non-critical orders"],
            "material_shortage": ["Qualify alternate supplier", "Use substitute ingredient", "Air freight"],
            "lead_time_violation": ["Switch to air freight", "Use backup carrier", "Adjust safety stock"],
            "inventory_excess": ["Run promotion", "Transfer to high-demand DC", "Donate before expiry"],
            "supply_disruption": ["Activate business continuity plan", "Source from alternate region", "Ration allocation"],
        }

        # Generate exceptions across plan versions
        for week_num in range(1, 53):
            plan_version = f"{self.base_year}-W{week_num:02d}-STAT"
            week_start = date(self.base_year, 1, 1) + timedelta(weeks=week_num - 1)
            week_end = week_start + timedelta(days=6)

            # ~400 exceptions per week on average
            num_exceptions = random.randint(300, 500)

            for _ in range(num_exceptions):
                exc_type = random.choices(exception_types, weights=exception_type_weights)[0]
                severity = random.choices(severities, weights=severity_weights)[0]
                exc_status = random.choices(exception_statuses, weights=exception_status_weights)[0]

                sku_id = random.choice(sku_ids) if random.random() > 0.1 else None
                dc_id = random.choice(dc_ids)

                # Gap calculation based on severity
                if severity == "critical":
                    gap_pct = round(random.uniform(50, 100), 2)
                    gap_qty = random.randint(5000, 20000)
                elif severity == "high":
                    gap_pct = round(random.uniform(25, 50), 2)
                    gap_qty = random.randint(2000, 5000)
                elif severity == "medium":
                    gap_pct = round(random.uniform(10, 25), 2)
                    gap_qty = random.randint(500, 2000)
                else:
                    gap_pct = round(random.uniform(1, 10), 2)
                    gap_qty = random.randint(100, 500)

                root_cause = random.choice(root_causes[exc_type])
                rec_action = random.choice(recommended_actions[exc_type])

                # Add special cases for named problem ingredients
                if exc_type == "material_shortage" and random.random() < 0.1:
                    root_cause = "Single-source Sorbitol (ING-SORB-001) supplier constraint"
                    severity = "high" if random.random() < 0.5 else "critical"
                elif exc_type == "lead_time_violation" and random.random() < 0.1:
                    root_cause = "Palm Oil (ING-PALM-001) extended lead time from Malaysia"
                    severity = "medium" if random.random() < 0.7 else "high"

                resolved_by = None
                resolved_at = None
                if exc_status in ("resolved", "accepted"):
                    resolved_by = self.fake.name()
                    resolved_at = now - timedelta(days=random.randint(1, 14))

                self.data["plan_exceptions"].append({
                    "id": exception_id,
                    "plan_version": plan_version,
                    "exception_type": exc_type,
                    "severity": severity,
                    "sku_id": sku_id,
                    "location_type": "dc",
                    "location_id": dc_id,
                    "period_start": week_start,
                    "period_end": week_end,
                    "gap_quantity_cases": gap_qty,
                    "gap_percent": gap_pct,
                    "root_cause": root_cause,
                    "recommended_action": rec_action,
                    "status": exc_status,
                    "resolved_by": resolved_by,
                    "resolved_at": resolved_at,
                    "created_at": now,
                    "updated_at": now,
                })
                exception_id += 1

                # Limit to ~20K total
                if exception_id > 20000:
                    break
            if exception_id > 20000:
                break

        print(f"      Generated {exception_id - 1:,} plan_exceptions")

        self.generated_levels.add(9)
        print(f"    Level 9 complete: {len(self.data['order_lines']):,} order_lines, "
              f"{len(self.data['order_allocations']):,} order_allocations, "
              f"{len(self.data['pick_waves']):,} pick_waves")

    def _generate_level_10(self) -> None:
        """
        Level 10: Shipments and legs.

        Tables: pick_wave_orders, shipments, shipment_legs
        """
        print("  Level 10: Shipments and legs...")
        # TODO: Implement in Step 6
        self.generated_levels.add(10)

    def _generate_level_11(self) -> None:
        """
        Level 11: Shipment lines with batch tracking.

        Tables: shipment_lines
        """
        print("  Level 11: Shipment lines...")
        # TODO: Implement in Step 6
        self.generated_levels.add(11)

    def _generate_level_12(self) -> None:
        """
        Level 12: Returns.

        Tables: rma_authorizations, returns, return_lines
        """
        print("  Level 12: Returns...")
        # TODO: Implement in Step 7
        self.generated_levels.add(12)

    def _generate_level_13(self) -> None:
        """
        Level 13: Disposition.

        Tables: disposition_logs
        """
        print("  Level 13: Disposition logs...")
        # TODO: Implement in Step 7
        self.generated_levels.add(13)

    def _generate_level_14(self) -> None:
        """
        Level 14: Monitoring and KPIs (Leaf).

        Tables: kpi_actuals, osa_metrics, risk_events, audit_log
        """
        print("  Level 14: Monitoring (KPIs, OSA, risk_events...)")
        # TODO: Implement in Step 7
        self.generated_levels.add(14)

    # =========================================================================
    # Generation Control
    # =========================================================================

    def generate_all(self) -> None:
        """
        Generate all data in dependency order (levels 0-14).

        Phase 5: Includes performance tracking and inline realism monitoring.
        """
        print("=" * 60)
        print("Prism Consumer Goods - FMCG Data Generation")
        print("=" * 60)
        print(f"Seed: {self.seed}")
        print(f"Target: ~{sum(TARGET_ROW_COUNTS.values()):,} rows across 67 tables")
        print()
        print("Generating levels 0-14...")
        print()

        gen_start = time.time()
        self.generate_from_level(0)
        gen_elapsed = time.time() - gen_start

        print()
        print("=" * 60)
        print("Generation Summary")
        print("=" * 60)
        total_rows = sum(len(rows) for rows in self.data.values())
        rows_per_sec = total_rows / gen_elapsed if gen_elapsed > 0 else 0
        print(f"Total rows: {total_rows:,}")
        print(f"Total time: {gen_elapsed:.2f}s ({rows_per_sec:,.0f} rows/sec)")

        # Phase 5: Performance breakdown by level
        if self._level_times:
            print()
            print("Level Performance:")
            for level in sorted(self._level_times.keys()):
                t = self._level_times[level]
                r = self._level_rows.get(level, 0)
                rps = r / t if t > 0 else 0
                print(f"  Level {level:2d}: {t:6.2f}s - {r:8,} rows ({rps:,.0f}/sec)")

        # Phase 5: Inline realism monitoring report
        if self.realism_monitor:
            report = self.realism_monitor.get_reality_report()
            if not report["is_realistic"]:
                print()
                print("WARNING: Realism violations detected:")
                for violation in report["violations"][:5]:  # Show first 5
                    print(f"  - {violation}")

    def generate_from_level(self, start_level: int) -> None:
        """
        Generate (or regenerate) from a specific level through level 14.

        This enables cascade regeneration for iteration:
        - If Level 8 (orders) needs tuning, regenerate 8-14
        - If only Level 14 (KPIs) needs tuning, regenerate just 14

        Args:
            start_level: Level to start generation from (0-14)
        """
        if start_level < 0 or start_level > 14:
            raise ValueError(f"start_level must be 0-14, got {start_level}")

        # If regenerating, clear affected levels
        if start_level > 0:
            print(f"Regenerating levels {start_level}-14 (cascade)...")
            self._clear_levels(start_level, 14)

        # Generate each level in order
        generators = [
            self._generate_level_0,
            self._generate_level_1,
            self._generate_level_2,
            self._generate_level_3,
            self._generate_level_4,
            self._generate_level_5,
            self._generate_level_6,
            self._generate_level_7,
            self._generate_level_8,
            self._generate_level_9,
            self._generate_level_10,
            self._generate_level_11,
            self._generate_level_12,
            self._generate_level_13,
            self._generate_level_14,
        ]

        for level in range(start_level, 15):
            generators[level]()

    def _clear_levels(self, start: int, end: int) -> None:
        """Clear data for specified levels (for regeneration)."""
        # Map levels to tables (simplified - full mapping in implementation)
        level_tables = {
            0: ["divisions", "channels", "products", "packaging_types", "ports",
                "carriers", "emission_factors", "kpi_thresholds", "business_rules",
                "ingredients"],
            1: ["suppliers", "plants", "production_lines", "carrier_contracts",
                "route_segments"],
            2: ["supplier_ingredients", "certifications", "formulas",
                "formula_ingredients", "carrier_rates", "routes",
                "route_segment_assignments"],
            3: ["retail_accounts", "retail_locations", "distribution_centers"],
            4: ["skus", "sku_costs", "sku_substitutes", "promotions",
                "promotion_skus", "promotion_accounts"],
            5: ["purchase_orders", "goods_receipts", "work_orders",
                "supplier_esg_scores", "sustainability_targets",
                "modal_shift_opportunities"],
            6: ["purchase_order_lines", "goods_receipt_lines",
                "work_order_materials", "batches", "batch_cost_ledger"],
            7: ["batch_ingredients", "inventory"],
            8: ["pos_sales", "demand_forecasts", "forecast_accuracy",
                "consensus_adjustments", "orders", "replenishment_params",
                "demand_allocation", "capacity_plans"],
            9: ["order_lines", "order_allocations", "supply_plans",
                "plan_exceptions", "pick_waves"],
            10: ["pick_wave_orders", "shipments", "shipment_legs"],
            11: ["shipment_lines"],
            12: ["rma_authorizations", "returns", "return_lines"],
            13: ["disposition_logs"],
            14: ["kpi_actuals", "osa_metrics", "risk_events", "audit_log"],
        }

        for level in range(start, end + 1):
            for table in level_tables.get(level, []):
                self.data[table] = []
            self.generated_levels.discard(level)

    # =========================================================================
    # Validation Suite (Step 8)
    # =========================================================================

    def validate_realism(self) -> dict[str, tuple[bool, str]]:
        """
        Validate generated data meets realism requirements.

        Returns dict of {check_name: (passed, message)}
        """
        print()
        print("=" * 60)
        print("Validation Suite")
        print("=" * 60)

        results = {}

        # Row count validation
        results["row_counts"] = self._validate_row_counts()

        # Pareto validation (80/20 rule)
        results["pareto"] = self._validate_pareto()

        # Hub concentration (MegaMart)
        results["hub_concentration"] = self._validate_hub_concentration()

        # Named entities present
        results["named_entities"] = self._validate_named_entities()

        # SPOF ingredients
        results["spof"] = self._validate_spof()

        # Promo hangover effect
        results["promo_hangover"] = self._validate_promo_hangover()

        # Referential integrity
        results["referential_integrity"] = self._validate_referential_integrity()

        # Print summary
        print()
        print("-" * 40)
        passed = sum(1 for p, _ in results.values() if p)
        total = len(results)
        print(f"Validation: {passed}/{total} checks passed")

        for name, (ok, msg) in results.items():
            status = "✓" if ok else "✗"
            print(f"  {status} {name}: {msg}")

        return results

    def _validate_row_counts(self) -> tuple[bool, str]:
        """Check row counts are within ±10% of targets."""
        total = sum(len(rows) for rows in self.data.values())
        target = sum(TARGET_ROW_COUNTS.values())
        pct_diff = abs(total - target) / target * 100

        if pct_diff <= 10:
            return True, f"{total:,} rows (target: {target:,}, diff: {pct_diff:.1f}%)"
        return False, f"{total:,} rows (target: {target:,}, diff: {pct_diff:.1f}% > 10%)"

    def _validate_pareto(self) -> tuple[bool, str]:
        """Check top 20% SKUs = 75-85% of order volume."""
        order_lines = self.data.get("order_lines", [])
        if not order_lines:
            return False, "No order_lines data"

        # Count quantity by SKU
        sku_qty = Counter()
        for line in order_lines:
            sku_qty[line.get("sku_id")] += line.get("quantity", 0)

        if not sku_qty:
            return False, "No SKU quantities"

        # Sort by quantity descending
        sorted_skus = sorted(sku_qty.items(), key=lambda x: x[1], reverse=True)
        total_qty = sum(q for _, q in sorted_skus)

        # Top 20%
        top_n = max(1, len(sorted_skus) // 5)
        top_qty = sum(q for _, q in sorted_skus[:top_n])
        top_pct = top_qty / total_qty * 100 if total_qty > 0 else 0

        if 75 <= top_pct <= 85:
            return True, f"Top 20% SKUs = {top_pct:.1f}% volume"
        return False, f"Top 20% SKUs = {top_pct:.1f}% (target: 75-85%)"

    def _validate_hub_concentration(self) -> tuple[bool, str]:
        """Check MegaMart (ACCT-MEGA-001) has 20-30% of orders."""
        orders = self.data.get("orders", [])
        if not orders:
            return False, "No orders data"

        mega_id = self.retail_account_ids.get("ACCT-MEGA-001")
        if not mega_id:
            return False, "ACCT-MEGA-001 not found"

        mega_orders = sum(1 for o in orders if o.get("retail_account_id") == mega_id)
        pct = mega_orders / len(orders) * 100 if orders else 0

        if 20 <= pct <= 30:
            return True, f"MegaMart: {pct:.1f}% of orders"
        return False, f"MegaMart: {pct:.1f}% (target: 20-30%)"

    def _validate_named_entities(self) -> tuple[bool, str]:
        """Check all 9 named entities exist in their tables."""
        missing = []

        # Check batches
        if "B-2024-RECALL-001" not in self.batch_ids:
            missing.append("B-2024-RECALL-001")

        # Check accounts
        if "ACCT-MEGA-001" not in self.retail_account_ids:
            missing.append("ACCT-MEGA-001")

        # Check suppliers
        if "SUP-PALM-MY-001" not in self.supplier_ids:
            missing.append("SUP-PALM-MY-001")

        # Check DCs
        if "DC-NAM-CHI-001" not in self.dc_ids:
            missing.append("DC-NAM-CHI-001")

        # Check promotions
        if "PROMO-BF-2024" not in self.promotion_ids:
            missing.append("PROMO-BF-2024")

        # Check route segments
        if "LANE-SH-LA-001" not in self.route_segment_ids:
            missing.append("LANE-SH-LA-001")

        # Check ingredients
        for ing in ["ING-PALM-001", "ING-SORB-001", "ING-PEPP-001"]:
            if ing not in self.ingredient_ids:
                missing.append(ing)

        if not missing:
            return True, "All 9 named entities present"
        return False, f"Missing: {', '.join(missing)}"

    def _validate_spof(self) -> tuple[bool, str]:
        """Check ING-SORB-001 and ING-PALM-001 are single-source."""
        supplier_ings = self.data.get("supplier_ingredients", [])
        if not supplier_ings:
            return False, "No supplier_ingredients data"

        # Count suppliers per ingredient
        ing_suppliers = Counter()
        for si in supplier_ings:
            ing_suppliers[si.get("ingredient_id")] += 1

        spof_ings = []
        for code in ["ING-SORB-001", "ING-PALM-001"]:
            ing_id = self.ingredient_ids.get(code)
            if ing_id and ing_suppliers.get(ing_id, 0) == 1:
                spof_ings.append(code)

        if len(spof_ings) >= 2:
            return True, f"SPOFs found: {', '.join(spof_ings)}"
        return False, f"Expected 2 SPOFs, found: {spof_ings}"

    def _validate_promo_hangover(self) -> tuple[bool, str]:
        """Check Black Friday shows lift in week 47 and dip in week 48."""
        pos = self.data.get("pos_sales", [])
        if not pos:
            return False, "No pos_sales data"

        # Group by week
        week_sales = Counter()
        for sale in pos:
            sale_date = sale.get("sale_date")
            if sale_date:
                week = sale_date.isocalendar()[1] if hasattr(sale_date, "isocalendar") else 1
                week_sales[week] += sale.get("quantity", 0)

        if not week_sales:
            return False, "No weekly sales data"

        avg_qty = sum(week_sales.values()) / len(week_sales)
        w47 = week_sales.get(47, 0)
        w48 = week_sales.get(48, 0)

        # Week 47 should be 2.5-3.5x average (Black Friday lift)
        # Week 48 should be 0.5-0.75x average (hangover)
        w47_ratio = w47 / avg_qty if avg_qty > 0 else 0
        w48_ratio = w48 / avg_qty if avg_qty > 0 else 0

        if 2.0 <= w47_ratio <= 4.0 and 0.4 <= w48_ratio <= 0.9:
            return True, f"W47: {w47_ratio:.1f}x, W48: {w48_ratio:.1f}x"
        return False, f"W47: {w47_ratio:.1f}x (exp 2.5-3.5x), W48: {w48_ratio:.1f}x (exp 0.5-0.75x)"

    def _validate_referential_integrity(self) -> tuple[bool, str]:
        """Spot-check FK validity (sample-based for speed)."""
        errors = []

        # Check order_lines -> orders
        order_lines = self.data.get("order_lines", [])
        order_id_set = {o.get("id") for o in self.data.get("orders", [])}
        if order_lines:
            sample = order_lines[:1000]  # Sample first 1000
            bad = [ol for ol in sample if ol.get("order_id") not in order_id_set]
            if bad:
                errors.append(f"order_lines: {len(bad)} invalid order_id refs")

        # Check shipment_lines -> shipments
        shipment_lines = self.data.get("shipment_lines", [])
        shipment_id_set = {s.get("id") for s in self.data.get("shipments", [])}
        if shipment_lines:
            sample = shipment_lines[:1000]
            bad = [sl for sl in sample if sl.get("shipment_id") not in shipment_id_set]
            if bad:
                errors.append(f"shipment_lines: {len(bad)} invalid shipment_id refs")

        if not errors:
            return True, "FK spot-checks passed"
        return False, "; ".join(errors)

    # =========================================================================
    # SQL Output
    # =========================================================================

    def write_sql(self, output_path: Path = OUTPUT_PATH) -> None:
        """
        Write generated data to SQL file using COPY format.

        Phase 5: Uses StreamingWriter for efficient buffered output with
        progress reporting.
        """
        print()
        print(f"Writing SQL to {output_path}...")
        write_start = time.time()

        total_rows = sum(len(rows) for rows in self.data.values())
        rows_written = 0

        with open(output_path, "w") as f:
            # Header
            f.write("-- ============================================\n")
            f.write("-- Prism Consumer Goods - FMCG Seed Data\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n")
            f.write(f"-- Seed: {self.seed}\n")
            f.write(f"-- Total rows: {total_rows:,}\n")
            f.write("-- ============================================\n\n")

            # Disable triggers for bulk load
            f.write("SET session_replication_role = replica;\n\n")

            # Write each table's data with progress reporting
            table_count = len([t for t, rows in self.data.items() if rows])
            tables_written = 0

            for table_name, rows in self.data.items():
                if not rows:
                    continue
                self._write_table_copy(f, table_name, rows)
                rows_written += len(rows)
                tables_written += 1

                # Progress every 10 tables
                if tables_written % 10 == 0:
                    pct = rows_written / total_rows * 100
                    print(f"    Writing... {pct:.0f}% ({tables_written}/{table_count} tables)")

            # Re-enable triggers
            f.write("\nSET session_replication_role = DEFAULT;\n")

            # Update sequences
            f.write("\n-- Update sequences\n")
            for table_name, rows in self.data.items():
                if rows and "id" in rows[0]:
                    max_id = max(r.get("id", 0) for r in rows)
                    f.write(f"SELECT setval('{table_name}_id_seq', {max_id});\n")

        write_elapsed = time.time() - write_start
        rows_per_sec = total_rows / write_elapsed if write_elapsed > 0 else 0
        print(f"Done. {total_rows:,} rows written in {write_elapsed:.2f}s ({rows_per_sec:,.0f} rows/sec)")

    def _write_table_copy(self, f, table_name: str, rows: list[dict]) -> None:
        """Write a table's data using COPY format."""
        if not rows:
            return

        # Get columns from first row
        columns = list(rows[0].keys())

        f.write(f"\n-- {table_name}: {len(rows):,} rows\n")
        f.write(f"COPY {table_name} ({', '.join(columns)}) FROM stdin;\n")

        for row in rows:
            values = []
            for col in columns:
                val = row.get(col)
                if val is None:
                    values.append("\\N")
                elif isinstance(val, bool):
                    values.append("t" if val else "f")
                elif isinstance(val, (date, datetime)):
                    values.append(val.isoformat())
                elif isinstance(val, str):
                    # Escape tabs, newlines, backslashes
                    values.append(val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n"))
                else:
                    values.append(str(val))
            f.write("\t".join(values) + "\n")

        f.write("\\.\n")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic FMCG supply chain data for Prism Consumer Goods.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full generation + validation (no file write)
  python generate_data.py --validate-only

  # Full generation + write seed.sql
  python generate_data.py

  # Regenerate from specific level (cascade)
  python generate_data.py --from-level 8 --validate-only

  # Custom output path
  python generate_data.py --output /tmp/seed.sql

  # Different random seed
  python generate_data.py --seed 123
""",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Generate and validate data without writing SQL file",
    )

    parser.add_argument(
        "--from-level",
        type=int,
        choices=range(0, 15),
        metavar="N",
        help="Regenerate from level N through 14 (cascade). Requires prior generation.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output path for seed.sql (default: {OUTPUT_PATH})",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help=f"Random seed for reproducibility (default: {RANDOM_SEED})",
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation checks after generation",
    )

    return parser.parse_args()


def main() -> int:
    """
    Generate FMCG data with CLI interface.

    Returns:
        0 on success, 1 on validation failure
    """
    args = parse_args()

    # Create generator
    generator = FMCGDataGenerator(seed=args.seed)

    # Generate data
    if args.from_level is not None:
        # Cascade regeneration from specific level
        if not generator.generated_levels:
            print("Warning: No prior generation found. Running full generation.")
            generator.generate_all()
        else:
            generator.generate_from_level(args.from_level)
    else:
        # Full generation
        generator.generate_all()

    # Run validation
    if not args.skip_validation:
        results = generator.validate_realism()
        all_passed = all(passed for passed, _ in results.values())
    else:
        all_passed = True
        print("\nValidation skipped.")

    # Write SQL if not validate-only
    if not args.validate_only:
        generator.write_sql(args.output)
        print(f"\nOutput: {args.output}")

    # Return status
    if all_passed:
        print("\nSuccess!")
        return 0
    else:
        print("\nValidation failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
