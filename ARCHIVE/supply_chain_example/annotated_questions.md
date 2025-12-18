# Annotated Question Inventory

**Purpose**: Technical annotations for all 85 benchmark questions - patterns, ontology elements, VG features, and handler mappings.

**Companion file**: `questions.md` (clean questions for testing)

---

## Q01-Q10: Basic Lookups, Joins, Aggregations

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 01 | Find the supplier with code "ACME-001" | Entity lookup by identifier | `Supplier.supplier_code` | `vg:identifier` | direct SQL |
| 02 | List all tier 1 suppliers | Entity filter by attribute | `Supplier.tier` | - | direct SQL |
| 03 | What parts can supplier "GlobalTech Industries" supply? | Forward relationship traversal | `Supplier` → `CanSupply` → `Part` | - | direct SQL |
| 04 | Who is the primary supplier for part "CHIP-001"? | Reverse relationship traversal | `Part.primary_supplier_id` → `Supplier` | - | direct SQL |
| 05 | Which suppliers have ISO 9001 certification? | Join with filter | `Supplier` → `HasCertification` → `SupplierCertification` | - | direct SQL |
| 06 | What are the direct components of product "Turbo Encabulator"? | Product-to-part join | `Product` → `ContainsComponent` → `Part` | - | direct SQL |
| 07 | What is the current inventory of part "CHIP-001" at "Chicago Warehouse"? | Multi-table join | `Inventory` + `Facility` + `Part` | - | direct SQL |
| 08 | List all pending orders for customer "Acme Industries" | Join with status filter | `Customer` → `PlacedBy` → `Order.status` | - | direct SQL |
| 09 | Total revenue by customer for last quarter | Aggregation with grouping | `Order.total_amount` GROUP BY customer | - | direct SQL |
| 10 | Which parts are below their reorder point? | Comparison filter | `Inventory.quantity_on_hand < reorder_point` | - | direct SQL |

---

## Q11-Q18: Supplier Network Traversal

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 11 | Find all tier 2 suppliers of "Acme Corp" | Upstream traversal (depth=1) | `Supplier` ← `SuppliesTo` | - | `traverse()` |
| 12 | Find all tier 2 AND tier 3 suppliers upstream from "Acme Corp" | Upstream traversal (depth=2+) | `SuppliesTo` multi-hop | - | `traverse()` |
| 13 | Who are the downstream customers (buyers) of "Pacific Components"? | Downstream traversal (all) | `Supplier` → `SuppliesTo` | - | `traverse()` |
| 14 | Trace the complete supply path from "Eastern Electronics" to any tier 1 | Upstream path tracking | `SuppliesTo` with path | - | `traverse()` |
| 15 | What is the maximum depth of our supplier network? | Network depth analysis | `SuppliesTo` depth measurement | - | `traverse()` |
| 16 | Which tier 1 suppliers have the deepest supply chains? | Depth per root analysis | `SuppliesTo` depth per root | - | `traverse()` |
| 17 | Find all suppliers that are exactly 2 hops from "GlobalTech Industries" | Distance query (exact) | `SuppliesTo` bidirectional | - | `traverse()` |
| 18 | Which suppliers appear in multiple supply chains (shared suppliers)? | Convergence detection | `SuppliesTo` shared nodes | - | `traverse()` |

---

## Q19-Q28: Bill of Materials Traversal

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 19 | Full BOM explosion for product "Turbo Encabulator" (all levels) | BOM explosion | `Product` → `ContainsComponent` → `Part` → `HasComponent` recursive | - | `traverse()` |
| 20 | Full BOM explosion with quantities for "Flux Capacitor" | BOM explosion + aggregation | `HasComponent` + `bill_of_materials.quantity` | `vg:edge_attributes` | `path_aggregate()` |
| 21 | Where is part "CHIP-001" used? (where-used analysis) | Where-used (upstream) | `Part` → `ComponentOf` recursive | - | `traverse()` |
| 22 | Find all products that contain part "RESISTOR-100" at any level | Impact to products | `ComponentOf` → `Product` | - | `traverse()` |
| 23 | Calculate total component cost for "Turbo Encabulator" | Cost rollup | `HasComponent` + `Part.unit_cost` | - | `path_aggregate()` |
| 24 | What is the deepest BOM level for any product? | Max depth analysis | `HasComponent` max depth | - | `traverse()` |
| 25 | Find all leaf components (no sub-parts) in "Turbo Encabulator" | Terminal node detection | `HasComponent` leaf nodes | - | `traverse_collecting()` |
| 26 | Which parts are used in BOTH "Turbo Encabulator" AND "Flux Capacitor"? | Common ancestor query | `ComponentOf` intersection | - | `traverse()` × 2 |
| 27 | Find the critical path (longest chain) in "Turbo Encabulator" BOM | Longest path analysis | `HasComponent` longest path | - | `traverse()` |
| 28 | If part "RESISTOR-100" fails, trace impact through all BOM levels | Impact cascade | `ComponentOf` multi-level | - | `traverse()` |

---

## Q29-Q40: Transport Network Algorithms

### Pathfinding (Q29-Q35)

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 29 | Find the shortest route (by distance) from "Chicago Warehouse" to "LA Distribution Center" | Shortest path (weighted) | `Facility` → `ConnectsTo` | `vg:weight_columns.distance_km` | `shortest_path()` |
| 30 | What is the cheapest route from "New York Factory" to "Seattle Warehouse"? | Shortest path (cost) | `ConnectsTo` | `vg:weight_columns.cost_usd` | `shortest_path()` |
| 31 | Find the fastest route from "Chicago Warehouse" to "Miami Hub" | Shortest path (time) | `ConnectsTo` | `vg:weight_columns.transit_time_hours` | `shortest_path()` |
| 32 | Show all routes from Chicago to LA with total distance under 3000km | All paths + filter | `ConnectsTo` all paths | `vg:weight_columns` | `all_shortest_paths()` |
| 33 | Find top 3 alternative routes from New York to LA by cost | K-shortest paths | `ConnectsTo` | `vg:weight_columns.cost_usd` | `all_shortest_paths()` |
| 34 | What is the minimum number of hops from Chicago to any West Coast facility? | BFS (unweighted) | `ConnectsTo` hop count | - | `shortest_path()` |
| 35 | Find a route from Chicago to Miami that avoids "Denver Hub" | Constrained path | `ConnectsTo` with node exclusion | - | `shortest_path()` |

### Centrality & Connectivity (Q36-Q40)

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 36 | Which facility is most central in the transport network? | Betweenness centrality | `ConnectsTo` | - | `centrality()` |
| 37 | Which facility has the most direct connections? | Degree centrality | `ConnectsTo` | - | `centrality()` |
| 38 | Rank facilities by their importance to network flow | PageRank | `ConnectsTo` | - | `centrality()` |
| 39 | Are there any isolated facilities (no routes in or out)? | Connectivity check | `ConnectsTo` | - | `connected_components()` |
| 40 | If "Denver Hub" goes offline, which facility pairs lose connectivity? | Resilience analysis | `ConnectsTo` with node removal | - | `resilience_analysis()` |

---

## Q41-Q50: Cross-Domain Patterns

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 41 | Do we have sufficient inventory to build 100 units of "Turbo Encabulator"? | BOM + inventory check | `ContainsComponent` → `HasComponent` → `Inventory` | - | `traverse()` + SQL |
| 42 | Which components of "Flux Capacitor" are currently out of stock? | BOM + inventory filter | `HasComponent` → `Inventory` | - | `traverse()` + SQL |
| 43 | Find all certified suppliers in "Acme Corp's" tier 2+ supply network | Network + certification | `SuppliesTo` → `HasCertification` | - | `traverse_collecting()` |
| 44 | What is the total value at risk if "Pacific Components" fails? | Network + cost aggregation | `SuppliesTo` → `CanSupply` → `Part.unit_cost` | - | `traverse()` + SQL |
| 45 | If "Acme Corp" fails, which products lose ALL their suppliers? | Network + product impact | `SuppliesTo` → `CanSupply` → `ContainsComponent` | - | `traverse()` + SQL |
| 46 | Identify single points of failure in "Turbo Encabulator" supply chain | BOM + supplier cardinality | `HasComponent` → `CanSupply` count = 1 | - | `traverse()` + SQL |
| 47 | Find the cheapest shipping route for order "ORD-2024-001" | Order + pathfinding | `Order` → `Facility` → `ConnectsTo` | `vg:weight_columns` | `shortest_path()` |
| 48 | Which suppliers could fulfill order "ORD-2024-001" within 5 days? | Order + BOM + lead time | `OrderContains` → `HasComponent` → `CanSupply.lead_time_days` | `vg:edge_attributes` | `traverse()` + SQL |
| 49 | Rank facilities by criticality: connections x inventory value | Centrality + aggregation | `ConnectsTo` degree × `Inventory` sum | - | `centrality()` + SQL |
| 50 | If "Denver Hub" fails, what's the cost increase to ship pending orders? | Resilience + rerouting | `ConnectsTo` reroute + `Order.shipping_cost` | - | `resilience_analysis()` |

---

## Q51-Q60: Multi-Graph Polymorphism

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 51 | Calculate total transport distance to assemble one "Turbo Encabulator" | BOM → Supplier → Logistics chain | `HasComponent` → `PrimarySupplier` → `ConnectsTo` | `vg:weight_columns` | `traverse()` + `shortest_path()` |
| 52 | Which transport route carries highest volume of distinct components for "Flux Capacitor"? | BOM → Inventory → Route mapping | `HasComponent` → `Inventory` → `ConnectsTo` | - | `traverse()` + SQL |
| 53 | Shortest path Chicago to Miami through facilities with 50+ units of "CHIP-001" | Inventory-filtered pathfinding | `ConnectsTo` + `Inventory` filter | - | `shortest_path()` + SQL |
| 54 | Route for order with transit < 48 hours, cost minimized | Multi-objective optimization | `ConnectsTo` time constraint + cost | `vg:weight_columns` | `shortest_path()` |
| 55 | Tier 3 supplier that is sole source for part in 3+ Tier 1 products | Risk concentration analysis | `SuppliesTo` → `CanSupply` → `ContainsComponent` | - | `traverse()` + SQL |
| 56 | Are there any loops in the supply chain? | Cycle detection | `SuppliesTo` cycles | - | `traverse()` |
| 57 | Compare theoretical vs actual transit time Chicago to Miami | Plan vs actual analysis | `ConnectsTo.transit_time_hours` vs `Shipment` actuals | - | SQL |
| 58 | Value of orders unfulfillable if "Denver Hub" destroyed | Facility → Inventory → Orders impact | `Facility` → `Inventory` → `Order` | - | SQL |
| 59 | Customers who received defective "RESISTOR-100" batch | Full lineage trace | `Supplier` → `Part` → `Product` → `Order` → `Shipment` → `Customer` | - | SQL |
| 60 | Parts in BOM with no product_components link (dead stock) | Orphan detection | `bill_of_materials` ⊄ `product_components` | - | SQL |

---

## Q61-Q68: Metamodel v2.0/v2.1 Features

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 61 | What was the BOM for "Turbo Encabulator" as of 6 months ago? | Point-in-time BOM query | `HasComponent` with date filter | `vg:temporal_bounds` (effective_from/to) | `traverse()` with valid_at |
| 62 | Which BOM entries are expiring within the next 30 days? | Node lifecycle query | `BOMEntry` (dual-model node) | dual-model: `bill_of_materials` as node | direct SQL |
| 63 | Find tier-2 suppliers via only active relationships | Filtered network traversal | `SuppliesTo` with status filter | `vg:sql_filter` (relationship_status) | `traverse()` |
| 64 | Show supplier contracts expiring next quarter | Contract lifecycle query | `SupplierContract` (dual-model node) | dual-model: `supplier_relationships` as node | direct SQL |
| 65 | Shortest route using only active routes | Filtered shortest path | `ConnectsTo` with status filter | `vg:sql_filter` (route_status) | `shortest_path()` |
| 66 | Routes with status 'seasonal' or 'suspended' | Route maintenance query | `Route` (dual-model node) | dual-model: `transport_routes` as node | direct SQL |
| 67 | Compare transit time: order fulfillment vs transfers | Shipment type segmentation | `Shipment` by type | `vg:sql_filter` (shipment_type) | SQL with GROUP BY |
| 68 | Order line items with high discount and quantity | Line item analysis | `OrderLineItem` (dual-model node) | dual-model: `order_items` as node, `vg:edge_attributes` | direct SQL |

---

## Q69-Q76: Manufacturing Execution (The "Make" Graph)

These questions test the link between **Demand** (Sales Orders) and **Supply** (Work Orders), and the execution of the **Recipe** (Routings).

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 69 | Find the Work Order currently fulfilling Sales Order "ORD-2024-001" | Demand-to-Supply Link | `Order` → `FulfilledBy` → `WorkOrder` | - | `traverse()` |
| 70 | What is the current status of production for Customer "Acme Industries"? | Customer Status Visibility | `Customer` → `PlacedBy` → `Order` → `FulfilledBy` → `WorkOrder.status` | - | `traverse()` |
| 71 | Which Work Centers are currently utilized by "Turbo Encabulator" production? | Resource Mapping | `Product` → `HasRouting` → `ProductionRouting` → `UsesWorkCenter` → `WorkCenter` | - | `traverse()` |
| 72 | Calculate the total planned labor hours for the "New York Factory" | Capacity Aggregation | `Facility` → `LocatedAt` ← `WorkCenter` → `WorkOrderStep.labor_hours` | - | `path_aggregate()` |
| 73 | Find all "make-to-stock" Work Orders that are currently "in_progress" | Inventory Planning | `WorkOrder` (order_type='make_to_stock', status='in_progress') | `vg:sql_filter` | direct SQL |
| 74 | Compare planned vs. actual duration for "WO-2024-00001" | Performance Analysis | `WorkOrder` → `HasStep` → `WorkOrderStep` (planned vs actual) | - | SQL + Aggregation |
| 75 | Identify Work Centers with efficiency rating < 80% | Asset Performance | `WorkCenter.efficiency_rating` | - | direct SQL |
| 76 | Find the "Critical Path" routing steps (longest time) for "Flux Capacitor" | Process Bottleneck | `Product` → `HasRouting` → `ProductionRouting` (ORDER BY run_time) | - | `traverse()` + SQL |

---

## Q77-Q85: Traceability & Quality (The Genealogy Graph)

These questions test **forward/backward traceability** through material transactions—the "holy grail" of graph databases in manufacturing.

| Q# | Question | Pattern Type | Ontology Elements | VG Features | Handler(s) |
|----|----------|--------------|-------------------|-------------|------------|
| 77 | Trace the specific lot of "CHIP-001" used in Work Order "WO-2024-00001" | Component Traceability | `WorkOrder` ← `ForWorkOrder` ← `MaterialTransaction` → `IssuesTo` → `Part` | - | `traverse()` |
| 78 | Which Supplier provided the material that caused a "quality_defect" scrap? | Root Cause Analysis (Deep) | `MaterialTransaction` (scrap) → `Part` → `PrimarySupplier` → `Supplier` | `vg:sql_filter` (reason_code) | `traverse()` |
| 79 | Find all Customers affected by a recall of "SENSOR-001" | Impact Radius (Forward) | `Part` → `MaterialTransaction` → `WorkOrder` → `Order` → `Customer` | - | `traverse()` |
| 80 | Calculate the total cost of scrap generated by "machine_error" this month | Cost of Quality | `MaterialTransaction` (type=scrap, reason=machine_error) × unit_cost | `vg:edge_attributes` | `path_aggregate()` |
| 81 | Which Work Center generates the highest scrap rate for "Motors"? | Machine Quality Profile | `WorkCenter` → `WorkOrderStep` → `WorkOrder` → `MaterialTransaction` (scrap) | - | `traverse()` + Aggregation |
| 82 | Show the full "Genealogy" (As-Built) for shipped Order "ORD-2024-002" | Full Graph Dump | `Order` → `WorkOrder` → `MaterialTransaction` → `Part` (all components) | - | `traverse_collecting()` |
| 83 | Did we use any substitute parts (not in BOM) for "WO-2024-00003"? | Conformance Check | `WorkOrder` actuals (MaterialTransaction) vs `Product` → `BOM` plan | - | SQL (Set Difference) |
| 84 | What is the "True Cost" (Material + Labor) of the last batch of Turbo Encabulators? | COGS Rollup | `WorkOrder` (labor_hours) + `MaterialTransaction` (material cost) | - | `path_aggregate()` |
| 85 | Find bottleneck: Which Work Center has the largest queue of "released" steps? | Queue Analysis | `WorkCenter` ← `WorkOrderStep` (status='pending') | - | SQL + Aggregation |

---

## Summary Statistics

### By Pattern Type

| Pattern Category | Questions | Count |
|------------------|-----------|-------|
| Entity lookup/filter | Q01-Q02, Q10, Q73, Q75 | 5 |
| Relationship traversal (1-hop) | Q03-Q09 | 7 |
| Recursive traversal (multi-hop) | Q11-Q28 | 18 |
| Shortest path algorithms | Q29-Q35, Q47, Q51, Q53-Q54, Q65 | 11 |
| Network analysis (centrality/connectivity) | Q36-Q40, Q49-Q50 | 7 |
| Cross-domain composite | Q41-Q46, Q48, Q52, Q55-Q60 | 13 |
| Dual-model node queries | Q62, Q64, Q66, Q68 | 4 |
| Filtered traversal/path | Q61, Q63, Q65, Q67 | 4 |
| Manufacturing execution | Q69-Q72, Q74, Q76 | 6 |
| Traceability/Genealogy | Q77-Q82, Q84 | 7 |
| Conformance/Variance analysis | Q83, Q85 | 2 |

### By VG Feature

| VG Feature | Questions | Count |
|------------|-----------|-------|
| `vg:weight_columns` | Q29-Q33, Q47, Q51, Q54 | 8 |
| `vg:sql_filter` | Q63, Q65, Q67, Q73, Q78 | 5 |
| `vg:temporal_bounds` | Q61 | 1 |
| `vg:edge_attributes` | Q20, Q48, Q68, Q80 | 4 |
| dual-model (same table as node + edge) | Q62, Q64, Q66, Q68, Q77-Q82 | 10 |

### By Handler

| Handler | Questions | Count |
|---------|-----------|-------|
| direct SQL | Q01-Q10, Q57-Q60, Q62, Q64, Q66-Q68, Q73, Q75 | 20 |
| `traverse()` | Q11-Q28, Q41-Q46, Q48, Q51-Q52, Q55-Q56, Q61, Q63, Q69-Q71, Q76-Q79, Q81 | 37 |
| `traverse_collecting()` | Q25, Q43, Q82 | 3 |
| `path_aggregate()` | Q20, Q23, Q72, Q80, Q84 | 5 |
| `shortest_path()` | Q29-Q35, Q47, Q51, Q53-Q54, Q65 | 11 |
| `all_shortest_paths()` | Q32-Q33 | 2 |
| `centrality()` | Q36-Q38, Q49 | 4 |
| `connected_components()` | Q39 | 1 |
| `resilience_analysis()` | Q40, Q50 | 2 |
| SQL + Aggregation | Q74, Q83, Q85 | 3 |

---

## Key Ontology Relationships

| Relationship | Source Table | Domain → Range | Key Questions |
|--------------|--------------|----------------|---------------|
| `SuppliesTo` | supplier_relationships | Supplier → Supplier | Q11-Q18, Q43-Q45, Q55-Q56, Q63 |
| `HasComponent` | bill_of_materials | Part → Part | Q19-Q28, Q41-Q42, Q46, Q48, Q51-Q52, Q61, Q83 |
| `ComponentOf` | bill_of_materials | Part → Part (inverse) | Q21-Q22, Q26, Q28 |
| `ConnectsTo` | transport_routes | Facility → Facility | Q29-Q40, Q47, Q49-Q54, Q65 |
| `CanSupply` | part_suppliers | Supplier → Part | Q03, Q44-Q46, Q48, Q55 |
| `OrderContains` | order_items | Order → Product | Q48, Q58-Q59, Q68 |
| `ForOrder` | shipments | Order → Shipment | Q59, Q67 |
| `TransfersInventory` | shipments | Facility → Facility | Q67 |
| `Replenishes` | shipments | Supplier → Facility | Q67 |
| `FulfilledBy` | work_orders | Order → WorkOrder | Q69-Q70, Q79, Q82 |
| `HasRouting` | production_routings | Product → ProductionRouting | Q71, Q76 |
| `HasStep` | work_order_steps | WorkOrder → WorkOrderStep | Q72, Q74, Q81, Q85 |
| `ForWorkOrder` | material_transactions | WorkOrder → MaterialTransaction | Q77-Q80, Q82-Q84 |
| `IssuesTo` | material_transactions | MaterialTransaction → Part | Q77-Q79, Q83 |
| `LocatedAt` | work_centers | WorkCenter → Facility | Q72, Q75 |

---

## Dual-Model Tables

These tables are modeled as both nodes (for lifecycle/management queries) and edges (for traversal):

| Table | Node Class | Edge Class(es) | Node Use Cases | Edge Use Cases |
|-------|------------|----------------|----------------|----------------|
| `supplier_relationships` | SupplierContract | SuppliesTo | Q64: contract expiry | Q11-Q18: network traversal |
| `bill_of_materials` | BOMEntry | ComponentOf, HasComponent | Q62: version expiry | Q19-Q28: BOM explosion |
| `transport_routes` | Route | ConnectsTo | Q66: route status | Q29-Q40: pathfinding |
| `order_items` | OrderLineItem | OrderContains | Q68: line item analysis | Q48: order contents |
| `shipments` | Shipment | ForOrder, TransfersInventory, Replenishes | tracking | fulfillment flow |
| `material_transactions` | MaterialTransaction | IssuesTo, ReceivesFrom, ScrapsPart, ForWorkOrder | Q80: scrap cost analysis | Q77-Q79: traceability |
| `work_order_steps` | WorkOrderStep | HasStep, UsesWorkCenter | Q74: performance analysis | Q72, Q81, Q85: capacity/queue |

---

## Design Notes

### As-Planned vs. As-Built
Two distinct graph paths exist for product structure:
- **As-Planned**: `Product` → `BillOfMaterials` → `Part` (design intent)
- **As-Built**: `WorkOrder` → `MaterialTransaction` → `Part` (actual execution)

Q83 explicitly tests conformance by comparing these paths.

### MaterialTransaction as Dual-Model Node
The `material_transactions` table functions as both:
- **Node**: Query scrap transactions, filter by reason_code (Q78, Q80)
- **Edge**: Trace material flow between WorkOrder and Part (Q77, Q79)

### Step Sequence Ordering
The `work_order_steps.step_sequence` column provides execution order. Traversal handlers should respect this ordering when reconstructing production runs (Q74, Q76).
