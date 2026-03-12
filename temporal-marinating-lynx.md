# Plan: Cost-to-Serve Demo Data Generator

## Context

We're building a curated ~2000-row DuckDB database to demo for a CSCO at a major FMCG company. The existing prism-sim DuckDB has 350M+ rows of flat, uninteresting simulation data. We need a small, story-rich dataset that answers one question compellingly:

**"Why does the same toothpaste make us 53% margin through Club and 25% through Convenience?"**

The answer unfolds across a **3D CTS cube** (Channel x Category x Location) with 6 cost drivers — all traceable through the ontology across multiple tables.

### The 3D CTS Cube

**Axis 1 — Channel**: Club vs Grocery vs Convenience (different freight modes, trade terms, return rates, DSO)
**Axis 2 — Category**: ORAL_CARE (light/high-margin, expensive actives) vs HOME_CARE (heavy/mid-margin, yield issues) vs PERSONAL_WASH (heavy/low-margin, price creep eats thin margins)
**Axis 3 — Location**: Even within a channel, individual stores vary — urban convenience (NYC, $18/case last mile) vs suburban convenience (Newark, $10/case); near-DC club store vs far club store

The CSCO can slice CTS any way: "show me margin by channel", "show me margin by category", "why is Store 5 unprofitable?"

## Output

- Script: `scripts/generate_demo_db.py`
- Database: `pcg_example/data/demo.duckdb`
- Run: `poetry run python scripts/generate_demo_db.py`

## The 6 CTS Dimensions (with target numbers for hero SKU: BrightSmile Premium @ $48/case)

| # | Dimension | Club | Grocery | Convenience | Tables involved |
|---|-----------|------|---------|-------------|-----------------|
| 1 | **Freight (drop size/mode)** | $1.60/case (FTL, 200+ cases) | $4.20/case (mix FTL/LTL, 60 cases) | $12.50/case (LTL, 15 cases) | shipments, shipment_lines, route_segments |
| 2 | **Trade spend** | 12% off list → net $42.24 | 25% off list → $36.00 | 15% off list → $40.80 | ar_invoice_lines.unit_price vs skus.price_per_case |
| 3 | **Return rates** | 1% | 3% | 5% | returns, return_lines, disposition_logs |
| 4 | **Payment terms (DSO)** | Net 15, pays day 18 | Net 30, pays day 38 | Net 60, pays day 65 | ar_invoices.due_date, ar_receipts.receipt_date |
| 5 | **Yield variance** | N/A (oral care OK) | Affects HC SKU | Affects HC SKU | batches.yield_percent, batch_ingredients |
| 6 | **Supplier price creep** | Affects all channels equally | Same | Same | invoice_variances, ap_invoice_lines vs po_lines |

### CTS Waterfall by Channel (hero SKU: BrightSmile Premium $48 list)

```
                          Club        Grocery     Convenience
List Price               $48.00      $48.00       $48.00
Trade Spend              -$5.76      -$12.00      -$7.20
= Net Revenue            $42.24      $36.00       $40.80

Materials (COGS)         $18.00      $18.00       $18.00
Freight (all legs)       $1.60       $4.20        $12.50
Returns cost             $0.18       $0.54        $0.90
Working capital cost     $0.05       $0.17        $0.32
= Total Cost-to-Serve    $19.83      $22.91       $31.72

Margin $                 $22.41      $13.09       $9.08
Margin %                 53.1%       36.4%        22.3%
```

### CTS Variance by Category (through Grocery channel as baseline)

```
                     ORAL_CARE      HOME_CARE       PERSONAL_WASH
                     (BrightSmile)  (FreshHome)     (AquaPure)
List Price           $48.00         $22.50          $16.50
Trade Spend (25%)    -$12.00        -$5.63          -$4.13
= Net Revenue        $36.00         $16.87          $12.37

Materials            $18.00         $8.60           $7.90
 (light cases)       (heavy cases)  (heavy cases)
Freight/case         $3.20          $4.80           $4.60
 (5.4 kg/case)       (7.2 kg/case)  (7.2 kg/case)
Returns (3%)         $0.54          $0.26           $0.24
WC cost              $0.17          $0.08           $0.06
= Total CTS          $21.91         $13.74          $12.80

Margin $             $14.09         $3.13           -$0.43  ← NEGATIVE!
Margin %             39.1%          18.6%           -3.5%
```

**Category insight**: PERSONAL_WASH through Grocery is margin-negative once freight is allocated — the heavy cases + thin margin + 25% trade spend kills it. This is invisible in aggregate P&L.

### CTS Variance by Store Location (Convenience channel, hero SKU)

```
                     Store 5        Store 6        Store 8
                     (NYC urban)    (Newark)       (Philly)
Freight/case         $18.00         $10.50         $8.20
 (congestion,        (easier         (near plant,
  delivery windows)   access)        short last mile)
Margin %             8.4%           22.0%          27.2%
```

**Location insight**: Same channel, same product — 19-point margin spread between NYC and Philly convenience stores, driven entirely by last-mile economics.

## ID Scheme

- Ingredients: 1-15
- Bulk Intermediates: 51-56 (avoids collision with ingredient IDs in polymorphic formula_ingredients.ingredient_id)
- SKUs: 1-10 (8 active + 2 OLD aliases)
- Suppliers: 1-5
- Plants: 1-3
- Production Lines: 1-6
- Formulas: 1-14
- Channels: 1-3
- Distribution Centers: 1-6 (IDs 1-2 = RDC, 3-6 = customer_dc)
- Retail Locations: 1-8
- Route Segments: 1-25
- Chart of Accounts: 1-12
- Days: 1-90 (Q1 window)

Transaction sequence IDs (for causal ordering):
- POs: 1000+, GRs: 2000+, WOs: 3000+, Shipments: 4000+
- Orders: 5000+, Returns: 6000+, AP Invoices: 7000+, AR Invoices: 8000+
- AP Payments: 9000+, AR Receipts: 9500+

## Data Design: Master Data (~190 rows)

### Suppliers (5)
| id | code | name | country | tier | story role |
|----|------|------|---------|------|------------|
| 1 | SUP-001 | ChemSource International | CN | 1 | Overseas specialty chemicals, long lead times |
| 2 | SUP-002 | AmeriPack Solutions | US | 1 | Domestic packaging — **the overcharger** (invoices 6% above PO on HDPE bottles) |
| 3 | SUP-003 | GreenBase Ingredients | IN | 2 | India-based bulk ingredients, competitive pricing |
| 4 | SUP-004 | NorthStar Chemicals | CA | 1 | Canadian chemicals, reliable domestic-ish |
| 5 | SUP-005 | Pacific Fragrances | US | 2 | Domestic fragrance house |

### Ingredients (15)
| id | code | name | cost/kg | story role |
|----|------|------|---------|------------|
| 1 | ACT-FLUOR-001 | Stannous Fluoride | $185.00 | Expensive active, drives premium SKU COGS |
| 2 | ACT-SURFAC-001 | Sodium Lauryl Sulfate | $12.50 | Common surfactant |
| 3 | ACT-CITRIC-001 | Citric Acid | $8.75 | |
| 4 | BASE-SORBIT-001 | Sorbitol Solution | $3.20 | |
| 5 | BASE-WATER-001 | Purified Water | $0.15 | Cheap bulk filler |
| 6 | BASE-GLYCER-001 | Glycerin | $4.80 | |
| 7 | BASE-SILICA-001 | Hydrated Silica | $22.00 | |
| 8 | FRAG-CITRUS-001 | Citrus Essential Oil | $45.00 | Key to HC premix |
| 9 | FRAG-MINT-001 | Peppermint Oil | $38.00 | |
| 10 | PKG-TUBE-001 | Laminate Tube 150ml | $0.42 | |
| 11 | PKG-BOTTLE-001 | HDPE Bottle 500ml | $0.68 | **Price creep target** — AP invoices show $0.72 |
| 12 | PKG-BOTTLE-002 | PET Bottle 250ml | $0.55 | |
| 13 | PKG-CAP-001 | Flip-Top Cap | $0.18 | |
| 14 | PKG-LABEL-001 | Adhesive Label | $0.08 | |
| 15 | STAB-XANTH-001 | Xanthan Gum | $32.00 | |

### Supplier-Ingredients (~22)
Key patterns:
- Stannous Fluoride (ING 1): **only from SUP-001** (45-day lead, single source)
- HDPE Bottles (ING 11): from SUP-002 at $0.68 (but invoiced at $0.72 — the leak)
- SLS (ING 2): dual-sourced from SUP-003 ($11.80) and SUP-004 ($12.80) — price competition visible
- Water (ING 5): from SUP-004 at $0.15, 3-day lead — trivially cheap

### SKUs (10)
| id | code | name | category | price/case | cost/case | weight_kg | story role |
|----|------|------|----------|-----------|-----------|-----------|------------|
| 1 | SKU-OC-001 | BrightSmile Premium Whitening 150ml | ORAL_CARE | $48.00 | $18.00 | 5.40 | **Hero SKU** — all 3 channels. Light case = low freight/case |
| 2 | SKU-OC-002 | BrightSmile Mint Fresh Gel 120ml | ORAL_CARE | $36.00 | $14.20 | 4.32 | Secondary OC, even lighter |
| 3 | SKU-HC-001 | FreshHome All-Purpose Cleaner 500ml | HOME_CARE | $22.50 | $8.60 | 7.20 | **Yield trap** + heavy case = high freight/case |
| 4 | SKU-HC-002 | FreshHome Citrus Spray 350ml | HOME_CARE | $18.00 | $7.80 | 5.04 | |
| 5 | SKU-PW-001 | AquaPure Body Wash 250ml | PERSONAL_WASH | $16.50 | $7.90 | 7.20 | **Price creep** + heavy + low margin = margin-negative in some combos |
| 6 | SKU-PW-002 | AquaPure Gentle Body Wash 250ml | PERSONAL_WASH | $14.00 | $7.50 | 7.20 | Lowest margin SKU — any cost pressure kills it |
| 7 | SKU-OC-003 | BrightSmile Kids Paste 75ml | ORAL_CARE | $28.00 | $11.00 | 4.32 | |
| 8 | SKU-HC-003 | FreshHome Lavender Spray 350ml | HOME_CARE | $19.50 | $8.20 | 5.04 | |
| 9 | SKU-OC-001-OLD | BrightSmile Whitening 150ml (OLD) | ORAL_CARE | $45.00 | $16.80 | 5.40 | Alias chain (superseded by SKU 1) |
| 10 | SKU-PW-001-OLD | AquaPure Body Wash 250ml (OLD) | PERSONAL_WASH | $15.00 | $7.60 | 7.20 | Alias chain (superseded by SKU 5) |

**Category weight economics**: OC cases ~5 kg, HC/PW cases ~7 kg. Since freight is weight-based, HC/PW pay ~33% more freight per case than OC — a hidden category-level CTS driver.

SKU 9: supersedes_sku_id → 1, SKU 10: supersedes_sku_id → 5

### Distribution Network

**Plants (3):**
1. PLANT-EAST, Philadelphia PA
2. PLANT-CENTRAL, Cincinnati OH
3. PLANT-WEST, Phoenix AZ

**Distribution Centers (6):**
1. RDC-EAST, Charlotte NC (type=rdc)
2. RDC-CENTRAL, Nashville TN (type=rdc)
3. CLUB-DC-EAST, Atlanta GA (type=customer_dc) — Club channel
4. GROC-DC-SOUTH, Tampa FL (type=customer_dc) — Grocery channel
5. CONV-DC-NORTHEAST, Newark NJ (type=customer_dc) — Convenience channel
6. GROC-DC-CENTRAL, Indianapolis IN (type=customer_dc) — Grocery channel

**Retail Locations (8):** — each with distinct CTS profile even within same channel
| id | name | city | format | channel | last-mile story |
|----|------|------|--------|---------|-----------------|
| 1 | Club Store Atlanta-1 | Atlanta | club | CLUB | Near DC, $0.40/case last mile |
| 2 | Club Store Atlanta-2 | Marietta | club | CLUB | Suburbs, $0.60/case |
| 3 | FreshMart Tampa-1 | Tampa | supermarket | GROCERY | Near DC, $2.50/case |
| 4 | FreshMart Tampa-2 | Clearwater | supermarket | GROCERY | Further out, $3.50/case |
| 5 | QuickStop NYC | New York | convenience | CONVENIENCE | Urban congestion, delivery windows → **$18/case** |
| 6 | QuickStop Newark | Newark | convenience | CONVENIENCE | Easier access, $10.50/case |
| 7 | FreshMart Indianapolis | Indianapolis | supermarket | GROCERY | Far from RDC, extra leg, $5.00/case |
| 8 | QuickStop Philadelphia | Philadelphia | convenience | CONVENIENCE | Near Plant-East, short route, $8.20/case |

**Channels (3):**
1. CLUB — warehouse clubs
2. GROCERY — supermarkets
3. CONVENIENCE — small format

**Route Segments (~25):**
Multi-leg transport network with realistic distances:
- Plant → RDC legs (primary distribution, FTL)
- RDC → RDC lateral links
- RDC → Customer DC legs (secondary, mix FTL/LTL)
- Customer DC → Store legs (last mile)
- Supplier → Plant legs (inbound)

### Product Hierarchy

**Bulk Intermediates (6):** IDs 51-56
- 51: Whitening Paste Base (OC, bom_level=1)
- 52: All-Purpose Cleaner Base (HC, bom_level=1)
- 53: Body Wash Base (PW, bom_level=1)
- 54: Fluoride Active Premix (OC, bom_level=2)
- 55: Citrus Fragrance Premix (HC, bom_level=2) — **the yield-problem premix**
- 56: Mint Gel Base (OC, bom_level=1)

**Formulas (14):**
- F1-F2: premix formulas (bom_level=2)
- F3-F6: bulk formulas (bom_level=1)
- F7-F14: SKU-level formulas (bom_level=0)

**Formula Ingredients (~55):**
Each formula has 3-5 ingredients. Key: formula_ingredients.ingredient_id is polymorphic — can reference ingredients (1-15) OR bulk_intermediates (51-56).

## Data Design: Transactional Data (~1,650 rows)

### Procurement Cycle (~170 rows)

**Purchase Orders (20):** Spread across days 5-30, various suppliers to various plants.

**PO Lines (35):** 1-3 lines per PO. Unit costs match supplier_ingredients.

**Goods Receipts (20):** Linked to inbound shipments, receipt_date = PO order_date + lead_time_days.

**GR Lines (35):** Mirror PO lines (quantities received).

**AP Invoices (20):** Linked to GRs and suppliers.
- **Story nugget:** AmeriPack (SUP-002) AP invoices for HDPE bottles (ING 11) show unit_cost = $0.72 instead of PO's $0.68.

**AP Invoice Lines (35):** Most match PO prices. AmeriPack bottle invoices are 6% higher.

**AP Payments (18):** Payment dates 30-45 days after invoice.

**Invoice Variances (8):** Captures the AmeriPack overcharges.
- variance_type = 'price'
- expected_value = $0.68, actual_value = $0.72
- variance_amount computed per line
- resolution_status = 'open' (nobody's fixing it!)

### Manufacturing (~170 rows)

**Work Orders (18):** Across 3 plants, days 10-40.

**Batches (30):**
- Most batches: yield_percent = 96-98% (normal)
- **Story nugget:** 4-5 Citrus Premix batches (formula 2, product_id=55) with yield_percent = 82-85% — the yield trap
- product_type: 'premix' (bom_level=2), 'bulk_intermediate' (bom_level=1), 'finished_good' (bom_level=0)

**Batch Ingredients (120):**
- Normal batches: actual qty ≈ formula qty × batch qty (within 1-2%)
- Bad yield batches: actual qty is HIGHER than expected (consumed more material for less output)
- This is where the yield trap becomes visible — same formula, more material consumed

### Demand & Fulfillment (~550 rows)

**Orders (60):** Distributed across channels with VERY different profiles:
- Club orders (15): 150-300 cases each, source_id=1 (CLUB channel), retail_location_id 1-2
- Grocery orders (25): 40-80 cases each, source_id=2, retail_location_id 3-4, 7
- Convenience orders (20): 8-20 cases each, source_id=3, retail_location_id 5-6, 8
- All orders include the hero SKU (SKU 1) plus others

**Order Lines (150):** 2-3 lines per order. Hero SKU appears in ~40 orders across all channels.

**Shipments (50):** Multi-leg, this is where freight economics diverge:
- Leg 1 (plant_to_rdc): 8-10 FTL shipments, $1,800-2,400 freight, 15,000-20,000 kg — shared across channels
- Leg 2 (rdc_to_customer_dc):
  - To Club DC: 5 shipments, near-FTL, $800-1,200, carrying 1,000+ cases
  - To Grocery DC: 8 shipments, partial load, $600-900, carrying 200-400 cases
  - To Conv DC: 6 shipments, LTL, $350-500, carrying 50-100 cases — **high per-case cost**
- Leg 3 (customer_dc_to_store):
  - Club: 4 shipments, large drops, $150-250
  - Grocery: 8 shipments, medium drops, $180-300
  - Convenience: 10 shipments, tiny drops (15-25 cases), $150-220 — **last mile killer**

**Shipment Lines (120):** Link shipments to SKUs with quantities and weights.

**AR Invoices (50):** Channel column set, due_dates vary by channel terms:
- Club: invoice_date + 15 days
- Grocery: invoice_date + 30 days
- Convenience: invoice_date + 60 days

**AR Invoice Lines (120):** unit_price reflects trade spend (discounted from list):
- Club: unit_price = price_per_case × 0.88
- Grocery: unit_price = price_per_case × 0.75
- Convenience: unit_price = price_per_case × 0.85

**AR Receipts (45):** receipt_date shows actual payment behavior:
- Club: pays on time or early (receipt_date ≈ due_date - 2 to due_date)
- Grocery: pays near terms (receipt_date ≈ due_date to due_date + 8)
- Convenience: pays LATE (receipt_date ≈ due_date + 5 to due_date + 15)

### Returns (~40 rows)

**Returns (10):** Rate varies by channel:
- Club: 1 return out of 15 orders (6.7% of orders, but tiny quantities)
- Grocery: 2 returns out of 25 orders
- Convenience: 3 returns out of 20 orders (15% of orders)

**Return Lines (15):** Small quantities per return.

**Disposition Logs (15):** Mix of restock/destroy/discount.

### GL Journal & Analytics (~380 rows)

**GL Journal (~200):** Double-entry for key events:
- Production: DR WIP / CR RM Inventory
- Completion: DR FG Inventory / CR WIP
- Shipment: DR In-Transit / CR FG Inventory
- Delivery: DR COGS / CR In-Transit
- Revenue: DR AR / CR Revenue
- Freight: DR Freight Expense / CR Cash/AP
- AP payment: DR AP / CR Cash
- AR receipt: DR Cash / CR AR

**Inventory (150):** Weekly snapshots (days 7, 14, 21, ...) across key locations and SKUs.

**Demand Forecasts (30):** Statistical forecasts for hero SKUs.

## Script Structure

```python
#!/usr/bin/env python3
"""Generate curated cost-to-serve demo DuckDB (~2000 rows, 38 tables).

Story: Same premium toothpaste, 53% margin through Club, 22% through Convenience.
Six CTS dimensions: freight/drop-size, trade spend, returns, payment terms,
yield variance, supplier price creep.

Usage: poetry run python scripts/generate_demo_db.py
Output: pcg_example/data/demo.duckdb
"""
import duckdb
from pathlib import Path

OUTPUT = Path("pcg_example/data/demo.duckdb")

def create_tables(conn):
    """DDL for all 38 tables — exact same schema as production DuckDB."""

def insert_suppliers(conn): ...
def insert_ingredients(conn): ...
def insert_supplier_ingredients(conn): ...
def insert_plants(conn): ...
def insert_production_lines(conn): ...
def insert_channels(conn): ...
def insert_chart_of_accounts(conn): ...
def insert_bulk_intermediates(conn): ...
def insert_formulas(conn): ...
def insert_formula_ingredients(conn): ...
def insert_skus(conn): ...
def insert_distribution_centers(conn): ...
def insert_retail_locations(conn): ...
def insert_route_segments(conn): ...

def insert_purchase_orders(conn): ...
def insert_goods_receipts(conn): ...
def insert_ap_invoices(conn): ...
def insert_ap_payments(conn): ...
def insert_invoice_variances(conn): ...

def insert_work_orders(conn): ...
def insert_batches(conn): ...
def insert_batch_ingredients(conn): ...

def insert_orders(conn): ...
def insert_shipments(conn): ...
def insert_ar_invoices(conn): ...
def insert_ar_receipts(conn): ...

def insert_returns(conn): ...

def insert_gl_journal(conn): ...
def insert_inventory(conn): ...
def insert_demand_forecasts(conn): ...

def verify(conn):
    """Print row counts and run 3 story-validation queries."""

def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()
    conn = duckdb.connect(str(OUTPUT))
    try:
        create_tables(conn)
        # ... all inserts in FK-dependency order ...
        verify(conn)
    finally:
        conn.close()
```

Data defined as lists of tuples with column-name comments. Bulk inserted via `executemany`.

## Verification Queries (run at end of script, printed as formatted tables)

1. **Margin by Channel** (Axis 1) — hero SKU net revenue vs allocated freight per case
2. **Margin by Category** (Axis 2) — through Grocery channel, showing OC profitable / PW margin-negative
3. **Margin by Store Location** (Axis 3) — Convenience stores showing NYC vs Newark vs Philly spread
4. **Yield variance** — good vs bad HC batches, material cost delta
5. **Supplier price creep** — AP vs PO unit cost on HDPE bottles, total variance $
6. **DSO by channel** — actual avg days-to-pay vs terms

## Files to Create/Modify

| File | Action |
|------|--------|
| `scripts/generate_demo_db.py` | **CREATE** — the generator script |
| `pcg_example/data/demo.duckdb` | **CREATE** — generated output (gitignored) |
| `pcg_example/data/.gitkeep` | **CREATE** — keep directory in git |
| `.gitignore` | **EDIT** — add `*.duckdb` |
| `CHANGELOG.md` | **EDIT** — add entry |
| `README.md` | **EDIT** — mention demo DB |
| `pyproject.toml` | **EDIT** — add duckdb dependency if not present |

## Row Count Target

| Category | Tables | Rows |
|----------|--------|------|
| Master/Reference | 14 tables | ~190 |
| Procurement | 5 tables | ~170 |
| Manufacturing | 3 tables | ~170 |
| Demand/Fulfillment | 7 tables | ~550 |
| Returns | 3 tables | ~40 |
| GL/Analytics | 3 tables | ~380 |
| **Total** | **38 tables** | **~1,850** |
