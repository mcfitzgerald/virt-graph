# Ontology Domain Redesign: SCOR-DS Aligned Semi-Functional Model

## Context

The PCG ontology currently organizes 38 classes and 50 relationships into 10 domains (A through H2) via YAML comments that are lost after parsing. There's no machine-readable domain information, no formal inter-domain flow declarations, and no Orchestrate concept.

We're redesigning to a **3+1 domain model** aligned with SCOR Digital Standard's double-infinity loop: **Procurement**, **Supply**, **Demand** + **Orchestrate** (cross-cutting meta-layer). This makes domain membership a first-class annotation and formalizes the inter-domain flows that make the ontology an end-to-end virtual twin.

## Additional Scope (added during implementation)

- **Context block cleanup**: Remove overly data-specific details from `vg:context` blocks (exact counts, specific code patterns, percentage distributions). Context should describe *what something is* and *how it relates to other entities*, not data that can be discovered by querying. Data-specific notes belong in `data_note` fields or are discoverable at runtime.
- **Fresh database schema**: The target PCG database has been updated — new DDL should be ingested before rewriting pcg.yaml.

## Versioning

- **Project**: v1.8.1 → v1.9.0 (additive API, non-breaking)
- **Metamodel** (`virt_graph.yaml`): 3.0 → 3.1 (new optional attributes)
- **Ontology** (`pcg.yaml`): 3.2.0 → 4.0.0 (domain restructure, conceptual breaking change)

## Key Design Decisions

1. **`vg:domain` = simple string** (`procurement`, `supply`, `demand`, `orchestrate`), with optional `vg:subdomain` for display grouping
2. **No new metamodel classes** for ProcessTrace/DomainFlow — use schema-level JSON annotations in pcg.yaml instead. Conservation groups already tag the relationships; process traces are documentation-grade annotations the accessor can surface
3. **`scm_base.yaml` unchanged** — it provides structural inheritance (Location, TransactionDocument, LineItem), which is orthogonal to domain membership
4. **Cross-domain relationships** get `vg:domain` based on primary actor (domain_class), plus `vg:cross_domain: "true"` flag for relationships that bridge domains
5. **Orchestrate is an interpretation layer**, not a new metamodel type — it aggregates existing annotations (state machines, flows, axioms, scenarios) across domain boundaries
6. **Functional split for Finance**: AP in Procurement, AR in Demand, GL/Variance in Orchestrate. Process flow is the primary lens (SCOR-aligned). A convenience method `get_financial_entities()` spans subdomains for the CFO view

## Domain Assignments

### Classes (38 total)

| Domain | Subdomain | Classes | Count |
|--------|-----------|---------|-------|
| procurement | sourcing | Supplier, Ingredient, SupplierIngredient | 3 |
| procurement | purchasing | PurchaseOrder, PurchaseOrderLine | 2 |
| procurement | inbound | GoodsReceipt, GoodsReceiptLine | 2 |
| procurement | accounts_payable | APInvoice, APInvoiceLine, APPayment | 3 |
| supply | product | SKU, BulkIntermediate, Formula, FormulaIngredient | 4 |
| supply | manufacturing | Plant, ProductionLine, WorkOrder, Batch, BatchIngredient | 5 |
| supply | network | DistributionCenter, RouteSegment | 2 |
| demand | planning | DemandForecast | 1 |
| demand | customer_service | Channel, Order, OrderLine, RetailLocation, Inventory | 5 |
| demand | fulfillment | Shipment, ShipmentLine | 2 |
| demand | reverse_logistics | Return, ReturnLine, DispositionLog | 3 |
| demand | accounts_receivable | ARInvoice, ARInvoiceLine, ARReceipt | 3 |
| orchestrate | finance | ChartOfAccounts, GLJournal, InvoiceVariance | 3 |
| **Total** | | | **38** |

### Relationships (50 total)

Relationship domain = domain of primary actor (domain_class). Cross-domain flag for relationships bridging domains.

| Domain | Relationships | Cross-domain examples |
|--------|--------------|----------------------|
| procurement (14) | SupplierOffersIngredient, POFromSupplier, POAtPlant, POHasLines, POLineForIngredient, GRFromShipment, GRAtPlant, GRHasLines, GRLineForIngredient, APInvoiceFromSupplier, APInvoiceForGR, APInvoiceHasLines, APInvoiceLineForIngredient, APPaymentForInvoice | POAtPlant (→supply), GRFromShipment (→demand) |
| supply (13) | ProductionLineAtPlant, FormulaForProduct, FormulaHasIngredients, WorkOrderAtPlant, WorkOrderUsesFormula, BatchFromWorkOrder, BatchAtPlant, BatchUsesFormula, BatchProducesProduct, BatchConsumesIngredient, SKUSupersedes, RouteSegmentOrigin, RouteSegmentDestination | BatchConsumesIngredient (→procurement) |
| demand (21) | OrderFromChannel, OrderForRetailLocation, OrderHasLines, OrderLineForSKU, ShipmentFromOrigin, ShipmentToDestination, ShipmentHasLines, ShipmentLineForSKU, InventoryForSKU, InventoryAtLocation, DemandForecastForSKU, ReturnFromRetailLocation, ReturnHasLines, ReturnLineForSKU, ReturnToDC, DispositionForReturn, ARInvoiceForShipment, ARInvoiceForCustomer, ARInvoiceHasLines, ARInvoiceLineForSKU, ARReceiptForInvoice | OrderLineForSKU (→supply), ReturnToDC (→supply), InventoryAtLocation (→supply) |
| orchestrate (2) | GLJournalToAccount, InvoiceVarianceForAPInvoice | Both inherently cross-cutting |
| **Total: 50** | | |

## Implementation Phases

### Phase 1: Metamodel (`virt_graph.yaml`)

Add optional attributes — **not required**, so existing ontologies continue to validate.

**To `SQLMappedClass`** (after `scenario_params`):
```yaml
# === Domain Classification ===
domain:
  range: string
  description: "Business domain: procurement, supply, demand, or orchestrate"
subdomain:
  range: string
  description: "Sub-domain grouping within the domain (e.g., sourcing, manufacturing)"
```

**To `SQLMappedRelationship`** (after `flow_config`):
```yaml
# === Domain Classification ===
domain:
  range: string
  description: "Primary execution domain for this relationship"
cross_domain:
  range: boolean
  description: "True if this relationship connects entities in different domains"
```

**Also bump metamodel version**: 3.0 → 3.1

**File**: `src/virt_graph/virt_graph.yaml`
**Changes**: ~15 lines added

### Phase 2: OntologyAccessor (`ontology.py`)

New methods (add after the kinetic extensions section, ~line 762):

```python
# Domain Classification
get_class_domain(name) -> Optional[str]
get_class_subdomain(name) -> Optional[str]
get_role_domain_category(name) -> Optional[str]  # NOT get_role_domain (already exists for domain CLASS)
is_role_cross_domain(name) -> bool
get_classes_by_domain(domain) -> list[str]
get_roles_by_domain(domain) -> list[str]
get_all_domains() -> dict[str, dict]  # {domain: {classes: [...], roles: [...]}}
get_cross_domain_roles() -> list[str]
get_orchestrate_summary() -> dict  # aggregates state machines, conservation groups, axioms, flows across domains
get_financial_entities() -> list[str]  # convenience: all classes with subdomain in {accounts_payable, accounts_receivable, finance}
```

Also update `classes` and `roles` properties to include `domain`/`subdomain` in their returned dicts.

**File**: `src/virt_graph/ontology.py`
**Changes**: ~100 lines added

### Phase 3: PCG Ontology (`pcg.yaml`)

This is the largest change — **full rewrite** of pcg.yaml incorporating:

**3a. Schema-level annotations** — add after existing `vg:connection_string`:
```yaml
vg:domains: >-
  {
    "procurement": {"scor_alignment": "Source", "description": "Sourcing, purchasing, inbound, accounts payable"},
    "supply": {"scor_alignment": "Transform + Network", "description": "Product master, manufacturing, distribution network"},
    "demand": {"scor_alignment": "Order + Fulfill + Plan + Return", "description": "Planning, customer service, fulfillment, logistics, reverse logistics, accounts receivable"},
    "orchestrate": {"scor_alignment": "Orchestrate", "description": "Cross-cutting finance, GL, data quality; interprets state machines, flows, axioms, and scenarios across domains"}
  }
vg:inter_domain_flows: >-
  [
    {"name": "material_forward", "direction": "procurement → supply → demand", "flow_type": "material", "description": "Raw materials → production → finished goods → customer"},
    {"name": "demand_signal", "direction": "demand → supply → procurement", "flow_type": "information", "description": "Forecasts and orders pull replenishment upstream"},
    {"name": "financial_reverse", "direction": "demand → orchestrate → procurement", "flow_type": "financial", "description": "AR receipts → GL → AP payments (reverse of material)"},
    {"name": "regenerate", "direction": "demand → procurement", "flow_type": "material", "description": "Returns and disposition flow (reverse logistics)"}
  ]
vg:process_traces: >-
  [
    {"name": "procure_to_pay", "conservation_group": "procure_to_pay", "domains": ["procurement", "orchestrate"], "scor_process": "Source"},
    {"name": "order_to_cash", "conservation_group": "order_to_cash", "domains": ["demand", "orchestrate"], "scor_process": "Deliver"},
    {"name": "production_mass_balance", "conservation_group": "production_mass_balance", "domains": ["supply", "procurement"], "scor_process": "Transform"}
  ]
```

**3b. Restructure section headers** — replace 10 DOMAIN A-H2 headers with 4 domain headers + subdomain markers.

**3c. Add `vg:domain` and `vg:subdomain` to all 88 elements** — one new annotation line each.

**3d. Clean up context blocks** — remove data-specific details (counts, percentages, specific code patterns). Keep semantic role descriptions and relationship guidance.

**3e. Physically reorder classes** to match new domain groupings.

**3f. Bump version** from `3.2.0` to `4.0.0`.

**3g. Reconcile against fresh DDL** — ensure tables, columns, PKs match the updated database.

**File**: `pcg_example/ontology/pcg.yaml`
**Changes**: Full rewrite

### Phase 4: Scripts

**`scripts/show_ontology.py`**:
- Add domain/subdomain columns to TBox and RBox output
- Add `--by-domain` flag for grouped display
- Add domain summary to stats line
- ~50 lines changed

**`scripts/validate_ontology.py`**:
- Add optional domain coverage check (warn if classes missing `vg:domain`)
- ~20 lines added

### Phase 5: Tests

Create `pcg_example/tests/` directory with:
- `__init__.py`
- `conftest.py` (shared `ontology` fixture)
- `test_domain_structure.py`

Key test cases:
1. Every TBox class has `vg:domain` set
2. Every RBox role has `vg:domain` set
3. Domain values are from `{procurement, supply, demand, orchestrate}`
4. `get_classes_by_domain()` returns correct classes per domain
5. `get_all_domains()` returns 4 domains with correct counts (10, 11, 14, 3)
6. Cross-domain roles are flagged correctly
7. `get_orchestrate_summary()` returns expected aggregation
8. Backward compatibility — existing methods unchanged

### Phase 6: Documentation

| File | Changes |
|------|---------|
| `docs/vg-extensions.md` | New "Domain Classification" section documenting `vg:domain`, `vg:subdomain`, `vg:cross_domain`, schema-level `vg:domains`/`vg:inter_domain_flows`/`vg:process_traces` |
| `docs/process-flows.md` | Update overview table to use new domain names; add "Domain Architecture" section with SCOR loop diagram |
| `docs/ontology-building-guide.md` | New step: "Assign Domains" between context blocks and behavioral metadata |
| `CLAUDE.md` | Update Architecture section for 3+1 domains; add domain methods to OntologyAccessor API table |
| `README.md` | Brief mention of SCOR-aligned domain model |
| `CHANGELOG.md` | v1.9.0 entry documenting domain restructure |
| `pyproject.toml` | Bump project version to 1.9.0 |

## Commit Strategy

Single commit or few commits — user preference.

## Verification

```bash
# 1. Validate ontology still passes two-layer validation
poetry run python scripts/validate_ontology.py --all

# 2. Run new domain tests
poetry run pytest pcg_example/tests/test_domain_structure.py -v

# 3. Show ontology with domain groupings
poetry run python scripts/show_ontology.py --by-domain

# 4. Verify schema match still passes (requires live DB)
poetry run python scripts/validate_schema_match.py --all

# 5. Spot-check accessor methods
poetry run python -c "
from virt_graph.ontology import OntologyAccessor
from pathlib import Path
o = OntologyAccessor(Path('pcg_example/ontology/pcg.yaml'))
domains = o.get_all_domains()
for d, info in domains.items():
    print(f'{d}: {len(info[\"classes\"])} classes, {len(info[\"roles\"])} roles')
print('Cross-domain:', o.get_cross_domain_roles())
"
```

## Critical Files

| File | Role |
|------|------|
| `src/virt_graph/virt_graph.yaml` | Metamodel — add domain/subdomain/cross_domain attributes |
| `src/virt_graph/ontology.py` | Accessor — add ~10 domain query methods |
| `pcg_example/ontology/pcg.yaml` | Main ontology — annotate 88 elements, restructure sections, add schema-level declarations |
| `pcg_example/ontology/scm_base.yaml` | **No changes needed** |
| `scripts/show_ontology.py` | Display — domain grouping support |
| `scripts/validate_ontology.py` | Validation — domain coverage check |
