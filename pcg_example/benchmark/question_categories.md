# Benchmark Question Categories

## Purpose

Abstract 85 benchmark questions into domain-agnostic graph pattern categories. Each category
defines a **generic graph problem type**, the VG/SQL operation types it exercises, and the
handler(s) required. Domain-specific examples use the PCG (Prism Consumer Goods) ontology
to ground each abstract pattern in concrete SQL-mapped entities and relationships.

This document serves three purposes:

1. **Benchmark design guide** -- ensures each question tests a known graph capability
2. **Coverage matrix** -- maps VG/SQL features to the questions that exercise them
3. **Portability template** -- categories are domain-agnostic; swap PCG examples for any ontology

---

## Category Definitions

### Category 1: Basic Lookups & Joins (Q01--Q10)

**Tests:** `direct_join` operation type
**Handler:** SQL (no graph handler needed)
**Difficulty:** Tier 1 (baseline)

**What it validates:**
- Entity lookup by primary key, natural key, or attribute filter
- Single-hop FK traversal between two entity classes
- JOIN + aggregate patterns (GROUP BY, COUNT, SUM, AVG)
- WHERE clause with multiple conditions and range predicates
- Composite primary key resolution (header + line items)

**Template patterns:**
- "Find [entity] where [attribute] = [value]"
- "List all [entity A] related to [entity B] via [relationship]"
- "Count [entity] grouped by [dimension] with [filter]"
- "Find the top N [entity] by [measure]"
- "List [line items] for [document header] with [filter]"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q01 | Entity lookup by natural key | Find supplier by supplier_code | `Supplier` (table: suppliers) |
| Q02 | Single-hop FK join | List all ingredients offered by a supplier | `SupplierOffersIngredient` (supplier_ingredients) |
| Q03 | Aggregate with filter | Total purchase order value by plant, status = 'open' | `PurchaseOrder`, `POAtPlant`, `POHasLines` |
| Q04 | Multi-condition WHERE | Find SKUs in category X with price > Y | `SKU` (table: skus) |
| Q05 | Header-to-line join | List order lines for a given order number | `OrderHasLines` (order_lines composite PK) |
| Q06 | Two-hop join chain | Find which suppliers provide ingredients for a formula | `FormulaHasIngredients` + `SupplierOffersIngredient` |
| Q07 | Aggregate by dimension | Revenue by channel (orders grouped by source_id) | `Order`, `OrderFromChannel`, `Channel` |
| Q08 | Date range filter | Orders placed between day X and day Y | `Order` (day column, integer date) |
| Q09 | Polymorphic entity lookup | Find all location entities (plants + DCs + retail) | `Plant`, `DistributionCenter`, `RetailLocation` (Location hierarchy) |
| Q10 | Edge attribute query | Find supplier-ingredient pairs with lead_time > 30 days | `SupplierOffersIngredient` (edge_attributes: lead_time_days) |

---

### Category 2: Recursive Chain Traversal (Q11--Q18)

**Tests:** `recursive_traversal` operation type
**Handler:** `traverse()`
**Difficulty:** Tier 2 (single handler)

**What it validates:**
- Self-referential FK chains (entity references itself via a column)
- WITH RECURSIVE CTE generation and cycle prevention
- Depth-limited traversal (max_depth parameter)
- Chain terminus detection (NULL pointer = end of chain)
- Collecting node attributes along a traversal path
- OWL 2 role axioms (asymmetric, irreflexive, acyclic) as traversal guarantees

**Template patterns:**
- "Starting from [entity X], follow [self-referential relationship] to find all [predecessors/successors]"
- "What is the full [chain type] starting from [entity]?"
- "How deep is the [chain] rooted at [entity]?"
- "Find all [entities] that are reachable via [chain] from [start]"
- "Which [entities] have no [predecessor/successor] in the [chain]?"
- "Find the [terminal/root] nodes in all [chains]"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q11 | Forward chain traversal | Follow SKU supersession chain from a given SKU | `SKUSupersedes` (skus.supersedes_sku_id) |
| Q12 | Reverse chain traversal | Find all SKUs that eventually supersede to SKU X | `SKUSupersedes` (reverse direction) |
| Q13 | Chain depth measurement | How many generations in the SKU alias chain from X? | `SKUSupersedes`, traverse() depth |
| Q14 | Root node detection | Find all root SKUs (no predecessor in supersession chain) | `SKUSupersedes` (supersedes_sku_id IS NULL) |
| Q15 | Terminal node detection | Find all leaf SKUs (not superseded by any other SKU) | `SKUSupersedes` (no inbound edges) |
| Q16 | Chain with attribute collection | Collect category and brand along the SKU alias chain | `SKUSupersedes` + `SKU` attributes |
| Q17 | Depth-limited traversal | Find SKUs within 3 hops of supersession from X | `SKUSupersedes`, traverse(max_depth=3) |
| Q18 | Chain statistics | Average/max chain length across all SKU alias chains | `SKUSupersedes`, multiple traverse() calls |

---

### Category 3: Hierarchical Traversal & Aggregation (Q19--Q28)

**Tests:** `recursive_traversal`, `path_aggregation`, `hierarchical_aggregation` operation types
**Handler:** `traverse()`, `path_aggregate()`
**Difficulty:** Tier 2 (single handler)

**What it validates:**
- Tree/DAG explosion (BOM, org chart, category hierarchy patterns)
- Multiplicative aggregation along paths (quantity rollup through levels)
- Additive aggregation along paths (cost summation)
- Edge attributes as aggregation weights (quantity_kg, cost)
- Multi-level hierarchy with intermediate nodes
- Polymorphic product output (finished vs. intermediate)

**Template patterns:**
- "Explode the [hierarchy] for [root entity] to all leaf nodes"
- "What is the total [measure] required for [root], rolling up through [levels]?"
- "List all [leaf entities] reachable from [root] through [hierarchy]"
- "What is the aggregated [cost/weight/quantity] for [root entity]?"
- "Find all [intermediates] between [root] and [leaves] in the [hierarchy]"
- "Compare planned vs. actual [measure] through the [hierarchy]"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q19 | Single-level BOM explosion | List all ingredients for formula X | `FormulaHasIngredients` (formula_ingredients) |
| Q20 | Multi-level BOM explosion | Full ingredient tree for a finished SKU (via formula chain) | `FormulaForProduct` + `FormulaHasIngredients` |
| Q21 | Quantity rollup (multiply) | Total kg of ingredient Y needed for 100 batches of SKU X | `path_aggregate(operation='multiply')` on quantity_kg |
| Q22 | Cost rollup | Total raw material cost for one batch of SKU X | `path_aggregate` with cost_per_kg from Ingredient |
| Q23 | Where-used (reverse BOM) | Which finished SKUs require ingredient Z? | `FormulaHasIngredients` (reverse) + `FormulaForProduct` |
| Q24 | BOM depth measurement | How many levels deep is the BOM for SKU X? | `FormulaHasIngredients`, traverse() depth |
| Q25 | Intermediate node enumeration | List all bulk intermediates in the BOM for SKU X | `BulkIntermediate` via `FormulaForProduct` (type_discriminator) |
| Q26 | Edge attribute aggregation | Total quantity_kg per ingredient across all formulas | `FormulaHasIngredients` edge_attributes: quantity_kg |
| Q27 | Planned vs. actual comparison | Compare formula quantity_kg vs. batch_ingredients quantity_kg | `FormulaHasIngredients` vs. `BatchConsumesIngredient` |
| Q28 | Multi-product shared ingredients | Find ingredients shared by 3+ formulas (common components) | `FormulaHasIngredients` (reverse aggregation) |

---

### Category 4: Weighted Network Algorithms (Q29--Q40)

**Tests:** `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` operation types
**Handler:** `shortest_path()`, `centrality()`, `connected_components()`, `resilience_analysis()`
**Difficulty:** Tier 2 (single handler)

**What it validates:**
- Dijkstra shortest path with configurable weight columns
- Multiple weight metrics on same network (distance vs. time)
- Centrality measures (degree, betweenness, closeness, PageRank)
- Connected component detection across polymorphic node types
- Network resilience (node/edge removal impact)
- Polymorphic endpoints resolved via type_discriminator
- Weight columns as edge properties (distance_km, transit_time_hours)

**Template patterns:**
- "Find the shortest [path] from [node A] to [node B] by [weight metric]"
- "What are all shortest paths between [node A] and [node B]?"
- "Which [node] has the highest [centrality measure] in the [network]?"
- "How many [connected components] exist in the [network]?"
- "What is the impact of removing [node X] from the [network]?"
- "Find all [nodes] reachable from [node A] within [weight threshold]"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q29 | Shortest path by distance | Shortest route from Plant A to RetailLocation B by km | `RouteSegmentOrigin/Destination` (distance_km) |
| Q30 | Shortest path by time | Fastest route from Plant A to RetailLocation B | `RouteSegmentOrigin/Destination` (transit_time_hours) |
| Q31 | All shortest paths | All equidistant routes between two locations | `all_shortest_paths()` |
| Q32 | Degree centrality | Which location has the most route connections? | `centrality(measure='degree')` |
| Q33 | Betweenness centrality | Which DCs are critical transit hubs? | `centrality(measure='betweenness')` |
| Q34 | Closeness centrality | Which location minimizes average distance to all others? | `centrality(measure='closeness')` |
| Q35 | PageRank | Rank locations by transport network importance | `centrality(measure='pagerank')` |
| Q36 | Connected components | Are all locations reachable from each other? | `connected_components()` on route_segments |
| Q37 | Resilience: node removal | Impact of closing Plant X on network connectivity | `resilience_analysis(remove_nodes=[X])` |
| Q38 | Resilience: edge removal | Impact of removing route segment Y on paths | `resilience_analysis(remove_edges=[Y])` |
| Q39 | Constrained path | Shortest path avoiding a specific DC | `shortest_path(excluded_nodes=[dc_id])` |
| Q40 | Polymorphic path endpoints | Route from a Plant (origin_type=plant) to RetailLocation (destination_type=retail) | `type_discriminator` on RouteSegmentOrigin/Destination |

---

### Category 5: Cross-Domain Composition (Q41--Q50)

**Tests:** Multiple operation types combined; `direct_join` + handler calls
**Handler:** SQL + `traverse()` / `path_aggregate()` / `shortest_path()`
**Difficulty:** Tier 3 (multi-handler)

**What it validates:**
- Chaining a handler result into a SQL query (or vice versa)
- Using SQL to resolve entry points, then dispatching to a handler
- Joining handler outputs across different graph structures
- Combining BOM results with supply network queries
- Mixing hierarchy traversal with network pathfinding
- Financial aggregation across traversal results

**Template patterns:**
- "For [entity from handler A result], find [related data via SQL join]"
- "Find [network path] then aggregate [measures] along [hierarchy]"
- "Starting from [SQL filter], traverse [chain/hierarchy], then join [other domain]"
- "Which [supplier/location] provides the cheapest [component] in the [BOM] for [product], considering [transport cost]?"
- "Combine [BOM explosion] with [supply network] to find total landed cost"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q41 | BOM + supplier lookup | For each ingredient in SKU X's BOM, find all suppliers and their costs | `FormulaHasIngredients` (BOM) + `SupplierOffersIngredient` (join) |
| Q42 | BOM + transport cost | Total landed cost: BOM cost + transport from supplier to plant | `path_aggregate` + `shortest_path` + SQL |
| Q43 | Chain + inventory | For the SKU alias chain from X, find current inventory at all locations | `SKUSupersedes` (traverse) + `InventoryForSKU` + `InventoryAtLocation` |
| Q44 | Network + orders | Which retail locations within 2 hops of DC X have pending orders? | `shortest_path` (route_segments) + `OrderForRetailLocation` |
| Q45 | BOM + production | Which work orders use formulas containing ingredient Y? | `FormulaHasIngredients` (reverse) + `WorkOrderUsesFormula` |
| Q46 | Financial + supply chain | Total AP invoice amount for ingredients in SKU X's BOM | `FormulaHasIngredients` + `SupplierOffersIngredient` + `APInvoiceFromSupplier` |
| Q47 | Network + fulfillment | Optimal fulfillment route: DC with inventory -> retail location via shortest path | `InventoryAtLocation` + `shortest_path` on transport network |
| Q48 | Hierarchy + state filter | Active work orders for formulas that require ingredient Z | `FormulaHasIngredients` + `WorkOrderUsesFormula` + state filter (status) |
| Q49 | Multi-join chain | Trace: Order -> OrderLine -> SKU -> Formula -> Ingredients -> Suppliers | 5-hop join chain across 6 entity classes |
| Q50 | Aggregate across domains | Revenue vs. cost comparison per SKU: AR invoices vs. BOM raw material cost | `ARInvoiceLineForSKU` + `path_aggregate` on BOM |

---

### Category 6: Multi-Graph Polymorphism (Q51--Q60)

**Tests:** Cross-graph patterns, polymorphic resolution, type_discriminator usage
**Handler:** Multiple handlers + polymorphic dispatch
**Difficulty:** Tier 4 (composite)

**What it validates:**
- Traversals that span multiple distinct graph structures
- Polymorphic relationship resolution via type_discriminator columns
- Context-block-guided queries (no discriminator, use vg:context hints)
- Grand unified chains: BOM hierarchy -> supply network -> fulfillment
- Impact analysis across graph boundaries
- Cycle detection across heterogeneous graphs
- Plan vs. actual divergence across graph layers

**Template patterns:**
- "Trace [entity] across [graph A] then [graph B] then [graph C]"
- "Resolve [polymorphic relationship] and continue traversal into [specific target type]"
- "What is the blast radius of [event] across [all connected graphs]?"
- "Compare [planned structure in graph A] vs. [actual execution in graph B]"
- "Find [hidden dependencies] that span [multiple graph types]"
- "Which [entities] appear in both [graph A] and [graph B]?"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q51 | Grand unified: BOM -> supply -> logistics | For SKU X, trace ingredients -> suppliers -> shipping routes to plant | `FormulaHasIngredients` + `SupplierOffersIngredient` + `RouteSegmentOrigin/Destination` |
| Q52 | Grand unified: order -> production -> material | Trace order -> work order -> batch -> ingredients consumed | `OrderLineForSKU` + `WorkOrderUsesFormula` + `BatchConsumesIngredient` |
| Q53 | Constrained polymorphic path | Shortest route from any Plant to RetailLocation X, weighted by transit_time | Polymorphic origin (type_discriminator) + `shortest_path` |
| Q54 | Polymorphic entity resolution | Find all inventory at locations of type 'dc', using type_discriminator | `InventoryAtLocation` (type_discriminator: location_type) |
| Q55 | Cross-graph dependency | Which suppliers feed into products shipped to RetailLocation Y? | BOM (FormulaHasIngredients) + supply (SupplierOffersIngredient) + fulfillment (ShipmentToDestination) |
| Q56 | Cycle detection across graphs | Are there circular dependencies between formulas (BOM cycles)? | `FormulaHasIngredients` with cycle detection in traverse() |
| Q57 | Plan vs. actual: BOM | Planned ingredient quantities (formula) vs. actual (batch_ingredients) for batch B | `FormulaHasIngredients` vs. `BatchConsumesIngredient` |
| Q58 | Blast radius: supplier disruption | If Supplier X goes offline, which SKUs, orders, and shipments are affected? | `SupplierOffersIngredient` -> `FormulaHasIngredients` -> `BatchProducesProduct` -> `OrderLineForSKU` |
| Q59 | Blast radius: plant shutdown | If Plant X shuts down, what orders cannot be fulfilled? | `BatchAtPlant` + `BatchProducesProduct` + `OrderLineForSKU` |
| Q60 | Context-guided polymorphism | Resolve ShipmentFromOrigin without type_discriminator using route_type context | `ShipmentFromOrigin` (vg:context), no discriminator column |

---

### Category 7: Metamodel Feature Validation (Q61--Q68)

**Tests:** `sql_filter`, edge_attributes, OWL 2 axioms, state_machine, composite keys
**Handler:** SQL with metamodel-driven query augmentation
**Difficulty:** Tier 3 (multi-handler)

**What it validates:**
- `vg:sql_filter` injection into edge queries (active-only filtering)
- Edge attribute access on junction tables
- OWL 2 role axioms as query constraints (functional, asymmetric, acyclic)
- State machine awareness (filter by lifecycle state)
- Composite primary key handling in joins
- Temporal filtering using integer day columns
- Type hierarchy (is_a, mixins) in query generation

**Template patterns:**
- "Find [entities] using [relationship] where [sql_filter] is applied"
- "Return [edge attributes] alongside [traversal results]"
- "Verify [OWL axiom]: is [relationship] truly [functional/acyclic]?"
- "Find all [entities] in state [X] of their [state machine]"
- "Query [line items] using [composite primary key]"
- "Find [entities] at time point [day N]"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q61 | sql_filter application | List active production lines at Plant X | `ProductionLineAtPlant` (sql_filter: is_active = true) |
| Q62 | Edge attribute retrieval | Get unit_cost and lead_time for all supplier-ingredient pairs | `SupplierOffersIngredient` (edge_attributes) |
| Q63 | Functional property check | Verify each batch produces exactly one product (functional FK) | `BatchProducesProduct` (vg:functional: true) |
| Q64 | State machine filter | Find all orders in 'allocated' state | `Order` state_machine (state_column: status) |
| Q65 | Composite key join | Retrieve specific order line by (order_id, line_number) | `OrderLine` (composite PK), `OrderHasLines` |
| Q66 | Temporal point-in-time | Inventory snapshot at day 180 for all DCs | `Inventory` (day column) + `InventoryAtLocation` (type_discriminator: dc) |
| Q67 | Acyclicity axiom | Verify SKU supersession chain has no cycles | `SKUSupersedes` (vg:acyclic: true) |
| Q68 | Class hierarchy query | List all TransactionDocuments regardless of subtype | `TransactionDocument` hierarchy (is_a: PO, GR, Order, etc.) |

---

### Category 8: Kinetic Operations (Q69--Q76)

**Tests:** `flow_analysis`, `state_analysis`, `scenario_analysis` operation types; state machines, flow configs, axioms, actions
**Handler:** Kinetic handlers (ad-hoc SQL via Claude orchestration)
**Difficulty:** Tier 3 (multi-handler)

**What it validates:**
- State machine transition analysis (valid/invalid transitions)
- Material and financial flow tracing through conservation groups
- Conservation law verification (mass balance, GL balance)
- Action precondition and effect evaluation
- Scenario parameter perturbation (what-if analysis)
- Flow quantification across relationship chains
- Axiom SQL expression evaluation

**Template patterns:**
- "What state transitions are valid for [entity] in state [X]?"
- "Trace the [material/financial] flow from [source] to [sink]"
- "Does [conservation law] hold for [entity/group]?"
- "What happens if [action] is applied to [entity]?"
- "What if [scenario_param] changes by [perturbation]?"
- "Quantify [flow_type] through [conservation_group] over [time range]"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q69 | State transition analysis | What can happen next to Order X in 'pending' state? | `Order` state_machine: pending -> allocated |
| Q70 | Invalid transition check | Can a Shipment go from 'planned' directly to 'delivered'? | `Shipment` state_machine (no planned->delivered transition) |
| Q71 | Material flow tracing | Trace material flow: PO -> GR -> Batch -> Shipment for ingredient X | procure_to_pay + production_mass_balance flow_configs |
| Q72 | Financial flow tracing | Trace financial flow: PO -> AP Invoice -> Payment for supplier X | procure_to_pay conservation_group (financial) |
| Q73 | Mass balance verification | Does input quantity match output for Batch B? | `Batch` axiom (yield_range) + `BatchConsumesIngredient` flow_config |
| Q74 | GL balance verification | Do debits equal credits for day N? | `GLJournal` axiom (gl_balance) |
| Q75 | Action evaluation | Can Order X be allocated? Check preconditions | `Order` action: allocate (preconditions: status='pending', inventory check) |
| Q76 | Scenario perturbation | What if Plant X capacity drops by 20%? Impact on work orders | `Plant` scenario_param: capacity_tons_per_day, perturbation: -20% |

---

### Category 9: End-to-End Traceability (Q77--Q85)

**Tests:** Full-chain lineage across all graph structures and domains
**Handler:** Multiple handlers chained; SQL + traverse + network
**Difficulty:** Tier 4 (composite)

**What it validates:**
- Full forward traceability: raw material -> finished good -> customer
- Full reverse traceability: customer complaint -> root cause ingredient/supplier
- Cross-domain lineage spanning 5+ entity classes
- Document-level traceability (PO -> GR -> Batch -> Shipment -> AR Invoice)
- Financial reconciliation across the full chain
- Genealogy: all batches that consumed a specific ingredient lot
- Impact radius: cascade from a single entity across the entire graph

**Template patterns:**
- "Trace [entity] forward through all downstream relationships to [end consumer]"
- "Trace [entity] backward through all upstream relationships to [raw material source]"
- "Given [event at node X], what is the full impact radius across all domains?"
- "Reconstruct the complete [document chain] from [procurement] to [revenue]"
- "Find all [end products] affected by [input material lot/supplier]"
- "Reconcile [financial flow] against [material flow] for [entity chain]"

**PCG examples:**

| ID  | Question Pattern | PCG Instance | Ontology Elements |
|-----|-----------------|--------------|-------------------|
| Q77 | Forward traceability | Trace ingredient X from supplier -> PO -> GR -> batch -> SKU -> order -> shipment | Full chain: 8 relationships across 8 entity classes |
| Q78 | Reverse traceability | Given shipped Order Y, trace back to raw ingredients and suppliers | Reverse of Q77 |
| Q79 | Lot genealogy | Find all batches that consumed ingredient lot from GR Z | `GRHasLines` + `GRLineForIngredient` + `BatchConsumesIngredient` |
| Q80 | Supplier blast radius | If Supplier X has a quality issue, which orders/shipments are affected? | `SupplierOffersIngredient` -> `FormulaHasIngredients` -> `BatchConsumesIngredient` -> ... |
| Q81 | Document chain | PO -> GR -> AP Invoice -> Payment: full procurement document trail | 4 join hops through Source and Finance domains |
| Q82 | Order-to-cash chain | Order -> Shipment -> AR Invoice -> Receipt: full revenue document trail | 4 join hops through Order, Fulfill, Finance domains |
| Q83 | Financial reconciliation | For SKU X, compare total AP cost (ingredients) vs. total AR revenue (sales) | BOM cost rollup vs. AR aggregation |
| Q84 | Return impact tracing | Return R -> original order -> batch -> formula -> ingredients: what went wrong? | `ReturnHasLines` + `ReturnLineForSKU` + ... (reverse through production) |
| Q85 | Full network + hierarchy | Cheapest path to deliver SKU X (BOM cost + transport cost) to RetailLocation Y | `path_aggregate` (BOM) + `shortest_path` (network) + cost aggregation |

---

## Difficulty Tiers

| Tier | Description | Handler Composition | Categories | Question Count |
|------|-------------|---------------------|------------|---------------|
| 1 | Baseline SQL | Single SQL query, no handler | Basic Lookups (Cat 1) | 10 |
| 2 | Single Handler | One handler call, possibly with SQL pre/post | Chain Traversal (Cat 2), BOM (Cat 3), Network (Cat 4) | 30 |
| 3 | Multi-Handler | Handler + SQL, or handler + metamodel-driven augmentation | Cross-Domain (Cat 5), Metamodel (Cat 7), Kinetic (Cat 8) | 26 |
| 4 | Composite | Multiple handlers chained across graph boundaries | Multi-Graph (Cat 6), Traceability (Cat 9) | 19 |

---

## VG/SQL Feature Coverage Matrix

| Feature | Annotation | Categories That Test It | Primary Questions |
|---------|-----------|------------------------|-------------------|
| `direct_join` | `vg:operation_types` | Cat 1, Cat 5 (entry points), Cat 7, Cat 9 | Q01--Q10, Q41--Q50 |
| `recursive_traversal` | `vg:operation_types` | Cat 2, Cat 3 | Q11--Q18, Q19--Q28 |
| `path_aggregation` | `vg:operation_types` | Cat 3, Cat 5 | Q21--Q22, Q42, Q50, Q85 |
| `hierarchical_aggregation` | `vg:operation_types` | Cat 3 | Q20, Q24--Q25 |
| `shortest_path` | `vg:operation_types` | Cat 4, Cat 5 | Q29--Q31, Q39--Q40, Q42, Q47, Q85 |
| `centrality` | `vg:operation_types` | Cat 4 | Q32--Q35 |
| `connected_components` | `vg:operation_types` | Cat 4 | Q36 |
| `resilience_analysis` | `vg:operation_types` | Cat 4 | Q37--Q38 |
| `flow_analysis` | `vg:operation_types` | Cat 8 | Q71--Q72 |
| `state_analysis` | `vg:operation_types` | Cat 8 | Q69--Q70, Q75 |
| `scenario_analysis` | `vg:operation_types` | Cat 8 | Q76 |
| `vg:sql_filter` | edge filtering | Cat 7 | Q61 |
| `vg:edge_attributes` | edge properties | Cat 1, Cat 3, Cat 7 | Q10, Q26, Q62 |
| `vg:type_discriminator` | polymorphic resolution | Cat 4, Cat 6, Cat 7 | Q40, Q53--Q54, Q60, Q66 |
| `vg:context` | AI query hints | Cat 6 | Q60 |
| `vg:weight_columns` | network edge weights | Cat 4 | Q29--Q30, Q53 |
| `vg:functional` | OWL 2 axiom | Cat 7 | Q63 |
| `vg:acyclic` | OWL 2 axiom | Cat 2, Cat 7 | Q14--Q15, Q67 |
| `vg:asymmetric` | OWL 2 axiom | Cat 2 | Q11--Q12 |
| `vg:state_machine` | lifecycle state | Cat 7, Cat 8 | Q64, Q69--Q70, Q75 |
| `vg:flow_config` | flow metadata | Cat 8, Cat 9 | Q71--Q72, Q73 |
| `vg:axioms` | SQL constraints | Cat 8 | Q73--Q74 |
| `vg:actions` | mutation semantics | Cat 8 | Q75 |
| `vg:scenario_params` | perturbation | Cat 8 | Q76 |
| Composite PK | `vg:primary_key` (JSON array) | Cat 1, Cat 7 | Q05, Q65 |
| Class hierarchy | `is_a`, `mixins` | Cat 1, Cat 7 | Q09, Q68 |

---

## Handler Coverage Summary

| Handler | Function | Operation Types | Questions |
|---------|----------|----------------|-----------|
| SQL (no handler) | Direct query generation | `direct_join` | Q01--Q10, Q61--Q68 (partial) |
| `traverse()` | Recursive BFS with cycle detection | `recursive_traversal` | Q11--Q18 |
| `path_aggregate()` | Traversal with multiplicative/additive rollup | `path_aggregation`, `hierarchical_aggregation` | Q19--Q28 |
| `shortest_path()` | Dijkstra via NetworkX | `shortest_path` | Q29--Q31, Q39--Q40 |
| `centrality()` | Degree, betweenness, closeness, PageRank | `centrality` | Q32--Q35 |
| `connected_components()` | Cluster detection | `connected_components` | Q36 |
| `resilience_analysis()` | Node/edge removal impact | `resilience_analysis` | Q37--Q38 |
| Kinetic (orchestrated) | Claude-generated SQL for state/flow/scenario | `flow_analysis`, `state_analysis`, `scenario_analysis` | Q69--Q76 |
| Composite | Multiple handlers sequenced | (varies) | Q41--Q60, Q77--Q85 |

---

## PCG Ontology Graph Structures

The PCG ontology declares three distinct graph structures that the benchmark exercises:

| Graph | Edge Table | From/To Columns | Weight Columns | Operation Types | Categories |
|-------|-----------|-----------------|----------------|-----------------|------------|
| Transport network | `route_segments` | origin_id / destination_id | distance_km, transit_time_hours | shortest_path, centrality, connected_components, resilience_analysis | Cat 4, Cat 5, Cat 6 |
| SKU alias chain | `skus` | id / supersedes_sku_id | (none) | recursive_traversal | Cat 2 |
| BOM hierarchy | `formula_ingredients` | formula_id / ingredient_id | quantity_kg (edge attribute) | path_aggregation, hierarchical_aggregation | Cat 3, Cat 5, Cat 6 |

All other relationships (47 of 50) use `direct_join` only and are exercised in Categories 1, 5, 7, 8, and 9.

---

## Per-Question Mapping

| ID  | Category | Difficulty | Primary Handler | Operation Types | VG Features |
|-----|----------|-----------|----------------|----------------|-------------|
| Q01 | Basic Lookups | T1 | SQL | direct_join | -- |
| Q02 | Basic Lookups | T1 | SQL | direct_join | edge_attributes |
| Q03 | Basic Lookups | T1 | SQL | direct_join | -- |
| Q04 | Basic Lookups | T1 | SQL | direct_join | -- |
| Q05 | Basic Lookups | T1 | SQL | direct_join | composite PK |
| Q06 | Basic Lookups | T1 | SQL | direct_join | -- |
| Q07 | Basic Lookups | T1 | SQL | direct_join | -- |
| Q08 | Basic Lookups | T1 | SQL | direct_join | temporal (day) |
| Q09 | Basic Lookups | T1 | SQL | direct_join | class hierarchy |
| Q10 | Basic Lookups | T1 | SQL | direct_join | edge_attributes |
| Q11 | Chain Traversal | T2 | traverse() | recursive_traversal | asymmetric |
| Q12 | Chain Traversal | T2 | traverse() | recursive_traversal | asymmetric |
| Q13 | Chain Traversal | T2 | traverse() | recursive_traversal | -- |
| Q14 | Chain Traversal | T2 | traverse() + SQL | recursive_traversal | acyclic |
| Q15 | Chain Traversal | T2 | traverse() + SQL | recursive_traversal | acyclic |
| Q16 | Chain Traversal | T2 | traverse() | recursive_traversal | -- |
| Q17 | Chain Traversal | T2 | traverse() | recursive_traversal | -- |
| Q18 | Chain Traversal | T2 | traverse() | recursive_traversal | -- |
| Q19 | BOM & Aggregation | T2 | path_aggregate() | path_aggregation | edge_attributes |
| Q20 | BOM & Aggregation | T2 | path_aggregate() | hierarchical_aggregation | type_discriminator |
| Q21 | BOM & Aggregation | T2 | path_aggregate() | path_aggregation | edge_attributes |
| Q22 | BOM & Aggregation | T2 | path_aggregate() | path_aggregation | edge_attributes |
| Q23 | BOM & Aggregation | T2 | path_aggregate() | hierarchical_aggregation | -- |
| Q24 | BOM & Aggregation | T2 | traverse() | recursive_traversal | -- |
| Q25 | BOM & Aggregation | T2 | path_aggregate() | hierarchical_aggregation | type_discriminator |
| Q26 | BOM & Aggregation | T2 | SQL | direct_join | edge_attributes |
| Q27 | BOM & Aggregation | T2 | SQL + path_aggregate() | path_aggregation | flow_config |
| Q28 | BOM & Aggregation | T2 | SQL | direct_join | -- |
| Q29 | Network Algorithms | T2 | shortest_path() | shortest_path | weight_columns |
| Q30 | Network Algorithms | T2 | shortest_path() | shortest_path | weight_columns |
| Q31 | Network Algorithms | T2 | all_shortest_paths() | shortest_path | weight_columns |
| Q32 | Network Algorithms | T2 | centrality() | centrality | -- |
| Q33 | Network Algorithms | T2 | centrality() | centrality | -- |
| Q34 | Network Algorithms | T2 | centrality() | centrality | -- |
| Q35 | Network Algorithms | T2 | centrality() | centrality | -- |
| Q36 | Network Algorithms | T2 | connected_components() | connected_components | -- |
| Q37 | Network Algorithms | T2 | resilience_analysis() | resilience_analysis | -- |
| Q38 | Network Algorithms | T2 | resilience_analysis() | resilience_analysis | -- |
| Q39 | Network Algorithms | T2 | shortest_path() | shortest_path | excluded_nodes |
| Q40 | Network Algorithms | T2 | shortest_path() | shortest_path | type_discriminator |
| Q41 | Cross-Domain | T3 | path_aggregate() + SQL | path_aggregation, direct_join | edge_attributes |
| Q42 | Cross-Domain | T3 | path_aggregate() + shortest_path() | path_aggregation, shortest_path | weight_columns |
| Q43 | Cross-Domain | T3 | traverse() + SQL | recursive_traversal, direct_join | type_discriminator |
| Q44 | Cross-Domain | T3 | shortest_path() + SQL | shortest_path, direct_join | -- |
| Q45 | Cross-Domain | T3 | SQL (multi-join) | direct_join | -- |
| Q46 | Cross-Domain | T3 | path_aggregate() + SQL | path_aggregation, direct_join | -- |
| Q47 | Cross-Domain | T3 | SQL + shortest_path() | shortest_path, direct_join | type_discriminator |
| Q48 | Cross-Domain | T3 | SQL (multi-join) | direct_join | state_machine |
| Q49 | Cross-Domain | T3 | SQL (multi-join) | direct_join | -- |
| Q50 | Cross-Domain | T3 | path_aggregate() + SQL | path_aggregation, direct_join | -- |
| Q51 | Multi-Graph | T4 | path_aggregate() + SQL + shortest_path() | path_aggregation, shortest_path, direct_join | type_discriminator |
| Q52 | Multi-Graph | T4 | SQL (multi-join) | direct_join | -- |
| Q53 | Multi-Graph | T4 | shortest_path() | shortest_path | type_discriminator, weight_columns |
| Q54 | Multi-Graph | T4 | SQL | direct_join | type_discriminator |
| Q55 | Multi-Graph | T4 | path_aggregate() + SQL | path_aggregation, direct_join | -- |
| Q56 | Multi-Graph | T4 | traverse() | recursive_traversal | acyclic |
| Q57 | Multi-Graph | T4 | SQL (comparison) | direct_join | flow_config |
| Q58 | Multi-Graph | T4 | SQL + traverse() | direct_join, recursive_traversal | -- |
| Q59 | Multi-Graph | T4 | SQL (multi-join) | direct_join | -- |
| Q60 | Multi-Graph | T4 | SQL | direct_join | context |
| Q61 | Metamodel Features | T3 | SQL | direct_join | sql_filter |
| Q62 | Metamodel Features | T3 | SQL | direct_join | edge_attributes |
| Q63 | Metamodel Features | T3 | SQL | direct_join | functional |
| Q64 | Metamodel Features | T3 | SQL | direct_join | state_machine |
| Q65 | Metamodel Features | T3 | SQL | direct_join | composite PK |
| Q66 | Metamodel Features | T3 | SQL | direct_join | type_discriminator, temporal |
| Q67 | Metamodel Features | T3 | traverse() | recursive_traversal | acyclic |
| Q68 | Metamodel Features | T3 | SQL | direct_join | class hierarchy |
| Q69 | Kinetic Operations | T3 | Kinetic (state) | state_analysis | state_machine |
| Q70 | Kinetic Operations | T3 | Kinetic (state) | state_analysis | state_machine |
| Q71 | Kinetic Operations | T3 | Kinetic (flow) | flow_analysis | flow_config |
| Q72 | Kinetic Operations | T3 | Kinetic (flow) | flow_analysis | flow_config |
| Q73 | Kinetic Operations | T3 | Kinetic (axiom) | flow_analysis | axioms, flow_config |
| Q74 | Kinetic Operations | T3 | Kinetic (axiom) | flow_analysis | axioms |
| Q75 | Kinetic Operations | T3 | Kinetic (state) | state_analysis | actions, state_machine |
| Q76 | Kinetic Operations | T3 | Kinetic (scenario) | scenario_analysis | scenario_params |
| Q77 | Traceability | T4 | Multi-handler chain | direct_join, recursive_traversal | -- |
| Q78 | Traceability | T4 | Multi-handler chain | direct_join, recursive_traversal | -- |
| Q79 | Traceability | T4 | SQL (multi-join) | direct_join | -- |
| Q80 | Traceability | T4 | SQL + traverse() | direct_join, recursive_traversal | -- |
| Q81 | Traceability | T4 | SQL (multi-join) | direct_join | flow_config |
| Q82 | Traceability | T4 | SQL (multi-join) | direct_join | flow_config |
| Q83 | Traceability | T4 | path_aggregate() + SQL | path_aggregation, direct_join | -- |
| Q84 | Traceability | T4 | SQL (multi-join) | direct_join | -- |
| Q85 | Traceability | T4 | path_aggregate() + shortest_path() | path_aggregation, shortest_path | weight_columns |

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total questions | 85 |
| Categories | 9 |
| Difficulty tiers | 4 |
| Distinct operation types tested | 11 of 11 |
| VG features exercised | 16 |
| PCG entity classes referenced | 38 |
| PCG relationships referenced | 50 |
| Questions requiring handler calls | 55 |
| Questions requiring SQL only | 30 |
| Questions requiring multiple handlers | 29 |

---

## Adapting to a New Domain

To port this benchmark to a different VG/SQL ontology:

1. **Identify the domain's graph structures** -- find self-referential chains (Cat 2), hierarchies (Cat 3), and weighted networks (Cat 4) in the ontology
2. **Map domain entities to template slots** -- replace `[entity]`, `[chain]`, `[hierarchy]`, `[network]` with domain-specific classes
3. **Verify operation type coverage** -- ensure the domain ontology declares all 11 operation types somewhere
4. **Adapt kinetic questions** -- map state machines, flow configs, and axioms to the domain's declarations
5. **Scale difficulty** -- Categories 1--4 can be written without domain expertise; Categories 5--9 require understanding entity relationships

The category definitions, template patterns, and difficulty tiers remain unchanged across domains.
