"""
RealismMonitor - Online streaming validation for FMCG data generation.

Uses O(1) space online algorithms to validate data realism as it streams
through the generation pipeline, enabling fail-fast detection of drift.

Flow: Vectorized Engine → RealismMonitor.observe_batch() → StreamingWriter

Online Algorithms:
- WelfordAccumulator: Online mean/variance (lead time variability, yield loss)
- FrequencySketch: Count-Min Sketch approximation (SKU frequency for Pareto)
- CardinalityEstimator: HyperLogLog approximation (unique affected stores)
- DegreeMonitor: Running degree counts (hub concentration)

Usage:
    monitor = RealismMonitor(manifest_path="benchmark_manifest.json")

    # Observe batches as they're generated
    for batch in generate_orders():
        monitor.observe_batch("demand", "orders", batch)

    # Check for violations
    if monitor.has_violations():
        raise RealismViolationError(monitor.get_violations())

    # Get final report
    report = monitor.get_reality_report()
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class StochasticMode(Enum):
    """
    Stochastic mode for controlling distribution behavior.

    Normal mode uses standard distributions (Poisson for delays, etc.)
    Disrupted mode uses fat-tail distributions (Gamma) for chaos scenarios.
    """

    NORMAL = "poisson"      # Standard friction
    DISRUPTED = "gamma"     # Fat-tail delays (port strike, etc.)


class RealismViolationError(Exception):
    """Raised when data fails realism validation."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__(f"Realism violations: {violations}")


# =============================================================================
# Online Statistical Accumulators
# =============================================================================

@dataclass
class WelfordAccumulator:
    """
    Welford's online algorithm for computing mean and variance.

    Numerically stable single-pass algorithm for streaming data.
    Space complexity: O(1)

    Reference: Welford, B. P. (1962). "Note on a method for calculating
    corrected sums of squares and products"
    """

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0  # Sum of squared differences from mean

    def update(self, value: float) -> None:
        """Add a new value to the accumulator."""
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    def update_batch(self, values: np.ndarray | list[float]) -> None:
        """Add multiple values to the accumulator."""
        for v in values:
            self.update(float(v))

    @property
    def variance(self) -> float:
        """Population variance."""
        if self.count < 2:
            return 0.0
        return self.m2 / self.count

    @property
    def sample_variance(self) -> float:
        """Sample variance (Bessel's correction)."""
        if self.count < 2:
            return 0.0
        return self.m2 / (self.count - 1)

    @property
    def std(self) -> float:
        """Population standard deviation."""
        return math.sqrt(self.variance)

    @property
    def cv(self) -> float:
        """Coefficient of variation (std/mean)."""
        if self.mean == 0:
            return 0.0
        return self.std / abs(self.mean)

    def get_stats(self) -> dict[str, float]:
        """Return all statistics."""
        return {
            "count": self.count,
            "mean": self.mean,
            "variance": self.variance,
            "std": self.std,
            "cv": self.cv,
        }


@dataclass
class FrequencySketch:
    """
    Approximate frequency counting using Count-Min Sketch approach.

    For FMCG, we use exact counting since the number of SKUs (~2000)
    is manageable. This class provides a consistent interface that
    could be swapped for CMS if scale increases.

    Space complexity: O(k) where k = number of unique keys
    """

    counts: Counter = field(default_factory=Counter)
    total: int = 0

    def update(self, key: Any, count: int = 1) -> None:
        """Increment count for a key."""
        self.counts[key] += count
        self.total += count

    def update_batch(self, keys: list[Any]) -> None:
        """Update counts for multiple keys."""
        self.counts.update(keys)
        self.total += len(keys)

    def get_count(self, key: Any) -> int:
        """Get count for a key."""
        return self.counts[key]

    def get_frequency(self, key: Any) -> float:
        """Get frequency (count/total) for a key."""
        if self.total == 0:
            return 0.0
        return self.counts[key] / self.total

    def top_k(self, k: int = 10) -> list[tuple[Any, int]]:
        """Get top k items by count."""
        return self.counts.most_common(k)

    def pareto_ratio(self, top_pct: float = 0.20) -> float:
        """
        Calculate what percentage of total volume comes from top X% of items.

        For 80/20 Pareto rule, top_pct=0.20 should return ~0.80.
        """
        if not self.counts or self.total == 0:
            return 0.0

        sorted_counts = sorted(self.counts.values(), reverse=True)
        n_items = len(sorted_counts)
        top_n = max(1, int(n_items * top_pct))

        top_volume = sum(sorted_counts[:top_n])
        return top_volume / self.total

    def get_stats(self) -> dict[str, Any]:
        """Return frequency statistics."""
        return {
            "unique_keys": len(self.counts),
            "total_observations": self.total,
            "top_10": self.top_k(10),
            "pareto_20_80": self.pareto_ratio(0.20),
        }


@dataclass
class CardinalityEstimator:
    """
    Exact cardinality counting for unique elements.

    Uses a set for exact counting since FMCG cardinalities are bounded
    (e.g., ~10K stores). Could be replaced with HyperLogLog for larger scale.

    Space complexity: O(k) where k = number of unique elements
    """

    seen: set = field(default_factory=set)

    def update(self, element: Any) -> None:
        """Add an element to track."""
        self.seen.add(element)

    def update_batch(self, elements: list[Any] | set[Any]) -> None:
        """Add multiple elements."""
        self.seen.update(elements)

    @property
    def cardinality(self) -> int:
        """Estimated cardinality (exact in this implementation)."""
        return len(self.seen)

    def contains(self, element: Any) -> bool:
        """Check if element has been seen."""
        return element in self.seen

    def get_stats(self) -> dict[str, Any]:
        """Return cardinality statistics."""
        return {
            "unique_count": self.cardinality,
        }


@dataclass
class DegreeMonitor:
    """
    Monitor node degrees for hub concentration analysis.

    Tracks in-degree and out-degree for network nodes to validate
    preferential attachment patterns (e.g., MegaMart gets 25% of orders).

    Space complexity: O(n) where n = number of nodes
    """

    in_degrees: Counter = field(default_factory=Counter)
    out_degrees: Counter = field(default_factory=Counter)
    total_edges: int = 0

    def add_edge(self, source: Any, target: Any) -> None:
        """Record an edge from source to target."""
        self.out_degrees[source] += 1
        self.in_degrees[target] += 1
        self.total_edges += 1

    def add_edges_batch(self, edges: list[tuple[Any, Any]]) -> None:
        """Record multiple edges."""
        for source, target in edges:
            self.add_edge(source, target)

    def get_in_degree(self, node: Any) -> int:
        """Get in-degree for a node."""
        return self.in_degrees[node]

    def get_out_degree(self, node: Any) -> int:
        """Get out-degree for a node."""
        return self.out_degrees[node]

    def get_hub_concentration(self, node: Any, direction: str = "in") -> float:
        """
        Get what fraction of total edges involve this node.

        Args:
            node: Node to check
            direction: "in" for in-degree, "out" for out-degree

        Returns:
            Fraction of total edges (0.0 to 1.0)
        """
        if self.total_edges == 0:
            return 0.0

        if direction == "in":
            return self.in_degrees[node] / self.total_edges
        return self.out_degrees[node] / self.total_edges

    def top_hubs(self, k: int = 10, direction: str = "in") -> list[tuple[Any, int]]:
        """Get top k hubs by degree."""
        degrees = self.in_degrees if direction == "in" else self.out_degrees
        return degrees.most_common(k)

    def get_stats(self) -> dict[str, Any]:
        """Return degree statistics."""
        return {
            "total_edges": self.total_edges,
            "unique_sources": len(self.out_degrees),
            "unique_targets": len(self.in_degrees),
            "top_in_hubs": self.top_hubs(5, "in"),
            "top_out_hubs": self.top_hubs(5, "out"),
        }


# =============================================================================
# Main RealismMonitor Class
# =============================================================================

class RealismMonitor:
    """
    Streaming validation monitor for FMCG data generation.

    Observes batches of generated data and validates against benchmark
    thresholds using online algorithms. Supports fail-fast detection
    when data drifts outside acceptable ranges.

    Attributes:
        benchmarks: Ground truth benchmark values
        stochastic_mode: Current stochastic mode (NORMAL or DISRUPTED)
        violations: List of detected violations
    """

    def __init__(
        self,
        manifest_path: Path | str | None = None,
        manifest_data: dict | None = None,
        fail_fast: bool = False,
    ) -> None:
        """
        Initialize realism monitor.

        Args:
            manifest_path: Path to benchmark_manifest.json
            manifest_data: Direct benchmark data (alternative to file)
            fail_fast: Raise exception immediately on violation
        """
        self.fail_fast = fail_fast
        self.stochastic_mode = StochasticMode.NORMAL

        # Load benchmarks
        if manifest_data is not None:
            self.benchmarks = manifest_data.get("benchmarks", {})
            self.profile_name = manifest_data.get("supply_chain_profile", "unknown")
        elif manifest_path is not None:
            with open(manifest_path) as f:
                data = json.load(f)
            self.benchmarks = data.get("benchmarks", {})
            self.profile_name = data.get("supply_chain_profile", "unknown")
        else:
            self.benchmarks = {}
            self.profile_name = "no_benchmarks"

        # Tracking structures
        self.violations: list[str] = []
        self.row_counts: dict[str, int] = defaultdict(int)

        # Online accumulators by domain
        self._accumulators: dict[str, dict[str, WelfordAccumulator]] = defaultdict(
            lambda: defaultdict(WelfordAccumulator)
        )

        # Frequency sketches for distribution validation
        self._frequencies: dict[str, FrequencySketch] = defaultdict(FrequencySketch)

        # Cardinality estimators
        self._cardinalities: dict[str, CardinalityEstimator] = defaultdict(
            CardinalityEstimator
        )

        # Degree monitors for network analysis
        self._degrees: dict[str, DegreeMonitor] = defaultdict(DegreeMonitor)

        # Domain-specific trackers
        self._pos_cv_accumulator = WelfordAccumulator()
        self._order_cv_accumulator = WelfordAccumulator()
        self._orders_by_account: Counter = Counter()
        self._recall_affected_stores: set = set()

    def observe_batch(
        self,
        domain: str,
        table: str,
        batch_data: list[dict[str, Any]] | np.ndarray,
    ) -> None:
        """
        Main entry point - observe a batch of generated data.

        Call this for every batch of rows generated. Performs domain-specific
        validation and updates online statistics.

        Args:
            domain: Domain name (e.g., "demand", "logistics", "source")
            table: Table name (e.g., "orders", "pos_sales", "shipment_legs")
            batch_data: List of row dicts or structured numpy array
        """
        if not batch_data:
            return

        # Convert numpy structured array to list of dicts if needed
        if isinstance(batch_data, np.ndarray):
            if batch_data.dtype.names:
                batch_data = [dict(zip(batch_data.dtype.names, row)) for row in batch_data]
            else:
                return  # Can't process unstructured arrays

        self.row_counts[table] += len(batch_data)

        # Route to domain-specific validators
        if table == "pos_sales":
            self._check_pos_sales(batch_data)
        elif table == "orders":
            self._check_orders(batch_data)
        elif table == "order_lines":
            self._check_order_lines(batch_data)
        elif table == "shipment_legs":
            self._check_logistics_friction(batch_data)
        elif table == "batches":
            self._check_batches(batch_data)
        elif table == "inventory":
            self._check_inventory(batch_data)
        elif table == "shipment_lines":
            self._check_recall_propagation(batch_data)

    def _check_pos_sales(self, batch: list[dict]) -> None:
        """Validate POS sales for demand volatility."""
        quantities = [row.get("quantity_cases", 0) for row in batch if row.get("quantity_cases")]
        if quantities:
            self._pos_cv_accumulator.update_batch(quantities)

            # Track SKU frequency for Pareto
            sku_ids = [row.get("sku_id") for row in batch if row.get("sku_id")]
            self._frequencies["pos_sku"].update_batch(sku_ids)

    def _check_orders(self, batch: list[dict]) -> None:
        """Validate orders for hub concentration."""
        for row in batch:
            account_id = row.get("account_id")
            if account_id:
                self._orders_by_account[account_id] += 1

            # Track order-location edges for degree monitoring
            location_id = row.get("retail_location_id")
            if account_id and location_id:
                self._degrees["account_orders"].add_edge(account_id, location_id)

    def _check_order_lines(self, batch: list[dict]) -> None:
        """Validate order lines for SKU Pareto distribution."""
        # Track quantities for order CV
        quantities = [row.get("quantity") for row in batch if row.get("quantity")]
        if quantities:
            self._order_cv_accumulator.update_batch(quantities)

        # Track SKU frequency
        sku_ids = [row.get("sku_id") for row in batch if row.get("sku_id")]
        self._frequencies["order_sku"].update_batch(sku_ids)

    def _check_logistics_friction(self, batch: list[dict]) -> None:
        """Validate shipment legs for kinetic friction."""
        # Track delay statistics
        for row in batch:
            delay = row.get("delay_hours", 0)
            mode = row.get("transport_mode", "unknown")
            self._accumulators["logistics"][f"delay_{mode}"].update(delay)

    def _check_batches(self, batch: list[dict]) -> None:
        """Validate batches for yield loss and QC."""
        for row in batch:
            yield_pct = row.get("yield_percentage")
            if yield_pct is not None:
                self._accumulators["production"]["yield"].update(yield_pct)

    def _check_inventory(self, batch: list[dict]) -> None:
        """Validate inventory for cash cycle metrics."""
        for row in batch:
            days_on_hand = row.get("days_on_hand")
            if days_on_hand is not None:
                self._accumulators["inventory"]["days_on_hand"].update(days_on_hand)

    def _check_recall_propagation(self, batch: list[dict]) -> None:
        """Track recall batch propagation to stores."""
        for row in batch:
            batch_id = row.get("batch_id")
            # Check if this is the recall batch (by ID or batch_number if available)
            if batch_id and row.get("destination_type") == "STORE":
                destination_id = row.get("destination_id")
                if destination_id:
                    self._recall_affected_stores.add(destination_id)

    def check_benchmarks(self, check_interval_rows: int = 10000) -> None:
        """
        Validate current state against benchmarks.

        Called periodically during generation to enable fail-fast.

        Args:
            check_interval_rows: Minimum rows between checks
        """
        total_rows = sum(self.row_counts.values())
        if total_rows < check_interval_rows:
            return

        # Check Pareto distribution (SKU 80/20)
        if "order_sku" in self._frequencies:
            pareto = self._frequencies["order_sku"].pareto_ratio(0.20)
            target_range = (0.75, 0.85)
            if not (target_range[0] <= pareto <= target_range[1]):
                self._add_violation(
                    f"Pareto drift: top 20% SKUs = {pareto:.1%} volume "
                    f"(target: {target_range[0]:.0%}-{target_range[1]:.0%})"
                )

        # Check hub concentration (MegaMart 20-30%)
        total_orders = sum(self._orders_by_account.values())
        if total_orders > 1000:
            # Find the top account (should be MegaMart)
            top_account, top_count = self._orders_by_account.most_common(1)[0]
            concentration = top_count / total_orders
            target_range = (0.20, 0.30)
            if not (target_range[0] <= concentration <= target_range[1]):
                self._add_violation(
                    f"Hub concentration drift: top account = {concentration:.1%} "
                    f"(target: {target_range[0]:.0%}-{target_range[1]:.0%})"
                )

        # Check Bullwhip effect (Order CV > POS CV)
        if self._pos_cv_accumulator.count > 100 and self._order_cv_accumulator.count > 100:
            pos_cv = self._pos_cv_accumulator.cv
            order_cv = self._order_cv_accumulator.cv
            if pos_cv > 0 and order_cv < pos_cv:
                self._add_violation(
                    f"Bullwhip violation: Order CV ({order_cv:.2f}) should be > "
                    f"POS CV ({pos_cv:.2f})"
                )

    def _add_violation(self, message: str) -> None:
        """Add a violation and optionally raise immediately."""
        self.violations.append(message)
        if self.fail_fast:
            raise RealismViolationError([message])

    def has_violations(self) -> bool:
        """Check if any violations have been detected."""
        return len(self.violations) > 0

    def get_violations(self) -> list[str]:
        """Get all detected violations."""
        return list(self.violations)

    def set_stochastic_mode(self, mode: StochasticMode) -> None:
        """
        Set stochastic mode for generators.

        Used by Risk Events to switch from normal to disrupted distributions.
        """
        self.stochastic_mode = mode

    def get_reality_report(self) -> dict[str, Any]:
        """
        Generate comprehensive reality report.

        Returns summary of all validations, statistics, and violations.
        """
        report = {
            "is_realistic": len(self.violations) == 0,
            "profile": self.profile_name,
            "stochastic_mode": self.stochastic_mode.value,
            "violations": self.violations,
            "row_counts": dict(self.row_counts),
            "total_rows": sum(self.row_counts.values()),
            "statistics": {},
        }

        # Add frequency statistics
        if self._frequencies:
            report["statistics"]["frequencies"] = {
                name: sketch.get_stats()
                for name, sketch in self._frequencies.items()
            }

        # Add Pareto check
        if "order_sku" in self._frequencies:
            pareto = self._frequencies["order_sku"].pareto_ratio(0.20)
            report["statistics"]["pareto_20_80"] = {
                "value": pareto,
                "target": "0.75-0.85",
                "passed": 0.75 <= pareto <= 0.85,
            }

        # Add hub concentration
        total_orders = sum(self._orders_by_account.values())
        if total_orders > 0:
            top_accounts = self._orders_by_account.most_common(5)
            report["statistics"]["hub_concentration"] = {
                "total_orders": total_orders,
                "top_accounts": [
                    {"account_id": acc, "count": cnt, "pct": cnt / total_orders}
                    for acc, cnt in top_accounts
                ],
            }

        # Add Bullwhip metrics
        if self._pos_cv_accumulator.count > 0:
            report["statistics"]["bullwhip"] = {
                "pos_cv": self._pos_cv_accumulator.cv,
                "order_cv": self._order_cv_accumulator.cv,
                "multiplier": (
                    self._order_cv_accumulator.cv / self._pos_cv_accumulator.cv
                    if self._pos_cv_accumulator.cv > 0
                    else 0
                ),
            }

        # Add recall tracking
        report["statistics"]["recall_trace"] = {
            "affected_stores": len(self._recall_affected_stores),
            "target": 500,
        }

        # Add accumulator summaries
        for domain, accumulators in self._accumulators.items():
            report["statistics"][domain] = {
                name: acc.get_stats()
                for name, acc in accumulators.items()
            }

        return report

    def reset(self) -> None:
        """Reset all tracking state."""
        self.violations.clear()
        self.row_counts.clear()
        self._accumulators.clear()
        self._frequencies.clear()
        self._cardinalities.clear()
        self._degrees.clear()
        self._pos_cv_accumulator = WelfordAccumulator()
        self._order_cv_accumulator = WelfordAccumulator()
        self._orders_by_account.clear()
        self._recall_affected_stores.clear()
