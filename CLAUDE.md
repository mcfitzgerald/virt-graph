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

# Start database (once infrastructure exists)
docker-compose up -d
```

## Project Overview

Virtual Graph enables graph-like queries over enterprise relational data without migrating to a graph database. The system uses an LLM to reason over SQL using a discovered ontology and learned SQL patterns.

## Architecture

The system routes queries through three paths based on complexity:

- **GREEN**: Simple SQL - direct lookups/joins, no handlers needed
- **YELLOW**: Recursive traversal - uses `traverse()` handler with frontier-batched BFS
- **RED**: Network algorithms - uses NetworkX handlers for pathfinding/centrality

Key components (to be implemented in `src/virt_graph/`):
- `handlers/base.py` - Safety limits (MAX_DEPTH=50, MAX_NODES=10K), frontier batching utilities
- `handlers/traversal.py` - Generic BFS traversal, schema-parameterized
- `handlers/pathfinding.py` - Dijkstra shortest path via NetworkX
- `handlers/network.py` - Centrality, connected components

## Critical Implementation Rules

- **Frontier batching mandatory**: One SQL query per depth level, never per node
- **Size guards**: Check before NetworkX load; >5K nodes must warn or fail
- **Hybrid SQL/Python**: Python orchestrates traversal, SQL filters; never bulk load entire tables
- **Safety limits are non-negotiable**: MAX_DEPTH=50, MAX_NODES=10,000, MAX_RESULTS=1,000, QUERY_TIMEOUT=30s

## MCP Integration

Always use Context7 MCP tools (`resolve-library-id` → `get-library-docs`) when generating code, configuration, or needing library documentation.

## Project Management

Update `CHANGELOG.md` and `pyproject.toml` with semantic versioning and change details on every commit

Use pytest and run integration tests (don't get crazy with unit tests) to make sure things are workin. Write and run tests for each phase.
