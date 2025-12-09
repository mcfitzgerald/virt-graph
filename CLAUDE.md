# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Quick Commands

```bash
# Setup
poetry install
make db-up              # Start PostgreSQL
make test               # Run all tests

# Database
make db-reset           # Reset database
make db-logs            # View logs

# Ontology
make validate-ontology  # Two-layer validation
make show-tbox          # Entity classes
make show-rbox          # Relationships

# Benchmark
make benchmark          # Full benchmark (VG + Neo4j)
make benchmark-vg       # Virtual Graph only

# Documentation
make serve-docs         # Serve docs locally
```

## Architecture

Routes queries by complexity:
- **GREEN**: Direct SQL - simple lookups/joins
- **YELLOW**: `traverse()` - recursive BFS traversal
- **RED**: NetworkX - pathfinding/centrality

## Handlers

**YELLOW (Traversal)**:
- `traverse(conn, nodes_table, edges_table, edge_from_col, edge_to_col, start_id, direction, max_depth)`
- `bom_explode(conn, start_part_id, max_depth, include_quantities)`

**RED (Network)**:
- `shortest_path(conn, ..., start_id, end_id, weight_col)`
- `centrality(conn, ..., centrality_type, top_n)`
- `connected_components(conn, ..., min_size)`

## Safety Limits

Non-negotiable:
- `MAX_DEPTH = 50`
- `MAX_NODES = 10,000`
- `MAX_RESULTS = 1,000`
- `QUERY_TIMEOUT = 30s`

## Database

PostgreSQL 14 with supply chain schema (15 tables, ~130K rows):
- Connection: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`

Named entities:
- Suppliers: "Acme Corp", "GlobalTech Industries", "Pacific Components"
- Products: "Turbo Encabulator" (TURBO-001), "Flux Capacitor" (FLUX-001)
- Facilities: "Chicago Warehouse" (FAC-CHI), "LA Distribution Center" (FAC-LA)

## Ontology

LinkML format in `ontology/supply_chain.yaml`:

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor()
table = ontology.get_class_table("Supplier")  # "suppliers"
domain_key, range_key = ontology.get_role_keys("SuppliesTo")  # ("seller_id", "buyer_id")
complexity = ontology.get_role_complexity("ConnectsTo")  # "RED"
```

## Testing

```bash
make test-gate1   # Database and core handlers
make test-gate2   # Ontology and traversal
```

## Project Management

- Update `CHANGELOG.md` and `pyproject.toml` on commits
- Run tests before committing
- Current version: see `pyproject.toml`
