# Plan: Expand Expert Reality Checks for CPG Validation

## Objective
Add four critical CPG supply chain KPIs to the validation suite, with industry-researched benchmarks.

## Research-Backed Benchmarks

| Metric | World-Class | Industry Avg | Our Target | Source |
|--------|-------------|--------------|------------|--------|
| OEE | 85% | 60-65% (FMCG: 70-80%) | 65-85% | Evocon, Worximity |
| Inventory Turns | 8-12x | P&G: 5.45x | 5-12x | GuruFocus |
| Forecast MAPE | <20% | 48% at SKU-week | 25-50% | E2Open study |
| Cost-to-Serve | — | $1.58/case | $1.00-$3.00/case | BCG |

---

## Phase 1: OEE (Overall Equipment Effectiveness)

### Formula
```
OEE = Availability × Quality
(Simplified: skip Performance since we don't track line speed)
```

### Data Available
- `work_orders`: `planned_start_date`, `actual_start_datetime`, `planned_quantity_kg`, `actual_quantity_kg`, `status`
- `batches`: `yield_percent`, `qc_status` (approved/rejected)

### Implementation

**1.1 Create OEEAccumulator class** (`realism_monitor.py`)
```python
@dataclass
class OEEAccumulator:
    """Tracks simplified OEE = Availability × Quality."""
    scheduled_runs: int = 0
    completed_runs: int = 0  # Availability numerator
    total_batches: int = 0
    approved_batches: int = 0  # Quality numerator

    @property
    def availability(self) -> float:
        return self.completed_runs / self.scheduled_runs if self.scheduled_runs > 0 else 0.0

    @property
    def quality(self) -> float:
        return self.approved_batches / self.total_batches if self.total_batches > 0 else 0.0

    @property
    def oee(self) -> float:
        return self.availability * self.quality
```

**1.2 Update `_check_work_orders()`** - Track availability
```python
# Count scheduled vs completed work orders
if row.get("status") in ("completed", "closed"):
    self._oee.completed_runs += 1
self._oee.scheduled_runs += 1
```

**1.3 Update `_check_batches()`** - Track quality
```python
self._oee.total_batches += 1
if row.get("qc_status") == "approved":
    self._oee.approved_batches += 1
```

**1.4 Add to manifest** (`benchmark_manifest.json`)
```json
"oee_range": [0.65, 0.85]
```

**1.5 Add validation in `check_benchmarks()`**

**1.6 Add to `get_reality_report()` and `_print_benchmark_comparison()`**

---

## Phase 2: Inventory Turns

### Formula
```
Inventory Turns = Annual COGS / Average Inventory Value
```

### Data Available
- `inventory`: `quantity_cases`, `location_type`
- Manifest already has `inventory_turns_range: [6.0, 14.0]` but NOT validated!
- Need to proxy COGS from shipment volume

### Implementation

**2.1 Create InventoryTurnsAccumulator** (`realism_monitor.py`)
```python
@dataclass
class InventoryTurnsAccumulator:
    """Tracks inventory velocity."""
    sum_inventory_cases: float = 0.0
    inventory_snapshots: int = 0
    sum_shipped_cases: float = 0.0  # Proxy for COGS

    @property
    def avg_inventory(self) -> float:
        return self.sum_inventory_cases / self.inventory_snapshots if self.inventory_snapshots > 0 else 1.0

    @property
    def turns(self) -> float:
        # Annualized: assume data represents ~1 year
        return self.sum_shipped_cases / self.avg_inventory if self.avg_inventory > 0 else 0.0
```

**2.2 Update `_check_inventory()`** - Track inventory levels
```python
qty = row.get("quantity_cases", 0)
self._inventory_turns.sum_inventory_cases += qty
self._inventory_turns.inventory_snapshots += 1
```

**2.3 Update `_check_shipments()`** - Track outbound volume (COGS proxy)
```python
cases = row.get("total_cases", 0)
self._inventory_turns.sum_shipped_cases += cases
```

**2.4 Manifest already has tolerance** - Just need to validate it

**2.5 Add validation in `check_benchmarks()`** using existing `inventory_turns_range`

---

## Phase 3: Forecast MAPE

### Formula
```
MAPE = Mean(|Forecast - Actual| / Actual) × 100%
```

### Data Available
- `demand_forecasts`: `forecast_quantity_cases`, `sku_id`, `forecast_week`
- `forecast_accuracy`: `forecast_quantity`, `actual_quantity` (compute MAPE fresh, don't use pre-calculated)
- Current `forecast_bias_max: 2000` is a fake check

### Implementation

**3.1 Create ForecastMAPEAccumulator** (`realism_monitor.py`)
```python
@dataclass
class ForecastMAPEAccumulator:
    """Tracks forecast accuracy via MAPE."""
    sum_ape: float = 0.0
    count: int = 0

    def update(self, forecast: float, actual: float) -> None:
        if actual > 0:
            ape = abs(forecast - actual) / actual
            self.sum_ape += ape
            self.count += 1

    @property
    def mape_pct(self) -> float:
        return (self.sum_ape / self.count * 100) if self.count > 0 else 0.0
```

**3.2 Add `_check_forecast_accuracy()` method** - New table handler
```python
def _check_forecast_accuracy(self, batch: list[dict]) -> None:
    for row in batch:
        forecast = row.get("forecast_quantity", 0)
        actual = row.get("actual_quantity", 0)
        if actual > 0:
            self._forecast_mape.update(forecast, actual)
```

**3.3 Route `forecast_accuracy` table in `observe_batch()`**

**3.4 Add to manifest** (`benchmark_manifest.json`)
```json
"mape_range": [0.20, 0.50]  // 20-50% MAPE (realistic for CPG)
```

**3.5 Add validation in `check_benchmarks()`**

**3.6 Update `generate_data.py` to feed `forecast_accuracy` to monitor**

---

## Phase 4: Cost-to-Serve

### Formula
```
Cost-to-Serve = Total Freight Cost / Total Cases Shipped
```

### Data Available
- `shipments`: `freight_cost`, `total_cases`
- `shipment_legs`: `freight_cost` (per leg)

### Implementation

**4.1 Create CostToServeAccumulator** (`realism_monitor.py`)
```python
@dataclass
class CostToServeAccumulator:
    """Tracks logistics cost per case."""
    sum_freight_cost: float = 0.0
    sum_cases: float = 0.0
    costs: list = field(default_factory=list)  # For distribution analysis

    def update(self, freight_cost: float, cases: float) -> None:
        if cases > 0 and freight_cost > 0:
            self.sum_freight_cost += freight_cost
            self.sum_cases += cases
            self.costs.append(freight_cost / cases)

    @property
    def cost_per_case(self) -> float:
        return self.sum_freight_cost / self.sum_cases if self.sum_cases > 0 else 0.0

    @property
    def cost_p90_p50_ratio(self) -> float:
        """Check for long-tail (expensive rural deliveries)."""
        if len(self.costs) < 10:
            return 1.0
        sorted_costs = sorted(self.costs)
        p50 = sorted_costs[len(sorted_costs) // 2]
        p90 = sorted_costs[int(len(sorted_costs) * 0.9)]
        return p90 / p50 if p50 > 0 else 1.0
```

**4.2 Update `_check_shipments()`**
```python
freight = row.get("freight_cost", 0)
cases = row.get("total_cases", 0)
if freight > 0 and cases > 0:
    self._cost_to_serve.update(freight, cases)
```

**4.3 Add to manifest** (`benchmark_manifest.json`)
```json
"cost_per_case_range": [1.00, 3.00],
"cost_variance_max_ratio": 4.0  // P90/P50 should be < 4x
```

**4.4 Add validation in `check_benchmarks()`**

---

## Files to Modify

| File | Changes |
|------|---------|
| `realism_monitor.py` | Add 4 accumulator classes, update `__init__`, add/update check methods, update `check_benchmarks()`, update `get_reality_report()`, update `reset()` |
| `benchmark_manifest.json` | Add `oee_range`, `mape_range`, `cost_per_case_range`, `cost_variance_max_ratio` |
| `generate_data.py` | Add `forecast_accuracy` to monitored tables, update `_print_benchmark_comparison()` |

---

## Validation Output (Expected)

```
Expert Reality Checks:
  Schedule Adherence     1.004    [<1.1]       PASS
  Truck Fill Rate        56.7%    [50%-100%]   PASS
  SLOB Inventory         25.1%    [<30%]       PASS
  OEE                    72.3%    [65%-85%]    PASS    <- NEW
  Inventory Turns        8.2x     [5-12x]      PASS    <- NEW
  Forecast MAPE          34.5%    [20%-50%]    PASS    <- NEW
  Cost-to-Serve          $1.82    [$1-$3]      PASS    <- NEW
  Cost Variance (P90/P50) 2.4x    [<4x]        PASS    <- NEW
```

---

## Implementation Order

1. **OEE** - Uses existing table handlers, just need accumulator
2. **Cost-to-Serve** - Uses existing `_check_shipments()`, straightforward
3. **Inventory Turns** - Uses existing handlers, manifest tolerance exists
4. **Forecast MAPE** - Needs new table routing for `forecast_accuracy`

---

## Test Strategy

After implementation:
1. Run `make fmcg-validate`
2. Verify all 8 structural + all realism checks pass
3. Verify new metrics show reasonable values within tolerances
4. Check that chaos injection doesn't break the new metrics unexpectedly
