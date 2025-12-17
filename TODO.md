# TODO

## Phase B: Manufacturing Ontology Implementation

### Dual-Model Nodes for Transactions
- [ ] Model `MaterialTransaction` as a **Node** in ontology to allow filtering on `reason_code` during traversal (Q78, Q80)
- [ ] Model `WorkOrderStep` as a **Node** for queue analysis and performance queries (Q74, Q85)
- [ ] Add `vg:sql_filter` support for transaction_type split relationships:
  - `IssuesTo`: `transaction_type = 'issue_to_wo'`
  - `ReceivesFrom`: `transaction_type = 'receipt_from_wo'`
  - `ScrapsPart`: `transaction_type = 'scrap'` with `reason_code` edge attribute

### As-Planned vs. As-Built Support
- [ ] Document the two-path pattern in ontology:
  - **As-Planned**: `Product` → `BillOfMaterials` → `Part`
  - **As-Built**: `WorkOrder` → `MaterialTransaction` → `Part`
- [ ] Add Q83 test case for conformance checking (set difference between planned and actual)

### Step Sequence Ordering
- [x] Ensure `traverse()` handler respects `step_sequence` column for work order steps (v0.9.14: `order_by` parameter added)
- [x] Test Q74 and Q76 for correct step ordering in results (v0.9.14: `TestOrderedTraversal` tests added)
- [ ] Add `vg:traversal_semantics` with `ordering_column` support for ontology-driven ordering

### Manufacturing Relationships to Define
- [ ] `FulfilledBy`: Order → WorkOrder (nullable FK, filter `order_id IS NOT NULL`)
- [ ] `HasRouting`: Product → ProductionRouting (with `temporal_bounds`)
- [ ] `HasStep`: WorkOrder → WorkOrderStep
- [ ] `ForWorkOrder`: MaterialTransaction → WorkOrder
- [ ] `IssuesTo`: MaterialTransaction → Part (filtered by transaction_type)
- [ ] `ReceivesFrom`: MaterialTransaction → Product (filtered by transaction_type)
- [ ] `ScrapsPart`: MaterialTransaction → Part (filtered, with reason_code edge attribute)
- [ ] `LocatedAt`: WorkCenter → Facility
- [ ] `UsesWorkCenter`: WorkOrderStep → WorkCenter
- [ ] `RoutingUsesWorkCenter`: ProductionRouting → WorkCenter

---

## Realistic Data Patterns (v0.9.18)

### Completed
- [x] "Supplier from Hell" (Reliable Parts Co) - 50% late deliveries, BB rating, 45-90 day lead times
- [x] Deep Aerospace BOM - 22-level hierarchy with recycling cycle (`AERO-TOP-01` → `PACK-BOX-A1` → `RECYC-CARD-A1` → `AERO-TOP-01`)
- [x] Realistic OEE distribution - 10% poor (40-55%), 15% below avg (55-65%), 60% avg (60-72%), 15% world-class (80-92%)
- [x] 3 named problem work centers: `WC-PROB-01`, `WC-PROB-02`, `WC-PROB-03`

### Pending (from plan)
- [ ] Perfect Order Metric - Make 18% of orders ship AFTER `required_date` (late shipments)
- [ ] Temporal Route Flickering - 10% of transport routes are seasonal (active 3 months/year)
- [ ] Lumpy Demand - Gaussian noise + 5% demand spikes + bottleneck product line
- [ ] Validation Queries - SQL script to verify benchmarks after regeneration

---

# Future Ideas
- linter for context slots in `virt_graph.yaml`
- ESG handler
- Genealogy visualization (As-Built graph rendering)
- COGS rollup handler for true cost calculation
- develop handlers into plugin architecture
