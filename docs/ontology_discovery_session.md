# Ontology Discovery Session

This document records the ontology discovery process for the Virtual Graph supply chain database.

## Overview

**Date**: 2024-12-04
**Database**: PostgreSQL 14
**Schema**: supply_chain
**Discovery Rounds**: 3

## Round 1: Schema Introspection

### Process

Ran introspection queries from `.claude/skills/schema/scripts/introspect.sql` against the `information_schema` to discover:

1. **Tables and Columns**: 16 tables discovered (15 domain + 1 audit)
2. **Foreign Keys**: 22 FK relationships identified
3. **Primary Keys**: All tables use `id` as PK
4. **Unique Constraints**: 7 natural identifiers (supplier_code, part_number, etc.)

### Initial Findings

#### Tables Discovered (by row count)

| Table | Row Count | Domain |
|-------|-----------|--------|
| order_items | 60,241 | Orders |
| orders | 20,000 | Orders |
| bill_of_materials | 14,283 | Parts |
| inventory | 10,056 | Inventory |
| shipments | 7,995 | Shipments |
| part_suppliers | 7,582 | Parts |
| parts | 5,003 | Parts |
| customers | 1,000 | Orders |
| supplier_relationships | 817 | Suppliers |
| supplier_certifications | 721 | Suppliers |
| product_components | 619 | Products |
| suppliers | 500 | Suppliers |
| products | 200 | Products |
| transport_routes | 197 | Facilities |
| facilities | 50 | Facilities |
| audit_log | 0 | Utility |

#### Self-Referential Edge Tables Identified

Three tables were identified as graph edge tables (self-referential FK patterns):

1. **supplier_relationships**
   - `seller_id` → `suppliers.id`
   - `buyer_id` → `suppliers.id`
   - Confidence: HIGH (explicit FK constraint with `no_self_supply` check)

2. **bill_of_materials**
   - `child_part_id` → `parts.id`
   - `parent_part_id` → `parts.id`
   - Confidence: HIGH (explicit FK constraint with `no_self_reference` check)

3. **transport_routes**
   - `origin_facility_id` → `facilities.id`
   - `destination_facility_id` → `facilities.id`
   - Confidence: HIGH (explicit FK constraint with `no_same_facility` check)

### Questions Generated

After Round 1, the following questions required business context:

1. **supplier_relationships**: What does the seller→buyer direction represent? Is this a tiered supply chain?
2. **bill_of_materials**: What does child→parent mean? Which direction represents "contains"?
3. **transport_routes**: Are routes bidirectional or asymmetric? What weights are relevant?
4. **suppliers.tier**: What do values 1, 2, 3 represent in business terms?

## Round 2: Business Context Interview

### Supplier Relationships

**Q: What does the seller_id → buyer_id relationship represent?**

A: This represents the tiered supply chain structure:
- Tier 3 suppliers (raw materials) SELL TO Tier 2 suppliers
- Tier 2 suppliers (components) SELL TO Tier 1 suppliers
- Tier 1 suppliers (direct) SELL TO us (implicit)
- Direction: `seller_id → buyer_id` means "supplies to"

**Q: Is this relationship strictly directional?**

A: Yes, it's directional. A tier 3 supplier never buys from tier 1.

**Q: Can a supplier relate to itself?**

A: No. The `no_self_supply` constraint enforces this.

### Bill of Materials

**Q: What does child_part_id → parent_part_id mean?**

A: The `child_part_id` is a COMPONENT OF the `parent_part_id`. Think of it as:
- A screw (child) goes INTO an assembly (parent)
- Direction: `child → parent` means "is component of"
- Reverse direction means "contains"

**Q: Is the BOM acyclic?**

A: Yes. The `no_self_reference` constraint prevents direct cycles, and the business process ensures no circular dependencies.

**Q: What's the typical depth?**

A: Analysis shows average depth of ~3.5 levels, maximum of 5 levels.

### Transport Routes

**Q: Are routes bidirectional?**

A: No, routes are directional and may be asymmetric:
- Route A→B might exist without B→A
- Even if both exist, costs/times may differ
- Multiple transport modes possible between same facilities

**Q: What weights are used for pathfinding?**

A: Three weight columns:
- `distance_km` - for shortest distance
- `cost_usd` - for cheapest route
- `transit_time_hours` - for fastest route

### Supplier Tiers

**Q: What do tier values 1, 2, 3 represent?**

A: Distribution discovered:
- Tier 1 (50 suppliers): Direct suppliers with contracts
- Tier 2 (150 suppliers): Component manufacturers
- Tier 3 (300 suppliers): Raw material providers

Higher tier number = further upstream in supply chain.

## Round 3: Data Validation

### Referential Integrity Checks

All self-referential edge tables passed integrity checks:

```sql
-- supplier_relationships: 0 orphans
SELECT COUNT(*) FROM supplier_relationships
WHERE seller_id NOT IN (SELECT id FROM suppliers)
   OR buyer_id NOT IN (SELECT id FROM suppliers);
-- Result: 0

-- bill_of_materials: 0 orphans
SELECT COUNT(*) FROM bill_of_materials
WHERE child_part_id NOT IN (SELECT id FROM parts)
   OR parent_part_id NOT IN (SELECT id FROM parts);
-- Result: 0

-- transport_routes: 0 orphans
SELECT COUNT(*) FROM transport_routes
WHERE origin_facility_id NOT IN (SELECT id FROM facilities)
   OR destination_facility_id NOT IN (SELECT id FROM facilities);
-- Result: 0
```

### Graph Property Validation

#### Supplier Network (DAG Check)

```sql
-- Verify tier structure forms valid DAG
SELECT DISTINCT
  s1.tier as seller_tier,
  s2.tier as buyer_tier,
  COUNT(*) as count
FROM supplier_relationships sr
JOIN suppliers s1 ON sr.seller_id = s1.id
JOIN suppliers s2 ON sr.buyer_id = s2.id
GROUP BY s1.tier, s2.tier
ORDER BY s1.tier, s2.tier;
```

Result: All relationships flow from higher tier to lower tier (3→2, 2→1), confirming DAG structure.

#### BOM Depth Analysis

```sql
WITH RECURSIVE bom_depth AS (
    SELECT child_part_id, parent_part_id, 1 as depth
    FROM bill_of_materials
    WHERE parent_part_id NOT IN (SELECT child_part_id FROM bill_of_materials)
    UNION ALL
    SELECT b.child_part_id, b.parent_part_id, bd.depth + 1
    FROM bill_of_materials b
    JOIN bom_depth bd ON b.parent_part_id = bd.child_part_id
    WHERE bd.depth < 20
)
SELECT depth, COUNT(*) FROM bom_depth GROUP BY depth ORDER BY depth;
```

Result:
| Depth | Count |
|-------|-------|
| 1 | 5,718 |
| 2 | 5,299 |
| 3 | 24,135 |
| 4 | 66,719 |
| 5 | 2,542 |

Average depth: ~3.5 levels (weighted by edge count).

#### Transport Network Connectivity

Verified all facilities are reachable (connected graph) - 100% connectivity.

### Sample Data Verification

Verified named entities exist as expected:

```sql
SELECT supplier_code, name, tier FROM suppliers
WHERE name IN ('Acme Corp', 'GlobalTech Industries', 'Precision Parts Ltd');
-- Result: All found with correct tiers

SELECT sku, name FROM products
WHERE name IN ('Turbo Encabulator', 'Flux Capacitor', 'Standard Widget');
-- Result: All found with correct SKUs

SELECT facility_code, name FROM facilities
WHERE name IN ('Chicago Warehouse', 'LA Distribution Center', 'New York Factory');
-- Result: All found with correct codes
```

## Final Ontology

The discovery process produced `ontology/supply_chain.yaml` with:

### Classes (8)
- Supplier, Part, Product, Facility, Customer, Order, Shipment, SupplierCertification

### Relationships (12)
- **YELLOW (recursive)**: supplies_to, component_of
- **RED (weighted)**: connects_to
- **GREEN (simple)**: provides, can_supply, contains_component, has_certification, stores_at, placed_by, ships_from, contains_item, fulfills, uses_route

### Key Design Decisions

1. **Traversal Complexity Classification**
   - GREEN: Simple FK joins, no recursion
   - YELLOW: Recursive traversal needed (supplies_to, component_of)
   - RED: Network algorithms needed (connects_to with weights)

2. **Direction Conventions**
   - `supplies_to`: seller → buyer (upstream to downstream)
   - `component_of`: child → parent (component to assembly)
   - `connects_to`: origin → destination (route direction)

3. **Soft Delete Handling**
   - Tables with `deleted_at` column flagged
   - Queries should filter `WHERE deleted_at IS NULL`

4. **Named Entities**
   - Key test entities documented (Acme Corp, Turbo Encabulator, etc.)
   - Used for validation and benchmark queries

## Validation Checklist

- [x] Every table in schema maps to a class or relationship
- [x] All relationships have sql_mapping with table, domain_key, range_key
- [x] All relationships have traversal_complexity (GREEN/YELLOW/RED)
- [x] All relationships have properties (cardinality, directionality, reflexivity)
- [x] Self-referential tables identified as graph edges
- [x] Weight columns documented for RED relationships
- [x] Data integrity verified (0 orphans in edge tables)
- [x] Graph properties validated (DAG, connectivity)
- [x] Named entities verified in database

## Next Steps

With the ontology complete, Phase 3 can proceed with:

1. GREEN path: Claude generates SQL directly using ontology mappings
2. YELLOW path: Use `traverse()` handler with ontology-derived parameters
3. RED path: Use NetworkX handlers with weight columns from ontology
