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

Raw pattern recordings in `patterns/raw/`:
- Supplier tier traversal (upstream/downstream)
- BOM explosion and where-used analysis
- Impact analysis for supplier failures
- Shortest path with cost/distance/time weights
- Centrality and connectivity analysis

## Critical Implementation Rules

- **Frontier batching mandatory**: One SQL query per depth level, never per node
- **Size guards**: Check before NetworkX load; >5K nodes must warn or fail
- **Hybrid SQL/Python**: Python orchestrates traversal, SQL filters; never bulk load entire tables
- **Safety limits are non-negotiable**: MAX_DEPTH=50, MAX_NODES=10,000, MAX_RESULTS=1,000, QUERY_TIMEOUT=30s

## Database

PostgreSQL 14 with supply chain schema (15 tables, ~130K rows):
- Connection: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
- Key tables: suppliers, supplier_relationships, parts, bill_of_materials, facilities, transport_routes

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

## MCP Integration

Always use Context7 MCP tools (`resolve-library-id` → `get-library-docs`) when generating code, configuration, or needing library documentation.

## Project Management

- Update `CHANGELOG.md` and `pyproject.toml` with semantic versioning on every commit
- Run integration tests for each phase (prefer integration over unit tests)
- Documentation lives in `docs/` - update when adding features
- Update `CLAUDE.md` if needed
- Use Claude's todo list to manage complex task
