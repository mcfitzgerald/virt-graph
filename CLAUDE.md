# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Python environment and dependencies managed by poetry

Always use poetry to run python for this project

## Coding and Engineering Standards

Employ a judicious but robust testing strategy, and prefer integration tests versus unit tests unless unit test is critical

Always use context7 when I need code generation, setup or configuration steps (unless already documented in codebase), or
library/API documentation. This means you should automatically use the Context7 MCP
tools to resolve library id and get library docs without me having to explicitly ask.

Don't reinvent the wheel, search web for robust libraries and always opt for simple. Don't over-engineer!

Update `CHANGELOG.md`, `README.md`, `docs/`, `TODO.md` and `pyproject.toml` when committing with git, use semantic versioning

Unless noted otherwise, do not plan for backwards compatibility

## Project Overview

VG/SQL ("VeeJee over Sequel") enables graph-like queries over relational SQL data WITHOUT migration. It combines:
1. An **ontology** in LinkML format mapping graph concepts to relational structures
2. **Python handlers** for recursive traversal and graph algorithms
3. **Claude Code** for orchestration and on-the-fly query generation

## Common Commands

```bash
# Setup
make install          # Install Python dependencies via Poetry

# FMCG Example (Primary - Prism Consumer Goods)
make fmcg-db-up       # Start FMCG PostgreSQL (port 5433)
make fmcg-db-down     # Stop FMCG PostgreSQL
make fmcg-db-reset    # Reset FMCG database (wipe and reload)
make fmcg-generate    # Generate ~11.4M rows of seed data (~2-3 minutes)
make fmcg-validate    # Validate data without writing SQL
make fmcg-test        # Run FMCG tests

# Legacy (supply_chain_example - archived)
make db-up/db-down    # Start/stop supply chain PostgreSQL (port 5432)
make test             # Run supply chain tests

# Neo4j (for benchmarking)
make neo4j-up         # Start Neo4j
make neo4j-down       # Stop Neo4j
make neo4j-cycle      # Full reset (fixes PID issues)

# Single test
poetry run pytest fmcg_example/tests/test_recall_trace.py -v           # Single test file
poetry run pytest fmcg_example/tests/test_recall_trace.py::test_name -v  # Single test

# Ontology validation
make validate-ontology  # Full two-layer validation (LinkML + VG)
make show-ontology      # Show TBox/RBox definitions

# Documentation
make serve-docs       # Serve docs at localhost:8000
```

## Architecture

### Core Components

```
src/virt_graph/
├── ontology.py           # OntologyAccessor - reads LinkML ontology with VG extensions
├── handlers/             # Graph operation handlers
│   ├── base.py           # Safety limits, edge fetching, result TypedDicts
│   ├── traversal.py      # traverse(), path_aggregate(), traverse_collecting()
│   ├── pathfinding.py    # shortest_path(), all_shortest_paths()
│   └── network.py        # centrality(), connected_components(), resilience_analysis()
└── estimator/            # Runtime estimation and guards
    ├── sampler.py        # Graph sampling for property detection
    ├── models.py         # Estimation models with damping
    ├── bounds.py         # DDL-derived table statistics
    └── guards.py         # Runtime safety guards
```

### Key Concepts

**Two-layer validation**: Ontologies are validated first by LinkML (structure) then by VG metamodel (`virt_graph.yaml`) for required annotations.

**Operation types**: Relationships in the ontology declare which operations they support:
- `direct_join` → Standard SQL
- `recursive_traversal` → `traverse()` handler
- `path_aggregation`, `hierarchical_aggregation` → `path_aggregate()` handler
- `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` → Network handlers

**Handler pattern**: All handlers are schema-parameterized—they take table/column names as arguments, not hardcoded SQL. Example:
```python
traverse(conn, nodes_table="suppliers", edges_table="supplier_relationships",
         edge_from_col="seller_id", edge_to_col="buyer_id", start_id=123)
```


### Database Access

Use `psycopg2` for PostgreSQL (psql CLI may not be available):
```python
import psycopg2

# FMCG database (primary)
conn = psycopg2.connect(host='localhost', port=5433, database='prism_fmcg',
                        user='virt_graph', password='dev_password')

# Legacy supply chain database
conn = psycopg2.connect(host='localhost', port=5432, database='supply_chain',
                        user='virt_graph', password='dev_password')
```

## Metamodel

`virt_graph.yaml` is the single source of truth for VG extensions. It defines:
- `SQLMappedClass` - For entity classes (TBox): requires `vg:table`, `vg:primary_key` (supports composite keys)
- `SQLMappedRelationship` - For relationships (RBox): requires `vg:table`, `vg:domain_key`, `vg:range_key`, `vg:operation_types`
- `OperationType` enum - Maps to handler functions
- `OperationCategory` enum - Groups operation types by handler family
- `ContextBlock` - Structured AI context for query generation (business_logic, llm_prompt_hint, traversal_semantics)
- `TypeDiscriminator` - Polymorphic relationship target resolution
- `EdgeAttribute` - Property Graph style edge properties

**Key features**:
- Composite keys: Use JSON arrays for `vg:primary_key`, `vg:domain_key`, `vg:range_key`
- Polymorphism: Use `vg:range_class` as array + `vg:type_discriminator` for multiple target types
- Edge filtering: Use `vg:sql_filter` for conditional edge traversal
- AI context: Use `vg:context` (ContextBlock) to provide domain hints for Claude

See `docs/ontology/vg-extensions.md` for detailed documentation.

## Working with Ontologies

The `OntologyAccessor` class provides the API for reading ontologies:
```python
from virt_graph.ontology import OntologyAccessor
from pathlib import Path

# FMCG ontology (primary - 71 classes, ~50 relationships)
ontology = OntologyAccessor(Path("fmcg_example/ontology/prism_fmcg.yaml"))

# Get table mapping for a class
table = ontology.get_class_table("Supplier")       # → "suppliers"
pk = ontology.get_class_pk("Order")                # → ["id"]

# Get relationship configuration
op_types = ontology.get_operation_types("SuppliesTo")  # → ["recursive_traversal"]
domain_keys, range_keys = ontology.get_role_keys("HasBatch")
```

## FMCG Example

Primary example demonstrating VG/SQL on an FMCG supply chain (~14.7M rows, 70 tables). Full specification: `FMCG_EXAMPLE_MASTER_PLAN.md`

**Architecture**: "Formula-to-Shelf" pipeline with convergent-divergent fan-out:
- **Convergent**: Many ingredients → 1 batch (SOURCE/TRANSFORM)
- **Divergent**: 1 batch → 20 SKUs → 50K retail nodes (ORDER/FULFILL)
- **SCOR-DS Loop**: Plan ↔ Source ↔ Transform ↔ Order ↔ Fulfill ↔ Return ↔ Orchestrate

**The Desmet Triangle**: Every edge carries three dimensions in tension:
- **Service**: OTIF, OSA, Fill Rate
- **Cost**: Landed cost, freight, handling
- **Cash**: Inventory days, payment terms

**Named test entities** (deterministic fixtures for benchmarking):
- `B-2024-RECALL-001` - Contaminated batch for recall trace (1 batch → 47K orders)
- `ACCT-MEGA-001` - MegaMart hub (4,500 stores, 25% of orders)
- `SUP-PALM-MY-001` - Single-source Palm Oil supplier (SPOF detection)
- `DC-NAM-CHI-001` - Chicago DC bottleneck (40% NAM volume)
- `PROMO-BF-2024` - Black Friday promotion (bullwhip effect, 3x demand)

**Beast mode queries**:
- Recall trace: `traverse()` from batch to affected orders
- Landed cost: `path_aggregate()` for margin calculation
- SPOF detection: `resilience_analysis()` for supplier criticality
- OSA root cause: `centrality()` for DC bottlenecks

**Data generation patterns** (see `fmcg_example/scripts/data_generation/`):
- Barabási–Albert preferential attachment for scale-free network topology
- Zipf distribution for Pareto (80/20) realism
- Bullwhip effect: 1.54x order CV vs POS CV, +12.4% forecast bias
- Chaos injection: 5 risk events, 6 behavioral quirks, multi-promo calendar
