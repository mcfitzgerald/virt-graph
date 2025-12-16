# Manufacturing Execution Layer Extension Plan

## Overview
Extend the supply chain data model from a "logistics/distribution" model to a "manufacturing execution" model by adding work orders, work centers, production routings, and material transactions.

## Design Decisions (Confirmed)
- **Work Orders**: Support both make-to-order (linked to sales orders) AND make-to-stock (inventory replenishment)
- **Material Transactions**: New dedicated table (not extending shipments)
- **Data Scale**: Realistic ratios - larger dataset acceptable (~1.1M new rows)

---

## New Tables (5 total)

### 1. `work_centers` - Manufacturing Capacity
Location: Child of `facilities` (only factories have work centers)

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | |
| `wc_code` | VARCHAR(20) UNIQUE | e.g., WC-ASM-01 |
| `name` | VARCHAR(200) | e.g., "Assembly Line 1" |
| `facility_id` | FK → facilities | Parent factory |
| `work_center_type` | VARCHAR(50) | assembly, machining, fabrication, testing, packaging |
| `capacity_per_day` | INTEGER | Units that can be processed |
| `efficiency_rating` | DECIMAL(3,2) | 0.00-1.00 (e.g., 0.85 = 85%) |
| `hourly_rate_usd` | DECIMAL(10,2) | Operating cost per hour |
| `setup_time_mins` | INTEGER | Default setup time |
| `is_active` | BOOLEAN | |
| `created_at` | TIMESTAMP | |

**Data Volume**: ~150 work centers (33 factories × 3-5 each)

### 2. `production_routings` - Process Steps
Defines HOW to make a product (the recipe)

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | |
| `product_id` | FK → products | What product this routing makes |
| `step_sequence` | INTEGER | 10, 20, 30... (SAP-style gaps for insertions) |
| `operation_name` | VARCHAR(100) | e.g., "Solder components", "Quality test" |
| `work_center_id` | FK → work_centers | Where this step is performed |
| `setup_time_mins` | INTEGER | Machine setup time for this step |
| `run_time_per_unit_mins` | DECIMAL(8,2) | Time to process one unit |
| `is_active` | BOOLEAN | |
| `effective_from` | DATE | Routing version control |
| `effective_to` | DATE | NULL = current |
| `created_at` | TIMESTAMP | |

**Data Volume**: ~2,500 routing steps (500 products × 3-5 steps average)

### 3. `work_orders` - The Make Signal
Links demand (orders/stock needs) to production execution

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | |
| `wo_number` | VARCHAR(30) UNIQUE | e.g., WO-2024-00001 |
| `product_id` | FK → products | What we're making |
| `facility_id` | FK → facilities | Where we're making it |
| `order_id` | FK → orders (NULLABLE) | NULL for make-to-stock |
| `order_type` | VARCHAR(20) | 'make_to_order', 'make_to_stock' |
| `priority` | INTEGER | 1=highest, 5=lowest |
| `quantity_planned` | INTEGER | Target quantity |
| `quantity_completed` | INTEGER | Good units produced |
| `quantity_scrapped` | INTEGER | Units failed/wasted |
| `status` | VARCHAR(20) | released, in_progress, quality_hold, completed, cancelled |
| `planned_start_date` | DATE | |
| `planned_end_date` | DATE | |
| `actual_start_date` | TIMESTAMP | |
| `actual_end_date` | TIMESTAMP | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**Data Volume**: ~120,000 work orders
- 80,000 orders × 1.2 = ~96,000 make-to-order WOs (some orders need multiple WOs)
- ~24,000 make-to-stock WOs

### 4. `work_order_steps` - WO Execution Progress
Tracks progress through routing steps for each work order

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | |
| `work_order_id` | FK → work_orders | |
| `routing_step_id` | FK → production_routings | |
| `step_sequence` | INTEGER | Copied from routing |
| `work_center_id` | FK → work_centers | Actual WC used (may differ from routing) |
| `status` | VARCHAR(20) | pending, in_progress, completed, skipped |
| `quantity_in` | INTEGER | Units entering this step |
| `quantity_out` | INTEGER | Units successfully completing |
| `quantity_scrapped` | INTEGER | Units scrapped at this step |
| `planned_start` | TIMESTAMP | |
| `actual_start` | TIMESTAMP | |
| `actual_end` | TIMESTAMP | |
| `labor_hours` | DECIMAL(8,2) | Actual labor time |
| `machine_hours` | DECIMAL(8,2) | Actual machine time |

**Data Volume**: ~400,000 WO steps (120K WOs × 3-4 steps average)

### 5. `material_transactions` - WIP & Consumption
Tracks material flow during production

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | |
| `transaction_number` | VARCHAR(30) UNIQUE | e.g., MTX-2024-00001 |
| `transaction_type` | VARCHAR(20) | issue_to_wo, receipt_from_wo, scrap, return_to_stock |
| `work_order_id` | FK → work_orders | |
| `part_id` | FK → parts | For issue/scrap: component consumed |
| `product_id` | FK → products | For receipt: product completed |
| `facility_id` | FK → facilities | |
| `quantity` | INTEGER | Always positive |
| `unit_cost` | DECIMAL(12,2) | Cost at time of transaction |
| `reason_code` | VARCHAR(50) | For scrap: quality_defect, machine_error, operator_error, material_defect |
| `reference_number` | VARCHAR(50) | External reference |
| `created_at` | TIMESTAMP | Transaction timestamp |
| `created_by` | VARCHAR(100) | |

**Data Volume**: ~600,000 transactions
- 120K WOs × 4 material issues (BOM components) = ~480K issue transactions
- 120K receipt transactions (one per WO completion)
- ~5% scrap rate on issues = ~24K scrap transactions

---

## New Graph Relationships

| Relationship | From → To | Traversal Use Case |
|--------------|-----------|-------------------|
| **PerformedAt** | WorkOrder → Facility | "WOs running at factory X" |
| **FulfilledBy** | Order → WorkOrder | "Production for order #123" |
| **Produces** | WorkOrder → Product | "What does WO-001 make?" |
| **HasStep** | WorkOrder → WorkOrderStep | "Progress of WO-001" |
| **UsesWorkCenter** | WorkOrderStep → WorkCenter | "What's running on Line A?" |
| **LocatedAt** | WorkCenter → Facility | "Work centers at Munich factory" |
| **RoutesThrough** | Product → ProductionRouting | "Steps to make Product X" |
| **ConsumesPart** | MaterialTransaction → Part | "Parts consumed by WO-001" |
| **ProducesProduct** | MaterialTransaction → Product | "Products from WO-001" |

---

## Data Generation Patterns

### Work Centers (Faker patterns)
```python
WORK_CENTER_TYPES = {
    'assembly': ['Assembly Line', 'Final Assembly', 'Sub-Assembly'],
    'machining': ['CNC Station', 'Lathe Cell', 'Mill Center'],
    'fabrication': ['Welding Bay', 'Stamping Press', 'Forming Line'],
    'testing': ['QC Station', 'Test Bench', 'Burn-In Rack'],
    'packaging': ['Pack Line', 'Shipping Prep', 'Kitting Station']
}
```

### Operation Names (for routings)
```python
OPERATIONS = [
    'Receive materials', 'Stage components', 'Pre-assembly inspection',
    'Solder components', 'Mount PCB', 'Wire harness assembly',
    'Mechanical assembly', 'Calibration', 'Functional test',
    'Burn-in test', 'Final QC inspection', 'Packaging', 'Label and ship'
]
```

### Work Order Status Distribution
- released: 5%
- in_progress: 10%
- quality_hold: 2%
- completed: 80%
- cancelled: 3%

### Scrap Reason Distribution
- quality_defect: 40%
- machine_error: 25%
- operator_error: 20%
- material_defect: 15%

---

## Updated Data Volumes Summary

| Table | Current | New | Change |
|-------|---------|-----|--------|
| work_centers | 0 | 150 | +150 |
| production_routings | 0 | 2,500 | +2,500 |
| work_orders | 0 | 120,000 | +120,000 |
| work_order_steps | 0 | 400,000 | +400,000 |
| material_transactions | 0 | 600,000 | +600,000 |
| **Total** | ~488,000 | ~1,610,000 | **+1,122,000** |

---

## Files to Modify

| File | Changes |
|------|---------|
| `supply_chain_example/postgres/schema.sql` | Add 5 new tables with indexes |
| `supply_chain_example/scripts/generate_data.py` | Add generation methods for new tables |
| `supply_chain_example/data_description.md` | Document new domain model |

---

## Implementation Steps

### Step 1: Schema Changes
Add to `schema.sql`:
1. `work_centers` table (after facilities)
2. `production_routings` table (after products)
3. `work_orders` table (after orders)
4. `work_order_steps` table (after work_orders)
5. `material_transactions` table (after inventory)
6. Appropriate indexes for all new tables

### Step 2: Generator Updates
Add to `SupplyChainGenerator` class:
1. `self.work_centers`, `self.production_routings`, etc. lists
2. `generate_work_centers()` - Creates WCs for factory-type facilities
3. `generate_production_routings()` - Creates 3-5 step routings per product
4. `generate_work_orders()` - Creates WOs linked to orders + make-to-stock
5. `generate_work_order_steps()` - Progress records for each WO
6. `generate_material_transactions()` - Consumption, production, scrap records
7. Update `generate_all()` to call new methods in dependency order

### Step 3: Named Entities for Testing
Add named work centers and work orders for query testing:
- `WC-ASM-01` - Primary assembly line at Chicago
- `WC-TEST-01` - Main test bench at Chicago
- `WO-2024-00001` - Reference work order

### Step 4: Documentation Update
Update `data_description.md` with:
- Manufacturing Execution domain section
- New table descriptions and volumes
- Graph-like structures for manufacturing (WO → WC → Facility)

### Step 5: Regenerate and Validate
```bash
poetry run python supply_chain_example/scripts/generate_data.py
make db-reset
# Verify with queries
```

---

## Questions Resolved
- Work orders support both make-to-order and make-to-stock ✓
- Material transactions in dedicated table (not extending shipments) ✓
- Realistic data volumes (1.1M+ new rows) ✓

## Open Questions
None - ready to implement

---

## Sources
- [Manufacturing Execution System - Wikipedia](https://en.wikipedia.org/wiki/Manufacturing_execution_system)
- [ISA-95/B2MML Schema Standard](https://www.iacsengineering.com/erp-mes-integration-using-b2mml-xml-schemas/)
- [MES Core Features - Tulip](https://tulip.co/blog/core-features-of-mes-manufacturing-execution-systems/)
