# Changelog

All notable changes to this project will be documented in this file.

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
