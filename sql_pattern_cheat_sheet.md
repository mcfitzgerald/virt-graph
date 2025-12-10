# SQL Pattern Cheat Sheet

Quick reference for Virtual Graph query patterns extracted from the benchmark.

---

## GREEN: Direct SQL

### Entity Lookup
```sql
SELECT * FROM suppliers WHERE supplier_code = 'SUP00001';
```

### Filter by Attribute
```sql
SELECT * FROM suppliers WHERE tier = 1 AND deleted_at IS NULL;
```

### Simple Join (FK relationship)
```sql
SELECT p.part_number, s.name
FROM parts p
JOIN suppliers s ON p.primary_supplier_id = s.id;
```

### Junction Table Join
```sql
SELECT p.part_number, ps.unit_cost, ps.lead_time_days
FROM suppliers s
JOIN part_suppliers ps ON s.id = ps.supplier_id
JOIN parts p ON ps.part_id = p.id
WHERE s.name = 'GlobalTech Industries';
```

### Aggregation with GROUP BY
```sql
SELECT c.name, SUM(o.total_amount) as revenue, COUNT(*) as orders
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.order_date >= NOW() - INTERVAL '3 months'
GROUP BY c.id, c.name
ORDER BY revenue DESC;
```

### Threshold Filter
```sql
SELECT p.part_number, i.quantity_on_hand, i.reorder_point
FROM inventory i
JOIN parts p ON i.part_id = p.id
WHERE i.quantity_on_hand < i.reorder_point;
```

---

## YELLOW: Handlers

### traverse() - Supplier Network

**Upstream (who sells TO me)**
```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=supplier_id,
    direction="inbound",
    max_depth=10,
    soft_delete_column="deleted_at",  # Align with Neo4j migration
)
```

**Downstream (who do I sell TO)**
```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=supplier_id,
    direction="outbound",
    max_depth=10,
    soft_delete_column="deleted_at",
)
```

### bom_explode() - Bill of Materials

**Explode (parent → children)**
```python
result = bom_explode(
    conn,
    start_part_id=part_id,
    max_depth=20,
    include_quantities=True,
    soft_delete_column="deleted_at",
)
```

### traverse() - Where-Used (child → parents)
```python
result = traverse(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="child_part_id",
    edge_to_col="parent_part_id",
    start_id=part_id,
    direction="outbound",
    max_depth=10,
)
```

---

## RED: Graph Algorithms

### shortest_path() - Weighted
```python
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=origin_id,
    end_id=dest_id,
    weight_col="distance_km",  # or "cost_usd", "transit_time_hours"
    soft_delete_column="deleted_at",
)
```

### centrality() - Find Chokepoints
```python
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",  # or "degree", "pagerank"
    top_n=10,
    soft_delete_column="deleted_at",
)
```

### connected_components() - Find Isolation
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

---

## MIXED: Combining Patterns

### Pattern: GREEN → YELLOW → GREEN
```python
# 1. GREEN: Get product parts
cur.execute("""
    SELECT pc.part_id, pc.quantity
    FROM products pr
    JOIN product_components pc ON pr.id = pc.product_id
    WHERE pr.name = 'Turbo Encabulator'
""")
parts = cur.fetchall()

# 2. YELLOW: Explode BOM
for part_id, qty in parts:
    result = bom_explode(conn, start_part_id=part_id, max_depth=20)

    # 3. GREEN: Check inventory
    for node in result['nodes']:
        cur.execute("SELECT SUM(quantity_on_hand) FROM inventory WHERE part_id = %s", (node['id'],))
```

### Pattern: YELLOW → GREEN (supplier analysis)
```python
# 1. YELLOW: Get upstream suppliers
result = traverse(conn, ..., direction="inbound")
upstream_ids = [n['id'] for n in result['nodes']]

# 2. GREEN: Filter by certification
cur.execute("""
    SELECT s.name, sc.certification_type
    FROM suppliers s
    JOIN supplier_certifications sc ON s.id = sc.supplier_id
    WHERE s.id = ANY(%s) AND sc.is_valid = true
""", (upstream_ids,))
```

### Pattern: RED → GREEN (criticality ranking)
```python
# 1. RED: Get centrality scores
result = centrality(conn, ..., centrality_type="degree")

# 2. GREEN: Enrich with business data
for item in result['results']:
    cur.execute("""
        SELECT SUM(i.quantity_on_hand * p.unit_cost)
        FROM inventory i JOIN parts p ON i.part_id = p.id
        WHERE i.facility_id = %s
    """, (item['node']['id'],))
```

---

## Direction Quick Reference

| Question Type | Edge Table | Direction | Meaning |
|--------------|------------|-----------|---------|
| Upstream suppliers | supplier_relationships | `inbound` | Who sells TO me |
| Downstream buyers | supplier_relationships | `outbound` | Who do I sell TO |
| BOM explosion | bill_of_materials | use `bom_explode()` | Parent → children |
| Where-used | bill_of_materials | `outbound` | Child → parents |

## Handler Return Values

| Handler | Key Fields |
|---------|------------|
| `traverse()` | `nodes`, `edges`, `paths`, `depth_reached` |
| `bom_explode()` | `nodes`, `edges`, `quantities`, `depth_reached` |
| `shortest_path()` | `path`, `path_nodes`, `distance` |
| `centrality()` | `results[].node`, `results[].score` |
| `connected_components()` | `components`, `component_count` |
