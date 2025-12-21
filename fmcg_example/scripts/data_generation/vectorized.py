"""
Vectorized Generators - NumPy-based generation for high-volume FMCG tables.

Uses NumPy structured arrays and vectorized operations to generate
high-volume tables (POS sales, order lines, shipment legs) efficiently.

Key Techniques:
- Structured arrays: Contiguous memory, direct COPY output
- Vectorized choice: rng.choice(p=weights) for Zipf/Pareto
- Vectorized dates: numpy.datetime64 arithmetic
- Batch generation: Process 10K-100K rows at a time

Target Tables:
- pos_sales (~500K rows): Highest volume, Zipf SKU distribution
- order_lines (~600K rows): Zipf SKU selection, Poisson quantities
- shipment_legs (~180K rows): Vectorized delay calculation

Usage:
    from data_generation.vectorized import POSSalesGenerator, OrderLinesGenerator

    # Generate POS sales
    gen = POSSalesGenerator(seed=42)
    gen.configure(sku_ids=sku_ids, location_ids=loc_ids, sku_weights=weights)
    for batch in gen.generate_batches(total_rows=500000, batch_size=50000):
        monitor.observe_batch("demand", "pos_sales", batch)
        writer.write_batch("pos_sales", batch_to_dicts(batch), POS_SALES_COLUMNS)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Iterator

import numpy as np
from numpy.random import Generator

from .realism_monitor import StochasticMode

# Import PromoCalendar for type hints (avoid circular import with TYPE_CHECKING)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .promo_calendar import PromoCalendar


# =============================================================================
# Structured Array Dtypes
# =============================================================================

POS_SALES_DTYPE = np.dtype([
    ("id", "i8"),
    ("retail_location_id", "i8"),
    ("sku_id", "i8"),
    ("sale_date", "datetime64[D]"),
    # sale_week is GENERATED ALWAYS - don't insert
    ("quantity_eaches", "i4"),
    ("quantity_cases", "f4"),
    ("revenue", "f8"),
    ("currency", "U3"),
    ("is_promotional", "?"),
    ("promo_id", "i8"),  # 0 for no promo
    ("created_at", "datetime64[s]"),
])

ORDER_LINES_DTYPE = np.dtype([
    # Note: order_lines uses composite PK (order_id, line_number), no separate id
    ("order_id", "i8"),
    ("line_number", "i4"),
    ("sku_id", "i8"),
    ("quantity_cases", "i4"),
    # quantity_eaches and line_amount are GENERATED ALWAYS - don't insert
    ("unit_price", "f4"),
    ("discount_percent", "f4"),
    ("status", "U12"),
    ("created_at", "datetime64[s]"),
])

SHIPMENT_LEGS_DTYPE = np.dtype([
    ("id", "i8"),
    ("shipment_id", "i8"),
    ("route_segment_id", "i8"),
    ("leg_sequence", "i4"),
    ("transport_mode", "U10"),
    ("carrier_id", "i8"),
    ("planned_departure", "datetime64[h]"),
    ("planned_arrival", "datetime64[h]"),
    ("actual_departure", "datetime64[h]"),
    ("actual_arrival", "datetime64[h]"),
    ("delay_hours", "f4"),
    ("status", "U12"),
])

SHIPMENT_LINES_DTYPE = np.dtype([
    # Note: shipment_lines uses composite PK (shipment_id, line_number), no separate id
    ("shipment_id", "i8"),
    ("line_number", "i4"),
    ("sku_id", "i8"),
    ("batch_id", "i8"),
    ("quantity_cases", "i4"),
    ("quantity_eaches", "i4"),
    ("batch_fraction", "f4"),
    ("weight_kg", "f4"),
    ("lot_number", "U20"),
    ("expiry_date", "datetime64[D]"),
    ("created_at", "datetime64[s]"),
])

SHIPMENT_LINES_COLUMNS = [
    "shipment_id", "line_number", "sku_id", "batch_id",
    "quantity_cases", "quantity_eaches", "batch_fraction", "weight_kg",
    "lot_number", "expiry_date", "created_at",
]


# =============================================================================
# Distribution Helpers
# =============================================================================

def zipf_weights(n: int, alpha: float = 1.05) -> np.ndarray:
    """
    Generate Zipf-distributed weights for Pareto selection.

    Args:
        n: Number of items
        alpha: Zipf exponent (1.05 gives roughly 80/20 split)

    Returns:
        Normalized probability weights summing to 1.0
    """
    ranks = np.arange(1, n + 1, dtype=np.float64)
    weights = 1.0 / np.power(ranks, alpha)
    return weights / weights.sum()


def lumpy_demand(
    rng: Generator,
    size: int,
    base_mean: float = 10.0,
    cv: float = 0.4,
) -> np.ndarray:
    """
    Generate lumpy demand quantities with controlled coefficient of variation.

    Uses negative binomial distribution for realistic demand lumpiness.

    Args:
        rng: NumPy random generator
        size: Number of samples
        base_mean: Mean demand quantity
        cv: Coefficient of variation (std/mean)

    Returns:
        Array of integer demand quantities
    """
    # Negative binomial parameterization
    # variance = mean + mean^2/r, so r = mean^2 / (variance - mean)
    variance = (cv * base_mean) ** 2
    if variance <= base_mean:
        # Fall back to Poisson if CV too low
        return rng.poisson(base_mean, size=size)

    r = base_mean ** 2 / (variance - base_mean)
    p = r / (r + base_mean)
    return rng.negative_binomial(r, p, size=size)


def apply_promo_effects(
    quantities: np.ndarray,
    is_promo: np.ndarray,
    promo_week_mask: np.ndarray,
    lift_multiplier: float = 2.5,
    hangover_multiplier: float = 0.7,
) -> np.ndarray:
    """
    Apply promotional lift and post-promo hangover to demand.

    Args:
        quantities: Base demand quantities
        is_promo: Boolean mask for promotional items
        promo_week_mask: 0=normal, 1=promo week, 2=hangover week
        lift_multiplier: Demand multiplier during promo (default 2.5x)
        hangover_multiplier: Demand multiplier post-promo (default 0.7x)

    Returns:
        Adjusted quantities with promo effects
    """
    result = quantities.astype(np.float32).copy()

    # Promo lift
    promo_mask = is_promo & (promo_week_mask == 1)
    result[promo_mask] *= lift_multiplier

    # Hangover effect
    hangover_mask = is_promo & (promo_week_mask == 2)
    result[hangover_mask] *= hangover_multiplier

    return np.maximum(result, 1).astype(np.int32)


# =============================================================================
# Base Generator Class
# =============================================================================

@dataclass
class VectorizedGenerator:
    """Base class for vectorized generators."""

    seed: int = 42
    rng: Generator = field(init=False)
    stochastic_mode: StochasticMode = StochasticMode.NORMAL
    _next_id: int = 1

    def __post_init__(self):
        self.rng = np.random.default_rng(self.seed)

    def reset(self, seed: int | None = None) -> None:
        """Reset generator state."""
        if seed is not None:
            self.seed = seed
        self.rng = np.random.default_rng(self.seed)
        self._next_id = 1

    def set_stochastic_mode(self, mode: StochasticMode) -> None:
        """Set stochastic mode for disruption scenarios."""
        self.stochastic_mode = mode


# =============================================================================
# POS Sales Generator
# =============================================================================

@dataclass
class POSSalesGenerator(VectorizedGenerator):
    """
    Vectorized generator for POS sales (~500K rows).

    Generates point-of-sale data with:
    - Zipf-distributed SKU selection (80/20 Pareto)
    - Lumpy demand with promotional effects
    - Weekly seasonality
    - Promo lift and hangover
    """

    # Configuration (set via configure())
    sku_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    location_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    sku_weights: np.ndarray | None = None
    sku_prices: dict[int, float] = field(default_factory=dict)

    # Multi-promo calendar for per-(week, account, sku) promo effects
    promo_calendar: "PromoCalendar | None" = None

    # Generation parameters
    base_year: int = 2024
    weeks_per_year: int = 52
    zipf_alpha: float = 1.05
    base_demand_mean: float = 8.0
    demand_cv: float = 0.4

    def configure(
        self,
        sku_ids: list[int] | np.ndarray,
        location_ids: list[int] | np.ndarray,
        sku_weights: np.ndarray | None = None,
        sku_prices: dict[int, float] | None = None,
        promo_calendar: "PromoCalendar | None" = None,
    ) -> "POSSalesGenerator":
        """
        Configure generator with SKU and location data.

        Args:
            sku_ids: Array of valid SKU IDs
            location_ids: Array of valid location IDs
            sku_weights: Optional pre-computed Zipf weights
            sku_prices: Optional dict mapping SKU ID to unit price
            promo_calendar: PromoCalendar for multi-promo effects

        Returns:
            Self for method chaining
        """
        self.sku_ids = np.asarray(sku_ids, dtype=np.int64)
        self.location_ids = np.asarray(location_ids, dtype=np.int64)

        if sku_weights is not None:
            self.sku_weights = np.asarray(sku_weights, dtype=np.float64)
        else:
            self.sku_weights = zipf_weights(len(self.sku_ids), self.zipf_alpha)

        self.sku_prices = sku_prices or {}
        self.promo_calendar = promo_calendar

        return self

    def generate_batch(self, batch_size: int) -> np.ndarray:
        """
        Generate a batch of POS sales records.

        Args:
            batch_size: Number of records to generate

        Returns:
            Structured NumPy array with POS_SALES_DTYPE
        """
        batch = np.zeros(batch_size, dtype=POS_SALES_DTYPE)

        # IDs
        batch["id"] = np.arange(self._next_id, self._next_id + batch_size)
        self._next_id += batch_size

        # Random locations (uniform)
        batch["retail_location_id"] = self.rng.choice(
            self.location_ids, size=batch_size
        )

        # Zipf-weighted SKU selection
        sku_indices = self.rng.choice(
            len(self.sku_ids), size=batch_size, p=self.sku_weights
        )
        batch["sku_id"] = self.sku_ids[sku_indices]

        # Random weeks and dates
        weeks = self.rng.integers(1, self.weeks_per_year + 1, size=batch_size)
        # sale_week is GENERATED ALWAYS in DB - don't set it

        # Convert weeks to dates (Monday of each week + random day offset)
        base_date = np.datetime64(f"{self.base_year}-01-01", "D")
        week_starts = base_date + (weeks - 1).astype("timedelta64[W]")
        day_offsets = self.rng.integers(0, 7, size=batch_size).astype("timedelta64[D]")
        batch["sale_date"] = week_starts + day_offsets

        # Generate base lumpy demand (quantity_eaches)
        base_quantities = lumpy_demand(
            self.rng, batch_size, self.base_demand_mean, self.demand_cv
        )

        # Apply promo effects from calendar
        if self.promo_calendar is not None:
            lifts, hangovers, is_promo, promo_ids = (
                self.promo_calendar.get_effects_vectorized(
                    weeks,
                    batch["sku_id"],
                    batch["retail_location_id"],
                )
            )

            # Apply lift and hangover effects to base quantities
            quantity_eaches = (base_quantities * lifts * hangovers).astype(np.int32)
            quantity_eaches = np.maximum(quantity_eaches, 1)

            batch["is_promotional"] = is_promo
            batch["promo_id"] = promo_ids
        else:
            # No promo calendar - no promo effects
            quantity_eaches = base_quantities.astype(np.int32)
            batch["is_promotional"] = False
            batch["promo_id"] = 0

        batch["quantity_eaches"] = quantity_eaches

        # quantity_cases = quantity_eaches / 12
        batch["quantity_cases"] = (quantity_eaches / 12.0).astype(np.float32)

        # Prices (default $5.99 if not in dict)
        prices = np.array([
            self.sku_prices.get(sku, 5.99) for sku in batch["sku_id"]
        ], dtype=np.float32)

        # Apply promotional discount (25% off)
        prices = np.where(batch["is_promotional"], prices * 0.75, prices)

        # Revenue = quantity_eaches * price
        batch["revenue"] = (quantity_eaches * prices).astype(np.float64)

        # Currency is always USD
        batch["currency"] = "USD"

        # created_at timestamp
        batch["created_at"] = np.datetime64("now", "s")

        return batch

    def generate_batches(
        self,
        total_rows: int,
        batch_size: int = 50000,
    ) -> Iterator[np.ndarray]:
        """
        Generate POS sales in batches.

        Args:
            total_rows: Total number of rows to generate
            batch_size: Rows per batch

        Yields:
            Structured NumPy arrays
        """
        remaining = total_rows
        while remaining > 0:
            size = min(batch_size, remaining)
            yield self.generate_batch(size)
            remaining -= size


# =============================================================================
# Order Lines Generator
# =============================================================================

@dataclass
class OrderLinesGenerator(VectorizedGenerator):
    """
    Vectorized generator for order lines (~600K rows).

    Generates order line items with:
    - Zipf-distributed SKU selection
    - Poisson-distributed quantities
    - Channel-based line count distribution
    """

    # Configuration
    sku_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    sku_weights: np.ndarray | None = None
    sku_prices: dict[int, float] = field(default_factory=dict)
    order_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    order_channels: dict[int, str] = field(default_factory=dict)  # order_id -> channel

    # Generation parameters
    zipf_alpha: float = 1.05
    quantity_mean: int = 12
    quantity_cv: float = 0.8  # High CV for Bullwhip Effect (0.8 > 0.67 POS CV)
    promo_lift_multiplier: float = 3.0  # Forward buying effect
    discount_rate: float = 0.05

    def configure(
        self,
        sku_ids: list[int] | np.ndarray,
        order_ids: list[int] | np.ndarray,
        sku_weights: np.ndarray | None = None,
        sku_prices: dict[int, float] | None = None,
        order_channels: dict[int, str] | None = None,
    ) -> "OrderLinesGenerator":
        """Configure generator with SKU and order data."""
        self.sku_ids = np.asarray(sku_ids, dtype=np.int64)
        self.order_ids = np.asarray(order_ids, dtype=np.int64)

        if sku_weights is not None:
            self.sku_weights = np.asarray(sku_weights, dtype=np.float64)
        else:
            self.sku_weights = zipf_weights(len(self.sku_ids), self.zipf_alpha)

        self.sku_prices = sku_prices or {}
        self.order_channels = order_channels or {}

        return self

    def generate_for_orders(
        self,
        order_ids: np.ndarray,
        lines_per_order: np.ndarray,
        order_statuses: np.ndarray | None = None,
        order_is_promo: np.ndarray | None = None,
        order_channels: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Generate order lines for a batch of orders.

        Args:
            order_ids: Array of order IDs
            lines_per_order: Array of line counts per order
            order_statuses: Optional array of order statuses (mapped to line status)
            order_is_promo: Optional boolean array for promotional orders
            order_channels: Optional array of channel types for quantity scaling

        Returns:
            Structured NumPy array with ORDER_LINES_DTYPE
        """
        total_lines = int(lines_per_order.sum())
        batch = np.zeros(total_lines, dtype=ORDER_LINES_DTYPE)

        # Expand order IDs to match line counts
        batch["order_id"] = np.repeat(order_ids, lines_per_order)

        # Line numbers within each order (1, 2, 3, ... per order)
        line_nums = []
        for count in lines_per_order:
            line_nums.extend(range(1, int(count) + 1))
        batch["line_number"] = np.array(line_nums, dtype=np.int32)

        # Zipf-weighted SKU selection
        sku_indices = self.rng.choice(
            len(self.sku_ids), size=total_lines, p=self.sku_weights
        )
        batch["sku_id"] = self.sku_ids[sku_indices]

        # Quantity cases - Lumpy demand for Bullwhip Effect
        # Use lumpy_demand instead of poisson to achieve higher CV
        quantities = lumpy_demand(
            self.rng,
            size=total_lines,
            base_mean=float(self.quantity_mean),
            cv=self.quantity_cv
        )

        # Apply promo lift (Forward Buying / Batching)
        if order_is_promo is not None:
            # Expand promo flag to match lines
            is_promo_expanded = np.repeat(order_is_promo, lines_per_order)
            # Apply multiplier to promo orders
            quantities = np.where(
                is_promo_expanded,
                quantities * self.promo_lift_multiplier,
                quantities
            ).astype(np.int64)

        quantities = np.maximum(quantities, 1)  # At least 1
        batch["quantity_cases"] = quantities.astype(np.int32)

        # Prices
        prices = np.array([
            self.sku_prices.get(int(sku), 5.99) for sku in batch["sku_id"]
        ], dtype=np.float32)
        batch["unit_price"] = prices

        # Discounts - higher for promo orders
        base_discount = self.rng.uniform(0, 0.10, size=total_lines).astype(np.float32)
        if order_is_promo is not None:
            # Expand promo flag to match lines
            is_promo_expanded = np.repeat(order_is_promo, lines_per_order)
            # Promo orders get 10-25% discount
            promo_discount = self.rng.uniform(0.10, 0.25, size=total_lines).astype(np.float32)
            base_discount = np.where(is_promo_expanded, promo_discount, base_discount)
        batch["discount_percent"] = (base_discount * 100).astype(np.float32)  # Store as percentage

        # Status - map from order status
        if order_statuses is not None:
            # Expand order statuses to match lines
            expanded_statuses = np.repeat(order_statuses, lines_per_order)
            # Map order status to line status
            status_map = {
                "pending": "open", "confirmed": "open",
                "allocated": "allocated", "picking": "allocated",
                "shipped": "shipped", "delivered": "shipped",
                "cancelled": "cancelled",
            }
            batch["status"] = np.array([
                status_map.get(str(s), "open") for s in expanded_statuses
            ])
        else:
            batch["status"] = "open"

        # created_at timestamp
        batch["created_at"] = np.datetime64("now", "s")

        return batch

    def generate_batch(
        self,
        batch_size: int,
        lines_per_order_range: tuple[int, int] = (1, 20),
    ) -> np.ndarray:
        """
        Generate a batch of order lines with random order assignment.

        Args:
            batch_size: Approximate number of lines to generate
            lines_per_order_range: (min, max) lines per order

        Returns:
            Structured NumPy array
        """
        # Estimate orders needed
        avg_lines = sum(lines_per_order_range) / 2
        n_orders = int(batch_size / avg_lines) + 1

        # Sample orders
        order_ids = self.rng.choice(self.order_ids, size=n_orders, replace=False)

        # Random lines per order
        lines_per_order = self.rng.integers(
            lines_per_order_range[0],
            lines_per_order_range[1] + 1,
            size=n_orders,
        )

        # Trim to batch_size
        cumsum = np.cumsum(lines_per_order)
        cutoff = np.searchsorted(cumsum, batch_size)
        if cutoff < n_orders:
            order_ids = order_ids[:cutoff + 1]
            lines_per_order = lines_per_order[:cutoff + 1]
            # Adjust last order's lines
            if cutoff > 0:
                lines_per_order[-1] = batch_size - cumsum[cutoff - 1]

        return self.generate_for_orders(order_ids, lines_per_order)


# =============================================================================
# Shipment Legs Generator
# =============================================================================

@dataclass
class ShipmentLegsGenerator(VectorizedGenerator):
    """
    Vectorized generator for shipment legs (~180K rows).

    Generates shipment leg data with:
    - Vectorized datetime arithmetic
    - Mode-specific delay distributions
    - Stochastic mode support (normal vs disrupted)
    """

    # Configuration
    shipment_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    route_segment_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    carrier_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))

    # Delay parameters by mode
    delay_params: dict[str, dict] = field(default_factory=lambda: {
        "truck": {"lambda": 1.6, "reliability": 0.94},
        "ocean": {"lambda": 8.0, "reliability": 0.53},
        "air": {"lambda": 2.0, "reliability": 0.88},
        "rail": {"lambda": 4.0, "reliability": 0.75},
    })

    # Disruption parameters (used when stochastic_mode == DISRUPTED)
    disruption_params: dict = field(default_factory=lambda: {
        "gamma_shape": 2.0,
        "delay_multiplier": 4.0,
    })

    base_year: int = 2024

    def configure(
        self,
        shipment_ids: list[int] | np.ndarray,
        route_segment_ids: list[int] | np.ndarray,
        carrier_ids: list[int] | np.ndarray,
    ) -> "ShipmentLegsGenerator":
        """Configure generator with shipment and route data."""
        self.shipment_ids = np.asarray(shipment_ids, dtype=np.int64)
        self.route_segment_ids = np.asarray(route_segment_ids, dtype=np.int64)
        self.carrier_ids = np.asarray(carrier_ids, dtype=np.int64)
        return self

    def _generate_delays(self, size: int, mode: str) -> np.ndarray:
        """
        Generate delay hours based on mode and stochastic setting.

        Args:
            size: Number of delays to generate
            mode: Transport mode (truck, ocean, air, rail)

        Returns:
            Array of delay hours
        """
        params = self.delay_params.get(mode, self.delay_params["truck"])

        if self.stochastic_mode == StochasticMode.DISRUPTED:
            # Fat-tail Gamma distribution for disruptions
            delays = self.rng.gamma(
                shape=self.disruption_params["gamma_shape"],
                scale=params["lambda"] * self.disruption_params["delay_multiplier"],
                size=size,
            )
        else:
            # Standard Poisson delays
            delays = self.rng.poisson(params["lambda"], size=size)

        return delays.astype(np.float32)

    def generate_batch(
        self,
        batch_size: int,
        modes: list[str] | None = None,
        base_date: date | None = None,
    ) -> np.ndarray:
        """
        Generate a batch of shipment leg records.

        Args:
            batch_size: Number of records to generate
            modes: List of transport modes to use (random if None)
            base_date: Base date for departure times

        Returns:
            Structured NumPy array with SHIPMENT_LEGS_DTYPE
        """
        batch = np.zeros(batch_size, dtype=SHIPMENT_LEGS_DTYPE)

        # IDs
        batch["id"] = np.arange(self._next_id, self._next_id + batch_size)
        self._next_id += batch_size

        # Random shipment and route assignments
        batch["shipment_id"] = self.rng.choice(self.shipment_ids, size=batch_size)
        batch["route_segment_id"] = self.rng.choice(self.route_segment_ids, size=batch_size)
        batch["carrier_id"] = self.rng.choice(self.carrier_ids, size=batch_size)

        # Leg sequence (1-5)
        batch["leg_sequence"] = self.rng.integers(1, 6, size=batch_size)

        # Transport modes
        if modes is None:
            modes = ["truck", "ocean", "air", "rail"]
        mode_choices = self.rng.choice(modes, size=batch_size)
        batch["transport_mode"] = mode_choices

        # Planned departure times (random throughout year)
        if base_date is None:
            base_date = date(self.base_year, 1, 1)
        base_dt = np.datetime64(base_date, "h")
        hours_offset = self.rng.integers(0, 365 * 24, size=batch_size)
        batch["planned_departure"] = base_dt + hours_offset.astype("timedelta64[h]")

        # Planned transit times by mode (hours)
        transit_times = {
            "truck": (24, 72),
            "ocean": (240, 480),  # 10-20 days
            "air": (12, 48),
            "rail": (48, 120),
        }
        planned_transit = np.array([
            self.rng.integers(*transit_times.get(m, (24, 72)))
            for m in mode_choices
        ], dtype=np.int32)
        batch["planned_arrival"] = batch["planned_departure"] + planned_transit.astype("timedelta64[h]")

        # Generate delays by mode
        delays = np.zeros(batch_size, dtype=np.float32)
        for mode in set(mode_choices):
            mask = mode_choices == mode
            delays[mask] = self._generate_delays(mask.sum(), mode)
        batch["delay_hours"] = delays

        # Actual times
        batch["actual_departure"] = batch["planned_departure"] + (delays * 0.3).astype("timedelta64[h]")
        batch["actual_arrival"] = batch["planned_arrival"] + delays.astype("timedelta64[h]")

        # Status based on delays
        status = np.where(
            delays == 0, "on_time",
            np.where(delays < 24, "delayed", "severely_delayed")
        )
        batch["status"] = status

        return batch


# =============================================================================
# Shipment Lines Generator
# =============================================================================

@dataclass
class ShipmentLinesGenerator(VectorizedGenerator):
    """
    Vectorized generator for shipment lines (~1M rows).

    Generates shipment line items with:
    - Zipf-distributed SKU selection
    - Batch assignment with traceability
    - Weight calculation based on SKU size
    """

    # Base parameters
    base_year: int = 2024

    # Configuration
    sku_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    sku_weights: np.ndarray | None = None
    sku_weight_kg: dict[int, float] = field(default_factory=dict)  # sku_id -> weight per case
    batch_ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    batch_output_cases: dict[int, int] = field(default_factory=dict)  # batch_id -> output_cases
    batch_numbers: dict[int, str] = field(default_factory=dict)  # batch_id -> batch_number
    batch_expiry: dict[int, date] = field(default_factory=dict)  # batch_id -> expiry_date

    # Generation parameters
    zipf_alpha: float = 0.8

    def configure(
        self,
        sku_ids: list[int] | np.ndarray,
        batch_ids: list[int] | np.ndarray,
        sku_weights: np.ndarray | None = None,
        sku_weight_kg: dict[int, float] | None = None,
        batch_output_cases: dict[int, int] | None = None,
        batch_numbers: dict[int, str] | None = None,
        batch_expiry: dict[int, date] | None = None,
    ) -> "ShipmentLinesGenerator":
        """Configure generator with SKU and batch data."""
        self.sku_ids = np.asarray(sku_ids, dtype=np.int64)
        self.batch_ids = np.asarray(batch_ids, dtype=np.int64)

        if sku_weights is not None:
            self.sku_weights = np.asarray(sku_weights, dtype=np.float64)
        else:
            self.sku_weights = zipf_weights(len(self.sku_ids), self.zipf_alpha)

        self.sku_weight_kg = sku_weight_kg or {}
        self.batch_output_cases = batch_output_cases or {}
        self.batch_numbers = batch_numbers or {}
        self.batch_expiry = batch_expiry or {}

        return self

    def generate_for_shipments(
        self,
        shipment_ids: np.ndarray,
        total_cases: np.ndarray,
        ship_dates: np.ndarray,
        now: datetime | None = None,
    ) -> np.ndarray:
        """
        Generate shipment lines for a batch of shipments.

        Args:
            shipment_ids: Array of shipment IDs
            total_cases: Array of total cases per shipment
            ship_dates: Array of ship dates (datetime64[D])
            now: Timestamp for created_at

        Returns:
            Structured NumPy array with SHIPMENT_LINES_DTYPE
        """
        if now is None:
            now = datetime.now()
        now_dt = np.datetime64(now, "s")

        n_shipments = len(shipment_ids)

        # Calculate lines per shipment based on total_cases
        lines_per_shipment = np.where(
            total_cases < 100,
            self.rng.integers(1, 4, size=n_shipments),
            np.where(
                total_cases < 500,
                self.rng.integers(2, 6, size=n_shipments),
                self.rng.integers(3, 11, size=n_shipments),
            ),
        ).astype(np.int32)

        total_lines = int(lines_per_shipment.sum())
        batch = np.zeros(total_lines, dtype=SHIPMENT_LINES_DTYPE)

        # Expand shipment IDs to match line counts
        batch["shipment_id"] = np.repeat(shipment_ids, lines_per_shipment)

        # Line numbers within each shipment (1, 2, 3, ... per shipment)
        line_nums = []
        for count in lines_per_shipment:
            line_nums.extend(range(1, int(count) + 1))
        batch["line_number"] = np.array(line_nums, dtype=np.int32)

        # Zipf-weighted SKU selection
        sku_indices = self.rng.choice(
            len(self.sku_ids), size=total_lines, p=self.sku_weights
        )
        batch["sku_id"] = self.sku_ids[sku_indices]

        # Random batch selection
        batch_indices = self.rng.integers(0, len(self.batch_ids), size=total_lines)
        batch["batch_id"] = self.batch_ids[batch_indices]

        # Distribute cases across lines within each shipment
        # Expand total_cases to match lines
        expanded_total = np.repeat(total_cases, lines_per_shipment)
        expanded_line_counts = np.repeat(lines_per_shipment, lines_per_shipment)

        # Divide cases roughly equally with some variation
        base_qty = expanded_total // expanded_line_counts
        # Add random variation (±20%)
        variation = self.rng.uniform(0.8, 1.2, size=total_lines)
        quantities = (base_qty * variation).astype(np.int32)
        quantities = np.maximum(quantities, 1)  # At least 1 case
        batch["quantity_cases"] = quantities
        batch["quantity_eaches"] = quantities * 24

        # Batch fraction (qty / batch output cases)
        batch_output = np.array([
            self.batch_output_cases.get(int(bid), 1000)
            for bid in batch["batch_id"]
        ], dtype=np.float32)
        batch["batch_fraction"] = np.minimum(1.0, quantities / batch_output).astype(np.float32)

        # Weight calculation
        weights_per_case = np.array([
            self.sku_weight_kg.get(int(sku), 5.0)
            for sku in batch["sku_id"]
        ], dtype=np.float32)
        batch["weight_kg"] = (quantities * weights_per_case).astype(np.float32)

        # Lot numbers from batch
        batch["lot_number"] = np.array([
            self.batch_numbers.get(int(bid), f"LOT-{bid:08d}")[:20]
            for bid in batch["batch_id"]
        ], dtype="U20")

        # Expiry dates - expand ship_dates and add default if no batch expiry
        expanded_ship_dates = np.repeat(ship_dates, lines_per_shipment)
        default_expiry = expanded_ship_dates + np.timedelta64(180, "D")
        batch["expiry_date"] = np.array([
            np.datetime64(self.batch_expiry.get(int(bid), None) or default_expiry[i], "D")
            for i, bid in enumerate(batch["batch_id"])
        ], dtype="datetime64[D]")

        batch["created_at"] = now_dt

        return batch


# =============================================================================
# Utility Functions
# =============================================================================

def structured_to_dicts(
    array: np.ndarray,
    datetime_format: str = "%Y-%m-%d",
) -> list[dict[str, Any]]:
    """
    Convert structured NumPy array to list of dicts for StreamingWriter.

    Args:
        array: Structured NumPy array
        datetime_format: Format for datetime conversion

    Returns:
        List of row dicts
    """
    rows = []
    for record in array:
        row = {}
        for name in array.dtype.names:
            val = record[name]
            # Convert numpy types to Python types
            if isinstance(val, (np.integer, np.int64, np.int32)):
                row[name] = int(val)
            elif isinstance(val, (np.floating, np.float32, np.float64)):
                row[name] = float(val)
            elif isinstance(val, np.bool_):
                row[name] = bool(val)
            elif isinstance(val, np.datetime64):
                if np.isnat(val):
                    row[name] = None
                else:
                    # Convert to Python datetime
                    ts = (val - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
                    dtype_str = str(val.dtype)
                    if "D" in dtype_str:
                        row[name] = date.fromtimestamp(ts)
                    else:
                        # Timestamp (datetime64[s], datetime64[ms], etc.)
                        row[name] = datetime.fromtimestamp(ts)
            elif isinstance(val, np.str_):
                row[name] = str(val) if val else None
            else:
                row[name] = val
        rows.append(row)
    return rows


def structured_to_copy_lines(
    array: np.ndarray,
    columns: list[str],
) -> list[str]:
    """
    Convert structured array directly to COPY format lines.

    More efficient than going through dicts for large batches.

    Args:
        array: Structured NumPy array
        columns: Column order for output

    Returns:
        List of tab-separated lines
    """
    lines = []
    for record in array:
        values = []
        for col in columns:
            val = record[col]
            if isinstance(val, np.bool_):
                values.append("t" if val else "f")
            elif isinstance(val, np.datetime64):
                if np.isnat(val):
                    values.append("\\N")
                else:
                    values.append(str(val))
            elif isinstance(val, (np.integer, np.floating)):
                if np.isnan(val) if isinstance(val, np.floating) else False:
                    values.append("\\N")
                else:
                    values.append(str(val))
            elif val is None or (isinstance(val, np.str_) and not val):
                values.append("\\N")
            else:
                # Escape special characters
                s = str(val).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
                values.append(s)
        lines.append("\t".join(values))
    return lines


# Column lists for COPY output (excludes GENERATED columns like sale_week)
POS_SALES_COLUMNS = [
    "id", "retail_location_id", "sku_id", "sale_date",
    "quantity_eaches", "quantity_cases", "revenue", "currency",
    "is_promotional", "promo_id", "created_at",
]

ORDER_LINES_COLUMNS = [
    "order_id", "line_number", "sku_id", "quantity_cases",
    "unit_price", "discount_percent", "status", "created_at",
]

SHIPMENT_LEGS_COLUMNS = [
    "id", "shipment_id", "route_segment_id", "leg_sequence", "transport_mode",
    "carrier_id", "planned_departure", "planned_arrival", "actual_departure",
    "actual_arrival", "delay_hours", "status",
]
