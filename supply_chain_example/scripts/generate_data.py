#!/usr/bin/env python3
"""
Generate synthetic supply chain data for Virtual Graph POC.

Target data volumes (~2.1M rows across 25 tables):

EXISTING DOMAIN (~500K rows):
- 1,000 suppliers (tiered: 100 T1, 300 T2, 600 T3)
- 15,000 parts with BOM hierarchy (avg depth: 5 levels)
- 100+ facilities (100 base + supplier hubs)
- 5,000 customers
- 80,000 orders with 250,000 order items (composite key)
- 50,000+ shipments (order fulfillment, transfer, replenishment, procurement, return)
- 50,000 BOM entries with effectivity dates
- 30,000 inventory records

MANUFACTURING EXECUTION DOMAIN (~1.1M rows):
- 150 work centers (3-5 per factory)
- 2,500 production routings (3-5 steps per product)
- 120,000 work orders (80% make-to-order, 20% make-to-stock)
- 400,000 work order steps
- 600,000 material transactions (issue, receipt, scrap)

SCOR MODEL DOMAINS (~360K rows):
- PLAN: 100,000 demand forecasts (seasonal patterns)
- SOURCE: 50,000 purchase orders with ~150,000 lines
- RETURN: 4,000 returns with ~12,000 return items

This generates realistic "enterprise messiness":
- Composite keys (order_items, purchase_order_lines, return_items)
- BOM effectivity dates (80% current, 15% superseded, 5% future)
- Shipment type polymorphism (5 types: fulfillment, transfer, replenishment, procurement, return)
- Supplier hub facilities (virtual origins for procurement shipments)
- Supplier relationship status (10% inactive/suspended)
- Transport route status (5% seasonal/suspended)
- Work order status (released, in_progress, quality_hold, completed, cancelled)
- Material transaction types (issue_to_wo, receipt_from_wo, scrap, return_to_stock)
- PO status (draft, submitted, confirmed, shipped, received, cancelled)
- Return dispositions (restock, refurbish, scrap based on reason)
- Scrap tracking with reason codes
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
OUTPUT_PATH = Path(__file__).parent.parent / "postgres" / "seed.sql"


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
        # Manufacturing execution domain
        self.work_centers: list[dict] = []
        self.production_routings: list[dict] = []
        self.work_orders: list[dict] = []
        self.work_order_steps: list[dict] = []
        self.material_transactions: list[dict] = []
        # SCOR Model domains (Plan/Source/Return)
        self.demand_forecasts: list[dict] = []
        self.purchase_orders: list[dict] = []
        self.purchase_order_lines: list[dict] = []
        self.returns: list[dict] = []
        self.return_items: list[dict] = []

        # Track IDs for relationships
        self.supplier_ids_by_tier: dict[int, list[int]] = {1: [], 2: [], 3: []}
        self.part_ids: list[int] = []
        self.leaf_part_ids: list[int] = []  # Parts with no children (raw materials)
        self.top_part_ids: list[int] = []  # Parts that go into products
        self.factory_ids: list[int] = []  # Facilities that are factories (have work centers)
        self.supplier_hub_facility_ids: dict[str, int] = {}  # country -> hub facility_id
        self.dc_facility_ids: list[int] = []  # Distribution center facility IDs

    def generate_all(self):
        """Generate all data in dependency order."""
        print("Generating suppliers...")
        self.generate_suppliers(1000)

        print("Generating supplier relationships...")
        self.generate_supplier_relationships()

        print("Generating parts with BOM hierarchy...")
        self.generate_parts_with_bom(15000)

        print("Generating part suppliers...")
        self.generate_part_suppliers()

        print("Generating products...")
        self.generate_products(500)

        print("Generating facilities...")
        self.generate_facilities(100)

        # Add supplier hub facilities (after facilities)
        print("Generating supplier hub facilities...")
        self.generate_supplier_hub_facilities()

        print("Generating transport routes...")
        self.generate_transport_routes()

        print("Generating customers...")
        self.generate_customers(5000)

        print("Generating orders...")
        self.generate_orders(80000)

        print("Generating additional shipments (transfers + replenishment)...")
        self.generate_additional_shipments()

        print("Generating inventory...")
        self.generate_inventory()

        print("Generating supplier certifications...")
        self.generate_supplier_certifications()

        # Manufacturing execution domain
        print("Generating work centers...")
        self.generate_work_centers()

        print("Generating production routings...")
        self.generate_production_routings()

        print("Generating work orders...")
        self.generate_work_orders(120000)

        print("Generating work order steps...")
        self.generate_work_order_steps()

        print("Generating material transactions...")
        self.generate_material_transactions()

        # SCOR Model domains (Plan/Source/Return)
        print("Generating demand forecasts...")
        self.generate_demand_forecasts(100000)

        print("Generating purchase orders...")
        self.generate_purchase_orders(50000)

        print("Generating returns...")
        self.generate_returns(4000)

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

        def get_relationship_status():
            """~10% inactive/suspended, 90% active."""
            r = random.random()
            if r < 0.05:
                return False, "suspended"
            elif r < 0.10:
                return False, "terminated"
            else:
                return True, "active"

        # First, ensure named supplier chain exists:
        # Eastern Electronics (T3, id=7) → Pacific Components (T2, id=4) → Acme Corp (T1, id=1)
        named_supply_chain = [
            (7, 4, True),   # Eastern Electronics → Pacific Components (primary)
            (4, 1, True),   # Pacific Components → Acme Corp (primary)
            (8, 4, False),  # Delta Supplies → Pacific Components (alternate)
            (5, 1, False),  # Northern Materials → Acme Corp (alternate)
            (6, 2, True),   # Apex Manufacturing → GlobalTech Industries (primary)
        ]

        for seller_id, buyer_id, is_primary in named_supply_chain:
            self.supplier_relationships.append({
                "id": rel_id,
                "seller_id": seller_id,
                "buyer_id": buyer_id,
                "relationship_type": "supplies",
                "contract_start_date": fake.date_between(start_date="-3y", end_date="-1y"),
                "is_primary": is_primary,
                "is_active": True,
                "relationship_status": "active",
            })
            rel_id += 1

        # Track existing relationships to avoid duplicates
        existing_rels = {(r["seller_id"], r["buyer_id"]) for r in self.supplier_relationships}

        # T3 suppliers sell to T2 suppliers
        for t3_id in self.supplier_ids_by_tier[3]:
            # Each T3 sells to 1-3 T2 suppliers
            num_buyers = random.randint(1, 3)
            buyers = random.sample(self.supplier_ids_by_tier[2], min(num_buyers, len(self.supplier_ids_by_tier[2])))
            for t2_id in buyers:
                if (t3_id, t2_id) not in existing_rels:
                    is_active, status = get_relationship_status()
                    self.supplier_relationships.append({
                        "id": rel_id,
                        "seller_id": t3_id,
                        "buyer_id": t2_id,
                        "relationship_type": "supplies",
                        "contract_start_date": fake.date_between(start_date="-3y", end_date="-1y"),
                        "is_primary": random.random() > 0.7,
                        "is_active": is_active,
                        "relationship_status": status,
                    })
                    existing_rels.add((t3_id, t2_id))
                    rel_id += 1

        # T2 suppliers sell to T1 suppliers
        for t2_id in self.supplier_ids_by_tier[2]:
            # Each T2 sells to 1-2 T1 suppliers
            num_buyers = random.randint(1, 2)
            buyers = random.sample(self.supplier_ids_by_tier[1], min(num_buyers, len(self.supplier_ids_by_tier[1])))
            for t1_id in buyers:
                if (t2_id, t1_id) not in existing_rels:
                    is_active, status = get_relationship_status()
                    self.supplier_relationships.append({
                        "id": rel_id,
                        "seller_id": t2_id,
                        "buyer_id": t1_id,
                        "relationship_type": "supplies",
                        "contract_start_date": fake.date_between(start_date="-3y", end_date="-1y"),
                        "is_primary": random.random() > 0.7,
                        "is_active": is_active,
                        "relationship_status": status,
                    })
                    existing_rels.add((t2_id, t1_id))
                    rel_id += 1

    def generate_parts_with_bom(self, count: int):
        """
        Generate parts with realistic BOM hierarchy.

        Structure:
        - Level 0 (raw materials): 40% of parts, no children
        - Level 1-2 (subassemblies): 40% of parts
        - Level 3-5 (assemblies): 20% of parts

        Average depth target: 5 levels

        BOM effectivity dates:
        - 80% current (effective_from = past, effective_to = NULL)
        - 15% superseded (effective_to = past date)
        - 5% future (effective_from = future date)
        """
        categories = [
            "Raw Material", "Electronic", "Mechanical", "Fastener",
            "Subassembly", "Assembly", "Sensor", "Motor", "Housing", "Cable"
        ]

        def get_effectivity_dates():
            """Generate effectivity dates with 80/15/5 distribution."""
            r = random.random()
            today = date.today()
            if r < 0.80:
                # Current: effective from past, no end date
                return fake.date_between(start_date="-3y", end_date="-1m"), None
            elif r < 0.95:
                # Superseded: both dates in the past
                effective_from = fake.date_between(start_date="-5y", end_date="-2y")
                effective_to = fake.date_between(start_date="-2y", end_date="-1m")
                return effective_from, effective_to
            else:
                # Future: effective_from is in the future
                return fake.date_between(start_date="+1m", end_date="+1y"), None

        # Generate parts
        for part_id in range(1, count + 1):
            category = random.choice(categories)
            # UoM conversion factors - raw materials may use different base UoMs
            if category == "Raw Material":
                base_uom = random.choice(["each", "kg", "m", "L"])
            else:
                base_uom = "each"  # Assemblies/components are always counted

            # Generate realistic conversion factors
            unit_weight_kg = round(random.uniform(0.001, 10.0), 6)
            unit_length_m = round(random.uniform(0.01, 5.0), 6) if base_uom == "m" else None
            unit_volume_l = round(random.uniform(0.001, 2.0), 6) if base_uom == "L" else None

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
                "base_uom": base_uom,
                "unit_weight_kg": unit_weight_kg,
                "unit_length_m": unit_length_m,
                "unit_volume_l": unit_volume_l,
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
                eff_from, eff_to = get_effectivity_dates()
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": sub_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 10),
                    "unit": random.choice(["each", "kg", "m", "L"]),
                    "is_optional": random.random() > 0.9,
                    "assembly_sequence": seq,
                    "effective_from": eff_from,
                    "effective_to": eff_to,
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
                eff_from, eff_to = get_effectivity_dates()
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": asm_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 5),
                    "unit": "each",
                    "is_optional": random.random() > 0.95,
                    "assembly_sequence": seq,
                    "effective_from": eff_from,
                    "effective_to": eff_to,
                })
                bom_id += 1

        # Level 3: Use level 2 assemblies
        for asm_id in level_3:
            num_components = random.randint(2, 5)
            components = random.sample(level_2, min(num_components, len(level_2)))
            if random.random() > 0.5:
                components.extend(random.sample(subassemblies, random.randint(1, 2)))
            for seq, comp_id in enumerate(components, 1):
                eff_from, eff_to = get_effectivity_dates()
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": asm_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 4),
                    "unit": "each",
                    "is_optional": random.random() > 0.95,
                    "assembly_sequence": seq,
                    "effective_from": eff_from,
                    "effective_to": eff_to,
                })
                bom_id += 1

        # Level 4-5: Use level 3 assemblies
        for asm_id in level_4_5:
            num_components = random.randint(2, 4)
            components = random.sample(level_3, min(num_components, len(level_3)))
            if random.random() > 0.7:
                components.extend(random.sample(level_2, random.randint(1, 2)))
            for seq, comp_id in enumerate(components, 1):
                eff_from, eff_to = get_effectivity_dates()
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": asm_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 3),
                    "unit": "each",
                    "is_optional": random.random() > 0.95,
                    "assembly_sequence": seq,
                    "effective_from": eff_from,
                    "effective_to": eff_to,
                })
                bom_id += 1

        # Add named raw material parts for testing (to be used in named product BOMs)
        named_raw_parts = [
            (count + 1, "CHIP-001", "Integrated Circuit Chip", "Electronic"),
            (count + 2, "RESISTOR-100", "100 Ohm Resistor", "Electronic"),
            (count + 3, "CAP-001", "10uF Capacitor", "Electronic"),
            (count + 4, "MOTOR-001", "Stepper Motor Unit", "Motor"),
            (count + 5, "SENSOR-001", "Temperature Sensor", "Sensor"),
        ]
        for part_id, part_number, description, category in named_raw_parts:
            self.parts.append({
                "id": part_id,
                "part_number": part_number,
                "description": description,
                "category": category,
                "unit_cost": round(random.uniform(1, 50), 2),
                "weight_kg": round(random.uniform(0.01, 0.5), 3),
                "lead_time_days": random.randint(7, 30),
                "primary_supplier_id": random.choice(self.supplier_ids_by_tier[2]),
                "is_critical": True,
                "min_stock_level": 100,
                "base_uom": "each",
                "unit_weight_kg": round(random.uniform(0.001, 0.5), 6),
                "unit_length_m": None,
                "unit_volume_l": None,
            })
            self.leaf_part_ids.append(part_id)

        # Add named assembly parts for testing
        named_assembly_parts = [
            (count + 6, "TURBO-ENC-001", "Turbo Encabulator Main Assembly"),
            (count + 7, "FLUX-CAP-001", "Flux Capacitor Module"),
            (count + 8, "WIDGET-A", "Standard Widget Type A"),
        ]
        for part_id, part_number, description in named_assembly_parts:
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
                "base_uom": "each",
                "unit_weight_kg": round(random.uniform(1.0, 25.0), 6),
                "unit_length_m": None,
                "unit_volume_l": None,
            })
            self.top_part_ids.append(part_id)

        # Build BOM for named assemblies using named raw parts and some level_4_5
        # Turbo Encabulator uses CHIP-001, RESISTOR-100, CAP-001, MOTOR-001
        turbo_id = count + 6
        chip_id = count + 1
        resistor_id = count + 2
        cap_id = count + 3
        motor_id = count + 4

        turbo_components = [
            (chip_id, 4, "each"),      # 4x CHIP-001
            (resistor_id, 10, "each"), # 10x RESISTOR-100
            (cap_id, 6, "each"),       # 6x CAP-001
            (motor_id, 2, "each"),     # 2x MOTOR-001
        ]
        # Named products always have current effectivity (no end date)
        current_eff_from = fake.date_between(start_date="-2y", end_date="-6m")
        for seq, (comp_id, qty, unit) in enumerate(turbo_components, 1):
            self.bom.append({
                "id": bom_id,
                "parent_part_id": turbo_id,
                "child_part_id": comp_id,
                "quantity": qty,
                "unit": unit,
                "is_optional": False,
                "assembly_sequence": seq,
                "effective_from": current_eff_from,
                "effective_to": None,
            })
            bom_id += 1

        # Add some level_4_5 assemblies to Turbo Encabulator
        for seq, comp_id in enumerate(random.sample(level_4_5, min(3, len(level_4_5))), len(turbo_components) + 1):
            self.bom.append({
                "id": bom_id,
                "parent_part_id": turbo_id,
                "child_part_id": comp_id,
                "quantity": random.randint(1, 2),
                "unit": "each",
                "is_optional": False,
                "assembly_sequence": seq,
                "effective_from": current_eff_from,
                "effective_to": None,
            })
            bom_id += 1

        # Flux Capacitor and Widget get similar treatment
        for part_id in [count + 7, count + 8]:
            for seq, comp_id in enumerate(random.sample(level_4_5, min(5, len(level_4_5))), 1):
                self.bom.append({
                    "id": bom_id,
                    "parent_part_id": part_id,
                    "child_part_id": comp_id,
                    "quantity": random.randint(1, 3),
                    "unit": "each",
                    "is_optional": False,
                    "assembly_sequence": seq,
                    "effective_from": current_eff_from,
                    "effective_to": None,
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
            ("FAC-DEN", "Denver Hub", "distribution_center", "Denver", "CO", "USA"),
            ("FAC-MIA", "Miami Hub", "distribution_center", "Miami", "FL", "USA"),
            ("FAC-SEA", "Seattle Warehouse", "warehouse", "Seattle", "WA", "USA"),
        ]

        for i, (code, name, ftype, city, state, country) in enumerate(named_facilities):
            fac_id = i + 1
            self.facilities.append({
                "id": fac_id,
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
            if ftype == "factory":
                self.factory_ids.append(fac_id)
            elif ftype == "distribution_center":
                self.dc_facility_ids.append(fac_id)

        start_id = len(named_facilities) + 1
        us_states = ["CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]
        countries = ["USA", "China", "Germany", "Japan", "Mexico", "Canada"]

        for fac_id in range(start_id, count + 1):
            country = random.choice(countries)
            ftype = random.choice(facility_types)
            self.facilities.append({
                "id": fac_id,
                "facility_code": f"FAC-{fac_id:03d}",
                "name": f"{fake.city()} {random.choice(['Warehouse', 'Distribution Center', 'Factory', 'Hub'])}",
                "facility_type": ftype,
                "city": fake.city(),
                "state": random.choice(us_states) if country == "USA" else None,
                "country": country,
                "latitude": round(random.uniform(-90, 90), 6),
                "longitude": round(random.uniform(-180, 180), 6),
                "capacity_units": random.randint(5000, 100000),
                "is_active": random.random() > 0.05,
            })
            if ftype == "factory":
                self.factory_ids.append(fac_id)
            elif ftype == "distribution_center":
                self.dc_facility_ids.append(fac_id)

    def generate_transport_routes(self):
        """Generate transport routes between facilities (connected network)."""
        route_id = 1
        facility_ids = [f["id"] for f in self.facilities]
        modes = ["truck", "rail", "air", "sea"]

        def get_route_status():
            """~5% seasonal/suspended, 95% active."""
            r = random.random()
            if r < 0.02:
                return False, "suspended"
            elif r < 0.04:
                return True, "seasonal"
            elif r < 0.05:
                return False, "discontinued"
            else:
                return True, "active"

        # Named facility IDs (based on named_facilities order):
        # 1=Chicago Warehouse, 2=LA Distribution, 3=NYC Factory, 4=Shanghai Hub,
        # 5=Munich Factory, 6=Denver Hub, 7=Miami Hub, 8=Seattle Warehouse

        # First, create explicit routes between named facilities
        named_routes = [
            # Denver Hub connections (Q35 asks about routing around Denver)
            (6, 1, "truck", 1000, 16, 800),    # Denver Hub → Chicago Warehouse
            (1, 6, "truck", 1000, 16, 800),    # Chicago Warehouse → Denver Hub
            (6, 2, "truck", 1100, 18, 900),    # Denver Hub → LA Distribution
            (2, 6, "truck", 1100, 18, 900),    # LA Distribution → Denver Hub
            (6, 8, "truck", 1400, 22, 1100),   # Denver Hub → Seattle Warehouse
            (8, 6, "truck", 1400, 22, 1100),   # Seattle Warehouse → Denver Hub
            # Main corridor
            (1, 2, "truck", 2800, 36, 1500),   # Chicago → LA (direct, bypassing Denver)
            (2, 1, "truck", 2800, 36, 1500),   # LA → Chicago (direct)
            (1, 3, "rail", 1200, 20, 600),     # Chicago → NYC
            (3, 1, "rail", 1200, 20, 600),     # NYC → Chicago
            # Miami Hub connections
            (7, 2, "truck", 4000, 48, 2000),   # Miami → LA
            (2, 7, "truck", 4000, 48, 2000),   # LA → Miami
            (7, 1, "truck", 2100, 28, 1200),   # Miami → Chicago
            (1, 7, "truck", 2100, 28, 1200),   # Chicago → Miami
            # International
            (4, 2, "sea", 10000, 360, 3000),   # Shanghai → LA
            (5, 3, "air", 6500, 12, 5000),     # Munich → NYC
        ]

        existing_routes = set()
        for origin, dest, mode, dist, time, cost in named_routes:
            self.transport_routes.append({
                "id": route_id,
                "origin_facility_id": origin,
                "destination_facility_id": dest,
                "transport_mode": mode,
                "distance_km": dist,
                "transit_time_hours": time,
                "cost_usd": cost,
                "capacity_tons": round(random.uniform(50, 500), 2),
                "is_active": True,
                "route_status": "active",
            })
            existing_routes.add((origin, dest, mode))
            route_id += 1

        # Ensure network is connected: create a spanning tree first
        connected = {facility_ids[0]}
        unconnected = set(facility_ids[1:])

        while unconnected:
            from_id = random.choice(list(connected))
            to_id = random.choice(list(unconnected))
            unconnected.remove(to_id)
            connected.add(to_id)

            # Create bidirectional routes (if not already exists)
            for origin, dest in [(from_id, to_id), (to_id, from_id)]:
                mode = random.choice(modes)
                if (origin, dest, mode) not in existing_routes:
                    is_active, status = get_route_status()
                    self.transport_routes.append({
                        "id": route_id,
                        "origin_facility_id": origin,
                        "destination_facility_id": dest,
                        "transport_mode": mode,
                        "distance_km": round(random.uniform(100, 5000), 2),
                        "transit_time_hours": round(random.uniform(4, 120), 2),
                        "cost_usd": round(random.uniform(100, 10000), 2),
                        "capacity_tons": round(random.uniform(10, 1000), 2),
                        "is_active": is_active,
                        "route_status": status,
                    })
                    existing_routes.add((origin, dest, mode))
                    route_id += 1

        # Add additional routes for more connectivity

        for _ in range(len(facility_ids) * 2):  # Add ~2x more routes
            from_id = random.choice(facility_ids)
            to_id = random.choice([f for f in facility_ids if f != from_id])
            mode = random.choice(modes)

            if (from_id, to_id, mode) not in existing_routes:
                existing_routes.add((from_id, to_id, mode))
                is_active, status = get_route_status()
                self.transport_routes.append({
                    "id": route_id,
                    "origin_facility_id": from_id,
                    "destination_facility_id": to_id,
                    "transport_mode": mode,
                    "distance_km": round(random.uniform(100, 5000), 2),
                    "transit_time_hours": round(random.uniform(4, 120), 2),
                    "cost_usd": round(random.uniform(100, 10000), 2),
                    "capacity_tons": round(random.uniform(10, 1000), 2),
                    "is_active": is_active,
                    "route_status": status,
                })
                route_id += 1

    def generate_customers(self, count: int):
        """Generate customers."""
        customer_types = ["retail", "wholesale", "enterprise"]

        # Named customers for testing
        named_customers = [
            ("CUST-ACME", "Acme Industries", "enterprise", "Chicago", "IL", "USA"),
            ("CUST-GLOBEX", "Globex Corporation", "enterprise", "New York", "NY", "USA"),
            ("CUST-INITECH", "Initech Inc", "wholesale", "Austin", "TX", "USA"),
        ]

        for i, (code, name, ctype, city, state, country) in enumerate(named_customers):
            self.customers.append({
                "id": i + 1,
                "customer_code": code,
                "name": name,
                "customer_type": ctype,
                "contact_email": f"orders@{name.lower().replace(' ', '')}.com",
                "shipping_address": fake.street_address(),
                "city": city,
                "state": state,
                "country": country,
            })

        start_id = len(named_customers) + 1
        for cust_id in range(start_id, count + 1):
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
        """Generate orders with items (composite key) and shipments."""
        statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
        facility_ids = [f["id"] for f in self.facilities]
        product_ids = [p["id"] for p in self.products]
        customer_ids = [c["id"] for c in self.customers]

        shipment_id = 1

        # Named orders for testing (first few orders get specific numbers)
        named_orders = [
            ("ORD-2024-001", 1, "pending", datetime(2024, 6, 15, 10, 30)),   # Acme Industries order
            ("ORD-2024-002", 2, "shipped", datetime(2024, 5, 20, 14, 0)),    # Globex order
            ("ORD-2024-003", 1, "delivered", datetime(2024, 4, 10, 9, 15)),  # Another Acme order
        ]

        for order_id, (order_num, cust_id, status, order_date) in enumerate(named_orders, 1):
            shipped_date = None
            if status in ["shipped", "delivered"]:
                shipped_date = order_date + timedelta(days=random.randint(1, 7))

            self.orders.append({
                "id": order_id,
                "order_number": order_num,
                "customer_id": cust_id,
                "order_date": order_date,
                "required_date": (order_date + timedelta(days=random.randint(7, 30))).date(),
                "shipped_date": shipped_date,
                "status": status,
                "shipping_facility_id": 1,  # Chicago Warehouse
                "total_amount": round(random.uniform(1000, 10000), 2),
                "shipping_cost": round(random.uniform(50, 200), 2),
            })

            # Add order items with line_number (SAP-style composite key)
            num_items = random.randint(2, 5)
            for line_num in range(1, num_items + 1):
                self.order_items.append({
                    "order_id": order_id,
                    "line_number": line_num,
                    "product_id": random.choice(product_ids[:10]),  # Named products first
                    "quantity": random.randint(1, 5),
                    "unit_price": round(random.uniform(100, 500), 2),
                    "discount_percent": 0,
                })

            # Add shipment for shipped/delivered (order_fulfillment type)
            if status in ["shipped", "delivered"]:
                self.shipments.append({
                    "id": shipment_id,
                    "shipment_number": f"SHP-{order_num.split('-')[-1]}",
                    "order_id": order_id,
                    "origin_facility_id": 1,  # Chicago Warehouse
                    "destination_facility_id": 2,  # LA Distribution Center
                    "transport_route_id": None,
                    "shipment_type": "order_fulfillment",
                    "carrier": "Priority Logistics",
                    "tracking_number": fake.bothify("??#########??"),
                    "status": "delivered" if status == "delivered" else "in_transit",
                    "shipped_at": shipped_date,
                    "delivered_at": shipped_date + timedelta(days=random.randint(1, 14)) if status == "delivered" else None,
                    "weight_kg": round(random.uniform(5, 50), 2),
                    "cost_usd": round(random.uniform(100, 500), 2),
                })
                shipment_id += 1

        start_order_id = len(named_orders) + 1

        for order_id in range(start_order_id, count + 1):
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

            # Generate 1-5 order items with line_number (SAP-style composite key)
            num_items = random.randint(1, 5)
            total = Decimal("0")
            for line_num in range(1, num_items + 1):
                quantity = random.randint(1, 10)
                unit_price = round(random.uniform(10, 500), 2)
                discount = round(random.uniform(0, 15), 2) if random.random() > 0.7 else 0

                self.order_items.append({
                    "order_id": order_id,
                    "line_number": line_num,
                    "product_id": random.choice(product_ids),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_percent": discount,
                })
                total += Decimal(str(quantity * unit_price * (1 - discount / 100)))

            self.orders[-1]["total_amount"] = round(float(total), 2)

            # Generate shipment for shipped orders (order_fulfillment type)
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
                    "shipment_type": "order_fulfillment",
                    "carrier": fake.company() + " Logistics",
                    "tracking_number": fake.bothify("??#########??"),
                    "status": "delivered" if status == "delivered" else "in_transit",
                    "shipped_at": shipped_date,
                    "delivered_at": shipped_date + timedelta(days=random.randint(1, 14)) if status == "delivered" else None,
                    "weight_kg": round(random.uniform(0.5, 100), 2),
                    "cost_usd": round(random.uniform(20, 500), 2),
                })
                shipment_id += 1

    def generate_additional_shipments(self):
        """
        Generate additional shipments for transfer and replenishment types.

        Target distribution of all shipments:
        - 70% order_fulfillment (already generated in generate_orders)
        - 20% transfer (facility-to-facility, NULL order_id)
        - 10% replenishment (supplier-to-facility inbound)

        Target: ~50,000 total shipments
        """
        # Get current shipment count (order_fulfillment already generated)
        current_count = len(self.shipments)
        # Estimate total needed: current is 70%, we need 30% more
        target_additional = int(current_count * 0.43)  # 30/70 ratio ≈ 0.43

        transfer_count = int(target_additional * 0.67)  # 20% of total → ~67% of additional
        replenishment_count = target_additional - transfer_count  # 10% of total → ~33% of additional

        facility_ids = [f["id"] for f in self.facilities]
        shipment_id = max(s["id"] for s in self.shipments) + 1 if self.shipments else 1

        # Generate transfer shipments (facility-to-facility, no order)
        for _ in range(transfer_count):
            origin = random.choice(facility_ids)
            dest = random.choice([f for f in facility_ids if f != origin])

            # Find a route if exists
            route = next(
                (r for r in self.transport_routes
                 if r["origin_facility_id"] == origin and r["destination_facility_id"] == dest),
                None
            )

            ship_date = fake.date_time_between(start_date="-2y", end_date="now")
            is_delivered = random.random() > 0.2

            self.shipments.append({
                "id": shipment_id,
                "shipment_number": f"TRF-{shipment_id:08d}",
                "order_id": None,  # No order for transfers
                "origin_facility_id": origin,
                "destination_facility_id": dest,
                "transport_route_id": route["id"] if route else None,
                "shipment_type": "transfer",
                "carrier": random.choice(["Internal Fleet", "Contract Carrier", fake.company() + " Transport"]),
                "tracking_number": fake.bothify("TRF??#########"),
                "status": "delivered" if is_delivered else random.choice(["pending", "in_transit"]),
                "shipped_at": ship_date,
                "delivered_at": ship_date + timedelta(days=random.randint(1, 14)) if is_delivered else None,
                "weight_kg": round(random.uniform(10, 500), 2),
                "cost_usd": round(random.uniform(100, 2000), 2),
            })
            shipment_id += 1

        # Generate replenishment shipments (inbound from supplier)
        for _ in range(replenishment_count):
            dest = random.choice(facility_ids)

            ship_date = fake.date_time_between(start_date="-2y", end_date="now")
            is_delivered = random.random() > 0.15

            self.shipments.append({
                "id": shipment_id,
                "shipment_number": f"REP-{shipment_id:08d}",
                "order_id": None,  # No customer order for replenishment
                "origin_facility_id": random.choice(facility_ids),  # Could be supplier warehouse
                "destination_facility_id": dest,
                "transport_route_id": None,
                "shipment_type": "replenishment",
                "carrier": random.choice(["Supplier Direct", fake.company() + " Freight", "LTL Consolidated"]),
                "tracking_number": fake.bothify("REP??#########"),
                "status": "delivered" if is_delivered else random.choice(["pending", "in_transit"]),
                "shipped_at": ship_date,
                "delivered_at": ship_date + timedelta(days=random.randint(3, 21)) if is_delivered else None,
                "weight_kg": round(random.uniform(50, 2000), 2),
                "cost_usd": round(random.uniform(200, 5000), 2),
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

    def generate_work_centers(self):
        """Generate work centers at factory facilities."""
        wc_id = 1

        # Work center types and their naming patterns
        wc_types = {
            'assembly': ['Assembly Line', 'Final Assembly', 'Sub-Assembly Station'],
            'machining': ['CNC Station', 'Lathe Cell', 'Mill Center', 'Grinding Bay'],
            'fabrication': ['Welding Bay', 'Stamping Press', 'Forming Line', 'Cutting Station'],
            'testing': ['QC Station', 'Test Bench', 'Burn-In Rack', 'Inspection Bay'],
            'packaging': ['Pack Line', 'Shipping Prep', 'Kitting Station', 'Label Station']
        }

        # Named work centers for testing (at named factories: NYC=3, Munich=5)
        named_wcs = [
            ("WC-ASM-01", "Primary Assembly Line", 3, "assembly", 500, 0.92, 150.00),
            ("WC-TEST-01", "Main Test Bench", 3, "testing", 200, 0.95, 120.00),
            ("WC-PACK-01", "Packaging Line Alpha", 3, "packaging", 800, 0.88, 80.00),
            ("WC-MUN-ASM", "Munich Assembly", 5, "assembly", 400, 0.90, 180.00),
            ("WC-MUN-FAB", "Munich Fabrication", 5, "fabrication", 300, 0.85, 200.00),
        ]

        for wc_code, name, fac_id, wc_type, capacity, efficiency, hourly_rate in named_wcs:
            self.work_centers.append({
                "id": wc_id,
                "wc_code": wc_code,
                "name": name,
                "facility_id": fac_id,
                "work_center_type": wc_type,
                "capacity_per_day": capacity,
                "efficiency_rating": efficiency,
                "hourly_rate_usd": hourly_rate,
                "setup_time_mins": random.randint(15, 60),
                "is_active": True,
            })
            wc_id += 1

        # Generate 3-5 work centers per factory
        for fac_id in self.factory_ids:
            # Skip named factories (3=NYC, 5=Munich) - already have work centers
            if fac_id in [3, 5]:
                continue

            num_wcs = random.randint(3, 5)
            used_types = set()

            for _ in range(num_wcs):
                # Pick a type we haven't used at this factory
                available_types = [t for t in wc_types.keys() if t not in used_types]
                if not available_types:
                    available_types = list(wc_types.keys())
                wc_type = random.choice(available_types)
                used_types.add(wc_type)

                name_template = random.choice(wc_types[wc_type])
                self.work_centers.append({
                    "id": wc_id,
                    "wc_code": f"WC-{fac_id:03d}-{wc_id:03d}",
                    "name": f"{name_template} {random.choice(['A', 'B', 'C', '1', '2'])}",
                    "facility_id": fac_id,
                    "work_center_type": wc_type,
                    "capacity_per_day": random.randint(100, 1000),
                    "efficiency_rating": round(random.uniform(0.75, 0.98), 2),
                    "hourly_rate_usd": round(random.uniform(50, 250), 2),
                    "setup_time_mins": random.randint(10, 90),
                    "is_active": random.random() > 0.05,
                })
                wc_id += 1

    def generate_production_routings(self):
        """Generate production routings (process steps) for products."""
        routing_id = 1

        # Operation templates by step type
        operations = {
            'setup': ['Receive materials', 'Stage components', 'Material verification'],
            'pre_assembly': ['Pre-assembly inspection', 'Component sorting', 'Kit preparation'],
            'assembly': ['Mechanical assembly', 'Wire harness assembly', 'Solder components',
                        'Mount PCB', 'Sub-assembly integration'],
            'calibration': ['Calibration', 'Alignment', 'Parameter tuning'],
            'testing': ['Functional test', 'Burn-in test', 'Quality inspection', 'Performance test'],
            'finishing': ['Final QC inspection', 'Packaging', 'Label and ship']
        }

        # Map operation categories to work center types
        op_to_wc_type = {
            'setup': ['assembly', 'fabrication'],
            'pre_assembly': ['assembly'],
            'assembly': ['assembly'],
            'calibration': ['testing'],
            'testing': ['testing'],
            'finishing': ['packaging']
        }

        # Build WC lookup by facility and type
        wc_by_facility_type: dict[tuple[int, str], list[int]] = {}
        for wc in self.work_centers:
            if wc["is_active"]:
                key = (wc["facility_id"], wc["work_center_type"])
                if key not in wc_by_facility_type:
                    wc_by_facility_type[key] = []
                wc_by_facility_type[key].append(wc["id"])

        # Each product gets 3-5 routing steps
        for product in self.products:
            # Pick a factory for this product's routing
            if not self.factory_ids:
                continue
            factory_id = random.choice(self.factory_ids)

            # Generate 3-5 steps in sequence
            num_steps = random.randint(3, 5)
            step_categories = ['setup']

            # Always have some assembly
            step_categories.extend(random.sample(['pre_assembly', 'assembly'], min(num_steps - 2, 2)))

            # Testing and finishing
            if num_steps >= 4:
                step_categories.append(random.choice(['calibration', 'testing']))
            step_categories.append('finishing')

            # Trim to exact num_steps
            step_categories = step_categories[:num_steps]

            for seq_idx, category in enumerate(step_categories):
                sequence = (seq_idx + 1) * 10  # 10, 20, 30...
                operation = random.choice(operations[category])

                # Find a suitable work center
                wc_id = None
                for wc_type in op_to_wc_type.get(category, ['assembly']):
                    candidates = wc_by_facility_type.get((factory_id, wc_type), [])
                    if candidates:
                        wc_id = random.choice(candidates)
                        break

                # Fallback to any WC at this factory
                if wc_id is None:
                    any_wc = [wc["id"] for wc in self.work_centers if wc["facility_id"] == factory_id]
                    wc_id = random.choice(any_wc) if any_wc else 1

                self.production_routings.append({
                    "id": routing_id,
                    "product_id": product["id"],
                    "step_sequence": sequence,
                    "operation_name": operation,
                    "work_center_id": wc_id,
                    "setup_time_mins": random.randint(5, 30),
                    "run_time_per_unit_mins": round(random.uniform(0.5, 15.0), 2),
                    "is_active": True,
                    "effective_from": fake.date_between(start_date="-2y", end_date="-6m"),
                    "effective_to": None,
                })
                routing_id += 1

    def generate_work_orders(self, count: int):
        """Generate work orders for production."""
        wo_id = 1
        product_ids = [p["id"] for p in self.products]
        order_ids = [o["id"] for o in self.orders if o["status"] not in ["cancelled"]]

        # Status distribution
        def get_wo_status():
            r = random.random()
            if r < 0.05:
                return "released"
            elif r < 0.15:
                return "in_progress"
            elif r < 0.17:
                return "quality_hold"
            elif r < 0.97:
                return "completed"
            else:
                return "cancelled"

        # Named work orders for testing
        named_wos = [
            ("WO-2024-00001", 1, 3, 1, "make_to_order", 1, 100, "completed"),  # Product 1 at NYC Factory for Order 1
            ("WO-2024-00002", 2, 5, 2, "make_to_order", 2, 50, "in_progress"),  # Product 2 at Munich for Order 2
            ("WO-2024-00003", 3, 3, None, "make_to_stock", 3, 200, "completed"),  # Make-to-stock
        ]

        for wo_num, prod_id, fac_id, order_id, order_type, priority, qty, status in named_wos:
            planned_start = fake.date_between(start_date="-6m", end_date="-1m")
            planned_end = planned_start + timedelta(days=random.randint(1, 14))
            actual_start = datetime.combine(planned_start, datetime.min.time()) + timedelta(hours=random.randint(0, 48))
            actual_end = None
            qty_completed = 0
            qty_scrapped = 0

            if status in ["completed", "quality_hold"]:
                actual_end = actual_start + timedelta(hours=random.randint(8, 120))
                scrap_rate = random.uniform(0.01, 0.08)
                qty_scrapped = int(qty * scrap_rate)
                qty_completed = qty - qty_scrapped

            self.work_orders.append({
                "id": wo_id,
                "wo_number": wo_num,
                "product_id": prod_id,
                "facility_id": fac_id,
                "order_id": order_id,
                "order_type": order_type,
                "priority": priority,
                "quantity_planned": qty,
                "quantity_completed": qty_completed,
                "quantity_scrapped": qty_scrapped,
                "status": status,
                "planned_start_date": planned_start,
                "planned_end_date": planned_end,
                "actual_start_date": actual_start if status != "released" else None,
                "actual_end_date": actual_end,
            })
            wo_id += 1

        # Make-to-order WOs: ~80% of total, linked to orders
        mto_count = int(count * 0.80)
        # Make-to-stock WOs: ~20% of total, no order link
        mts_count = count - mto_count

        # Generate make-to-order work orders
        for _ in range(mto_count - len([w for w in named_wos if w[4] == "make_to_order"])):
            status = get_wo_status()
            order_id = random.choice(order_ids) if order_ids else None
            product_id = random.choice(product_ids)
            facility_id = random.choice(self.factory_ids) if self.factory_ids else 1

            planned_start = fake.date_between(start_date="-2y", end_date="today")
            planned_end = planned_start + timedelta(days=random.randint(1, 21))
            qty = random.randint(10, 500)

            actual_start = None
            actual_end = None
            qty_completed = 0
            qty_scrapped = 0

            if status in ["in_progress", "completed", "quality_hold"]:
                actual_start = datetime.combine(planned_start, datetime.min.time()) + timedelta(hours=random.randint(0, 48))

            if status in ["completed", "quality_hold"]:
                actual_end = actual_start + timedelta(hours=random.randint(8, 240)) if actual_start else None
                scrap_rate = random.uniform(0.02, 0.10)
                qty_scrapped = int(qty * scrap_rate)
                qty_completed = qty - qty_scrapped if status == "completed" else int(qty * random.uniform(0.5, 0.9))

            self.work_orders.append({
                "id": wo_id,
                "wo_number": f"WO-{wo_id:08d}",
                "product_id": product_id,
                "facility_id": facility_id,
                "order_id": order_id,
                "order_type": "make_to_order",
                "priority": random.randint(1, 5),
                "quantity_planned": qty,
                "quantity_completed": qty_completed,
                "quantity_scrapped": qty_scrapped,
                "status": status,
                "planned_start_date": planned_start,
                "planned_end_date": planned_end,
                "actual_start_date": actual_start,
                "actual_end_date": actual_end,
            })
            wo_id += 1

        # Generate make-to-stock work orders
        for _ in range(mts_count - len([w for w in named_wos if w[4] == "make_to_stock"])):
            status = get_wo_status()
            product_id = random.choice(product_ids)
            facility_id = random.choice(self.factory_ids) if self.factory_ids else 1

            planned_start = fake.date_between(start_date="-2y", end_date="today")
            planned_end = planned_start + timedelta(days=random.randint(1, 21))
            qty = random.randint(50, 1000)  # Larger batches for make-to-stock

            actual_start = None
            actual_end = None
            qty_completed = 0
            qty_scrapped = 0

            if status in ["in_progress", "completed", "quality_hold"]:
                actual_start = datetime.combine(planned_start, datetime.min.time()) + timedelta(hours=random.randint(0, 48))

            if status in ["completed", "quality_hold"]:
                actual_end = actual_start + timedelta(hours=random.randint(8, 240)) if actual_start else None
                scrap_rate = random.uniform(0.02, 0.10)
                qty_scrapped = int(qty * scrap_rate)
                qty_completed = qty - qty_scrapped if status == "completed" else int(qty * random.uniform(0.5, 0.9))

            self.work_orders.append({
                "id": wo_id,
                "wo_number": f"WO-{wo_id:08d}",
                "product_id": product_id,
                "facility_id": facility_id,
                "order_id": None,
                "order_type": "make_to_stock",
                "priority": random.randint(2, 5),  # Stock replenishment usually lower priority
                "quantity_planned": qty,
                "quantity_completed": qty_completed,
                "quantity_scrapped": qty_scrapped,
                "status": status,
                "planned_start_date": planned_start,
                "planned_end_date": planned_end,
                "actual_start_date": actual_start,
                "actual_end_date": actual_end,
            })
            wo_id += 1

    def generate_work_order_steps(self):
        """Generate work order steps tracking progress through routing."""
        step_id = 1

        # Build routing lookup by product
        routings_by_product: dict[int, list[dict]] = {}
        for r in self.production_routings:
            pid = r["product_id"]
            if pid not in routings_by_product:
                routings_by_product[pid] = []
            routings_by_product[pid].append(r)

        # Sort routings by sequence
        for pid in routings_by_product:
            routings_by_product[pid].sort(key=lambda x: x["step_sequence"])

        for wo in self.work_orders:
            product_id = wo["product_id"]
            routings = routings_by_product.get(product_id, [])

            if not routings:
                continue

            # Generate step records for each routing step
            qty_remaining = wo["quantity_planned"]

            for i, routing in enumerate(routings):
                # Determine step status based on WO status and position
                if wo["status"] == "released":
                    step_status = "pending"
                    qty_in = None
                    qty_out = None
                    qty_scrapped = 0
                elif wo["status"] == "cancelled":
                    step_status = "skipped" if i > 0 else "pending"
                    qty_in = None
                    qty_out = None
                    qty_scrapped = 0
                elif wo["status"] == "in_progress":
                    # Some steps completed, current one in progress, rest pending
                    progress_point = random.randint(0, len(routings) - 1)
                    if i < progress_point:
                        step_status = "completed"
                        qty_in = qty_remaining
                        step_scrap = int(qty_remaining * random.uniform(0, 0.03))
                        qty_scrapped = step_scrap
                        qty_out = qty_remaining - step_scrap
                        qty_remaining = qty_out
                    elif i == progress_point:
                        step_status = "in_progress"
                        qty_in = qty_remaining
                        qty_out = None
                        qty_scrapped = 0
                    else:
                        step_status = "pending"
                        qty_in = None
                        qty_out = None
                        qty_scrapped = 0
                else:  # completed or quality_hold
                    step_status = "completed"
                    qty_in = qty_remaining
                    step_scrap = int(qty_remaining * random.uniform(0, 0.03))
                    qty_scrapped = step_scrap
                    qty_out = qty_remaining - step_scrap
                    qty_remaining = qty_out

                # Timing
                planned_start = None
                actual_start = None
                actual_end = None

                if wo["actual_start_date"]:
                    planned_start = wo["actual_start_date"] + timedelta(hours=i * random.randint(1, 8))
                    if step_status in ["completed", "in_progress"]:
                        actual_start = planned_start + timedelta(minutes=random.randint(-30, 60))
                    if step_status == "completed":
                        actual_end = actual_start + timedelta(minutes=random.randint(30, 480))

                # Labor and machine hours
                labor_hours = None
                machine_hours = None
                if step_status == "completed" and qty_out:
                    run_time = routing["run_time_per_unit_mins"] * qty_out / 60
                    setup_time = routing["setup_time_mins"] / 60
                    machine_hours = round(setup_time + run_time, 2)
                    labor_hours = round(machine_hours * random.uniform(0.8, 1.2), 2)

                self.work_order_steps.append({
                    "id": step_id,
                    "work_order_id": wo["id"],
                    "routing_step_id": routing["id"],
                    "step_sequence": routing["step_sequence"],
                    "work_center_id": routing["work_center_id"],
                    "status": step_status,
                    "quantity_in": qty_in,
                    "quantity_out": qty_out,
                    "quantity_scrapped": qty_scrapped,
                    "planned_start": planned_start,
                    "actual_start": actual_start,
                    "actual_end": actual_end,
                    "labor_hours": labor_hours,
                    "machine_hours": machine_hours,
                })
                step_id += 1

    def generate_material_transactions(self):
        """Generate material transactions for WIP, consumption, and scrap."""
        tx_id = 1

        # Scrap reason distribution
        scrap_reasons = [
            ("quality_defect", 0.40),
            ("machine_error", 0.25),
            ("operator_error", 0.20),
            ("material_defect", 0.15),
        ]

        def get_scrap_reason():
            r = random.random()
            cumulative = 0
            for reason, prob in scrap_reasons:
                cumulative += prob
                if r < cumulative:
                    return reason
            return "quality_defect"

        # For completed/in_progress WOs, generate material transactions
        for wo in self.work_orders:
            if wo["status"] in ["released", "cancelled"]:
                continue

            product_id = wo["product_id"]
            facility_id = wo["facility_id"]
            wo_start = wo.get("actual_start_date") or datetime.now()

            # Find BOM for this product via product_components
            # product -> product_components -> parts (top-level) -> BOM (children)
            product_parts = [pc for pc in self.product_components if pc["product_id"] == product_id]

            # Get child parts from BOM for each top-level part
            consumed_parts = []
            for pc in product_parts:
                top_part_id = pc["part_id"]
                # Find BOM entries where this is the parent
                bom_entries = [b for b in self.bom if b["parent_part_id"] == top_part_id]
                for bom in bom_entries:
                    consumed_parts.append({
                        "part_id": bom["child_part_id"],
                        "qty_per_unit": bom["quantity"],
                    })

            # If no BOM found, use some random leaf parts
            if not consumed_parts and self.leaf_part_ids:
                for part_id in random.sample(self.leaf_part_ids, min(3, len(self.leaf_part_ids))):
                    consumed_parts.append({
                        "part_id": part_id,
                        "qty_per_unit": random.randint(1, 5),
                    })

            # Issue transactions (material consumption)
            for cp in consumed_parts[:5]:  # Limit to 5 parts per WO for manageable data
                qty = cp["qty_per_unit"] * wo["quantity_planned"]

                # Get unit cost from parts
                part = next((p for p in self.parts if p["id"] == cp["part_id"]), None)
                unit_cost = part["unit_cost"] if part else round(random.uniform(1, 50), 2)

                self.material_transactions.append({
                    "id": tx_id,
                    "transaction_number": f"MTX-{tx_id:08d}",
                    "transaction_type": "issue_to_wo",
                    "work_order_id": wo["id"],
                    "part_id": cp["part_id"],
                    "product_id": None,
                    "facility_id": facility_id,
                    "quantity": qty,
                    "unit_cost": unit_cost,
                    "reason_code": None,
                    "reference_number": wo["wo_number"],
                    "created_at": wo_start + timedelta(minutes=random.randint(0, 60)),
                    "created_by": random.choice(["system", "operator", "supervisor"]),
                })
                tx_id += 1

                # Scrap transaction for some issues (~5% scrap rate)
                if random.random() < 0.05:
                    scrap_qty = max(1, int(qty * random.uniform(0.01, 0.10)))
                    self.material_transactions.append({
                        "id": tx_id,
                        "transaction_number": f"MTX-{tx_id:08d}",
                        "transaction_type": "scrap",
                        "work_order_id": wo["id"],
                        "part_id": cp["part_id"],
                        "product_id": None,
                        "facility_id": facility_id,
                        "quantity": scrap_qty,
                        "unit_cost": unit_cost,
                        "reason_code": get_scrap_reason(),
                        "reference_number": wo["wo_number"],
                        "created_at": wo_start + timedelta(hours=random.randint(1, 24)),
                        "created_by": random.choice(["qc_inspector", "operator", "supervisor"]),
                    })
                    tx_id += 1

            # Receipt transaction (product completion) - only for completed WOs
            if wo["status"] == "completed" and wo["quantity_completed"] > 0:
                # Get product list price as cost basis
                product = next((p for p in self.products if p["id"] == product_id), None)
                unit_cost = product["list_price"] * 0.6 if product else round(random.uniform(50, 500), 2)  # ~60% of list

                self.material_transactions.append({
                    "id": tx_id,
                    "transaction_number": f"MTX-{tx_id:08d}",
                    "transaction_type": "receipt_from_wo",
                    "work_order_id": wo["id"],
                    "part_id": None,
                    "product_id": product_id,
                    "facility_id": facility_id,
                    "quantity": wo["quantity_completed"],
                    "unit_cost": unit_cost,
                    "reason_code": None,
                    "reference_number": wo["wo_number"],
                    "created_at": wo["actual_end_date"] if wo["actual_end_date"] else wo_start + timedelta(days=1),
                    "created_by": "system",
                })
                tx_id += 1

    def generate_supplier_hub_facilities(self):
        """
        Create virtual supplier hub facilities - one per supplier country.

        These hubs serve as origin points for procurement shipments,
        solving the problem of PO shipments needing a facility origin.
        """
        # Get unique supplier countries
        supplier_countries = set(s["country"] for s in self.suppliers if s["country"])

        # Get next facility ID
        next_id = max(f["id"] for f in self.facilities) + 1

        for country in sorted(supplier_countries):
            # Create country code (2-letter)
            country_code = {
                "USA": "US", "China": "CN", "Germany": "DE", "Japan": "JP",
                "Mexico": "MX", "Canada": "CA", "UK": "GB", "Taiwan": "TW",
                "South Korea": "KR", "India": "IN"
            }.get(country, country[:2].upper())

            hub = {
                "id": next_id,
                "facility_code": f"SUPHUB-{country_code}",
                "name": f"{country} Supplier Hub",
                "facility_type": "supplier_hub",
                "city": None,
                "state": None,
                "country": country,
                "latitude": None,
                "longitude": None,
                "capacity_units": None,
                "is_active": True,
            }
            self.facilities.append(hub)
            self.supplier_hub_facility_ids[country] = next_id
            next_id += 1

    def generate_demand_forecasts(self, count: int):
        """
        Generate demand forecasts for S&OP planning.

        Uses sine wave seasonality with category-specific phase shifts:
        - Electronics: peak Nov-Dec (phase = 11)
        - Industrial: peak Q1 (phase = 1)
        - Consumer: peak summer (phase = 7)
        - Others: random phase
        """
        import math

        forecast_id = 1
        product_ids = [p["id"] for p in self.products]
        dc_ids = self.dc_facility_ids if self.dc_facility_ids else [f["id"] for f in self.facilities][:10]

        # Category phase shifts (month of peak demand)
        category_phases = {
            "Electronics": 11,  # Peak in November
            "Industrial": 1,    # Peak in Q1
            "Consumer": 7,      # Peak in summer
            "Automotive": 3,    # Peak in spring
            "Medical": 9,       # Peak in fall
        }

        # Forecast type distribution
        def get_forecast_type():
            r = random.random()
            if r < 0.60:
                return "statistical"
            elif r < 0.75:
                return "manual"
            elif r < 0.90:
                return "consensus"
            else:
                return "machine_learning"

        # Named forecasts for testing
        named_forecasts = [
            ("FC-2024-001", 1, dc_ids[0] if dc_ids else 1, date(2024, 1, 1), 500, "statistical"),
            ("FC-2024-002", 2, dc_ids[0] if dc_ids else 1, date(2024, 2, 1), 300, "consensus"),
            ("FC-2024-003", 1, dc_ids[1] if len(dc_ids) > 1 else 1, date(2024, 1, 1), 200, "machine_learning"),
        ]

        for fc_num, prod_id, fac_id, fc_date, qty, fc_type in named_forecasts:
            product = next((p for p in self.products if p["id"] == prod_id), None)
            category = product.get("category", "Industrial") if product else "Industrial"
            phase = category_phases.get(category, random.randint(1, 12))

            # Calculate seasonality factor
            month = fc_date.month
            seasonality = 1.0 + 0.3 * math.sin(2 * math.pi * (month - phase) / 12)

            self.demand_forecasts.append({
                "id": forecast_id,
                "forecast_number": fc_num,
                "product_id": prod_id,
                "facility_id": fac_id,
                "forecast_date": fc_date,
                "forecast_quantity": qty,
                "forecast_type": fc_type,
                "confidence_level": round(random.uniform(0.70, 0.95), 2),
                "seasonality_factor": round(seasonality, 2),
            })
            forecast_id += 1

        # Generate remaining forecasts
        # 12 months of forecasts per product per DC (subset)
        products_sample = random.sample(product_ids, min(200, len(product_ids)))
        dcs_sample = random.sample(dc_ids, min(5, len(dc_ids)))

        remaining = count - len(named_forecasts)
        generated = 0

        for prod_id in products_sample:
            if generated >= remaining:
                break

            product = next((p for p in self.products if p["id"] == prod_id), None)
            category = product.get("category", "Industrial") if product else "Industrial"
            phase = category_phases.get(category, random.randint(1, 12))
            base_qty = random.randint(50, 500)

            for dc_id in dcs_sample:
                if generated >= remaining:
                    break

                for month_offset in range(12):
                    if generated >= remaining:
                        break

                    fc_date = date(2024, 1, 1) + timedelta(days=month_offset * 30)
                    month = fc_date.month
                    seasonality = 1.0 + 0.3 * math.sin(2 * math.pi * (month - phase) / 12)
                    qty = int(base_qty * seasonality * random.uniform(0.9, 1.1))

                    self.demand_forecasts.append({
                        "id": forecast_id,
                        "forecast_number": f"FC-{forecast_id:08d}",
                        "product_id": prod_id,
                        "facility_id": dc_id,
                        "forecast_date": fc_date,
                        "forecast_quantity": qty,
                        "forecast_type": get_forecast_type(),
                        "confidence_level": round(random.uniform(0.60, 0.98), 2),
                        "seasonality_factor": round(seasonality, 2),
                    })
                    forecast_id += 1
                    generated += 1

    def generate_purchase_orders(self, count: int):
        """
        Generate purchase orders for parts procurement.

        Links via part_suppliers table (approved suppliers for parts).
        Creates 'procurement' shipments from supplier hubs.
        """
        po_id = 1
        facility_ids = [f["id"] for f in self.facilities if f["facility_type"] != "supplier_hub"]

        # Build approved supplier lookup from part_suppliers
        approved_suppliers: dict[int, list[int]] = {}  # part_id -> [supplier_ids]
        for ps in self.part_suppliers:
            if ps.get("is_approved", True):
                part_id = ps["part_id"]
                if part_id not in approved_suppliers:
                    approved_suppliers[part_id] = []
                approved_suppliers[part_id].append(ps["supplier_id"])

        # Status distribution
        def get_po_status():
            r = random.random()
            if r < 0.05:
                return "draft"
            elif r < 0.10:
                return "submitted"
            elif r < 0.15:
                return "confirmed"
            elif r < 0.25:
                return "shipped"
            elif r < 0.95:
                return "received"
            else:
                return "cancelled"

        # Named POs for testing
        named_pos = [
            ("PO-2024-00001", 1, 1, date(2024, 1, 15), "received"),  # Supplier 1, Facility 1
            ("PO-2024-00002", 2, 1, date(2024, 2, 1), "shipped"),    # Supplier 2, Facility 1
            ("PO-2024-00003", 4, 2, date(2024, 3, 1), "confirmed"),  # Pacific Components, Facility 2
        ]

        shipment_id = max(s["id"] for s in self.shipments) + 1 if self.shipments else 1

        for po_num, supplier_id, facility_id, order_date, status in named_pos:
            supplier = next((s for s in self.suppliers if s["id"] == supplier_id), None)
            lead_time = random.randint(14, 45)
            expected_date = order_date + timedelta(days=lead_time)

            received_date = None
            if status == "received":
                # Add variance: ±20-30%
                variance = random.uniform(-0.3, 0.2)
                actual_days = int(lead_time * (1 + variance))
                received_date = order_date + timedelta(days=actual_days)

            self.purchase_orders.append({
                "id": po_id,
                "po_number": po_num,
                "supplier_id": supplier_id,
                "facility_id": facility_id,
                "order_date": order_date,
                "expected_date": expected_date,
                "received_date": received_date,
                "status": status,
                "total_amount": 0,  # Will calculate from lines
            })

            # Generate 1-5 PO lines
            num_lines = random.randint(1, 5)
            total = 0
            parts_with_supplier = [p for p in self.parts if supplier_id in approved_suppliers.get(p["id"], [supplier_id])]
            if not parts_with_supplier:
                parts_with_supplier = random.sample(self.parts, min(10, len(self.parts)))

            for line_num in range(1, num_lines + 1):
                part = random.choice(parts_with_supplier)
                qty = random.randint(100, 1000)
                unit_price = part["unit_cost"] * random.uniform(0.9, 1.1)

                line_status = "received" if status == "received" else "pending"
                qty_received = qty if status == "received" else 0

                self.purchase_order_lines.append({
                    "purchase_order_id": po_id,
                    "line_number": line_num,
                    "part_id": part["id"],
                    "quantity": qty,
                    "unit_price": round(unit_price, 2),
                    "quantity_received": qty_received,
                    "status": line_status,
                })
                total += qty * unit_price

            self.purchase_orders[-1]["total_amount"] = round(total, 2)

            # Create procurement shipment for shipped/received POs
            if status in ["shipped", "received"]:
                supplier_country = supplier["country"] if supplier else "USA"
                origin_hub = self.supplier_hub_facility_ids.get(supplier_country)
                if not origin_hub:
                    origin_hub = list(self.supplier_hub_facility_ids.values())[0] if self.supplier_hub_facility_ids else facility_id

                ship_date = order_date + timedelta(days=random.randint(3, 10))
                self.shipments.append({
                    "id": shipment_id,
                    "shipment_number": f"PROC-{shipment_id:08d}",
                    "order_id": None,
                    "purchase_order_id": po_id,
                    "return_id": None,
                    "origin_facility_id": origin_hub,
                    "destination_facility_id": facility_id,
                    "transport_route_id": None,
                    "shipment_type": "procurement",
                    "carrier": random.choice(["Ocean Freight", "Air Cargo", "Express Logistics"]),
                    "tracking_number": fake.bothify("PROC??#########"),
                    "status": "delivered" if status == "received" else "in_transit",
                    "shipped_at": datetime.combine(ship_date, datetime.min.time()),
                    "delivered_at": datetime.combine(received_date, datetime.min.time()) if received_date else None,
                    "weight_kg": round(random.uniform(100, 5000), 2),
                    "cost_usd": round(random.uniform(500, 5000), 2),
                })
                shipment_id += 1

            po_id += 1

        # Generate remaining POs
        supplier_ids = [s["id"] for s in self.suppliers]
        remaining = count - len(named_pos)

        for _ in range(remaining):
            supplier_id = random.choice(supplier_ids)
            supplier = next((s for s in self.suppliers if s["id"] == supplier_id), None)
            facility_id = random.choice(facility_ids)
            order_date = fake.date_between(start_date="-2y", end_date="today")
            status = get_po_status()

            lead_time = random.randint(14, 60)
            expected_date = order_date + timedelta(days=lead_time)

            received_date = None
            if status == "received":
                variance = random.uniform(-0.3, 0.2)
                actual_days = int(lead_time * (1 + variance))
                received_date = order_date + timedelta(days=actual_days)

            self.purchase_orders.append({
                "id": po_id,
                "po_number": f"PO-{po_id:08d}",
                "supplier_id": supplier_id,
                "facility_id": facility_id,
                "order_date": order_date,
                "expected_date": expected_date,
                "received_date": received_date,
                "status": status,
                "total_amount": 0,
            })

            # Generate PO lines
            num_lines = random.randint(1, 5)
            total = 0
            parts_with_supplier = [p for p in self.parts if supplier_id in approved_suppliers.get(p["id"], [supplier_id])]
            if not parts_with_supplier:
                parts_with_supplier = random.sample(self.parts, min(10, len(self.parts)))

            for line_num in range(1, num_lines + 1):
                part = random.choice(parts_with_supplier)
                qty = random.randint(50, 500)
                unit_price = part["unit_cost"] * random.uniform(0.85, 1.15)

                if status == "received":
                    line_status = "received"
                    qty_received = qty
                elif status == "cancelled":
                    line_status = "cancelled"
                    qty_received = 0
                else:
                    line_status = "pending"
                    qty_received = 0

                self.purchase_order_lines.append({
                    "purchase_order_id": po_id,
                    "line_number": line_num,
                    "part_id": part["id"],
                    "quantity": qty,
                    "unit_price": round(unit_price, 2),
                    "quantity_received": qty_received,
                    "status": line_status,
                })
                total += qty * unit_price

            self.purchase_orders[-1]["total_amount"] = round(total, 2)

            # Create procurement shipment for shipped/received POs
            if status in ["shipped", "received"]:
                supplier_country = supplier["country"] if supplier else "USA"
                origin_hub = self.supplier_hub_facility_ids.get(supplier_country)
                if not origin_hub:
                    origin_hub = list(self.supplier_hub_facility_ids.values())[0] if self.supplier_hub_facility_ids else facility_id

                ship_date = order_date + timedelta(days=random.randint(3, 10))
                self.shipments.append({
                    "id": shipment_id,
                    "shipment_number": f"PROC-{shipment_id:08d}",
                    "order_id": None,
                    "purchase_order_id": po_id,
                    "return_id": None,
                    "origin_facility_id": origin_hub,
                    "destination_facility_id": facility_id,
                    "transport_route_id": None,
                    "shipment_type": "procurement",
                    "carrier": random.choice(["Ocean Freight", "Air Cargo", "Express Logistics", "Ground Freight"]),
                    "tracking_number": fake.bothify("PROC??#########"),
                    "status": "delivered" if status == "received" else "in_transit",
                    "shipped_at": datetime.combine(ship_date, datetime.min.time()),
                    "delivered_at": datetime.combine(received_date, datetime.min.time()) if received_date else None,
                    "weight_kg": round(random.uniform(50, 2000), 2),
                    "cost_usd": round(random.uniform(200, 3000), 2),
                })
                shipment_id += 1

            po_id += 1

    def generate_returns(self, count: int):
        """
        Generate customer returns (RMAs).

        Only from delivered orders (~5% return rate).
        Creates 'return' shipments back to shipping facility.
        """
        return_id = 1

        # Get delivered orders
        delivered_orders = [o for o in self.orders if o["status"] == "delivered"]
        if not delivered_orders:
            print("Warning: No delivered orders found for returns")
            return

        # Reason distribution
        reasons = [
            ("defective", 0.35),
            ("damaged", 0.20),
            ("wrong_item", 0.15),
            ("not_as_described", 0.15),
            ("changed_mind", 0.15),
        ]

        def get_return_reason():
            r = random.random()
            cumulative = 0
            for reason, prob in reasons:
                cumulative += prob
                if r < cumulative:
                    return reason
            return "defective"

        # Disposition by reason
        disposition_by_reason = {
            "defective": [("scrap", 0.60), ("refurbish", 0.30), ("restock", 0.10)],
            "damaged": [("scrap", 0.40), ("refurbish", 0.40), ("restock", 0.20)],
            "wrong_item": [("restock", 0.90), ("refurbish", 0.10)],
            "not_as_described": [("restock", 0.70), ("refurbish", 0.20), ("scrap", 0.10)],
            "changed_mind": [("restock", 0.95), ("refurbish", 0.05)],
        }

        def get_disposition(reason: str):
            dispositions = disposition_by_reason.get(reason, [("restock", 1.0)])
            r = random.random()
            cumulative = 0
            for disp, prob in dispositions:
                cumulative += prob
                if r < cumulative:
                    return disp
            return "restock"

        # Named returns for testing
        named_returns = [
            ("RMA-2024-001", delivered_orders[0]["id"], delivered_orders[0]["customer_id"], "defective"),
            ("RMA-2024-002", delivered_orders[1]["id"] if len(delivered_orders) > 1 else delivered_orders[0]["id"],
             delivered_orders[1]["customer_id"] if len(delivered_orders) > 1 else delivered_orders[0]["customer_id"],
             "changed_mind"),
        ]

        shipment_id = max(s["id"] for s in self.shipments) + 1 if self.shipments else 1

        for rma_num, order_id, customer_id, reason in named_returns:
            order = next((o for o in self.orders if o["id"] == order_id), None)
            order_items = [oi for oi in self.order_items if oi["order_id"] == order_id]

            if not order or not order_items:
                continue

            return_date = order["shipped_date"].date() + timedelta(days=random.randint(5, 30)) if order.get("shipped_date") else date.today()

            self.returns.append({
                "id": return_id,
                "rma_number": rma_num,
                "order_id": order_id,
                "customer_id": customer_id,
                "return_date": return_date,
                "return_reason": reason,
                "status": random.choice(["received", "processed"]),
                "refund_amount": round(order["total_amount"] * random.uniform(0.8, 1.0), 2),
                "refund_status": "processed",
            })

            # Return 1-3 items from the order
            num_items = min(random.randint(1, 3), len(order_items))
            returned_items = random.sample(order_items, num_items)

            for line_num, oi in enumerate(returned_items, 1):
                qty_to_return = random.randint(1, oi["quantity"])
                self.return_items.append({
                    "return_id": return_id,
                    "line_number": line_num,
                    "order_id": oi["order_id"],
                    "order_line_number": oi["line_number"],
                    "quantity_returned": qty_to_return,
                    "disposition": get_disposition(reason),
                })

            # Create return shipment
            shipping_facility = order.get("shipping_facility_id", 1)
            self.shipments.append({
                "id": shipment_id,
                "shipment_number": f"RET-{shipment_id:08d}",
                "order_id": None,
                "purchase_order_id": None,
                "return_id": return_id,
                "origin_facility_id": shipping_facility,  # Returns come back to shipping facility
                "destination_facility_id": shipping_facility,
                "transport_route_id": None,
                "shipment_type": "return",
                "carrier": random.choice(["Return Logistics", "Express Return", "Customer Drop-off"]),
                "tracking_number": fake.bothify("RET??#########"),
                "status": "delivered",
                "shipped_at": datetime.combine(return_date, datetime.min.time()),
                "delivered_at": datetime.combine(return_date + timedelta(days=random.randint(3, 10)), datetime.min.time()),
                "weight_kg": round(random.uniform(1, 20), 2),
                "cost_usd": round(random.uniform(10, 100), 2),
            })
            shipment_id += 1

            return_id += 1

        # Generate remaining returns (~5% of delivered orders)
        remaining = count - len(named_returns)
        returns_to_generate = min(remaining, int(len(delivered_orders) * 0.05))
        orders_for_returns = random.sample(delivered_orders, min(returns_to_generate, len(delivered_orders)))

        for order in orders_for_returns:
            order_items = [oi for oi in self.order_items if oi["order_id"] == order["id"]]
            if not order_items:
                continue

            reason = get_return_reason()
            return_date = order["shipped_date"].date() + timedelta(days=random.randint(5, 45)) if order.get("shipped_date") else date.today()

            status = random.choice(["requested", "approved", "received", "processed"])
            refund_status = "processed" if status == "processed" else ("pending" if status != "rejected" else "denied")

            self.returns.append({
                "id": return_id,
                "rma_number": f"RMA-{return_id:08d}",
                "order_id": order["id"],
                "customer_id": order["customer_id"],
                "return_date": return_date,
                "return_reason": reason,
                "status": status,
                "refund_amount": round(order["total_amount"] * random.uniform(0.5, 1.0), 2),
                "refund_status": refund_status,
            })

            # Return 1-3 items
            num_items = min(random.randint(1, 3), len(order_items))
            returned_items = random.sample(order_items, num_items)

            for line_num, oi in enumerate(returned_items, 1):
                qty_to_return = random.randint(1, oi["quantity"])
                self.return_items.append({
                    "return_id": return_id,
                    "line_number": line_num,
                    "order_id": oi["order_id"],
                    "order_line_number": oi["line_number"],
                    "quantity_returned": qty_to_return,
                    "disposition": get_disposition(reason) if status in ["received", "processed"] else "pending",
                })

            # Create return shipment for received/processed returns
            if status in ["received", "processed"]:
                shipping_facility = order.get("shipping_facility_id", 1)
                self.shipments.append({
                    "id": shipment_id,
                    "shipment_number": f"RET-{shipment_id:08d}",
                    "order_id": None,
                    "purchase_order_id": None,
                    "return_id": return_id,
                    "origin_facility_id": shipping_facility,
                    "destination_facility_id": shipping_facility,
                    "transport_route_id": None,
                    "shipment_type": "return",
                    "carrier": random.choice(["Return Logistics", "Express Return", "Ground Return"]),
                    "tracking_number": fake.bothify("RET??#########"),
                    "status": "delivered",
                    "shipped_at": datetime.combine(return_date, datetime.min.time()),
                    "delivered_at": datetime.combine(return_date + timedelta(days=random.randint(2, 7)), datetime.min.time()),
                    "weight_kg": round(random.uniform(0.5, 15), 2),
                    "cost_usd": round(random.uniform(5, 75), 2),
                })
                shipment_id += 1

            return_id += 1

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
                f"INSERT INTO supplier_relationships (id, seller_id, buyer_id, relationship_type, contract_start_date, is_primary, is_active, relationship_status) "
                f"VALUES ({sr['id']}, {sr['seller_id']}, {sr['buyer_id']}, {sql_str(sr['relationship_type'])}, "
                f"{sql_date(sr.get('contract_start_date'))}, {sql_bool(sr['is_primary'])}, "
                f"{sql_bool(sr.get('is_active', True))}, {sql_str(sr.get('relationship_status', 'active'))});"
            )
        lines.append(f"SELECT setval('supplier_relationships_id_seq', {max(sr['id'] for sr in self.supplier_relationships)});")
        lines.append("")

        # Parts
        lines.append("-- Parts")
        for p in self.parts:
            lines.append(
                f"INSERT INTO parts (id, part_number, description, category, unit_cost, weight_kg, lead_time_days, "
                f"primary_supplier_id, is_critical, min_stock_level, base_uom, unit_weight_kg, unit_length_m, unit_volume_l) "
                f"VALUES ({p['id']}, {sql_str(p['part_number'])}, {sql_str(p['description'])}, {sql_str(p['category'])}, "
                f"{sql_num(p['unit_cost'])}, {sql_num(p['weight_kg'])}, {sql_num(p['lead_time_days'])}, "
                f"{sql_num(p.get('primary_supplier_id'))}, {sql_bool(p['is_critical'])}, {sql_num(p['min_stock_level'])}, "
                f"{sql_str(p.get('base_uom', 'each'))}, {sql_num(p.get('unit_weight_kg'))}, "
                f"{sql_num(p.get('unit_length_m'))}, {sql_num(p.get('unit_volume_l'))});"
            )
        lines.append(f"SELECT setval('parts_id_seq', {max(p['id'] for p in self.parts)});")
        lines.append("")

        # Bill of Materials
        lines.append("-- Bill of Materials")
        for b in self.bom:
            lines.append(
                f"INSERT INTO bill_of_materials (id, parent_part_id, child_part_id, quantity, unit, is_optional, assembly_sequence, effective_from, effective_to) "
                f"VALUES ({b['id']}, {b['parent_part_id']}, {b['child_part_id']}, {b['quantity']}, "
                f"{sql_str(b['unit'])}, {sql_bool(b['is_optional'])}, {sql_num(b.get('assembly_sequence'))}, "
                f"{sql_date(b.get('effective_from'))}, {sql_date(b.get('effective_to'))});"
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
                f"distance_km, transit_time_hours, cost_usd, capacity_tons, is_active, route_status) "
                f"VALUES ({tr['id']}, {tr['origin_facility_id']}, {tr['destination_facility_id']}, {sql_str(tr['transport_mode'])}, "
                f"{sql_num(tr['distance_km'])}, {sql_num(tr['transit_time_hours'])}, {sql_num(tr['cost_usd'])}, "
                f"{sql_num(tr['capacity_tons'])}, {sql_bool(tr['is_active'])}, {sql_str(tr.get('route_status', 'active'))});"
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

        # Order Items (composite key: order_id, line_number)
        lines.append("-- Order Items (SAP-style composite key)")
        for oi in self.order_items:
            lines.append(
                f"INSERT INTO order_items (order_id, line_number, product_id, quantity, unit_price, discount_percent) "
                f"VALUES ({oi['order_id']}, {oi['line_number']}, {oi['product_id']}, {oi['quantity']}, "
                f"{sql_num(oi['unit_price'])}, {sql_num(oi.get('discount_percent', 0))});"
            )
        # No sequence for composite key table
        lines.append("")

        # NOTE: Shipments moved to after Returns due to FK dependencies (purchase_order_id, return_id)

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

        # Work Centers
        lines.append("-- Work Centers")
        for wc in self.work_centers:
            lines.append(
                f"INSERT INTO work_centers (id, wc_code, name, facility_id, work_center_type, capacity_per_day, "
                f"efficiency_rating, hourly_rate_usd, setup_time_mins, is_active) "
                f"VALUES ({wc['id']}, {sql_str(wc['wc_code'])}, {sql_str(wc['name'])}, {wc['facility_id']}, "
                f"{sql_str(wc['work_center_type'])}, {sql_num(wc.get('capacity_per_day'))}, "
                f"{sql_num(wc.get('efficiency_rating'))}, {sql_num(wc.get('hourly_rate_usd'))}, "
                f"{sql_num(wc.get('setup_time_mins'))}, {sql_bool(wc.get('is_active', True))});"
            )
        if self.work_centers:
            lines.append(f"SELECT setval('work_centers_id_seq', {max(wc['id'] for wc in self.work_centers)});")
        lines.append("")

        # Production Routings
        lines.append("-- Production Routings")
        for pr in self.production_routings:
            lines.append(
                f"INSERT INTO production_routings (id, product_id, step_sequence, operation_name, work_center_id, "
                f"setup_time_mins, run_time_per_unit_mins, is_active, effective_from, effective_to) "
                f"VALUES ({pr['id']}, {pr['product_id']}, {pr['step_sequence']}, {sql_str(pr['operation_name'])}, "
                f"{pr['work_center_id']}, {sql_num(pr.get('setup_time_mins'))}, {sql_num(pr['run_time_per_unit_mins'])}, "
                f"{sql_bool(pr.get('is_active', True))}, {sql_date(pr.get('effective_from'))}, {sql_date(pr.get('effective_to'))});"
            )
        if self.production_routings:
            lines.append(f"SELECT setval('production_routings_id_seq', {max(pr['id'] for pr in self.production_routings)});")
        lines.append("")

        # Work Orders
        lines.append("-- Work Orders")
        for wo in self.work_orders:
            lines.append(
                f"INSERT INTO work_orders (id, wo_number, product_id, facility_id, order_id, order_type, priority, "
                f"quantity_planned, quantity_completed, quantity_scrapped, status, planned_start_date, planned_end_date, "
                f"actual_start_date, actual_end_date) "
                f"VALUES ({wo['id']}, {sql_str(wo['wo_number'])}, {wo['product_id']}, {wo['facility_id']}, "
                f"{sql_num(wo.get('order_id'))}, {sql_str(wo['order_type'])}, {wo['priority']}, "
                f"{wo['quantity_planned']}, {wo['quantity_completed']}, {wo['quantity_scrapped']}, "
                f"{sql_str(wo['status'])}, {sql_date(wo.get('planned_start_date'))}, {sql_date(wo.get('planned_end_date'))}, "
                f"{sql_timestamp(wo.get('actual_start_date'))}, {sql_timestamp(wo.get('actual_end_date'))});"
            )
        if self.work_orders:
            lines.append(f"SELECT setval('work_orders_id_seq', {max(wo['id'] for wo in self.work_orders)});")
        lines.append("")

        # Work Order Steps
        lines.append("-- Work Order Steps")
        for ws in self.work_order_steps:
            lines.append(
                f"INSERT INTO work_order_steps (id, work_order_id, routing_step_id, step_sequence, work_center_id, "
                f"status, quantity_in, quantity_out, quantity_scrapped, planned_start, actual_start, actual_end, "
                f"labor_hours, machine_hours) "
                f"VALUES ({ws['id']}, {ws['work_order_id']}, {sql_num(ws.get('routing_step_id'))}, {ws['step_sequence']}, "
                f"{ws['work_center_id']}, {sql_str(ws['status'])}, {sql_num(ws.get('quantity_in'))}, "
                f"{sql_num(ws.get('quantity_out'))}, {sql_num(ws.get('quantity_scrapped', 0))}, "
                f"{sql_timestamp(ws.get('planned_start'))}, {sql_timestamp(ws.get('actual_start'))}, "
                f"{sql_timestamp(ws.get('actual_end'))}, {sql_num(ws.get('labor_hours'))}, {sql_num(ws.get('machine_hours'))});"
            )
        if self.work_order_steps:
            lines.append(f"SELECT setval('work_order_steps_id_seq', {max(ws['id'] for ws in self.work_order_steps)});")
        lines.append("")

        # Material Transactions
        lines.append("-- Material Transactions")
        for mt in self.material_transactions:
            lines.append(
                f"INSERT INTO material_transactions (id, transaction_number, transaction_type, work_order_id, part_id, "
                f"product_id, facility_id, quantity, unit_cost, reason_code, reference_number, created_at, created_by) "
                f"VALUES ({mt['id']}, {sql_str(mt['transaction_number'])}, {sql_str(mt['transaction_type'])}, "
                f"{mt['work_order_id']}, {sql_num(mt.get('part_id'))}, {sql_num(mt.get('product_id'))}, "
                f"{mt['facility_id']}, {mt['quantity']}, {sql_num(mt.get('unit_cost'))}, "
                f"{sql_str(mt.get('reason_code'))}, {sql_str(mt.get('reference_number'))}, "
                f"{sql_timestamp(mt.get('created_at'))}, {sql_str(mt.get('created_by'))});"
            )
        if self.material_transactions:
            lines.append(f"SELECT setval('material_transactions_id_seq', {max(mt['id'] for mt in self.material_transactions)});")
        lines.append("")

        # Demand Forecasts (PLAN domain)
        lines.append("-- Demand Forecasts")
        for df in self.demand_forecasts:
            lines.append(
                f"INSERT INTO demand_forecasts (id, forecast_number, product_id, facility_id, forecast_date, "
                f"forecast_quantity, forecast_type, confidence_level, seasonality_factor) "
                f"VALUES ({df['id']}, {sql_str(df['forecast_number'])}, {df['product_id']}, {df['facility_id']}, "
                f"{sql_date(df['forecast_date'])}, {df['forecast_quantity']}, {sql_str(df['forecast_type'])}, "
                f"{sql_num(df.get('confidence_level'))}, {sql_num(df.get('seasonality_factor'))});"
            )
        if self.demand_forecasts:
            lines.append(f"SELECT setval('demand_forecasts_id_seq', {max(df['id'] for df in self.demand_forecasts)});")
        lines.append("")

        # Purchase Orders (SOURCE domain)
        lines.append("-- Purchase Orders")
        for po in self.purchase_orders:
            lines.append(
                f"INSERT INTO purchase_orders (id, po_number, supplier_id, facility_id, order_date, expected_date, "
                f"received_date, status, total_amount) "
                f"VALUES ({po['id']}, {sql_str(po['po_number'])}, {po['supplier_id']}, {po['facility_id']}, "
                f"{sql_date(po['order_date'])}, {sql_date(po.get('expected_date'))}, {sql_date(po.get('received_date'))}, "
                f"{sql_str(po['status'])}, {sql_num(po.get('total_amount'))});"
            )
        if self.purchase_orders:
            lines.append(f"SELECT setval('purchase_orders_id_seq', {max(po['id'] for po in self.purchase_orders)});")
        lines.append("")

        # Purchase Order Lines (composite key)
        lines.append("-- Purchase Order Lines")
        for pol in self.purchase_order_lines:
            lines.append(
                f"INSERT INTO purchase_order_lines (purchase_order_id, line_number, part_id, quantity, unit_price, "
                f"quantity_received, status) "
                f"VALUES ({pol['purchase_order_id']}, {pol['line_number']}, {pol['part_id']}, {pol['quantity']}, "
                f"{sql_num(pol['unit_price'])}, {sql_num(pol.get('quantity_received', 0))}, {sql_str(pol['status'])});"
            )
        lines.append("")

        # Returns (RETURN domain)
        lines.append("-- Returns")
        for r in self.returns:
            lines.append(
                f"INSERT INTO returns (id, rma_number, order_id, customer_id, return_date, return_reason, "
                f"status, refund_amount, refund_status) "
                f"VALUES ({r['id']}, {sql_str(r['rma_number'])}, {r['order_id']}, {r['customer_id']}, "
                f"{sql_date(r['return_date'])}, {sql_str(r['return_reason'])}, {sql_str(r['status'])}, "
                f"{sql_num(r.get('refund_amount'))}, {sql_str(r.get('refund_status'))});"
            )
        if self.returns:
            lines.append(f"SELECT setval('returns_id_seq', {max(r['id'] for r in self.returns)});")
        lines.append("")

        # Return Items (composite key)
        lines.append("-- Return Items")
        for ri in self.return_items:
            lines.append(
                f"INSERT INTO return_items (return_id, line_number, order_id, order_line_number, quantity_returned, disposition) "
                f"VALUES ({ri['return_id']}, {ri['line_number']}, {ri['order_id']}, {ri['order_line_number']}, "
                f"{ri['quantity_returned']}, {sql_str(ri['disposition'])});"
            )
        lines.append("")

        # Shipments (after PO/Returns due to FK dependencies)
        lines.append("-- Shipments")
        for sh in self.shipments:
            lines.append(
                f"INSERT INTO shipments (id, shipment_number, order_id, purchase_order_id, return_id, origin_facility_id, destination_facility_id, "
                f"transport_route_id, shipment_type, carrier, tracking_number, status, shipped_at, delivered_at, weight_kg, cost_usd) "
                f"VALUES ({sh['id']}, {sql_str(sh['shipment_number'])}, {sql_num(sh.get('order_id'))}, "
                f"{sql_num(sh.get('purchase_order_id'))}, {sql_num(sh.get('return_id'))}, "
                f"{sh['origin_facility_id']}, {sql_num(sh.get('destination_facility_id'))}, {sql_num(sh.get('transport_route_id'))}, "
                f"{sql_str(sh.get('shipment_type', 'order_fulfillment'))}, "
                f"{sql_str(sh.get('carrier'))}, {sql_str(sh.get('tracking_number'))}, {sql_str(sh['status'])}, "
                f"{sql_timestamp(sh.get('shipped_at'))}, {sql_timestamp(sh.get('delivered_at'))}, "
                f"{sql_num(sh.get('weight_kg'))}, {sql_num(sh.get('cost_usd'))});"
            )
        if self.shipments:
            lines.append(f"SELECT setval('shipments_id_seq', {max(sh['id'] for sh in self.shipments)});")
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
            len(self.supplier_certifications) +
            len(self.work_centers) +
            len(self.production_routings) +
            len(self.work_orders) +
            len(self.work_order_steps) +
            len(self.material_transactions) +
            len(self.demand_forecasts) +
            len(self.purchase_orders) +
            len(self.purchase_order_lines) +
            len(self.returns) +
            len(self.return_items)
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
        lines.append(f"-- Work Centers: {len(self.work_centers):,}")
        lines.append(f"-- Production Routings: {len(self.production_routings):,}")
        lines.append(f"-- Work Orders: {len(self.work_orders):,}")
        lines.append(f"-- Work Order Steps: {len(self.work_order_steps):,}")
        lines.append(f"-- Material Transactions: {len(self.material_transactions):,}")
        lines.append(f"-- Demand Forecasts: {len(self.demand_forecasts):,}")
        lines.append(f"-- Purchase Orders: {len(self.purchase_orders):,}")
        lines.append(f"-- Purchase Order Lines: {len(self.purchase_order_lines):,}")
        lines.append(f"-- Returns: {len(self.returns):,}")
        lines.append(f"-- Return Items: {len(self.return_items):,}")

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
