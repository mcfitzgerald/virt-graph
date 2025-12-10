# VG/SQL Benchmark Results

Virtual Graph queries using SQL + Python handlers against PostgreSQL.

**Benchmark Date**: 2025-12-08
**Database**: PostgreSQL 14 (supply_chain)
**Total Questions**: 50

---

## GREEN - Direct SQL (Q01-Q10)

### Q01: Find the supplier with code "SUP00001"
```sql
SELECT * FROM suppliers WHERE supplier_code = 'SUP00001' AND deleted_at IS NULL;
```
**Result**: 1 row - Acme Corp (tier 1)

### Q02: List all tier 1 suppliers
```sql
SELECT * FROM suppliers WHERE tier = 1 AND deleted_at IS NULL;
```
**Result**: 50 tier 1 suppliers

### Q03: What parts can supplier "GlobalTech Industries" supply?
```sql
SELECT p.part_number, p.description, ps.unit_cost
FROM suppliers s
JOIN part_suppliers ps ON s.id = ps.supplier_id
JOIN parts p ON ps.part_id = p.id
WHERE s.name = 'GlobalTech Industries' AND s.deleted_at IS NULL;
```
**Result**: 15 parts

### Q04: Who is the primary supplier for part "CHIP-001"?
```sql
SELECT s.name, s.supplier_code
FROM parts p
JOIN suppliers s ON p.primary_supplier_id = s.id
WHERE p.part_number = 'CHIP-001' AND p.deleted_at IS NULL;
```
**Result**: Ortega, Jackson and Salazar (SUP00197)

### Q05: Which suppliers have ISO 9001 certification?
```sql
SELECT DISTINCT s.name, sc.certification_type
FROM suppliers s
JOIN supplier_certifications sc ON s.id = sc.supplier_id
WHERE sc.certification_type LIKE '%ISO 9001%' AND s.deleted_at IS NULL AND sc.is_valid = true;
```
**Result**: 0 suppliers (no ISO 9001 certifications in data)

### Q06: What are the direct components of product "Turbo Encabulator"?
```sql
SELECT p.part_number, p.description, pc.quantity
FROM products pr
JOIN product_components pc ON pr.id = pc.product_id
JOIN parts p ON pc.part_id = p.id
WHERE pr.name = 'Turbo Encabulator' AND p.deleted_at IS NULL;
```
**Result**: 3 direct components

### Q07: What is the current inventory of part "CHIP-001" at "Chicago Warehouse"?
```sql
SELECT i.quantity_on_hand, i.quantity_reserved, i.reorder_point
FROM inventory i
JOIN parts p ON i.part_id = p.id
JOIN facilities f ON i.facility_id = f.id
WHERE p.part_number = 'CHIP-001' AND f.name = 'Chicago Warehouse';
```
**Result**: None (no inventory record for this combination)

### Q08: List all pending orders for customer "Acme Industries"
```sql
SELECT o.order_number, o.order_date, o.status, o.total_amount
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE c.name = 'Acme Industries' AND o.status = 'pending';
```
**Result**: 2 pending orders

### Q09: Total revenue by customer for last quarter
```sql
SELECT c.name, SUM(o.total_amount) as revenue, COUNT(*) as order_count
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.order_date >= NOW() - INTERVAL '3 months'
GROUP BY c.id, c.name
ORDER BY revenue DESC LIMIT 10;
```
**Result**: Top 10 customers by revenue returned

### Q10: Which parts are below their reorder point?
```sql
SELECT p.part_number, i.quantity_on_hand, i.reorder_point, f.name as facility
FROM inventory i
JOIN parts p ON i.part_id = p.id
JOIN facilities f ON i.facility_id = f.id
WHERE i.quantity_on_hand < i.reorder_point AND p.deleted_at IS NULL;
```
**Result**: 5,102 parts below reorder point

---

## YELLOW - Supplier Network Traversal (Q11-Q18)

### Q11: Find all tier 2 suppliers of "Acme Corp"
```python
result = traverse(
    conn, nodes_table="suppliers", edges_table="supplier_relationships",
    edge_from_col="seller_id", edge_to_col="buyer_id",
    start_id=acme_id, direction="inbound", max_depth=1
)
```
**Result**: 9 tier 2 suppliers (1 hop upstream)

### Q12: Find all tier 2 AND tier 3 suppliers upstream from "Acme Corp"
```python
result = traverse(
    conn, nodes_table="suppliers", edges_table="supplier_relationships",
    edge_from_col="seller_id", edge_to_col="buyer_id",
    start_id=acme_id, direction="inbound", max_depth=10
)
```
**Result**: 43 suppliers upstream, max depth: 3

### Q13: Who are the downstream customers of "Pacific Components"?
```python
result = traverse(
    conn, nodes_table="suppliers", edges_table="supplier_relationships",
    edge_from_col="seller_id", edge_to_col="buyer_id",
    start_id=pacific_id, direction="outbound", max_depth=10
)
```
**Result**: 3 downstream buyers

### Q14: Trace the supply path from "Eastern Electronics" to any tier 1
```python
result = traverse(
    conn, nodes_table="suppliers", edges_table="supplier_relationships",
    edge_from_col="seller_id", edge_to_col="buyer_id",
    start_id=eastern_id, direction="outbound", max_depth=10,
    stop_condition="tier = 1"
)
```
**Result**: Reaches 5 tier 1 suppliers, depth: 2

### Q15: What is the maximum depth of our supplier network?
```python
# Traverse from multiple tier 1 suppliers, find max depth
```
**Result**: Maximum depth: 3

### Q16: Which tier 1 suppliers have the deepest supply chains?
```python
# Compare depths across tier 1 suppliers
```
**Result**: Deepest supply chain: depth 3

### Q17: Find all suppliers exactly 2 hops from "GlobalTech Industries"
```python
result = traverse(
    conn, nodes_table="suppliers", edges_table="supplier_relationships",
    edge_from_col="seller_id", edge_to_col="buyer_id",
    start_id=globaltech_id, direction="both", max_depth=2
)
# Filter paths of length 3
```
**Result**: 20 suppliers exactly 2 hops away

### Q18: Which suppliers appear in multiple supply chains?
```python
# Traverse from multiple tier 1 suppliers, find intersection
```
**Result**: 7 suppliers appear in multiple supply chains

---

## YELLOW - Bill of Materials Traversal (Q19-Q28)

### Q19: Full BOM explosion for "Turbo Encabulator"
```python
# Get ALL direct components of product
cur.execute("SELECT part_id FROM product_components WHERE product_id = %s", (turbo_id,))
all_roots = [row[0] for row in cur.fetchall()]

# Explode each and union results
all_parts = set()
for root_id in all_roots:
    result = bom_explode(conn, start_part_id=root_id, max_depth=20)
    all_parts.update(n['id'] for n in result['nodes'])
```
**Result**: 734 parts (from all 3 direct components), depth: 5

### Q20: Full BOM explosion with quantities for "Flux Capacitor"
```python
# Get ALL direct components of product
cur.execute("SELECT part_id FROM product_components WHERE product_id = %s", (flux_id,))
all_roots = [row[0] for row in cur.fetchall()]

# Explode each and union results
all_parts = set()
for root_id in all_roots:
    result = bom_explode(conn, start_part_id=root_id, max_depth=20, include_quantities=True)
    all_parts.update(n['id'] for n in result['nodes'])
```
**Result**: 688 parts (from all 3 direct components)

### Q21: Where is part "CHIP-001" used?
```python
result = traverse(
    conn, nodes_table="parts", edges_table="bill_of_materials",
    edge_from_col="child_part_id", edge_to_col="parent_part_id",
    start_id=chip_id, direction="outbound", max_depth=10
)
```
**Result**: Used in 1 parent assembly

### Q22: Find all products containing "RESISTOR-100" at any level
```python
# Traverse where-used, then find products
```
**Result**: Used in 2 products

### Q23: Calculate total component cost for "Turbo Encabulator"
```python
result = bom_explode(conn, start_part_id=turbo_part_id, max_depth=20, include_quantities=True)
# Sum unit_cost * quantity
```
**Result**: $5,846,557.79

### Q24: What is the deepest BOM level for any product?
```python
# Explode BOMs for all products, find max depth
```
**Result**: Maximum BOM depth: 5

### Q25: Find all leaf components in "Turbo Encabulator"
```python
# Traverse all roots, find parts with no children
all_parts = set()
for root_id in all_roots:
    result = bom_explode(conn, start_part_id=root_id, max_depth=20)
    all_parts.update(n['id'] for n in result['nodes'])

# Filter to leaf nodes (no children in BOM)
leaf_parts = [p for p in all_parts if not has_children(p)]
```
**Result**: 563 leaf components (from all 3 roots)

### Q26: Parts used in BOTH "Turbo Encabulator" AND "Flux Capacitor"
```python
# Explode both BOMs from all roots, find intersection
turbo_parts = explode_all_roots(turbo_id)  # 734 parts
flux_parts = explode_all_roots(flux_id)    # 688 parts
common = turbo_parts & flux_parts
```
**Result**: 201 common parts

### Q27: Critical path (longest chain) in "Turbo Encabulator" BOM
```python
# Find longest path in BOM
```
**Result**: 5 levels (critical path)

### Q28: Impact if "RESISTOR-100" fails
```python
result = traverse(
    conn, nodes_table="parts", edges_table="bill_of_materials",
    edge_from_col="child_part_id", edge_to_col="parent_part_id",
    start_id=resistor_id, direction="outbound", max_depth=20
)
```
**Result**: Impacts 1 assembly, depth: 2

---

## RED - Pathfinding (Q29-Q35)

### Q29: Shortest route by distance: Chicago to LA
```python
result = shortest_path(
    conn, nodes_table="facilities", edges_table="transport_routes",
    edge_from_col="origin_facility_id", edge_to_col="destination_facility_id",
    start_id=chicago_id, end_id=la_id, weight_col="distance_km"
)
```
**Result**: 2,100.0 km, 3 hops

### Q30: Cheapest route: NYC to Seattle
```python
result = shortest_path(
    conn, ..., start_id=nyc_id, end_id=seattle_id, weight_col="cost_usd"
)
```
**Result**: $5,920.57, 5 hops

### Q31: Fastest route: Chicago to Miami
```python
result = shortest_path(
    conn, ..., start_id=chicago_id, end_id=miami_id, weight_col="transit_time_hours"
)
```
**Result**: 28.0 hours, 2 hops

### Q32: All routes Chicago to LA
```python
result = all_shortest_paths(
    conn, ..., start_id=chicago_id, end_id=la_id, weight_col="distance_km"
)
```
**Result**: 1 optimal route, 2,100.0 km

### Q33: Top 3 routes NYC to LA by cost
```python
result = all_shortest_paths(
    conn, ..., start_id=nyc_id, end_id=la_id, weight_col="cost_usd", max_paths=3
)
```
**Result**: 1 optimal route, $8,109.16

### Q34: Minimum hops Chicago to LA
```python
result = shortest_path(
    conn, ..., start_id=chicago_id, end_id=la_id, weight_col=None
)
```
**Result**: 1 hop (direct connection)

### Q35: Route Chicago to Miami avoiding Denver
```python
result = shortest_path(
    conn, ..., start_id=chicago_id, end_id=miami_id, weight_col="distance_km",
    excluded_nodes=[denver_id]
)
```
**Result**: 2,100.0 km, 2 hops

---

## RED - Centrality & Connectivity (Q36-Q40)

### Q36: Most central facility (betweenness)
```python
result = centrality(
    conn, nodes_table="facilities", edges_table="transport_routes",
    edge_from_col="origin_facility_id", edge_to_col="destination_facility_id",
    centrality_type="betweenness", top_n=5
)
```
**Result**: Chicago Warehouse, score: 0.2275

### Q37: Most direct connections (degree)
```python
result = centrality(conn, ..., centrality_type="degree", top_n=5)
```
**Result**: Chicago Warehouse, score: 0.4490

### Q38: Facility importance (PageRank)
```python
result = centrality(conn, ..., centrality_type="pagerank", top_n=5)
```
**Result**: New York Factory, score: 0.0663

### Q39: Isolated facilities
```python
result = connected_components(conn, ...)
```
**Result**: 1 connected component, 0 isolated facilities

### Q40: Denver Hub removal impact
```python
result = resilience_analysis(conn, ..., node_to_remove=denver_id)
```
**Result**: 0 pairs lose connectivity, 0 new components

---

## MIXED - Cross-Complexity Patterns (Q41-Q50)

### Q41: Inventory for 100 Turbo Encabulators
**Result**: 215 parts have insufficient inventory

### Q42: Flux Capacitor components out of stock
**Result**: 0 components out of stock

### Q43: Certified suppliers in Acme's upstream network
**Result**: 31 certified suppliers

### Q44: Value at risk if Pacific Components fails
**Result**: $12,272,994.20

### Q45: Products losing ALL suppliers if Acme fails
**Result**: 0 products

### Q46: Single points of failure in Turbo Encabulator
**Result**: 67 single-source parts (SPOFs)

### Q47: Cheapest shipping route for order
**Result**: $1,500.00

### Q48: Suppliers delivering within 5 days
**Result**: 242 suppliers

### Q49: Most critical facility (connections x inventory)
**Result**: Chicago Warehouse, score: 51,397,822.85

### Q50: Cost increase if Denver fails
**Result**: $0.00 per route (alternative paths exist)

---

## Summary

| Category | Questions | Pass Rate |
|----------|-----------|-----------|
| GREEN | Q01-Q10 | 10/10 (100%) |
| YELLOW (Supplier) | Q11-Q18 | 8/8 (100%) |
| YELLOW (BOM) | Q19-Q28 | 10/10 (100%) |
| RED (Pathfinding) | Q29-Q35 | 7/7 (100%) |
| RED (Centrality) | Q36-Q40 | 5/5 (100%) |
| MIXED | Q41-Q50 | 10/10 (100%) |
| **Total** | **50** | **50/50 (100%)** |
