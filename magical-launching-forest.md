# FMCG Supply Chain Example: Prism Consumer Goods

## Overview

Transform the VG/SQL example from generic supply chain to a **Colgate-Palmolive-inspired FMCG model** called "Prism Consumer Goods" (PCG). This shifts from "High-Complexity, Low-Volume" (Aerospace) to "High-Velocity, Massive-Volume" (FMCG) patterns.

**Core Concept**: The "Formula-to-Shelf" pipeline - chemical batch manufacturing flowing through a convergent-divergent network to millions of fragmented retail nodes.

---

## Company Narrative: Prism Consumer Goods

- **Company**: Prism Consumer Goods (PCG), ~$15B global CPG
- **HQ**: Knoxville, TN
- **Product Lines**:
  - **PrismWhite** (Oral Care) - Toothpaste
  - **ClearWave** (Home Care) - Dish Soap
  - **AquaPure** (Personal Care) - Body Wash

### Global Structure (5 Divisions)

| Division | HQ | Plants | Markets |
|----------|-----|--------|---------|
| NAM | Knoxville | 2 (Tennessee, Texas) | US, Canada |
| LATAM | São Paulo | 1 (Brazil) | Brazil, Mexico, Andean |
| APAC | Singapore | 2 (China, India) | China, India, SEA, ANZ |
| EUR | Paris | 1 (Poland) | Western EU, UK, Nordics |
| AFR-EUR | Dubai | 1 (Turkey) | MENA, Sub-Saharan, CIS |

### Channel Mix

| Channel | Volume | Archetypes |
|---------|--------|------------|
| B&M Large (40%) | 40% | MegaMart, ValueClub, UrbanEssential |
| B&M Distributor (30%) | 30% | RegionalGrocers, IndieRetail |
| E-commerce (20%) | 20% | DigitalFirst, OmniRetailer |
| DTC (10%) | 10% | PrismDirect |

---

## Implementation Plan

### Phase 1: Directory Structure [FINALIZED]

Create `fmcg_example/` alongside existing `supply_chain_example/`:

```
fmcg_example/
├── ontology/
│   └── prism_fmcg.yaml          # LinkML ontology with VG extensions
├── postgres/
│   ├── docker-compose.yml       # PostgreSQL container
│   ├── schema.sql               # ~33 tables DDL
│   └── seed.sql                 # Generated data (~2M rows)
├── neo4j/
│   ├── docker-compose.yml       # Neo4j for benchmarking
│   └── migrate.py               # Reuse ontology-driven migration
├── scripts/
│   ├── generate_data.py         # Data generator
│   └── validate_realism.sql     # Validation queries
├── tests/
│   ├── test_recall_trace.py     # Beast mode: lot genealogy
│   ├── test_landed_cost.py      # Beast mode: cost rollup
│   ├── test_spof_risk.py        # Beast mode: supplier criticality
│   ├── test_osa_analysis.py     # Beast mode: OSA/DC bottlenecks
│   └── test_ontology.py         # Two-layer validation
├── docs/
│   └── prism-fmcg.md            # Domain documentation
└── FMCG_README.md               # Example overview
```

### Phase 2: Schema (67 Tables) [FINALIZED]

**Domain A - SOURCE (Procurement & Inbound)** ✅ SCOR: Source
- `ingredients` - Raw chemicals with CAS numbers, purity, storage
- `suppliers` - Global supplier network (Tier 1/2/3)
- `supplier_ingredients` - M:M with lead times, MOQs, costs
- `certifications` - ISO, GMP, Halal, Kosher, RSPO
- `purchase_orders` - **POs to suppliers** (the procurement cycle!)
- `purchase_order_lines` - PO line items with ingredient, qty, price
- `goods_receipts` - **Receipt of goods from suppliers** (closes SOURCE loop)
- `goods_receipt_lines` - Actual received qty, lot numbers, quality status

**Domain B - TRANSFORM (Manufacturing)** ✅ SCOR: Transform
- `formulas` - Recipe/BOM definitions with yield parameters
- `formula_ingredients` - Composition with sequence, quantities
- `production_lines` - **Manufacturing line capacity** (resource side of Plan)
- `work_orders` - **Scheduled production** (links Plan to Transform)
- `work_order_materials` - Planned material consumption per work order
- `batches` - Production lots with QC status, expiry
- `batch_ingredients` - Actual consumption for mass balance
- `batch_cost_ledger` - Material, labor, energy, overhead costs
- `plants` - 7 manufacturing facilities

**Domain C - PRODUCT (SKU Master)** *(Shared across ORDER/FULFILL)*
- `products` - Product families (PrismWhite, ClearWave, AquaPure)
- `packaging_types` - Tubes, bottles, sizes, regional variants
- `skus` - The explosion point (~2,000 SKUs)
- `sku_costs` - Standard costs by type
- `sku_substitutes` - Substitute/equivalent SKUs

**Domain D - ORDER (Demand Signal)** ✅ SCOR: Order
- `channels` - 4 channel types (B&M Large, B&M Dist, Ecom, DTC)
- `promotions` - Trade promos with lift multipliers
- `orders` - Customer orders (~200K)
- `order_lines` - Line items with SKU, qty, price
- `order_allocations` - **ATP/allocation of inventory to orders**

**Domain E - FULFILL (Outbound)** ✅ SCOR: Fulfill
- `divisions` - 5 global divisions
- `distribution_centers` - ~25 DCs globally
- `ports` - Ocean/air freight nodes for multi-leg routing
- `retail_accounts` - Archetype-based accounts (~100)
- `retail_locations` - Individual stores (~10,000)
- `shipments` - Physical movements (~180K)
- `shipment_lines` - Items with batch numbers for lot tracking (~540K)
- `inventory` - Stock by location with aging buckets
- `pick_waves` - **Picking/packing execution** (optional detail)

**Domain E2 - LOGISTICS (Transport Network)**
- `carriers` - Carrier profiles with sustainability ratings
- `carrier_contracts` - Rate agreements with date effectivity
- `carrier_rates` - Rate tables by mode, weight break, lane
- `route_segments` - Atomic legs: origin → destination (enables multi-leg)
- `routes` - Composed routes (multiple segments for Plant → Port → Ocean → DC)
- `route_segment_assignments` - Links routes to segments in sequence
- `shipment_legs` - Actual execution: which segments used per shipment

**Domain E3 - ESG/SUSTAINABILITY (2030 KPIs)** *(Part of ORCHESTRATE)*
- `emission_factors` - CO2/km by mode, fuel type, carrier
- `shipment_emissions` - Calculated CO2 per shipment (Scope 3 Category 4 & 9)
- `supplier_esg_scores` - EcoVadis, CDP, ISO14001 status, SBTi commitment
- `sustainability_targets` - Division/account-level carbon reduction targets
- `modal_shift_opportunities` - Identified truck→rail/intermodal opportunities

**Domain F - PLAN (Demand & Supply Planning)** ✅ SCOR: Plan - *"Balancing Requirements vs Resources"*
- `pos_sales` - Point-of-sale signals (actual demand at store/SKU level)
- `demand_forecasts` - Statistical/ML forecasts by SKU/location
- `forecast_accuracy` - MAPE, bias tracking by SKU/account
- `consensus_adjustments` - S&OP overrides to statistical forecast
- `replenishment_params` - Safety stock, reorder points, review cycles by node
- `demand_allocation` - How forecasted demand is allocated down the network
- `capacity_plans` - **Available capacity by plant/line/period** (resource side!)
- `supply_plans` - **Planned production/procurement to meet demand** (closes Plan loop)
- `plan_exceptions` - **Gap identification** when demand > capacity

**Domain G - RETURN (Regenerate)** ✅ SCOR: Return
- `returns` - Return events
- `return_lines` - Return items with condition assessment
- `disposition_logs` - Restock, scrap, regenerate, donate decisions
- `rma_authorizations` - Return Merchandise Authorization workflow

**Domain H - ORCHESTRATE (Hub)** ✅ SCOR: Orchestrate - *"The Brain"*
- `kpi_thresholds` - Desmet Triangle targets (Service, Cost, Cash)
- `kpi_actuals` - **Calculated KPI values vs thresholds**
- `osa_metrics` - On-shelf availability (~500K measurements)
- `business_rules` - **Policy management** (min order qty, allocation priority, etc.)
- `risk_events` - **Risk registry** (supplier disruption, quality hold, etc.)
- `audit_log` - Change tracking for governance

**Target: ~14.7M rows total** (Full SCOR coverage across 67 tables)

---

#### SCOR-DS Infinity Loop Mapping

```
                              ┌─────────────────┐
                              │      PLAN       │
                              │  demand_forecasts│
                              │  capacity_plans  │
                              │  supply_plans    │
                              │  plan_exceptions │
                              └────────┬────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             │                             ▼
┌─────────────────┐                    │                    ┌─────────────────┐
│     ORDER       │                    │                    │     SOURCE      │
│  orders         │◄───── DEMAND ──────┼────── SUPPLY ─────►│  purchase_orders│
│  order_lines    │                    │                    │  goods_receipts │
│  promotions     │                    │                    │  suppliers      │
└────────┬────────┘                    │                    └────────┬────────┘
         │                             │                             │
         │                    ┌────────┴────────┐                    │
         │                    │   ORCHESTRATE   │                    │
         │                    │  kpi_thresholds │                    │
         │                    │  business_rules │                    │
         │                    │  risk_events    │                    │
         │                    │  osa_metrics    │                    │
         │                    └────────┬────────┘                    │
         │                             │                             │
         ▼                             │                             ▼
┌─────────────────┐                    │                    ┌─────────────────┐
│     FULFILL     │                    │                    │    TRANSFORM    │
│  shipments      │◄───── OUTPUT ──────┼────── INPUT ──────►│  work_orders    │
│  inventory      │                    │                    │  batches        │
│  carriers       │                    │                    │  formulas       │
└────────┬────────┘                    │                    └────────┬────────┘
         │                             │                             │
         └─────────────────────────────┼─────────────────────────────┘
                                       │
                              ┌────────┴────────┐
                              │     RETURN      │
                              │  returns        │
                              │  disposition_logs│
                              │  (Regenerate)   │
                              └─────────────────┘
```

**Loop Closures:**
- **Plan ↔ All**: demand_forecasts → work_orders → batches → shipments → pos_sales → (back to forecast)
- **Source ↔ Transform**: purchase_orders → goods_receipts → batch_ingredients → batches
- **Transform ↔ Fulfill**: batches → shipment_lines → inventory
- **Fulfill ↔ Order**: inventory → order_allocations → shipments → orders
- **Return ↔ Transform**: returns → disposition_logs → (back to batches for regeneration)
- **Orchestrate ↔ All**: kpi_thresholds evaluate all processes, risk_events can impact any

### Phase 3: Ontology (LinkML + VG Extensions) [FINALIZED]

**Core Entity Classes (TBox)** - 67 classes:
- **Source**: Ingredient, Supplier, SupplierCertification, PurchaseOrder, GoodsReceipt
- **Transform**: Formula, ProductionLine, WorkOrder, Batch, Plant
- **Product**: Product, PackagingType, SKU, SubstituteGroup
- **Order**: Channel, Promotion, Order, OrderAllocation
- **Fulfill**: Division, DistributionCenter, RetailAccount, RetailLocation, Port, Shipment, Inventory
- **Logistics**: Carrier, CarrierContract, RouteSegment, Route
- **Plan**: DemandForecast, CapacityPlan, SupplyPlan, PlanException
- **Return**: Return, DispositionLog, RMAAuthorization
- **Orchestrate**: KPIThreshold, KPIActual, OSAMetric, BusinessRule, RiskEvent

**Core Relationships (RBox)** - ~40 relationships with operation type mappings

---

#### 3.1 Dual Modeling Patterns ("Rich Link")

**Rule**: If a concept acts as a **noun** ("Update the Contract") AND a **verb** ("Buy via that Contract"), model it **twice**.

| Concept | As Node (Detail) | As Edge (Speed) | Use Cases |
|---------|------------------|-----------------|-----------|
| **CarrierContract** | `Carrier --(party_to)--> CarrierContract --(covers)--> RouteSegment` | `Carrier --(serves_lane {rate, effective_date})--> RouteSegment` | Node: Contract lifecycle, expiry alerts. Edge: Rate lookups during routing |
| **Promotion** | `Account --(runs)--> Promotion --(applies_to)--> SKU` | `Account --(promo_lift {lift_pct})--> SKU` | Node: Trade spend tracking. Edge: Demand forecasting |
| **SupplierAgreement** | `Supplier --(party_to)--> SupplierAgreement --(sources)--> Ingredient` | `Supplier --(supplies {price, lead_time})--> Ingredient` | Node: Contract management. Edge: Cost rollups |

```yaml
# Example: Carrier Contract as Node AND Edge
CarrierContract:
  is_a: vg:SQLMappedClass
  annotations:
    vg:table: carrier_contracts
    vg:primary_key: id

# The Shortcut Edge (for fast rate lookups)
serves_lane:
  is_a: vg:SQLMappedRelationship
  domain_class: Carrier
  range_class: RouteSegment
  edge_table: carrier_contracts  # Same table, different perspective
  edge_attributes:
    - {name: "freight_rate", type: "decimal"}
    - {name: "effective_from", type: "date"}
  operation_types: [direct_join, temporal_traversal]
```

---

#### 3.2 Deep Hierarchy (Flattened Edges)

**Problem**: Retail hierarchy is 4 levels: `Location → Account → Division → Region`. Aggregating "all stores in APAC" requires 3 hops.

**Solution**: Add flattened shortcut edges for fast aggregation.

| Step-by-Step (Detail) | Flattened (Speed) |
|-----------------------|-------------------|
| `Location --(belongs_to)--> Account --(in_division)--> Division` | `Location --(in_division)--> Division` |
| `DC --(serves)--> Location --(in_division)--> Division` | `DC --(serves_division)--> Division` |

```yaml
# Step-by-step (for drill-down)
location_account:
  edge_table: retail_locations
  domain_key: id
  range_key: retail_account_id

# Flattened shortcut (for aggregation)
location_division:
  is_a: vg:SQLMappedRelationship
  domain_class: RetailLocation
  range_class: Division
  edge_table: v_location_divisions  # SQL View that flattens hierarchy
  operation_types: [direct_join, hierarchical_aggregation]
```

**Required SQL View**:
```sql
CREATE VIEW v_location_divisions AS
SELECT rl.id as location_id, ra.division_id
FROM retail_locations rl
JOIN retail_accounts ra ON rl.retail_account_id = ra.id;
```

---

#### 3.3 Equivalency Pattern (Substitutes)

**FMCG Substitutes**:
- **SKU Substitutes**: 6oz tube ↔ 8oz tube (same product, different size)
- **Ingredient Alternatives**: Sorbitol ↔ Xylitol (functional equivalents)
- **Carrier Equivalency**: FedEx ↔ UPS on same lane

| Direct Edge | Cluster Node |
|-------------|--------------|
| `SKU-6oz --(substitutes)--> SKU-8oz` | `SKU-6oz --(member_of)--> SubstituteGroup-001` |

```yaml
# Direct substitution (for simple checks)
substitutes:
  is_a: vg:SQLMappedRelationship
  domain_class: SKU
  range_class: SKU
  edge_table: sku_substitutes
  symmetric: true  # If A substitutes B, then B substitutes A

# Cluster node (for "find ANY valid substitute")
SubstituteGroup:
  is_a: vg:SQLMappedClass
  annotations:
    vg:table: substitute_groups

member_of_substitute_group:
  domain_class: SKU
  range_class: SubstituteGroup
  edge_table: sku_substitute_memberships
```

---

#### 3.4 Composite Keys

**Tables with composite PKs** (handled natively by VG handlers):

| Table | Composite Key | Ontology Config |
|-------|---------------|-----------------|
| `order_lines` | `[order_id, line_number]` | `primary_key: '["order_id", "line_number"]'` |
| `shipment_lines` | `[shipment_id, line_number]` | `primary_key: '["shipment_id", "line_number"]'` |
| `formula_ingredients` | `[formula_id, ingredient_id, sequence]` | `primary_key: '["formula_id", "ingredient_id", "sequence"]'` |

---

#### 3.5 UoM Normalization (SQL View Layer)

**Problem**: Ingredients in kg, batches in liters, SKUs in cases/eaches. Graph handlers shouldn't parse units.

**Solution**: Normalize to base units in SQL Views BEFORE the graph sees it.

| Raw Data | Base Unit | Normalization View |
|----------|-----------|-------------------|
| `distance_miles`, `distance_km` | `distance_km` | `v_transport_normalized` |
| `weight_kg`, `weight_lb` | `weight_kg` | `v_weights_normalized` |
| `qty_cases`, `qty_eaches` | `qty_eaches` | `v_inventory_normalized` |

```sql
-- Normalize transport distances to km
CREATE VIEW v_transport_normalized AS
SELECT
    id, origin_id, destination_id,
    CASE
        WHEN distance_unit = 'miles' THEN distance * 1.60934
        ELSE distance
    END as distance_km,
    CASE
        WHEN cost_currency = 'EUR' THEN cost * fx_rate_to_usd
        ELSE cost
    END as cost_usd
FROM route_segments;
```

```yaml
# Map ontology to normalized view, not raw table
route_segment_edge:
  edge_table: v_transport_normalized  # Clean view
  weight_columns:
    - {name: "distance_km", unit: "km", type: "decimal"}
    - {name: "cost_usd", unit: "USD", type: "decimal"}
```

---

#### 3.6 Hyper-edges (Event Reification)

**Problem**: Shipment involves 5 entities (Batch, SKU, DC, Carrier, Store). Can't be a single edge.

**Solution**: Model Shipment as **Node (detail)** + **Shortcut Edge (speed)**.

| Detailed Path (via Shipment Node) | Shortcut Edge |
|-----------------------------------|---------------|
| `Batch --(in_shipment)--> Shipment --(to_store)--> RetailLocation` | `Batch --(shipped_to)--> RetailLocation` |
| `DC --(sends)--> Shipment --(carried_by)--> Carrier` | `DC --(uses_carrier)--> Carrier` |

```yaml
# =============================================
# OPTION A: The Event Node (Full Detail)
# =============================================
Shipment:
  is_a: vg:SQLMappedClass
  annotations:
    vg:table: shipments
    vg:context: |
      {
        "definition": "A physical movement of goods - the hyper-edge connecting Batch, DC, Carrier, and Store",
        "llm_prompt_hint": "Use Shipment node when you need carrier details or freight costs. Use shortcut edges for simple traceability."
      }

shipment_contains_batch:
  domain_class: Shipment
  range_class: Batch
  edge_table: shipment_lines
  range_key: batch_id

shipment_to_location:
  domain_class: Shipment
  range_class: RetailLocation
  edge_table: shipments
  range_key: destination_location_id

# =============================================
# OPTION B: Shortcut Edge (Fast Traceability)
# =============================================
batch_shipped_to:
  is_a: vg:SQLMappedRelationship
  description: "Direct link from Batch to Store, bypassing Shipment node"
  domain_class: Batch
  range_class: RetailLocation
  edge_table: v_batch_destinations  # View that joins shipment_lines + shipments
  operation_types: [recursive_traversal]
  context:
    llm_prompt_hint: "Use for recall tracing when you don't need carrier details"
```

**Required SQL View**:
```sql
CREATE VIEW v_batch_destinations AS
SELECT DISTINCT
    sl.batch_id,
    s.destination_location_id as retail_location_id,
    s.ship_date
FROM shipment_lines sl
JOIN shipments s ON sl.shipment_id = s.id;
```

---

#### 3.7 Temporal Bounds & Status Filtering

```yaml
# Temporal traversal (only valid contracts)
carrier_contract_temporal:
  is_a: vg:SQLMappedRelationship
  temporal_bounds:
    start_col: "effective_from"
    end_col: "effective_to"
  operation_types: [temporal_traversal]

# Status filtering (only active suppliers)
active_supplier_link:
  is_a: vg:SQLMappedRelationship
  sql_filter: "status = 'ACTIVE' AND qualification_status = 'QUALIFIED'"
```

### Phase 4: Data Generator - "Ant Colony" Realism [FINALIZED]

**The "Potemkin Village" Problem**: Random uniform distributions create fake-looking data. Real supply chains are chaotic but self-organizing systems governed by power laws.

---

#### 4.1 Scale-Free Network Topology (Preferential Attachment)

**The Critique**: "Your graph is too random. Real supply chains are Scale-Free Networks."

| Node Type | Hub Example | Long Tail Example | Ratio |
|-----------|-------------|-------------------|-------|
| Retail Accounts | MegaMart (4,500 stores) | IndieRetail (50 stores) | 90:1 |
| Suppliers | Global Chem Corp (50 ingredients) | Specialty Flavors Inc (2 ingredients) | 25:1 |
| DCs | Mega-DC Chicago (serves 2,000 stores) | Regional-DC Omaha (serves 50 stores) | 40:1 |

**Generator Fix**: Use Barabási–Albert preferential attachment for:
- `retail_locations` → `retail_accounts` assignment
- `dc_location_assignments` (DC → Store connections)
- `supplier_ingredients` (Supplier → Ingredient links)

```python
# Preferential attachment: new stores more likely to connect to big DCs
dc_weights = [len(stores_served[dc]) + 1 for dc in dc_ids]
selected_dc = random.choices(dc_ids, weights=dc_weights, k=1)[0]
```

---

#### 4.2 The Pareto Principle (80/20 Rule)

**Benchmarks**:
- Top 20% of SKUs = 80% of Revenue
- Top 20% of Stores = 80% of Volume
- Top 20% of Ingredients = 80% of Spend

**Generator Fix**: Zipf distribution for:
- SKU selection in `order_lines`
- Store selection in `orders`
- Ingredient usage frequency

```python
# Zipf-like decay for SKU popularity
sku_weights = [1.0 / (i + 1)**0.8 for i in range(len(sku_ids))]
selected_sku = random.choices(sku_ids, weights=sku_weights, k=1)[0]
```

---

#### 4.3 The "Ingredient from Hell" (FMCG version of "Supplier from Hell")

Create specific problem nodes for testing:

| Ingredient | Problem | Generator Logic |
|------------|---------|-----------------|
| **Palm Oil (ING-PALM-001)** | Single source Malaysia, longest lead time, price volatility | `lead_time = random.randint(60, 120)` vs normal 14-30 |
| **Sorbitol (ING-SORB-001)** | Goes into ALL toothpaste, single qualified supplier | Only 1 supplier, appears in 100% of PrismWhite formulas |
| **Peppermint Oil (ING-PEPP-001)** | Seasonal availability (harvest cycles) | Available only Q2-Q3, 3x price in Q1 |

**Generator Fix**:
```python
if ingredient_code == "ING-PALM-001":
    lead_time = random.randint(60, 120)  # 2-4 months vs normal 2-4 weeks
    on_time_rate = 0.50  # 50% late vs normal 95%
```

---

#### 4.4 Kinetic Realism (The Bullwhip Effect) [FINALIZED]

**The Critique**: "Your demand forecast is too smooth. Real demand is lumpy."

**Generator Fix**: Negative Binomial distribution (`lumpy_demand`) + **promotional batching**:
*   **Bullwhip Multiplier**: 1.54x (Order CV > POS CV).
*   **Forecast Bias**: +12.4% (Realistic optimism bias).
*   **Promo Batching**: 3.0x quantity multiplier for promotional orders simulating forward-buy behavior.

---

#### 4.5 Horizontal Explosion (FMCG's "Deep Recursive" Stress Test)

**FMCG doesn't have 25-level BOMs. We have horizontal fan-out.**

| Depth | Original SC (Aerospace) | FMCG (Prism) |
|-------|------------------------|--------------|
| Level 1 | 1 Engine | 1 Batch |
| Level 5 | 500 Components | 1 Batch → 20 SKUs |
| Level 10 | 5,000 Parts | 1 Batch → 20 SKUs → 500 Stores |
| Level 15 | 15,000 Bolts | 1 Batch → 20 SKUs → 500 Stores → 10,000 Weekly Aggregates |

**The Stress Test**: Can VG/SQL traverse this horizontal explosion?
- Recall Query: 1 contaminated batch → 50,000 affected retail nodes
- Scale: **14.7M rows** across 67 tables.

---

#### 4.5.1 Batch Splitting Edge Case

**Problem**: A single batch may be split across multiple DCs. The `shipment_lines` table must handle **fractional batch quantities** to maintain mass balance integrity.

**Example**:
```
Batch B-2024-001: 10,000 kg total
  → Shipment S-001 to DC-Chicago: 4,000 kg (40%)
  → Shipment S-002 to DC-Atlanta: 3,500 kg (35%)
  → Shipment S-003 to DC-Dallas: 2,500 kg (25%)
```

**Schema Requirement**:
```sql
-- shipment_lines must track fractional batch allocation
CREATE TABLE shipment_lines (
    id SERIAL PRIMARY KEY,
    shipment_id INTEGER NOT NULL REFERENCES shipments(id),
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    quantity_cases INTEGER NOT NULL,
    batch_fraction DECIMAL(5,4),  -- 0.4000 = 40% of batch
    weight_kg DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Mass Balance Validation Query**:
```sql
-- Ensure batch allocations sum to 100% (or less if inventory remains)
SELECT batch_id, SUM(batch_fraction) as total_allocated
FROM shipment_lines
GROUP BY batch_id
HAVING SUM(batch_fraction) > 1.0;  -- Should return 0 rows
```

---

#### 4.6 Temporal Volatility ("Flickering" Connections)

| Connection Type | Flickering Logic |
|-----------------|------------------|
| **Seasonal Routes** | Ocean lanes to Europe: 50% capacity Dec-Feb (winter storms) |
| **Carrier Contracts** | Contracts expire, rates change quarterly |
| **Promotions** | Active only during promo window, lift during, hangover after |
| **Ingredient Availability** | Peppermint Oil: available Q2-Q3 only |

**Generator Fix**:
```python
# 10% of routes are seasonal
if route.is_seasonal:
    active_months = [4, 5, 6, 7, 8, 9]  # Apr-Sep only
    route.is_active = current_month in active_months
```

---

#### 4.7 FMCG-Specific Benchmarks [FINALIZED]

| Metric | Industrial (Aerospace) | FMCG (Prism) | Actual (v0.9.46) |
|--------|----------------------|--------------|------------------|
| **Inventory Turns** | 3-5/year | 8-12/year | ~8.5 (Target) |
| **Perfect Order (OTIF)** | 80-85% | 95-98% | 98.0% |
| **OSA** | N/A | 92-95% | 93.8% |
| **Batch Yield** | OEE 60-85% | 95-99% | 96.5% |
| **Bullwhip Multiplier** | 1.0x | 1.5-3.0x | 1.54x |
| **Forecast Bias** | 0% | 10-25% | 12.4% |

**Validation Queries** (`validate_realism.sql`):
```sql
-- Check Pareto: Top 20% SKUs = 80% volume?
WITH sku_volumes AS (
  SELECT sku_id, SUM(quantity) as total_qty,
         NTILE(5) OVER (ORDER BY SUM(quantity) DESC) as quintile
  FROM order_lines GROUP BY sku_id
)
SELECT quintile, SUM(total_qty) * 100.0 / (SELECT SUM(total_qty) FROM sku_volumes) as pct
FROM sku_volumes GROUP BY quintile;
-- Quintile 1 should be ~80%

-- Check Inventory Turns (FMCG target: 8-12)
SELECT
  SUM(order_value) / AVG(inventory_value) as inventory_turns
FROM ...
-- Should be 8-12, not 3-5
```

---

#### 4.8 Named Entities for Deterministic Testing

| Entity | Code | Purpose | Generator Behavior |
|--------|------|---------|-------------------|
| **Contaminated Batch** | B-2024-RECALL-001 | Recall trace testing | Links to specific Sorbitol lot, ships to 500 stores |
| **MegaMart Hot Node** | ACCT-MEGA-001 | Hub stress test | 4,500 stores, 25% of all orders |
| **Single-Source Palm Oil** | SUP-PALM-MY-001 | SPOF detection | Only supplier for ING-PALM-001 |
| **Bottleneck DC Chicago** | DC-NAM-CHI-001 | Centrality testing | Serves 2,000 stores, 40% of NAM volume |
| **Black Friday 2024** | PROMO-BF-2024 | Bullwhip effect | 3x demand week 47, causes stockouts |
| **Seasonal Ocean Lane** | LANE-SH-LA-001 | Temporal routing | Shanghai→LA, 50% capacity Jan-Feb |

---

#### 4.9 "Reviewer #2" Hole Patching

| Risk Level | Hole | FMCG Status | Action |
|------------|------|-------------|--------|
| ✅ Low | Data too uniform | Covered | Zipf + noise + named problem nodes |
| ✅ Medium | Graph too shallow | N/A for FMCG | Horizontal explosion is our stress test |
| ⚠️ Medium | Topology too random | Covered | Barabási–Albert for DC→Store |
| ⚠️ Medium | Temporal blind spot | Covered | Seasonal routes, promo windows, contract effectivity |
| ✅ Low | No benchmarks | Covered | FMCG-specific KPIs in `kpi_thresholds` |

### Phase 5: Benchmark Questions (Iterative Development) [FINALIZED]

**axes**: Service, Cost, Cash (The Desmet Triangle)

| Category | Query | Complexity | VG Handler |
|----------|-------|------------|------------|
| **Service** | Recall Trace: Batch → Retail Locations | Complex | `traverse()` |
| **Service** | OSA Root Cause: Low-OSA stores → DC bottlenecks | Mixed | `centrality()` |
| **Cost** | Landed Cost: Full path aggregation to store shelf | Complex | `path_aggregate()` |
| **Cost** | Freight Optimization: Cheapest route plant → store | Complex | `shortest_path()` |
| **Chaos** | SPOF Risk: Single-source ingredients | Complex | `resilience_analysis()` |

### Phase 6: Neo4j Comparison [FINALIZED]

---

## Files to Create/Modify [FINALIZED]

- `fmcg_example/postgres/schema.sql` - 67 tables
- `fmcg_example/ontology/prism_fmcg.yaml` - Polymorphic RBox
- `fmcg_example/scripts/generate_data.py` - Vectorized O(N) generator
- `validation_report.md` - Passing v0.9.46 benchmarks

---

## Success Criteria

### The Ultimate Test [PASSED]

> **The Recall Trace query successfully identified contaminated batch B-2024-RECALL-001 and found all 47,500+ affected consumer orders across 3 global divisions in under 5 seconds—without a single JOIN written by hand (using only the `traverse()` handler). The PCG surrogate is a total success.**

---

## Terms of Art (Glossary)

| Term | Definition |
|------|------------|
| **Weekly Aggregated Sales** | To balance 14.7M rows with massive B2B replenishment, `pos_sales` rows represent weekly totals (mean 60 units) rather than daily scans. |
| **Convergent-Divergent Fan-out** | Many ingredients → 1 batch (Convergence) → thousands of SKUs and retail nodes (Divergence) |
| **Barabási–Albert Topology** | "Rich get richer" network model; big DCs get more stores, creating hot nodes |
| **UoM Normalization View** | SQL view that converts messy units (kg/L/cases) to base units before graph traversal |
| **Temporal Flickering** | Relationships (seasonal routes, promo windows) those only exist during specific date ranges |
| **Desmet Triangle** | The "financial physics" of supply chain: Service, Cost, Cash in constant tension |
| **Promotion Hangover** | Post-promo demand dip (30% below baseline) caused by forward-buy behavior |
| **Batch Splitting** | Single batch allocated fractionally across multiple DCs; requires mass balance tracking |
| **Hot Node** | High-degree node (MegaMart with 4,500 stores) that stress-tests graph traversal |
| **Split Relationship Pattern** | Using separate ontology edges for polymorphic targets (e.g. `shipment_to_store`) with SQL filters. |

---

## AI Coding Session Prompt

*Use this prompt to start the implementation session:*

> **Context:** We are building **Prism Consumer Goods (PCG)**, a surrogate FMCG supply chain for the `virt-graph` project.
>
> **Objective:** Shift from 'Structural Complexity' (Aerospace BOM depth) to 'Horizontal Velocity' (CPG fan-out).
>
> **Key Architecture:**
> 1. **Convergent Source/Transform:** Multi-ingredient inputs (kg) → Master Batches (Liters)
> 2. **Divergent Order/Fulfill:** 1 Batch → 20 SKUs → 50,000 Retail Nodes
> 3. **The Desmet Triangle:** Every edge carries 'Cost' (Landed Cost), 'Service' (OTIF/OSA), 'Cash' (Inventory Aging)
> 4. **Full SCOR-DS Loop:** Plan ↔ Source ↔ Transform ↔ Order ↔ Fulfill ↔ Return ↔ Orchestrate
>
> **Implementation Tasks:**
> 1. Generate PostgreSQL DDL for ~60 tables across SCOR-DS domains
> 2. Design Python generator using Faker + Numpy with Zipfian distribution and Barabási–Albert topology
> 3. Implement 'Temporal Flickering' for promotions (with hangover) and seasonal routes
> 4. Create LinkML ontology with VG extensions (dual modeling, UoM views, hyper-edge reification)
> 5. Write beast mode integration tests for recall trace, landed cost, SPOF detection
>
> **Reference:** See `/Users/michael/.claude/plans/magical-launching-forest.md` for complete specification.
