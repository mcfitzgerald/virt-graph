# Benchmarks

This guide explains how to run the benchmark suite comparing Virtual Graph against Neo4j.

## Prerequisites

- PostgreSQL running with supply chain data (see [Setup](setup.md))
- Docker for Neo4j container
- All tests passing (`make test`)

## Quick Start

```bash
# Start Neo4j
make neo4j-up

# Wait for Neo4j to be ready (check logs)
make neo4j-logs

# Migrate data to Neo4j
poetry run python neo4j/migrate.py

# Generate ground truth
poetry run python benchmark/generate_ground_truth.py

# Run benchmarks
poetry run python benchmark/run.py --system both

# View results
cat benchmark/results/summary.json
```

## Step-by-Step Guide

### 1. Start Neo4j

```bash
make neo4j-up
# Or: docker-compose -f neo4j/docker-compose.yml up -d
```

Neo4j starts with:

| Setting | Value |
|---------|-------|
| HTTP | `http://localhost:7474` |
| Bolt | `bolt://localhost:7687` |
| User | `neo4j` |
| Password | `password` |

Wait for Neo4j to be ready:

```bash
# Watch logs until you see "Started"
make neo4j-logs
```

### 2. Migrate Data

The migration script reads from `ontology/supply_chain.yaml` and creates:
- Node labels matching entity classes
- Relationships matching relationship classes
- Properties from SQL columns

```bash
poetry run python neo4j/migrate.py
```

Expected output:
```
Migrating data to Neo4j...
  Creating nodes: 35,469
  Creating relationships: 147,670
Migration complete in 57.3 seconds
```

### 3. Generate Ground Truth

Ground truth queries run directly against PostgreSQL and Neo4j to establish expected results:

```bash
poetry run python benchmark/generate_ground_truth.py
```

This creates `benchmark/ground_truth/` with expected results for each query.

### 4. Run Benchmarks

Run the full benchmark suite:

```bash
# Both systems
poetry run python benchmark/run.py --system both

# Virtual Graph only
poetry run python benchmark/run.py --system vg

# Neo4j only
poetry run python benchmark/run.py --system neo4j
```

Results are saved to `benchmark/results/`.

### 5. View Results

```bash
# Summary
cat benchmark/results/summary.json

# Detailed results
cat benchmark/results/detailed.json
```

## Benchmark Queries

The benchmark includes 25 queries across three routes:

### GREEN Queries (1-9)

| # | Query | Handler |
|---|-------|---------|
| 1 | Find supplier by name | SQL |
| 2 | List tier 1 suppliers | SQL |
| 3 | Parts with 'sensor' | SQL |
| 4 | Parts from supplier | SQL JOIN |
| 5 | Facilities by state | SQL |
| 6 | Supplier certifications | SQL JOIN |
| 7 | Products with part | SQL JOIN |
| 8 | Orders from facility | SQL JOIN |
| 9 | Alternate suppliers | SQL JOIN |

### YELLOW Queries (10-18)

| # | Query | Handler |
|---|-------|---------|
| 10 | Tier 3 suppliers | traverse_collecting |
| 11 | Upstream suppliers | traverse |
| 12 | Downstream customers | traverse |
| 13 | BOM explosion | bom_explode |
| 14 | Where used | traverse |
| 15 | Supplier impact | traverse |
| 16 | Supply chain depth | traverse |
| 17 | BOM leaf parts | traverse |
| 18 | Common suppliers | traverse |

### RED Queries (19-25)

| # | Query | Handler |
|---|-------|---------|
| 19 | Cheapest route | shortest_path |
| 20 | Fastest route | shortest_path |
| 21 | Shortest distance | shortest_path |
| 22 | Critical facility | centrality |
| 23 | Most connected supplier | centrality |
| 24 | Isolated facilities | connected_components |
| 25 | All routes | all_shortest_paths |

## Understanding Results

### Accuracy Metrics

```json
{
  "overall_accuracy": 0.92,
  "first_attempt_accuracy": 0.92,
  "route_accuracy": {
    "GREEN": 0.889,
    "YELLOW": 1.0,
    "RED": 0.857
  }
}
```

- **Overall accuracy**: Fraction of queries returning correct results
- **First-attempt**: No retries needed
- **Route accuracy**: Breakdown by complexity

### Latency Metrics

```json
{
  "avg_latency_ms": 2,
  "p95_latency_ms": 5,
  "by_route": {
    "GREEN": {"avg": 2, "p95": 5},
    "YELLOW": {"avg": 2, "p95": 3},
    "RED": {"avg": 1, "p95": 2}
  }
}
```

### Safety Limit Triggers

YELLOW queries may hit safety limits:

```json
{
  "safety_triggers": {
    "query_13_bom_explosion": {
      "estimated_nodes": 65629,
      "limit": 10000,
      "action": "blocked"
    }
  }
}
```

These are **correct** behaviors - the system identifies potentially dangerous queries before execution.

## Interpreting Comparisons

### Virtual Graph vs Neo4j

| Metric | Virtual Graph | Neo4j |
|--------|---------------|-------|
| Accuracy | 92% | 36%* |
| Avg Latency | 2ms | 53ms |
| P95 Latency | 5ms | 136ms |

*Neo4j accuracy appears low due to comparison methodology - results are correct but formatted differently.

### Why Virtual Graph is Faster

1. **No network hop** - Data stays in PostgreSQL
2. **Query optimization** - PostgreSQL optimizer handles simple queries
3. **Frontier batching** - One query per depth level, not per node

### Trade-offs

| Aspect | Virtual Graph | Neo4j |
|--------|---------------|-------|
| Setup | Uses existing DB | Requires new DB |
| Data freshness | Real-time | Requires sync |
| Simple queries | Excellent | Good |
| Complex patterns | Basic | Native Cypher |
| Safety limits | Built-in | Manual |

## Archiving Results

Before running a fresh benchmark:

```bash
./scripts/archive_benchmark.sh
```

This moves current results to `benchmark/archive/` with a timestamp.

## Troubleshooting

### Neo4j Won't Start

```bash
# Check logs
docker-compose -f neo4j/docker-compose.yml logs

# Reset Neo4j
docker-compose -f neo4j/docker-compose.yml down -v
docker-compose -f neo4j/docker-compose.yml up -d
```

### Migration Fails

Ensure Neo4j is ready:

```bash
# Check Neo4j browser
open http://localhost:7474

# Or check bolt connection
docker exec neo4j cypher-shell -u neo4j -p password "RETURN 1"
```

### Benchmark Times Out

Increase timeout or run subsets:

```bash
# Run only GREEN queries
poetry run python benchmark/run.py --queries 1-9

# Run only YELLOW queries
poetry run python benchmark/run.py --queries 10-18
```

## Key Findings

From the supply chain benchmark:

1. **Handler approach works** - 92% accuracy on graph-like queries
2. **Safety limits essential** - Large BOMs can expand to 65K nodes
3. **SQL wins for simple queries** - Sub-5ms for GREEN route
4. **Virtual Graph is 26x faster** - No migration or sync overhead

See [Benchmark Results](../../evaluation/benchmark-results.md) for full analysis.
