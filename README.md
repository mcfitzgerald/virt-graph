# Virtual Graph

Graph-like queries over relational data using LLM reasoning.

## Status

This branch (`feature/interactive-discovery-v2`) is a fresh start for interactive ontology discovery.

## Quick Start

```bash
# Ensure PostgreSQL is running
docker-compose -f postgres/docker-compose.yml up -d

# Install dependencies
poetry install

# Run tests
poetry run pytest
```

## Project Structure

- `postgres/` - PostgreSQL schema and seed data (source of truth)
- `src/virt_graph/handlers/` - Core traversal and algorithm handlers
- `patterns/templates/` - Reusable query pattern templates
- `.claude/skills/` - Claude Code skills for schema introspection
- `ontology/` - Discovered ontology (TBD via interactive session)

## Next Steps

1. Run ontology discovery session
2. Validate with gate tests
3. Pattern exploration
4. Neo4j migration and benchmark
