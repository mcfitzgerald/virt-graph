# Changelog

All notable changes to this project will be documented in this file.

## [1.8.1] - 2026-03-07

### Added

- **Supply chain process flows documentation** (`docs/process-flows.md`)
  - 5 end-to-end process flows mapped to SCOR Digital Standard (Plan, Source, Make, Deliver, Return)
  - Order-to-Cash (O2C): demand-to-revenue cycle with state machines and GL traceability
  - Procure-to-Pay (P2P): supplier sourcing with three-way match and variance detection
  - BOM Explosion & Production (M2S): hierarchical aggregation, polymorphic production, mass balance
  - Network Resilience & Disruption: graph algorithm handlers (shortest_path, centrality, resilience_analysis)
  - Return & Disposition: reverse logistics with condition-based branching
  - Cross-flow connections showing how a single question can traverse all 5 flows
  - What-if scenario examples for each flow using existing `vg:scenario_params` and `vg:actions`
  - Mapping to Virtual Twin strategic roadmap phases (Semantic Mapping -> Kinetic Modeling -> Intelligence Layer)
- **O2C trace demo** (`pcg_example/demos/trace_o2c.py`) — traces a single order through the full Order-to-Cash cycle (Order -> Shipment -> ARInvoice -> ARReceipt -> GL), demonstrates polymorphic source resolution, state machines, revenue source of truth, and conservation checks
- Added process flows link to `docs/index.md` and `README.md`

## [1.8.0] - 2026-03-01

### Fixed

- **Type discriminator mappings** — RouteSegmentOrigin, RouteSegmentDestination, InventoryAtLocation now match actual DB values (`rdc`, `customer_dc`, `store`, `supplier` instead of `dc`, `retail`)
- **State machine status values** — added `data_note` to all 9 state machines documenting observed status values vs declared lifecycle; WorkOrder terminal state changed from `completed` to `complete`; ARInvoice states expanded to include `disputed` and `partial`

### Changed

- **PCG ontology overhaul** (`pcg_example/ontology/pcg.yaml` v3.0 → v3.1)
  - All 38 classes now have `vg:context` blocks (was 6/38, now 38/38)
  - All 50 relationships now have `vg:context` blocks (was 6/50, now 50/50)
  - Context blocks include `business_logic`, `llm_prompt_hint`, and `traversal_semantics`
  - Documents undocumented polymorphism: BOM ingredient_id → ingredients OR bulk_intermediates, order source_id → channels OR retail_locations, revenue lives in AR invoices not order_lines
  - DistributionCenter context explains RDC vs customer_dc type column distinction
  - RouteSegmentOrigin range_class updated to include Supplier (origins include supplier nodes)

### Added

- **New scenario_params** on Ingredient (cost_per_kg), ProductionLine (capacity_units_per_hour), RouteSegment (distance_km, transit_time_hours), Shipment (freight_cost)
- **New axioms** on Supplier (no_duplicate_suppliers) and APInvoice (no_duplicate_invoices) for data quality friction detection

## [1.7.0] - 2026-03-01

### Added

- **PCG benchmark questions** (`pcg_example/benchmark/questions.md`)
  - 85 natural-language questions (Q01–Q85) across 9 sections
  - Written from VP Supply Chain / Finance Controller / Procurement Director perspective
  - Covers all 11 operation types and 16 VG metamodel features
  - PCG-specific references (Dallas, Columbus, Oral Care, Mass Retail, etc.)
  - ~12 questions naturally surface data quality friction (duplicate suppliers, SKU renames, invoice variances, bad debt, missing FKs)
  - Complements `question_categories.md` mapping rubric (no answer keys — future file)

## [1.6.0] - 2026-03-01

### Added

- **Neo4j schema generator** (`src/virt_graph/neo4j/schema.py`)
  - Reads any VG ontology and generates Neo4j Cypher DDL (uniqueness constraints)
  - Supports composite primary keys
  - `generate_schema(ontology)` returns statements; optional `driver` param executes them

- **Neo4j data loader** (`src/virt_graph/neo4j/loader.py`)
  - Ontology-driven migration from PostgreSQL to Neo4j
  - Handles polymorphic relationships via `vg:type_discriminator`
  - Edge attributes become relationship properties
  - Batch UNWIND for performance (configurable batch size)
  - `load_data(ontology, pg_conn, neo4j_driver)` returns MigrationMetrics
  - Distinguishes FK relationships from junction table relationships

- **PCG Neo4j infrastructure**
  - `pcg_example/neo4j/docker-compose.yml` — Neo4j 5 Community container
  - `pcg_example/tests/test_neo4j.py` — integration tests (skip if Neo4j unavailable)

## [1.5.0] - 2026-03-01

### Added

- **Schema match validation** (`scripts/validate_schema_match.py`)
  - Cross-references VG ontology against live PostgreSQL database
  - Checks: table existence, column existence, PK match, FK existence, row count plausibility
  - Exit codes: 0 (pass), 1 (fail), 2 (DB unavailable)
  - `pcg_example/tests/test_schema_match.py` — integration test (skips if DB unavailable)

### Changed

- **Docs refactor** — flattened from 12 files in 4 subdirectories to 8 flat files
  - Merged `concepts/ontology.md` + `ontology/linkml-format.md` → `ontology-system.md`
  - Merged `handlers/overview.md` + `traversal.md` + `pathfinding.md` + `network.md` → `handlers.md`
  - Removed stale `make` commands, replaced with `poetry run` equivalents
  - Removed Neo4j validation section from `validation.md`
  - Added schema match validation to `validation.md`

### Fixed

- **ChartOfAccounts** — removed `HasName` mixin (DB column is `account_name`, not `name`)
- **test_db_connection.py** — fixed PCG table list (`supplier_ingredients` not `supplier_offers`, `gl_journal` not `gl_journals`, added missing tables)

## [1.4.0] - 2026-03-01

### Added

- **Database connectivity tooling**
  - `src/virt_graph/db.py` — `get_connection()` + `connection()` context manager
  - Inline `.env` parser (no `python-dotenv` dependency) reads `DATABASE_URL`
  - `.env.example` with connection string template
  - `pcg_example/tests/test_db_connection.py` — integration test (skips if DB unavailable)

- **Benchmark question categories** (`pcg_example/benchmark/question_categories.md`)
  - Domain-agnostic category definitions for 85 benchmark questions
  - Difficulty tiers based on handler composition
  - VG/SQL feature coverage matrix
  - Template question patterns with abstract placeholders
  - Per-question mapping to handlers and operation types

- **Ontology creation lifecycle** (`docs/ontology/creating-ontologies.md`)
  - Phase 2: Complete FK Coverage — polymorphism, context blocks, edge attributes
  - Phase 3: Kinetic Enrichment — state machines, flows, axioms, actions, scenarios
  - Phase 4: Structural Patterns — class hierarchy, mixins, enums, imports
  - Phase 5: Schema Validation — cross-reference against live database
  - Inline SQL introspection queries for schema discovery

### Changed

- **Migrated from psycopg2 to psycopg (v3)**
  - Replaced `psycopg2-binary` with `psycopg[binary]>=3.1` in dependencies
  - Updated all handler imports: `from psycopg import Connection as PgConnection`
  - Updated `get_connection()` in `base.py` to use `psycopg.connect(conninfo)`
  - Connection type hint: `psycopg.Connection` replaces `psycopg2.extensions.connection`
  - All existing `%s` parameter style queries work unchanged with psycopg v3
- Project version `1.3.1` → `1.4.0`

---

## [1.3.1] - 2026-03-01

### Changed

- **Repository reorganization**
  - Moved `virt_graph.yaml` → `src/virt_graph/virt_graph.yaml` (ships with package)
  - Moved `scm_base.yaml` → `pcg_example/ontology/scm_base.yaml` (sibling of pcg.yaml)
  - Moved `schema.sql` → `pcg_example/pcg_schema.sql`
  - Moved gap analyses, whitepaper, research PDF → `planning/`
  - Updated all internal paths: metamodel loader, LinkML imports, test fixtures
  - Added `virt_graph.yaml` to pyproject.toml package data

### Removed

- `Makefile` — commands documented in CLAUDE.md, no build targets needed
- `scripts/validate_neo4j.py` — no Neo4j infrastructure on this branch
- `mkdocs.yml` — docs serving not currently active

---

## [1.3.0] - 2026-02-28

### Added

- **Supply Chain Base Schema (`scm_base.yaml`)**
  - Reusable structural patterns for supply chain domain ontologies
  - Abstract classes: `Location`, `TransactionDocument`, `LineItem`
  - Mixins: `HasActiveFlag` (is_active soft-delete), `HasName` (display name)
  - Shared slots: `name`, `status`, `is_active`, `day`, `quantity_kg`, `line_amount`, `total_amount`, `line_number`
  - `LocationType` enum (`plant`, `dc`, `retail`) for polymorphic location references

- **Class hierarchy in PCG ontology (v3.0)**
  - `imports: ../../scm_base` — PCG now imports scm_base via LinkML native imports
  - Location hierarchy: Plant, DistributionCenter, RetailLocation → Location (abstract)
  - TransactionDocument hierarchy: PO, GR, WorkOrder, Batch, Order, Shipment, Return, AP/AR Invoice → TransactionDocument
  - LineItem hierarchy: all 7 line item classes → LineItem
  - `HasActiveFlag` mixin on 10 master data entities (Supplier, Ingredient, SKU, etc.)
  - `HasName` mixin on 9 entities (removes duplicate `name` attribute declarations)
  - `LocationType` enum used on Inventory, RouteSegment, DemandForecast location_type columns

- **OntologyAccessor: SchemaView integration**
  - `SchemaView(merge_imports=True)` loaded alongside raw YAML for slot inheritance
  - New `get_class_inherited_attributes(name)` method returns all attributes including inherited ones
  - Abstract/mixin classes automatically excluded from TBox/RBox (no `instantiates`)
  - `.classes` property now surfaces `name`, `table`, `primary_key`, `description`, `attributes`
  - `.roles` property now surfaces `name`, `edge_table`, `domain_key`, `range_key`, `domain_class`, `range_class`, `operation_types`, `description`

- **Test suite** (`pcg_example/tests/test_structural_patterns.py`):
  - scm_base.yaml validity and LinkML loading (~5 tests)
  - Abstract class flag and TBox exclusion tests (~9 tests)
  - is_a hierarchy tests for all 3 hierarchies (~40 parametrized tests)
  - Mixin application tests (is_active on 10 classes, name on 9 classes)
  - Slot inheritance tests (inherited + local attributes)
  - LocationType enum value and usage tests
  - TBox/RBox count unchanged assertions

### Changed

- PCG ontology version `2.0.0` → `3.0.0`
- Project version `1.2.0` → `1.3.0`
- `vg:type_discriminator` annotations converted from native YAML dicts to `>-` JSON strings for SchemaView compatibility (consistent with all other complex VG annotations)
- Removed 9 duplicate `status` attribute declarations (inherited from TransactionDocument)
- Removed 9 duplicate `name` attribute declarations (inherited via HasName mixin)
- Updated test_ontology.py: version assertion `2.0.0` → `3.0.0`, added import and abstract exclusion tests

---

## [1.2.0] - 2026-02-28

### Added

- **PCG Ontology v2.0 — Complete Virtual Twin Declaration**
  - 20 new relationships (30→50): all FK columns in schema.sql now mapped
  - 7 polymorphic relationships: BatchProducesProduct, FormulaForProduct, RouteSegmentOrigin, RouteSegmentDestination, InventoryAtLocation, ShipmentFromOrigin, ShipmentToDestination
  - 5 `vg:type_discriminator` declarations for polymorphic target resolution
  - Transport network: `route_segments` declared with `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` operations and weight columns (distance_km, transit_time_hours)
  - SKU alias chain: `SKUSupersedes` with `recursive_traversal`, asymmetric/irreflexive/acyclic axioms
  - BOM hierarchy: `FormulaHasIngredients` now includes `path_aggregation` for cost rollups
  - 6 entity context blocks: Batch, Order, Shipment, Inventory, RouteSegment, GLJournal
  - 6 relationship context blocks: FormulaHasIngredients, BatchConsumesIngredient, RouteSegmentOrigin/Destination, ShipmentFromOrigin/ToDestination
  - 3 relationships with `vg:edge_attributes`: SupplierOffersIngredient, FormulaHasIngredients, BatchConsumesIngredient
  - `vg:sql_filter` on ProductionLineAtPlant (is_active = true)
  - 8 of 11 operation types now used (was 2)

- **New entity class attributes**:
  - Batch: `product_type`, `bom_level` (discriminators)
  - SKU: `supersedes_sku_id` (self-referential FK)
  - Shipment: `route_type` (polymorphism hint)
  - Inventory: `location_type` (discriminator)
  - RouteSegment: `origin_type`, `destination_type` (discriminators)
  - DemandForecast: `location_type`

- **Test suite** (`pcg_example/tests/test_graph_operations.py`):
  - Transport network operation tests (shortest_path, centrality, etc.)
  - SKU alias chain recursive traversal tests
  - Polymorphic relationship and type_discriminator tests
  - Context block coverage tests
  - Edge attribute tests
  - Operation type coverage tests (8 of 11)
  - New relationship existence and functional property tests

### Changed

- PCG ontology version `1.0.0` → `2.0.0`
- Project version `1.1.0` → `1.2.0`
- Updated test_ontology.py: EXPECTED_ROLE_COUNT `30` → `50`
- Scrubbed docs/ of legacy references (supplier_relationships, transport_routes, facilities → PCG table names)
- Updated README.md handler examples to use PCG patterns
- Updated docs/index.md project structure (fmcg_example → pcg_example)

---

## [1.1.0] - 2026-02-28

### Added

- **Metamodel v3.0 — Axioms, Virtual Kinetics, Actions**
  - 5 new enums: `AxiomSeverity`, `AxiomType`, `FlowType`, `ActionEffectType`, `PropagationDirection`
  - 7 new metamodel classes: `Axiom`, `StateTransition`, `StateMachine`, `FlowConfig`, `ActionEffect`, `Action`, `ScenarioParam`
  - 3 new kinetic operation types: `flow_analysis`, `state_analysis`, `scenario_analysis` (category: kinetic)
  - Extended `SQLMappedClass` with: `axioms`, `state_machine`, `actions`, `scenario_params`
  - Extended `SQLMappedRelationship` with: `axioms`, `flow_config`

- **OntologyAccessor kinetic methods**:
  - `get_class_axioms()`, `get_role_axioms()` — retrieve SQL-evaluable constraints
  - `get_class_state_machine()` — retrieve lifecycle state machine definition
  - `get_role_flow_config()` — retrieve material/financial flow metadata
  - `get_class_actions()` — retrieve semantic mutation definitions
  - `get_class_scenario_params()` — retrieve perturbable attributes
  - `get_classes_with_state_machines()` — discover stateful entities
  - `get_roles_with_flow_config()` — discover flow-bearing relationships
  - `get_conservation_groups()` — map conservation group names to member relationships
  - `_reset_metamodel_cache()` — classmethod for test isolation

- **Validation for kinetic extensions**:
  - Axiom validation: required fields, enum values, SQL injection detection
  - State machine validation: states, transitions, initial/terminal state references
  - Flow config validation: required fields, FlowType enum
  - Action validation: effects, effect_type enum, affected_relationships references
  - Scenario param validation: propagation direction enum

- **PCG reference ontology** (`pcg_example/ontology/pcg.yaml`):
  - 38 entity classes mapping all tables in schema.sql
  - 30 relationships covering FK relationships
  - 9 state machines (PurchaseOrder, GoodsReceipt, WorkOrder, Batch, Order, Shipment, Return, APInvoice, ARInvoice)
  - Axioms on key physics constraints (mass balance, temporal ordering, GL balance, positivity)
  - Actions on Order (allocate, ship), Shipment (dispatch, deliver), Batch (start/complete production)
  - Scenario params on Order, Plant, Supplier
  - 10 flow configs across material and financial flows
  - 3 conservation groups: procure_to_pay, order_to_cash, production_mass_balance

- **Test suite** (`pcg_example/tests/`):
  - `test_ontology.py` — structural validation (38 classes, 30 relationships, composite keys)
  - `test_kinetic_extensions.py` — kinetic extension validation (~20 tests)

- **Documentation for virtual kinetics** in `docs/ontology/vg-extensions.md`:
  - Axioms, State Machines, Flow Configuration, Actions, Scenario Parameters
  - Updated Operation Types table with kinetic category

- **Virtual Kinetics Stack** in `docs/concepts/architecture.md`:
  - 4-layer architecture: declared structure → derived properties → virtual what-if → simulation

### Changed

- Metamodel version `2.1` → `3.0` in `virt_graph.yaml`
- Project version `1.0.0` → `1.1.0`
- Replaced `fmcg_example/` with `pcg_example/` (old FMCG ontology archived to git history)
- Updated all paths in Makefile, scripts, pyproject.toml, README, CLAUDE.md
- Extended `show_ontology.py` to display state machines, axioms, actions, flow configs
- Extended `validate_ontology.py` default path to pcg_example

---

## [1.0.0] - 2026-02-28

### Changed

- **ontology-core branch** — Stripped to ontology construction, validation, and handler execution layer
- Removed `ARCHIVE/`, `supply_chain_example/`, `prompts/`, data generation scripts, DB infrastructure, and working notes
- Added FMCG reference ontology (`fmcg_example/ontology/prism_fmcg.yaml`) from fmcg branch
- Updated all scripts (`validate_ontology.py`, `show_ontology.py`, `validate_neo4j.py`) to default to FMCG ontology
- Trimmed Makefile to ontology/validation/handler targets only
- Removed data-gen-only dependencies (numpy, pandas, faker, scipy)
- Updated pyproject.toml testpaths to `fmcg_example/tests`
- Simplified README.md and CLAUDE.md to focus on ontology + handler framework

---

## [0.9.19] - 2025-12-16

### Added

- **Perfect Order Metric** - Realistic late delivery patterns for benchmarking:
  - 18% of shipped/delivered orders have `shipped_date` AFTER `required_date`
  - Enables Perfect Order Rate calculation of ~82% (industry average)
  - On-time orders ship 1-7 days after order, late orders ship 1-14 days after required date
  - Added `calculate_shipped_date()` helper function with late delivery logic

- **Temporal Route Flickering** - Seasonal transport routes for time-aware queries:
  - 10% of routes are "seasonal" (up from ~2%)
  - Seasonal routes active only 3 months/year (quarterly: summer, winter, spring, fall)
  - `route_status='seasonal'` with `is_active=True` for query filtering
  - Enables time-aware path queries: "Find route from A to B on date X"
  - Added seasonal route statistics reporting

- **Lumpy Demand Patterns** - Realistic demand volatility:
  - Gaussian noise (σ = 15%) added to sine wave seasonality
  - 5% chance of 2-3x demand spike per forecast period
  - Medical category designated as "bottleneck" with 2.5x demand multiplier
  - Ensures demand > capacity for at least one product line
  - Added spike and bottleneck statistics reporting

- **KPI Targets Generation** - SCOR Orchestrate domain data:
  - 14 standard supply chain KPIs with industry benchmark targets
  - **Delivery**: OTD (95%), Perfect Order (85%), Fill Rate (98%), Lead Time (5 days)
  - **Quality**: First Pass Yield (95%), Scrap Rate (<2%), Defect Rate (3400 DPMO)
  - **Inventory**: Turns (6/year), Days (60), Accuracy (99%)
  - **Production**: OEE (85%), Utilization (80%), Schedule Adherence (95%)
  - **Cost**: Freight Cost per Unit ($2.50)
  - Premium product-specific targets with tighter tolerances
  - Facility-specific OEE targets for problem work centers

### Changed

- **Data Generator** (`generate_data.py`):
  - `generate_orders()` uses late delivery logic for 18% imperfect orders
  - `generate_transport_routes()` returns seasonal months info, 10% seasonal rate
  - `generate_demand_forecasts()` adds Gaussian noise, spikes, and bottleneck category
  - Added `generate_kpi_targets()` method for Orchestrate domain
  - Added `self.kpi_targets` list to track KPI target data
  - SQL output includes KPI targets COPY section

### Technical

- Late deliveries: 18% ship 1-14 days after `required_date`
- Seasonal months tracked in Python dict (not persisted, for validation)
- Noise factor clamped to [0.5, 1.5] range for reasonable variance
- ~26 KPI targets generated: 14 global + 9 premium + 3 facility-specific

---

## [0.9.18] - 2025-12-16

### Added

- **"Supplier from Hell"** - Realistic problem supplier for benchmark testing:
  - "Reliable Parts Co" (ironic name) - T2 supplier with BB credit rating
  - 50% late deliveries on received POs (vs ~10% for normal suppliers)
  - Longer lead times: 45-90 days (vs 14-60 for normal suppliers)
  - Tracks `supplier_from_hell_id` for validation queries
  - Named entity for testing supplier performance analysis

- **Deep Aerospace BOM** - 22-level hierarchy for stress testing:
  - 68 aerospace parts: 3 per level × 22 levels + 2 packaging parts
  - Named parts: `AERO-RAW-*`, `AERO-L02-*` through `AERO-TOP-*`
  - True recycling cycle: `AERO-TOP-01` → `PACK-BOX-A1` → `RECYC-CARD-A1` → `AERO-TOP-01`
  - Tests SQL WITH RECURSIVE limits and cycle detection
  - Validates existing `NOT ... = ANY(p.path)` cycle prevention in CTE handlers
  - Benchmark talking point: SQL requires explicit cycle management vs Neo4j automatic detection

- **Realistic OEE Distribution** - Industry-accurate work center efficiency:
  - 10% poor performers (40-55% OEE) - tracked as `problem_work_center_ids`
  - 15% below average (55-65%)
  - 60% average (60-72%) - industry average is ~65%
  - 15% world-class (80-92%)
  - 3 named problem work centers: `WC-PROB-01`, `WC-PROB-02`, `WC-PROB-03`
  - Sources: Evocon OEE Report, ASCM SCOR-DS benchmarks

### Changed

- **Data Generator** (`generate_data.py`):
  - Added `generate_aerospace_bom()` method for 22-level hierarchy
  - `generate_suppliers()` now includes "Reliable Parts Co" with override rating
  - `generate_purchase_orders()` applies 50% late variance to "Supplier from Hell"
  - `generate_work_centers()` uses `get_realistic_oee()` function for distribution
  - Added tracking fields: `supplier_from_hell_id`, `aerospace_part_ids`, `problem_work_center_ids`

### Technical

- Aerospace BOM adds ~200 BOM entries (3 children × 3 parents × 22 levels + cycle)
- Named problem work centers have fixed OEE: 42%, 48%, 51%
- "Supplier from Hell" POs: late deliveries use +10-50% variance (vs ±30/20% normal)

---

## [0.9.17] - 2025-12-16

### Added

- **SCOR Orchestrate Domain** - New `kpi_targets` table for performance measurement:
  - Supports KPI categories: delivery, quality, cost, inventory, production
  - Target values with warning/critical thresholds
  - Product and facility-specific targets with effectivity dates
  - Schema now has 26 tables (was 25)

- **Realistic Data Distributions** - Addresses "Potemkin Village" feedback:
  - **Pareto/Zipf for Orders**: Top 20% of products receive ~80% of order volume
  - **Scale-Free Supplier Network**: Barabási-Albert preferential attachment creates natural "super hub" suppliers
  - Tracks `popular_product_ids` and `super_hub_supplier_ids` for validation

- **numpy dependency** - Added for statistical distributions (`numpy>=1.26`)

### Changed

- **Data Generator** (`generate_data.py`):
  - Added `create_zipf_weights()` and `zipf_sample()` for Pareto distribution
  - Added `preferential_attachment_targets()` for BA model
  - `generate_supplier_relationships()` now uses preferential attachment
  - `generate_orders()` uses Zipf-weighted product selection
  - `generate_products()` initializes distribution weights

### Technical

- Pre-samples products using numpy for efficient Zipf distribution
- Suppliers shuffled to simulate BA model arrival order
- Super hubs identified as suppliers with 10x median connections

---

## [0.9.16] - 2025-12-16

### Changed

- **PostgreSQL COPY format** - Data generator now uses COPY instead of INSERT:
  - ~10x faster bulk loading (30-60s vs 5-10 min)
  - ~6x smaller seed.sql file (~100MB vs 604MB)
  - Added `copy_str()`, `copy_num()`, `copy_bool()`, `copy_date()`, `copy_timestamp()` helpers

- **PostgreSQL tuning** - docker-compose.yml optimized for bulk loading:
  - `shared_buffers=256MB`, `work_mem=64MB`, `maintenance_work_mem=256MB`
  - `effective_cache_size=512MB`, `synchronous_commit=off`
  - `wal_level=minimal`, `checkpoint_completion_target=0.9`
  - 1GB memory limit for consistent performance

---

## [0.9.15] - 2025-12-16

### Added

- **SCOR Model Completion** - Plan/Source/Return domains with 5 new tables (~360K rows):
  - **Plan Domain**: `demand_forecasts` (~100K rows) - S&OP planning with seasonal patterns
  - **Source Domain**: `purchase_orders` + `purchase_order_lines` (~200K rows) - Parts procurement
  - **Return Domain**: `returns` + `return_items` (~16K rows) - Customer RMAs with dispositions

- **Supplier Hub Facilities** - Virtual facilities (one per supplier country) as procurement shipment origins

- **Extended Shipment Types** - Added `procurement` and `return` types to shipments table

- **Named entities for testing**:
  - `FC-2024-001`, `FC-2024-002`, `FC-2024-003` - Named demand forecasts
  - `PO-2024-00001`, `PO-2024-00002`, `PO-2024-00003` - Named purchase orders
  - `RMA-2024-001`, `RMA-2024-002` - Named returns
  - `SUPHUB-*` facilities - Supplier hubs by country code

### Changed

- **Schema**: 25 tables (was 20), facilities CHECK constraint includes `supplier_hub`
- **Shipments**: Added `purchase_order_id` and `return_id` FK columns
- **Data scale**: ~2.1M rows (was ~1.73M)

### Technical

- Demand forecasts use sine wave seasonality with category-specific phase shifts
- PO status lifecycle: draft → submitted → confirmed → shipped → received
- Return dispositions based on reason: defective→60% scrap, changed_mind→95% restock
- Generator correctly orders INSERTs to respect FK dependencies

---

## [0.9.14] - 2025-12-16

### Added

- **`order_by` parameter for traversal handlers** - Enables sequence-aware result ordering:
  - `fetch_nodes()` now accepts `order_by` parameter (e.g., `order_by="step_sequence"`)
  - `traverse()`, `traverse_collecting()`, `path_aggregate()` pass through ordering
  - Supports ascending (default) and descending (`"column DESC"`) ordering
  - Critical for reconstructing production runs from `work_order_steps`

- **Q69-Q85 benchmark questions** - 17 new questions covering Manufacturing Execution and Traceability:
  - **Q69-Q76: Manufacturing Execution** - Demand-to-supply linking, capacity aggregation, work center utilization, performance analysis
  - **Q77-Q85: Traceability & Quality (Genealogy)** - Component traceability, root cause analysis, impact radius, cost of quality, As-Built conformance

- **New ontology relationship mappings** in annotated_questions.md:
  - `FulfilledBy`: Order → WorkOrder
  - `HasRouting`: Product → ProductionRouting
  - `HasStep`: WorkOrder → WorkOrderStep
  - `ForWorkOrder`: MaterialTransaction → WorkOrder
  - `IssuesTo`: MaterialTransaction → Part
  - `LocatedAt`: WorkCenter → Facility

- **Dual-model table entries** for manufacturing:
  - `material_transactions` as Node (scrap analysis) and Edge (traceability)
  - `work_order_steps` as Node (performance) and Edge (capacity/queue)

- **Design Notes section** in annotated_questions.md:
  - As-Planned vs. As-Built path distinction
  - MaterialTransaction dual-model usage
  - Step sequence ordering requirements

### Documentation

- Updated `TODO.md` with Phase B manufacturing ontology implementation tasks
- Updated question inventory from 68 to 85 questions
- Updated summary statistics with new pattern types and handler counts

---

## [0.9.13] - 2025-12-16

### Added

- **Manufacturing Execution Domain** - 5 new tables (~1.24M rows):
  - `work_centers` (126 rows) - Manufacturing capacity at factories
  - `production_routings` (2,002 rows) - Process steps per product (3-5 steps each)
  - `work_orders` (120,000 rows) - Production orders (make-to-order/make-to-stock)
  - `work_order_steps` (480,352 rows) - Execution progress through routing
  - `material_transactions` (639,666 rows) - WIP, consumption, and scrap tracking

- **Named manufacturing entities for testing**:
  - `WC-ASM-01`, `WC-TEST-01`, `WC-PACK-01` - Named work centers at New York Factory
  - `WC-MUN-ASM`, `WC-MUN-FAB` - Named work centers at Munich Factory
  - `WO-2024-00001`, `WO-2024-00002`, `WO-2024-00003` - Named work orders

- **Manufacturing relationships** (planned for ontology v2):
  - Work center location, production routings, work order execution
  - Material transactions with split relationships by type (issue, receipt, scrap)

### Changed

- **Data scale**: ~1.73M rows across 20 tables (was 500K across 16 tables)
- Updated `generate_data.py` with manufacturing domain generation methods
- Regenerated seed data (~518 MB) with full manufacturing execution layer

### Documentation

- Comprehensive overhaul of `data_description.md` with actual database statistics
- Updated `README.md` with new table counts and manufacturing entities
- Updated Phase B plan (`warm-swimming-crystal.md`) with manufacturing relationships and Q69-Q76

---

## [0.9.12] - 2025-12-16

### Added

- **UoM conversion factors on `parts` table** - New columns for BOM weight/cost rollups:
  - `base_uom` - Base unit of measure (each, kg, m, L)
  - `unit_weight_kg` - Weight per unit in kilograms
  - `unit_length_m` - Length per unit in meters
  - `unit_volume_l` - Volume per unit in liters

- **`bom_with_conversions` SQL view** - Normalized BOM view for aggregations:
  - Joins `bill_of_materials` with `parts` conversion factors
  - Pre-computes `weight_kg` and `cost_usd` columns
  - Can be used as `edge_table` in ontology (views supported by metamodel)

### Changed

- Updated `generate_data.py` to populate conversion factors for all parts
- Regenerated seed data (~97 MB) with new columns

### Documentation

- Updated `data_description.md` with UoM handling section
- Updated Phase B plan (`warm-swimming-crystal.md`) with UoM implementation status

---

## [0.9.11] - 2025-12-16

### Added

- **Q61-68 benchmark questions** - 8 new questions testing metamodel v2.0/v2.1 features:
  - Temporal bounds (point-in-time BOM queries)
  - Dual-model nodes (BOMEntry, SupplierContract, Route, OrderLineItem)
  - sql_filter (active relationships, routes, shipment types)
  - edge_attributes

- **`annotated_questions.md`** - Comprehensive technical annotations for all 68 questions:
  - Pattern type, ontology elements, VG features, handler mappings
  - Summary statistics by pattern, feature, and handler
  - Dual-model table reference

- **Phase B implementation plan** (`warm-swimming-crystal.md`) - Ontology re-discovery plan using:
  - `virt_graph.yaml` as metamodel template
  - Split relationships with `sql_filter` for shipment polymorphism
  - Dual modeling strategy (same table as node + edge)

### Changed

- Archived old `supply_chain.yaml` to `ARCHIVE/` pending Phase B re-write
- Cleaned question hints from Q61-68 (moved to annotated file)

---

## [0.9.10] - 2025-12-15

### Breaking Changes

- **Metamodel version bumped to 2.1** in `virt_graph.yaml`
- **`vg:type_discriminator` now uses native YAML format** instead of JSON strings
  - Old: `vg:type_discriminator: '{"column": "owner_type", "mapping": {"user": "User"}}'`
  - New: `vg:type_discriminator: {column: owner_type, mapping: {user: User}}`

### Added

- **ContextBlock enhancements** - Two new fields for richer AI context:
  - `definition`: Formal business definition or glossary term
  - `data_quality_notes`: Known data issues, reliability warnings, or scope limitations

- **DiscriminatorEntry class** - New metamodel class for structured type discriminator mappings
  - Replaces JSON string format with native YAML
  - Fields: `discriminator_value`, `target_class`

### Changed

- `TypeDiscriminator.mapping` now uses `DiscriminatorEntry` instead of JSON string
- Updated `OntologyAccessor` validation and accessor methods for new format
- Updated documentation with new ContextBlock fields and TypeDiscriminator syntax

---

## [0.9.9-data] - 2025-12-15

### Breaking Changes

- **`order_items` table now uses composite primary key** `(order_id, line_number)` instead of serial `id`
  - Follows SAP VBAP pattern: Document Number + Item Number
  - Queries must use `WHERE order_id = X AND line_number = Y` instead of `WHERE id = X`

### Added

- **Shipment Type Polymorphism** - `shipment_type` column with 3 types:
  - `order_fulfillment` (70%): Customer order shipments with `order_id` FK
  - `transfer` (20%): Inter-facility transfers, `order_id` is NULL
  - `replenishment` (10%): Inbound from supplier, `order_id` is NULL
  - Enables `sql_filter` demonstration for polymorphic relationships

- **BOM Effectivity Dates** - Time-bounded bill of materials:
  - `effective_from` (DATE): When component became active
  - `effective_to` (DATE, nullable): When superseded (NULL = current)
  - Distribution: 80% current, 15% superseded, 5% future
  - Enables point-in-time BOM queries

- **Supplier Relationship Status** - Track relationship health:
  - `is_active` (BOOLEAN): Quick filter for active relationships
  - `relationship_status` (VARCHAR): 'active', 'suspended', 'terminated'
  - ~10% of relationships are inactive/suspended

- **Transport Route Status** - Track route availability:
  - `route_status` (VARCHAR): 'active', 'seasonal', 'suspended', 'discontinued'
  - ~5% of routes are non-active

### Changed

- **Data volume scaled to ~500K rows** (was ~130K):
  | Entity | Old | New |
  |--------|-----|-----|
  | Suppliers | 500 | 1,000 |
  | Parts | 5,008 | 15,008 |
  | BOM entries | 14,285 | 42,706 |
  | Products | 200 | 500 |
  | Facilities | 50 | 100 |
  | Customers | 1,000 | 5,000 |
  | Orders | 20,000 | 80,000 |
  | Order Items | 60,246 | 239,985 |
  | Shipments | 7,995 | 45,737 |
  | Inventory | 10,032 | 30,054 |
  | **Total** | ~130K | **~488K** |

- `generate_data.py` updated with new data generation logic
- `schema.sql` updated with new columns and composite key

### Indexes Added

- `idx_supplier_rel_active` - Partial index on active relationships
- `idx_bom_effective` - Index on effectivity date range
- `idx_transport_status` - Index on route status
- `idx_shipments_type` - Index on shipment type

---

## [0.9.8] - 2025-12-15

### Breaking Changes

- **`get_class_pk()` now returns `list[str]`** instead of `str` to support composite primary keys
- **`get_role_keys()` now returns `tuple[list[str], list[str]]`** instead of `tuple[str, str]` to support composite foreign keys
- **Metamodel version bumped to 2.0** in `virt_graph.yaml`

### Added

- **Composite Key Support** - Multi-column primary and foreign keys via JSON arrays
  - `vg:primary_key: '["order_id", "line_number"]'` for composite PKs
  - `vg:domain_key` and `vg:range_key` now accept JSON arrays
  - Handlers use tuple-based `NodeId` type: `NodeId = Union[int, tuple[Any, ...]]`

- **ContextBlock** - Structured AI hints for query generation
  - `vg:context` annotation on classes and relationships
  - Fields: `business_logic`, `llm_prompt_hint`, `traversal_semantics`, `examples`
  - New `get_role_context()` and `get_class_context()` methods

- **sql_filter** - SQL WHERE clause filtering for edge tables
  - `vg:sql_filter: "is_active = true AND status != 'suspended'"`
  - Injected into edge queries during traversal
  - Basic SQL injection pattern detection
  - New `get_role_filter()` method

- **edge_attributes** - Property Graph style edge properties
  - `vg:edge_attributes` for non-weight columns returned with edge data
  - New `get_role_edge_attributes()` method

- **Polymorphism Support** - Multi-class domain/range
  - `vg:domain_class` and `vg:range_class` accept JSON arrays
  - `vg:type_discriminator` for polymorphic target resolution
  - New methods: `get_role_domain_classes()`, `get_role_range_classes()`, `is_role_polymorphic()`, `get_role_type_discriminator()`

- **New metamodel classes** in `virt_graph.yaml`:
  - `ContextBlock` - AI context structure
  - `TraversalSemantics` - Inbound/outbound meaning
  - `EdgeAttribute` - Edge property definition
  - `TypeDiscriminator` - Polymorphic resolution config

### Changed

- All handlers (`traverse`, `shortest_path`, `centrality`, etc.) now accept:
  - `edge_from_col` and `edge_to_col` as `str | list[str]`
  - `sql_filter` parameter for edge filtering
- `fetch_edges_for_frontier()` and `fetch_nodes()` updated for composite keys
- Documentation updated with new feature examples

---

## [0.9.7] - 2025-12-15

### Breaking Changes

- **`OntologyAccessor` now requires explicit path** - No default ontology path; users must provide `Path` argument
  - `OntologyAccessor()` now raises `ValueError` if path not provided
  - All code using `OntologyAccessor` must now pass explicit path

### Changed

- **Reorganized project structure** - Separated supply chain example from core framework
  - Moved `ontology/virt_graph.yaml` → `virt_graph.yaml` (project root)
  - Created `supply_chain_example/` directory containing:
    - `ontology/supply_chain.yaml` - Example domain ontology
    - `postgres/` - Database schema, seed data, docker-compose
    - `neo4j/` - Neo4j setup and migration script
    - `scripts/generate_data.py` - Data generation
    - `tests/` - All 8 integration test files
    - `docs/supply-chain.md` - Tutorial documentation
    - `questions.md` - 60 benchmark questions
    - `README.md` - Example-specific documentation
  - Removed empty `ontology/` directory
  - Updated all scripts with new default paths
  - Updated Makefile with `supply_chain_example/` paths
  - Updated pyproject.toml testpaths

### Updated

- **Documentation** - All references to file paths updated:
  - CLAUDE.md - Updated key files and code examples
  - docs/index.md - Updated project structure
  - docs/concepts/ontology.md - Updated metamodel path
  - docs/concepts/architecture.md - Updated metamodel reference
  - docs/ontology/validation.md - Updated example paths
  - docs/ontology/vg-extensions.md - Updated metamodel reference
  - prompts/ontology_discovery.md - Updated metamodel path

---

## [0.9.6] - 2025-12-15

### Breaking Changes

- **Removed `traversal_complexity` system** - The GREEN/YELLOW/RED classification has been completely removed
  - Deleted `TraversalComplexity` enum from `virt_graph.yaml` metamodel
  - Deleted `traversal_complexity` slot from `SQLMappedRelationship`
  - Removed all `vg:traversal_complexity` annotations from `supply_chain.yaml`
  - Removed `get_role_complexity()` method from `OntologyAccessor`
  - `operation_types` is now the sole classification system

- **Removed `bom_explode()` function** - Use `path_aggregate(operation='multiply')` instead
  - Removed `BomExplodeResult` TypedDict
  - Tests updated to use generic `path_aggregate()` handler

### Changed

- `show_ontology.py` now displays `operation_types` instead of complexity colors
- **Complete documentation overhaul** - All docs now use operation types instead of complexity colors:
  - Deleted `docs/concepts/complexity-levels.md` (obsolete)
  - Updated all handler docs to use category names (Traversal, Algorithm) instead of colors
  - Replaced all `bom_explode()` examples with `path_aggregate(operation='multiply')`
  - Updated ontology docs with new `vg:operation_types` annotation examples
- Test fixtures in `test_pathfinding.py` now use dynamic data fetching instead of hardcoded facility names

### Fixed

- Type mismatch in `_aggregate_paths_cte()` for count operation (integer vs numeric)

---

## [0.9.5] - 2025-12-14

### Added

- **GOLD benchmark questions (Q51-Q60)** - 10 new "cross-domain polymorphism" questions that test traversals across multiple graph structures (BOM + Supplier + Logistics)
  - Grand Unified Chain (Q51-Q52): BOM → Supplier → Logistics in single query
  - Constrained Pathfinding (Q53-Q54): Graph algorithms with dynamic state filters
  - Hidden Dependencies (Q55-Q56): Network topology analysis, cycle detection
  - Plan vs. Actual (Q57): Graph definition vs. transactional history
  - Impact Analysis (Q58-Q60): End-to-end lineage and blast radius queries

- **`cycle_detection()` handler** noted in handler coverage for supply chain loop detection

### Changed

- Benchmark expanded from 50 to 60 questions
- Distribution: GREEN 17%, YELLOW 30%, RED 20%, MIXED 17%, GOLD 17%
- Updated ontology coverage matrix with GOLD question relationships
- Updated handler coverage counts

---

## [0.9.4] - 2025-12-14

### Added

- **Neo4j Graph Validator** (`scripts/validate_neo4j.py`) - Generic validation script that verifies Neo4j graph structure matches ontology definitions
  - Node label existence and count validation
  - Relationship type coverage and endpoint validation (domain/range)
  - Relationship count validation
  - Constraint validation (irreflexive, asymmetric)
  - CLI with `--json` output for CI integration
  - `make validate-neo4j` Makefile target

- **Neo4j Makefile commands**:
  - `make neo4j-stop` - Clean shutdown (stop then down)
  - `make neo4j-cycle` - Full cycle with wait (fixes stale PID issues)

- **Neo4j Troubleshooting section** in README - Documents stale PID issue and recovery commands

### Fixed

- **Ontology row_count annotations** - Updated to match current seed.sql data:
  - Part: 5003 → 5008, Inventory: 10056 → 10032, SupplierCertification: 721 → 707
  - SuppliesTo: 817 → 822, ComponentOf/HasComponent: 14283 → 14285
  - ConnectsTo: 197 → 212, CanSupply: 7582 → 7587, ContainsComponent: 619 → 612
  - OrderContains: 60241 → 60246, InventoryAt/InventoryOf: 10056 → 10032

---

## [0.9.3] - 2025-12-14

### Changed

- **MAX_RESULTS increased** from 1,000 to 100,000 to cover demo database (largest table ~60K rows)
- **CLAUDE.md improvements** - Added safety limits section, psycopg2 usage note, documentation commands
- **README.md** - Added note that `psql` CLI may not be available; use psycopg2

---

## [0.9.2] - 2025-12-14

### Added

- **Complete MkDocs documentation** - All referenced pages now exist
  - `concepts/architecture.md` - System overview, dispatch pattern, design principles
  - `concepts/complexity-levels.md` - GREEN/YELLOW/RED deep dive with decision tree
  - `handlers/traversal.md` - traverse(), traverse_collecting(), bom_explode() details
  - `handlers/pathfinding.md` - shortest_path(), all_shortest_paths() details
  - `handlers/network.md` - centrality(), connected_components(), resilience_analysis() details
  - `ontology/linkml-format.md` - LinkML basics, data types, inheritance
  - `ontology/vg-extensions.md` - Complete VG annotation reference
  - `ontology/creating-ontologies.md` - 4-round discovery protocol guide
  - `ontology/validation.md` - Two-layer validation explained
  - `examples/supply-chain.md` - Full tutorial with working code examples

### Removed

- **API Reference section** from mkdocs.yml - Claude reads source directly, making separate API docs redundant

---

## [0.9.1] - 2025-12-14

### Changed

- **virt_graph.yaml is now single source of truth** for VG extension validation
- `OntologyAccessor` dynamically loads validation rules from metamodel via LinkML SchemaView
- Removed hardcoded `ENTITY_REQUIRED`, `RELATIONSHIP_REQUIRED`, `VALID_COMPLEXITIES` constants

### Removed

- `ontology/TEMPLATE.yaml` - redundant; virt_graph.yaml serves as both metamodel and template

### Updated Documentation

- `docs/concepts/ontology.md` - explains metamodel-driven validation
- `prompts/ontology_discovery.md` - references virt_graph.yaml as source of truth
- `README.md` - added metamodel to Key Resources table
- `CLAUDE.md` - updated key files list

---

## [0.9.0] - 2025-12-08

### Changed

- **Lean academic publication branch** - Simplified repository structure
- Consolidated documentation from 25+ pages to 5 essential pages
- Simplified README.md with focused quick start and reference docs
- Simplified queries.md to concise VG/SQL benchmark catalogue

### Removed

- `.claude/skills/` - Handler, pattern, and schema skill definitions
- `benchmark/` - Entire benchmark suite (queries.yaml, ground truth, results, runner)
- `docs/` - MkDocs documentation pages (architecture, getting-started, ontology-guide, etc.)
- `neo4j/queries/` - All 25 Cypher query files
- `prompts/` - Analysis session prompts
- `REPORT.md`, `benchmarking.md` - Benchmark reports
- `virtgraph_whiteboard.png` - Whiteboard image
- Cleared `CLAUDE.md` content
- Stripped `mkdocs.yml` to minimal config

### Added

- `sql_pattern_cheat_sheet.md` - SQL and handler usage patterns
- `handler_pattern_cheat_sheet.md` - Handler signatures and parameters
- `experiment_notebook_1.md` - Experimental notes
- `benchmark_comparison.md` - Comparison documentation
- `neo4j_queries.md` - Neo4j query reference
- `the_plan.md` - Project planning document
- `RUN_1/` - Archive of benchmark run artifacts

---

## [0.8.x] - Development Release Series

### 0.8.10 - Handler Cookbook
- Added comprehensive handler cookbook with generic patterns
- Direction semantics documentation for all traversals

### 0.8.9 - Handler Enhancements
- `resilience_analysis()` handler for network vulnerability analysis
- `excluded_nodes` parameter for constrained pathfinding
- Named test entities (Acme Corp, Turbo Encabulator, Chicago Warehouse)
- Decimal type conversion fixes

### 0.8.8 - Benchmark Auto-Update
- Benchmark results auto-update documentation
- `make benchmark` and `make benchmark-vg` targets

### 0.8.7 - Documentation Overhaul
- MkDocs Material theme with full navigation
- Landing page with research question and key results

### 0.8.0 - Configurable Limits
- `max_nodes`, `skip_estimation`, `estimation_config` handler parameters
- Estimator module for pre-traversal size checking

---

## [0.7.0] - TBox/RBox Migration

- Migrated ontology to LinkML format with VG extensions
- Separated entity classes (TBox) from relationship classes (RBox)
- Two-layer validation (LinkML structure + VG annotations)

---

## [0.6.0] - Benchmark Completion

- 25-query benchmark suite across GREEN/YELLOW/RED routes
- Neo4j baseline comparison infrastructure
- 92% overall accuracy achieved, 26x faster than Neo4j

---

## [0.5.0] - Neo4j Baseline

- Neo4j migration script from PostgreSQL
- Cypher query ground truth generation
- Performance comparison infrastructure

---

## [0.4.0] - Network Handlers

- `shortest_path()` - Dijkstra via NetworkX
- `centrality()` - degree/betweenness/closeness/pagerank
- `connected_components()` - cluster detection
- RED route traffic light routing

---

## [0.3.0] - Traversal Handlers

- `traverse()` - frontier-batched BFS
- `bom_explode()` - bill of materials explosion
- Safety limits (MAX_DEPTH=50, MAX_NODES=10,000)
- YELLOW route implementation

---

## [0.2.0] - Ontology System

- LinkML-based ontology with SQL mappings
- `OntologyAccessor` for programmatic access
- Supply chain domain ontology (9 entities, 15 relationships)

---

## [0.1.0] - Initial Release

- PostgreSQL database infrastructure (15 tables, ~130K rows)
- Supply chain synthetic data generator
- Basic project structure and testing framework
