# VG/SQL Operation Types Refactor

**Status:** Proposed
**Author:** Claude + Michael
**Date:** 2025-12-15

## Executive Summary

Replace the abstract GREEN/YELLOW/RED complexity classification with explicit **operation types** that map directly to handlers. Add **temporal traversal** and **path aggregation** capabilities crucial for supply chain analytics.

**Key Changes:**
1. New ontology vocabulary: `OperationCategory` and `OperationType` enums
2. Temporal support: Time-bounded graph traversal for contract/certification validity
3. Generalized aggregation: Replace domain-specific `bom_explode()` with generic `path_aggregate()`

**No special libraries required** — all implementations use pure SQL recursive CTEs.

---

## Motivation

### Problem with Current Approach

The current `vg:traversal_complexity` uses color codes (GREEN/YELLOW/RED) that are:
- **Imprecise** — "YELLOW" doesn't tell Claude which handler to use
- **Non-extensible** — Adding new operation types requires redefining colors
- **Not discoverable** — During ontology discovery, Claude can't infer colors from schema analysis

### Solution

Replace colors with **semantic operation types** that:
- Map directly to handler functions
- Are multi-valued (relationships can support multiple operations)
- Include metadata (temporal bounds, aggregation columns)
- Can be inferred during ontology discovery

---

## Part 1: Ontology Refactor

### New Enums

#### OperationCategory
High-level classification of graph operation families.

| Category | Description | Handler Type |
|----------|-------------|--------------|
| `direct` | Simple SQL joins/filters | Standard SQL |
| `traversal` | Recursive path-following (BFS/DFS) | `traverse()` |
| `temporal` | Time-aware queries | `traverse(valid_at=...)` |
| `aggregation` | Value aggregation along paths | `path_aggregate()` |
| `algorithm` | Global graph analysis | NetworkX-based |
| `pattern` | Subgraph pattern matching | Future |

#### OperationType
Specific handler operations. Each type belongs to exactly one category.

| Operation Type | Category | Handler | Use When |
|----------------|----------|---------|----------|
| `direct_join` | direct | (SQL) | Simple FK lookups, junction tables |
| `recursive_traversal` | traversal | `traverse()` | Multi-hop paths through relationships |
| `temporal_traversal` | temporal | `traverse(valid_at=...)` | Time-bounded path following |
| `path_aggregation` | aggregation | `path_aggregate()` | SUM/MAX/MIN along paths |
| `hierarchical_aggregation` | aggregation | `path_aggregate(op='multiply')` | Quantity propagation (BOM) |
| `shortest_path` | algorithm | `shortest_path()` | Optimal route between nodes |
| `centrality` | algorithm | `centrality()` | Node importance ranking |
| `connected_components` | algorithm | `connected_components()` | Find isolated clusters |
| `resilience_analysis` | algorithm | `resilience_analysis()` | Impact of node removal |
| `subgraph_match` | pattern | (future) | Structural pattern matching |

### Annotation Format

**Old format:**
```yaml
SuppliesTo:
  annotations:
    vg:traversal_complexity: YELLOW
```

**New format:**
```yaml
SuppliesTo:
  annotations:
    vg:operation_types: [recursive_traversal, temporal_traversal]
    vg:temporal_bounds:
      start_col: contract_start_date
      end_col: contract_end_date
```

### Migration Mapping

| Old (Color) | New Operation Type(s) |
|-------------|----------------------|
| GREEN | `[direct_join]` |
| YELLOW (traverse) | `[recursive_traversal]` |
| YELLOW (bom) | `[recursive_traversal, path_aggregation]` |
| RED | `[shortest_path, centrality, connected_components, resilience_analysis]` |

---

## Part 2: Temporal Traversal

### Motivation

Supply chains are inherently time-varying:
- Supplier contracts have start/end dates
- Certifications expire
- Relationships change over time

Without temporal support, we cannot answer:
- "Who were our suppliers when we placed order X?"
- "What certifications will expire in 90 days?"
- "Show the supply network as of 2024-01-01"

### Database Support

The supply chain schema already has temporal columns:

| Table | Start Column | End Column |
|-------|--------------|------------|
| `supplier_relationships` | `contract_start_date` | `contract_end_date` |
| `supplier_certifications` | `issued_date` | `expiry_date` |
| `part_suppliers` | `approval_date` | — |

### Implementation

Extend `traverse()` with temporal parameters:

```python
def traverse(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    direction: str = "outbound",
    max_depth: int = 10,
    # ... existing params ...

    # NEW: Temporal filtering
    valid_at: datetime | None = None,
    temporal_start_col: str | None = None,
    temporal_end_col: str | None = None,
) -> TraverseResult:
```

Edge query modification in `fetch_edges_for_frontier()`:

```sql
SELECT {edge_from_col}, {edge_to_col}
FROM {edges_table}
WHERE {edge_from_col} = ANY(%s)
  -- Temporal filter: edge must be valid at the given timestamp
  AND ({temporal_start_col} IS NULL OR {temporal_start_col} <= %s)
  AND ({temporal_end_col} IS NULL OR {temporal_end_col} >= %s)
```

### Usage Example

```python
from datetime import datetime

# Find suppliers with active contracts on Jan 1, 2024
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",
    max_depth=10,
    valid_at=datetime(2024, 1, 1),
    temporal_start_col="contract_start_date",
    temporal_end_col="contract_end_date",
)
```

---

## Part 3: Path Aggregation Handler

### Motivation

Current `bom_explode()` is domain-specific (Bill of Materials) but the underlying algorithm is generic: **aggregate values along all paths from a root node**.

Supply chain needs various aggregations:
- **Multiply**: Quantity propagation (BOM explosion)
- **Sum**: Total lead time from raw materials
- **Max**: Maximum risk score along supply chain
- **Min**: Minimum quality rating
- **Count**: Number of hops to each node

### Implementation

New generic `path_aggregate()` function:

```python
def path_aggregate(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    value_col: str,
    operation: Literal["sum", "max", "min", "multiply", "count"] = "sum",
    direction: str = "outbound",
    max_depth: int = 20,
    # Temporal support built-in
    valid_at: datetime | None = None,
    temporal_start_col: str | None = None,
    temporal_end_col: str | None = None,
) -> PathAggregateResult:
```

### Recursive CTE Implementation

```sql
WITH RECURSIVE paths AS (
    -- Anchor: direct children of start node
    SELECT
        e.{edge_to_col} as node_id,
        e.{value_col}::numeric as path_value,
        1 as depth,
        ARRAY[{start_id}, e.{edge_to_col}] as path
    FROM {edges_table} e
    WHERE e.{edge_from_col} = {start_id}

    UNION ALL

    -- Recursive: aggregate along each path
    SELECT
        e.{edge_to_col},
        CASE '{operation}'
            WHEN 'sum' THEN p.path_value + e.{value_col}
            WHEN 'max' THEN GREATEST(p.path_value, e.{value_col})
            WHEN 'min' THEN LEAST(p.path_value, e.{value_col})
            WHEN 'multiply' THEN p.path_value * e.{value_col}
            WHEN 'count' THEN p.path_value + 1
        END,
        p.depth + 1,
        p.path || e.{edge_to_col}
    FROM paths p
    JOIN {edges_table} e ON e.{edge_from_col} = p.node_id
    WHERE p.depth < {max_depth}
      AND NOT e.{edge_to_col} = ANY(p.path)  -- cycle prevention
)
-- Aggregate across all paths to each node
SELECT
    node_id,
    CASE '{operation}'
        WHEN 'sum' THEN SUM(path_value)      -- sum of all path sums
        WHEN 'max' THEN MAX(path_value)      -- max across all paths
        WHEN 'min' THEN MIN(path_value)      -- min across all paths
        WHEN 'multiply' THEN SUM(path_value) -- sum of products (BOM style)
        WHEN 'count' THEN MIN(depth)         -- shortest path length
    END as aggregated_value,
    MIN(depth) as min_depth
FROM paths
GROUP BY node_id
```

### Result Type

```python
class PathAggregateResult(TypedDict):
    nodes: list[dict]                    # Node data with aggregated values
    aggregated_values: dict[int, float]  # node_id → aggregated value
    operation: str                       # sum/max/min/multiply/count
    value_column: str                    # Column that was aggregated
    max_depth: int                       # Deepest level reached
    nodes_visited: int                   # Total unique nodes
```

### Usage Examples

```python
# Total lead time from raw materials to finished product
result = path_aggregate(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="parent_part_id",
    edge_to_col="child_part_id",
    start_id=product_id,
    value_col="lead_time_days",
    operation="sum"
)

# Maximum risk score along supply chain
result = path_aggregate(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="buyer_id",
    edge_to_col="seller_id",
    start_id=oem_id,
    value_col="risk_score",
    operation="max"
)

# BOM explosion (backward compatible usage)
result = path_aggregate(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="parent_part_id",
    edge_to_col="child_part_id",
    start_id=product_id,
    value_col="quantity",
    operation="multiply"
)
```

### Backward Compatibility

Deprecate `bom_explode()` but keep as thin wrapper:

```python
def bom_explode(conn, start_part_id, max_depth=20, include_quantities=True, **kwargs):
    """
    DEPRECATED: Use path_aggregate(operation='multiply') instead.

    This function is maintained for backward compatibility.
    """
    warnings.warn(
        "bom_explode() is deprecated. Use path_aggregate(operation='multiply')",
        DeprecationWarning,
        stacklevel=2
    )
    result = path_aggregate(
        conn,
        nodes_table="parts",
        edges_table="bill_of_materials",
        edge_from_col="parent_part_id",
        edge_to_col="child_part_id",
        start_id=start_part_id,
        value_col="quantity",
        operation="multiply",
        max_depth=max_depth,
        **kwargs
    )
    # Transform to legacy BomExplodeResult format
    return _to_bom_explode_result(result)
```

---

## Part 4: Supply Chain Ontology Migration

### Relationship Annotations

| Relationship | Old | New | Notes |
|--------------|-----|-----|-------|
| PrimarySupplier | GREEN | `[direct_join]` | Simple FK |
| CanSupply | GREEN | `[direct_join]` | Junction table |
| ContainsComponent | GREEN | `[direct_join]` | Junction table |
| PlacedBy | GREEN | `[direct_join]` | Simple FK |
| ShipsFrom | GREEN | `[direct_join]` | Simple FK |
| OrderContains | GREEN | `[direct_join]` | Junction table |
| InventoryAt | GREEN | `[direct_join]` | Simple FK |
| InventoryOf | GREEN | `[direct_join]` | Simple FK |
| ForOrder | GREEN | `[direct_join]` | Simple FK |
| OriginatesAt | GREEN | `[direct_join]` | Simple FK |
| UsesRoute | GREEN | `[direct_join]` | Simple FK |
| SuppliesTo | YELLOW | `[recursive_traversal, temporal_traversal]` | + temporal_bounds |
| ComponentOf | YELLOW | `[recursive_traversal, path_aggregation]` | BOM child→parent |
| HasComponent | YELLOW | `[recursive_traversal, path_aggregation]` | BOM parent→child |
| ConnectsTo | RED | `[recursive_traversal, shortest_path, centrality, connected_components, resilience_analysis]` | Weighted network |
| HasCertification | GREEN | `[direct_join, temporal_traversal]` | + temporal_bounds |

### Temporal Bounds Configuration

```yaml
SuppliesTo:
  instantiates: vg:SQLMappedRelationship
  annotations:
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id
    vg:range_key: buyer_id
    vg:operation_types: [recursive_traversal, temporal_traversal]
    vg:temporal_bounds:
      start_col: contract_start_date
      end_col: contract_end_date

HasCertification:
  instantiates: vg:SQLMappedRelationship
  annotations:
    vg:edge_table: supplier_certifications
    vg:domain_key: supplier_id
    vg:range_key: certification_id
    vg:operation_types: [direct_join, temporal_traversal]
    vg:temporal_bounds:
      start_col: issued_date
      end_col: expiry_date
```

---

## Implementation Plan

### Phase 1: Ontology Layer
**Files:** `ontology/virt_graph.yaml`, `src/virt_graph/ontology.py`

1. Add `OperationCategory` enum to virt_graph.yaml
2. Add `OperationType` enum with category attribute
3. Add `temporal_bounds` slot definition
4. Deprecate `TraversalComplexity` enum (keep for backward compat)
5. Update `OntologyAccessor`:
   - Add `get_operation_types(role_name) -> list[str]`
   - Add `get_operation_category(op_type) -> str`
   - Add `get_temporal_bounds(role_name) -> dict | None`
   - Update validation for new annotations

### Phase 2: Handler Layer
**Files:** `src/virt_graph/handlers/traversal.py`, `src/virt_graph/handlers/base.py`

1. Add temporal parameters to `traverse()`:
   - `valid_at: datetime | None`
   - `temporal_start_col: str | None`
   - `temporal_end_col: str | None`
2. Update `fetch_edges_for_frontier()` with temporal filtering
3. Create `path_aggregate()` function
4. Add `PathAggregateResult` TypedDict
5. Deprecate `bom_explode()` as wrapper

### Phase 3: Domain Ontology Migration
**Files:** `ontology/supply_chain.yaml`

1. Replace all `vg:traversal_complexity` with `vg:operation_types`
2. Add `vg:temporal_bounds` to SuppliesTo, HasCertification
3. Update ConnectsTo with full algorithm support list

### Phase 4: Documentation & Tests
**Files:** `CLAUDE.md`, `docs/concepts/complexity-levels.md`, `tests/`

1. Update CLAUDE.md handler reference
2. Rewrite complexity-levels.md as operation-types.md
3. Add tests for temporal traversal
4. Add tests for path_aggregate operations
5. Update ontology validation tests

---

## Files Changed

| File | Type | Changes |
|------|------|---------|
| `ontology/virt_graph.yaml` | Modify | New enums, deprecate old |
| `ontology/supply_chain.yaml` | Modify | Migrate all annotations |
| `src/virt_graph/ontology.py` | Modify | New accessors, validation |
| `src/virt_graph/handlers/base.py` | Modify | Add PathAggregateResult |
| `src/virt_graph/handlers/traversal.py` | Modify | Temporal params, path_aggregate() |
| `src/virt_graph/handlers/__init__.py` | Modify | Export path_aggregate |
| `CLAUDE.md` | Modify | Update handler docs |
| `docs/concepts/complexity-levels.md` | Rename/Rewrite | → operation-types.md |
| `tests/test_traversal.py` | Modify | Add new tests |
| `tests/test_ontology_validation.py` | Modify | Update for new schema |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing code using `bom_explode()` | Medium | Keep as deprecated wrapper |
| Breaking ontology validation | High | Support both old and new annotations during transition |
| Performance of temporal filtering | Low | Uses indexed date columns, adds simple WHERE clause |
| Complex CTE for path aggregation | Medium | Similar to existing bom_explode CTE, well-tested pattern |

---

## Success Criteria

1. All existing tests pass
2. New operation types correctly validated
3. Temporal traversal returns only time-valid edges
4. `path_aggregate()` produces correct results for all operations
5. `bom_explode()` continues to work (with deprecation warning)
6. CLAUDE.md accurately documents new handlers

---

## Future Work (Out of Scope)

- **Pattern matching**: Subgraph/motif detection handler
- **Temporal analytics**: Trend analysis, change detection over time
- **Performance optimization**: Parallel path aggregation for large graphs
