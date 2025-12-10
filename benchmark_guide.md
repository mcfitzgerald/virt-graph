# Benchmark Guide: VG/SQL vs Neo4j

This guide covers running the 50-question benchmark comparing Virtual Graph (SQL + handlers) against Neo4j (Cypher + GDS).

---

## Quick Start

### Pre-Flight Checklist

```bash
# 1. Verify both databases running
docker ps | grep -E "(postgres|neo4j)"

# 2. Check Neo4j GDS availability
docker exec virt-graph-neo4j cypher-shell -u neo4j -p dev_password "RETURN gds.version()"
```

### Entity ID Cache
Load named entity IDs before running queries:

| Entity Type | Test Entities |
|-------------|---------------|
| Suppliers | Acme Corp, GlobalTech Industries, Pacific Components, Eastern Electronics |
| Parts | CHIP-001, RESISTOR-100 |
| Products | Turbo Encabulator, Flux Capacitor |
| Facilities | Chicago Warehouse, LA Distribution Center, New York Factory, Denver Hub, Miami Hub, Seattle Warehouse |

---

## Benchmark Phases

### Phase 0: GREEN Validation Gate (Q01-Q10)
**Required: 100% match** - Basic connectivity validation.
If results differ → STOP and debug before proceeding.

### Phase 1: YELLOW Supplier Network (Q11-Q18)
Recursive traversal of tiered supplier network.
Target: 95%+ match.

### Phase 2: YELLOW Bill of Materials (Q19-Q28)
BOM explosion with quantity aggregation.
**Critical**: Both systems must start from ALL product_components.
Target: 100% match.

### Phase 3: RED Pathfinding (Q29-Q35)
Weighted shortest path on transport network.
Uses `distance_km`, `cost_usd`, `transit_time_hours`.

### Phase 4: RED Centrality (Q36-Q40)
Graph algorithms: betweenness, degree, PageRank.
Neo4j uses GDS; VG/SQL uses NetworkX.

### Phase 5: MIXED (Q41-Q50)
Cross-complexity patterns combining GREEN + YELLOW/RED.
Target: 90%+ match.

---

## Soft-Delete Filtering

To align VG/SQL with Neo4j migration (which filters `WHERE deleted_at IS NULL`):

```python
# All handlers support soft_delete_column parameter
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=supplier_id,
    soft_delete_column="deleted_at",  # Excludes soft-deleted nodes
)

result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    soft_delete_column="deleted_at",
)
```

---

## Query Pattern Summary

### VG/SQL
- **GREEN**: Direct SQL queries
- **YELLOW**: `traverse()`, `bom_explode()` handlers
- **RED**: `shortest_path()`, `centrality()` handlers

### Neo4j
- **GREEN**: Direct Cypher `MATCH` patterns
- **YELLOW**: Variable-length paths `[:REL*1..10]`
- **RED**: GDS algorithms (`gds.betweenness.stream()`, `gds.pageRank.stream()`)

---

## Troubleshooting

### Count Mismatches in BOM
- Verify BOTH systems start from ALL `product_components`
- Check for duplicate counting (use `DISTINCT` in Cypher)

### "No path found" in Neo4j
- Check relationship direction: `()-[:REL]->()` vs `()-[:REL]-()`
- Verify nodes exist: `MATCH (n) WHERE n.name = 'X' RETURN n`

### VG/SQL Returns More Results
- Apply soft-delete filter: `soft_delete_column="deleted_at"`
- Neo4j migration already filters deleted records

### Centrality Score Differences
- VG/SQL uses NetworkX (real algorithms)
- Neo4j needs GDS for proper betweenness/PageRank

---

## Output Files

| File | Description |
|------|-------------|
| `queries.md` | VG/SQL benchmark results |
| `neo4j_queries.md` | Neo4j benchmark results |
| `benchmark_comparison.md` | Side-by-side analysis |
| `question_inventory.md` | The 50 questions with ontology references |

---

## Reference

- `handler_pattern_cheat_sheet.md` - Handler signatures and parameters
- `sql_pattern_cheat_sheet.md` - SQL and handler patterns
- `src/virt_graph/ontology.py` - Ontology definitions
- `neo4j/migration_metrics.json` - Neo4j schema reference
