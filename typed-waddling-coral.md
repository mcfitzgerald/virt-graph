# Plan: Multi-Promo Lift Generation System

## Overview

Enhance the FMCG data generator to apply promotional lift effects for **all 100 promotions** throughout the year, not just Black Friday. Each promotion affects specific SKUs at specific retail accounts during its active date range.

**Current State**: 100 promotions exist with dates, but only Black Friday (week 48) affects POS demand.

**Goal**: All promotions affect demand with account-level targeting while maintaining vectorized performance.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Overlapping promos | **Max lift** | Take highest lift when multiple promos overlap for same SKU |
| Account targeting | **Account-level** | Use promotion_accounts table - different retailers have different promo calendars |
| Performance target | **<3 seconds** | Currently ~1s for 500K rows, allow 2x overhead for multi-promo |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    PromoCalendar (New Module)                     │
│                                                                   │
│  Input:                                                          │
│  ├── promotions (100 records with dates, lift_multiplier)        │
│  ├── promotion_skus (2,587 links: promo → SKUs)                  │
│  └── promotion_accounts (2,000 links: promo → retail accounts)   │
│                                                                   │
│  Index Structure:                                                 │
│  └── (week, sku_id, account_id) → PromoEffect                    │
│                                                                   │
│  Output: Vectorized lookup for 500K POS sales                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    POSSalesGenerator (Modified)                   │
│                                                                   │
│  For each sale:                                                  │
│  1. Get week from sale_date                                      │
│  2. Get account_id from location → retail_locations.account_id  │
│  3. Lookup promo effect: calendar.get(week, sku_id, account_id) │
│  4. Apply lift_multiplier to base demand                         │
│  5. Set promo_id and is_promotional flag                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `data_generation/promo_calendar.py` | **Create** | PromoCalendar class with vectorized lookup |
| `data_generation/vectorized.py` | Modify | Update POSSalesGenerator for multi-promo |
| `data_generation/__init__.py` | Modify | Export PromoCalendar |
| `generate_data.py` | Modify | Build calendar at Level 8, pass to generator |
| `CHANGELOG.md` | Update | Document v0.9.31 changes |

---

## Step 1: Create `promo_calendar.py` (~200 lines)

### 1.1 Data Structures

```python
@dataclass
class PromoEffect:
    """Promo effect for a (week, sku, account) combination."""
    promo_id: int
    lift_multiplier: float
    hangover_multiplier: float
    discount_percent: float | None
    is_hangover: bool = False

@dataclass
class PromoCalendar:
    """Pre-computed promo calendar for O(1) vectorized lookups."""

    # Core index: week -> account_id -> sku_id -> PromoEffect
    # Resolves overlaps by keeping max lift
    _index: dict[int, dict[int, dict[int, PromoEffect]]]

    # Lookup helpers for vectorization
    _location_to_account: dict[int, int]  # retail_location_id -> account_id
    _promo_weeks: set[int]  # All weeks with any promo activity
    _promo_sku_ids: set[int]  # All SKUs in any promo

    @classmethod
    def build(cls,
              promotions: list[dict],
              promotion_skus: list[dict],
              promotion_accounts: list[dict],
              retail_locations: list[dict]) -> "PromoCalendar":
        """Build calendar from promotion data."""
        ...
```

### 1.2 Build Algorithm

```python
def build(cls, promotions, promotion_skus, promotion_accounts, retail_locations):
    # Step 1: Build helper indices
    promo_to_skus = defaultdict(set)      # promo_id -> {sku_ids}
    promo_to_accounts = defaultdict(set)  # promo_id -> {account_ids}
    location_to_account = {}               # location_id -> account_id

    for ps in promotion_skus:
        promo_to_skus[ps["promo_id"]].add(ps["sku_id"])
    for pa in promotion_accounts:
        promo_to_accounts[pa["promo_id"]].add(pa["retail_account_id"])
    for loc in retail_locations:
        location_to_account[loc["id"]] = loc["retail_account_id"]

    # Step 2: Build week-indexed calendar
    index = defaultdict(lambda: defaultdict(dict))

    for promo in promotions:
        promo_id = promo["id"]
        start_week = date_to_week(promo["start_date"])
        end_week = date_to_week(promo["end_date"])
        lift = promo["lift_multiplier"]
        hangover_mult = promo.get("hangover_multiplier", 0.7)
        hangover_weeks_count = promo.get("hangover_weeks", 1)

        sku_ids = promo_to_skus.get(promo_id, set())
        account_ids = promo_to_accounts.get(promo_id, set())

        # Add promo weeks (with lift)
        for week in range(start_week, end_week + 1):
            for account_id in account_ids:
                for sku_id in sku_ids:
                    effect = PromoEffect(promo_id, lift, hangover_mult, ...)
                    _update_with_max_lift(index[week][account_id], sku_id, effect)

        # Add hangover weeks (with dip)
        for hw in range(1, hangover_weeks_count + 1):
            hangover_week = end_week + hw
            if hangover_week <= 52:
                for account_id in account_ids:
                    for sku_id in sku_ids:
                        # Only add hangover if no active promo exists
                        if sku_id not in index[hangover_week][account_id]:
                            effect = PromoEffect(promo_id, 1.0, hangover_mult, is_hangover=True)
                            index[hangover_week][account_id][sku_id] = effect

    return cls(_index=dict(index), _location_to_account=location_to_account, ...)
```

### 1.3 Vectorized Lookup

```python
def get_effects_vectorized(
    self,
    weeks: np.ndarray,        # (N,) int - week numbers
    sku_ids: np.ndarray,      # (N,) int64
    location_ids: np.ndarray  # (N,) int64 - retail_location_ids
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns: (lift_multipliers, hangover_multipliers, is_promotional, promo_ids)
    All arrays shape (N,)
    """
    n = len(weeks)
    lifts = np.ones(n, dtype=np.float32)
    hangovers = np.ones(n, dtype=np.float32)
    is_promo = np.zeros(n, dtype=bool)
    promo_ids = np.zeros(n, dtype=np.int64)

    # Vectorized account lookup
    account_ids = np.array([
        self._location_to_account.get(loc_id, 0)
        for loc_id in location_ids
    ], dtype=np.int64)

    # Process by unique weeks (reduces dict lookups)
    for week in np.unique(weeks):
        if week not in self._index:
            continue

        week_mask = weeks == week
        week_accounts = account_ids[week_mask]
        week_skus = sku_ids[week_mask]

        week_data = self._index[week]

        for i, (acc, sku) in enumerate(zip(week_accounts, week_skus)):
            if acc in week_data and sku in week_data[acc]:
                effect = week_data[acc][sku]
                idx = np.where(week_mask)[0][i]
                if effect.is_hangover:
                    hangovers[idx] = effect.hangover_multiplier
                else:
                    lifts[idx] = effect.lift_multiplier
                    is_promo[idx] = True
                    promo_ids[idx] = effect.promo_id

    return lifts, hangovers, is_promo, promo_ids
```

---

## Step 2: Modify POSSalesGenerator

### 2.1 Add PromoCalendar Support

```python
@dataclass
class POSSalesGenerator(VectorizedGenerator):
    # New: PromoCalendar for multi-promo support
    promo_calendar: PromoCalendar | None = None

    # Legacy fields (keep for backward compatibility)
    promo_sku_ids: set[int] = field(default_factory=set)
    promo_weeks: set[int] = field(default_factory=set)
    ...

    def configure(
        self,
        sku_ids: list[int] | np.ndarray,
        location_ids: list[int] | np.ndarray,
        sku_prices: dict[int, float] | None = None,
        promo_calendar: PromoCalendar | None = None,  # NEW
        # Legacy params...
    ) -> "POSSalesGenerator":
        ...
        self.promo_calendar = promo_calendar
```

### 2.2 Update generate_batch()

```python
def generate_batch(self, batch_size: int, promo_id: int | None = None) -> np.ndarray:
    ...
    # Generate base data (SKUs, locations, dates, quantities)
    batch = np.zeros(batch_size, dtype=POS_SALES_DTYPE)
    batch["sku_id"] = self._rng.choice(self.sku_ids, size=batch_size, p=self.sku_weights)
    batch["retail_location_id"] = self._rng.choice(self.location_ids, size=batch_size)

    # Generate dates and extract weeks
    weeks = self._rng.integers(1, 53, size=batch_size)
    batch["sale_date"] = self._generate_dates(weeks)

    # Generate base demand (lumpy)
    base_qty = lumpy_demand(self._rng, batch_size, mean=8.0, cv=0.4)

    if self.promo_calendar is not None:
        # NEW: Multi-promo path
        lifts, hangovers, is_promo, promo_ids = self.promo_calendar.get_effects_vectorized(
            weeks, batch["sku_id"], batch["retail_location_id"]
        )

        # Apply effects
        final_qty = (base_qty * lifts * hangovers).astype(np.int32)
        final_qty = np.maximum(final_qty, 1)

        batch["quantity_eaches"] = final_qty
        batch["is_promotional"] = is_promo
        batch["promo_id"] = promo_ids

    else:
        # Legacy: Single promo path (unchanged)
        ...existing code...

    # Calculate revenue with promo discount
    base_prices = np.array([self.sku_prices.get(s, 5.0) for s in batch["sku_id"]])
    discount_mask = batch["is_promotional"]
    prices = np.where(discount_mask, base_prices * 0.75, base_prices)  # 25% off
    batch["revenue"] = batch["quantity_eaches"] * prices

    return batch
```

---

## Step 3: Update generate_data.py Level 8

```python
def _generate_level_8(self) -> None:
    """Level 8: Demand signals and orders (LARGEST)."""
    print("  Level 8: Demand and orders (LARGEST - pos_sales, orders...)")
    level_start = time.time()

    # Build multi-promo calendar
    from data_generation import PromoCalendar

    promo_calendar = PromoCalendar.build(
        promotions=self.data["promotions"],
        promotion_skus=self.data["promotion_skus"],
        promotion_accounts=self.data["promotion_accounts"],
        retail_locations=self.data["retail_locations"],
    )

    promo_count = len(self.data["promotions"])
    promo_weeks = len(promo_calendar._promo_weeks)
    print(f"    [Promo] Built calendar: {promo_count} promos, {promo_weeks} active weeks")

    # Configure vectorized generator
    pos_gen = POSSalesGenerator(seed=self.seed)
    pos_gen.configure(
        sku_ids=sku_ids,
        location_ids=location_ids,
        sku_prices=sku_prices,
        promo_calendar=promo_calendar,  # Pass full calendar
    )

    # Generate 500K rows vectorized
    pos_sales_array = pos_gen.generate_batch(500000)
    pos_sales_dicts = structured_to_dicts(pos_sales_array)

    # Convert promo_id=0 to None
    for row in pos_sales_dicts:
        if row["promo_id"] == 0:
            row["promo_id"] = None

    self.data["pos_sales"] = pos_sales_dicts

    # Report promo distribution
    promo_sales = sum(1 for s in pos_sales_dicts if s.get("is_promotional"))
    unique_promos = len({s["promo_id"] for s in pos_sales_dicts if s.get("promo_id")})
    print(f"    [Promo] {promo_sales:,} promo sales across {unique_promos} unique promotions")
```

---

## Step 4: Update Validation

```python
def _validate_promo_distribution(self) -> tuple[bool, str]:
    """Validate multi-promo lift is working correctly."""
    pos = self.data.get("pos_sales", [])
    if not pos:
        return False, "No pos_sales data"

    # Check unique promos used
    used_promos = {s.get("promo_id") for s in pos if s.get("promo_id")}
    if len(used_promos) < 20:
        return False, f"Only {len(used_promos)} promos used (expected 50+)"

    # Check lift effect
    promo_sales = [s for s in pos if s.get("is_promotional")]
    non_promo_sales = [s for s in pos if not s.get("is_promotional")]

    if promo_sales and non_promo_sales:
        avg_promo = sum(s["quantity_eaches"] for s in promo_sales) / len(promo_sales)
        avg_non = sum(s["quantity_eaches"] for s in non_promo_sales) / len(non_promo_sales)
        lift = avg_promo / avg_non if avg_non > 0 else 0

        if lift >= 1.5:
            return True, f"Multi-promo active: {len(used_promos)} promos, {lift:.1f}x avg lift"
        return False, f"Weak lift: {lift:.1f}x"

    return True, f"{len(used_promos)} promos used"
```

---

## Step 5: Update Exports

```python
# In data_generation/__init__.py
from .promo_calendar import PromoCalendar, PromoEffect

__all__ = [
    ...existing exports...
    "PromoCalendar",
    "PromoEffect",
]
```

---

## Expected Output

After implementation, generation output should show:

```
  Level 8: Demand and orders (LARGEST - pos_sales, orders...)
    [Promo] Built calendar: 100 promos, 47 active weeks
    [Promo] 127,432 promo sales across 89 unique promotions
    Generated: 500000 pos_sales, 200000 orders, 100000 forecasts
    ⏱  2.34s (342,465 rows/sec)
```

---

## Validation Checks

| Check | Expected |
|-------|----------|
| Unique promos used | 50+ of 100 promos |
| Promo sales count | ~100K-150K of 500K (20-30%) |
| Average lift ratio | 1.5x - 2.5x vs non-promo |
| Week distribution | Promos spread across 40+ weeks |
| Account targeting | Different accounts have different promo mixes |

---

## Performance Budget

| Operation | Time Budget |
|-----------|-------------|
| Calendar build | <0.5s |
| Vectorized lookup (500K) | <1.5s |
| Dict conversion | <1.0s |
| **Total Level 8** | **<3.0s** |

---

## Success Criteria

1. All 100 promotions can affect POS demand
2. Account-level targeting works (MegaMart promos differ from Costco)
3. Overlapping promos resolved with max-lift
4. Hangover effects apply when no follow-on promo
5. Generation time <3 seconds for 500K rows
6. Validation passes with 50+ promos used
