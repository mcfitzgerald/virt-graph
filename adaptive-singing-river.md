# Plan: Realistic Supply Chain Data Generation

## Summary

Address the "Potemkin Village" vs "Ant Colony" feedback by introducing **imbalance** and **realistic patterns** into the data generator. The goal is to make synthetic data pass both static analysis (schema correctness) AND dynamic stress tests (domain expert scrutiny).

## Research Findings (2024-2025 Benchmarks)

| Metric | Industry Average | World Class | Current State |
|--------|------------------|-------------|---------------|
| OEE | 60-66% | 85%+ | Fixed 85% |
| Inventory Turns | 4-8 (mfg), 5-10 (electronics) | 10+ | Not validated |
| Perfect Order Rate | 80-85% | 95%+ | ~100% (too perfect) |
| Pareto Distribution | Top 20% = 80% revenue | - | Uniform random |

**Sources**: [Evocon OEE Report](https://evocon.com/world-class-oee-report/), [NetSuite 80/20 Rule](https://www.netsuite.com/portal/resource/articles/inventory-management/80-20-inventory-rule.shtml), [ASCM SCOR-DS](https://scor.ascm.org/)

---

## Implementation Plan

### Phase 1: Schema Changes

**File**: `supply_chain_example/postgres/01_schema.sql`

Add `kpi_targets` table for SCOR Orchestrate domain:
```sql
CREATE TABLE kpi_targets (
    id SERIAL PRIMARY KEY,
    kpi_name VARCHAR(100) NOT NULL,
    kpi_category VARCHAR(50) CHECK (kpi_category IN ('delivery', 'quality', 'cost', 'inventory', 'production')),
    target_value DECIMAL(12, 4) NOT NULL,
    target_unit VARCHAR(20) NOT NULL,
    threshold_warning DECIMAL(12, 4),
    threshold_critical DECIMAL(12, 4),
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,
    product_id INTEGER REFERENCES products(id),
    facility_id INTEGER REFERENCES facilities(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### Phase 2: Data Generator Changes

Note: we already made a change to the current data generator to use COPY format for faster bulk loading given 
size of data (~600MB) versus original small files. Shouldn't impact what you are doing, but keep in mind.

**File**: `supply_chain_example/scripts/generate_data.py`

#### 2.1 Add numpy for distributions
```python
import numpy as np
np.random.seed(42)
```

#### 2.2 Pareto/Zipf Distribution for Orders (~line 924)
- Replace `random.choice(product_ids)` with Zipf-weighted selection
- Top 20% of products will receive ~80% of order volume
- Track `self.popular_product_ids` for later use

#### 2.3 Scale-Free Supplier Network (~line 263)
- Replace tier-based random connections with Barabási-Albert preferential attachment
- New suppliers connect preferentially to already well-connected suppliers
- Creates "super hub" suppliers naturally
- Track `self.super_hub_supplier_ids`

#### 2.4 "Supplier from Hell" (~line 258)
- Create one named T2 supplier "Reliable Parts Co" with:
  - 50% late deliveries in PO generation
  - Poor credit rating (BB)
  - Long lead times (45-90 days vs 14-60 normal)
- Track as `self.supplier_from_hell_id`

#### 2.5 Deep Aerospace BOM (~line 520)
- Add 22-level deep BOM hierarchy for "Aerospace" product line
- ~66 aerospace parts (3 per level × 22 levels)
- **True cycle design** (A→B→C→A closed loop, not just back-edge):
  ```
  AERO-L21 (top assembly)
      ↓ uses
  PACK-BOX-A1 (packing material)
      ↓ made from
  RECYC-CARD-A1 (recycled cardboard)
      ↓ sourced from scraps of
  AERO-L21 ← TRUE CYCLE back to top
  ```
- Cycle handled by existing `NOT ... = ANY(p.path)` in CTE
- Tests SQL WITH RECURSIVE limits AND cycle detection
- **Benchmark talking point**: "SQL requires explicit cycle management vs Neo4j automatic detection"

#### 2.6 OEE Distribution (~line 1190)
- Replace fixed 85% efficiency with realistic distribution:
  - 10% poor performers (40-55% OEE) - `self.problem_work_center_ids`
  - 15% below average (55-65%)
  - 60% average (60-72%)
  - 15% world-class (80-92%)
- Add 3 named "problem" work centers

#### 2.7 Perfect Order Metric (~line 1005)
- Make 18% of orders ship AFTER `required_date` (late)
- Enables Perfect Order calculation: ~82% (industry average)

#### 2.8 Temporal Route Flickering (~line 769)
- 10% of transport routes are "seasonal" (active 3 months/year)
- Add `seasonal_months` field or encode in `route_status`
- Enables time-aware path queries: "Find route from A to B on date X"

#### 2.9 Lumpy Demand (~line 1763)
- Add Gaussian noise to sine wave seasonality (σ = 15%)
- 5% chance of 2-3x demand spike per forecast period
- Ensures demand > capacity for at least one product line (bottleneck)

#### 2.10 KPI Targets Generation (new method)
- Generate 14 standard supply chain KPIs:
  - Delivery: OTD (95%), Perfect Order (85%), Fill Rate (98%)
  - Quality: First Pass Yield (95%), Scrap Rate (<2%)
  - Inventory: Turns (6), Days (60), Accuracy (99%)
  - Production: OEE (85%), Utilization (80%)
- Product-specific targets for premium items

---

### Phase 3: Validation Queries
 
**File**: `supply_chain_example/scripts/validate_realism.sql` (new)

SQL queries to verify benchmarks after data generation:
1. Pareto check: Top 20% products = ~80% revenue
2. OEE distribution: Average 60-66%, outliers exist
3. Perfect Order Rate: ~82%
4. Scale-free network: Hub suppliers have 10x median connections
5. BOM depth: Max >= 22 levels
6. Inventory turns: 4-8 range
7. **Cycle detection test**: Query Aerospace BOM without `NOT ... = ANY(path)` should timeout; with it should complete in <1s

---

### Phase 4: Benchmark Questions

**File**: `supply_chain_example/questions.md`

Add Q86-Q108 to validate new patterns:
- Q86-88: Pareto/power law validation
- Q89-91: OEE benchmarks
- Q92-94: Inventory turns
- Q95-97: Perfect Order metric
- Q98-100: Scale-free network
- Q101-103: Deep BOM / cycles
- Q104-105: Temporal connectivity
- Q106-107: Capacity bottlenecks
- Q108: Supplier from Hell

---

### Phase 5: Documentation

**Files**: `CHANGELOG.md`, `TODO.md`, `pyproject.toml`

- Version bump to 0.9.16
- Document all new patterns and validation queries
- Update TODO.md with completion status

---

## Files to Modify

| File | Changes |
|------|---------|
| `supply_chain_example/postgres/01_schema.sql` | Add `kpi_targets` table |
| `supply_chain_example/scripts/generate_data.py` | All distribution/pattern changes |
| `supply_chain_example/scripts/validate_realism.sql` | New validation queries |
| `supply_chain_example/questions.md` | Add Q86-Q108 |
| `supply_chain_example/ontology/supply_chain.yaml` | Add KpiTarget class |
| `CHANGELOG.md` | Document v0.9.16 |
| `TODO.md` | Mark complete |
| `pyproject.toml` | Add numpy dependency, bump version |

---

## Implementation Order

**Phase A: Dependencies**
1. Add numpy to pyproject.toml
2. Run `poetry lock && poetry install`

**Phase B: Schema**
3. Add kpi_targets table to `01_schema.sql`
4. Check docker-compose.yml volume handling

**Phase C: Data Generator** (`generate_data.py`)
5. Add numpy import and helper functions (zipf_sample, preferential attachment)
6. Implement Pareto orders (most impactful change)
7. Implement scale-free supplier network (Barabási-Albert)
8. Add "Supplier from Hell" (50% late, poor rating)
9. Create deep Aerospace BOM (22 levels + recycling cycle)
10. OEE distribution (10% poor, avg 60-66%)
11. Perfect Order (18% late deliveries)
12. Temporal routes (10% seasonal)
13. Lumpy demand (noise + spikes + bottleneck)
14. KPI targets generation

**Phase D: Regenerate & Validate**
15. Run `python generate_data.py` → new seed.sql
16. Run `make db-reset` (nukes and recreates DB)
17. Run validation queries to verify benchmarks

**Phase E: Documentation**
18. Add benchmark questions Q86-Q108
19. Create validate_realism.sql script
20. Update CHANGELOG.md (v0.9.16)
21. Update TODO.md with completion status
22. Commit with semantic version bump

---

## Estimated Impact

| Pattern | New Row Count | Impact |
|---------|---------------|--------|
| Aerospace BOM | +5,000 BOM entries | Tests recursive depth |
| Aerospace Products | +3 products | Named test entities |
| KPI Targets | +20 rows | SCOR Orchestrate domain |
| Total | ~+5,025 rows | <1% increase |

Distribution changes (Pareto, OEE, etc.) modify existing data patterns without adding rows.

---

## Backward Compatibility

- All existing Q1-Q85 queries remain valid
- Named entities unchanged (Acme Corp, Turbo Encabulator, etc.)
- Same seed (42) ensures reproducibility
- Schema is additive (new table, no column changes to existing)

---

## Resolved Questions

1. **numpy dependency**: ✅ Add numpy (user confirmed)
2. **Full implementation**: ✅ All items, not just quick wins
3. **Cycle handling**: ✅ Current handlers already handle cycles safely:
   - `traverse()`: Uses `visited` set - nodes visited once via shortest path
   - `path_aggregate()`: CTE uses `NOT ... = ANY(p.path)` to prevent re-visiting
   - No code changes needed - recycled materials cycle will work correctly

## Migration Approach

✅ **Fresh implementation** - Nuke existing DB and recreate from scratch:
1. Update schema (01_schema.sql)
2. Update data generator (generate_data.py)
3. Regenerate seed.sql
4. Check docker-compose.yml for volume handling
5. Run `make db-reset` to recreate with new data
