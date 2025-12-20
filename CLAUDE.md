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

# Databases (Docker required)
make db-up            # Start PostgreSQL
make db-down          # Stop PostgreSQL
make db-reset         # Reset PostgreSQL (wipe and recreate)
make neo4j-up         # Start Neo4j (for benchmarking)
make neo4j-down       # Stop Neo4j
make neo4j-cycle      # Full reset (fixes PID issues)

# Testing
make test             # Run all tests
make test-handlers    # Run handler safety tests only
make test-ontology    # Run ontology validation tests only
poetry run pytest supply_chain_example/tests/test_traversal.py -v  # Single test file
poetry run pytest supply_chain_example/tests/test_traversal.py::test_name -v  # Single test

# Ontology validation
make validate-ontology  # Full two-layer validation (LinkML + VG)
make validate-linkml    # LinkML structure only
make validate-vg        # VG annotations only
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
conn = psycopg2.connect(host='localhost', database='supply_chain',
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
ontology = OntologyAccessor(Path("supply_chain_example/ontology/supply_chain.yaml"))
table = ontology.get_class_table("Supplier")
op_types = ontology.get_operation_types("SuppliesTo")
```
