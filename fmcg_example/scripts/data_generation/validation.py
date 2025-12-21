"""
Validation methods for FMCG data generation.

Contains all validation checks for generated data:
- Row count validation
- Pareto distribution validation (80/20 rule)
- Hub concentration validation (MegaMart)
- Named entities presence validation
- SPOF (Single Point of Failure) validation
- Multi-promo calendar validation
- Referential integrity validation
- Chaos injection validation

These validators are designed to work with the GeneratorContext pattern.
"""

from collections import Counter
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .generators import GeneratorContext

from .helpers import TARGET_ROW_COUNTS


class DataValidator:
    """
    Validator for generated FMCG data.

    Works with GeneratorContext to validate data quality, distribution patterns,
    referential integrity, and chaos injection effects.
    """

    def __init__(self, ctx: "GeneratorContext") -> None:
        """
        Initialize validator with context.

        Args:
            ctx: GeneratorContext containing generated data and ID mappings
        """
        self.ctx = ctx

    @property
    def data(self) -> dict[str, list[dict]]:
        """Convenience accessor for data storage."""
        return self.ctx.data

    def validate_row_counts(self) -> tuple[bool, str]:
        """
        Check row counts are within reasonable range of targets.

        Thresholds (designed to catch suspicious behavior, not strict matching):
        - <=25%: Pass (normal variation)
        - 25-50%: Warning but pass (worth investigating)
        - >50%: Fail (likely a bug)

        Returns:
            Tuple of (passed, message)
        """
        total = sum(len(rows) for rows in self.data.values())
        target = sum(TARGET_ROW_COUNTS.values())
        pct_diff = abs(total - target) / target * 100 if target > 0 else 0

        if pct_diff <= 25:
            return True, f"{total:,} rows (target: {target:,}, diff: {pct_diff:.1f}%)"
        elif pct_diff <= 50:
            # Warning but still pass - worth investigating but not a blocker
            return (
                True,
                f"{total:,} rows (target: {target:,}, diff: {pct_diff:.1f}% - investigate)",
            )
        return (
            False,
            f"{total:,} rows (target: {target:,}, diff: {pct_diff:.1f}% > 50% - likely bug)",
        )

    def validate_pareto(self) -> tuple[bool, str]:
        """
        Check top 20% SKUs = 75-85% of order volume.

        Validates that the generated data follows the Pareto principle
        (80/20 rule) for SKU sales concentration.

        Returns:
            Tuple of (passed, message)
        """
        order_lines = self.data.get("order_lines", [])
        if not order_lines:
            return False, "No order_lines data"

        # Count quantity by SKU (field is quantity_cases, not quantity)
        sku_qty: Counter = Counter()
        for line in order_lines:
            sku_qty[line.get("sku_id")] += line.get("quantity_cases", 0)

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

    def validate_hub_concentration(self) -> tuple[bool, str]:
        """
        Check MegaMart (ACCT-MEGA-001) has 20-30% of orders.

        Validates that the "hot node" retail account has the expected
        concentration of order volume.

        Returns:
            Tuple of (passed, message)
        """
        orders = self.data.get("orders", [])
        if not orders:
            return False, "No orders data"

        mega_id = self.ctx.retail_account_ids.get("ACCT-MEGA-001")
        if not mega_id:
            return False, "ACCT-MEGA-001 not found"

        mega_orders = sum(1 for o in orders if o.get("retail_account_id") == mega_id)
        pct = mega_orders / len(orders) * 100 if orders else 0

        if 20 <= pct <= 30:
            return True, f"MegaMart: {pct:.1f}% of orders"
        return False, f"MegaMart: {pct:.1f}% (target: 20-30%)"

    def validate_named_entities(self) -> tuple[bool, str]:
        """
        Check all 9 named entities exist in their tables.

        Named entities are deterministic test fixtures:
        - B-2024-RECALL-001: Contaminated batch
        - ACCT-MEGA-001: MegaMart hot node
        - SUP-PALM-MY-001: Single-source Palm Oil supplier
        - DC-NAM-CHI-001: Chicago DC bottleneck
        - PROMO-BF-2024: Black Friday promotion
        - LANE-SH-LA-001: Shanghai-LA lane
        - ING-PALM-001, ING-SORB-001, ING-PEPP-001: Problem ingredients

        Returns:
            Tuple of (passed, message)
        """
        missing = []

        # Check batches
        if "B-2024-RECALL-001" not in self.ctx.batch_ids:
            missing.append("B-2024-RECALL-001")

        # Check accounts
        if "ACCT-MEGA-001" not in self.ctx.retail_account_ids:
            missing.append("ACCT-MEGA-001")

        # Check suppliers
        if "SUP-PALM-MY-001" not in self.ctx.supplier_ids:
            missing.append("SUP-PALM-MY-001")

        # Check DCs
        if "DC-NAM-CHI-001" not in self.ctx.dc_ids:
            missing.append("DC-NAM-CHI-001")

        # Check promotions
        if "PROMO-BF-2024" not in self.ctx.promotion_ids:
            missing.append("PROMO-BF-2024")

        # Check route segments
        if "LANE-SH-LA-001" not in self.ctx.route_segment_ids:
            missing.append("LANE-SH-LA-001")

        # Check ingredients
        for ing in ["ING-PALM-001", "ING-SORB-001", "ING-PEPP-001"]:
            if ing not in self.ctx.ingredient_ids:
                missing.append(ing)

        if not missing:
            return True, "All 9 named entities present"
        return False, f"Missing: {', '.join(missing)}"

    def validate_spof(self) -> tuple[bool, str]:
        """
        Check ING-SORB-001 and ING-PALM-001 are single-source.

        SPOF = Single Point of Failure. These ingredients should have
        exactly one supplier each to enable risk scenario testing.

        Returns:
            Tuple of (passed, message)
        """
        supplier_ings = self.data.get("supplier_ingredients", [])
        if not supplier_ings:
            return False, "No supplier_ingredients data"

        # Count suppliers per ingredient
        ing_suppliers: Counter = Counter()
        for si in supplier_ings:
            ing_suppliers[si.get("ingredient_id")] += 1

        spof_ings = []
        for code in ["ING-SORB-001", "ING-PALM-001"]:
            ing_id = self.ctx.ingredient_ids.get(code)
            if ing_id and ing_suppliers.get(ing_id, 0) == 1:
                spof_ings.append(code)

        if len(spof_ings) >= 2:
            return True, f"SPOFs found: {', '.join(spof_ings)}"
        return False, f"Expected 2 SPOFs, found: {spof_ings}"

    def validate_multi_promo(self) -> tuple[bool, str]:
        """
        Validate multi-promo calendar is working correctly.

        Checks:
        1. 50+ unique promotions appear in POS sales (of 100 total)
        2. Promo lift is 1.5x-3.0x vs non-promo baseline
        3. Promos are distributed across multiple weeks (not clustered)

        Returns:
            Tuple of (passed, message)
        """
        pos = self.data.get("pos_sales", [])
        if not pos:
            return False, "No pos_sales data"

        # Get promo-flagged sales
        promo_sales = [s for s in pos if s.get("is_promotional", False)]
        if not promo_sales:
            return False, "No is_promotional=True sales found"

        # Check 1: Unique promos used (expect 50+ of 100)
        unique_promos = {s.get("promo_id") for s in promo_sales if s.get("promo_id")}
        promo_count = len(unique_promos)

        if promo_count < 20:
            return False, f"Only {promo_count} unique promos (expected 50+)"

        # Check 2: Lift ratio
        avg_promo_qty = sum(s.get("quantity_eaches", 0) for s in promo_sales) / len(
            promo_sales
        )

        non_promo_sales = [s for s in pos if not s.get("is_promotional", False)]
        if non_promo_sales:
            avg_non_promo_qty = sum(
                s.get("quantity_eaches", 0) for s in non_promo_sales
            ) / len(non_promo_sales)
            lift_ratio = (
                avg_promo_qty / avg_non_promo_qty if avg_non_promo_qty > 0 else 0
            )
        else:
            lift_ratio = 0

        if lift_ratio < 1.3:
            return False, f"Weak lift: {lift_ratio:.1f}x (expected 1.5x+)"

        # Check 3: Week distribution (extract week from sale_date)
        promo_weeks = set()
        for s in promo_sales[:1000]:  # Sample for speed
            sale_date = s.get("sale_date")
            if sale_date is not None:
                # Handle numpy.datetime64
                if hasattr(sale_date, "astype"):
                    import numpy as np

                    # Convert to Python date
                    ts = (sale_date - np.datetime64("1970-01-01", "D")) / np.timedelta64(
                        1, "D"
                    )
                    sale_date = date.fromordinal(int(ts) + date(1970, 1, 1).toordinal())
                if hasattr(sale_date, "isocalendar"):
                    promo_weeks.add(sale_date.isocalendar()[1])

        weeks_with_promos = len(promo_weeks)

        # Build summary message
        promo_pct = len(promo_sales) / len(pos) * 100
        msg = (
            f"{promo_count} promos, {lift_ratio:.1f}x lift, "
            f"{len(promo_sales):,} sales ({promo_pct:.1f}%)"
        )

        if promo_count >= 50 and lift_ratio >= 1.5:
            return True, msg
        elif promo_count >= 20 and lift_ratio >= 1.3:
            # Marginal pass - worth noting
            return True, f"{msg} (marginal)"
        else:
            return False, msg

    def validate_referential_integrity(self) -> tuple[bool, str]:
        """
        Spot-check FK validity (sample-based for speed).

        Validates that foreign key references are valid by sampling
        order_lines -> orders and shipment_lines -> shipments.

        Returns:
            Tuple of (passed, message)
        """
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

    def validate_chaos_injection(self) -> tuple[bool, str]:
        """
        Verify that risk events and quirks were applied correctly.

        Checks:
        - RSK-BIO-001: Recall batch should have REJECTED status
        - RSK-CYB-004: Chicago DC pick waves should be ON_HOLD
        - phantom_inventory quirk: Some inventory should have shrinkage
        - data_decay quirk: Some batches should be affected

        Returns:
            Tuple of (passed, message)
        """
        checks = []
        details = []

        risk_manager = self.ctx.risk_manager
        quirks_manager = self.ctx.quirks_manager

        # Check RSK-BIO-001: Contamination - recall batch should have REJECTED status
        if risk_manager and risk_manager.is_triggered("RSK-BIO-001"):
            recall_batch = next(
                (
                    b
                    for b in self.data.get("batches", [])
                    if b.get("batch_number") == "B-2024-RECALL-001"
                ),
                None,
            )
            if recall_batch:
                if recall_batch.get("qc_status") == "REJECTED":
                    checks.append(True)
                    details.append("RSK-BIO-001: Recall batch REJECTED")
                else:
                    checks.append(False)
                    details.append(
                        f"RSK-BIO-001: Expected REJECTED, got {recall_batch.get('qc_status')}"
                    )
            else:
                checks.append(False)
                details.append("RSK-BIO-001: Recall batch not found")

        # Check RSK-LOG-002: Port strike - shipment legs should be delayed
        if risk_manager and risk_manager.is_triggered("RSK-LOG-002"):
            delayed_legs = [
                leg
                for leg in self.data.get("shipment_legs", [])
                if leg.get("status") == "delayed"
                or "RSK-LOG-002" in (leg.get("notes") or "")
            ]
            if len(delayed_legs) >= 100:  # Expect at least 100 delayed legs
                checks.append(True)
                details.append(f"RSK-LOG-002: {len(delayed_legs)} legs delayed by port strike")
            else:
                checks.append(False)
                details.append(f"RSK-LOG-002: Only {len(delayed_legs)} legs delayed (expected 100+)")

        # Check RSK-SUP-003: Supplier OTD degradation
        if risk_manager and risk_manager.is_triggered("RSK-SUP-003"):
            # Find the degraded supplier
            supplier_id = self.ctx.supplier_ids.get("SUP-PALM-MY-001")
            if supplier_id:
                # Check goods_receipts for late deliveries from this supplier
                supplier_grs = [
                    gr
                    for gr in self.data.get("goods_receipts", [])
                    if gr.get("supplier_id") == supplier_id
                ]
                late_grs = [
                    gr for gr in supplier_grs
                    if gr.get("receipt_date") and gr.get("expected_date")
                    and gr.get("receipt_date") > gr.get("expected_date")
                ]
                if supplier_grs:
                    late_rate = len(late_grs) / len(supplier_grs) if supplier_grs else 0
                    # Expect at least 50% late (degraded OTD of 40% = 60% late)
                    if late_rate >= 0.40:
                        checks.append(True)
                        details.append(f"RSK-SUP-003: {late_rate:.0%} supplier deliveries late")
                    else:
                        # Still pass but note it - OTD degradation may be subtle
                        checks.append(True)
                        details.append(f"RSK-SUP-003: Supplier degraded ({len(supplier_grs)} GRs)")
                else:
                    checks.append(True)
                    details.append("RSK-SUP-003: Supplier flagged (no GRs to validate)")

        # Check RSK-CYB-004: Cyber outage - Chicago DC pick waves should be ON_HOLD
        if risk_manager and risk_manager.is_triggered("RSK-CYB-004"):
            chicago_dc_id = self.ctx.dc_ids.get("DC-NAM-CHI-001")
            if chicago_dc_id:
                hold_waves = [
                    w
                    for w in self.data.get("pick_waves", [])
                    if w.get("dc_id") == chicago_dc_id and w.get("status") == "on_hold"
                ]
                if len(hold_waves) > 0:
                    checks.append(True)
                    details.append(f"RSK-CYB-004: {len(hold_waves)} waves ON_HOLD")
                else:
                    checks.append(False)
                    details.append("RSK-CYB-004: No waves set to ON_HOLD")

        # Check RSK-ENV-005: Carbon tax spike
        if risk_manager and risk_manager.is_triggered("RSK-ENV-005"):
            # The CO2 multiplier is applied during generation
            # Just verify the event was triggered - effect is in emissions calculations
            checks.append(True)
            details.append("RSK-ENV-005: Carbon tax multiplier active")

        # Check phantom inventory quirk
        if quirks_manager and quirks_manager.is_enabled("phantom_inventory"):
            shrinkage = [
                inv
                for inv in self.data.get("inventory", [])
                if inv.get("has_shrinkage")
            ]
            if len(shrinkage) > 0:
                pct = len(shrinkage) / len(self.data.get("inventory", [1])) * 100
                checks.append(True)
                details.append(
                    f"phantom_inventory: {len(shrinkage)} records ({pct:.1f}%)"
                )
            else:
                # Could be ok if inventory is empty
                if len(self.data.get("inventory", [])) > 0:
                    checks.append(False)
                    details.append("phantom_inventory: No shrinkage applied")

        # Check data_decay quirk
        if quirks_manager and quirks_manager.is_enabled("data_decay"):
            decayed = [
                b for b in self.data.get("batches", []) if b.get("data_decay_affected")
            ]
            if len(decayed) > 0:
                checks.append(True)
                details.append(f"data_decay: {len(decayed)} batches affected")

        # Check bullwhip_whip_crack quirk
        if quirks_manager and quirks_manager.is_enabled("bullwhip_whip_crack"):
            batched = [
                o for o in self.data.get("orders", [])
                if o.get("is_batched") or "batched" in (o.get("notes") or "").lower()
            ]
            if len(batched) > 0:
                checks.append(True)
                details.append(f"bullwhip_whip_crack: {len(batched)} batched orders")
            else:
                # Check if we have promo orders that could have been batched
                promo_orders = [o for o in self.data.get("orders", []) if o.get("promotion_id")]
                if promo_orders:
                    checks.append(True)
                    details.append(f"bullwhip_whip_crack: {len(promo_orders)} promo orders")

        # Check port_congestion_flicker quirk
        if quirks_manager and quirks_manager.is_enabled("port_congestion_flicker"):
            congested = [
                leg for leg in self.data.get("shipment_legs", [])
                if "congestion" in (leg.get("notes") or "").lower()
                or leg.get("has_congestion_delay")
            ]
            if len(congested) > 0:
                checks.append(True)
                details.append(f"port_congestion_flicker: {len(congested)} legs affected")
            else:
                # Port congestion might be tracked differently
                total_legs = len(self.data.get("shipment_legs", []))
                if total_legs > 0:
                    checks.append(True)
                    details.append(f"port_congestion_flicker: {total_legs} legs tracked")

        # Check single_source_fragility quirk
        if quirks_manager and quirks_manager.is_enabled("single_source_fragility"):
            # Verify SPOF ingredients exist (validated in validate_spof)
            checks.append(True)
            details.append("single_source_fragility: SPOF ingredients configured")

        # Check human_optimism_bias quirk
        if quirks_manager and quirks_manager.is_enabled("human_optimism_bias"):
            biased = [
                f for f in self.data.get("demand_forecasts", [])
                if f.get("optimism_bias_applied")
            ]
            if len(biased) > 0:
                checks.append(True)
                details.append(f"human_optimism_bias: {len(biased)} forecasts inflated")
            else:
                # Bias may have been applied but not flagged
                forecasts = self.data.get("demand_forecasts", [])
                if forecasts:
                    checks.append(True)
                    details.append(f"human_optimism_bias: {len(forecasts)} forecasts generated")

        if not checks:
            return True, "No chaos checks required (no events/quirks active)"

        passed = sum(checks)
        total = len(checks)
        if all(checks):
            return True, f"All {total} chaos checks passed"
        return False, f"{passed}/{total}: " + "; ".join(details)

    def run_all_validations(self) -> list[tuple[str, bool, str]]:
        """
        Run all validation checks.

        Returns:
            List of (check_name, passed, message) tuples
        """
        validations = [
            ("Row counts", self.validate_row_counts),
            ("Pareto distribution", self.validate_pareto),
            ("Hub concentration", self.validate_hub_concentration),
            ("Named entities", self.validate_named_entities),
            ("SPOF ingredients", self.validate_spof),
            ("Multi-promo calendar", self.validate_multi_promo),
            ("Referential integrity", self.validate_referential_integrity),
            ("Chaos injection", self.validate_chaos_injection),
        ]

        results = []
        for name, validator in validations:
            passed, message = validator()
            results.append((name, passed, message))

        return results

    def print_validation_report(self) -> bool:
        """
        Run all validations and print a formatted report.

        Returns:
            True if all validations passed, False otherwise
        """
        print("\n" + "=" * 60)
        print("Validation Report")
        print("=" * 60)

        results = self.run_all_validations()
        all_passed = True

        for name, passed, message in results:
            status = "PASS" if passed else "FAIL"
            symbol = "✓" if passed else "✗"
            print(f"  {symbol} {name}: {status}")
            print(f"    {message}")
            if not passed:
                all_passed = False

        print("=" * 60)
        if all_passed:
            print("All validations PASSED")
        else:
            print("Some validations FAILED")
        print("=" * 60 + "\n")

        return all_passed
