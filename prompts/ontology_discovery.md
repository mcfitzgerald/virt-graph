# Ontology Discovery & Validation Primer

**Goal**: Discover the supply chain ontology from PostgreSQL, output `ontology/supply_chain.yaml` in TBox/RBox format, and validate it.

---

## Database Connection

```
postgresql://virt_graph:dev_password@localhost:5432/supply_chain
```

PostgreSQL 14 with ~130K rows across 15 tables.

---

## Phase 1: Discovery Protocol (4 Rounds)

### Round 1: Schema Introspection
Run SQL introspection to discover:
- All tables with columns and types
- Foreign key relationships
- Self-referential edge tables (graph traversal candidates)
- Constraints (unique, check, not null)

```sql
-- Tables and columns
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

-- Foreign keys
SELECT tc.table_name, kcu.column_name,
       ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';

-- Check constraints (self-reference prevention)
SELECT tc.table_name, tc.constraint_name, cc.check_clause
FROM information_schema.table_constraints tc
JOIN information_schema.check_constraints cc
  ON tc.constraint_name = cc.constraint_name
WHERE tc.constraint_type = 'CHECK';

-- Unique constraints
SELECT tc.table_name, kcu.column_name, tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'UNIQUE';
```

### Round 2: Class Proposals (TBox)
For each table, propose a class:
- Map table → class name (semantic naming)
- Identify primary key and natural identifier columns
- Map columns → slots with appropriate ranges
- Note soft delete patterns (`deleted_at`)

**Expected classes**: Supplier, Part, Product, Facility, Customer, Order, Shipment, SupplierCertification

### Round 3: Relationship Proposals (RBox)
For each FK relationship, propose a role:
- Assign domain (source class) and range (target class)
- Map to SQL (table, domain_key, range_key)
- Set OWL 2 properties (transitive, symmetric, asymmetric, etc.)
- Set Virtual Graph properties (acyclic, is_hierarchical, is_weighted)
- Assign traversal complexity:
  - **GREEN**: Simple FK join
  - **YELLOW**: Recursive traversal (self-referential)
  - **RED**: Network algorithm (weighted paths)

**Key edge tables**:
| Table | Pattern | Expected Complexity |
|-------|---------|---------------------|
| `supplier_relationships` | seller_id → buyer_id (self-ref) | YELLOW |
| `bill_of_materials` | parent_part_id → child_part_id (self-ref) | YELLOW |
| `transport_routes` | origin → destination (weighted) | RED |

### Round 4: Draft Review
- Human reviews proposed TBox/RBox
- Corrections for business semantics
- Finalize `ontology/supply_chain.yaml`

---

## Phase 2: Validation Protocol

After discovery, validate the ontology against the actual data.

### 2.1 Row Count Validation
Verify `row_count` estimates in the ontology match actual data:

```sql
-- Count all tables
SELECT 'suppliers' as table_name, COUNT(*) FROM suppliers WHERE deleted_at IS NULL
UNION ALL SELECT 'parts', COUNT(*) FROM parts WHERE deleted_at IS NULL
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'facilities', COUNT(*) FROM facilities
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'shipments', COUNT(*) FROM shipments
UNION ALL SELECT 'supplier_certifications', COUNT(*) FROM supplier_certifications
UNION ALL SELECT 'supplier_relationships', COUNT(*) FROM supplier_relationships
UNION ALL SELECT 'bill_of_materials', COUNT(*) FROM bill_of_materials
UNION ALL SELECT 'transport_routes', COUNT(*) FROM transport_routes
UNION ALL SELECT 'part_suppliers', COUNT(*) FROM part_suppliers
UNION ALL SELECT 'product_components', COUNT(*) FROM product_components
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'inventory', COUNT(*) FROM inventory;
```

### 2.2 Referential Integrity Validation
Verify all FKs resolve (no orphans):

```sql
-- Example: Check supplier_relationships integrity
SELECT COUNT(*) as orphan_sellers
FROM supplier_relationships sr
LEFT JOIN suppliers s ON sr.seller_id = s.id
WHERE s.id IS NULL;

SELECT COUNT(*) as orphan_buyers
FROM supplier_relationships sr
LEFT JOIN suppliers s ON sr.buyer_id = s.id
WHERE s.id IS NULL;

-- Check BOM integrity
SELECT COUNT(*) as orphan_parents
FROM bill_of_materials bom
LEFT JOIN parts p ON bom.parent_part_id = p.id
WHERE p.id IS NULL;
```

### 2.3 DAG Validation (Acyclic Properties)
For relationships marked `acyclic: true`, verify no cycles exist:

```sql
-- Supplier relationships: verify tier hierarchy (no back edges)
WITH RECURSIVE chain AS (
    SELECT seller_id, buyer_id, ARRAY[seller_id] as path, 1 as depth
    FROM supplier_relationships
    UNION ALL
    SELECT sr.seller_id, sr.buyer_id, c.path || sr.seller_id, c.depth + 1
    FROM supplier_relationships sr
    JOIN chain c ON sr.seller_id = c.buyer_id
    WHERE NOT sr.seller_id = ANY(c.path)
      AND c.depth < 20
)
SELECT COUNT(*) as cycle_count
FROM chain c
JOIN supplier_relationships sr ON sr.seller_id = c.buyer_id
WHERE sr.buyer_id = ANY(c.path);

-- BOM: verify no circular dependencies
WITH RECURSIVE bom_chain AS (
    SELECT parent_part_id, child_part_id, ARRAY[parent_part_id] as path
    FROM bill_of_materials
    UNION ALL
    SELECT bom.parent_part_id, bom.child_part_id, bc.path || bom.parent_part_id
    FROM bill_of_materials bom
    JOIN bom_chain bc ON bom.parent_part_id = bc.child_part_id
    WHERE NOT bom.parent_part_id = ANY(bc.path)
      AND array_length(bc.path, 1) < 20
)
SELECT COUNT(*) as cycle_count
FROM bom_chain bc
JOIN bill_of_materials bom ON bom.parent_part_id = bc.child_part_id
WHERE bom.child_part_id = ANY(bc.path);
```

### 2.4 Graph Property Validation

**Tier Structure** (for `is_hierarchical: true`):
```sql
-- Supplier tier distribution
SELECT s_seller.tier as seller_tier, s_buyer.tier as buyer_tier, COUNT(*)
FROM supplier_relationships sr
JOIN suppliers s_seller ON sr.seller_id = s_seller.id
JOIN suppliers s_buyer ON sr.buyer_id = s_buyer.id
GROUP BY s_seller.tier, s_buyer.tier
ORDER BY seller_tier, buyer_tier;
-- Expected: Higher tiers sell to lower tiers (T3→T2→T1)
```

**BOM Depth Statistics**:
```sql
-- BOM tree depth distribution
WITH RECURSIVE bom_depth AS (
    SELECT parent_part_id, child_part_id, 1 as depth
    FROM bill_of_materials
    WHERE parent_part_id NOT IN (SELECT child_part_id FROM bill_of_materials)
    UNION ALL
    SELECT bom.parent_part_id, bom.child_part_id, bd.depth + 1
    FROM bill_of_materials bom
    JOIN bom_depth bd ON bom.parent_part_id = bd.child_part_id
    WHERE bd.depth < 20
)
SELECT MAX(depth) as max_depth, AVG(depth) as avg_depth
FROM bom_depth;
```

**Transport Network Connectivity**:
```sql
-- Check if transport network is connected (has spanning tree potential)
SELECT COUNT(DISTINCT origin_facility_id) as origins,
       COUNT(DISTINCT destination_facility_id) as destinations,
       COUNT(*) as total_routes
FROM transport_routes
WHERE is_active = true;
```

### 2.5 Weighted Edge Validation
For relationships marked `is_weighted: true`:

```sql
-- Transport route weight distribution
SELECT transport_mode,
       MIN(distance_km) as min_dist, MAX(distance_km) as max_dist, AVG(distance_km) as avg_dist,
       MIN(cost_usd) as min_cost, MAX(cost_usd) as max_cost, AVG(cost_usd) as avg_cost
FROM transport_routes
GROUP BY transport_mode;
```

### 2.6 Gate Test Validation
Run the automated gate tests:

```bash
poetry run pytest tests/test_gate2_validation.py -v
```

Expected tests:
- Ontology file exists and parses
- All classes have required fields
- All relationships have required fields
- Traversal handlers work with ontology mappings
- Row counts match expectations

---

## Output Format

Output file: `ontology/supply_chain.yaml`

See `ontology/TEMPLATE.yaml` for full structure. Key sections:

```yaml
meta:
  name: supply_chain
  version: "1.0"
  created: "YYYY-MM-DD"
  format: tbox-rbox
  database:
    type: postgresql
    version: "14"
    connection: "postgresql://virt_graph:dev_password@localhost:5432/supply_chain"

tbox:
  classes:
    ClassName:
      description: "..."
      sql:
        table: table_name
        primary_key: id
        identifier: [natural_key]
      slots:
        attr_name:
          range: string|integer|decimal|boolean|date|timestamp
          column: sql_column
          required: true|false
      soft_delete:
        enabled: true
        column: deleted_at
      row_count: 1000

rbox:
  roles:
    role_name:
      description: "..."
      domain: SourceClass
      range: TargetClass
      sql:
        table: edge_table
        domain_key: fk_source
        range_key: fk_target
        additional_columns: [col1, col2]
        weight_columns:
          - name: cost_usd
            type: decimal
      properties:
        transitive: false
        symmetric: false
        asymmetric: true
        reflexive: false
        irreflexive: true
        functional: false
        inverse_functional: false
        inverse_of: inverse_role_name
        acyclic: true
        is_hierarchical: true
        is_weighted: false
      cardinality:
        domain: "0..*"
        range: "0..*"
      traversal_complexity: GREEN|YELLOW|RED
      row_count: 1000
```

---

## Quick Reference

### OWL 2 Properties
| Property | Definition | Example |
|----------|------------|---------|
| transitive | A→B, B→C ⇒ A→C | ancestor_of |
| symmetric | A→B ⇒ B→A | sibling_of |
| asymmetric | A→B ⇒ ¬B→A | parent_of |
| reflexive | A→A valid | knows_self |
| irreflexive | A→A invalid | component_of |
| functional | max 1 target | has_primary_supplier |
| inverse_functional | max 1 source | is_primary_supplier_of |

### Traversal Complexity
| Color | When | Handler |
|-------|------|---------|
| GREEN | Simple FK join | None (direct SQL) |
| YELLOW | Recursive (self-ref edges) | `traverse()` |
| RED | Network algorithm (weighted) | NetworkX handlers |

### Cardinality Notation
| Notation | Meaning |
|----------|---------|
| "1..1" | Exactly one (required) |
| "0..1" | Zero or one (optional) |
| "1..*" | One or more |
| "0..*" | Zero or more |

---

## Session Flow

1. **Round 1**: Schema introspection → human reviews findings
2. **Round 2**: TBox proposals → human corrects class names/semantics
3. **Round 3**: RBox proposals → human corrects relationship semantics
4. **Round 4**: Draft review → human approves final ontology
5. **Validation**: Run all validation queries → fix any issues
6. **Gate Tests**: `poetry run pytest tests/test_gate2_validation.py -v`
