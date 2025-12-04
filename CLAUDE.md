# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Environment setup
poetry install

# Add dependencies
poetry add <package>

# Run Python in project environment
poetry run python <script.py>

# Run tests
poetry run pytest

# Run single test
poetry run pytest tests/test_file.py::test_function -v

# Start database
docker-compose up -d

# View database logs
docker-compose logs -f postgres

# Reset database (regenerate data)
docker-compose down -v && docker-compose up -d

# Regenerate seed data
poetry run python scripts/generate_data.py

# Serve documentation
poetry run mkdocs serve

# Run benchmark suite (requires Neo4j running)
docker-compose -f neo4j/docker-compose.yml up -d
poetry run python neo4j/migrate.py
poetry run python benchmark/generate_ground_truth.py
poetry run python benchmark/run.py --system both

# Check database status
docker-compose ps
docker-compose logs -f  # Follow all logs
```

## Project Overview

Virtual Graph enables graph-like queries over enterprise relational data without migrating to a graph database. The system uses an LLM to reason over SQL using a discovered ontology and learned SQL patterns.

## Architecture

The system routes queries through three paths based on complexity:

- **GREEN**: Simple SQL - direct lookups/joins, no handlers needed
- **YELLOW**: Recursive traversal - uses `traverse()` handler with frontier-batched BFS
- **RED**: Network algorithms - uses NetworkX handlers for pathfinding/centrality

Key components in `src/virt_graph/`:
- `handlers/base.py` - Safety limits, frontier batching utilities, exceptions
- `handlers/traversal.py` - Generic BFS traversal, schema-parameterized
- `handlers/pathfinding.py` - Dijkstra shortest path via NetworkX
- `handlers/network.py` - Centrality, connected components

## Handlers

Available handlers for graph operations:

**YELLOW (Recursive Traversal)**:
- `traverse(conn, nodes_table, edges_table, edge_from_col, edge_to_col, start_id, direction, max_depth)` - Generic BFS traversal
- `traverse_collecting(conn, ..., target_condition)` - Traverse and collect nodes matching condition
- `bom_explode(conn, start_part_id, max_depth, include_quantities)` - BOM explosion with quantities

**RED (Network Algorithms)**:
- `shortest_path(conn, nodes_table, edges_table, ..., start_id, end_id, weight_col)` - Dijkstra shortest path
- `all_shortest_paths(conn, ..., max_paths)` - Find all optimal routes
- `centrality(conn, ..., centrality_type, top_n)` - Degree/betweenness/closeness/PageRank
- `connected_components(conn, ..., min_size)` - Find graph clusters
- `graph_density(conn, edges_table, ...)` - Network statistics
- `neighbors(conn, ..., node_id, direction)` - Direct neighbor lookup

## Patterns

**Raw patterns** in `patterns/raw/` - discovered query patterns with recorded parameters.

**Pattern templates** in `patterns/templates/` - generalized, reusable patterns:
- `traversal/` - tier_traversal, bom_explosion, where_used
- `pathfinding/` - shortest_path, all_paths
- `aggregation/` - impact_analysis
- `network-analysis/` - centrality, components

Each template includes applicability signals, ontology bindings, variants, and examples.

## Critical Implementation Rules

- **Frontier batching mandatory**: One SQL query per depth level, never per node
- **Size guards**: Check before NetworkX load; >5K nodes must warn or fail
- **Hybrid SQL/Python**: Python orchestrates traversal, SQL filters; never bulk load entire tables
- **Safety limits are non-negotiable**: MAX_DEPTH=50, MAX_NODES=10,000, MAX_RESULTS=1,000, QUERY_TIMEOUT=30s

## Database

PostgreSQL 14 with supply chain schema (15 tables, ~130K rows):
- Connection: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
- Key tables: suppliers, supplier_relationships, parts, bill_of_materials, facilities, transport_routes

Named test entities for queries:
- Suppliers: "Acme Corp", "GlobalTech Industries", "Pacific Components"
- Products: "Turbo Encabulator" (TURBO-001), "Flux Capacitor" (FLUX-001)
- Facilities: "Chicago Warehouse" (FAC-CHI), "LA Distribution Center" (FAC-LA)

## Ontology

The discovered ontology (`ontology/supply_chain.yaml`) maps semantic concepts to physical SQL:
- **8 Classes**: Supplier, Part, Product, Facility, Customer, Order, Shipment, SupplierCertification
- **12 Relationships** with traversal complexity (GREEN/YELLOW/RED)
- Use ontology mappings when generating SQL for graph queries

Key relationship complexities:
- **GREEN**: Simple FK joins (provides, can_supply, contains_component, etc.)
- **YELLOW**: Recursive traversal (supplies_to, component_of)
- **RED**: Network algorithms with weights (connects_to)

## Skills

Claude Code skills in `.claude/skills/`:
- `schema/` - Schema introspection queries and skill definition
- `patterns/` - Pattern template matching and selection
- `handlers/` - Handler invocation and parameter resolution

Use skills to:
1. Match queries to pattern templates (`patterns/SKILL.md`)
2. Resolve parameters from ontology
3. Invoke handlers with resolved parameters (`handlers/SKILL.md`)

## MCP Integration

Always use Context7 MCP tools (`resolve-library-id` → `get-library-docs`) when generating code, configuration, or needing library documentation.

## Testing

Gate validation tests in `tests/`:
- `test_gate1_validation.py` - Database and core handler tests
- `test_gate2_validation.py` - Ontology and traversal tests
- `test_gate3_validation.py` - Pattern matching tests
- `test_gate4_validation.py` - Pathfinding and network tests
- `test_gate5_validation.py` - Benchmark infrastructure tests

Run specific test: `poetry run pytest tests/test_gate1_validation.py::test_bom_traversal -v`

## Project Management

- Update `CHANGELOG.md` and `pyproject.toml` with semantic versioning on every commit
- Run integration tests for each phase (prefer integration over unit tests)
- Documentation lives in `docs/` - update when adding features
- Update `CLAUDE.md` if needed
- Use Claude's todo list to manage complex tasks
- Current version: see `pyproject.toml` (follows semantic versioning)
