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
- `handlers/pathfinding.py` - Dijkstra shortest path via NetworkX (Phase 3)
- `handlers/network.py` - Centrality, connected components (Phase 3)

## Critical Implementation Rules

- **Frontier batching mandatory**: One SQL query per depth level, never per node
- **Size guards**: Check before NetworkX load; >5K nodes must warn or fail
- **Hybrid SQL/Python**: Python orchestrates traversal, SQL filters; never bulk load entire tables
- **Safety limits are non-negotiable**: MAX_DEPTH=50, MAX_NODES=10,000, MAX_RESULTS=1,000, QUERY_TIMEOUT=30s

## Database

PostgreSQL 14 with supply chain schema (15 tables, ~130K rows):
- Connection: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
- Key tables: suppliers, supplier_relationships, parts, bill_of_materials, facilities, transport_routes

## MCP Integration

Always use Context7 MCP tools (`resolve-library-id` → `get-library-docs`) when generating code, configuration, or needing library documentation.

## Project Management

- Update `CHANGELOG.md` and `pyproject.toml` with semantic versioning on every commit
- Run integration tests for each phase (prefer integration over unit tests)
- Documentation lives in `docs/` - update when adding features
- Update `CLAUDE.md` if needed
