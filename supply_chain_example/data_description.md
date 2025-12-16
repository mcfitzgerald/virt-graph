# Supply Chain Data Description

This document describes the synthetic supply chain data used for VG/SQL demonstrations and testing.

## Overview

The database contains **~488,000 rows** across **16 tables** representing a realistic enterprise supply chain with:
- Multi-tier supplier network
- Hierarchical bill of materials (BOM)
- Facility and transport network
- Customer orders with line items
- Multiple shipment types

## Data Volumes

| Table | Rows | Description |
|-------|------|-------------|
| `order_items` | 239,985 | Line items with composite key (order_id, line_number) |
| `orders` | 80,000 | Customer purchase orders |
| `shipments` | 45,737 | Order fulfillment, transfers, and replenishment |
| `bill_of_materials` | 42,706 | Parent-child part relationships with effectivity |
| `inventory` | 30,054 | Part quantities at facilities |
| `part_suppliers` | 22,457 | Alternate suppliers for parts |
| `parts` | 15,008 | Components with 5-level hierarchy |
| `customers` | 5,000 | Retail, wholesale, and enterprise |
| `supplier_relationships` | 1,690 | Tier-to-tier supplier network |
| `product_components` | 1,528 | Product to top-level part mapping |
| `supplier_certifications` | 1,374 | ISO and industry certifications |
| `suppliers` | 1,000 | Tiered supplier network |
| `products` | 500 | Finished goods |
| `transport_routes` | 411 | Routes between facilities |
| `facilities` | 100 | Warehouses, factories, DCs |
| `audit_log` | 0 | (Available for tracking changes) |

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
 id | supplier_code |       name        | tier | country | credit_rating
----+---------------+-------------------+------+---------+---------------
  1 | SUP00001      | Acme Corp         |    1 | USA     | A
  2 | SUP00002      | GlobalTech        |    1 | China   | AAA
  4 | SUP00004      | Pacific Components|    2 | Japan   | B
  7 | SUP00007      | Eastern Electronics|   3 | Taiwan  | AA
```

### Supplier Relationships (1,690 records)

Self-referential edges representing the supplier network. Tier 3 suppliers sell to Tier 2, who sell to Tier 1.

**Relationship statuses:**
- `active` (~90%) - Current business relationship
- `suspended` (~5%) - Temporarily paused
- `terminated` (~5%) - Ended relationship

**Example supply chain path:**
```
Eastern Electronics (T3) → Pacific Components (T2) → Acme Corp (T1)
```

### Parts (15,008 records)

Components organized in a 5-level bill of materials hierarchy.

**Categories:**
| Category | Count |
|----------|-------|
| Motor | 1,546 |
| Mechanical | 1,538 |
| Cable | 1,538 |
| Subassembly | 1,524 |
| Fastener | 1,519 |
| Electronic | 1,511 |
| Housing | 1,496 |
| Raw Material | 1,470 |
| Sensor | 1,464 |
| Assembly | 1,402 |

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

### Bill of Materials (42,706 records)

Recursive parent-child relationships with effectivity date ranges.

**Effectivity distribution:**
- 80% current (effective_from in past, effective_to = NULL)
- 15% superseded (both dates in past)
- 5% future (effective_from in future)

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
| Warehouse | 39 |
| Factory | 33 |
| Distribution Center | 28 |

**Named facilities for testing:**
- `FAC-CHI` - Chicago Warehouse (USA)
- `FAC-LA` - LA Distribution Center (USA)
- `FAC-NYC` - New York Factory (USA)
- `FAC-SH` - Shanghai Hub (China)
- `FAC-MUN` - Munich Factory (Germany)
- `FAC-DEN` - Denver Hub (USA)
- `FAC-MIA` - Miami Hub (USA)
- `FAC-SEA` - Seattle Warehouse (USA)

### Transport Routes (411 records)

Weighted edges between facilities with transport mode, distance, time, and cost.

**Transport modes:** truck, rail, air, sea

**Route statuses:**
- `active` (~95%)
- `seasonal` (~2%)
- `suspended` (~2%)
- `discontinued` (~1%)

### Customers (5,000 records)

**Customer types:**
- Retail
- Wholesale
- Enterprise

**Named customers for testing:**
- `Acme Industries` (CUST-ACME) - Enterprise, Chicago
- `Globex Corporation` (CUST-GLOBEX) - Enterprise, New York
- `Initech Inc` (CUST-INITECH) - Wholesale, Austin

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

### Order Items (239,985 records)

Line items using SAP-style composite key `(order_id, line_number)`.

Each order has 1-5 line items with:
- Product reference
- Quantity
- Unit price
- Discount percent

### Shipments (45,737 records)

Three shipment types for different logistics operations:

| Type | Count | Description |
|------|-------|-------------|
| order_fulfillment | 31,984 | Customer order deliveries |
| transfer | 9,214 | Facility-to-facility moves |
| replenishment | 4,539 | Inbound supplier shipments |

**Shipment statuses:** pending, in_transit, delivered, failed

**Example transfer/replenishment shipments:**
```
shipment_number | shipment_type | status    | carrier
----------------+---------------+-----------+------------------
TRF-00032000    | transfer      | delivered | Internal Fleet
REP-00041199    | replenishment | delivered | LTL Consolidated
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
