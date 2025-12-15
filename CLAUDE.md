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
make install              # Install dependencies via Poetry

# Database
make db-up                # Start PostgreSQL
make db-down              # Stop PostgreSQL
make db-reset             # Wipe and recreate (re-runs schema and seed)
make neo4j-up             # Start Neo4j (for benchmarking)
make neo4j-down           # Stop Neo4j

# Testing
make test                 # Run all tests
poetry run pytest tests/test_handler_safety.py -v           # Run specific test file
poetry run pytest tests/test_bom_explode.py::test_name -v   # Run single BOM/path_aggregate test

# Ontology
make validate-ontology    # Full two-layer validation
make validate-linkml      # LinkML structure only
make validate-vg          # VG annotation validation only
make show-ontology        # Show TBox/RBox definitions

# Documentation
make serve-docs           # Serve MkDocs locally (http://localhost:8000)
```

### Core Components

**Ontology** (`ontology/supply_chain.yaml`):
- LinkML format with VG extensions (`vg:` annotations)
- Entity classes (TBox) instantiate `vg:SQLMappedClass`
- Relationship classes (RBox) instantiate `vg:SQLMappedRelationship`
- Access via `OntologyAccessor` in `src/virt_graph/ontology.py`

**Handlers** (`src/virt_graph/handlers/`):
- `traversal.py`: `traverse()`, `path_aggregate()`, `traverse_collecting()`
- `pathfinding.py`: `shortest_path()`, `all_shortest_paths()`
- `network.py`: `centrality()`, `connected_components()`, `neighbors()`, `resilience_analysis()`
- `base.py`: Safety limits, edge fetching utilities, result TypedDicts

**Estimator** (`src/virt_graph/estimator/`):
- Statistical sampling for query planning
- Provides bounds estimation before executing expensive traversals

### Safety Limits

Default limits in `handlers/base.py` (can be overridden per-call via `max_nodes` parameter):
- `MAX_DEPTH=50` - Absolute traversal depth limit
- `MAX_NODES=10,000` - Max nodes per traversal
- `MAX_RESULTS=100,000` - Max rows returned (covers demo DB's largest table ~60K)
- `QUERY_TIMEOUT_SEC=30` - Per-query timeout

All handlers use **frontier-batched BFS** (never one query per node). Soft-delete filtering supported via `soft_delete_column` parameter. Temporal filtering supported via `valid_at`, `temporal_start_col`, and `temporal_end_col` parameters.

### Operation Types

Relationships are classified by `vg:operation_types` which map to specific handlers:

| Operation Type | Handler | Use Case |
|----------------|---------|----------|
| `direct_join` | SQL | Simple FK lookups |
| `recursive_traversal` | `traverse()` | Multi-hop paths |
| `temporal_traversal` | `traverse(valid_at=...)` | Time-bounded paths |
| `path_aggregation` | `path_aggregate()` | SUM/MAX/MIN along paths |
| `hierarchical_aggregation` | `path_aggregate(op='multiply')` | BOM quantity propagation |
| `shortest_path` | `shortest_path()` | Optimal routes |
| `centrality` | `centrality()` | Node importance |
| `connected_components` | `connected_components()` | Cluster detection |
| `resilience_analysis` | `resilience_analysis()` | Impact of node removal |

Access operation types via ontology:
```python
op_types = ontology.get_operation_types("SuppliesTo")  # ["recursive_traversal", "temporal_traversal"]
temporal = ontology.get_temporal_bounds("SuppliesTo")  # {"start_col": "contract_start_date", ...}
```

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
op_types = ontology.get_operation_types("SuppliesTo")
domain_key, range_key = ontology.get_role_keys("SuppliesTo")
```

## Database Access

**Use psycopg2 for PostgreSQL access** (not `psql` CLI - may not be installed):

```python
import psycopg2
conn = psycopg2.connect(
    host='localhost', port=5432, database='supply_chain',
    user='virt_graph', password='dev_password'
)
```

| Database   | Host      | Port | User        | Password     | Database      |
|------------|-----------|------|-------------|--------------|---------------|
| PostgreSQL | localhost | 5432 | virt_graph  | dev_password | supply_chain  |
| Neo4j      | localhost | 7687 | neo4j       | dev_password | neo4j         |

## Key Files

- `ontology/supply_chain.yaml` - Domain ontology with VG annotations
- `ontology/virt_graph.yaml` - VG metamodel (single source of truth for extensions and template)
- `prompts/ontology_discovery.md` - 4-round protocol for creating ontologies from new databases
