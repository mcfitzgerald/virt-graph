# Supply Chain Data Description

This document describes the synthetic supply chain data used for VG/SQL demonstrations and testing.

## Overview

The database contains **~1.73M rows** across **20 tables** representing a realistic enterprise supply chain with:
- Multi-tier supplier network
- Hierarchical bill of materials (BOM)
- Facility and transport network
- Customer orders with line items
- Multiple shipment types
- **Manufacturing execution** with work orders, routings, and material transactions

## Data Volumes

### Logistics & Distribution Domain (~488K rows)

| Table | Rows | Description |
|-------|------|-------------|
| `order_items` | 239,827 | Line items with composite key (order_id, line_number) |
| `orders` | 80,000 | Customer purchase orders |
| `shipments` | 45,780 | Order fulfillment, transfers, and replenishment |
| `bill_of_materials` | 42,652 | Parent-child part relationships with effectivity |
| `inventory` | 30,038 | Part quantities at facilities |
| `part_suppliers` | 22,568 | Alternate suppliers for parts |
| `parts` | 15,008 | Components with 5-level hierarchy |
| `customers` | 5,000 | Retail, wholesale, and enterprise |
| `supplier_relationships` | 1,690 | Tier-to-tier supplier network |
| `product_components` | 1,510 | Product to top-level part mapping |
| `supplier_certifications` | 1,365 | ISO and industry certifications |
| `suppliers` | 1,000 | Tiered supplier network |
| `products` | 500 | Finished goods |
| `transport_routes` | 414 | Routes between facilities |
| `facilities` | 100 | Warehouses, factories, DCs |
| `audit_log` | 0 | (Available for tracking changes) |

### Manufacturing Execution Domain (~1.24M rows)

| Table | Rows | Description |
|-------|------|-------------|
| `material_transactions` | 639,666 | WIP, consumption, and scrap tracking |
| `work_order_steps` | 480,352 | Execution progress through routing steps |
| `work_orders` | 120,000 | Production orders (make-to-order and make-to-stock) |
| `production_routings` | 2,002 | Process steps per product (3-5 steps each) |
| `work_centers` | 126 | Manufacturing capacity at factories |

## Domain Model

### Suppliers (1,000 records)

Three-tier supplier network representing supply chain depth:

| Tier | Count | Description |
|------|-------|-------------|
| Tier 1 | 100 | Direct suppliers (OEMs, assemblers) |
| Tier 2 | 300 | Component manufacturers |
| Tier 3 | 600 | Raw material suppliers |

**Named suppliers for testing:**
- `Acme Corp` (Tier 1, USA) - Primary test supplier
- `GlobalTech Industries` (Tier 1, China)
- `Precision Parts Ltd` (Tier 1, Germany)
- `Pacific Components` (Tier 2, Japan)
- `Northern Materials` (Tier 2, Canada)
- `Eastern Electronics` (Tier 3, Taiwan)
- `Delta Supplies` (Tier 3, India)

**Example supplier data:**
```
 id | supplier_code |         name          | tier | country | credit_rating
----+---------------+-----------------------+------+---------+---------------
  1 | SUP00001      | Acme Corp             |    1 | USA     | A
  2 | SUP00002      | GlobalTech Industries |    1 | China   | AAA
  3 | SUP00003      | Precision Parts Ltd   |    1 | Germany | AAA
  4 | SUP00004      | Pacific Components    |    2 | Japan   | B
  7 | SUP00007      | Eastern Electronics   |    3 | Taiwan  | AA
```

### Supplier Relationships (1,690 records)

Self-referential edges representing the supplier network. Tier 3 suppliers sell to Tier 2, who sell to Tier 1.

**Relationship statuses:**
- `active` (1,535, 90.8%) - Current business relationship
- `suspended` (82, 4.9%) - Temporarily paused
- `terminated` (73, 4.3%) - Ended relationship

**Example supply chain path:**
```
Eastern Electronics (T3) → Pacific Components (T2) → Acme Corp (T1)
```

### Parts (15,008 records)

Components organized in a 5-level bill of materials hierarchy.

**Categories:**
| Category | Count |
|----------|-------|
| Sensor | 1,571 |
| Cable | 1,545 |
| Housing | 1,543 |
| Subassembly | 1,527 |
| Fastener | 1,505 |
| Assembly | 1,489 |
| Motor | 1,484 |
| Mechanical | 1,477 |
| Electronic | 1,452 |
| Raw Material | 1,415 |

**Named parts for testing:**
- `CHIP-001` - Integrated Circuit Chip (Electronic, critical)
- `RESISTOR-100` - 100 Ohm Resistor
- `CAP-001` - 10uF Capacitor
- `MOTOR-001` - Stepper Motor Unit
- `SENSOR-001` - Temperature Sensor
- `TURBO-ENC-001` - Turbo Encabulator Main Assembly
- `FLUX-CAP-001` - Flux Capacitor Module
- `WIDGET-A` - Standard Widget Type A

**UoM Conversion Factors:**

Each part has conversion factor columns for normalized BOM rollups:
- `base_uom` - Base unit of measure (each, kg, m, L)
- `unit_weight_kg` - Weight per unit in kilograms
- `unit_length_m` - Length per unit in meters (for length-based materials)
- `unit_volume_l` - Volume per unit in liters (for volume-based materials)

Raw materials may use kg, m, or L as base UoM; assemblies always use "each".

### Bill of Materials (42,652 records)

Recursive parent-child relationships with effectivity date ranges.

**Effectivity distribution:**
- 80.1% current (effective_from in past, effective_to = NULL)
- 14.9% superseded (both dates in past)
- 4.9% future (effective_from in future)

**Example BOM for Turbo Encabulator:**
```
parent        | child        | quantity | effective_from
--------------+--------------+----------+---------------
TURBO-ENC-001 | CHIP-001     |        4 | 2024-12-25
TURBO-ENC-001 | RESISTOR-100 |       10 | 2024-12-25
TURBO-ENC-001 | CAP-001      |        6 | 2024-12-25
TURBO-ENC-001 | MOTOR-001    |        2 | 2024-12-25
```

### Facilities (100 records)

Distribution network of warehouses, factories, and distribution centers.

| Type | Count |
|------|-------|
| Distribution Center | 34 |
| Warehouse | 33 |
| Factory | 33 |

**Named facilities for testing:**
- `FAC-CHI` - Chicago Warehouse (USA)
- `FAC-LA` - LA Distribution Center (USA)
- `FAC-NYC` - New York Factory (USA)
- `FAC-SH` - Shanghai Hub (China)
- `FAC-MUN` - Munich Factory (Germany)
- `FAC-DEN` - Denver Hub (USA)
- `FAC-MIA` - Miami Hub (USA)
- `FAC-SEA` - Seattle Warehouse (USA)

### Transport Routes (414 records)

Weighted edges between facilities with transport mode, distance, time, and cost.

**Transport modes:**
| Mode | Count |
|------|-------|
| truck | 114 |
| air | 109 |
| sea | 98 |
| rail | 93 |

**Route statuses:**
- `active` (389, 94%)
- `seasonal` (10, 2.4%)
- `discontinued` (8, 1.9%)
- `suspended` (7, 1.7%)

### Customers (5,000 records)

**Customer types:** Retail, Wholesale, Enterprise

**Named customers for testing:**
- `Acme Industries` (CUST-ACME) - Enterprise, Chicago
- `Globex Corporation` (CUST-GLOBEX) - Enterprise, New York
- `Initech Inc` (CUST-INITECH) - Wholesale, Austin

### Products (500 records)

Finished goods that can be ordered by customers and manufactured via work orders.

**Named products for testing:**
| SKU | Name | Category | List Price |
|-----|------|----------|------------|
| TURBO-001 | Turbo Encabulator | Industrial | $1,322.05 |
| FLUX-001 | Flux Capacitor | Industrial | $3,161.22 |
| WIDGET-STD | Standard Widget | Industrial | $2,551.39 |

### Orders (80,000 records)

Customer orders spanning ~2 years of history.

**Order statuses:** pending, confirmed, shipped, delivered, cancelled

**Example orders:**
```
order_number  | customer          | status    | total_amount
--------------+-------------------+-----------+-------------
ORD-2024-001  | Acme Industries   | pending   |     5099.51
ORD-2024-002  | Globex Corporation| shipped   |     5187.54
ORD-2024-003  | Acme Industries   | delivered |     1917.67
```

### Order Items (239,827 records)

Line items using SAP-style composite key `(order_id, line_number)`.

Each order has 1-5 line items with:
- Product reference
- Quantity
- Unit price
- Discount percent

### Shipments (45,780 records)

Three shipment types for different logistics operations:

| Type | Count | Description |
|------|-------|-------------|
| order_fulfillment | ~32,000 | Customer order deliveries |
| transfer | ~9,200 | Facility-to-facility moves |
| replenishment | ~4,500 | Inbound supplier shipments |

**Shipment statuses:**
- `delivered` (27,246, 59.5%)
- `in_transit` (17,323, 37.8%)
- `pending` (1,211, 2.6%)

**Example transfer/replenishment shipments:**
```
shipment_number | shipment_type | status    | carrier
----------------+---------------+-----------+------------------
TRF-00032000    | transfer      | delivered | Internal Fleet
REP-00041199    | replenishment | delivered | LTL Consolidated
```

## Manufacturing Execution Domain

The manufacturing execution layer tracks the transformation of materials into finished goods, bridging the gap between demand (orders) and supply (production).

### Work Centers (126 records)

Manufacturing capacity within factory facilities. Only factories have work centers (3-5 per factory).

**Work center types:**
| Type | Count | Description |
|------|-------|-------------|
| machining | 28 | CNC stations, lathe cells, mill centers |
| assembly | 26 | Assembly lines, final assembly, sub-assembly stations |
| testing | 26 | QC stations, test benches, burn-in racks |
| fabrication | 24 | Welding bays, stamping presses, forming lines |
| packaging | 22 | Pack lines, shipping prep, kitting stations |

**Named work centers for testing:**
- `WC-ASM-01` - Primary Assembly Line (New York Factory)
- `WC-TEST-01` - Main Test Bench (New York Factory)
- `WC-PACK-01` - Packaging Line Alpha (New York Factory)
- `WC-MUN-ASM` - Munich Assembly (Munich Factory)
- `WC-MUN-FAB` - Munich Fabrication (Munich Factory)

**Key columns:**
- `capacity_per_day` - Units that can be processed
- `efficiency_rating` - 0.00-1.00 (e.g., 0.85 = 85%)
- `hourly_rate_usd` - Operating cost per hour

### Production Routings (2,002 records)

Process steps defining HOW to make each product (the recipe). Average 4 steps per product (range: 3-5).

**Operation categories:**
- Setup: Receive materials, stage components, material verification
- Pre-assembly: Inspection, component sorting, kit preparation
- Assembly: Mechanical assembly, soldering, wire harness, PCB mounting
- Calibration: Alignment, parameter tuning
- Testing: Functional test, burn-in test, quality inspection
- Finishing: Final QC, packaging, label and ship

Each product has 3-5 routing steps in sequence (10, 20, 30... SAP-style gaps).

**Example routing for Turbo Encabulator:**
```
step_sequence | operation_name           | wc_code
--------------+--------------------------+-----------
           10 | Receive materials        | WC-067-090
           20 | Pre-assembly inspection  | WC-067-090
           30 | Sub-assembly integration | WC-067-090
           40 | Alignment                | WC-067-089
           50 | Final QC inspection      | WC-067-091
```

### Work Orders (120,000 records)

The "make" signal that triggers production.

**Order types:**
| Type | Count | Percentage | Description |
|------|-------|------------|-------------|
| make_to_order | 96,000 | 80% | Linked to customer orders |
| make_to_stock | 24,000 | 20% | Inventory replenishment (no order link) |

**Work order statuses:**
| Status | Count | Percentage |
|--------|-------|------------|
| completed | 95,955 | 80.0% |
| in_progress | 12,043 | 10.0% |
| released | 6,025 | 5.0% |
| cancelled | 3,603 | 3.0% |
| quality_hold | 2,374 | 2.0% |

**Named work orders for testing:**
- `WO-2024-00001` - Turbo Encabulator at New York Factory (completed, make_to_order, qty: 100)
- `WO-2024-00002` - Flux Capacitor at Munich Factory (in_progress, make_to_order, qty: 50)
- `WO-2024-00003` - Standard Widget at New York Factory (completed, make_to_stock, qty: 200)

**Key columns:**
- `quantity_planned` - Target production quantity
- `quantity_completed` - Good units produced
- `quantity_scrapped` - Units failed/wasted
- `priority` - 1 (highest) to 5 (lowest)

### Work Order Steps (480,352 records)

Execution progress tracking through routing steps for each work order. Average 4 steps per work order (range: 3-5).

**Step statuses:**
| Status | Count | Percentage |
|--------|-------|------------|
| completed | 411,785 | 85.7% |
| pending | 45,718 | 9.5% |
| in_progress | 12,013 | 2.5% |
| skipped | 10,836 | 2.3% |

**Key columns:**
- `quantity_in` - Units entering this step
- `quantity_out` - Units successfully completing
- `quantity_scrapped` - Units scrapped at this step
- `labor_hours` - Actual labor time
- `machine_hours` - Actual machine time

### Material Transactions (639,666 records)

Tracks material flow during production (WIP, consumption, and scrap).

**Transaction types:**
| Type | Count | Percentage | Description |
|------|-------|------------|-------------|
| issue_to_wo | 517,768 | 80.9% | Material issued to work order (consumption) |
| receipt_from_wo | 95,955 | 15.0% | Finished product received from work order |
| scrap | 25,943 | 4.1% | Material scrapped during production |

**Scrap reason codes:**
| Reason | Count | Percentage |
|--------|-------|------------|
| quality_defect | 10,443 | 40.3% |
| machine_error | 6,464 | 24.9% |
| operator_error | 5,226 | 20.1% |
| material_defect | 3,810 | 14.7% |

**Example transaction flow for WO-2024-00001:**
```
transaction_number | transaction_type | item       | quantity | reason_code
-------------------+------------------+------------+----------+--------------
MTX-00000001       | issue_to_wo      | PRT-013156 |      100 |
MTX-00000002       | issue_to_wo      | PRT-013860 |      300 |
MTX-00000003       | issue_to_wo      | PRT-013054 |      300 |
MTX-00000004       | scrap            | PRT-013054 |       29 | machine_error
MTX-00000005       | issue_to_wo      | PRT-013735 |      300 |
```

## Graph-like Structures

The schema contains several self-referential and interconnected structures suitable for graph traversal:

### 1. Supplier Network
```
suppliers ←→ supplier_relationships (seller_id, buyer_id)
```
Use case: Find all upstream suppliers, trace supply chain disruptions

### 2. Bill of Materials
```
parts ←→ bill_of_materials (parent_part_id, child_part_id)
```
Use case: BOM explosion, component impact analysis, cost rollup

### 3. Transport Network
```
facilities ←→ transport_routes (origin_facility_id, destination_facility_id)
```
Use case: Route optimization, shortest path, network resilience

### 4. Order Flow
```
customers → orders → order_items → products → product_components → parts
```
Use case: Demand tracing, product-to-part mapping

### 5. Manufacturing Execution Flow
```
orders → work_orders → work_order_steps → work_centers → facilities
                    ↓
         material_transactions → parts (consumed)
                              → products (produced)
```
Use case: Production tracking, capacity analysis, WIP visibility

### 6. Product to Routing
```
products → production_routings → work_centers
```
Use case: Lead time calculation, capacity planning, bottleneck analysis

### 7. Scrap Analysis Path
```
suppliers → parts → material_transactions (scrap) → work_orders → work_centers
```
Use case: "Which supplier's parts cause the most scrap at which work center?"

## Unit of Measure (UoM) Handling

### Unified Units by Domain

| Domain | Column | Unit |
|--------|--------|------|
| Transport | `distance_km` | kilometers |
| Transport | `transit_time_hours` | hours |
| Transport | `cost_usd` | USD |
| Transport | `capacity_tons` | metric tons |
| Parts | `weight_kg` | kilograms |
| Shipments | `weight_kg` | kilograms |
| Parts | `lead_time_days` | days |
| All costs | `*_cost`, `*_price`, `*_amount` | USD (implicit) |

### BOM Unit Normalization

The `bill_of_materials.unit` column allows mixed units (each, kg, m, L) for flexibility. To support weight/cost rollups, use the `bom_with_conversions` view which joins parts conversion factors:

```sql
SELECT parent_part_id, child_part_id, quantity, unit,
       weight_kg,  -- Normalized weight contribution
       cost_usd    -- Normalized cost contribution
FROM bom_with_conversions
WHERE parent_part_id = 15006;  -- TURBO-ENC-001
```

**Example output:**
```
parent_part_id | child_part_id | quantity | unit | weight_kg | cost_usd
---------------+---------------+----------+------+-----------+----------
         15006 |         15001 |        4 | each |   0.22398 |    56.96
         15006 |         15002 |       10 | each |   2.75705 |   420.60
         15006 |         15003 |        6 | each |   0.84107 |   137.64
```

The view calculates:
- `weight_kg = quantity * part.unit_weight_kg`
- `cost_usd = quantity * part.unit_cost`

## Connection Details

```python
import psycopg2
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='supply_chain',
    user='virt_graph',
    password='dev_password'
)
```

## Regenerating Data

To regenerate with fresh synthetic data:

```bash
poetry run python supply_chain_example/scripts/generate_data.py
make db-reset
```

Data generation uses `Faker` with seed `42` for reproducibility.
