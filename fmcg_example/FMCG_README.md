# FMCG Example: Prism Consumer Goods

A **Fast-Moving Consumer Goods (FMCG)** supply chain example for the Virtual Graph project, demonstrating high-velocity, massive-volume patterns inspired by Colgate-Palmolive.

## Quick Start

```bash
# Start PostgreSQL (port 5433)
docker-compose -f fmcg_example/postgres/docker-compose.yml up -d

# Generate and load data (after schema is implemented)
# poetry run python fmcg_example/scripts/generate_data.py

# Run tests
poetry run pytest fmcg_example/tests/ -v

# Start Neo4j for benchmarking (port 7475/7688)
docker-compose -f fmcg_example/neo4j/docker-compose.yml up -d
```

## Directory Structure

```
fmcg_example/
├── ontology/
│   └── prism_fmcg.yaml          # LinkML ontology with VG extensions
├── postgres/
│   ├── docker-compose.yml       # PostgreSQL container (port 5433)
│   ├── schema.sql               # ~60 tables DDL
│   └── seed.sql                 # Generated data (~4M rows)
├── neo4j/
│   ├── docker-compose.yml       # Neo4j container (port 7475/7688)
│   └── migrate.py               # Ontology-driven migration
├── scripts/
│   ├── generate_data.py         # Data generator
│   └── validate_realism.sql     # Validation queries
├── tests/
│   ├── test_recall_trace.py     # Beast mode: lot genealogy
│   ├── test_landed_cost.py      # Beast mode: cost rollup
│   ├── test_spof_risk.py        # Beast mode: supplier criticality
│   ├── test_osa_analysis.py     # Beast mode: OSA/DC bottlenecks
│   └── test_ontology.py         # Two-layer validation
├── docs/
│   └── prism-fmcg.md            # Domain documentation
└── FMCG_README.md               # This file
```

## Key Differences from supply_chain_example

| Aspect | supply_chain_example | fmcg_example |
|--------|---------------------|--------------|
| Domain | Aerospace/Industrial | Consumer Goods |
| Graph Shape | Deep (25+ level BOM) | Wide (1 → 50,000 fan-out) |
| Stress Test | Recursive traversal depth | Horizontal explosion width |
| Target Metric | BOM cost rollup | Recall trace speed |
| SCOR Coverage | Partial | Full (all 7 domains) |

## Beast Mode Queries

| Query | Target | Handler |
|-------|--------|---------|
| **Recall Trace** | 1 batch → 47,500 orders in <5s | `traverse()` |
| **Landed Cost** | Full path aggregation in <2s | `path_aggregate()` |
| **SPOF Detection** | Find single-source ingredients in <1s | `resilience_analysis()` |
| **OSA Root Cause** | Correlate low-OSA with DC bottlenecks in <3s | `centrality()` |

## Connection Settings

| Service | Host | Port | Database | User | Password |
|---------|------|------|----------|------|----------|
| PostgreSQL | localhost | **5433** | prism_fmcg | virt_graph | dev_password |
| Neo4j HTTP | localhost | **7475** | - | neo4j | dev_password |
| Neo4j Bolt | localhost | **7688** | - | neo4j | dev_password |

*Note: Ports differ from supply_chain_example (5432/7474/7687) to allow both to run simultaneously.*

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Directory Structure | ✅ Complete |
| 2 | Schema (67 tables + 8 views) | ✅ Complete |
| 3 | Ontology (LinkML + VG) | 📋 TODO |
| 4 | Data Generator (~4M rows) | 📋 TODO |
| 5 | Beast Mode Tests | 📋 TODO |
| 6 | Neo4j Comparison | 📋 TODO |

## Specification

Full specification: [`magical-launching-forest.md`](../magical-launching-forest.md)

## Domain Documentation

See [`docs/prism-fmcg.md`](docs/prism-fmcg.md) for:
- Company profile (Prism Consumer Goods)
- Global structure (5 divisions, 7 plants)
- SCOR-DS domain model
- Named entities for testing
- FMCG benchmarks
