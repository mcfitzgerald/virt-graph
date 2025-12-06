# Pattern Discovery Primer

**Goal**: Explore the supply chain database to discover and document query patterns, outputting raw patterns to `patterns/raw/`.

**Prerequisites**:
- Completed ontology discovery (`ontology/supply_chain.yaml` exists)
- PostgreSQL running

---

## Database Connection

```
postgresql://virt_graph:dev_password@localhost:5432/supply_chain
```

---

## Pattern Categories

Discover patterns across three complexity tiers:

### GREEN Patterns (Simple SQL)
Direct lookups and joins that don't require handlers.

**Discovery queries**:
```sql
-- Supplier lookup by name
SELECT * FROM suppliers WHERE name = 'Acme Corp';

-- Parts by supplier
SELECT p.* FROM parts p
JOIN suppliers s ON p.primary_supplier_id = s.id
WHERE s.name = 'Acme Corp';

-- Customer orders
SELECT o.* FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE c.name LIKE '%Corp%';

-- Facility inventory
SELECT p.part_number, i.quantity_on_hand
FROM inventory i
JOIN parts p ON i.part_id = p.id
JOIN facilities f ON i.facility_id = f.id
WHERE f.name = 'Chicago Warehouse';
```

### YELLOW Patterns (Recursive Traversal)
Self-referential relationships requiring `traverse()` handler.

**Supplier Tier Traversal**:
```sql
-- Upstream suppliers (who supplies my suppliers?)
WITH RECURSIVE upstream AS (
    SELECT seller_id, buyer_id, 1 as depth
    FROM supplier_relationships
    WHERE buyer_id = (SELECT id FROM suppliers WHERE name = 'Acme Corp')
    UNION ALL
    SELECT sr.seller_id, sr.buyer_id, u.depth + 1
    FROM supplier_relationships sr
    JOIN upstream u ON sr.buyer_id = u.seller_id
    WHERE u.depth < 10
)
SELECT DISTINCT s.*, u.depth
FROM upstream u
JOIN suppliers s ON u.seller_id = s.id
ORDER BY u.depth, s.name;

-- Downstream customers (who do we supply to?)
WITH RECURSIVE downstream AS (
    SELECT seller_id, buyer_id, 1 as depth
    FROM supplier_relationships
    WHERE seller_id = (SELECT id FROM suppliers WHERE name = 'Acme Corp')
    UNION ALL
    SELECT sr.seller_id, sr.buyer_id, d.depth + 1
    FROM supplier_relationships sr
    JOIN downstream d ON sr.seller_id = d.buyer_id
    WHERE d.depth < 10
)
SELECT DISTINCT s.*, d.depth
FROM downstream d
JOIN suppliers s ON d.buyer_id = s.id
ORDER BY d.depth, s.name;
```

**BOM Explosion**:
```sql
-- What components make up this part? (explode downward)
WITH RECURSIVE bom_explosion AS (
    SELECT parent_part_id, child_part_id, quantity, 1 as depth,
           ARRAY[parent_part_id] as path
    FROM bill_of_materials
    WHERE parent_part_id = (SELECT id FROM parts WHERE part_number = 'TURBO-001')
    UNION ALL
    SELECT bom.parent_part_id, bom.child_part_id, bom.quantity,
           be.depth + 1, be.path || bom.parent_part_id
    FROM bill_of_materials bom
    JOIN bom_explosion be ON bom.parent_part_id = be.child_part_id
    WHERE be.depth < 10 AND NOT bom.parent_part_id = ANY(be.path)
)
SELECT p.part_number, p.description, be.quantity, be.depth
FROM bom_explosion be
JOIN parts p ON be.child_part_id = p.id
ORDER BY be.depth, p.part_number;

-- Where is this part used? (explode upward)
WITH RECURSIVE where_used AS (
    SELECT parent_part_id, child_part_id, quantity, 1 as depth
    FROM bill_of_materials
    WHERE child_part_id = (SELECT id FROM parts WHERE part_number = 'WIDGET-A')
    UNION ALL
    SELECT bom.parent_part_id, bom.child_part_id, bom.quantity, wu.depth + 1
    FROM bill_of_materials bom
    JOIN where_used wu ON bom.child_part_id = wu.parent_part_id
    WHERE wu.depth < 10
)
SELECT p.part_number, p.description, wu.depth
FROM where_used wu
JOIN parts p ON wu.parent_part_id = p.id
ORDER BY wu.depth, p.part_number;
```

**Impact Analysis**:
```sql
-- If supplier X fails, what parts/products are affected?
WITH RECURSIVE affected_parts AS (
    SELECT id as part_id, 0 as depth
    FROM parts
    WHERE primary_supplier_id = (SELECT id FROM suppliers WHERE name = 'Acme Corp')
    UNION ALL
    SELECT bom.parent_part_id, ap.depth + 1
    FROM bill_of_materials bom
    JOIN affected_parts ap ON bom.child_part_id = ap.part_id
    WHERE ap.depth < 10
)
SELECT DISTINCT p.part_number, p.description, ap.depth as impact_level
FROM affected_parts ap
JOIN parts p ON ap.part_id = p.id
ORDER BY ap.depth, p.part_number;
```

### RED Patterns (Network Algorithms)
Weighted graph algorithms requiring NetworkX handlers.

**Shortest Path**:
```sql
-- Find optimal route between facilities (for NetworkX input)
SELECT tr.origin_facility_id, tr.destination_facility_id,
       tr.distance_km, tr.cost_usd, tr.transit_time_hours,
       f1.name as origin_name, f2.name as dest_name
FROM transport_routes tr
JOIN facilities f1 ON tr.origin_facility_id = f1.id
JOIN facilities f2 ON tr.destination_facility_id = f2.id
WHERE tr.is_active = true;
```

**Centrality Analysis**:
```sql
-- Facility connectivity for centrality calculation
SELECT origin_facility_id, destination_facility_id, COUNT(*) as route_count
FROM transport_routes
WHERE is_active = true
GROUP BY origin_facility_id, destination_facility_id;

-- Supplier network for PageRank
SELECT seller_id, buyer_id,
       CASE WHEN is_primary THEN 2.0 ELSE 1.0 END as weight
FROM supplier_relationships;
```

**Connected Components**:
```sql
-- Check for isolated facility clusters
SELECT f.facility_code, f.name,
       (SELECT COUNT(*) FROM transport_routes WHERE origin_facility_id = f.id) as outbound,
       (SELECT COUNT(*) FROM transport_routes WHERE destination_facility_id = f.id) as inbound
FROM facilities f
WHERE f.is_active = true
ORDER BY outbound + inbound;
```

---

## Pattern Output Format

For each discovered pattern, create a YAML file in `patterns/raw/`:

```yaml
# patterns/raw/{pattern_name}_{sequence}.yaml

name: pattern_name
version: "1.0"
discovered: "YYYY-MM-DD"
complexity: GREEN | YELLOW | RED

description: |
  Human-readable description of what this pattern does
  and when to use it.

applicability:
  keywords:
    - "keyword1"
    - "keyword2"
  intent: "user intent description"

ontology_bindings:
  classes:
    - ClassName1
    - ClassName2
  relationships:
    - role_name1
    - role_name2

parameters:
  - name: param_name
    type: string | integer | id
    description: "What this parameter represents"
    required: true | false
    default: "optional default value"

sql_template: |
  -- SQL with {{param_name}} placeholders
  SELECT * FROM table WHERE col = {{param_name}};

handler:
  name: handler_function_name  # For YELLOW/RED only
  module: virt_graph.handlers.module_name
  params:
    - nodes_table
    - edges_table
    - start_id
    - direction
    - max_depth

example_queries:
  - natural_language: "Find all suppliers upstream of Acme Corp"
    parameters:
      start_entity: "Acme Corp"
      direction: "upstream"
      max_depth: 5

validation:
  test_query: "SELECT COUNT(*) FROM ..."
  expected_behavior: "Returns N rows for test entity"
```

---

## Discovery Protocol

### Step 1: Explore Named Entities
Use the named test entities for exploration:

| Entity Type | Name | Code |
|-------------|------|------|
| Supplier | Acme Corp | SUP00001 |
| Supplier | GlobalTech Industries | SUP00002 |
| Supplier | Pacific Components | - |
| Product | Turbo Encabulator | TURBO-001 |
| Product | Flux Capacitor | FLUX-001 |
| Facility | Chicago Warehouse | FAC-CHI |
| Facility | LA Distribution Center | FAC-LA |

### Step 2: Run Exploration Queries
Execute each category of queries above, noting:
- Execution time
- Row counts
- Edge cases encountered

### Step 3: Document Patterns
For each successful query pattern:
1. Create `patterns/raw/{name}_{seq}.yaml`
2. Fill in the template
3. Include working SQL

### Step 4: Map to Templates
Match raw patterns to existing templates in `patterns/templates/`:

| Raw Pattern | Template | Handler |
|-------------|----------|---------|
| upstream_suppliers | `traversal/tier_traversal.yaml` | `traverse()` |
| downstream_customers | `traversal/tier_traversal.yaml` | `traverse()` |
| bom_explosion | `traversal/bom_explosion.yaml` | `bom_explode()` |
| where_used | `traversal/where_used.yaml` | `traverse()` |
| impact_analysis | `aggregation/impact_analysis.yaml` | `traverse_collecting()` |
| shortest_path | `pathfinding/shortest_path.yaml` | `shortest_path()` |
| centrality | `network-analysis/centrality.yaml` | `centrality()` |
| components | `network-analysis/components.yaml` | `connected_components()` |

### Step 5: Validate with Gate Tests
```bash
poetry run pytest tests/test_gate3_validation.py -v
```

---

## Expected Raw Patterns

By end of discovery, `patterns/raw/` should contain:

```
patterns/raw/
├── supplier_tier_traversal_001.yaml
├── upstream_suppliers_001.yaml
├── downstream_customers_001.yaml
├── bom_explosion_001.yaml
├── where_used_001.yaml
├── impact_analysis_001.yaml
├── shortest_path_cost_001.yaml
├── shortest_path_time_001.yaml
├── centrality_betweenness_001.yaml
├── connected_components_001.yaml
└── supply_chain_depth_001.yaml
```

---

## Session Flow

1. **GREEN exploration**: Run simple lookups, document findings
2. **YELLOW exploration**: Run recursive CTEs, time them, document
3. **RED exploration**: Prepare NetworkX inputs, run algorithms
4. **Pattern documentation**: Create raw pattern files
5. **Template mapping**: Link to existing templates
6. **Gate validation**: `poetry run pytest tests/test_gate3_validation.py -v`
