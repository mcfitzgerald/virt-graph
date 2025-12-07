# Estimator API Reference

This reference documents the estimator module for intelligent graph size estimation and runtime guards.

## Overview

The estimator module prevents over-estimation that would block valid queries, while still protecting against dangerous traversals:

```
┌─────────────────┐     ┌───────────────┐     ┌─────────────────┐
│  GraphSampler   │ ──► │   estimate()  │ ──► │  check_guards() │
│  (sample graph) │     │ (extrapolate) │     │ (decide action) │
└─────────────────┘     └───────────────┘     └─────────────────┘
```

---

## Module Structure

```
virt_graph.estimator/
├── sampler.py   # GraphSampler, SampleResult
├── models.py    # EstimationConfig, estimate()
├── bounds.py    # TableStats, get_table_bound()
└── guards.py    # GuardResult, check_guards()
```

---

## Sampler Module (`virt_graph.estimator.sampler`)

### `SampleResult`

```python
@dataclass
class SampleResult:
    """Results from graph sampling with auto-detected properties."""

    # Basic metrics
    visited_count: int          # Nodes visited during sampling
    level_sizes: list[int]      # Nodes at each depth level
    terminated: bool            # Hit empty frontier before depth limit

    # Auto-detected properties
    growth_trend: Literal["increasing", "stable", "decreasing"]
    convergence_ratio: float    # visited/edges (1.0 = tree, <1 = DAG)
    has_cycles: bool            # Possible cycles detected

    # Hub detection
    max_expansion_factor: float # Largest level-to-level jump
    hub_detected: bool          # expansion > threshold

    # Raw data
    edges_seen: int             # Total edges encountered
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `visited_count` | `int` | Nodes visited during sampling |
| `level_sizes` | `list[int]` | Node count at each depth |
| `terminated` | `bool` | True if frontier became empty |
| `growth_trend` | `str` | `"increasing"`, `"stable"`, or `"decreasing"` |
| `convergence_ratio` | `float` | 1.0 = tree structure, <1 = DAG with sharing |
| `has_cycles` | `bool` | Detected potential cycles |
| `max_expansion_factor` | `float` | Largest jump between levels |
| `hub_detected` | `bool` | True if expansion > threshold |
| `edges_seen` | `int` | Total edges encountered |

---

### `GraphSampler`

```python
class GraphSampler:
    """
    Samples a graph structure and detects properties automatically.

    Use this to make informed decisions about traversal strategy
    before committing to a full traversal.
    """
```

#### Constructor

```python
def __init__(
    self,
    conn: PgConnection,
    edges_table: str,
    from_col: str,
    to_col: str,
    direction: str = "outbound",
    hub_threshold: float = 50.0,
)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `conn` | `PgConnection` | - | Database connection |
| `edges_table` | `str` | - | Edge table name |
| `from_col` | `str` | - | Source column |
| `to_col` | `str` | - | Target column |
| `direction` | `str` | `"outbound"` | `"outbound"`, `"inbound"`, or `"both"` |
| `hub_threshold` | `float` | `50.0` | Expansion factor threshold for hub detection |

---

#### `sample()`

```python
def sample(self, start_id: int, depth: int = 5) -> SampleResult
```

Sample graph and detect properties automatically.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `start_id` | `int` | - | Starting node ID |
| `depth` | `int` | `5` | Number of levels to sample |

**Returns:** `SampleResult` with detected properties.

**Example:**

```python
from virt_graph.estimator import GraphSampler

sampler = GraphSampler(
    conn,
    edges_table="bill_of_materials",
    from_col="parent_part_id",
    to_col="child_part_id",
    direction="outbound",
)
sample = sampler.sample(start_part_id, depth=5)

print(f"Visited: {sample.visited_count} nodes")
print(f"Terminated: {sample.terminated}")
print(f"Growth trend: {sample.growth_trend}")
print(f"Convergence ratio: {sample.convergence_ratio:.2f}")
print(f"Hub detected: {sample.hub_detected}")
```

---

## Models Module (`virt_graph.estimator.models`)

### `EstimationConfig`

```python
@dataclass
class EstimationConfig:
    """Configuration for estimation behavior."""

    # Damping parameters
    base_damping: float = 0.85
    convergence_multiplier: float = 0.8
    decreasing_trend_multiplier: float = 0.7

    # Safety parameters
    safety_margin: float = 1.2
    min_safety_margin: float = 1.05

    # Sampling parameters
    sample_depth: int = 5

    # Thresholds
    convergence_threshold: float = 0.95
    stable_growth_threshold: float = 0.2
```

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `base_damping` | `float` | 0.85 | Universal damping baseline |
| `convergence_multiplier` | `float` | 0.8 | Extra damping for convergent graphs |
| `decreasing_trend_multiplier` | `float` | 0.7 | Extra damping for shrinking frontiers |
| `safety_margin` | `float` | 1.2 | Multiply estimate by this |
| `min_safety_margin` | `float` | 1.05 | Minimum margin for terminated graphs |
| `sample_depth` | `int` | 5 | Levels to sample |
| `convergence_threshold` | `float` | 0.95 | Below this, apply convergence damping |
| `stable_growth_threshold` | `float` | 0.2 | Growth rate change threshold |

**Example:**

```python
from virt_graph.estimator import EstimationConfig

# Conservative config (less likely to allow large traversals)
conservative = EstimationConfig(
    base_damping=0.7,
    safety_margin=1.5,
)

# Aggressive config (more permissive)
aggressive = EstimationConfig(
    base_damping=0.9,
    safety_margin=1.1,
)
```

---

### `estimate()`

```python
def estimate(
    sample: SampleResult,
    max_depth: int,
    table_bound: int | None = None,
    config: EstimationConfig | None = None,
) -> int
```

Estimate reachable nodes with configurable model.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `sample` | `SampleResult` | - | Results from `GraphSampler.sample()` |
| `max_depth` | `int` | - | Maximum depth of planned traversal |
| `table_bound` | `int \| None` | `None` | Upper bound from table size |
| `config` | `EstimationConfig \| None` | `None` | Custom estimation config |

**Returns:** Estimated number of reachable nodes.

**Example:**

```python
from virt_graph.estimator import GraphSampler, estimate, EstimationConfig

sampler = GraphSampler(conn, "bill_of_materials", "parent_part_id", "child_part_id")
sample = sampler.sample(start_id, depth=5)

# Default estimation
est = estimate(sample, max_depth=20)

# With table bound cap
est_capped = estimate(sample, max_depth=20, table_bound=5000)

# Custom config
config = EstimationConfig(base_damping=0.7, safety_margin=1.5)
est_conservative = estimate(sample, max_depth=20, config=config)
```

---

## Bounds Module (`virt_graph.estimator.bounds`)

### `TableStats`

```python
@dataclass
class TableStats:
    """DDL-derived table statistics."""

    row_count: int               # Total rows in table
    is_junction: bool            # Composite PK (M:M pattern)
    has_self_ref: bool           # Self-referencing FK
    has_no_self_ref_constraint: bool  # CHECK constraint
    indexed_columns: list[str]   # Columns with indexes
    unique_from_nodes: int | None  # Distinct values in from column
    unique_to_nodes: int | None    # Distinct values in to column
    density: float | None        # edges/nodes^2 if calculable
```

---

### `get_table_stats()`

```python
def get_table_stats(
    conn: PgConnection,
    table: str,
    from_col: str | None = None,
    to_col: str | None = None,
) -> TableStats
```

Introspect DDL via information_schema and pg_stat.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `table` | `str` | Table name |
| `from_col` | `str \| None` | Edge source column |
| `to_col` | `str \| None` | Edge target column |

**Returns:** `TableStats` with DDL-derived properties.

---

### `get_table_bound()`

```python
def get_table_bound(
    conn: PgConnection,
    edges_table: str,
    from_col: str,
    to_col: str,
) -> int
```

Get absolute upper bound from unique nodes in table.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `conn` | `PgConnection` | Database connection |
| `edges_table` | `str` | Edge table name |
| `from_col` | `str` | Source column |
| `to_col` | `str` | Target column |

**Returns:** Upper bound on reachable nodes.

**Example:**

```python
from virt_graph.estimator import get_table_bound

bound = get_table_bound(
    conn,
    edges_table="bill_of_materials",
    from_col="parent_part_id",
    to_col="child_part_id",
)
print(f"Max reachable nodes: {bound}")
```

---

### `get_cardinality_stats()`

```python
def get_cardinality_stats(
    conn: PgConnection,
    edges_table: str,
    from_col: str,
    to_col: str,
) -> dict[str, float]
```

Get cardinality statistics for edges.

**Returns:**

```python
{
    "avg_out_degree": 2.5,
    "max_out_degree": 15,
    "avg_in_degree": 2.5,
    "max_in_degree": 8,
}
```

---

## Guards Module (`virt_graph.estimator.guards`)

### `GuardResult`

```python
@dataclass
class GuardResult:
    """Result of runtime guard checks."""

    safe_to_proceed: bool
    recommended_action: Literal[
        "traverse",
        "aggregate",
        "switch_networkx",
        "abort",
        "warn_and_proceed",
    ]
    reason: str | None
    estimated_nodes: int | None
    warnings: list[str]
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `safe_to_proceed` | `bool` | Whether traversal is safe |
| `recommended_action` | `str` | What to do next |
| `reason` | `str \| None` | Explanation |
| `estimated_nodes` | `int \| None` | Estimated size |
| `warnings` | `list[str]` | Non-fatal warnings |

**Recommended Actions:**

| Action | Description |
|--------|-------------|
| `traverse` | Safe to proceed with BFS |
| `aggregate` | Use COUNT instead of full traversal |
| `switch_networkx` | Load to NetworkX for algorithm |
| `abort` | Too large, require filter |
| `warn_and_proceed` | Over limit but can proceed |

---

### `check_guards()`

```python
def check_guards(
    sample: SampleResult,
    max_depth: int,
    max_nodes: int = 10_000,
    stats: TableStats | None = None,
    table_bound: int | None = None,
    estimation_config: EstimationConfig | None = None,
) -> GuardResult
```

Runtime decision logic for traversal safety.

**Checks performed:**

1. **Scout Check**: Hub detected? → Abort
2. **Structure Check**: Junction table? → Aggregate instead
3. **Volume Check**: Estimate vs limits

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `sample` | `SampleResult` | - | Results from GraphSampler |
| `max_depth` | `int` | - | Maximum traversal depth |
| `max_nodes` | `int` | 10,000 | Node limit |
| `stats` | `TableStats \| None` | `None` | Optional table stats |
| `table_bound` | `int \| None` | `None` | Optional upper bound |
| `estimation_config` | `EstimationConfig \| None` | `None` | Optional config |

**Returns:** `GuardResult` with recommendation.

**Example:**

```python
from virt_graph.estimator import GraphSampler, check_guards, get_table_bound

sampler = GraphSampler(conn, "bill_of_materials", "parent_part_id", "child_part_id")
sample = sampler.sample(start_id)
table_bound = get_table_bound(conn, "bill_of_materials", "parent_part_id", "child_part_id")

result = check_guards(
    sample,
    max_depth=20,
    max_nodes=10_000,
    table_bound=table_bound,
)

if result.safe_to_proceed:
    print(f"Safe to traverse: ~{result.estimated_nodes} nodes")
    # proceed with traversal
else:
    print(f"Blocked: {result.reason}")
    print(f"Recommended action: {result.recommended_action}")

# Check warnings
for warning in result.warnings:
    print(f"Warning: {warning}")
```

---

### `should_use_networkx()`

```python
def should_use_networkx(
    sample: SampleResult,
    stats: TableStats | None = None,
    algorithm: str | None = None,
) -> tuple[bool, str | None]
```

Determine if NetworkX should be used instead of SQL-based traversal.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `sample` | `SampleResult` | Sampling results |
| `stats` | `TableStats \| None` | Optional table stats |
| `algorithm` | `str \| None` | Algorithm being used |

**Returns:** Tuple of `(should_use_networkx, reason)`.

---

## Integration with Handlers

The estimator module integrates with traversal handlers via configurable parameters:

### Handler Parameters

```python
def traverse(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    start_id,
    direction="outbound",
    max_depth=10,
    # ... other params ...

    # Configurable limits
    max_nodes: int | None = None,         # Override default 10,000
    skip_estimation: bool = False,         # Bypass size check
    estimation_config: EstimationConfig | None = None,
) -> dict[str, Any]
```

### Usage Patterns

```python
from virt_graph.handlers import traverse, bom_explode
from virt_graph.estimator import EstimationConfig

# Normal usage (improved estimation)
result = bom_explode(conn, part_id)

# Override limit for known-bounded graph
result = bom_explode(conn, part_id, max_nodes=50_000)

# Skip estimation (caller takes responsibility)
result = bom_explode(conn, part_id, skip_estimation=True)

# Custom estimation config
config = EstimationConfig(
    base_damping=0.7,
    safety_margin=1.5,
)
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,
    estimation_config=config,
)
```

---

## Error Messages

The improved estimator provides actionable error messages:

**Before (v0.7.x):**
```
SubgraphTooLarge: Query would touch ~21,365 nodes (limit: 10,000).
Consider adding filters or reducing depth.
```

**After (v0.8.0):**
```
SubgraphTooLarge: Query would touch ~2,500 nodes (limit: 10,000).
Consider: max_nodes=N to increase limit, or skip_estimation=True to bypass.
```

---

## Import Shortcuts

```python
from virt_graph.estimator import (
    # Sampler
    GraphSampler,
    SampleResult,
    # Models
    EstimationConfig,
    estimate,
    # Bounds
    TableStats,
    get_table_stats,
    get_table_bound,
    get_cardinality_stats,
    # Guards
    GuardResult,
    check_guards,
    should_use_networkx,
)
```

---

## See Also

- [Handlers API Reference](handlers.md) - Handler function signatures
- [Ontology API Reference](ontology.md) - Schema mapping
