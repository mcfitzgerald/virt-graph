# Estimator API Reference

::: virt_graph.estimator

The estimator module provides intelligent graph size estimation and runtime guards to prevent over-estimation and allow configurable limits.

## Module: `virt_graph.estimator.sampler`

### Classes

#### `SampleResult`

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

#### `GraphSampler`

```python
class GraphSampler:
    """
    Samples a graph structure and detects properties automatically.

    Use this to make informed decisions about traversal strategy
    before committing to a full traversal.
    """

    def __init__(
        self,
        conn: PgConnection,
        edges_table: str,
        from_col: str,
        to_col: str,
        direction: str = "outbound",
        hub_threshold: float = 50.0,
    ):
        """
        Initialize sampler.

        Args:
            conn: Database connection
            edges_table: Table containing edges
            from_col: Column for edge source
            to_col: Column for edge target
            direction: "outbound", "inbound", or "both"
            hub_threshold: Expansion factor threshold for hub detection
        """

    def sample(self, start_id: int, depth: int = 5) -> SampleResult:
        """
        Sample graph and detect properties automatically.

        Performs BFS for `depth` levels and collects metrics to
        characterize the graph structure.

        Args:
            start_id: Starting node ID
            depth: Number of levels to sample (default 5)

        Returns:
            SampleResult with detected properties
        """
```

### Usage Example

```python
from virt_graph.estimator import GraphSampler

# Sample BOM structure
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

## Module: `virt_graph.estimator.models`

### Classes

#### `EstimationConfig`

```python
@dataclass
class EstimationConfig:
    """Configuration for estimation behavior."""

    # Damping parameters
    base_damping: float = 0.85       # Universal damping baseline
    convergence_multiplier: float = 0.8  # Extra damping for convergent graphs
    decreasing_trend_multiplier: float = 0.7  # Extra damping for shrinking frontiers

    # Safety parameters
    safety_margin: float = 1.2       # Multiply estimate by this
    min_safety_margin: float = 1.05  # Minimum margin for terminated graphs

    # Sampling parameters
    sample_depth: int = 5            # Levels to sample

    # Thresholds
    convergence_threshold: float = 0.95  # Below this, apply convergence damping
    stable_growth_threshold: float = 0.2  # Growth rate change threshold
```

### Functions

#### `estimate()`

```python
def estimate(
    sample: SampleResult,
    max_depth: int,
    table_bound: int | None = None,
    config: EstimationConfig | None = None,
) -> int:
    """
    Estimate reachable nodes with configurable model.

    Uses sampling results and detected properties to produce
    an accurate estimate that won't over- or under-estimate.

    Args:
        sample: Results from GraphSampler.sample()
        max_depth: Maximum depth of planned traversal
        table_bound: Upper bound from table size (caps estimate)
        config: Estimation configuration

    Returns:
        Estimated number of reachable nodes
    """
```

### Usage Example

```python
from virt_graph.estimator import GraphSampler, estimate, EstimationConfig

sampler = GraphSampler(conn, "bill_of_materials", "parent_part_id", "child_part_id")
sample = sampler.sample(start_id, depth=5)

# Default estimation
est = estimate(sample, max_depth=20)

# With table bound cap
table_bound = 5000
est_capped = estimate(sample, max_depth=20, table_bound=table_bound)

# Custom config for conservative estimation
conservative = EstimationConfig(
    base_damping=0.7,
    safety_margin=1.5,
)
est_conservative = estimate(sample, max_depth=20, config=conservative)
```

---

## Module: `virt_graph.estimator.bounds`

### Classes

#### `TableStats`

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

### Functions

#### `get_table_stats()`

```python
def get_table_stats(
    conn: PgConnection,
    table: str,
    from_col: str | None = None,
    to_col: str | None = None,
) -> TableStats:
    """
    Introspect DDL via information_schema and pg_stat.

    Args:
        conn: Database connection
        table: Table name
        from_col: Optional edge source column
        to_col: Optional edge target column

    Returns:
        TableStats with DDL-derived properties
    """
```

#### `get_table_bound()`

```python
def get_table_bound(
    conn: PgConnection,
    edges_table: str,
    from_col: str,
    to_col: str,
) -> int:
    """
    Get absolute upper bound from unique nodes in table.

    This is the maximum possible nodes that could be reached
    by traversing all edges in the table.

    Args:
        conn: Database connection
        edges_table: Edge table name
        from_col: Source column
        to_col: Target column

    Returns:
        Upper bound on reachable nodes
    """
```

#### `get_cardinality_stats()`

```python
def get_cardinality_stats(
    conn: PgConnection,
    edges_table: str,
    from_col: str,
    to_col: str,
) -> dict[str, float]:
    """
    Get cardinality statistics for edges.

    Returns:
        Dict with avg_out_degree, max_out_degree, avg_in_degree, max_in_degree
    """
```

### Usage Example

```python
from virt_graph.estimator import get_table_bound, get_table_stats

# Get absolute upper bound
bound = get_table_bound(
    conn,
    edges_table="bill_of_materials",
    from_col="parent_part_id",
    to_col="child_part_id",
)
print(f"Max reachable nodes: {bound}")

# Get detailed stats
stats = get_table_stats(
    conn,
    table="bill_of_materials",
    from_col="parent_part_id",
    to_col="child_part_id",
)
print(f"Row count: {stats.row_count}")
print(f"Is junction table: {stats.is_junction}")
print(f"Unique parents: {stats.unique_from_nodes}")
print(f"Unique children: {stats.unique_to_nodes}")
```

---

## Module: `virt_graph.estimator.guards`

### Classes

#### `GuardResult`

```python
@dataclass
class GuardResult:
    """Result of runtime guard checks."""

    safe_to_proceed: bool       # Whether traversal is safe
    recommended_action: Literal[
        "traverse",             # Safe to proceed with BFS
        "aggregate",            # Use COUNT instead
        "switch_networkx",      # Load to NetworkX
        "abort",                # Too large, require filter
        "warn_and_proceed",     # Over limit but can proceed
    ]
    reason: str | None          # Explanation
    estimated_nodes: int | None # Estimated size
    warnings: list[str]         # Non-fatal warnings
```

### Functions

#### `check_guards()`

```python
def check_guards(
    sample: SampleResult,
    max_depth: int,
    max_nodes: int = 10_000,
    stats: TableStats | None = None,
    table_bound: int | None = None,
    estimation_config: EstimationConfig | None = None,
) -> GuardResult:
    """
    Runtime decision logic for traversal safety.

    Checks:
    1. Scout Check: Hub detected? -> Abort
    2. Structure Check: Junction table? -> Aggregate instead
    3. Volume Check: Estimate vs limits

    Args:
        sample: Results from GraphSampler
        max_depth: Maximum traversal depth
        max_nodes: Node limit (default 10,000)
        stats: Optional table stats
        table_bound: Optional upper bound from table
        estimation_config: Optional estimation config

    Returns:
        GuardResult with recommendation
    """
```

#### `should_use_networkx()`

```python
def should_use_networkx(
    sample: SampleResult,
    stats: TableStats | None = None,
    algorithm: str | None = None,
) -> tuple[bool, str | None]:
    """
    Determine if NetworkX should be used instead of SQL-based traversal.

    Args:
        sample: Sampling results
        stats: Optional table stats
        algorithm: Algorithm being used

    Returns:
        Tuple of (should_use_networkx, reason)
    """
```

### Usage Example

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

## Integration with Handlers

The estimator module is integrated into traversal handlers via the new configurable parameters:

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

    # NEW: Configurable limits
    max_nodes: int | None = None,         # Override default 10,000
    skip_estimation: bool = False,         # Bypass size check
    estimation_config: EstimationConfig | None = None,
) -> dict[str, Any]:
```

### Usage Patterns

```python
from virt_graph.handlers import traverse, bom_explode, EstimationConfig

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

### Before (v0.7.x)
```
SubgraphTooLarge: Query would touch ~21,365 nodes (limit: 10,000).
Consider adding filters or reducing depth.
```

### After (v0.8.0)
```
SubgraphTooLarge: Query would touch ~2,500 nodes (limit: 10,000).
Consider: max_nodes=N to increase limit, or skip_estimation=True to bypass.
```

---

## Deprecation Notice

The old `estimate_reachable_nodes()` function in `handlers.base` is deprecated:

```python
# DEPRECATED
from virt_graph.handlers.base import estimate_reachable_nodes

# Will emit DeprecationWarning:
# "estimate_reachable_nodes is deprecated.
#  Use virt_graph.estimator.estimate() with GraphSampler for better accuracy."
```

**Migration**:
```python
# OLD
from virt_graph.handlers.base import estimate_reachable_nodes
est = estimate_reachable_nodes(conn, edges_table, start_id, max_depth, from_col, to_col)

# NEW
from virt_graph.estimator import GraphSampler, estimate, get_table_bound
sampler = GraphSampler(conn, edges_table, from_col, to_col)
sample = sampler.sample(start_id)
table_bound = get_table_bound(conn, edges_table, from_col, to_col)
est = estimate(sample, max_depth, table_bound)
```
