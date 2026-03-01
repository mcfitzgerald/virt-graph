# Gap Analysis — Consolidated (2026-03-01)

Consolidation of `gap_analysis.md` and `gap_analysis_2.txt`, updated against v1.3.0 / ontology v3.0.

## What's Done

| Area | Status | Details |
|------|--------|---------|
| Table mapping | 38/38 | Complete coverage of all PCG ERP tables |
| Relationships | 50 | All FK columns mapped (was 30 at v1.0) |
| Polymorphism | 7 relationships | 5 with `type_discriminator`, 2 with context-only resolution |
| Context blocks | 12 | 6 entity + 6 relationship |
| Edge attributes | 3 | SupplierOffersIngredient, FormulaHasIngredients, BatchConsumesIngredient |
| SQL filter | 1 | ProductionLineAtPlant (`is_active = true`) |
| Weight columns | 2 | RouteSegmentOrigin/Destination (distance_km, transit_time_hours) |
| Operation types | 8 of 11 | Missing: `flow_analysis`, `state_analysis`, `scenario_analysis` |
| State machines | 9 | PO, GR, WorkOrder, Batch, Order, Shipment, Return, AP/AR Invoice |
| Flow configs | 10 | Material + financial flows across 3 conservation groups |
| Axioms | 6 | Capacity, yield, temporal, GL balance, inventory non-negative |
| Actions | 3 entities | Batch (start/complete), Order (allocate/ship), Shipment (dispatch/deliver) |
| Scenario params | 3 entities | Supplier (lead_time), Plant (capacity), Order (volume) |
| LinkML structure | Done | `scm_base.yaml` with abstract classes, mixins, shared slots, enums |
| Class hierarchy | Done | Location, TransactionDocument, LineItem hierarchies; HasActiveFlag/HasName mixins |
| SchemaView | Done | `merge_imports=True`, `get_class_inherited_attributes()` |
| Accessor enrichment | Done | `.classes` and `.roles` surface key annotations as top-level fields |
| OWL 2 properties | Partial | SKUSupersedes has asymmetric/irreflexive/acyclic; many functional FKs |

## What's Still Open

### 1. Kinetic Handlers (High Priority)

The metamodel declares state machines, flow configs, actions, and scenario params — but there are no handler implementations. Currently Claude generates ad-hoc SQL for these patterns.

| Handler | What It Would Do | Declared Metadata |
|---------|-----------------|-------------------|
| `flow_analysis()` | Conservation checks, throughput, Little's Law | 10 flow configs, 3 conservation groups |
| `state_analysis()` | Lifecycle queries, transition validation, dwell times | 9 state machines |
| `scenario_analysis()` | What-if perturbation, cascade propagation | 3 scenario param sets, 6 action definitions |

The whitepaper's "Behavior Equations and Mechanistic Models" section (`I(t) = I(t0) + integral of inflow-outflow`) maps directly to what `flow_analysis()` should compute.

These are the 3 remaining operation types (of 11 total) not yet backed by handlers.

### 2. Axiom Checker Handler (Medium Priority)

`validate_axioms(conn, ontology)` — runs all 6 SQL axiom expressions against live data and reports violations. The declarations exist; there's just no runner.

Axioms declared:
- `capacity_positive` on Plant
- `yield_range` on Batch
- `temporal_order` on Shipment
- `quantity_non_negative` on Inventory
- `gl_balance` on GLJournal

### 3. Context-Stuffing Strategy (Medium Priority)

Decided: stuff `scm_base.yaml` (~2k tokens) + `pcg.yaml` (~15k tokens) into the LLM context at query time. ~17k tokens total, ~8.5% of context window.

Not yet implemented:
- No system prompt template that loads these files
- No orchestration layer that reads ontology → builds prompt → dispatches to handlers
- The "intelligence layer" (Phase 4 in the whitepaper) is conceptual, not wired up

### 4. Remaining LinkML Enhancements (Low Priority)

Structural patterns are in place. Nice-to-haves:
- `required: true` on attributes matching NOT NULL constraints
- More enums (status values, channel_type, shipment route_type)
- Additional `sql_filter` annotations (other `is_active` columns beyond ProductionLine)

### 5. Layer 4: Focused Simulation (Out of Scope)

DES, Monte Carlo for cascade timing. Described in whitepaper Section 6. Likely out of scope for VG/SQL (which is about querying, not simulation).

## Recommended Priority Order

1. **Kinetic handlers** — `flow_analysis()`, `state_analysis()`, `scenario_analysis()`. This is the highest-value remaining work. The metadata is fully declared; the handlers are missing.
2. **Axiom checker** — Small, self-contained. Runs declared SQL expressions and reports violations.
3. **Context-stuffing / orchestration** — Wire up the ontology-to-prompt pipeline so the virtual graph actually works end-to-end.
4. **LinkML enhancements** — `required: true`, more enums, more filters. Low priority polish.
