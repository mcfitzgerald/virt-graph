# Phase 4: FMCG Data Generator Implementation Plan

## Summary

Implement `fmcg_example/scripts/generate_data.py` to generate **~7.5M rows** across 67 tables with realistic FMCG distributions (Zipf, preferential attachment, lumpy demand with promo hangover).

**Decisions Made:**
- **Row count**: Full ~7.5M (not reduced to 4M)
- **Output**: Single `seed.sql` file (~600MB estimated)
- **Progress**: Print statements to stdout
- **Validation**: In-memory (no SQL load until ready)
- **Iteration**: Level-based regeneration with cascade support

## Current State

- **Schema**: Complete (67 tables + 8 views in `fmcg_example/postgres/schema.sql`)
- **Scaffold**: `generate_data.py` has COPY helpers, distribution functions, named entities, but zero actual generation
- **Old Reference**: `ARCHIVE/supply_chain_example/scripts/generate_data.py` (3,663 lines) provides COPY patterns

## Key Design Decisions

### 1. Architecture: Single-Class Generator with Level-Based Regeneration

```
generate_data.py
├── FMCGDataGenerator (orchestrator)
│   ├── generate_all() - calls level generators in FK order (0-14)
│   ├── generate_from_level(n) - regenerate levels n through 14 (cascade)
│   ├── validate_realism() - in-memory validation, returns pass/fail
│   └── write_sql() - outputs COPY statements (only when ready)
│
├── Level Generators (grouped by dependency level)
│   ├── _generate_level_0() - divisions, channels, products, ingredients...
│   ├── _generate_level_1() - suppliers, plants, production_lines...
│   ├── _generate_level_2() - supplier_ingredients, formulas...
│   ├── _generate_level_3() - retail_accounts, retail_locations, DCs
│   ├── _generate_level_4() - skus, promotions...
│   ├── _generate_level_5() - purchase_orders, work_orders...
│   ├── _generate_level_6() - batches, batch_cost_ledger...
│   ├── _generate_level_7() - batch_ingredients, inventory
│   ├── _generate_level_8() - pos_sales, orders, forecasts... (LARGEST)
│   ├── _generate_level_9() - order_lines, order_allocations...
│   ├── _generate_level_10() - shipments, shipment_legs...
│   ├── _generate_level_11() - shipment_lines
│   ├── _generate_level_12() - returns, return_lines...
│   ├── _generate_level_13() - disposition_logs
│   └── _generate_level_14() - kpi_actuals, osa_metrics... (LEAF)
│
└── Validation Suite
    ├── _validate_row_counts()
    ├── _validate_pareto()
    ├── _validate_hub_concentration()
    ├── _validate_named_entities()
    ├── _validate_spof()
    ├── _validate_promo_hangover()
    └── _validate_referential_integrity()
```

**CLI Interface:**
```bash
# Full generation + validation (no file write)
python generate_data.py --validate-only

# Full generation + write seed.sql
python generate_data.py

# Regenerate from specific level (cascade) - for iteration
python generate_data.py --from-level 8 --validate-only

# Regenerate leaf tables only (Level 14)
python generate_data.py --from-level 14 --validate-only
```

### 2. Performance: PostgreSQL COPY (Already Scaffolded)

The COPY helpers are already implemented. Output format:
```sql
COPY table_name (col1, col2, ...) FROM stdin;
value1\tvalue2\t...
value1\tvalue2\t...
\.
SELECT setval('table_name_id_seq', <max_id>);
```

Estimated file size: ~600MB for 7.5M rows (acceptable for single-file load).

### 3. Generation Order (14 Levels by FK Dependencies)

| Level | Tables | Est. Rows |
|-------|--------|-----------|
| 0 | divisions, channels, products, packaging_types, ports, carriers, emission_factors, kpi_thresholds, business_rules, ingredients | ~1.2K |
| 1 | suppliers, plants, production_lines, carrier_contracts, route_segments | ~500 |
| 2 | supplier_ingredients, certifications, formulas, formula_ingredients, carrier_rates, routes, route_segment_assignments | ~6K |
| 3 | retail_accounts, retail_locations, distribution_centers | ~10K |
| 4 | skus, sku_costs, sku_substitutes, promotions, promotion_skus, promotion_accounts | ~20K |
| 5 | purchase_orders, goods_receipts, work_orders, supplier_esg_scores, sustainability_targets, modal_shift_opportunities | ~80K |
| 6 | purchase_order_lines, goods_receipt_lines, work_order_materials, batches, batch_cost_ledger | ~550K |
| 7 | batch_ingredients, inventory | ~700K |
| 8 | pos_sales, demand_forecasts, forecast_accuracy, consensus_adjustments, orders, replenishment_params, demand_allocation, capacity_plans | ~2.5M |
| 9 | order_lines, order_allocations, supply_plans, plan_exceptions, pick_waves | ~1M |
| 10 | pick_wave_orders, shipments, shipment_legs | ~730K |
| 11 | shipment_lines | ~540K |
| 12 | rma_authorizations, returns, return_lines | ~140K |
| 13 | disposition_logs | ~100K |
| 14 | kpi_actuals, osa_metrics, risk_events, audit_log | ~1M |

**Total: ~7.5M rows**

### 4. Realism Requirements (from magical-launching-forest.md Section 4)

| Pattern | Implementation | Where Applied |
|---------|---------------|---------------|
| **Zipf/Pareto** | `zipf_weights()` already implemented | SKU popularity in orders/POS, store volume |
| **Preferential Attachment** | `barabasi_albert_attachment()` already implemented | DC→Store, Supplier→Ingredient |
| **Lumpy Demand** | `lumpy_demand()` already implemented | POS sales, order quantities |
| **Promo Hangover** | 0.6x multiplier post-promo | pos_sales, orders during promo windows |
| **Seasonal Routes** | 50% capacity Jan-Feb | route_segments.is_active filter |
| **Named Problem Nodes** | `create_named_entities()` already implemented | Contaminated batch, single-source supplier, hot DC |

### 5. Named Entities (Deterministic Testing)

Already defined in scaffold:
- `B-2024-RECALL-001`: Contaminated Sorbitol batch → 500 stores
- `ACCT-MEGA-001`: MegaMart (4,500 stores, 25% of orders)
- `SUP-PALM-MY-001`: Single-source Palm Oil (SPOF)
- `DC-NAM-CHI-001`: Bottleneck DC Chicago (40% NAM volume)
- `PROMO-BF-2024`: Black Friday 2024 (3x demand)
- `LANE-SH-LA-001`: Seasonal Shanghai→LA (50% capacity Jan-Feb)

### 6. In-Memory Validation & Iteration Workflow

**Problem**: Loading 7.5M rows to PostgreSQL takes 5-10 minutes per iteration. With 10-20 iterations for realism tuning, that's 100-200 minutes of SQL loading alone.

**Solution**: Validate in Python memory before writing to file.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ITERATION WORKFLOW                           │
│                                                                 │
│  1. Generate ALL levels (0-14) into memory         [4-5 min]   │
│                         ↓                                       │
│  2. validate_realism() - in-memory checks          [30-60 sec] │
│                         ↓                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ IF issue in LEAF tables (Level 14):                     │   │
│  │   → Clear Level 14 lists, regenerate with new params    │   │
│  │   → Time: ~30 seconds                                   │   │
│  │                                                         │   │
│  │ IF issue in FOUNDATION tables (Levels 0-7):             │   │
│  │   → generate_from_level(N) - cascade regenerates N-14   │   │
│  │   → Time: depends on level (see table below)            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         ↓                                       │
│  3. Repeat until all checks pass                               │
│                         ↓                                       │
│  4. write_sql() - only once when ready             [1 min]     │
│                         ↓                                       │
│  5. psql -f seed.sql - only once                   [5-10 min]  │
└─────────────────────────────────────────────────────────────────┘
```

**Cascade Regeneration Times:**

| From Level | Tables Affected | Rows Regenerated | Time |
|------------|-----------------|------------------|------|
| 0 | All (0-14) | ~7.5M | ~5 min |
| 3 | Levels 3-14 | ~7.4M | ~5 min |
| 8 | Levels 8-14 | ~5.5M | ~3 min |
| 11 | Levels 11-14 | ~1.8M | ~1 min |
| 14 | Level 14 only | ~1M | ~30 sec |

**Validation Checks (All In-Memory):**

| Check | Target | How Validated |
|-------|--------|---------------|
| Row counts | ±10% of target | `len(self.orders)` etc. |
| Pareto 80/20 | 75-85% | Counter on order_lines by SKU |
| Hub concentration | MegaMart 20-30% | Filter orders by account_id |
| Named entities | All 9 present | Dict lookup |
| SPOF ingredients | 2-3 single-source | Group supplier_ingredients |
| Promo hangover | Week 47: 2.5-3.5x, Week 48: 0.5-0.75x | Group pos_sales by week |
| FK integrity | 0 invalid refs | Set membership checks |

**Expected Iteration Pattern (10-20 iterations):**

| Phase | Iterations | Issue Type | Level | Time Each |
|-------|------------|------------|-------|-----------|
| Early | 3-5 | Foundation fixes (hub distribution, Zipf params) | 0-7 | ~5 min |
| Middle | 5-10 | Transaction fixes (order patterns, promo effects) | 8-11 | ~2 min |
| Late | 5-10 | Leaf fixes (OSA values, KPI thresholds) | 14 | ~30 sec |

**Total iteration time: ~50-60 minutes** (vs. 200-300 minutes with SQL load each time)

## Implementation Steps

### Step 1: Dependencies, Setup, and CLI (~1 hour)
- Uncomment numpy and faker imports
- Add `numpy` and `faker` to pyproject.toml if missing
- Initialize Faker with seed for reproducibility
- Create ID tracking dicts for referential integrity
- Add argparse CLI with flags:
  - `--validate-only` - generate + validate, no file write
  - `--from-level N` - regenerate levels N-14 only (requires prior generation)
  - `--output PATH` - custom output path (default: seed.sql)
  - `--seed N` - random seed for reproducibility

### Step 2: Level 0-3 Reference/Master Data (~2 hours)
Tables: divisions, channels, products, packaging_types, ports, carriers, emission_factors, kpi_thresholds, business_rules, ingredients, suppliers, plants, production_lines, carrier_contracts, route_segments, supplier_ingredients, certifications, formulas, formula_ingredients, carrier_rates, routes, route_segment_assignments, retail_accounts, retail_locations, distribution_centers

Key patterns:
- Hardcode divisions, plants, products (already in stub generators)
- Generate ingredients with CAS numbers, storage requirements
- Generate suppliers with tier distribution (40 T1, 80 T2, 80 T3)
- Apply preferential attachment for supplier-ingredient links
- Generate retail accounts with named hot node (ACCT-MEGA-001)
- Apply preferential attachment for retail_locations→retail_accounts (MegaMart gets 4,500)

### Step 3: Level 4-5 SKU Explosion and Procurement (~2 hours)
Tables: skus, sku_costs, sku_substitutes, promotions, promotion_skus, promotion_accounts, purchase_orders, goods_receipts, work_orders, supplier_esg_scores, sustainability_targets, modal_shift_opportunities

Key patterns:
- SKU explosion: product × packaging × size × region = ~2,000 SKUs
- SKU substitutes: create equivalency groups (6oz ↔ 8oz)
- Promotions: include PROMO-BF-2024 with dates, lift multiplier
- POs: generate with realistic lead times, supplier tier pricing

### Step 4: Level 6-7 Manufacturing Core (~2 hours)
Tables: purchase_order_lines, goods_receipt_lines, work_order_materials, batches, batch_cost_ledger, batch_ingredients, inventory

Key patterns:
- Batches: include B-2024-RECALL-001 with QUALITY_HOLD status
- Batch ingredients: maintain mass balance (input kg = output kg - scrap)
- Inventory: distribute across DCs with aging buckets

### Step 5: Level 8-9 Demand and Orders (~3 hours) - **LARGEST**
Tables: pos_sales (~2M), demand_forecasts, forecast_accuracy, consensus_adjustments, orders, replenishment_params, demand_allocation, capacity_plans, order_lines, order_allocations, supply_plans, plan_exceptions, pick_waves

Key patterns:
- POS sales: Zipf distribution for SKUs, lumpy demand with seasonality
- Apply promo lift and hangover around PROMO-BF-2024 week 47
- Orders: 25% to ACCT-MEGA-001 (hot node)
- Order lines: Zipf for SKU selection

### Step 6: Level 10-11 Shipments (~2 hours)
Tables: pick_wave_orders, shipments, shipment_legs, shipment_lines

Key patterns:
- Shipments: batch splitting with batch_fraction
- Shipment legs: multi-leg routing (Plant→Port→Ocean→DC→Store)
- DC-NAM-CHI-001: 40% of NAM shipments

### Step 7: Level 12-14 Returns and Monitoring (~2 hours)
Tables: rma_authorizations, returns, return_lines, disposition_logs, kpi_actuals, osa_metrics, risk_events, audit_log

Key patterns:
- Returns: 3-5% return rate
- Disposition: weighted (70% restock, 15% liquidate, 10% scrap, 5% donate)
- OSA metrics: 92-95% average, lower during promo weeks
- KPI actuals: variance from thresholds

### Step 8: In-Memory Validation Suite (~2 hours)
Implement `validate_realism()` with these checks:
- `_validate_row_counts()` - compare len() to targets (±10%)
- `_validate_pareto()` - Counter on order_lines, check 75-85%
- `_validate_hub_concentration()` - MegaMart orders 20-30%
- `_validate_named_entities()` - all 9 codes exist in their tables
- `_validate_spof()` - ING-SORB-001, ING-PALM-001 are single-source
- `_validate_promo_hangover()` - week 47 lift, week 48 dip
- `_validate_referential_integrity()` - spot-check FK validity
- Print detailed report with ✓/✗ per check
- Return dict of {check_name: (passed, message)}

### Step 9: Output Generation (~1 hour)
- Implement `write_sql()` with COPY statements
- Add summary statistics header comment
- Add deferred FK ALTER statements at end
- Implement `generate_from_level(n)` for cascade regeneration
  - Clear lists for levels n through 14
  - Re-run `_generate_level_N()` through `_generate_level_14()`

### Step 10: Integration Testing (~1 hour)
- Test full workflow: `python generate_data.py --validate-only`
- Test cascade: `python generate_data.py --from-level 14 --validate-only`
- Load to PostgreSQL: `psql -f seed.sql`
- Run `validate_realism.sql` queries to confirm SQL matches in-memory

## Files to Modify

| File | Changes |
|------|---------|
| `fmcg_example/scripts/generate_data.py` | Full implementation (~2,500-3,500 lines) |
| `fmcg_example/postgres/seed.sql` | Generated output (overwritten by script) |
| `pyproject.toml` | Add numpy, faker if missing |
| `Makefile` | Add `fmcg-generate` target |
| `CHANGELOG.md` | Document Phase 4 completion |

## Success Criteria

1. **Row Counts**: ~7.5M total rows (±10%)
2. **Referential Integrity**: All FKs valid, no constraint violations
3. **Named Entities**: All 9 problem nodes present and queryable
4. **Pareto**: Top 20% SKUs = 80% order volume (verify with `validate_realism.sql`)
5. **Load Time**: `psql -f seed.sql` completes in <10 minutes
6. **Beast Mode Ready**: Schema supports all Phase 5 test queries

## Execution Approach

**Development order:**
1. Step 1 (CLI + setup): Foundation for iteration workflow
2. Steps 2-7 (Level generators): Build all 15 level generators
3. Step 8 (Validation suite): Enable fast iteration
4. Steps 9-10 (Output + integration): Final polish

**Iteration workflow (once implemented):**
```bash
# Initial development - validate as you build each level
python generate_data.py --validate-only

# Tuning loop (10-20 iterations)
# 1. Run validation, see what fails
# 2. Adjust parameters in code
# 3. Regenerate from affected level
python generate_data.py --from-level 8 --validate-only  # if order patterns wrong
python generate_data.py --from-level 14 --validate-only # if just OSA/KPIs wrong

# Final output (once all checks pass)
python generate_data.py --output fmcg_example/postgres/seed.sql

# Load to PostgreSQL (once)
psql -h localhost -p 5433 -U virt_graph -d prism_fmcg -f seed.sql
```

**Time budget:**
- Development: ~16 hours (Steps 1-10)
- Realism tuning: ~1 hour (10-20 iterations at ~3 min average)
- Final SQL load + verification: ~15 min
