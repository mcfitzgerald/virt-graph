# Benchmark Setup

Complete guide to setting up the benchmark infrastructure, including Neo4j for comparison testing.

## Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    BENCHMARK INFRASTRUCTURE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐         ┌─────────────┐                      │
│   │ PostgreSQL  │         │   Neo4j     │                      │
│   │   (source)  │────────▶│  (compare)  │                      │
│   └─────────────┘  migrate└─────────────┘                      │
│         │                       │                               │
│         │                       │                               │
│         ▼                       ▼                               │
│   ┌─────────────┐         ┌─────────────┐                      │
│   │   Virtual   │         │   Cypher    │                      │
│   │    Graph    │         │  Queries    │                      │
│   └─────────────┘         └─────────────┘                      │
│         │                       │                               │
│         └───────────┬───────────┘                              │
│                     ▼                                           │
│              ┌─────────────┐                                   │
│              │  Benchmark  │                                   │
│              │   Runner    │                                   │
│              └─────────────┘                                   │
│                     │                                           │
│                     ▼                                           │
│              ┌─────────────┐                                   │
│              │   Results   │                                   │
│              │  Comparison │                                   │
│              └─────────────┘                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Docker and Docker Compose
- PostgreSQL running with supply chain data (see [Setup](../examples/supply-chain/setup.md))
- Python 3.12+ with Poetry
- ~4GB RAM available for Neo4j

## PostgreSQL Setup

If not already running:

```bash
# Start PostgreSQL
make db-up

# Verify data
docker exec -it virt-graph-db psql -U virt_graph -d supply_chain \
  -c "SELECT COUNT(*) FROM suppliers;"
```

## Neo4j Setup

### 1. Start Neo4j

```bash
# Using Makefile
make neo4j-up

# Or directly with docker-compose
docker-compose -f neo4j/docker-compose.yml up -d
```

### 2. Wait for Neo4j Ready

Neo4j takes 30-60 seconds to start:

```bash
# Watch logs
make neo4j-logs

# Or check status
docker-compose -f neo4j/docker-compose.yml ps
```

Look for "Started" in the logs:
```
neo4j    | 2024-12-04 10:00:00.000+0000 INFO  Started.
```

### 3. Verify Neo4j

Access Neo4j Browser:
```
URL: http://localhost:7474
User: neo4j
Password: password
```

Or test via command line:
```bash
docker exec virt-graph-neo4j cypher-shell -u neo4j -p password "RETURN 1"
```

### Neo4j Configuration

The docker-compose configuration (`neo4j/docker-compose.yml`):

```yaml
services:
  neo4j:
    image: neo4j:5.15-community
    container_name: virt-graph-neo4j
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_apoc_export_file_enabled=true
      - NEO4J_apoc_import_file_enabled=true
    volumes:
      - neo4j_data:/data
```

| Setting | Value |
|---------|-------|
| HTTP Port | 7474 |
| Bolt Port | 7687 |
| Username | neo4j |
| Password | password |
| Plugins | APOC |

## Data Migration

### 1. Run Migration Script

The migration script reads from the ontology and PostgreSQL:

```bash
poetry run python neo4j/migrate.py
```

### 2. Migration Process

The script:
1. Reads `ontology/supply_chain.yaml` for schema
2. Creates node labels from entity classes
3. Creates relationships from relationship classes
4. Transfers data from PostgreSQL to Neo4j

```
Migrating data to Neo4j...
  Reading ontology: ontology/supply_chain.yaml
  Creating constraints and indexes...
  Migrating nodes:
    Supplier: 500 nodes
    Part: 5,003 nodes
    Product: 200 nodes
    Facility: 50 nodes
    Customer: 1,000 nodes
    Order: 20,000 nodes
    Shipment: 7,995 nodes
    SupplierCertification: 721 nodes
  Total nodes: 35,469

  Migrating relationships:
    SUPPLIES_TO: 817 relationships
    COMPONENT_OF: 14,283 relationships
    CONNECTS_TO: 197 relationships
    CAN_SUPPLY: 7,582 relationships
    ...
  Total relationships: 147,670

Migration complete in 57.3 seconds
```

### 3. Verify Migration

Check node counts in Neo4j:

```bash
docker exec virt-graph-neo4j cypher-shell -u neo4j -p password "
MATCH (n) RETURN labels(n)[0] as label, COUNT(*) as count
ORDER BY count DESC
"
```

Expected output:
```
+----------------------+-------+
| label                | count |
+----------------------+-------+
| "Order"              | 20000 |
| "Shipment"           |  7995 |
| "Part"               |  5003 |
| "Customer"           |  1000 |
| "Supplier"           |   500 |
| "SupplierCert"       |   721 |
| "Product"            |   200 |
| "Facility"           |    50 |
+----------------------+-------+
```

## Ground Truth Generation

Generate expected results for benchmark queries:

```bash
poetry run python benchmark/generate_ground_truth.py
```

This creates `benchmark/ground_truth/` with:
- JSON files for each query's expected results
- Metadata about execution time and result counts

## Running Benchmarks

### Full Benchmark

```bash
# Run both Virtual Graph and Neo4j
poetry run python benchmark/run.py --system both
```

### Partial Benchmarks

```bash
# Virtual Graph only
poetry run python benchmark/run.py --system vg

# Neo4j only
poetry run python benchmark/run.py --system neo4j

# Specific query range
poetry run python benchmark/run.py --queries 10-18

# Single query
poetry run python benchmark/run.py --queries 13
```

### Benchmark Output

Results are saved to `benchmark/results/`:

```
benchmark/results/
├── summary.json          # Overall metrics
├── detailed.json         # Per-query results
├── vg_results.json       # Virtual Graph raw results
├── neo4j_results.json    # Neo4j raw results
└── comparison.json       # Side-by-side comparison
```

## Archiving Results

Before running a fresh benchmark, archive current results:

```bash
./scripts/archive_benchmark.sh
```

This moves results to `benchmark/archive/` with timestamp:

```
benchmark/archive/
├── v2024-12-04_0.7.0/
│   ├── summary.json
│   ├── detailed.json
│   └── ...
└── v2024-12-07_0.8.0/
    └── ...
```

## Troubleshooting

### Neo4j Won't Start

```bash
# Check Docker logs
docker-compose -f neo4j/docker-compose.yml logs

# Common issues:
# - Port 7474 or 7687 already in use
# - Insufficient memory
# - Permission issues with volume

# Reset Neo4j
docker-compose -f neo4j/docker-compose.yml down -v
docker-compose -f neo4j/docker-compose.yml up -d
```

### Migration Fails

```bash
# Ensure Neo4j is ready
docker exec virt-graph-neo4j cypher-shell -u neo4j -p password "RETURN 1"

# Check PostgreSQL connection
docker exec virt-graph-db pg_isready

# Run with verbose output
poetry run python neo4j/migrate.py --verbose
```

### Benchmark Times Out

```bash
# Increase timeout
poetry run python benchmark/run.py --timeout 300

# Skip problematic queries
poetry run python benchmark/run.py --skip 13,14,17
```

### Memory Issues

Neo4j may need more memory for large datasets:

```yaml
# neo4j/docker-compose.yml
environment:
  - NEO4J_dbms_memory_heap_initial__size=512m
  - NEO4J_dbms_memory_heap_max__size=2g
  - NEO4J_dbms_memory_pagecache_size=512m
```

## Clean Up

### Stop Services

```bash
# Stop Neo4j
make neo4j-down

# Stop PostgreSQL
make db-down
```

### Remove Data

```bash
# Remove Neo4j data (keeps PostgreSQL)
docker-compose -f neo4j/docker-compose.yml down -v

# Remove everything
make db-down
docker-compose -f neo4j/docker-compose.yml down -v
```

## Next Steps

After setup:

1. [**Run Benchmarks**](../examples/supply-chain/benchmark.md) - Execute the full suite
2. [**View Results**](benchmark-results.md) - Analyze benchmark findings
