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

    def _generate_shipments(self, now: datetime) -> None:
        """Generate shipments table (~180K)."""
        print("    Generating shipments...")
        plant_ids = list(self.ctx.plant_ids.values())
        dc_ids = list(self.ctx.dc_ids.values())
        carrier_ids = list(self.ctx.carrier_ids.values()) if self.ctx.carrier_ids else [1]
        route_ids = [r["id"] for r in self.data["routes"]] if self.data["routes"] else [1]
        location_ids = [loc["id"] for loc in self.data["retail_locations"]]
        order_ids = list(self.ctx.order_ids.values())

        chicago_dc_id = self.ctx.dc_ids.get("DC-NAM-CHI-001", dc_ids[0] if dc_ids else 1)

        shipment_types = ["plant_to_dc", "dc_to_dc", "dc_to_store", "direct_to_store"]
        shipment_type_weights = [30, 10, 55, 5]
        shipment_statuses = ["planned", "loading", "in_transit", "at_port", "delivered", "exception"]
        shipment_status_weights = [5, 5, 15, 5, 65, 5]

        shipment_id = 1
        for _ in range(180000):
            shipment_num = f"SHIP-{self.ctx.base_year}-{shipment_id:08d}"
            shipment_type = random.choices(shipment_types, weights=shipment_type_weights)[0]

            if shipment_type == "plant_to_dc":
                origin_type = "plant"
                origin_id = random.choice(plant_ids)
                destination_type = "dc"
                # 40% of plant→DC go to Chicago (bottleneck)
                destination_id = chicago_dc_id if random.random() < 0.40 else random.choice(dc_ids)
            elif shipment_type == "dc_to_dc":
                origin_type = "dc"
                origin_id = random.choice(dc_ids)
                destination_type = "dc"
                other_dcs = [d for d in dc_ids if d != origin_id]
                destination_id = random.choice(other_dcs) if other_dcs else origin_id
            elif shipment_type == "dc_to_store":
                origin_type = "dc"
                # 40% originate from Chicago DC (bottleneck)
                origin_id = chicago_dc_id if random.random() < 0.40 else random.choice(dc_ids)
                destination_type = "store"
                destination_id = random.choice(location_ids) if location_ids else 1
            else:  # direct_to_store
                origin_type = "plant"
                origin_id = random.choice(plant_ids)
                destination_type = "store"
                destination_id = random.choice(location_ids) if location_ids else 1

            # Link to an order (70%)
            order_id = random.choice(order_ids) if random.random() < 0.70 and order_ids else None

            ship_date = self.fake.date_between(
                start_date=date(self.ctx.base_year, 1, 1),
                end_date=date(self.ctx.base_year, 12, 31),
            )
            lead_days = (
                random.randint(2, 21)
                if shipment_type in ("plant_to_dc", "dc_to_dc")
                else random.randint(1, 7)
            )
            expected_delivery = ship_date + timedelta(days=lead_days)

            status = random.choices(shipment_statuses, weights=shipment_status_weights)[0]
            actual_delivery = None
            if status == "delivered":
                delay = random.randint(-2, 5)
                actual_delivery = expected_delivery + timedelta(days=delay)

            total_cases = random.randint(50, 2000)
            total_pallets = max(1, total_cases // 50)
            total_weight = round(total_cases * random.uniform(8, 15), 2)
            freight_cost = round(total_pallets * random.uniform(50, 200), 2)

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
                    "order_id": order_id,
                    "carrier_id": random.choice(carrier_ids),
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
