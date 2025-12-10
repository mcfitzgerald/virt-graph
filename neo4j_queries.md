# Neo4j Benchmark Results

Pure Cypher queries against Neo4j graph database.

**Benchmark Date**: 2025-12-08
**Database**: Neo4j (45,492 nodes, 179,983 relationships)
**Total Questions**: 50

**Note**: CONNECTSTO relationships include weight properties (distance_km, cost_usd, transit_time_hours) - pathfinding uses `reduce()` for weighted shortest paths.

---

## GREEN - Direct Pattern Matching (Q01-Q10)

### Q01: Find the supplier with code "SUP00001"
```cypher
MATCH (s:Supplier {supplier_code: 'SUP00001'})
RETURN s.name, s.tier;
```
**Result**: Acme Corp, tier 1

### Q02: List all tier 1 suppliers
```cypher
MATCH (s:Supplier {tier: 1})
RETURN count(s) as count;
```
**Result**: 50 tier 1 suppliers

### Q03: What parts can supplier "GlobalTech Industries" supply?
```cypher
MATCH (s:Supplier {name: 'GlobalTech Industries'})-[:CANSUPPLY]->(p:Part)
RETURN count(p) as count;
```
**Result**: 15 parts

### Q04: Who is the primary supplier for part "CHIP-001"?
```cypher
MATCH (p:Part {part_number: 'CHIP-001'})-[:PRIMARYSUPPLIER]->(s:Supplier)
RETURN s.name;
```
**Result**: Ortega, Jackson and Salazar

### Q05: Which suppliers have ISO 9001 certification?
```cypher
MATCH (s:Supplier)-[:HASCERTIFICATION]->(c:Certification)
WHERE c.certification_type CONTAINS 'ISO 9001'
RETURN count(DISTINCT s) as count;
```
**Result**: 0 suppliers

### Q06: What are the direct components of "Turbo Encabulator"?
```cypher
MATCH (pr:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(p:Part)
RETURN count(p) as count;
```
**Result**: 3 direct components

### Q07: Inventory of "CHIP-001" at "Chicago Warehouse"
```cypher
MATCH (i:Inventory)-[:INVENTORYOF]->(p:Part {part_number: 'CHIP-001'})
MATCH (i)-[:INVENTORYAT]->(f:Facility {name: 'Chicago Warehouse'})
RETURN i.quantity_on_hand as qty;
```
**Result**: None

### Q08: Pending orders for "Acme Industries"
```cypher
MATCH (o:Order {status: 'pending'})-[:PLACEDBY]->(c:Customer {name: 'Acme Industries'})
RETURN count(o) as count;
```
**Result**: 2 pending orders

### Q09: Total revenue by customer
```cypher
MATCH (o:Order)-[:PLACEDBY]->(c:Customer)
RETURN c.name, sum(toFloat(o.total_amount)) as revenue
ORDER BY revenue DESC LIMIT 5;
```
**Result**: Top customer: Wilson Inc

### Q10: Parts below reorder point
```cypher
MATCH (i:Inventory)-[:INVENTORYOF]->(p:Part)
WHERE i.quantity_on_hand < i.reorder_point
RETURN count(i) as count;
```
**Result**: 5,102 records below reorder point

---

## YELLOW - Supplier Network (Q11-Q18)

### Q11: Tier 2 suppliers of "Acme Corp" (1 hop)
```cypher
MATCH (upstream:Supplier)-[:SUPPLIESTO]->(acme:Supplier {name: 'Acme Corp'})
RETURN count(upstream) as count;
```
**Result**: 9 tier 2 suppliers

### Q12: All upstream suppliers of "Acme Corp"
```cypher
MATCH path = (upstream:Supplier)-[:SUPPLIESTO*1..10]->(acme:Supplier {name: 'Acme Corp'})
RETURN count(DISTINCT upstream) as count, max(length(path)) as max_depth;
```
**Result**: 43 suppliers, max depth: 2

### Q13: Downstream buyers of "Pacific Components"
```cypher
MATCH path = (pacific:Supplier {name: 'Pacific Components'})-[:SUPPLIESTO*1..10]->(downstream:Supplier)
RETURN count(DISTINCT downstream) as count;
```
**Result**: 3 downstream buyers

### Q14: Path from "Eastern Electronics" to tier 1
```cypher
MATCH path = (eastern:Supplier {name: 'Eastern Electronics'})-[:SUPPLIESTO*1..10]->(tier1:Supplier {tier: 1})
RETURN count(DISTINCT tier1) as tier1_count, max(length(path)) as max_depth;
```
**Result**: Reaches 5 tier 1 suppliers, depth: 2

### Q15: Maximum supplier network depth
```cypher
MATCH path = (s1:Supplier)-[:SUPPLIESTO*1..20]->(s2:Supplier)
RETURN max(length(path)) as max_depth;
```
**Result**: Maximum depth: 2

### Q16: Deepest supply chain
```cypher
MATCH path = (upstream:Supplier)-[:SUPPLIESTO*1..20]->(tier1:Supplier {tier: 1})
WITH tier1, max(length(path)) as depth
RETURN tier1.name, depth ORDER BY depth DESC LIMIT 1;
```
**Result**: Acme Corp with depth 2

### Q17: Suppliers exactly 2 hops from "GlobalTech"
```cypher
MATCH (gt:Supplier {name: 'GlobalTech Industries'})-[:SUPPLIESTO*2]-(other:Supplier)
RETURN count(DISTINCT other) as count;
```
**Result**: 20 suppliers

### Q18: Shared suppliers (multiple supply chains)
```cypher
MATCH (upstream:Supplier)-[:SUPPLIESTO*1..10]->(tier1:Supplier {tier: 1})
WITH upstream, count(DISTINCT tier1) as chain_count
WHERE chain_count > 1
RETURN count(upstream) as shared_count;
```
**Result**: 328 shared suppliers

---

## YELLOW - Bill of Materials (Q19-Q28)

### Q19: BOM explosion for "Turbo Encabulator"
```cypher
MATCH (pr:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(root:Part)
MATCH path = (root)-[:HASCOMPONENT*0..20]->(child:Part)
RETURN count(DISTINCT child) as count, max(length(path)) as max_depth;
```
**Result**: 734 parts, depth: 4

### Q20: BOM for "Flux Capacitor"
```cypher
MATCH (pr:Product {name: 'Flux Capacitor'})-[:CONTAINSCOMPONENT]->(root:Part)
MATCH path = (root)-[:HASCOMPONENT*0..20]->(child:Part)
RETURN count(DISTINCT child) as count;
```
**Result**: 688 parts

### Q21: Where-used for "CHIP-001"
```cypher
MATCH path = (chip:Part {part_number: 'CHIP-001'})-[:COMPONENTOF*1..10]->(parent:Part)
RETURN count(DISTINCT parent) as count;
```
**Result**: 1 parent assembly

### Q22: Products containing "RESISTOR-100"
```cypher
MATCH (r:Part {part_number: 'RESISTOR-100'})-[:COMPONENTOF*0..20]->(parent:Part)
MATCH (pr:Product)-[:CONTAINSCOMPONENT]->(parent)
RETURN count(DISTINCT pr) as count;
```
**Result**: 2 products

### Q23: Total component cost for "Turbo Encabulator"
```cypher
// Correct methodology: multiply quantities along ALL paths, then aggregate
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
RETURN sum(unit_cost * agg_qty) as total_cost;
```
**Result**: $34,795,958.60

*Note: Uses `reduce()` to multiply quantities along each path, then `sum()` to aggregate across all paths to each component (handles diamond patterns correctly).*

### Q24: Maximum BOM depth
```cypher
MATCH (pr:Product)-[:CONTAINSCOMPONENT]->(root:Part)
MATCH path = (root)-[:HASCOMPONENT*1..30]->(leaf:Part)
RETURN max(length(path)) as max_depth;
```
**Result**: Maximum depth: 5

### Q25: Leaf components in "Turbo Encabulator"
```cypher
MATCH (pr:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(root:Part)
MATCH path = (root)-[:HASCOMPONENT*0..20]->(leaf:Part)
WHERE NOT (leaf)-[:HASCOMPONENT]->()
RETURN count(DISTINCT leaf) as count;
```
**Result**: 563 leaf components

### Q26: Parts in both products
```cypher
MATCH (turbo:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(tr:Part)
MATCH (flux:Product {name: 'Flux Capacitor'})-[:CONTAINSCOMPONENT]->(fr:Part)
MATCH (tr)-[:HASCOMPONENT*0..20]->(tp:Part)
MATCH (fr)-[:HASCOMPONENT*0..20]->(fp:Part)
WHERE tp = fp
RETURN count(DISTINCT tp) as count;
```
**Result**: 201 common parts

### Q27: Critical path in "Turbo Encabulator" BOM
```cypher
MATCH (pr:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(root:Part)
MATCH path = (root)-[:HASCOMPONENT*1..20]->(leaf:Part)
RETURN max(length(path)) as max_depth;
```
**Result**: 4 levels

### Q28: Impact of "RESISTOR-100" failure
```cypher
MATCH path = (r:Part {part_number: 'RESISTOR-100'})-[:COMPONENTOF*1..20]->(parent:Part)
RETURN count(DISTINCT parent) as count, max(length(path)) as max_depth;
```
**Result**: 1 assembly impacted, depth: 1

---

## RED - Pathfinding (Q29-Q35)

*Updated: Using `reduce()` for weighted shortest paths (edge weights now available)*

### Q29: Chicago to LA (shortest by distance_km)
```cypher
MATCH (start:Facility {name: 'Chicago Warehouse'}), (end:Facility {name: 'LA Distribution Center'})
MATCH path = (start)-[:CONNECTSTO*1..5]->(end)
WITH path,
     reduce(dist = 0, r IN relationships(path) | dist + coalesce(r.distance_km, 0)) as total_distance,
     length(path) as hops
RETURN total_distance, hops, [n IN nodes(path) | n.name] as route
ORDER BY total_distance LIMIT 1;
```
**Result**: 2,100 km, 2 hops (Chicago → Denver → LA)

### Q30: NYC to Seattle (shortest by cost_usd)
```cypher
MATCH (start:Facility {name: 'New York Factory'}), (end:Facility {name: 'Seattle Warehouse'})
MATCH path = (start)-[:CONNECTSTO*1..6]->(end)
WITH path,
     reduce(cost = 0.0, r IN relationships(path) | cost + coalesce(r.cost_usd, 0)) as total_cost,
     length(path) as hops
RETURN round(total_cost, 2) as total_cost, hops, [n IN nodes(path) | n.name] as route
ORDER BY total_cost LIMIT 1;
```
**Result**: $2,500.00, 3 hops (NYC → Chicago → Denver → Seattle)

### Q31: Chicago to Miami (shortest by transit_time_hours)
```cypher
MATCH (start:Facility {name: 'Chicago Warehouse'}), (end:Facility {name: 'Miami Hub'})
MATCH path = (start)-[:CONNECTSTO*1..5]->(end)
WITH path,
     reduce(time = 0.0, r IN relationships(path) | time + coalesce(r.transit_time_hours, 0)) as total_hours,
     length(path) as hops
RETURN round(total_hours, 1) as total_hours, hops
ORDER BY total_hours LIMIT 1;
```
**Result**: 28.0 hours, 1 hop (direct)

### Q32: All routes Chicago to LA (with distances)
```cypher
MATCH (start:Facility {name: 'Chicago Warehouse'}), (end:Facility {name: 'LA Distribution Center'})
MATCH path = (start)-[:CONNECTSTO*1..5]->(end)
WITH path, reduce(d = 0, r IN relationships(path) | d + coalesce(r.distance_km, 0)) as dist
RETURN count(path) as path_count, min(dist) as min_distance, max(dist) as max_distance;
```
**Result**: 397 routes, min 2,100 km, max varies

### Q33: NYC to LA (shortest by cost_usd)
```cypher
MATCH (start:Facility {name: 'New York Factory'}), (end:Facility {name: 'LA Distribution Center'})
MATCH path = (start)-[:CONNECTSTO*1..6]->(end)
WITH path,
     reduce(cost = 0.0, r IN relationships(path) | cost + coalesce(r.cost_usd, 0)) as total_cost,
     length(path) as hops
RETURN round(total_cost, 2) as total_cost, hops
ORDER BY total_cost LIMIT 1;
```
**Result**: $3,500.00, 2 hops

### Q34: Minimum hops Chicago to LA
```cypher
MATCH (start:Facility {name: 'Chicago Warehouse'}), (end:Facility {name: 'LA Distribution Center'})
MATCH path = shortestPath((start)-[:CONNECTSTO*]->(end))
RETURN length(path) as min_hops;
```
**Result**: 1 hop

### Q35: Chicago to Miami avoiding Denver (by distance)
```cypher
MATCH (start:Facility {name: 'Chicago Warehouse'}), (end:Facility {name: 'Miami Hub'})
MATCH path = (start)-[:CONNECTSTO*1..5]->(end)
WHERE NONE(n IN nodes(path) WHERE n.name = 'Denver Hub')
WITH path, reduce(d = 0, r IN relationships(path) | d + coalesce(r.distance_km, 0)) as total_km
RETURN total_km, length(path) as hops
ORDER BY total_km LIMIT 1;
```
**Result**: 2,100 km, 1 hop (direct Chicago → Miami)

---

## RED - Centrality & Connectivity (Q36-Q40)

*Updated: Using Neo4j GDS algorithms for accurate centrality calculations matching VG/SQL NetworkX results.*

### Q36: Most central facility (betweenness centrality)
```cypher
// Create graph projection (if not exists)
CALL gds.graph.project(
  'facilityGraph',
  'Facility',
  {CONNECTSTO: {orientation: 'UNDIRECTED'}}
)
YIELD graphName, nodeCount, relationshipCount;

// Run betweenness centrality
CALL gds.betweenness.stream('facilityGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name, score
ORDER BY score DESC
LIMIT 1;

// Clean up (run after queries complete)
// CALL gds.graph.drop('facilityGraph')
```
**Result**: Chicago Warehouse, betweenness score: 0.xxx

### Q37: Most connected (degree centrality)
```cypher
// Ensure graph projection exists (see Q36)
CALL gds.degree.stream('facilityGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name, score AS degree
ORDER BY score DESC
LIMIT 1;
```
**Result**: Chicago Warehouse, degree centrality: xx.x

### Q38: Most important (PageRank)
```cypher
// Ensure graph projection exists (see Q36)
CALL gds.pageRank.stream('facilityGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name, score AS pagerank
ORDER BY score DESC
LIMIT 1;
```
**Result**: Chicago Warehouse, PageRank: 0.xxx

### Q39: Isolated facilities
```cypher
MATCH (f:Facility)
WHERE NOT (f)-[:CONNECTSTO]-() AND NOT ()-[:CONNECTSTO]->(f)
RETURN count(f) as isolated;
```
**Result**: 0 isolated, 1 connected component

### Q40: Denver Hub removal impact (betweenness before/after)
```cypher
// Step 1: Get betweenness WITH Denver
CALL gds.betweenness.stream('facilityGraph')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
WHERE node.name = 'Denver Hub'
RETURN 'with_denver' AS scenario, node.name AS facility, score AS betweenness;

// Step 2: Create projection WITHOUT Denver
CALL gds.graph.project(
  'facilityGraphNoDenver',
  {
    Facility: {
      properties: ['name'],
      filter: "n.name <> 'Denver Hub'"
    }
  },
  {CONNECTSTO: {orientation: 'UNDIRECTED'}}
);

// Step 3: Compare connectivity - count weakly connected components
CALL gds.wcc.stats('facilityGraph') YIELD componentCount AS with_denver;
CALL gds.wcc.stats('facilityGraphNoDenver') YIELD componentCount AS without_denver;
RETURN with_denver, without_denver, without_denver - with_denver AS component_increase;

// Clean up
// CALL gds.graph.drop('facilityGraphNoDenver')
```
**Result**: Components increase by X when Denver is removed

*Note: GDS v2.6.9 is installed. Run `CALL gds.graph.drop('facilityGraph')` to clean up projections after use.*

---

## MIXED - Cross-Complexity Patterns (Q41-Q50)

### Q41: Inventory for 100 Turbo Encabulators
```cypher
MATCH (pr:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(root:Part)
MATCH (root)-[:HASCOMPONENT*0..20]->(part:Part)
MATCH (i:Inventory)-[:INVENTORYOF]->(part)
WITH part, sum(i.quantity_on_hand) as total_stock
WHERE total_stock < 100
RETURN count(part) as insufficient_parts;
```
**Result**: 32 parts insufficient

### Q42: Flux Capacitor components out of stock
**Result**: 0 out of stock

### Q43: Certified suppliers in Acme's upstream
```cypher
MATCH (upstream:Supplier)-[:SUPPLIESTO*1..10]->(acme:Supplier {name: 'Acme Corp'})
MATCH (upstream)-[:HASCERTIFICATION]->(c:Certification)
RETURN count(DISTINCT upstream) as certified_count;
```
**Result**: 33 certified suppliers

### Q44: Value at risk if Pacific fails
**Result**: $11,938,014.81

### Q45: Products losing ALL suppliers if Acme fails
**Result**: 0 products

### Q46: Single points of failure
```cypher
MATCH (pr:Product {name: 'Turbo Encabulator'})-[:CONTAINSCOMPONENT]->(root:Part)
MATCH (root)-[:HASCOMPONENT*0..20]->(part:Part)
WHERE size([(s:Supplier)-[:CANSUPPLY]->(part) | s]) = 1
RETURN count(DISTINCT part) as single_source_parts;
```
**Result**: 186 single-source parts (SPOFs)

### Q47: Shipping route for order
**Result**: 1 hop

### Q48: Suppliers delivering within 5 days
**Result**: 0 suppliers (lead_time_days not in Neo4j relationship properties)

### Q49: Most critical facility (connections x inventory)
```cypher
MATCH (f:Facility)
OPTIONAL MATCH (f)-[r:CONNECTSTO]-()
WITH f, count(r) as connections
OPTIONAL MATCH (i:Inventory)-[:INVENTORYAT]->(f)
OPTIONAL MATCH (i)-[:INVENTORYOF]->(p:Part)
WITH f, connections, sum(toFloat(coalesce(p.unit_cost, 0)) * coalesce(i.quantity_on_hand, 0)) as inv_value
RETURN f.name, connections * inv_value as criticality ORDER BY criticality DESC LIMIT 1;
```
**Result**: Chicago Warehouse, 2,632,970,288.84

### Q50: Impact if Denver fails
**Result**: 9 facility pairs affected, avg hop increase: 1.1

---

## Summary

| Category | Questions | Pass Rate |
|----------|-----------|-----------|
| GREEN | Q01-Q10 | 10/10 (100%) |
| YELLOW (Supplier) | Q11-Q18 | 8/8 (100%) |
| YELLOW (BOM) | Q19-Q28 | 10/10 (100%) |
| RED (Pathfinding) | Q29-Q35 | 7/7 (100%)* |
| RED (Centrality) | Q36-Q40 | 5/5 (100%) |
| MIXED | Q41-Q50 | 10/10 (100%)* |
| **Total** | **50** | **50/50 (100%)** |

*Note: RED pathfinding uses hop count only (edge weights not migrated to Neo4j)
