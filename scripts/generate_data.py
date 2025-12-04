#!/usr/bin/env python3
"""
Generate synthetic supply chain data for Virtual Graph POC.

Target data volumes:
- 500 suppliers (tiered: 50 T1, 150 T2, 300 T3)
- 5,000 parts with BOM hierarchy (avg depth: 5 levels)
- 50 facilities with transport network
- 20,000 orders with shipments
- ~130K total rows

This generates realistic "enterprise messiness":
- Some nullable FKs
- Realistic distributions
- Named entities for testing
"""

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

# Output path
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "seed.sql"


def sql_str(val: str | None) -> str:
    """Escape string for SQL."""
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
    """Format date for SQL."""
    if val is None:
        return "NULL"
    return f"'{val.isoformat()}'"


def sql_timestamp(val: datetime | None) -> str:
    """Format timestamp for SQL."""
    if val is None:
        return "NULL"
    return f"'{val.isoformat()}'"


class SupplyChainGenerator:
    """Generate interconnected supply chain data."""

    def __init__(self):
        self.suppliers: list[dict] = []
        self.supplier_relationships: list[dict] = []
        self.parts: list[dict] = []
        self.bom: list[dict] = []
        self.part_suppliers: list[dict] = []
        self.products: list[dict] = []
        self.product_components: list[dict] = []
        self.facilities: list[dict] = []
        self.transport_routes: list[dict] = []
        self.inventory: list[dict] = []
        self.customers: list[dict] = []
        self.orders: list[dict] = []
        self.order_items: list[dict] = []
        self.shipments: list[dict] = []
        self.supplier_certifications: list[dict] = []

        # Track IDs for relationships
        self.supplier_ids_by_tier: dict[int, list[int]] = {1: [], 2: [], 3: []}
        self.part_ids: list[int] = []
        self.leaf_part_ids: list[int] = []  # Parts with no children (raw materials)
        self.top_part_ids: list[int] = []  # Parts that go into products

    def generate_all(self):
        """Generate all data in dependency order."""
        print("Generating suppliers...")
        self.generate_suppliers(500)

        print("Generating supplier relationships...")
        self.generate_supplier_relationships()

        print("Generating parts with BOM hierarchy...")
        self.generate_parts_with_bom(5000)

        print("Generating part suppliers...")
        self.generate_part_suppliers()

        print("Generating products...")
        self.generate_products(200)

        print("Generating facilities...")
        self.generate_facilities(50)

        print("Generating transport routes...")
        self.generate_transport_routes()

        print("Generating customers...")
        self.generate_customers(1000)

        print("Generating orders...")
        self.generate_orders(20000)

        print("Generating inventory...")
        self.generate_inventory()

        print("Generating supplier certifications...")
        self.generate_supplier_certifications()

    def generate_suppliers(self, count: int):
        """Generate tiered suppliers: 10% T1, 30% T2, 60% T3."""
        tier_counts = {1: int(count * 0.10), 2: int(count * 0.30), 3: int(count * 0.60)}

        # Ensure we hit exact count
        tier_counts[3] += count - sum(tier_counts.values())

        supplier_id = 1
        countries = ["USA", "China", "Germany", "Japan", "Mexico", "Canada", "UK", "Taiwan", "South Korea", "India"]
        ratings = ["AAA", "AA", "A", "BBB", "BB", "B"]

        # Some named suppliers for testing
        named_suppliers = [
            ("Acme Corp", 1, "USA"),
            ("GlobalTech Industries", 1, "China"),
            ("Precision Parts Ltd", 1, "Germany"),
            ("Pacific Components", 2, "Japan"),
            ("Northern Materials", 2, "Canada"),
            ("Apex Manufacturing", 2, "Mexico"),
            ("Eastern Electronics", 3, "Taiwan"),
            ("Delta Supplies", 3, "India"),
        ]

        for name, tier, country in named_suppliers:
            self.suppliers.append({
                "id": supplier_id,
                "supplier_code": f"SUP{supplier_id:05d}",
                "name": name,
                "tier": tier,
                "country": country,
                "city": fake.city(),
                "contact_email": fake.company_email(),
                "credit_rating": random.choice(ratings[:3]) if tier == 1 else random.choice(ratings),
                "is_active": True,
                "created_by": "system",
            })
            self.supplier_ids_by_tier[tier].append(supplier_id)
            tier_counts[tier] -= 1
            supplier_id += 1

        # Generate remaining suppliers
        for tier, remaining in tier_counts.items():
            for _ in range(remaining):
                self.suppliers.append({
                    "id": supplier_id,
                    "supplier_code": f"SUP{supplier_id:05d}",
                    "name": fake.company(),
                    "tier": tier,
                    "country": random.choice(countries),
                    "city": fake.city(),
                    "contact_email": fake.company_email() if random.random() > 0.1 else None,
                    "credit_rating": random.choice(ratings[:3]) if tier == 1 else random.choice(ratings),
                    "is_active": random.random() > 0.05,  # 5% inactive
                    "created_by": random.choice(["system", "admin", "import"]),
                })
                self.supplier_ids_by_tier[tier].append(supplier_id)
                supplier_id += 1

    def generate_supplier_relationships(self):
        """Generate tier relationships: T3 → T2 → T1."""
        rel_id = 1

        # T3 suppliers sell to T2 suppliers
        for t3_id in self.supplier_ids_by_tier[3]:
            # Each T3 sells to 1-3 T2 suppliers
            num_buyers = random.randint(1, 3)
            buyers = random.sample(self.supplier_ids_by_tier[2], min(num_buyers, len(self.supplier_ids_by_tier[2])))
            for t2_id in buyers:
                self.supplier_relationships.append({
                    "id": rel_id,
                    "seller_id": t3_id,
                    "buyer_id": t2_id,
                    "relationship_type": "supplies",
                    "contract_start_date": fake.date_between(start_date="-3y", end_date="-1y"),
                    "is_primary": random.random() > 0.7,
                })
                rel_id += 1

        # T2 suppliers sell to T1 suppliers
        for t2_id in self.supplier_ids_by_tier[2]:
            # Each T2 sells to 1-2 T1 suppliers
            num_buyers = random.randint(1, 2)
            buyers = random.sample(self.supplier_ids_by_tier[1], min(num_buyers, len(self.supplier_ids_by_tier[1])))
            for t1_id in buyers:
                self.supplier_relationships.append({
                    "id": rel_id,
                    "seller_id": t2_id,
                    "buyer_id": t1_id,
                    "relationship_type": "supplies",
                    "contract_start_date": fake.date_between(start_date="-3y", end_date="-1y"),
                    "is_primary": random.random() > 0.7,
                })
                rel_id += 1

    def generate_parts_with_bom(self, count: int):
        """
        Generate parts with realistic BOM hierarchy.

        Structure:
        - Level 0 (raw materials): 40% of parts, no children
        - Level 1-2 (subassemblies): 40% of parts
        - Level 3-5 (assemblies): 20% of parts

        Average depth target: 5 levels
        """
        categories = [
            "Raw Material", "Electronic", "Mechanical", "Fastener",
            "Subassembly", "Assembly", "Sensor", "Motor", "Housing", "Cable"
        ]

        # Generate parts
        for part_id in range(1, count + 1):
            category = random.choice(categories)
            self.parts.append({
                "id": part_id,
                "part_number": f"PRT-{part_id:06d}",
                "description": f"{fake.word().title()} {category} Component",
                "category": category,
                "unit_cost": round(random.uniform(0.10, 500.00), 2),
                "weight_kg": round(random.uniform(0.001, 50.0), 3),
                "lead_time_days": random.randint(1, 90),
                "primary_supplier_id": random.choice(
                    self.supplier_ids_by_tier[random.choice([1, 2, 3])]
                ),
                "is_critical": random.random() > 0.9,
                "min_stock_level": random.randint(10, 1000),
            })
            self.part_ids.append(part_id)

        # Build BOM hierarchy
        # First, categorize parts by level
        raw_material_count = int(count * 0.40)
        subassembly_count = int(count * 0.40)
        assembly_count = count - raw_material_count - subassembly_count

        raw_materials = self.part_ids[:raw_material_count]
        subassemblies = self.part_ids[raw_material_count:raw_material_count + subassembly_count]
        assemblies = self.part_ids[raw_material_count + subassembly_count:]

        self.leaf_part_ids = raw_materials.copy()
        self.top_part_ids = assemblies[-200:]  # Top 200 assemblies can be products

        bom_id = 1

        # Subassemblies use raw materials (level 1)
        for sub_id in subassemblies:
            num_components = random.randint(2, 8)
            components = random.sample(raw_materials, min(num_components, len(raw_materials)))
            for seq, comp_id in enumerate(components, 1):
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": sub_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 10),
                    "unit": random.choice(["each", "kg", "m", "L"]),
                    "is_optional": random.random() > 0.9,
                    "assembly_sequence": seq,
                })
                bom_id += 1

        # Assemblies use subassemblies and some raw materials (levels 2-5)
        # Split assemblies into levels
        level_2 = assemblies[:len(assemblies)//3]
        level_3 = assemblies[len(assemblies)//3:2*len(assemblies)//3]
        level_4_5 = assemblies[2*len(assemblies)//3:]

        # Level 2: Use subassemblies
        for asm_id in level_2:
            num_components = random.randint(2, 6)
            components = random.sample(subassemblies, min(num_components, len(subassemblies)))
            # Maybe add some raw materials too
            if random.random() > 0.5:
                components.extend(random.sample(raw_materials, random.randint(1, 3)))
            for seq, comp_id in enumerate(components, 1):
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": asm_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 5),
                    "unit": "each",
                    "is_optional": random.random() > 0.95,
                    "assembly_sequence": seq,
                })
                bom_id += 1

        # Level 3: Use level 2 assemblies
        for asm_id in level_3:
            num_components = random.randint(2, 5)
            components = random.sample(level_2, min(num_components, len(level_2)))
            if random.random() > 0.5:
                components.extend(random.sample(subassemblies, random.randint(1, 2)))
            for seq, comp_id in enumerate(components, 1):
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": asm_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 4),
                    "unit": "each",
                    "is_optional": random.random() > 0.95,
                    "assembly_sequence": seq,
                })
                bom_id += 1

        # Level 4-5: Use level 3 assemblies
        for asm_id in level_4_5:
            num_components = random.randint(2, 4)
            components = random.sample(level_3, min(num_components, len(level_3)))
            if random.random() > 0.7:
                components.extend(random.sample(level_2, random.randint(1, 2)))
            for seq, comp_id in enumerate(components, 1):
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": asm_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 3),
                    "unit": "each",
                    "is_optional": random.random() > 0.95,
                    "assembly_sequence": seq,
                })
                bom_id += 1

        # Add some named parts for testing
        named_parts = [
            (count + 1, "TURBO-ENC-001", "Turbo Encabulator Main Assembly"),
            (count + 2, "FLUX-CAP-001", "Flux Capacitor Module"),
            (count + 3, "WIDGET-A", "Standard Widget Type A"),
        ]
        for part_id, part_number, description in named_parts:
            self.parts.append({
                "id": part_id,
                "part_number": part_number,
                "description": description,
                "category": "Assembly",
                "unit_cost": round(random.uniform(100, 1000), 2),
                "weight_kg": round(random.uniform(1, 20), 3),
                "lead_time_days": random.randint(14, 60),
                "primary_supplier_id": random.choice(self.supplier_ids_by_tier[1]),
                "is_critical": True,
                "min_stock_level": 50,
            })
            self.top_part_ids.append(part_id)
            # Add BOM for named parts (use existing high-level assemblies)
            for seq, comp_id in enumerate(random.sample(level_4_5, min(5, len(level_4_5))), 1):
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": part_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 3),
                    "unit": "each",
                    "is_optional": False,
                    "assembly_sequence": seq,
                })
                bom_id += 1

    def generate_part_suppliers(self):
        """Generate alternate suppliers for parts."""
        ps_id = 1
        for part in self.parts:
            # Primary supplier already set, add 0-3 alternates
            num_alternates = random.randint(0, 3)
            if num_alternates > 0:
                primary_id = part.get("primary_supplier_id")
                available = [s["id"] for s in self.suppliers if s["id"] != primary_id]
                alternates = random.sample(available, min(num_alternates, len(available)))
                for supp_id in alternates:
                    self.part_suppliers.append({
                        "id": ps_id,
                        "part_id": part["id"],
                        "supplier_id": supp_id,
                        "supplier_part_number": f"SP-{fake.bothify('??###')}",
                        "unit_cost": round(part["unit_cost"] * random.uniform(0.8, 1.3), 2),
                        "lead_time_days": part["lead_time_days"] + random.randint(-10, 20),
                        "is_approved": random.random() > 0.1,
                        "approval_date": fake.date_between(start_date="-2y", end_date="today") if random.random() > 0.1 else None,
                    })
                    ps_id += 1

    def generate_products(self, count: int):
        """Generate finished products linked to top-level parts."""
        categories = ["Electronics", "Industrial", "Consumer", "Automotive", "Medical"]

        # Named products for testing
        named_products = [
            ("TURBO-001", "Turbo Encabulator"),
            ("FLUX-001", "Flux Capacitor"),
            ("WIDGET-STD", "Standard Widget"),
        ]

        for i, (sku, name) in enumerate(named_products):
            self.products.append({
                "id": i + 1,
                "sku": sku,
                "name": name,
                "description": f"The famous {name} - industry standard equipment",
                "category": "Industrial",
                "list_price": round(random.uniform(500, 5000), 2),
                "is_active": True,
                "launch_date": fake.date_between(start_date="-5y", end_date="-1y"),
            })

        start_id = len(named_products) + 1
        for prod_id in range(start_id, count + 1):
            self.products.append({
                "id": prod_id,
                "sku": f"SKU-{prod_id:05d}",
                "name": f"{fake.word().title()} {fake.word().title()} {random.choice(['Pro', 'Plus', 'Max', 'Standard', ''])}".strip(),
                "description": fake.sentence(nb_words=10),
                "category": random.choice(categories),
                "list_price": round(random.uniform(50, 10000), 2),
                "is_active": random.random() > 0.1,
                "launch_date": fake.date_between(start_date="-5y", end_date="today"),
                "discontinued_date": fake.date_between(start_date="-1y", end_date="today") if random.random() > 0.9 else None,
            })

        # Link products to top-level parts
        pc_id = 1
        for product in self.products:
            num_parts = random.randint(1, 5)
            parts = random.sample(self.top_part_ids, min(num_parts, len(self.top_part_ids)))
            for part_id in parts:
                self.product_components.append({
                    "id": pc_id,
                    "product_id": product["id"],
                    "part_id": part_id,
                    "quantity": random.randint(1, 3),
                    "is_required": random.random() > 0.1,
                })
                pc_id += 1

    def generate_facilities(self, count: int):
        """Generate warehouses, factories, and distribution centers."""
        facility_types = ["warehouse", "factory", "distribution_center"]

        # Named facilities for testing
        named_facilities = [
            ("FAC-CHI", "Chicago Warehouse", "warehouse", "Chicago", "IL", "USA"),
            ("FAC-LA", "LA Distribution Center", "distribution_center", "Los Angeles", "CA", "USA"),
            ("FAC-NYC", "New York Factory", "factory", "New York", "NY", "USA"),
            ("FAC-SH", "Shanghai Hub", "distribution_center", "Shanghai", None, "China"),
            ("FAC-MUN", "Munich Factory", "factory", "Munich", "Bavaria", "Germany"),
        ]

        for i, (code, name, ftype, city, state, country) in enumerate(named_facilities):
            self.facilities.append({
                "id": i + 1,
                "facility_code": code,
                "name": name,
                "facility_type": ftype,
                "city": city,
                "state": state,
                "country": country,
                "latitude": round(random.uniform(-90, 90), 6),
                "longitude": round(random.uniform(-180, 180), 6),
                "capacity_units": random.randint(10000, 100000),
                "is_active": True,
            })

        start_id = len(named_facilities) + 1
        us_states = ["CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]
        countries = ["USA", "China", "Germany", "Japan", "Mexico", "Canada"]

        for fac_id in range(start_id, count + 1):
            country = random.choice(countries)
            self.facilities.append({
                "id": fac_id,
                "facility_code": f"FAC-{fac_id:03d}",
                "name": f"{fake.city()} {random.choice(['Warehouse', 'Distribution Center', 'Factory', 'Hub'])}",
                "facility_type": random.choice(facility_types),
                "city": fake.city(),
                "state": random.choice(us_states) if country == "USA" else None,
                "country": country,
                "latitude": round(random.uniform(-90, 90), 6),
                "longitude": round(random.uniform(-180, 180), 6),
                "capacity_units": random.randint(5000, 100000),
                "is_active": random.random() > 0.05,
            })

    def generate_transport_routes(self):
        """Generate transport routes between facilities (connected network)."""
        route_id = 1
        facility_ids = [f["id"] for f in self.facilities]
        modes = ["truck", "rail", "air", "sea"]

        # Ensure network is connected: create a spanning tree first
        connected = {facility_ids[0]}
        unconnected = set(facility_ids[1:])

        while unconnected:
            from_id = random.choice(list(connected))
            to_id = random.choice(list(unconnected))
            unconnected.remove(to_id)
            connected.add(to_id)

            # Create bidirectional routes
            for origin, dest in [(from_id, to_id), (to_id, from_id)]:
                mode = random.choice(modes)
                self.transport_routes.append({
                    "id": route_id,
                    "origin_facility_id": origin,
                    "destination_facility_id": dest,
                    "transport_mode": mode,
                    "distance_km": round(random.uniform(100, 5000), 2),
                    "transit_time_hours": round(random.uniform(4, 120), 2),
                    "cost_usd": round(random.uniform(100, 10000), 2),
                    "capacity_tons": round(random.uniform(10, 1000), 2),
                    "is_active": True,
                })
                route_id += 1

        # Add additional routes for more connectivity
        existing_routes = {(r["origin_facility_id"], r["destination_facility_id"], r["transport_mode"])
                          for r in self.transport_routes}

        for _ in range(len(facility_ids) * 2):  # Add ~2x more routes
            from_id = random.choice(facility_ids)
            to_id = random.choice([f for f in facility_ids if f != from_id])
            mode = random.choice(modes)

            if (from_id, to_id, mode) not in existing_routes:
                existing_routes.add((from_id, to_id, mode))
                self.transport_routes.append({
                    "id": route_id,
                    "origin_facility_id": from_id,
                    "destination_facility_id": to_id,
                    "transport_mode": mode,
                    "distance_km": round(random.uniform(100, 5000), 2),
                    "transit_time_hours": round(random.uniform(4, 120), 2),
                    "cost_usd": round(random.uniform(100, 10000), 2),
                    "capacity_tons": round(random.uniform(10, 1000), 2),
                    "is_active": random.random() > 0.1,
                })
                route_id += 1

    def generate_customers(self, count: int):
        """Generate customers."""
        customer_types = ["retail", "wholesale", "enterprise"]

        for cust_id in range(1, count + 1):
            self.customers.append({
                "id": cust_id,
                "customer_code": f"CUST-{cust_id:05d}",
                "name": fake.company() if random.random() > 0.3 else fake.name(),
                "customer_type": random.choice(customer_types),
                "contact_email": fake.email(),
                "shipping_address": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr() if random.random() > 0.3 else None,
                "country": random.choice(["USA", "Canada", "UK", "Germany", "France"]),
            })

    def generate_orders(self, count: int):
        """Generate orders with items and shipments."""
        statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
        facility_ids = [f["id"] for f in self.facilities]
        product_ids = [p["id"] for p in self.products]
        customer_ids = [c["id"] for c in self.customers]

        order_item_id = 1
        shipment_id = 1

        for order_id in range(1, count + 1):
            order_date = fake.date_time_between(start_date="-2y", end_date="now")
            status = random.choice(statuses)

            shipped_date = None
            if status in ["shipped", "delivered"]:
                shipped_date = order_date + timedelta(days=random.randint(1, 7))

            self.orders.append({
                "id": order_id,
                "order_number": f"ORD-{order_id:08d}",
                "customer_id": random.choice(customer_ids),
                "order_date": order_date,
                "required_date": (order_date + timedelta(days=random.randint(7, 30))).date(),
                "shipped_date": shipped_date,
                "status": status,
                "shipping_facility_id": random.choice(facility_ids),
                "total_amount": 0,  # Will calculate
                "shipping_cost": round(random.uniform(10, 200), 2),
            })

            # Generate 1-5 order items
            num_items = random.randint(1, 5)
            total = Decimal("0")
            for _ in range(num_items):
                quantity = random.randint(1, 10)
                unit_price = round(random.uniform(10, 500), 2)
                discount = round(random.uniform(0, 15), 2) if random.random() > 0.7 else 0

                self.order_items.append({
                    "id": order_item_id,
                    "order_id": order_id,
                    "product_id": random.choice(product_ids),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_percent": discount,
                })
                total += Decimal(str(quantity * unit_price * (1 - discount / 100)))
                order_item_id += 1

            self.orders[-1]["total_amount"] = round(float(total), 2)

            # Generate shipment for shipped orders
            if status in ["shipped", "delivered"]:
                origin = random.choice(facility_ids)
                dest = random.choice([f for f in facility_ids if f != origin])

                # Find a route if exists
                route = next(
                    (r for r in self.transport_routes
                     if r["origin_facility_id"] == origin and r["destination_facility_id"] == dest),
                    None
                )

                self.shipments.append({
                    "id": shipment_id,
                    "shipment_number": f"SHP-{shipment_id:08d}",
                    "order_id": order_id,
                    "origin_facility_id": origin,
                    "destination_facility_id": dest,
                    "transport_route_id": route["id"] if route else None,
                    "carrier": fake.company() + " Logistics",
                    "tracking_number": fake.bothify("??#########??"),
                    "status": "delivered" if status == "delivered" else "in_transit",
                    "shipped_at": shipped_date,
                    "delivered_at": shipped_date + timedelta(days=random.randint(1, 14)) if status == "delivered" else None,
                    "weight_kg": round(random.uniform(0.5, 100), 2),
                    "cost_usd": round(random.uniform(20, 500), 2),
                })
                shipment_id += 1

    def generate_inventory(self):
        """Generate inventory records for parts at facilities."""
        inv_id = 1
        facility_ids = [f["id"] for f in self.facilities if f["facility_type"] == "warehouse"]

        # Not all parts at all facilities
        for part in self.parts:
            # Part exists at 1-3 warehouses
            num_locations = random.randint(1, min(3, len(facility_ids)))
            locations = random.sample(facility_ids, num_locations)

            for fac_id in locations:
                self.inventory.append({
                    "id": inv_id,
                    "facility_id": fac_id,
                    "part_id": part["id"],
                    "quantity_on_hand": random.randint(0, 1000),
                    "quantity_reserved": random.randint(0, 100),
                    "quantity_on_order": random.randint(0, 500) if random.random() > 0.5 else 0,
                    "reorder_point": part["min_stock_level"],
                    "last_counted_at": fake.date_time_between(start_date="-6m", end_date="now") if random.random() > 0.3 else None,
                })
                inv_id += 1

    def generate_supplier_certifications(self):
        """Generate certifications for suppliers."""
        cert_types = ["ISO9001", "ISO14001", "ISO27001", "AS9100", "IATF16949"]
        cert_id = 1

        for supplier in self.suppliers:
            # 70% of suppliers have at least one certification
            if random.random() > 0.3:
                num_certs = random.randint(1, 3)
                certs = random.sample(cert_types, min(num_certs, len(cert_types)))
                for cert_type in certs:
                    issued = fake.date_between(start_date="-5y", end_date="-1y")
                    self.supplier_certifications.append({
                        "id": cert_id,
                        "supplier_id": supplier["id"],
                        "certification_type": cert_type,
                        "certification_number": fake.bothify("CERT-####-????"),
                        "issued_date": issued,
                        "expiry_date": issued + timedelta(days=365 * 3),
                        "is_valid": random.random() > 0.1,
                    })
                    cert_id += 1

    def to_sql(self) -> str:
        """Generate SQL INSERT statements."""
        lines = [
            "-- Generated seed data for Virtual Graph POC",
            "-- DO NOT EDIT - regenerate with scripts/generate_data.py",
            "",
            "BEGIN;",
            "",
        ]

        # Suppliers
        lines.append("-- Suppliers")
        for s in self.suppliers:
            lines.append(
                f"INSERT INTO suppliers (id, supplier_code, name, tier, country, city, contact_email, credit_rating, is_active, created_by) "
                f"VALUES ({s['id']}, {sql_str(s['supplier_code'])}, {sql_str(s['name'])}, {s['tier']}, "
                f"{sql_str(s['country'])}, {sql_str(s['city'])}, {sql_str(s.get('contact_email'))}, "
                f"{sql_str(s['credit_rating'])}, {sql_bool(s['is_active'])}, {sql_str(s.get('created_by'))});"
            )
        lines.append(f"SELECT setval('suppliers_id_seq', {max(s['id'] for s in self.suppliers)});")
        lines.append("")

        # Supplier relationships
        lines.append("-- Supplier Relationships")
        for sr in self.supplier_relationships:
            lines.append(
                f"INSERT INTO supplier_relationships (id, seller_id, buyer_id, relationship_type, contract_start_date, is_primary) "
                f"VALUES ({sr['id']}, {sr['seller_id']}, {sr['buyer_id']}, {sql_str(sr['relationship_type'])}, "
                f"{sql_date(sr.get('contract_start_date'))}, {sql_bool(sr['is_primary'])});"
            )
        lines.append(f"SELECT setval('supplier_relationships_id_seq', {max(sr['id'] for sr in self.supplier_relationships)});")
        lines.append("")

        # Parts
        lines.append("-- Parts")
        for p in self.parts:
            lines.append(
                f"INSERT INTO parts (id, part_number, description, category, unit_cost, weight_kg, lead_time_days, "
                f"primary_supplier_id, is_critical, min_stock_level) "
                f"VALUES ({p['id']}, {sql_str(p['part_number'])}, {sql_str(p['description'])}, {sql_str(p['category'])}, "
                f"{sql_num(p['unit_cost'])}, {sql_num(p['weight_kg'])}, {sql_num(p['lead_time_days'])}, "
                f"{sql_num(p.get('primary_supplier_id'))}, {sql_bool(p['is_critical'])}, {sql_num(p['min_stock_level'])});"
            )
        lines.append(f"SELECT setval('parts_id_seq', {max(p['id'] for p in self.parts)});")
        lines.append("")

        # Bill of Materials
        lines.append("-- Bill of Materials")
        for b in self.bom:
            lines.append(
                f"INSERT INTO bill_of_materials (id, parent_part_id, child_part_id, quantity, unit, is_optional, assembly_sequence) "
                f"VALUES ({b['id']}, {b['parent_part_id']}, {b['child_part_id']}, {b['quantity']}, "
                f"{sql_str(b['unit'])}, {sql_bool(b['is_optional'])}, {sql_num(b.get('assembly_sequence'))});"
            )
        lines.append(f"SELECT setval('bill_of_materials_id_seq', {max(b['id'] for b in self.bom)});")
        lines.append("")

        # Part Suppliers
        lines.append("-- Part Suppliers")
        for ps in self.part_suppliers:
            lines.append(
                f"INSERT INTO part_suppliers (id, part_id, supplier_id, supplier_part_number, unit_cost, lead_time_days, is_approved, approval_date) "
                f"VALUES ({ps['id']}, {ps['part_id']}, {ps['supplier_id']}, {sql_str(ps['supplier_part_number'])}, "
                f"{sql_num(ps['unit_cost'])}, {sql_num(ps['lead_time_days'])}, {sql_bool(ps['is_approved'])}, {sql_date(ps.get('approval_date'))});"
            )
        if self.part_suppliers:
            lines.append(f"SELECT setval('part_suppliers_id_seq', {max(ps['id'] for ps in self.part_suppliers)});")
        lines.append("")

        # Products
        lines.append("-- Products")
        for p in self.products:
            lines.append(
                f"INSERT INTO products (id, sku, name, description, category, list_price, is_active, launch_date, discontinued_date) "
                f"VALUES ({p['id']}, {sql_str(p['sku'])}, {sql_str(p['name'])}, {sql_str(p.get('description'))}, "
                f"{sql_str(p.get('category'))}, {sql_num(p.get('list_price'))}, {sql_bool(p['is_active'])}, "
                f"{sql_date(p.get('launch_date'))}, {sql_date(p.get('discontinued_date'))});"
            )
        lines.append(f"SELECT setval('products_id_seq', {max(p['id'] for p in self.products)});")
        lines.append("")

        # Product Components
        lines.append("-- Product Components")
        for pc in self.product_components:
            lines.append(
                f"INSERT INTO product_components (id, product_id, part_id, quantity, is_required) "
                f"VALUES ({pc['id']}, {pc['product_id']}, {pc['part_id']}, {pc['quantity']}, {sql_bool(pc['is_required'])});"
            )
        lines.append(f"SELECT setval('product_components_id_seq', {max(pc['id'] for pc in self.product_components)});")
        lines.append("")

        # Facilities
        lines.append("-- Facilities")
        for f in self.facilities:
            lines.append(
                f"INSERT INTO facilities (id, facility_code, name, facility_type, city, state, country, latitude, longitude, capacity_units, is_active) "
                f"VALUES ({f['id']}, {sql_str(f['facility_code'])}, {sql_str(f['name'])}, {sql_str(f['facility_type'])}, "
                f"{sql_str(f['city'])}, {sql_str(f.get('state'))}, {sql_str(f['country'])}, "
                f"{sql_num(f.get('latitude'))}, {sql_num(f.get('longitude'))}, {sql_num(f.get('capacity_units'))}, {sql_bool(f['is_active'])});"
            )
        lines.append(f"SELECT setval('facilities_id_seq', {max(f['id'] for f in self.facilities)});")
        lines.append("")

        # Transport Routes
        lines.append("-- Transport Routes")
        for tr in self.transport_routes:
            lines.append(
                f"INSERT INTO transport_routes (id, origin_facility_id, destination_facility_id, transport_mode, "
                f"distance_km, transit_time_hours, cost_usd, capacity_tons, is_active) "
                f"VALUES ({tr['id']}, {tr['origin_facility_id']}, {tr['destination_facility_id']}, {sql_str(tr['transport_mode'])}, "
                f"{sql_num(tr['distance_km'])}, {sql_num(tr['transit_time_hours'])}, {sql_num(tr['cost_usd'])}, "
                f"{sql_num(tr['capacity_tons'])}, {sql_bool(tr['is_active'])});"
            )
        lines.append(f"SELECT setval('transport_routes_id_seq', {max(tr['id'] for tr in self.transport_routes)});")
        lines.append("")

        # Customers
        lines.append("-- Customers")
        for c in self.customers:
            lines.append(
                f"INSERT INTO customers (id, customer_code, name, customer_type, contact_email, shipping_address, city, state, country) "
                f"VALUES ({c['id']}, {sql_str(c['customer_code'])}, {sql_str(c['name'])}, {sql_str(c['customer_type'])}, "
                f"{sql_str(c.get('contact_email'))}, {sql_str(c.get('shipping_address'))}, {sql_str(c.get('city'))}, "
                f"{sql_str(c.get('state'))}, {sql_str(c.get('country'))});"
            )
        lines.append(f"SELECT setval('customers_id_seq', {max(c['id'] for c in self.customers)});")
        lines.append("")

        # Orders
        lines.append("-- Orders")
        for o in self.orders:
            lines.append(
                f"INSERT INTO orders (id, order_number, customer_id, order_date, required_date, shipped_date, status, "
                f"shipping_facility_id, total_amount, shipping_cost) "
                f"VALUES ({o['id']}, {sql_str(o['order_number'])}, {sql_num(o.get('customer_id'))}, "
                f"{sql_timestamp(o['order_date'])}, {sql_date(o.get('required_date'))}, {sql_timestamp(o.get('shipped_date'))}, "
                f"{sql_str(o['status'])}, {sql_num(o.get('shipping_facility_id'))}, {sql_num(o['total_amount'])}, {sql_num(o.get('shipping_cost'))});"
            )
        lines.append(f"SELECT setval('orders_id_seq', {max(o['id'] for o in self.orders)});")
        lines.append("")

        # Order Items
        lines.append("-- Order Items")
        for oi in self.order_items:
            lines.append(
                f"INSERT INTO order_items (id, order_id, product_id, quantity, unit_price, discount_percent) "
                f"VALUES ({oi['id']}, {oi['order_id']}, {oi['product_id']}, {oi['quantity']}, "
                f"{sql_num(oi['unit_price'])}, {sql_num(oi.get('discount_percent', 0))});"
            )
        lines.append(f"SELECT setval('order_items_id_seq', {max(oi['id'] for oi in self.order_items)});")
        lines.append("")

        # Shipments
        lines.append("-- Shipments")
        for sh in self.shipments:
            lines.append(
                f"INSERT INTO shipments (id, shipment_number, order_id, origin_facility_id, destination_facility_id, "
                f"transport_route_id, carrier, tracking_number, status, shipped_at, delivered_at, weight_kg, cost_usd) "
                f"VALUES ({sh['id']}, {sql_str(sh['shipment_number'])}, {sql_num(sh.get('order_id'))}, "
                f"{sh['origin_facility_id']}, {sql_num(sh.get('destination_facility_id'))}, {sql_num(sh.get('transport_route_id'))}, "
                f"{sql_str(sh.get('carrier'))}, {sql_str(sh.get('tracking_number'))}, {sql_str(sh['status'])}, "
                f"{sql_timestamp(sh.get('shipped_at'))}, {sql_timestamp(sh.get('delivered_at'))}, "
                f"{sql_num(sh.get('weight_kg'))}, {sql_num(sh.get('cost_usd'))});"
            )
        if self.shipments:
            lines.append(f"SELECT setval('shipments_id_seq', {max(sh['id'] for sh in self.shipments)});")
        lines.append("")

        # Inventory
        lines.append("-- Inventory")
        for inv in self.inventory:
            lines.append(
                f"INSERT INTO inventory (id, facility_id, part_id, quantity_on_hand, quantity_reserved, quantity_on_order, "
                f"reorder_point, last_counted_at) "
                f"VALUES ({inv['id']}, {inv['facility_id']}, {inv['part_id']}, {inv['quantity_on_hand']}, "
                f"{inv['quantity_reserved']}, {inv['quantity_on_order']}, {sql_num(inv.get('reorder_point'))}, "
                f"{sql_timestamp(inv.get('last_counted_at'))});"
            )
        if self.inventory:
            lines.append(f"SELECT setval('inventory_id_seq', {max(inv['id'] for inv in self.inventory)});")
        lines.append("")

        # Supplier Certifications
        lines.append("-- Supplier Certifications")
        for sc in self.supplier_certifications:
            lines.append(
                f"INSERT INTO supplier_certifications (id, supplier_id, certification_type, certification_number, "
                f"issued_date, expiry_date, is_valid) "
                f"VALUES ({sc['id']}, {sc['supplier_id']}, {sql_str(sc['certification_type'])}, "
                f"{sql_str(sc.get('certification_number'))}, {sql_date(sc.get('issued_date'))}, "
                f"{sql_date(sc.get('expiry_date'))}, {sql_bool(sc['is_valid'])});"
            )
        if self.supplier_certifications:
            lines.append(f"SELECT setval('supplier_certifications_id_seq', {max(sc['id'] for sc in self.supplier_certifications)});")
        lines.append("")

        lines.append("COMMIT;")
        lines.append("")

        # Summary
        total_rows = (
            len(self.suppliers) +
            len(self.supplier_relationships) +
            len(self.parts) +
            len(self.bom) +
            len(self.part_suppliers) +
            len(self.products) +
            len(self.product_components) +
            len(self.facilities) +
            len(self.transport_routes) +
            len(self.customers) +
            len(self.orders) +
            len(self.order_items) +
            len(self.shipments) +
            len(self.inventory) +
            len(self.supplier_certifications)
        )

        lines.append(f"-- Total rows: {total_rows:,}")
        lines.append(f"-- Suppliers: {len(self.suppliers):,}")
        lines.append(f"-- Supplier Relationships: {len(self.supplier_relationships):,}")
        lines.append(f"-- Parts: {len(self.parts):,}")
        lines.append(f"-- BOM entries: {len(self.bom):,}")
        lines.append(f"-- Part Suppliers: {len(self.part_suppliers):,}")
        lines.append(f"-- Products: {len(self.products):,}")
        lines.append(f"-- Product Components: {len(self.product_components):,}")
        lines.append(f"-- Facilities: {len(self.facilities):,}")
        lines.append(f"-- Transport Routes: {len(self.transport_routes):,}")
        lines.append(f"-- Customers: {len(self.customers):,}")
        lines.append(f"-- Orders: {len(self.orders):,}")
        lines.append(f"-- Order Items: {len(self.order_items):,}")
        lines.append(f"-- Shipments: {len(self.shipments):,}")
        lines.append(f"-- Inventory: {len(self.inventory):,}")
        lines.append(f"-- Supplier Certifications: {len(self.supplier_certifications):,}")

        return "\n".join(lines)


def main():
    print("=" * 60)
    print("Virtual Graph - Supply Chain Data Generator")
    print("=" * 60)

    generator = SupplyChainGenerator()
    generator.generate_all()

    print("\nWriting SQL to", OUTPUT_PATH)
    sql = generator.to_sql()
    OUTPUT_PATH.write_text(sql)

    print("\nDone!")
    print(f"Generated {OUTPUT_PATH.stat().st_size / 1024 / 1024:.1f} MB of SQL")


if __name__ == "__main__":
    main()
