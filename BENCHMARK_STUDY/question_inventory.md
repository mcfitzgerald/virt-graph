# Question Inventory for Demand-Driven Pattern Discovery

**Purpose**: 50 realistic business questions that drive pattern discovery and serve as the benchmark.

**Ontology Reference**: `ontology/supply_chain.yaml` (v1.0)
- 9 Entity Classes (TBox): Supplier, Part, Product, Facility, Customer, Order, Shipment, Inventory, SupplierCertification
- 15 Relationships (RBox): 3 YELLOW, 1 RED, 11 GREEN

**Design Principle**: GREEN patterns are parameterized templates - if they work for a few, they work for many. Focus testing on YELLOW/RED/MIXED where complexity lives.

---

## Distribution Summary

| Complexity | Count | % | Rationale |
|------------|-------|---|-----------|
| GREEN | 10 | 20% | Representative samples - if these work, hundreds more will |
| YELLOW | 18 | 36% | Deep coverage of recursive traversal (supplier network + BOM) |
| RED | 12 | 24% | Pathfinding variants + centrality/connectivity algorithms |
| MIXED | 10 | 20% | Cross-domain patterns combining GREEN + YELLOW/RED |

---

## GREEN - Representative Samples (Q01-Q10)

*These 10 questions validate that basic lookups, joins, and aggregations work. Once proven, the same patterns scale to hundreds of similar queries.*

| ID | Question | Pattern Type | Ontology Elements |
|----|----------|--------------|-------------------|
| Q01 | Find the supplier with code "ACME-001" | Entity lookup by identifier | `Supplier.supplier_code` |
| Q02 | List all tier 1 suppliers | Entity filter by attribute | `Supplier.tier` |
| Q03 | What parts can supplier "GlobalTech Industries" supply? | Forward relationship traversal | `Supplier` → `CanSupply` → `Part` |
| Q04 | Who is the primary supplier for part "CHIP-001"? | Reverse relationship traversal | `Part` → `PrimarySupplier` → `Supplier` |
| Q05 | Which suppliers have ISO 9001 certification? | Join with filter | `Supplier` → `HasCertification` → `SupplierCertification.certification_type` |
| Q06 | What are the direct components of product "Turbo Encabulator"? | Product to Part join | `Product` → `ContainsComponent` → `Part` |
| Q07 | What is the current inventory of part "CHIP-001" at "Chicago Warehouse"? | Multi-table join | `Inventory` + `Facility` + `Part` |
| Q08 | List all pending orders for customer "Acme Industries" | Join with status filter | `Customer` → `PlacedBy` → `Order.status` |
| Q09 | Total revenue by customer for last quarter | Aggregation with grouping | `Order.total_amount` GROUP BY customer |
| Q10 | Which parts are below their reorder point? | Comparison filter | `Inventory.quantity_on_hand < reorder_point` |

---

## YELLOW - Supplier Network Traversal (Q11-Q18)

*Recursive traversal of the tiered supplier network using the `SuppliesTo` relationship.*

| ID | Question | Direction | Depth | Ontology Elements |
|----|----------|-----------|-------|-------------------|
| Q11 | Find all tier 2 suppliers of "Acme Corp" | Upstream | 1 | `Supplier` ← `SuppliesTo` |
| Q12 | Find all tier 2 AND tier 3 suppliers upstream from "Acme Corp" | Upstream | 2+ | `SuppliesTo` multi-hop |
| Q13 | Who are the downstream customers (buyers) of "Pacific Components"? | Downstream | All | `Supplier` → `SuppliesTo` |
| Q14 | Trace the complete supply path from "Eastern Electronics" to any tier 1 | Upstream | All | `SuppliesTo` with path tracking |
| Q15 | What is the maximum depth of our supplier network? | Analysis | All | `SuppliesTo` depth measurement |
| Q16 | Which tier 1 suppliers have the deepest supply chains? | Analysis | All | `SuppliesTo` depth per root |
| Q17 | Find all suppliers that are exactly 2 hops from "GlobalTech Industries" | Bidirectional | 2 | `SuppliesTo` distance query |
| Q18 | Which suppliers appear in multiple supply chains (shared suppliers)? | Analysis | All | `SuppliesTo` convergence detection |

---

## YELLOW - Bill of Materials Traversal (Q19-Q28)

*Recursive traversal of BOM hierarchy using `HasComponent` (explosion) and `ComponentOf` (where-used).*

| ID | Question | Direction | Pattern | Ontology Elements |
|----|----------|-----------|---------|-------------------|
| Q19 | Full BOM explosion for product "Turbo Encabulator" (all levels) | Downstream | Explosion | `HasComponent` recursive |
| Q20 | Full BOM explosion with quantities for "Flux Capacitor" | Downstream | Explosion + aggregation | `HasComponent` + `quantity` |
| Q21 | Where is part "CHIP-001" used? (where-used analysis) | Upstream | Where-used | `ComponentOf` recursive |
| Q22 | Find all products that contain part "RESISTOR-100" at any level | Upstream | Impact to products | `ComponentOf` → `Product` |
| Q23 | Calculate total component cost for "Turbo Encabulator" | Downstream | Cost rollup | `HasComponent` + `Part.unit_cost` |
| Q24 | What is the deepest BOM level for any product? | Analysis | Depth | `HasComponent` max depth |
| Q25 | Find all leaf components (no sub-parts) in "Turbo Encabulator" | Downstream | Terminal nodes | `HasComponent` leaf detection |
| Q26 | Which parts are used in BOTH "Turbo Encabulator" AND "Flux Capacitor"? | Upstream | Common ancestors | `ComponentOf` intersection |
| Q27 | Find the critical path (longest chain) in "Turbo Encabulator" BOM | Downstream | Path analysis | `HasComponent` longest path |
| Q28 | If part "RESISTOR-100" fails, trace impact through all BOM levels | Upstream | Impact cascade | `ComponentOf` multi-level impact |

---

## RED - Transport Network Algorithms (Q29-Q40)

*Network algorithms on weighted transport routes using `ConnectsTo` relationship.*

### Pathfinding (Q29-Q35)

| ID | Question | Algorithm | Weight Column | Ontology Elements |
|----|----------|-----------|---------------|-------------------|
| Q29 | Find the shortest route (by distance) from "Chicago Warehouse" to "LA Distribution Center" | Dijkstra | `distance_km` | `ConnectsTo` shortest_path |
| Q30 | What is the cheapest route from "New York Factory" to "Seattle Warehouse"? | Dijkstra | `cost_usd` | `ConnectsTo` shortest_path |
| Q31 | Find the fastest route from "Chicago Warehouse" to "Miami Hub" | Dijkstra | `transit_time_hours` | `ConnectsTo` shortest_path |
| Q32 | Show all routes from Chicago to LA with total distance under 3000km | All paths | `distance_km` | `ConnectsTo` all_paths + filter |
| Q33 | Find top 3 alternative routes from New York to LA by cost | K-shortest | `cost_usd` | `ConnectsTo` k_shortest_paths |
| Q34 | What is the minimum number of hops from Chicago to any West Coast facility? | BFS | unweighted | `ConnectsTo` hop count |
| Q35 | Find a route from Chicago to Miami that avoids "Denver Hub" | Constrained | any | `ConnectsTo` with node exclusion |

### Centrality & Connectivity (Q36-Q40)

| ID | Question | Algorithm | Purpose | Ontology Elements |
|----|----------|-----------|---------|-------------------|
| Q36 | Which facility is most central in the transport network? | Betweenness | Find chokepoints | `ConnectsTo` betweenness_centrality |
| Q37 | Which facility has the most direct connections? | Degree | Hub identification | `ConnectsTo` degree_centrality |
| Q38 | Rank facilities by their importance to network flow | PageRank | Influence ranking | `ConnectsTo` pagerank |
| Q39 | Are there any isolated facilities (no routes in or out)? | Connectivity | Gap detection | `ConnectsTo` connected_components |
| Q40 | If "Denver Hub" goes offline, which facility pairs lose connectivity? | Resilience | Impact analysis | `ConnectsTo` with node removal |

---

## MIXED - Cross-Complexity Patterns (Q41-Q50)

*Queries requiring GREEN entry points combined with YELLOW/RED operations.*

| ID | Question | Entry (GREEN) | Operation (YELLOW/RED) | Ontology Elements |
|----|----------|---------------|------------------------|-------------------|
| Q41 | Do we have sufficient inventory to build 100 units of "Turbo Encabulator"? | Product lookup | BOM explosion (Y) + Inventory | `ContainsComponent` → `HasComponent` → `Inventory` |
| Q42 | Which components of "Flux Capacitor" are currently out of stock? | Product lookup | BOM explosion (Y) + Inventory | `HasComponent` → `InventoryOf` |
| Q43 | Find all certified suppliers in "Acme Corp's" tier 2+ supply network | Supplier lookup | Network traversal (Y) + Cert | `SuppliesTo` → `HasCertification` |
| Q44 | What is the total value at risk if "Pacific Components" fails? | Supplier lookup | Network (Y) + Cost aggregation | `SuppliesTo` → `CanSupply` → `Part.unit_cost` |
| Q45 | If "Acme Corp" fails, which products lose ALL their suppliers? | Supplier lookup | Network (Y) + CanSupply + Products | `SuppliesTo` → `CanSupply` → `ContainsComponent` |
| Q46 | Identify single points of failure in "Turbo Encabulator" supply chain | Product lookup | BOM (Y) + Supplier cardinality | `HasComponent` → `CanSupply` count = 1 |
| Q47 | Find the cheapest shipping route for order "ORD-2024-001" | Order lookup | Pathfinding (R) | `Order` → `ShipsFrom` → `ConnectsTo` |
| Q48 | Which suppliers could fulfill order "ORD-2024-001" within 5 days? | Order → Product | BOM (Y) + CanSupply + lead_time | `OrderContains` → `HasComponent` → `CanSupply.lead_time` |
| Q49 | Rank facilities by criticality: connections × inventory value | Facility metrics | Centrality (R) + Aggregation | `ConnectsTo` degree × `Inventory` sum |
| Q50 | If "Denver Hub" fails, what's the cost increase to ship pending orders? | Facility removal | Pathfinding (R) + Order aggregation | `ConnectsTo` reroute + `Order.shipping_cost` |

---

## Ontology Coverage Matrix

### Relationships by Question Count

| Relationship | Complexity | Questions | Count |
|--------------|------------|-----------|-------|
| **SuppliesTo** | YELLOW | Q11-Q18, Q43-Q45 | 11 |
| **HasComponent** | YELLOW | Q19-Q20, Q23-Q28, Q41-Q42, Q46, Q48 | 12 |
| **ComponentOf** | YELLOW | Q21-Q22, Q26, Q28 | 4 |
| **ConnectsTo** | RED | Q29-Q40, Q47, Q49-Q50 | 15 |
| CanSupply | GREEN | Q03, Q44-Q46, Q48 | 5 |
| ContainsComponent | GREEN | Q06, Q41, Q45 | 3 |
| InventoryOf | GREEN | Q07, Q10, Q41-Q42 | 4 |
| PrimarySupplier | GREEN | Q04 | 1 |
| HasCertification | GREEN | Q05, Q43 | 2 |
| PlacedBy | GREEN | Q08 | 1 |
| InventoryAt | GREEN | Q07, Q49 | 2 |
| ShipsFrom | GREEN | Q47 | 1 |
| OrderContains | GREEN | Q48 | 1 |

**Key Insight**: The 3 YELLOW + 1 RED relationships drive 80% of the questions. GREEN relationships are supporting joins.

---

## Handler Coverage

| Handler | Questions | Count |
|---------|-----------|-------|
| `traverse()` | Q11-Q18, Q19-Q28 | 18 |
| `traverse_collecting()` | Q25, Q43 | 2 |
| `bom_explode()` | Q19-Q20, Q23 | 3 |
| `shortest_path()` | Q29-Q31, Q35, Q47 | 5 |
| `all_shortest_paths()` | Q32-Q33 | 2 |
| `centrality()` | Q36-Q38, Q49 | 4 |
| `connected_components()` | Q39-Q40 | 2 |

---

## Named Test Entities

Ensure these exist in the database:

**Suppliers**:
- "Acme Corp" (tier 1)
- "GlobalTech Industries" (tier 1)
- "Pacific Components" (tier 2)
- "Eastern Electronics" (tier 3)

**Parts**:
- "CHIP-001"
- "RESISTOR-100"

**Products**:
- "Turbo Encabulator" (SKU: TURBO-001)
- "Flux Capacitor" (SKU: FLUX-001)

**Facilities**:
- "Chicago Warehouse" (FAC-CHI)
- "LA Distribution Center" (FAC-LA)
- "New York Factory" (FAC-NYC)
- "Denver Hub"
- "Miami Hub"
- "Seattle Warehouse"

**Orders**:
- "ORD-2024-001"

**Customers**:
- "Acme Industries"

---

## Execution Workflow

### Phase 1: Entity Validation
Verify all named test entities exist in database with expected relationships.

### Phase 2: Ground Truth Generation
For each question, write SQL (with recursive CTEs for YELLOW/RED) producing correct answers.
```
benchmark/ground_truth/query_01.json ... query_50.json
```

### Phase 3: Pattern Discovery
For each question:
1. Identify applicable handler(s)
2. Map ontology elements to handler parameters
3. Record as pattern in `patterns/raw/`
4. Generalize to template if pattern is novel

### Phase 4: Benchmark Execution
```bash
make benchmark
```
- Run all 50 questions through Virtual Graph
- Compare results to ground truth
- Measure accuracy and latency

### Phase 5: Documentation
- Update `docs/evaluation/benchmark-results-latest.md`
- Archive previous results with `./scripts/archive_benchmark.sh`
- Update CHANGELOG.md with new version
