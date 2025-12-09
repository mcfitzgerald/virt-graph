# Fixes and Enhancements Backlog

**Created**: 2025-12-08
**Context**: Issues identified during Q01-Q50 benchmark execution
**Source**: `REPORT.md`, session analysis

---

## Quick Context for New Session

The Virtual Graph benchmark executed 50 questions (GREEN/YELLOW/RED/MIXED complexity) with ~98% accuracy. This document captures fixes and enhancements needed. Key files:

- `REPORT.md` - Full execution report
- `queries.md` - All 50 generated queries
- `benchmarking.md` - Methodology guide
- `question_inventory.md` - The 50 questions

---

## Fix 1: Named Entity Sync (Data Generator)

### Problem
Question inventory uses intuitive names that don't exist in the database:

| Inventory Says | Database Has |
|----------------|--------------|
| `CHIP-001`, `RESISTOR-100` | `PRT-000001`, `PRT-000002`... |
| `Denver Hub`, `Miami Hub`, `Seattle Warehouse` | `Shanghai Hub`, `Munich Factory`... |
| `Acme Industries` (customer) | (doesn't exist) |
| `ORD-2024-001` | `ORD-00000001` |

### Root Cause Analysis
**Q: Should questions match data, or data match questions?**

**A: Data should match questions.** Rationale:
1. Question inventory was designed with business-intuitive names ("Denver Hub" makes sense)
2. Questions should be stable/reusable across data regenerations
3. Named test entities make queries reproducible and meaningful

**However**, there's a secondary issue: when *generating* questions, the schema should be consulted first to understand what entities exist. For this benchmark, the questions were designed independently, which created the mismatch.

### Fix Implementation

**File**: `scripts/generate_data.py`

Add explicit named test entities after random generation:

```python
# After generating random data, ensure named test entities exist

NAMED_TEST_ENTITIES = {
    "suppliers": [
        {"supplier_code": "ACME-001", "name": "Acme Corp", "tier": 1},
        {"supplier_code": "GLOBAL-001", "name": "GlobalTech Industries", "tier": 1},
        {"supplier_code": "PACIFIC-001", "name": "Pacific Components", "tier": 2},
        {"supplier_code": "EASTERN-001", "name": "Eastern Electronics", "tier": 3},
    ],
    "parts": [
        {"part_number": "CHIP-001", "description": "Integrated Circuit Chip", "category": "Electronics"},
        {"part_number": "RESISTOR-100", "description": "100 Ohm Resistor", "category": "Electronics"},
    ],
    "facilities": [
        {"facility_code": "FAC-CHI", "name": "Chicago Warehouse", "facility_type": "warehouse"},
        {"facility_code": "FAC-LA", "name": "LA Distribution Center", "facility_type": "distribution"},
        {"facility_code": "FAC-NYC", "name": "New York Factory", "facility_type": "factory"},
        {"facility_code": "FAC-DEN", "name": "Denver Hub", "facility_type": "hub"},
        {"facility_code": "FAC-MIA", "name": "Miami Hub", "facility_type": "hub"},
        {"facility_code": "FAC-SEA", "name": "Seattle Warehouse", "facility_type": "warehouse"},
    ],
    "customers": [
        {"customer_code": "CUST-ACME", "name": "Acme Industries", "customer_type": "enterprise"},
    ],
    "orders": [
        {"order_number": "ORD-2024-001", "status": "pending"},  # Specific test order
    ],
}

def ensure_named_entities(conn):
    """Insert or update named test entities for reproducible benchmarking."""
    # Implementation: upsert each entity, create relationships between them
```

**Also needed**: Ensure relationships between named entities:
- "Eastern Electronics" supplies to "Pacific Components" supplies to "Acme Corp"
- "CHIP-001" is a component in Turbo Encabulator BOM
- "Denver Hub" connects to "Chicago Warehouse" and "LA Distribution Center"

### Verification
```bash
poetry run python -c "
from scripts.generate_data import ensure_named_entities
import psycopg2
conn = psycopg2.connect('...')
ensure_named_entities(conn)
# Verify
cur = conn.cursor()
cur.execute(\"SELECT name FROM facilities WHERE name = 'Denver Hub'\")
assert cur.fetchone() is not None
"
```

---

## Fix 2: Decimal Type Conversion Bug

### Problem
PostgreSQL returns `decimal.Decimal`, which doesn't multiply with Python `float`:

```python
inventory_value = cur.fetchone()[0]  # decimal.Decimal('121321928.45')
degree_score = 0.204                  # float from handler
criticality = degree_score * inventory_value  # TypeError!
```

### Fix Implementation

**File**: `src/virt_graph/handlers/base.py`

In `fetch_nodes()` function:

```python
from decimal import Decimal

def fetch_nodes(
    conn: PgConnection,
    nodes_table: str,
    node_ids: list[int],
    columns: list[str] | None = None,
    id_column: str = "id",
) -> list[dict]:
    """Fetch node data for given IDs."""
    # ... existing query code ...

    nodes = []
    for row in rows:
        node = dict(zip(col_names, row))
        # Convert Decimal to float for numeric fields
        for key, value in node.items():
            if isinstance(value, Decimal):
                node[key] = float(value)
        nodes.append(node)

    return nodes
```

**Also check**: `_fetch_edges_with_weights()` in `pathfinding.py` for same issue.

### Verification
```python
from virt_graph.handlers import centrality
result = centrality(conn, ...)
score = result['results'][0]['score']  # Should be float
assert isinstance(score, float)
```

---

## Fix 3: Constrained Pathfinding (Excluded Nodes)

### Problem
Q35 asked "find route avoiding Denver Hub" - no native support.

Current workaround is inefficient:
```python
result = all_shortest_paths(..., max_paths=10)
valid_paths = [p for p in result['paths'] if hub_id not in p]
```

### Fix Implementation

**File**: `src/virt_graph/handlers/pathfinding.py`

```python
def shortest_path(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    end_id: int,
    weight_col: str | None = None,
    max_depth: int = 20,
    id_column: str = "id",
    excluded_nodes: list[int] | None = None,  # NEW PARAMETER
) -> dict[str, Any]:
    """
    Find shortest path between two nodes using Dijkstra.

    Args:
        ...
        excluded_nodes: Node IDs to exclude from path (route around these)
    """
    # In graph building section, skip excluded nodes:
    if excluded_nodes:
        excluded_set = set(excluded_nodes)
    else:
        excluded_set = set()

    # When adding edges to graph:
    for from_id, to_id, weight in edges:
        if from_id in excluded_set or to_id in excluded_set:
            continue  # Skip edges involving excluded nodes
        G.add_edge(from_id, to_id, weight=weight if weight else 1)
```

**Also update**: `all_shortest_paths()` with same parameter.

### Verification
```python
result = shortest_path(
    conn, ...,
    start_id=chicago_id,
    end_id=la_id,
    excluded_nodes=[denver_id],
)
assert denver_id not in result['path']
```

---

## Fix 4: Resilience Analysis Handler

### Problem
Q40 asked "if hub goes offline, which facility pairs lose connectivity?" - can't answer properly.

Currently using betweenness centrality as proxy, which doesn't actually answer the question.

### Fix Implementation

**File**: `src/virt_graph/handlers/network.py`

```python
def resilience_analysis(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    node_to_remove: int,
    id_column: str = "id",
) -> dict[str, Any]:
    """
    Analyze network resilience by simulating node removal.

    Calculates which node pairs lose connectivity if a specific node is removed.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes
        edges_table: Table containing edges
        edge_from_col: Column for edge source
        edge_to_col: Column for edge target
        node_to_remove: Node ID to simulate removal of
        id_column: ID column name

    Returns:
        dict with:
            - disconnected_pairs: list of (node_a, node_b) tuples that lose connectivity
            - components_before: number of connected components before removal
            - components_after: number of connected components after removal
            - isolated_nodes: nodes that become completely disconnected
            - affected_node_count: total nodes affected by the removal
    """
    import networkx as nx

    # Load full graph
    G = _load_full_graph(conn, edges_table, edge_from_col, edge_to_col)

    # Analyze before removal
    components_before = nx.number_weakly_connected_components(G)

    # Find pairs that are connected through this node
    # (simplified: check if removing node increases components)

    # Create graph without the node
    G_removed = G.copy()
    G_removed.remove_node(node_to_remove)

    components_after = nx.number_weakly_connected_components(G_removed)

    # Find disconnected pairs
    disconnected_pairs = []
    if components_after > components_before:
        # Get the components after removal
        components = list(nx.weakly_connected_components(G_removed))

        # Find pairs that were connected before but now in different components
        # (This is the expensive part - may need optimization for large graphs)
        component_map = {}
        for i, comp in enumerate(components):
            for node in comp:
                component_map[node] = i

        # Check neighbors of removed node - they may now be disconnected
        neighbors = list(G.predecessors(node_to_remove)) + list(G.successors(node_to_remove))
        for i, n1 in enumerate(neighbors):
            for n2 in neighbors[i+1:]:
                if n1 in component_map and n2 in component_map:
                    if component_map[n1] != component_map[n2]:
                        disconnected_pairs.append((n1, n2))

    # Find isolated nodes (were only connected through removed node)
    isolated_nodes = [n for n in G_removed.nodes() if G_removed.degree(n) == 0]

    return {
        "node_removed": node_to_remove,
        "disconnected_pairs": disconnected_pairs,
        "components_before": components_before,
        "components_after": components_after,
        "isolated_nodes": isolated_nodes,
        "affected_node_count": len(set(n for pair in disconnected_pairs for n in pair)),
    }
```

**Also add to exports**: `src/virt_graph/handlers/__init__.py`

### Verification
```python
result = resilience_analysis(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_to_remove=critical_hub_id,
)
print(f"Removing hub creates {result['components_after'] - result['components_before']} new components")
print(f"Disconnected pairs: {result['disconnected_pairs']}")
```

---

## Fix 5: Direction Semantics in Ontology

### Problem
Initial confusion about `HasComponent` vs `ComponentOf` direction during query execution.

### Analysis
**Q: Should this be in the ontology?**

**A: Yes, partially.** The ontology already has:
- `vg:domain_key` and `vg:range_key` (which columns)
- `vg:domain_class` and `vg:range_class` (which entities)

What's missing is **semantic direction documentation** - what "inbound" vs "outbound" means in business terms.

### Fix Implementation

**Option A: Add to ontology YAML** (Preferred)

**File**: `ontology/supply_chain.yaml`

Add new annotation `vg:traversal_semantics`:

```yaml
SuppliesTo:
  description: "Supplier sells to another supplier (tiered supply network)"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id
    vg:range_key: buyer_id
    vg:domain_class: Supplier
    vg:range_class: Supplier
    vg:traversal_complexity: YELLOW
    # NEW: Semantic direction hints
    vg:traversal_semantics: |
      inbound: "Find suppliers who sell TO this entity (upstream suppliers)"
      outbound: "Find entities this supplier sells TO (downstream customers)"
```

**Option B: Add to CLAUDE.md as cheat sheet**

```markdown
## Relationship Direction Quick Reference

| Relationship | edge_from → edge_to | "inbound" means | "outbound" means |
|--------------|---------------------|-----------------|------------------|
| SuppliesTo | seller_id → buyer_id | Who sells to me (upstream) | Who I sell to (downstream) |
| HasComponent | parent_part_id → child_part_id | What contains me | My sub-components |
| ComponentOf | child_part_id → parent_part_id | My sub-components | What contains me |
| ConnectsTo | origin_id → destination_id | Routes arriving here | Routes departing here |
```

**Option C: Update ontology discovery prompt**

**File**: `prompts/ontology_discovery.md`

Add instruction to capture traversal semantics:

```markdown
For each YELLOW/RED relationship, document:
1. The edge table and FK columns (existing)
2. **Traversal semantics**: What does "inbound" mean? What does "outbound" mean?
   - Example for SuppliesTo: inbound = "find upstream suppliers", outbound = "find downstream buyers"
```

### Recommendation
Implement **both A and B**:
- A (ontology) makes it machine-readable and discoverable
- B (CLAUDE.md) provides quick human reference

---

## Enhancement A: BOM Depth Analysis

### Research Finding
According to [manufacturing research](https://journalwjaets.com/sites/default/files/fulltext_pdf/WJAETS-2025-0828.pdf), typical BOM depths:
- **Simple products**: 1-2 levels (single-level BOM)
- **Complex electromechanical**: 4-7 levels typical
- **Aerospace/Automotive**: Can exceed 10+ levels for products with millions of parts

**Our synthetic data**: 5 levels - **this is realistic** for moderately complex products.

### Action
**No fix needed** - current depth is appropriate. However, for comprehensive testing:

**Optional Enhancement**: Add parameter to `generate_data.py` for configurable BOM depth:

```python
def generate_bom(max_depth=5, min_depth=3):
    """Generate BOM hierarchy with configurable depth."""
```

---

## Enhancement B: Handler Cookbook

### Problem
No concrete examples for each handler - learning curve for new users.

### Implementation

**File**: `docs/guides/handler-cookbook.md` (or root level `COOKBOOK.md`)

Structure:
```markdown
# Handler Cookbook

## YELLOW Handlers

### traverse() - Basic Usage
[concrete example with real table names]

### traverse() - Upstream vs Downstream
[examples showing direction parameter]

### bom_explode() - With Quantities
[example with cost rollup]

## RED Handlers

### shortest_path() - By Different Weights
[distance vs cost vs time examples]

### centrality() - Choosing the Right Type
[when to use degree vs betweenness vs pagerank]

## MIXED Patterns

### GREEN + YELLOW: Inventory Check
[full example from Q41]
```

**Source**: Extract from `queries.md` which already has all examples.

---

## Enhancement C: Entity Validation Script

### Problem
No way to verify named test entities exist before running benchmark.

### Implementation

**File**: `scripts/validate_entities.py`

```python
#!/usr/bin/env python3
"""Validate that named test entities exist in the database."""

import psycopg2
import sys

REQUIRED_ENTITIES = {
    "suppliers": ["Acme Corp", "GlobalTech Industries", "Pacific Components", "Eastern Electronics"],
    "products": ["Turbo Encabulator", "Flux Capacitor"],
    "facilities": ["Chicago Warehouse", "LA Distribution Center", "New York Factory",
                   "Denver Hub", "Miami Hub", "Seattle Warehouse"],
    "customers": ["Acme Industries"],
}

def validate(conn):
    missing = []
    for table, names in REQUIRED_ENTITIES.items():
        for name in names:
            cur = conn.cursor()
            cur.execute(f"SELECT 1 FROM {table} WHERE name = %s", (name,))
            if not cur.fetchone():
                missing.append(f"{table}.{name}")
    return missing

if __name__ == "__main__":
    conn = psycopg2.connect("postgresql://virt_graph:dev_password@localhost:5432/supply_chain")
    missing = validate(conn)
    if missing:
        print("❌ Missing entities:")
        for m in missing:
            print(f"   - {m}")
        sys.exit(1)
    else:
        print("✓ All named test entities exist")
        sys.exit(0)
```

**Add to Makefile**:
```makefile
validate-entities:
	poetry run python scripts/validate_entities.py
```

---

## Enhancement D: Handler Output Schema Documentation

### Problem
Handler return dicts have undocumented structure - hard to know what keys exist.

### Implementation

**Option 1: TypedDict in handlers** (Best for IDE support)

```python
from typing import TypedDict

class TraverseResult(TypedDict):
    nodes: list[dict]
    paths: dict[int, list[int]]
    edges: list[tuple[int, int]]
    depth_reached: int
    nodes_visited: int
    terminated_at: list[int]

def traverse(...) -> TraverseResult:
    ...
```

**Option 2: Document in docstrings** (Already partially done)

Ensure every handler has complete Returns section:

```python
def traverse(...) -> dict[str, Any]:
    """
    ...

    Returns:
        dict with:
            - nodes: list of node dicts with all columns
            - paths: dict mapping node_id → path (list of IDs from start)
            - edges: list of (from_id, to_id) tuples traversed
            - depth_reached: int, actual max depth encountered
            - nodes_visited: int, total unique nodes visited
            - terminated_at: list of node IDs where stop_condition matched
    """
```

---

## Priority Summary

| Fix | Priority | Effort | Dependencies |
|-----|----------|--------|--------------|
| Fix 2: Decimal conversion | P1 | Low | None |
| Fix 5B: Direction cheat sheet in CLAUDE.md | P1 | Low | None |
| Fix 1: Named entity sync | P2 | Medium | None |
| Fix 3: Excluded nodes | P2 | Medium | None |
| Fix 5A: Direction in ontology | P2 | Low | Update discovery prompt |
| Fix 4: Resilience handler | P3 | High | None |
| Enhancement B: Cookbook | ✅ DONE | Medium | `docs/guides/handler-cookbook.md` |
| Enhancement C: Validation script | P3 | Low | Fix 1 first |
| Enhancement D: Output schemas | P4 | Medium | None |

---

## Implementation Order

**Session 1: Quick Wins**
1. Fix 2 (Decimal) - 15 min
2. Fix 5B (Cheat sheet) - 10 min
3. Run tests to verify

**Session 2: Data Sync**
1. Fix 1 (Named entities) - 1 hour
2. Enhancement C (Validation script) - 20 min
3. Regenerate data, run benchmark to verify

**Session 3: Handler Enhancements**
1. Fix 3 (Excluded nodes) - 30 min
2. Fix 4 (Resilience) - 1 hour
3. Add tests for new functionality

**Session 4: Documentation**
1. Fix 5A (Ontology annotations) - 30 min
2. Enhancement B (Cookbook) - 1 hour
3. Enhancement D (Output schemas) - 1 hour
