# Changelog

All notable changes to this project will be documented in this file.

## [0.9.0] - 2025-12-08

### Changed

- **Lean academic publication branch** - Simplified repository structure
- Consolidated documentation from 25+ pages to 5 essential pages
- Removed patterns/, archive/, and unused prompts
- Simplified CLAUDE.md and configuration files

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
