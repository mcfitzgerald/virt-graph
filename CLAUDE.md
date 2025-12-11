# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VG/SQL ("VeeJee over Sequel") enables graph-like queries over relational SQL data WITHOUT migration. It combines:
1. A LinkML ontology mapping graph concepts to relational structures
2. Python handlers for recursive traversal and graph algorithms
3. Claude Code as the orchestrator for on-the-fly query generation

## Common Commands

```bash
# Setup
make install          # Install dependencies via Poetry

# Database management
make db-up            # Start PostgreSQL
make db-down          # Stop PostgreSQL
make db-reset         # Wipe and recreate PostgreSQL (re-runs schema and seed scripts)
make neo4j-up         # Start Neo4j (for benchmarking)
make neo4j-down       # Stop Neo4j

# Testing
make test             # Run all tests
poetry run pytest tests/test_gate1_validation.py -v   # Run specific test file
poetry run pytest tests/test_bom_explode.py::test_function_name -v   # Run single test

# Ontology validation (two-layer)
make validate-ontology    # Full validation
make validate-linkml      # LinkML structure only
make validate-vg          # VG annotation validation only
make show-ontology        # Show TBox/RBox definitions
```

## Architecture

### Complexity Classification (GREEN/YELLOW/RED)

The ontology classifies relationships by query strategy in `vg:traversal_complexity`:

- **GREEN**: Direct SQL joins/aggregations - use standard SQL
- **YELLOW**: Recursive traversal - use `traverse()` or `bom_explode()` handlers
- **RED**: Graph algorithms - use `shortest_path()`, `centrality()`, etc. via NetworkX

### Core Components

**Ontology** (`ontology/supply_chain.yaml`):
- LinkML format with VG extensions (`vg:` annotations)
- Entity classes (TBox) instantiate `vg:SQLMappedClass`
- Relationship classes (RBox) instantiate `vg:SQLMappedRelationship`
- Access via `OntologyAccessor` in `src/virt_graph/ontology.py`

**Handlers** (`src/virt_graph/handlers/`):
- `traversal.py`: `traverse()`, `bom_explode()`, `traverse_collecting()` - YELLOW complexity
- `pathfinding.py`: `shortest_path()`, `all_shortest_paths()` - RED complexity
- `network.py`: `centrality()`, `connected_components()`, `neighbors()`, `resilience_analysis()` - RED complexity
- `base.py`: Safety limits, edge fetching utilities, result TypedDicts

**Estimator** (`src/virt_graph/estimator/`):
- Statistical sampling for query planning
- Provides bounds estimation before executing expensive traversals

### Handler Pattern

All handlers are schema-parameterized - they accept table/column names as arguments:

```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=some_id,
    direction="inbound",
    max_depth=10,
)
```

### Ontology Access

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor()  # Uses default ontology/supply_chain.yaml
table = ontology.get_class_table("Supplier")
complexity = ontology.get_role_complexity("SuppliesTo")
domain_key, range_key = ontology.get_role_keys("SuppliesTo")
```

### Workflow for Answering Questions

1. Read the ontology to understand available entities and relationships
2. Determine complexity: GREEN (direct SQL), YELLOW (traverse/bom_explode), or RED (graph algorithms)
3. Generate query on-the-fly: SQL for GREEN, handler call for YELLOW/RED
4. Execute and return results

## Database Credentials

| Database   | Host      | Port | User        | Password     | Database      |
|------------|-----------|------|-------------|--------------|---------------|
| PostgreSQL | localhost | 5432 | virt_graph  | dev_password | supply_chain  |
| Neo4j      | localhost | 7687 | neo4j       | dev_password | neo4j         |

## Key Files

- `ontology/supply_chain.yaml` - Domain ontology with VG annotations
- `ontology/virt_graph.yaml` - VG metamodel (extension definitions)
- `ontology/TEMPLATE.yaml` - Template for new ontologies
- `prompts/ontology_discovery.md` - 4-round protocol for creating ontologies from new databases
