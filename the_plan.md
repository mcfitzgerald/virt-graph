# Plan: Dual Benchmark - VG/SQL vs Neo4j (All 50 Questions)

## Objective
1. **Re-run VG/SQL benchmark** (handlers + SQL) to get fresh baseline after bug fixes
2. **Run Neo4j benchmark** using pure Cypher (no handlers)
3. **Produce side-by-side markdown comparison**

## Context
- **Hypothesis**: Virtual Graph (ontology + handlers over SQL) is a viable alternative to migrating relational data to a graph database
- **Previous VG/SQL benchmark**: ~98% accuracy, but bugs were fixed since then - needs re-run
- **Neo4j**: Already populated with same data (45,492 nodes, 179,983 relationships) via ontology-driven migration

## Key Distinction
| System | Query Method |
|--------|--------------|
| **VG/SQL** | SQL + Python handlers (`traverse()`, `shortest_path()`, `centrality()`) |
| **Neo4j** | Pure Cypher only (native `shortestPath()`, APOC/GDS for algorithms) |

This comparison validates whether VG handlers can match native graph database capabilities.

---

## Pre-Flight Checklist

### 1. Database Verification
```bash
# Verify both databases running
docker ps | grep -E "(postgres|neo4j)"

# Expected output shows both containers healthy
```

### 2. Entity ID Cache
Load and cache IDs for named test entities BEFORE benchmark execution:

| Entity Type | Named Entities |
|-------------|----------------|
| Suppliers | Acme Corp, GlobalTech Industries, Pacific Components, Eastern Electronics |
| Parts | CHIP-001, RESISTOR-100 |
| Products | Turbo Encabulator, Flux Capacitor |
| Facilities | Chicago Warehouse, LA Distribution Center, New York Factory, Denver Hub, Miami Hub, Seattle Warehouse |
| Customers | Acme Industries |
| Orders | ORD-2024-001 |

```python
# Example: Cache all entity IDs at start
entity_ids = {
    'acme_id': get_supplier_id("Acme Corp"),
    'globaltech_id': get_supplier_id("GlobalTech Industries"),
    'chicago_id': get_facility_id("Chicago Warehouse"),
    # ... etc
}
```

### 3. Schema Property Check (CRITICAL)
Verify Neo4j has required relationship properties:
```cypher
-- Check CONNECTSTO properties
MATCH ()-[r:CONNECTSTO]->() RETURN keys(r) LIMIT 1
-- Expected: [distance_km, cost_usd, transit_time_hours, transport_mode, ...]
```

**If properties missing**: RED pathfinding will use hop count only. Document in results.

### 4. Capability Check
```cypher
-- Check APOC availability
RETURN apoc.version()

-- Check GDS availability
RETURN gds.version()
```
If GDS unavailable, use fallback patterns (degree count instead of betweenness, etc.)

---

## Execution Phases

### Phase 0: GREEN Validation Gate (Q01-Q10)
Execute GREEN questions FIRST as connectivity validation:
- **Required**: 100% parity between VG/SQL and Neo4j
- If results don't match → **STOP and debug before proceeding**
- This validates basic setup before complex queries

### Phase 1: YELLOW Supplier Network (Q11-Q18)
Test recursive traversal of tiered supplier network using `SuppliesTo` relationship.
- **Acceptable variance**: 95%+ match (minor traversal differences)

### Phase 2: YELLOW Bill of Materials (Q19-Q28)
**BOM Alignment Requirement** - Both systems MUST traverse from same starting point:

For VG/SQL - traverse ALL product_components:
```python
# Get ALL direct components of product
cur.execute("""
    SELECT part_id FROM product_components
    WHERE product_id = %s
""", (product_id,))
all_roots = [row[0] for row in cur.fetchall()]

# Explode each and union results
all_parts = set()
for root_id in all_roots:
    result = bom_explode(conn, start_part_id=root_id, max_depth=20)
    all_parts.update(n['id'] for n in result['nodes'])
```

For Neo4j:
```cypher
MATCH (pr:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(root:Part)
MATCH path = (root)-[:HASCOMPONENT*0..20]->(child:Part)
RETURN count(DISTINCT child) as count
```

- **Required**: 100% match (same starting point = same results)

### Phase 3: RED Pathfinding (Q29-Q35)
Test weighted shortest path algorithms on transport network.

**If edge weights available**:
```cypher
MATCH path = shortestPath((start)-[:CONNECTSTO*]-(end))
RETURN reduce(d = 0, r in relationships(path) | d + r.distance_km) as total
```

**If edge weights missing (fallback)**:
```cypher
MATCH path = shortestPath((start)-[:CONNECTSTO*]-(end))
RETURN length(path) as hops
```

### Phase 4: RED Centrality & Connectivity (Q36-Q40)
Test graph algorithms for network analysis.

**With GDS**:
```cypher
CALL gds.betweenness.stream('transport-graph')
YIELD nodeId, score
```

**Without GDS (fallback)**:
```cypher
MATCH (f:Facility)-[r:CONNECTSTO]-()
RETURN f.name, count(r) as degree
ORDER BY degree DESC
```

### Phase 5: MIXED (Q41-Q50)
Cross-complexity patterns combining GREEN + YELLOW/RED operations.
- **Acceptable variance**: 90%+ match

---

## Key Cypher Patterns

### GREEN (Direct matches)
```cypher
MATCH (s:Supplier)-[:CANSUPPLY]->(p:Part)
WHERE s.name = 'GlobalTech Industries'
RETURN p.part_number, p.description
```

### YELLOW (Variable-length paths)
```cypher
// Upstream suppliers (who sells TO Acme)
MATCH path = (upstream:Supplier)-[:SUPPLIESTO*1..10]->(acme:Supplier {name: 'Acme Corp'})
RETURN upstream, length(path) as depth

// BOM explosion
MATCH (pr:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(root:Part)
MATCH path = (root)-[:HASCOMPONENT*0..20]->(child:Part)
RETURN child, length(path) as level
```

### RED (Graph algorithms)
```cypher
// Shortest path (hop count)
MATCH (start:Facility {name: 'Chicago Warehouse'}), (end:Facility {name: 'LA Distribution Center'})
MATCH path = shortestPath((start)-[:CONNECTSTO*]->(end))
RETURN [n IN nodes(path) | n.name] as route, length(path) as hops

// Path avoiding specific node
MATCH path = shortestPath((start)-[:CONNECTSTO*]->(end))
WHERE NONE(n IN nodes(path) WHERE n.name = 'Denver Hub')
RETURN path
```

---

## Output Files

| File | Description |
|------|-------------|
| `queries.md` | VG/SQL results - SQL queries and handler calls with results |
| `neo4j_queries.md` | Neo4j results - Cypher queries with results |
| `benchmark_comparison.md` | Side-by-side comparison with match/mismatch indicators |

---

## Success Criteria

| Category | Questions | Required Match Rate |
|----------|-----------|---------------------|
| GREEN | Q01-Q10 | **100%** (validation gate) |
| YELLOW Supplier | Q11-Q18 | 95%+ |
| YELLOW BOM | Q19-Q28 | **100%** (same starting point) |
| RED Pathfinding | Q29-Q35 | Valid given capabilities |
| RED Centrality | Q36-Q40 | Valid given capabilities |
| MIXED | Q41-Q50 | 90%+ |

**All discrepancies must have ROOT CAUSE identified** (not just noted as "different").

---

## Known Issues (Current State)

| Issue | Impact | Status |
|-------|--------|--------|
| CONNECTSTO missing edge weights | RED pathfinding uses hop count only | Needs migration fix |
| GDS not installed | Centrality uses fallback patterns | Optional enhancement |
| lead_time_days not on CANSUPPLY | Q48 returns 0 in Neo4j | Needs migration fix |

**To fix migration**: Update `neo4j/migrate.py` to include edge properties:
- CONNECTSTO: `distance_km`, `cost_usd`, `transit_time_hours`, `transport_mode`
- CANSUPPLY: `lead_time_days`, `unit_cost`

---

## Post-Execution Verification

After benchmark completion, verify:

| Check | Expected | Action if Failed |
|-------|----------|------------------|
| GREEN match rate | 100% | STOP - debug before proceeding |
| BOM counts (Turbo) | 734 parts both systems | Check all roots traversed |
| BOM counts (Flux) | 688 parts both systems | Check all roots traversed |
| All discrepancies | Have documented root cause | Investigate before finalizing |

**Session Documentation**: Update `experiment_notebook_N.md` with:
- Issues encountered
- Fixes applied
- Remaining gaps
- Next steps

---

## Troubleshooting Guide

### "No path found" in Neo4j
- Check relationship direction: `()-[:REL]->()` vs `()-[:REL]-()`
- Verify start/end nodes exist: `MATCH (n) WHERE n.name = 'X' RETURN n`

### Count mismatches in BOM
- Verify BOTH systems start from ALL product_components
- Check for duplicate counting in Neo4j (use `DISTINCT`)

### Missing relationship properties
- Check migration script: `neo4j/migrate.py`
- May need to re-run migration with property mapping

### VG/SQL returns more results than Neo4j
- Check soft-delete filter: `WHERE deleted_at IS NULL`
- Neo4j may have filtered during migration

---

## Key Files
- `question_inventory.md` - The 50 questions with ontology references
- `queries.md` - VG/SQL results (to be generated)
- `neo4j_queries.md` - Neo4j results (to be generated)
- `ontology/supply_chain.yaml` - Node/relationship mappings
- `neo4j/migration_metrics.json` - Neo4j schema reference

## Reference Cheat Sheets
- `sql_pattern_cheat_sheet.md` - SQL and handler patterns for VG/SQL benchmark
- `handler_pattern_cheat_sheet.md` - Handler signatures, parameters, and return values
