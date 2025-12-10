# Query Catalogue

Queries generated during the Virtual Graph benchmark session (Q01-Q50). All queries were generated in real-time by Claude Code using ontology-driven reasoning.

---

## GREEN Queries (Q01-Q10)

Direct SQL queries for simple lookups, joins, and aggregations.

### Q01: Find supplier by code

**Question**: Find the supplier with code 'SUP00001'

**Ontology Mapping**: `Supplier.supplier_code`

```sql
SELECT id, supplier_code, name, tier, country, is_active
FROM suppliers
WHERE supplier_code = 'SUP00001';
```

---

### Q02: List tier 1 suppliers

**Question**: List all tier 1 suppliers

**Ontology Mapping**: `Supplier.tier`

```sql
SELECT COUNT(*) FROM suppliers WHERE tier = 1 AND deleted_at IS NULL;

SELECT supplier_code, name
FROM suppliers
WHERE tier = 1 AND deleted_at IS NULL
ORDER BY id
LIMIT 5;
```

---

### Q03: Parts a supplier can supply

**Question**: What parts can supplier 'GlobalTech Industries' supply?

**Ontology Mapping**: `Supplier` → `CanSupply` → `Part`

```sql
SELECT p.part_number, p.description, ps.lead_time_days, ps.unit_cost
FROM suppliers s
JOIN part_suppliers ps ON s.id = ps.supplier_id
JOIN parts p ON ps.part_id = p.id
WHERE s.name = 'GlobalTech Industries'
LIMIT 5;
```

---

### Q04: Primary supplier for a part

**Question**: Who is the primary supplier for a given part?

**Ontology Mapping**: `Part` → `PrimarySupplier` → `Supplier`

```sql
SELECT p.part_number, p.description, s.name, s.tier
FROM parts p
JOIN suppliers s ON p.primary_supplier_id = s.id
WHERE p.primary_supplier_id IS NOT NULL
LIMIT 5;
```

---

### Q05: Suppliers with certification

**Question**: Which suppliers have ISO9001 certification?

**Ontology Mapping**: `Supplier` → `HasCertification` → `SupplierCertification`

```sql
SELECT DISTINCT s.supplier_code, s.name, sc.certification_number
FROM suppliers s
JOIN supplier_certifications sc ON s.id = sc.supplier_id
WHERE sc.certification_type = 'ISO9001' AND sc.is_valid = true
LIMIT 5;
```

---

### Q06: Direct components of a product

**Question**: What are the direct components of product 'Turbo Encabulator'?

**Ontology Mapping**: `Product` → `ContainsComponent` → `Part`

```sql
SELECT p.part_number, p.description, pc.quantity, p.unit_cost
FROM products pr
JOIN product_components pc ON pr.id = pc.product_id
JOIN parts p ON pc.part_id = p.id
WHERE pr.name = 'Turbo Encabulator'
ORDER BY pc.quantity DESC;
```

---

### Q07: Inventory at a facility

**Question**: Current inventory of a part at a specific facility?

**Ontology Mapping**: `Inventory` + `InventoryAt` → `Facility` + `InventoryOf` → `Part`

```sql
SELECT p.part_number, f.name, i.quantity_on_hand, i.quantity_reserved, i.reorder_point
FROM inventory i
JOIN parts p ON i.part_id = p.id
JOIN facilities f ON i.facility_id = f.id
WHERE f.name = 'Chicago Warehouse'
LIMIT 5;
```

---

### Q08: Pending orders for a customer

**Question**: List all pending orders for a customer

**Ontology Mapping**: `Customer` → `PlacedBy` → `Order`

```sql
SELECT c.name, COUNT(*) as pending_orders
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.status = 'pending'
GROUP BY c.id, c.name
HAVING COUNT(*) > 0
LIMIT 3;

SELECT o.order_number, o.order_date, o.total_amount
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.status = 'pending'
LIMIT 5;
```

---

### Q09: Revenue by customer

**Question**: Total revenue by customer for last quarter

**Ontology Mapping**: `Customer` → `PlacedBy` → `Order.total_amount`

```sql
SELECT c.name, SUM(o.total_amount) as revenue, COUNT(o.id) as orders
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.order_date >= NOW() - INTERVAL '3 months'
GROUP BY c.id, c.name
ORDER BY revenue DESC NULLS LAST
LIMIT 5;
```

---

### Q10: Parts below reorder point

**Question**: Which parts are below their reorder point?

**Ontology Mapping**: `Inventory.quantity_on_hand < reorder_point`

```sql
SELECT COUNT(*)
FROM inventory
WHERE quantity_on_hand < reorder_point AND reorder_point IS NOT NULL;

SELECT p.part_number, f.name as facility, i.quantity_on_hand, i.reorder_point
FROM inventory i
JOIN parts p ON i.part_id = p.id
JOIN facilities f ON i.facility_id = f.id
WHERE i.quantity_on_hand < i.reorder_point AND i.reorder_point IS NOT NULL
LIMIT 5;
```

---

## YELLOW Queries - Supplier Network (Q11-Q18)

Recursive traversal using `traverse()` handler on `SuppliesTo` relationship.

### Q11: Tier 2 suppliers (1 hop upstream)

**Question**: Find all tier 2 suppliers of 'Acme Corp'

**Ontology Mapping**: `SuppliesTo` (seller_id → buyer_id), direction=inbound

```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",  # Find who sells TO Acme
    max_depth=1,
    include_start=False,
)
```

**Result**: 7 tier 2 suppliers

---

### Q12: All upstream suppliers (multi-hop)

**Question**: Find all tier 2 AND tier 3 suppliers upstream from 'Acme Corp'

**Ontology Mapping**: `SuppliesTo` multi-hop traversal

```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",
    max_depth=10,
    include_start=False,
)
```

**Result**: 33 upstream suppliers (7 tier 2, 26 tier 3), depth_reached=3

---

### Q13: Downstream customers

**Question**: Who are the downstream customers (buyers) of 'Pacific Components'?

**Ontology Mapping**: `SuppliesTo`, direction=outbound

```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=pacific_id,
    direction="outbound",  # Pacific sells TO whom
    max_depth=10,
    include_start=False,
)
```

**Result**: 2 downstream buyers (tier 1)

---

### Q14: Supply path with tracking

**Question**: Trace complete supply path from 'Eastern Electronics' to any tier 1

**Ontology Mapping**: `SuppliesTo` with path tracking, stop_condition="tier = 1"

```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=eastern_id,
    direction="outbound",
    max_depth=10,
    stop_condition="tier = 1",
    include_start=True,
)

# Access paths
for tier1 in tier1_nodes:
    path = result['paths'].get(tier1['id'], [])
```

**Result**: Terminated at 2 tier 1 suppliers

---

### Q15: Network depth analysis

**Question**: What is the maximum depth of our supplier network?

**Ontology Mapping**: `SuppliesTo` depth measurement from tier 3 roots

```python
max_depth_found = 0
for start_id in tier3_ids:
    result = traverse(
        conn,
        nodes_table="suppliers",
        edges_table="supplier_relationships",
        edge_from_col="seller_id",
        edge_to_col="buyer_id",
        start_id=start_id,
        direction="outbound",
        max_depth=20,
        include_start=True,
    )
    if result['depth_reached'] > max_depth_found:
        max_depth_found = result['depth_reached']
```

**Result**: Maximum depth = 3

---

### Q16: Deepest supply chains per tier 1

**Question**: Which tier 1 suppliers have the deepest supply chains?

**Ontology Mapping**: `SuppliesTo` per-root depth analysis

```python
for supplier_id, name in tier1_suppliers:
    result = traverse(
        conn,
        nodes_table="suppliers",
        edges_table="supplier_relationships",
        edge_from_col="seller_id",
        edge_to_col="buyer_id",
        start_id=supplier_id,
        direction="inbound",
        max_depth=20,
        include_start=False,
    )
    depth_results.append((name, result['depth_reached'], len(result['nodes'])))
```

**Result**: Top is "Lewis, Perry and Rivera" with depth=3, 51 suppliers

---

### Q17: Suppliers at exact distance

**Question**: Find all suppliers exactly 2 hops from 'GlobalTech Industries'

**Ontology Mapping**: `SuppliesTo` bidirectional, filter by path length

```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=globaltech_id,
    direction="both",
    max_depth=2,
    include_start=False,
)

# Filter to exactly 2 hops (path length = 3 including start)
exactly_2_hops = [n for n in result['nodes']
                  if len(result['paths'].get(n['id'], [])) == 3]
```

**Result**: 13 suppliers at exactly 2 hops

---

### Q18: Shared suppliers (convergence)

**Question**: Which suppliers appear in multiple supply chains?

**Ontology Mapping**: SQL aggregation on `SuppliesTo` edges

```sql
WITH upstream AS (
    SELECT DISTINCT sr.seller_id as supplier_id, t1.id as tier1_id
    FROM supplier_relationships sr
    JOIN suppliers t1 ON sr.buyer_id = t1.id
    WHERE t1.tier = 1
)
SELECT s.name, s.tier, COUNT(DISTINCT tier1_id) as feeds_into
FROM suppliers s
JOIN upstream u ON s.id = u.supplier_id
WHERE s.tier > 1
GROUP BY s.id, s.name, s.tier
HAVING COUNT(DISTINCT tier1_id) > 1
ORDER BY feeds_into DESC;
```

**Result**: 10 shared suppliers (each feeding 2 tier 1 companies)

---

## YELLOW Queries - BOM Traversal (Q19-Q28)

Recursive traversal using `bom_explode()` and `traverse()` on BOM hierarchy.

### Q19: Full BOM explosion

**Question**: Full BOM explosion for product 'Turbo Encabulator'

**Ontology Mapping**: `HasComponent` (parent_part_id → child_part_id)

```python
# Get product parts first
cur.execute("""
    SELECT pc.part_id
    FROM products pr
    JOIN product_components pc ON pr.id = pc.product_id
    WHERE pr.name = 'Turbo Encabulator'
""")
turbo_parts = [row[0] for row in cur.fetchall()]

# Explode BOM for each
all_parts = set()
for part_id in turbo_parts:
    result = bom_explode(
        conn,
        start_part_id=part_id,
        max_depth=20,
        include_quantities=False,
    )
    for node in result['nodes']:
        all_parts.add(node['id'])
```

**Result**: 1,024 unique parts

---

### Q20: BOM with quantities

**Question**: Full BOM explosion with quantities for 'Flux Capacitor'

**Ontology Mapping**: `HasComponent` + quantity aggregation

```python
result = bom_explode(
    conn,
    start_part_id=part_id,
    max_depth=20,
    include_quantities=True,
)

for node in result['nodes']:
    qty = result['quantities'].get(node['id'], 1)
    print(f"{node['part_number']}: qty={qty}")
```

**Result**: 276 parts with aggregated quantities

---

### Q21: Where-used analysis

**Question**: Where is a specific part used?

**Ontology Mapping**: `ComponentOf` (child_part_id → parent_part_id)

```python
result = traverse(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="child_part_id",
    edge_to_col="parent_part_id",
    start_id=part_id,
    direction="outbound",  # child → parent (upward)
    max_depth=10,
    include_start=False,
)
```

**Result**: 113 parent assemblies for PRT-000001

---

### Q22: Products containing a part

**Question**: Find all products that contain a specific part at any level

**Ontology Mapping**: `ComponentOf` → `ContainsComponent` → `Product`

```python
# Traverse upward to find all ancestors
result = traverse(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="child_part_id",
    edge_to_col="parent_part_id",
    start_id=part_id,
    direction="outbound",
    max_depth=20,
    include_start=True,
)

ancestor_ids = [n['id'] for n in result['nodes']]

# Check which are in product_components
cur.execute("""
    SELECT DISTINCT pr.name, pr.sku
    FROM product_components pc
    JOIN products pr ON pc.product_id = pr.id
    WHERE pc.part_id = ANY(%s)
""", (ancestor_ids,))
```

**Result**: 107 products contain PRT-000001

---

### Q23: Total component cost

**Question**: Calculate total component cost for 'Turbo Encabulator'

**Ontology Mapping**: `HasComponent` + `Part.unit_cost` × quantities

```python
total_cost = 0
parts_counted = set()

for part_id in turbo_parts:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=True)
    for node in result['nodes']:
        if node['id'] not in parts_counted:
            qty = result.get('quantities', {}).get(node['id'], 1)
            unit_cost = float(node.get('unit_cost', 0) or 0)
            total_cost += unit_cost * qty
            parts_counted.add(node['id'])
```

**Result**: $18,099,239.20 total component cost

---

### Q24: Deepest BOM level

**Question**: What is the deepest BOM level for any product?

**Ontology Mapping**: `HasComponent` max depth across products

```python
max_depth = 0
deepest_product = None

for part_id, product_name in product_parts:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=False)
    if result['depth_reached'] > max_depth:
        max_depth = result['depth_reached']
        deepest_product = product_name
```

**Result**: Maximum depth = 5 levels

---

### Q25: Leaf components

**Question**: Find all leaf components (no sub-parts) in 'Turbo Encabulator'

**Ontology Mapping**: `HasComponent` terminal node detection

```python
leaf_parts = []
for part_id in turbo_parts:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=False)

    # Leaves are parts that don't appear as parents
    parents = {e[0] for e in result['edges']}
    for node in result['nodes']:
        if node['id'] not in parents:
            leaf_parts.append(node)
```

**Result**: 979 leaf components

---

### Q26: Common parts across products

**Question**: Parts used in BOTH 'Turbo Encabulator' AND 'Flux Capacitor'

**Ontology Mapping**: `HasComponent` set intersection

```python
# Get all parts in each BOM
turbo_parts_set = set()
for part_id in turbo_roots:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=False)
    for node in result['nodes']:
        turbo_parts_set.add(node['id'])

flux_parts_set = set()
for part_id in flux_roots:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=False)
    for node in result['nodes']:
        flux_parts_set.add(node['id'])

# Intersection
common_parts = turbo_parts_set & flux_parts_set
```

**Result**: 243 common parts

---

### Q27: Critical path (longest chain)

**Question**: Find the critical path in 'Turbo Encabulator' BOM

**Ontology Mapping**: `HasComponent` longest path analysis

```python
max_path_len = 0
longest_path = []

for part_id in turbo_roots:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=False)
    for node_id, path in result['paths'].items():
        if len(path) > max_path_len:
            max_path_len = len(path)
            longest_path = path
```

**Result**: 5 levels - PRT-004868 → PRT-004647 → PRT-004101 → PRT-002058 → PRT-001603

---

### Q28: Failure impact cascade

**Question**: If a part fails, trace impact through all BOM levels

**Ontology Mapping**: `ComponentOf` upward traversal + product check

```python
# Traverse upward
result = traverse(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="child_part_id",
    edge_to_col="parent_part_id",
    start_id=failed_part_id,
    direction="outbound",
    max_depth=20,
    include_start=False,
)

impacted_parts = [n['id'] for n in result['nodes']]

# Check which products are impacted
cur.execute("""
    SELECT DISTINCT pr.name
    FROM product_components pc
    JOIN products pr ON pc.product_id = pr.id
    WHERE pc.part_id = ANY(%s)
""", (impacted_parts + [failed_part_id],))
```

**Result**: 113 impacted parts, 107 impacted products

---

## RED Queries - Pathfinding (Q29-Q35)

NetworkX-based pathfinding using `shortest_path()` and `all_shortest_paths()`.

### Q29: Shortest path by distance

**Question**: Shortest route (by distance) from Chicago to LA

**Ontology Mapping**: `ConnectsTo` with weight_col="distance_km"

```python
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=facilities['Chicago Warehouse'],
    end_id=facilities['LA Distribution Center'],
    weight_col="distance_km",
)
```

**Result**: 3,388.3 km, 3 hops

---

### Q30: Cheapest route by cost

**Question**: Cheapest route from New York to West Coast

**Ontology Mapping**: `ConnectsTo` with weight_col="cost_usd"

```python
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=facilities['New York Factory'],
    end_id=west_coast[0],
    weight_col="cost_usd",
)
```

**Result**: $12,275.81

---

### Q31: Fastest route by time

**Question**: Fastest route by transit time

**Ontology Mapping**: `ConnectsTo` with weight_col="transit_time_hours"

```python
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=southern_id,
    weight_col="transit_time_hours",
)
```

---

### Q32: All shortest paths

**Question**: All routes from Chicago to LA

**Ontology Mapping**: `ConnectsTo` all_shortest_paths()

```python
result = all_shortest_paths(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=facilities['Chicago Warehouse'],
    end_id=facilities['LA Distribution Center'],
    weight_col="distance_km",
    max_paths=5,
)
```

**Result**: 1 optimal path at 3,388.3 km

---

### Q33: K-shortest paths by cost

**Question**: Top 3 alternative routes by cost

**Ontology Mapping**: `ConnectsTo` k-shortest paths

```python
result = all_shortest_paths(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=facilities['New York Factory'],
    end_id=facilities['LA Distribution Center'],
    weight_col="cost_usd",
    max_paths=3,
)
```

---

### Q34: Minimum hops (unweighted)

**Question**: Minimum number of hops from Chicago to LA

**Ontology Mapping**: `ConnectsTo` unweighted (weight_col=None)

```python
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=facilities['Chicago Warehouse'],
    end_id=facilities['LA Distribution Center'],
    weight_col=None,  # Unweighted = hop count
)
```

**Result**: 3 hops

---

### Q35: Constrained path (avoid node)

**Question**: Route avoiding a specific hub

**Ontology Mapping**: `ConnectsTo` with post-filtering (workaround)

```python
# Get multiple paths and filter
result = all_shortest_paths(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="distance_km",
    max_paths=10,
)

# Filter out paths containing hub_to_avoid
valid_paths = [p for p in result['paths'] if hub_to_avoid[0] not in p]
```

**Note**: Limitation - no native excluded_nodes parameter

---

## RED Queries - Centrality & Connectivity (Q36-Q40)

NetworkX-based analytics using `centrality()` and `connected_components()`.

### Q36: Betweenness centrality (chokepoints)

**Question**: Which facility is most central?

**Ontology Mapping**: `ConnectsTo` betweenness_centrality

```python
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10,
)
```

**Result**: New York Factory (score=0.2327)

---

### Q37: Degree centrality (most connections)

**Question**: Which facility has the most direct connections?

**Ontology Mapping**: `ConnectsTo` degree_centrality

```python
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="degree",
    top_n=10,
)
```

**Result**: New York Factory (score=0.4082)

---

### Q38: PageRank (importance)

**Question**: Rank facilities by importance to network flow

**Ontology Mapping**: `ConnectsTo` pagerank

```python
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="pagerank",
    top_n=10,
)
```

**Result**: New York Factory (score=0.0535)

---

### Q39: Connected components

**Question**: Are there any isolated facilities?

**Ontology Mapping**: `ConnectsTo` connected_components

```python
result = connected_components(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    min_size=1,
)
```

**Result**: 1 component, 50 nodes, 0 isolated - fully connected!

---

### Q40: Resilience analysis

**Question**: If hub goes offline, which pairs lose connectivity?

**Ontology Mapping**: `ConnectsTo` betweenness as proxy for criticality

```python
# Find most critical node
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=1,
)
critical_hub = result['results'][0]['node']
```

**Note**: Full resilience analysis would require graph modification

---

## MIXED Queries (Q41-Q50)

Cross-complexity patterns combining GREEN lookups with YELLOW/RED operations.

### Q41: Inventory sufficiency for production

**Question**: Sufficient inventory to build 100 units of 'Turbo Encabulator'?

**Pattern**: GREEN (product lookup) → YELLOW (BOM explosion) → GREEN (inventory check)

```python
BUILD_QUANTITY = 100
shortages = []

# GREEN: Get product parts
cur.execute("""
    SELECT pc.part_id, pc.quantity
    FROM products pr
    JOIN product_components pc ON pr.id = pc.product_id
    WHERE pr.name = 'Turbo Encabulator'
""")
turbo_direct_parts = cur.fetchall()

for part_id, direct_qty in turbo_direct_parts:
    # YELLOW: Explode BOM
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=True)

    for node in result['nodes']:
        qty_needed = result['quantities'].get(node['id'], 1) * direct_qty * BUILD_QUANTITY

        # GREEN: Check inventory
        cur.execute("""
            SELECT SUM(quantity_on_hand - quantity_reserved)
            FROM inventory WHERE part_id = %s
        """, (node['id'],))
        available = cur.fetchone()[0] or 0

        if available < qty_needed:
            shortages.append((node['part_number'], qty_needed, available))
```

**Result**: 1,056 parts with shortages

---

### Q42: Out of stock components

**Question**: Which components of 'Flux Capacitor' are currently out of stock?

**Pattern**: GREEN → YELLOW → GREEN (filter available <= 0)

```python
out_of_stock = []
for part_id in flux_parts:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=False)

    for node in result['nodes']:
        cur.execute("""
            SELECT COALESCE(SUM(quantity_on_hand - quantity_reserved), 0)
            FROM inventory WHERE part_id = %s
        """, (node['id'],))
        available = cur.fetchone()[0]

        if available <= 0:
            out_of_stock.append(node)
```

**Result**: 16 out-of-stock components

---

### Q43: Certified suppliers in network

**Question**: Find all certified suppliers in 'Acme Corp' tier 2+ supply network

**Pattern**: GREEN (supplier) → YELLOW (network traversal) → GREEN (certification join)

```python
# YELLOW: Traverse upstream
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",
    max_depth=10,
    include_start=False,
)
upstream_ids = [n['id'] for n in result['nodes']]

# GREEN: Check certifications
cur.execute("""
    SELECT DISTINCT s.name, sc.certification_type
    FROM suppliers s
    JOIN supplier_certifications sc ON s.id = sc.supplier_id
    WHERE s.id = ANY(%s) AND sc.is_valid = true
""", (upstream_ids,))
```

**Result**: 24 certified suppliers out of 33 upstream

---

### Q44: Value at risk from supplier failure

**Question**: Total value at risk if 'Pacific Components' fails?

**Pattern**: GREEN (supplier) → YELLOW (network) → GREEN (cost aggregation)

```python
# YELLOW: Find downstream impact
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=pacific_id,
    direction="outbound",
    max_depth=10,
    include_start=False,
)

# GREEN: Calculate inventory value at risk
cur.execute("""
    SELECT SUM(i.quantity_on_hand * p.unit_cost)
    FROM part_suppliers ps
    JOIN parts p ON ps.part_id = p.id
    JOIN inventory i ON p.id = i.part_id
    WHERE ps.supplier_id = %s
""", (pacific_id,))
value_at_risk = cur.fetchone()[0]
```

**Result**: $3,118,610.43 at risk

---

### Q45: Products losing all suppliers

**Question**: If 'Acme Corp' fails, which products lose ALL their suppliers?

**Pattern**: YELLOW (network) → GREEN (supplier cardinality check)

```python
# Get Acme network
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",
    max_depth=10,
    include_start=True,
)
acme_network_ids = [n['id'] for n in result['nodes']]

# Find parts ONLY supplied by Acme network
cur.execute("""
    WITH acme_only_parts AS (
        SELECT ps.part_id
        FROM part_suppliers ps
        GROUP BY ps.part_id
        HAVING EVERY(ps.supplier_id = ANY(%s))
    )
    SELECT DISTINCT pr.name
    FROM acme_only_parts aop
    JOIN product_components pc ON pc.part_id = aop.part_id
    JOIN products pr ON pc.product_id = pr.id
""", (acme_network_ids,))
```

**Result**: 2 products lose all suppliers

---

### Q46: Single points of failure

**Question**: Single points of failure in 'Turbo Encabulator' supply chain

**Pattern**: YELLOW (BOM) → GREEN (supplier count = 1)

```python
single_source_parts = []
for part_id in turbo_parts:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20, include_quantities=False)

    for node in result['nodes']:
        cur.execute("""
            SELECT COUNT(DISTINCT supplier_id)
            FROM part_suppliers WHERE part_id = %s
        """, (node['id'],))
        supplier_count = cur.fetchone()[0]

        if supplier_count == 1:
            single_source_parts.append(node)
```

**Result**: 306 single-source parts (30% of BOM)

---

### Q47: Cheapest shipping route for order

**Question**: Find cheapest shipping route for a specific order

**Pattern**: GREEN (order lookup) → RED (pathfinding)

```python
# GREEN: Get order's shipping facility
cur.execute("""
    SELECT o.shipping_facility_id, f.name
    FROM orders o
    JOIN facilities f ON o.shipping_facility_id = f.id
    WHERE o.order_number = 'ORD-00000001'
""")
ship_from_id = cur.fetchone()[0]

# RED: Find cheapest route
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=ship_from_id,
    end_id=destination_id,
    weight_col="cost_usd",
)
```

---

### Q48: Suppliers within lead time

**Question**: Suppliers that could fulfill order within 5 days

**Pattern**: GREEN (order → product) → YELLOW (BOM) → GREEN (lead_time filter)

```python
# GREEN: Get order products
cur.execute("""
    SELECT oi.product_id FROM order_items oi WHERE oi.order_id = %s
""", (order_id,))

# Get product parts
cur.execute("SELECT part_id FROM product_components WHERE product_id = %s", (product_id,))
part_ids = [row[0] for row in cur.fetchall()]

# GREEN: Find fast suppliers
cur.execute("""
    SELECT DISTINCT s.name, ps.lead_time_days
    FROM part_suppliers ps
    JOIN suppliers s ON ps.supplier_id = s.id
    WHERE ps.part_id = ANY(%s) AND ps.lead_time_days <= 5
""", (part_ids,))
```

---

### Q49: Facility criticality ranking

**Question**: Rank facilities by criticality (connections × inventory value)

**Pattern**: RED (centrality) → GREEN (inventory aggregation)

```python
# RED: Get degree centrality
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="degree",
    top_n=50,
)

# GREEN: Calculate inventory value per facility
for item in result['results']:
    facility_id = item['node']['id']
    degree_score = item['score']

    cur.execute("""
        SELECT COALESCE(SUM(i.quantity_on_hand * p.unit_cost), 0)
        FROM inventory i
        JOIN parts p ON i.part_id = p.id
        WHERE i.facility_id = %s
    """, (facility_id,))
    inventory_value = float(cur.fetchone()[0])

    criticality = degree_score * (inventory_value / 1000000)
```

**Result**: Top is North Melaniestad (criticality=24.76)

---

### Q50: Hub failure cost impact

**Question**: If hub fails, cost increase for pending orders?

**Pattern**: RED (centrality) → GREEN (order aggregation)

```python
# RED: Find most critical hub
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=1,
)
critical_hub = result['results'][0]['node']

# GREEN: Count affected orders
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(shipping_cost), 0)
    FROM orders
    WHERE status = 'pending' AND shipping_facility_id = %s
""", (critical_hub['id'],))
```

**Result**: New York Factory: 79 pending orders, $8,100.44 shipping cost

---

## Summary

| Complexity | Questions | Query Type |
|------------|-----------|------------|
| GREEN | Q01-Q10 | Direct SQL |
| YELLOW (Supplier) | Q11-Q18 | `traverse()` on supplier_relationships |
| YELLOW (BOM) | Q19-Q28 | `bom_explode()` / `traverse()` on bill_of_materials |
| RED | Q29-Q40 | `shortest_path()`, `centrality()`, `connected_components()` |
| MIXED | Q41-Q50 | GREEN + YELLOW/RED combinations |

**Key Insight**: All queries were generated in real-time using ontology-driven reasoning. The ontology provided table/column mappings, and Claude Code determined the appropriate query strategy based on relationship complexity annotations.
