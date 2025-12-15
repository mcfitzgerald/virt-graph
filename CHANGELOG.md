# Changelog

All notable changes to this project will be documented in this file.

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
- Documentation updated throughout to reference operation types
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
