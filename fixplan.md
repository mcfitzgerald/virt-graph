# Fix Plan: Benchmark Gap Resolution

**Created**: 2025-12-09
**Context**: Continuing from experiment_notebook_1.md benchmark session

---

## Completed Fixes

### 1. Edge Weights on CONNECTSTO ✅
**Problem**: Neo4j CONNECTSTO relationships had no properties (distance_km, cost_usd, etc.)

**Fix Applied**: Updated `OntologyAccessor.get_role_sql()` in `src/virt_graph/ontology.py` to include `additional_columns` derived from relationship attributes.

**Verification**:
```cypher
MATCH ()-[r:CONNECTSTO]->() RETURN keys(r) LIMIT 1
-- Returns: ["transit_time_hours", "capacity_tons", "cost_usd", "is_active", "distance_km", "transport_mode"]
```

### 2. GDS Plugin Installed ✅
**Problem**: Neo4j lacked Graph Data Science for centrality algorithms

**Fix Applied**: Changed `neo4j/docker-compose.yml`:
```yaml
NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
```

**Verification**:
```cypher
RETURN gds.version()  -- Returns "2.6.9"
```

---

## Remaining Fixes

### 3. Supplier Depth Discrepancy (Document Only) ✅
**Observation**: VG/SQL reports max depth 3, Neo4j reports max depth 2

**Root Cause**:
- Neo4j migration filters soft-deleted nodes (`WHERE deleted_at IS NULL`)
- VG/SQL `traverse()` follows ALL edges including those to soft-deleted suppliers
- Result: VG/SQL reaches deeper through soft-deleted intermediate nodes

**Resolution**: Documented as expected difference in `benchmark_comparison.md`.

---

### 4. Q23 Cost Calculation - BOM EXPLODE BUG ✅

**Fixed 2025-12-09** using CTE-based multi-path quantity aggregation.

#### The Problem

Q23 asks for total component cost of "Turbo Encabulator". Results differ wildly:

| Source | Result | Status |
|--------|--------|--------|
| `queries.md` (documented) | $5,846,557.79 | ❌ WRONG |
| VG/SQL actual (`bom_explode`) | $33,243,882.94 | Current behavior |
| Neo4j (all paths) | $34,795,958.60 | More accurate |

#### Root Cause: BFS Single-Path Bug

The `bom_explode` function in `src/virt_graph/handlers/traversal.py` uses BFS traversal which **visits each node only once via the first-discovered path**.

**Bug scenario**:
```
Assembly A
├── Bolt [qty: 2]      ← BFS finds this first
└── Bracket [qty: 1]
    └── Bolt [qty: 3]  ← NEVER COUNTED (already visited)
```

The bolt's total quantity should be `2 + (1 × 3) = 5`, but BFS only returns `2`.

#### Code Location

**File**: `src/virt_graph/handlers/traversal.py` lines 365-450

**Current (buggy) logic**:
```python
def bom_explode(...):
    # Uses BFS traverse - visits each node ONCE
    result = traverse(...)

    # Only calculates qty for the ONE stored path per node
    for node_id, path in result["paths"].items():
        total_qty = 1
        for i in range(len(path) - 1):
            # Multiply quantities along THIS path only
            total_qty *= get_edge_quantity(path[i], path[i+1])
        quantities[node_id] = total_qty  # Overwrites, doesn't accumulate
```

#### The Fix Required

Need to accumulate quantities across ALL paths to each part, not just the first BFS path.

**Option A - SQL-based aggregation** (recommended):
```python
def bom_explode_fixed(...):
    """
    Use recursive CTE to find ALL paths and sum quantities.
    """
    query = """
    WITH RECURSIVE bom_paths AS (
        -- Base: start part with qty 1
        SELECT child_part_id as part_id,
               quantity as path_qty,
               1 as depth
        FROM bill_of_materials
        WHERE parent_part_id = %s

        UNION ALL

        -- Recursive: multiply quantities along each path
        SELECT bom.child_part_id,
               bp.path_qty * bom.quantity,
               bp.depth + 1
        FROM bom_paths bp
        JOIN bill_of_materials bom ON bom.parent_part_id = bp.part_id
        WHERE bp.depth < %s
    )
    SELECT part_id, SUM(path_qty) as total_qty
    FROM bom_paths
    GROUP BY part_id
    """
```

**Option B - Fix BFS to track all paths**:
- More complex, requires changing traverse() to not deduplicate
- Would need new `track_all_paths=True` parameter

#### Verification Test

After fix, run:
```python
result = bom_explode(conn, start_part_id=turbo_part_id, include_quantities=True)
# Calculate total cost
total = sum(node['unit_cost'] * result['quantities'][node['id']] for node in result['nodes'])
# Should be ~$34.8M (matching Neo4j all-paths result)
```

---

## Files Summary

| File | Action | Status |
|------|--------|--------|
| `src/virt_graph/ontology.py` | Added additional_columns to get_role_sql() | ✅ Done |
| `neo4j/docker-compose.yml` | Added graph-data-science plugin | ✅ Done |
| `src/virt_graph/handlers/traversal.py` | CTE-based bom_explode with BomExplodeResult return type | ✅ Done |
| `tests/test_bom_explode.py` | Comprehensive regression tests (11 tests) | ✅ Done |
| `queries.md` | Q23 result: $34,795,958.60 | ✅ Done |
| `neo4j_queries.md` | Q23 with quantity multiplication methodology | ✅ Done |
| `benchmark_comparison.md` | Depth discrepancy + Q23 match documented | ✅ Done |

---

## Quick Start for Next Session

1. **Read this file** and `experiment_notebook_1.md` for context
2. **The key fix** is in `src/virt_graph/handlers/traversal.py` - the `bom_explode` function
3. **Test with**:
   ```bash
   poetry run python -c "
   from virt_graph.handlers.traversal import bom_explode
   import psycopg2
   conn = psycopg2.connect('postgresql://virt_graph:dev_password@localhost:5432/supply_chain')
   result = bom_explode(conn, start_part_id=4983, include_quantities=True)
   print(f'Parts: {len(result[\"nodes\"])}, Sample qtys: {dict(list(result[\"quantities\"].items())[:5])}')
   "
   ```
4. **Neo4j ground truth** (what we should match):
   ```bash
   docker exec virt-graph-neo4j cypher-shell -u neo4j -p dev_password "
   MATCH (pr:Product {name: 'Turbo Encabulator'})-[pc:CONTAINSCOMPONENT]->(root:Part)
   CALL {
     WITH root, pc
     MATCH path = (root)-[:HASCOMPONENT*0..20]->(child:Part)
     WHERE child.unit_cost IS NOT NULL
     WITH child, toFloat(child.unit_cost) as unit_cost, pc.quantity as root_qty,
          reduce(q = 1, rel in relationships(path) | q * coalesce(rel.quantity, 1)) as path_qty
     RETURN child.id as part_id, unit_cost, root_qty * path_qty as total_qty
   }
   WITH part_id, unit_cost, sum(total_qty) as agg_qty
   RETURN sum(unit_cost * agg_qty) as total_cost
   "
   -- Returns: $34,795,958.60
   ```
