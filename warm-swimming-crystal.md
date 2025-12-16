# Phase B: Ontology Re-Discovery Implementation Plan

## Overview
Fresh rewrite of `supply_chain.yaml` using metamodel v2.0/v2.1 features, following the guided direct write approach (protocol as checklist, not full interactive 4-round).

## Design Decisions (Confirmed)
- **Discovery approach**: Guided direct write (protocol as checklist)
- **Shipment polymorphism**: Split relationships with `sql_filter` (ForOrder, TransfersInventory, Replenishes)
- **ContextBlocks**: Minimal - traversal_semantics on key relationships only

---

## Implementation Steps

### Step 1: Backup Existing Ontology
done already, `supply_chain.yaml` is in ARCHIVE/

### Step 2: Update Discovery Protocol
**File**: `prompts/ontology_discovery.md`

Add the following sections:
1. **Metamodel Reference** - Emphasize `virt_graph.yaml` as the golden template for ontology structure
2. **Handler Reference Table** - Link to `docs/handlers/overview.md`, quick operation_type → handler mapping
3. **Web Research Step** - When to use WebSearch for domain patterns
4. **Metamodel v2.0/v2.1 Features** - Quick reference for:
   - `vg:sql_filter` - Edge filtering with WHERE clause
   - `vg:edge_attributes` - Property Graph style edge properties
   - `vg:type_discriminator` - Polymorphic relationships (note: split relationships preferred)
   - `vg:context` - ContextBlock for AI hints
   - `vg:temporal_bounds` - Time-bounded traversal
   - Composite keys as JSON arrays

4. **Graph Modeling Patterns** - Common decisions:
   - Join tables with properties → edges with `edge_attributes`
   - Type columns → split relationships with `sql_filter` (preferred over discriminator)
   - Validity dates → `temporal_bounds`

### Step 3: Write New Ontology
**File**: `supply_chain_example/ontology/supply_chain_V2.yaml`

**References**:
- **Metamodel (template)**: `virt_graph.yaml` - Golden reference for ontology structure, valid annotations, and validation rules
- **Data source**: `supply_chain_example/postgres/schema.sql` - Tables, columns, FKs, constraints available
- **Extension docs**: `docs/ontology/vg-extensions.md` - Detailed annotation documentation

#### 3.1 Entity Classes (TBox) - 13 entities
**Core Entities (9):**
- Supplier, Part, Product, Facility, Customer, Order, Shipment, Inventory (implicit), AuditLog (utility)
- This entitie list should be confirmed by introspecting schema, we  might have missed some things

**Dual-Model Node Classes (4 new):**
- NOTE: this was proposed during a reasearch step on how to build the ontology. Ultimately this should be discovered or defined interactively. it's good to start here but discover process should still think through others and make its own inference as to 
what could/should be dual modeled and can support this with web research if needed
- **SupplierContract** - Node view of `supplier_relationships` (contract lifecycle)
- **BOMEntry** - Node view of `bill_of_materials` (version management)
- **Route** - Node view of `transport_routes` (route maintenance)
- **OrderLineItem** - Node view of `order_items` (composite PK: `["order_id", "line_number"]`)

All entities get:
- `vg:row_count` metadata for cardinality estimation
- Composite primary keys use JSON array syntax where needed

#### 3.2 Relationship Classes (RBox) - Core Changes

| Relationship | New Features |
|--------------|--------------|
| **SuppliesTo** | `sql_filter: "relationship_status = 'active'"`, `traversal_semantics` |
| **ComponentOf** | `temporal_bounds: {start: effective_from, end: effective_to}`, `edge_attributes` for quantity. **Use `bom_with_conversions` view** for normalized weight_kg/cost_usd rollups (see UoM note below) |
| **HasComponent** | Same as ComponentOf (inverse) |
| **ConnectsTo** | `sql_filter: "route_status = 'active'"`, `traversal_semantics` |
| **OrderContains** | `edge_attributes` for quantity, unit_price, discount_percent |
| **CanSupply** | `edge_attributes` for supplier_part_number, unit_cost, lead_time_days |
| **ForOrder** | `sql_filter: "shipment_type = 'order_fulfillment' AND order_id IS NOT NULL"` |
| **TransfersInventory** (NEW) | `sql_filter: "shipment_type = 'transfer'"`, Facility → Facility (inter-warehouse) |
| **Replenishes** (NEW) | `sql_filter: "shipment_type = 'replenishment'"`, Supplier → Facility (inbound stock) |

#### 3.3 ContextBlocks (Minimal)
Add `traversal_semantics` to these key relationships:
- SuppliesTo (inbound/outbound supplier network)
- ComponentOf/HasComponent (BOM explosion direction)
- ConnectsTo (logistics routing)

### Step 4: Validate Ontology
```bash
make validate-ontology  # Two-layer validation
```

### Step 5: Add Q61-68 to Questions
**DONE** - See `supply_chain_example/questions.md`

Questions test: temporal_bounds, dual-model nodes (BOMEntry, SupplierContract, Route, OrderLineItem), sql_filter (active relationships, routes, shipment types), edge_attributes.

### Step 6: Update Tests (if needed)
**File**: `supply_chain_example/tests/test_ontology_validation.py`

- Verify new relationships (TransfersInventory, Replenishes) are loaded
- Verify sql_filter syntax passes validation
- Verify temporal_bounds are parsed correctly

### Step 7: Commit
```bash
git add supply_chain_example/ontology/supply_chain.yaml \
        supply_chain_example/ontology/supply_chain.yaml.v1-backup \
        prompts/ontology_discovery.md \
        supply_chain_example/questions.md \
        supply_chain_example/tests/

git commit -m "feat: ontology v2 with sql_filter, edge_attributes, temporal_bounds (Phase B)"
```

---

## Files to Modify

| File | Action |
|------|--------|
| `prompts/ontology_discovery.md` | Add v2.0 feature guidance sections |
| `supply_chain_example/ontology/supply_chain.yaml` | Fresh rewrite with new features |
| `supply_chain_example/ontology/supply_chain.yaml.v1-backup` | New file (backup) |
| `supply_chain_example/questions.md` | Add Q61-68 |
| `supply_chain_example/tests/test_ontology_validation.py` | Minor updates if needed |

---

## Key Technical Decisions

### Why Split Relationships over type_discriminator
- Graph modeling best practices favor distinct edge types
- Pattern matching on relationship type is more efficient than property filtering
- `sql_filter` is already implemented in OntologyAccessor
- Semantically clearer for LLM query generation

### Dual Modeling Strategy (Node + Edge for Same Table)
The metamodel supports mapping one SQL table to both a Node (SQLMappedClass) and Edge(s) (SQLMappedRelationship). Use this when data acts as both a **noun** ("Update the Contract") and **verb** ("Buy via Contract").

**Phase B Dual Models (High Value):**

| Table | Node | Edge(s) | Node Use Case | Edge Use Case |
|-------|------|---------|---------------|---------------|
| `shipments` | Shipment | ForOrder, TransfersInventory, Replenishes | "Track shipment #101" | Order fulfillment traversal |
| `supplier_relationships` | SupplierContract | SuppliesTo | "Contracts expiring next month" | Supplier network traversal |
| `bill_of_materials` | BOMEntry | ComponentOf, HasComponent | "BOM versions expiring soon" | BOM explosion/where-used |
| `transport_routes` | Route | ConnectsTo | "Routes needing review" | Shortest path algorithms |
| `order_items` | OrderLineItem | OrderContains | "High-discount line items" | "Products in order X" |

**Deferred (add later if needed):**
- `part_suppliers` → SourcingAgreement node + CanSupply edge
- `inventory` → InventoryRecord node + StocksAt edge

**Implementation:** Same table name in both `vg:table` (class) and `vg:edge_table` (relationship). No metamodel changes needed - it's a configuration choice.

### Minimal ContextBlocks Rationale
- `traversal_semantics` on 4-5 key traversable relationships is sufficient for Phase B
- Full ContextBlocks (definition, business_logic, data_quality_notes, llm_prompt_hint) can be added incrementally in future phases
- Focus on features that handlers actually use

### Q61-68 Design
- Each question targets a specific v2.0 feature
- Questions should be answerable with existing handler capabilities
- Include questions that exercise both Node and Edge views of dual-modeled tables

### UoM Handling (Implemented)
**Status:** DONE - Schema and data updated

The BOM has mixed units (each, kg, m, L) which require conversion factors for weight/cost rollups.

**Schema changes:**
- `parts` table now has: `base_uom`, `unit_weight_kg`, `unit_length_m`, `unit_volume_l`
- New view `bom_with_conversions` joins BOM with parts to provide pre-computed `weight_kg` and `cost_usd` columns

**Ontology options for ComponentOf:**
1. Point at base `bill_of_materials` table (for simple traversal)
2. Point at `bom_with_conversions` view (for aggregation with normalized units)

The metamodel's `edge_table` accepts any string - views work without metamodel changes. The view includes all required columns (parent_part_id, child_part_id, effective_from, effective_to).

**Documentation:** See `supply_chain_example/data_description.md` § "Unit of Measure (UoM) Handling"
