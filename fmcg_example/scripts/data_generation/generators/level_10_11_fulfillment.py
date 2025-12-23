"""
Level 10-11 Generator: Fulfillment (Shipments).

Level 10 Tables:
- pick_wave_orders (~180,000)
- shipments (~180,000)
- shipment_legs (~360,000)

Level 11 Tables:
- shipment_lines (~540,000)

Named entities:
- DC-NAM-CHI-001: Bottleneck DC (40% of NAM volume flows through Chicago)
"""

import random
import time
from datetime import date, datetime, timedelta

import numpy as np

from .base import BaseLevelGenerator
from ..lookup_builder import LookupBuilder
from ..vectorized import zipf_weights, ShipmentLinesGenerator, structured_to_dicts


class Level10Generator(BaseLevelGenerator):
    """
    Generate Level 10 shipment data.

    Level 10 contains pick_wave_orders, shipments, and shipment_legs.
    """

    LEVEL = 10

    def generate(self) -> None:
        """Generate all Level 10 tables."""
        print("  Level 10: Shipments and legs...")
        level_start = time.time()
        now = datetime.now()

        self._generate_pick_wave_orders(now)
        self._generate_shipments(now)
        self._generate_shipment_legs(now)
        self._apply_chaos_logistics()

        self.ctx.generated_levels.add(self.LEVEL)
        level_elapsed = time.time() - level_start
        print(
            f"    Generated: {len(self.data['pick_wave_orders'])} pick_wave_orders, "
            f"{len(self.data['shipments'])} shipments, "
            f"{len(self.data['shipment_legs'])} legs ({level_elapsed:.1f}s)"
        )

    def _generate_pick_wave_orders(self, now: datetime) -> None:
        """Generate pick_wave_orders table (~180K)."""
        print("    Generating pick_wave_orders...")
        completed_statuses = {"shipped", "delivered"}
        order_status_by_id = {o["id"]: o["status"] for o in self.data["orders"]}

        pickable_orders = [
            oid for oid in self.ctx.order_ids.values()
            if order_status_by_id.get(oid) in completed_statuses
        ]

        pwo_count = 0
        for wave in self.data["pick_waves"]:
            wave_id = wave["id"]
            wave_status = wave["status"]
            target_orders = wave.get("total_orders", random.randint(10, 50))

            sample_size = min(target_orders, len(pickable_orders))
            if sample_size == 0:
                continue

            wave_orders = random.sample(pickable_orders, sample_size)

            for seq, order_id in enumerate(wave_orders, 1):
                if wave_status == "completed":
                    status = "staged"
                elif wave_status in ("loaded", "staged"):
                    status = "staged"
                elif wave_status in ("packing", "picking"):
                    status = random.choice(["picking", "picked", "packed"])
                else:
                    status = "pending"

                self.data["pick_wave_orders"].append(
                    {
                        "wave_id": wave_id,
                        "order_id": order_id,
                        "pick_sequence": seq,
                        "status": status,
                        "created_at": now,
                    }
                )
                pwo_count += 1

        print(f"      Generated {pwo_count:,} pick_wave_orders")

    def _get_sku_weights(self) -> dict:
        """Helper to get SKU weights for bin packing."""
        sku_weight_kg = {}
        for sku in self.data["skus"]:
            size_str = sku.get("size", "6oz")
            try:
                size_val = float(size_str.replace("oz", "").replace("ml", "").replace("g", ""))
                if "oz" in size_str:
                    sku_weight_kg[sku["id"]] = round(size_val * 0.028 * 24, 2)
                elif "ml" in size_str:
                    sku_weight_kg[sku["id"]] = round(size_val * 0.001 * 24, 2)
                else:
                    sku_weight_kg[sku["id"]] = 5.0
            except ValueError:
                sku_weight_kg[sku["id"]] = 5.0
        return sku_weight_kg

    def _generate_shipments(self, now: datetime) -> None:
        """
        Generate shipments table with SKU-Level Mass Balance and Emergent Logistics.
        Uses Demand-Pull distribution to ensure production matches SKU popularity.
        """
        print("    Generating shipments (SKU-Level Physics)...")
        plant_ids = list(self.ctx.plant_ids.values())
        dc_ids = list(self.ctx.dc_ids.values())
        carrier_ids = list(self.ctx.carrier_ids.values()) if self.ctx.carrier_ids else [1]
        route_ids = [r["id"] for r in self.data["routes"]] if self.data["routes"] else [1]
        location_ids = [loc["id"] for loc in self.data["retail_locations"]]

        chicago_dc_id = self.ctx.dc_ids.get("DC-NAM-CHI-001", dc_ids[0] if dc_ids else 1)
        sku_weights = self._get_sku_weights()

        # 1. Aggregate Demand per SKU
        demand_by_sku = {}
        for ol in self.data.get("order_lines", []):
            sid = ol.get("sku_id")
            demand_by_sku[sid] = demand_by_sku.get(sid, 0) + ol.get("quantity_cases", 0)

        # 2. Demand-Pull Supply Distribution
        # Formulas produce multiple SKUs; we allocate batch output based on SKU demand share
        supply_by_sku = {}
        formula_to_skus = LookupBuilder.build(self.data["skus"], key_field="formula_id")
        
        for b in self.data.get("batches", []):
            formula_id = b.get("formula_id")
            skus_for_formula = formula_to_skus.get(formula_id, [])
            if not skus_for_formula:
                continue
            
            total_cases = b.get("output_cases", 0)
            sku_ids = [s["id"] for s in skus_for_formula]
            
            # Calculate total demand for all SKUs of this formula
            formula_demand = sum(demand_by_sku.get(sid, 0) for sid in sku_ids)
            
            if formula_demand > 0:
                # Distribute proportional to demand (Demand-Pull)
                for sid in sku_ids:
                    share = demand_by_sku.get(sid, 0) / formula_demand
                    supply_by_sku[sid] = supply_by_sku.get(sid, 0) + int(total_cases * share)
            else:
                # Distribute equally if no demand
                cases_per_sku = total_cases // len(sku_ids)
                for sid in sku_ids:
                    supply_by_sku[sid] = supply_by_sku.get(sid, 0) + cases_per_sku

        # 3. Calculate Shippable (to stores) and Inventory
        shippable_to_store_by_sku = {}
        inventory_by_sku = {}
        all_skus = set(supply_by_sku.keys()) | set(demand_by_sku.keys())
        total_production_weight = 0

        for sid in all_skus:
            supply = supply_by_sku.get(sid, 0)
            demand = demand_by_sku.get(sid, 0)
            
            # Dynamic Safety Stock (5-12% target to maintain healthy 8-12x turns)
            is_promo = random.random() < 0.15
            ss_pct = random.uniform(0.12, 0.20) if is_promo else random.uniform(0.05, 0.10)
            
            available = max(0, supply - int(supply * ss_pct))
            shippable = min(available, demand)
            
            shippable_to_store_by_sku[sid] = shippable
            inventory_by_sku[sid] = supply - shippable
            total_production_weight += supply * sku_weights.get(sid, 10.0)

        self.inventory_by_sku = inventory_by_sku  # Save for inventory generation

        # 4. Emergent Logistics (Derive count from production volume)
        TRUCK_CAPACITY_KG = 20000
        TARGET_FILL_RATE = random.uniform(0.85, 0.95)
        num_shipments = max(100, int(total_production_weight / (TRUCK_CAPACITY_KG * TARGET_FILL_RATE)))
        
        print(f"    [Physics] Total Production Weight: {total_production_weight/1000:,.1f} tons")
        print(f"    [Physics] Derived {num_shipments} shipments (Avg Fill: {TARGET_FILL_RATE:.1%})")

        shipment_types = ["plant_to_dc", "dc_to_dc", "dc_to_store", "direct_to_store"]
        shipment_type_weights = [30, 10, 55, 5]
        shipment_statuses = ["planned", "loading", "in_transit", "at_port", "delivered", "exception"]
        shipment_status_weights = [5, 5, 15, 5, 65, 5]

        # Calculate target averages for scaling
        total_shippable_to_store = sum(shippable_to_store_by_sku.values())
        num_store_shipments = int(num_shipments * 0.60)
        avg_cases_store = total_shippable_to_store // num_store_shipments if num_store_shipments > 0 else 800
        
        total_inventory_cases = sum(inventory_by_sku.values())
        num_internal_shipments = num_shipments - num_store_shipments
        avg_cases_internal = total_inventory_cases // num_internal_shipments if num_internal_shipments > 0 else 1000

        shipment_id = 1
        for _ in range(num_shipments):
            shipment_num = f"SHIP-{self.ctx.base_year}-{shipment_id:08d}"
            shipment_type = random.choices(shipment_types, weights=shipment_type_weights)[0]
            is_store_bound = shipment_type in ("dc_to_store", "direct_to_store")

            if shipment_type == "plant_to_dc":
                origin_type = "plant"
                origin_id = random.choice(plant_ids)
                destination_type = "dc"
                destination_id = chicago_dc_id if random.random() < 0.40 else random.choice(dc_ids)
            elif shipment_type == "dc_to_dc":
                origin_type = "dc"
                origin_id = random.choice(dc_ids)
                destination_type = "dc"
                other_dcs = [d for d in dc_ids if d != origin_id]
                destination_id = random.choice(other_dcs) if other_dcs else origin_id
            elif shipment_type == "dc_to_store":
                origin_type = "dc"
                origin_id = chicago_dc_id if random.random() < 0.40 else random.choice(dc_ids)
                destination_type = "store"
                destination_id = random.choice(location_ids) if location_ids else 1
            else:  # direct_to_store
                origin_type = "plant"
                origin_id = random.choice(plant_ids)
                destination_type = "store"
                destination_id = random.choice(location_ids) if location_ids else 1

            ship_date = self.fake.date_between(
                start_date=date(self.ctx.base_year, 1, 1),
                end_date=date(self.ctx.base_year, 12, 31),
            )
            lead_days = random.randint(2, 14) if not is_store_bound else random.randint(1, 5)
            expected_delivery = ship_date + timedelta(days=lead_days)
            status = random.choices(shipment_statuses, weights=shipment_status_weights)[0]
            actual_delivery = expected_delivery + timedelta(days=random.randint(-2, 4)) if status == "delivered" else None

            # Size shipments to satisfy RealismMonitor mass balance
            if is_store_bound:
                total_cases = max(10, int(avg_cases_store * random.uniform(0.6, 1.4)))
            else:
                # Internal shipments move the stock that eventually becomes inventory or later shipments
                total_cases = max(10, int(avg_cases_internal * random.uniform(0.6, 1.4)))

            total_pallets = max(1, total_cases // 50)
            total_weight = round(total_cases * random.uniform(9, 13), 2)
            freight_cost = round(total_pallets * random.uniform(60, 180), 2)

            self.ctx.shipment_ids[shipment_num] = shipment_id
            self.data["shipments"].append(
                {
                    "id": shipment_id,
                    "shipment_number": shipment_num,
                    "shipment_type": shipment_type,
                    "origin_type": origin_type,
                    "origin_id": origin_id,
                    "destination_type": destination_type,
                    "destination_id": destination_id,
                    "order_id": random.choice(list(self.ctx.order_ids.values())) if random.random() < 0.7 else None,
                    "carrier_id": random.choice(list(self.ctx.carrier_ids.values())) if self.ctx.carrier_ids else 1,
                    "route_id": random.choice(route_ids) if route_ids else None,
                    "ship_date": ship_date,
                    "expected_delivery_date": expected_delivery,
                    "actual_delivery_date": actual_delivery,
                    "status": status,
                    "total_cases": total_cases,
                    "total_weight_kg": total_weight,
                    "total_pallets": total_pallets,
                    "freight_cost": freight_cost,
                    "currency": "USD",
                    "tracking_number": f"TRK{random.randint(1000000000, 9999999999)}",
                    "notes": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            shipment_id += 1

        print(f"      Generated {shipment_id - 1:,} shipments")
        self._generate_inventory(now)

    def _generate_inventory(self, now: datetime) -> None:
        """
        Generate inventory table based on calculated SKU-level remaining production.
        Ensures strict mass balance: Inventory = Production - Shipped (to stores).
        """
        inventory_by_sku = getattr(self, "inventory_by_sku", {})
        total_inv_cases = sum(inventory_by_sku.values())
        print(f"    Generating inventory (SKU-Level: {total_inv_cases:,} cases)...")

        batches_idx = LookupBuilder.build_unique(self.data["batches"], "id")
        dc_ids = list(self.ctx.dc_ids.values())
        batches_by_formula = LookupBuilder.build(self.data["batches"], key_field="formula_id")
        sku_formula_map = {sku["id"]: sku.get("formula_id") for sku in self.data["skus"]}

        inv_id = 1
        total_actual_cases = 0
        eligible_skus = [sid for sid, qty in inventory_by_sku.items() if qty > 0]

        for sid in eligible_skus:
            formula_id = sku_formula_map.get(sid)
            compatible_batches = [b["id"] for b in batches_by_formula.get(formula_id, [])]
            if not compatible_batches:
                continue

            remaining_qty = inventory_by_sku[sid]
            # Distribute across random DCs
            target_dcs = random.sample(dc_ids, min(random.randint(1, 3), len(dc_ids)))
            
            for dc_id in target_dcs:
                if remaining_qty <= 0:
                    break
                
                # Use a small number of lots to prevent record explosion
                num_lots = random.randint(1, min(2, len(compatible_batches)))
                selected_batches = random.sample(compatible_batches, num_lots)
                
                for batch_id in selected_batches:
                    if remaining_qty <= 0:
                        break
                    
                    batch = batches_idx.get(batch_id)
                    # Don't make individual records too large, but ensure we use all remaining_qty
                    qty_cases = min(remaining_qty, random.randint(200, 2000))
                    if batch_id == selected_batches[-1] and dc_id == target_dcs[-1]:
                        qty_cases = remaining_qty # Ensure full depletion

                    remaining_qty -= qty_cases
                    total_actual_cases += qty_cases

                    self.ctx.inventory_ids[(dc_id, sid, batch_id)] = inv_id
                    self.data["inventory"].append(
                        {
                            "id": inv_id,
                            "location_type": "dc",
                            "location_id": dc_id,
                            "sku_id": sid,
                            "batch_id": batch_id,
                            "quantity_cases": qty_cases,
                            "quantity_eaches": qty_cases * 12,
                            "lot_number": batch.get("batch_number", "LOT-000"),
                            "expiry_date": batch.get("expiry_date", date(2025, 12, 31)),
                            "receipt_date": batch.get("production_date", date(2024, 1, 1)) + timedelta(days=random.randint(1, 14)),
                            "aging_bucket": random.choice(["0-30", "31-60", "61-90", "90+"]),
                            "quality_status": "available",
                            "is_allocated": random.random() < 0.3,
                            "allocated_quantity": random.randint(0, qty_cases // 2) if random.random() < 0.3 else 0,
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
                    inv_id += 1

        # Apply phantom inventory quirk
        if self.ctx.quirks_manager and self.ctx.quirks_manager.is_enabled("phantom_inventory"):
            self.data["inventory"] = self.ctx.quirks_manager.apply_phantom_inventory(
                self.data["inventory"], reference_date=now
            )

        print(f"      Generated {inv_id - 1:,} inventory records ({total_actual_cases:,} cases)")



    def _generate_shipment_legs(self, now: datetime) -> None:
        """Generate shipment_legs table (~360K)."""
        print("    Generating shipment_legs...")
        segment_ids = list(self.ctx.route_segment_ids.values())
        carrier_ids = list(self.ctx.carrier_ids.values()) if self.ctx.carrier_ids else [1]

        leg_id = 1
        leg_statuses = ["planned", "departed", "in_transit", "arrived", "exception"]
        leg_status_weights = [5, 5, 10, 75, 5]

        for shipment in self.data["shipments"]:
            ship_id = shipment["id"]
            ship_type = shipment["shipment_type"]
            ship_date = shipment["ship_date"]

            # Number of legs based on shipment type
            if ship_type == "plant_to_dc":
                num_legs = random.randint(1, 3)
            elif ship_type == "dc_to_dc":
                num_legs = random.randint(1, 2)
            elif ship_type == "dc_to_store":
                num_legs = 1
            else:  # direct_to_store
                num_legs = random.randint(2, 4)

            current_datetime = datetime.combine(ship_date, datetime.min.time()) + timedelta(
                hours=random.randint(6, 18)
            )

            for leg_seq in range(1, num_legs + 1):
                segment_id = random.choice(segment_ids)
                carrier_id = random.choice(carrier_ids)

                transit_hours = random.randint(4, 48)
                departure = current_datetime
                arrival = departure + timedelta(hours=transit_hours)
                actual_transit = transit_hours + random.uniform(-2, 4)

                status = random.choices(leg_statuses, weights=leg_status_weights)[0]
                freight = round(random.uniform(100, 500), 2)

                self.data["shipment_legs"].append(
                    {
                        "id": leg_id,
                        "shipment_id": ship_id,
                        "segment_id": segment_id,
                        "leg_sequence": leg_seq,
                        "carrier_id": carrier_id,
                        "departure_datetime": departure,
                        "arrival_datetime": arrival,
                        "actual_transit_hours": round(actual_transit, 2),
                        "status": status,
                        "freight_cost": freight,
                        "tracking_number": f"LEG{leg_id:010d}",
                        "notes": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                leg_id += 1
                current_datetime = arrival + timedelta(hours=random.randint(1, 4))

        print(f"      Generated {leg_id - 1:,} shipment_legs")

    def _apply_chaos_logistics(self) -> None:
        """Apply chaos injection to logistics (port strike, congestion)."""
        # RSK-LOG-002: Port strike delays
        if self.ctx.risk_manager:
            port_overrides = self.ctx.risk_manager.get_port_strike_overrides()
            if port_overrides:
                affected_port_codes = port_overrides.get("affected_ports", ["USLAX"])
                delay_multiplier = port_overrides.get("delay_multiplier", 4.0)

                affected_port_ids = {
                    self.ctx.port_ids.get(code)
                    for code in affected_port_codes
                    if code in self.ctx.port_ids
                }

                segment_lookup = {seg["id"]: seg for seg in self.data["route_segments"]}

                strike_count = 0
                for leg in self.data["shipment_legs"]:
                    seg_id = leg.get("segment_id")
                    if seg_id and seg_id in segment_lookup:
                        seg = segment_lookup[seg_id]
                        origin_is_port = (
                            seg.get("origin_type") == "port"
                            and seg.get("origin_id") in affected_port_ids
                        )
                        dest_is_port = (
                            seg.get("destination_type") == "port"
                            and seg.get("destination_id") in affected_port_ids
                        )
                        if origin_is_port or dest_is_port:
                            current_transit = leg.get("actual_transit_hours", 24)
                            extra_delay = current_transit * (delay_multiplier - 1)
                            leg["actual_transit_hours"] = round(current_transit + extra_delay, 2)
                            leg["status"] = "delayed"
                            leg["notes"] = f"RISK EVENT RSK-LOG-002: Port strike delay (+{extra_delay:.1f}h)"
                            strike_count += 1

                if strike_count > 0:
                    print(f"    [Risk] RSK-LOG-002: {strike_count} shipment legs delayed by port strike")

        # Port congestion flicker quirk
        if self.ctx.quirks_manager and self.ctx.quirks_manager.is_enabled("port_congestion_flicker"):
            segment_lookup = {seg["id"]: seg for seg in self.data["route_segments"]}
            self.data["shipment_legs"] = self.ctx.quirks_manager.apply_port_congestion(
                self.data["shipment_legs"],
                segment_lookup=segment_lookup,
                port_ids=self.ctx.port_ids,
            )
            congestion_count = sum(
                1 for leg in self.data["shipment_legs"] if leg.get("congestion_affected")
            )
            if congestion_count > 0:
                print(f"    [Quirk] Port congestion flicker: {congestion_count} legs with correlated delays")


class Level11Generator(BaseLevelGenerator):
    """
    Generate Level 11 shipment lines.

    Level 11 contains shipment_lines with batch tracking.
    """

    LEVEL = 11

    def generate(self) -> None:
        """Generate all Level 11 tables."""
        print("  Level 11: Shipment lines...")
        level_start = time.time()
        now = datetime.now()

        self._generate_shipment_lines(now)

        self.ctx.generated_levels.add(self.LEVEL)
        level_elapsed = time.time() - level_start
        print(f"    Generated: {len(self.data['shipment_lines'])} shipment_lines ({level_elapsed:.1f}s)")

    def _generate_shipment_lines(self, now: datetime) -> None:
        """Generate shipment_lines table (~1M) using vectorized generator."""
        print("    Generating shipment_lines...")

        # Prepare SKU data
        sku_ids = list(self.ctx.sku_ids.values())
        sku_weight_kg = {}
        for sku in self.data["skus"]:
            size_str = sku.get("size", "6oz")
            try:
                size_val = float(size_str.replace("oz", "").replace("ml", "").replace("g", ""))
                if "oz" in size_str:
                    sku_weight_kg[sku["id"]] = round(size_val * 0.028 * 24, 2)
                elif "ml" in size_str:
                    sku_weight_kg[sku["id"]] = round(size_val * 0.001 * 24, 2)
                else:
                    sku_weight_kg[sku["id"]] = 5.0
            except ValueError:
                sku_weight_kg[sku["id"]] = 5.0

        # Prepare batch data
        batch_ids = [b["id"] for b in self.data["batches"]]
        batch_output_cases = {b["id"]: b.get("output_cases", 1000) for b in self.data["batches"]}
        batch_numbers = {b["id"]: b.get("batch_number", f"LOT-{b['id']:08d}") for b in self.data["batches"]}
        batch_expiry = {b["id"]: b.get("expiry_date") for b in self.data["batches"]}

        # Extract shipment arrays
        shipments = self.data["shipments"]
        shipment_ids = np.array([s["id"] for s in shipments], dtype=np.int64)
        total_cases = np.array([s.get("total_cases", 100) for s in shipments], dtype=np.int32)
        ship_dates = np.array([
            np.datetime64(s.get("ship_date", date(self.ctx.base_year, 6, 15)), "D")
            for s in shipments
        ], dtype="datetime64[D]")

        # Create and configure vectorized generator
        generator = ShipmentLinesGenerator(seed=self.ctx.seed, base_year=self.ctx.base_year)
        generator.configure(
            sku_ids=sku_ids,
            batch_ids=batch_ids,
            sku_weight_kg=sku_weight_kg,
            batch_output_cases=batch_output_cases,
            batch_numbers=batch_numbers,
            batch_expiry=batch_expiry,
        )

        # Generate all shipment lines in one vectorized call
        lines_array = generator.generate_for_shipments(
            shipment_ids=shipment_ids,
            total_cases=total_cases,
            ship_dates=ship_dates,
            now=now,
        )

        # Convert to list of dicts
        self.data["shipment_lines"] = structured_to_dicts(lines_array)

        print(f"      Generated {len(self.data['shipment_lines']):,} shipment_lines")
