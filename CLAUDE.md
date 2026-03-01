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

Update `CHANGELOG.md`, `README.md`, and `pyproject.toml` and relevant documentation (`docs/`) when committing with git, use semantic versioning

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

# Ontology validation
make validate-ontology  # Full two-layer validation (LinkML + VG)
make show-ontology      # Show TBox/RBox definitions

# Testing
make test-ontology      # Run ontology validation tests
poetry run pytest pcg_example/tests/ -v  # All tests

# Neo4j (for benchmarking)
make neo4j-up         # Start Neo4j
make neo4j-down       # Stop Neo4j
make neo4j-cycle      # Full reset (fixes PID issues)

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
- `flow_analysis`, `state_analysis`, `scenario_analysis` → Kinetic (ad-hoc SQL via Claude)

**Handler pattern**: All handlers are schema-parameterized—they take table/column names as arguments, not hardcoded SQL. Example:
```python
traverse(conn, nodes_table="suppliers", edges_table="supplier_relationships",
         edge_from_col="seller_id", edge_to_col="buyer_id", start_id=123)
```

### Reference Ontology

`pcg_example/ontology/pcg.yaml` — PCG ERP supply chain ontology (38 classes, 30 relationships) with kinetic annotations (state machines, axioms, flow configs, actions, scenario params).

### Database Access

Use `psycopg2` for PostgreSQL (psql CLI may not be available):
```python
import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, database='prism_fmcg',
                        user='virt_graph', password='dev_password')
```

## Metamodel

`virt_graph.yaml` is the single source of truth for VG extensions (v3.0). It defines:
- `SQLMappedClass` - For entity classes (TBox): requires `vg:table`, `vg:primary_key` (supports composite keys)
- `SQLMappedRelationship` - For relationships (RBox): requires `vg:table`, `vg:domain_key`, `vg:range_key`, `vg:operation_types`
- `OperationType` enum - Maps to handler functions (includes kinetic: flow_analysis, state_analysis, scenario_analysis)
- `OperationCategory` enum - Groups operation types by handler family (includes kinetic)
- `ContextBlock` - Structured AI context for query generation (business_logic, llm_prompt_hint, traversal_semantics)
- `TypeDiscriminator` - Polymorphic relationship target resolution
- `EdgeAttribute` - Property Graph style edge properties
- `Axiom` - SQL-evaluable data integrity constraints (on classes and relationships)
- `StateMachine` / `StateTransition` - Lifecycle state definitions
- `FlowConfig` - Material/information/financial flow metadata
- `Action` / `ActionEffect` - Semantic mutation definitions for what-if reasoning
- `ScenarioParam` - Perturbable attributes with propagation direction

**Key features**:
- Composite keys: Use JSON arrays for `vg:primary_key`, `vg:domain_key`, `vg:range_key`
- Polymorphism: Use `vg:range_class` as array + `vg:type_discriminator` for multiple target types
- Edge filtering: Use `vg:sql_filter` for conditional edge traversal
- AI context: Use `vg:context` (ContextBlock) to provide domain hints for Claude
- Axioms: Use `vg:axioms` for SQL-evaluable constraints (class + relationship level)
- State machines: Use `vg:state_machine` for lifecycle definitions
- Flow config: Use `vg:flow_config` for throughput/conservation analysis
- Actions: Use `vg:actions` for what-if reasoning (NOT executable)
- Scenario params: Use `vg:scenario_params` for perturbation analysis

See `docs/ontology/vg-extensions.md` for detailed documentation.

## Working with Ontologies

The `OntologyAccessor` class provides the API for reading ontologies:
```python
from virt_graph.ontology import OntologyAccessor
from pathlib import Path

ontology = OntologyAccessor(Path("pcg_example/ontology/pcg.yaml"))

# Get table mapping for a class
table = ontology.get_class_table("Supplier")       # → "suppliers"
pk = ontology.get_class_pk("Order")                # → ["id"]

# Get relationship configuration
op_types = ontology.get_operation_types("OrderHasLines")  # → ["direct_join"]
domain_keys, range_keys = ontology.get_role_keys("BatchConsumesIngredient")

# Kinetic extensions (v3.0)
sm = ontology.get_class_state_machine("Order")     # → {"state_column": "status", ...}
axioms = ontology.get_class_axioms("Shipment")     # → [{"name": "temporal_order", ...}]
fc = ontology.get_role_flow_config("BatchConsumesIngredient")  # → {"flow_type": "material", ...}
actions = ontology.get_class_actions("Batch")       # → [{"name": "start_production", ...}]
params = ontology.get_class_scenario_params("Plant") # → [{"attribute": "capacity_tons_per_day", ...}]

# Discovery queries
ontology.get_classes_with_state_machines()          # → ["PurchaseOrder", "Order", ...]
ontology.get_roles_with_flow_config()               # → ["BatchConsumesIngredient", ...]
ontology.get_conservation_groups()                  # → {"procure_to_pay": [...], ...}
```
