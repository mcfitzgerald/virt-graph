# Virtual Graph

Graph-like queries over relational data using LLM reasoning.

## Research Question

> Can an LLM agent system (Claude Code) equipped with an ontology and tooling for complex queries (DAGs, recursion, etc.) on top of a relational database perform effectively versus implementing a graph database?

For enterprises with existing SQL infrastructure, Virtual Graph delivers **92% of graph query accuracy** at a fraction of the migration cost.

## How It Works

Virtual Graph routes queries through three paths based on complexity:

| Route | Description | Example | Handler |
|-------|-------------|---------|---------|
| GREEN | Simple lookups/joins | "Find supplier ABC Corp" | Direct SQL |
| YELLOW | Recursive traversal | "All tier 3 suppliers for Acme" | `traverse()` |
| RED | Network algorithms | "Cheapest route from A to B" | NetworkX |

An ontology maps business concepts to SQL tables. Handlers generate efficient queries. No graph database required.

## Quick Start

```bash
# Install dependencies
poetry install

# Start PostgreSQL
make db-up

# Run tests
make test

# Serve documentation
make serve-docs
```

## Project Structure

```
virt-graph/
  src/virt_graph/
    handlers/           # GREEN/YELLOW/RED handlers
    estimator/          # Graph size estimation
    ontology.py         # OntologyAccessor API
  ontology/
    supply_chain.yaml   # Domain ontology (LinkML)
  prompts/              # Claude Code session starters
  benchmark/            # VG vs Neo4j comparison
  docs/                 # MkDocs documentation
```

## Key Features

- **No Migration Required**: Query existing PostgreSQL data as a graph
- **Safety Limits**: Built-in guards prevent runaway queries (MAX_NODES=10,000)
- **Frontier Batching**: Efficient traversal with one query per depth level
- **26x Faster**: No network hop to a separate database

## Benchmark Results

Virtual Graph achieves **92% accuracy** compared to Neo4j baseline:

| Route | Accuracy | Avg Latency | Target |
|-------|----------|-------------|--------|
| GREEN | 88.9% | 2ms | 100% |
| YELLOW | 100%* | 2ms | 90% |
| RED | 85.7% | 1ms | 80% |
| **Overall** | **92%** | **2ms** | 85% |

*YELLOW includes queries that correctly triggered safety limits.

## TCO Comparison

| Scenario | Virtual Graph | Neo4j | Savings |
|----------|--------------|-------|---------|
| Tech Startup | $15,200 | $67,600 | 77% |
| Enterprise | $145,800 | $306,600 | 52% |

## Documentation

- [Getting Started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Ontology Guide](docs/ontology-guide.md)
- [Benchmark Report](docs/benchmark-report.md)

## Development

```bash
make test-gate1         # Database and core handlers
make test-gate2         # Ontology and traversal
make validate-ontology  # Two-layer validation
make benchmark          # Run full benchmark
```

## Version

Current version: **0.9.0** (Lean Academic Publication)

## License

MIT
