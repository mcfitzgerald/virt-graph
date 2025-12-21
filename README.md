# VG/SQL: Virtual Graph over SQL

## What is VG/SQL?

**The problem**: Enterprise data lives in relational SQL databases. Graph databases offer powerful query patterns (traversals, pathfinding, centrality), but migrating data is cumbersome and often impractical.

**The solution**: VG/SQL ("VeeJee over Sequel") enables graph-like queries over relational data WITHOUT migration. It combines:

1. An **ontology** expressed in [LinkML](https://linkml.io) forma that maps graph concepts to relational structures and translates 1:1 to an annotated Tbox/Rbox ontological structure.
2. **Lightweight Python handlers** for recursive traversal and graph algorithms filling in gaps in native SQL for graph operations.
3. **Overall orchestration and on-the-fly query generation** via general-purpose agentic systems (in this case Claude Code)

This work extends the previously introduced [virtual-ontology](https://github.com/mcfitzgerald/virtual-ontology) concept by adopting LinkML for standardized, validatable ontology definitions and adding handlers for full graph operations.

**Proof of concept**: We share an FMCG (Fast-Moving Consumer Goods) supply chain example to demonstrate the approach; the pattern generalizes to any relational schema

## Quick Start

```bash
make install          # Install Python dependencies
make fmcg-db-up       # Start FMCG PostgreSQL (port 5433)
make neo4j-up         # Start Neo4j (optional, for benchmarking)
```

## Database Setup

While the general use case is on realtional SQL data, we compare two databases: **PostgreSQL** for relational data and **Neo4j** for validation/benchmarking

### Prerequisites

- Docker and Docker Compose installed
- Poetry installed (`pip install poetry`)
- Python dependencies: `make install`

### Starting the Databases

```bash
# Start FMCG PostgreSQL (port 5433)
make fmcg-db-up

# Start Neo4j (optional, for benchmarking)
make neo4j-up
```

### Checking Database Health

```bash
# Check running containers
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(fmcg|neo4j)"
```

Expected output shows containers as "healthy":
```
virt-graph-neo4j      Up X minutes (healthy)
fmcg-postgres-1       Up X minutes (healthy)
```

### Stopping the Databases

```bash
# Stop FMCG PostgreSQL
make fmcg-db-down

# Stop Neo4j
make neo4j-down
```

### Resetting FMCG Database

To wipe and recreate the FMCG database (re-runs schema and seed scripts):

```bash
make fmcg-db-reset
```

### Viewing Logs

```bash
# FMCG PostgreSQL logs
make fmcg-db-logs

# Neo4j logs
make neo4j-logs
```

### Neo4j Troubleshooting

If Neo4j fails to start with errors like `Neo4j is already running (pid:X)`, this indicates a stale PID file from an unclean shutdown. Use the cycle command to fully reset:

```bash
# Full cycle: stop, wipe volumes, restart (fixes PID issues)
make neo4j-cycle
```

This performs a clean stop, removes all volumes (including stale PID files), and restarts. Wait ~20 seconds after restart for Neo4j to fully initialize before connecting.

For a clean shutdown without wiping data:
```bash
make neo4j-stop
```

### Database Credentials

| Database        | Host      | Port | User        | Password     | Database      |
|-----------------|-----------|------|-------------|--------------|---------------|
| FMCG PostgreSQL | localhost | 5433 | virt_graph  | dev_password | prism_fmcg    |
| Neo4j           | localhost | 7687 | neo4j       | dev_password | neo4j         |

Neo4j also exposes a browser UI at http://localhost:7474

### Python Access

**Note:** Use psycopg2 for database access. The `psql` CLI may not be installed in all environments.

#### PostgreSQL

```python
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5433,
    database='prism_fmcg',
    user='virt_graph',
    password='dev_password'
)
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
for row in cur.fetchall():
    print(row[0])
conn.close()
```

#### Neo4j

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'dev_password'))
with driver.session() as session:
    result = session.run('MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count')
    for record in result:
        print(f"{record['label']}: {record['count']}")
driver.close()
```

## How VG/SQL Works

VG/SQL enables graph-like queries over relational data through three components:

### The Handlers (Key Contribution)

Lightweight, generic Python tools that enable full graph operations over SQL—a small price to pay for graph capabilities without migration:

| Handler | Category | Description |
|---------|----------|-------------|
| `traverse()` | Traversal | BFS/DFS with direction control |
| `path_aggregate()` | Aggregation | Aggregate values along paths (SUM/MAX/MIN/multiply) |
| `shortest_path()` | Algorithm | Dijkstra weighted shortest path |
| `all_shortest_paths()` | Algorithm | All shortest paths between nodes |
| `centrality()` | Algorithm | Betweenness/closeness/degree centrality |
| `connected_components()` | Algorithm | Find connected subgraphs |
| `neighbors()` | Algorithm | Direct neighbors of a node |
| `resilience_analysis()` | Algorithm | Impact analysis of node removal |

These handlers are easily extended or new ones created for domain-specific graph operations.

### Key Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| Metamodel | `virt_graph.yaml` | VG extensions (single source of truth for validation rules) |
| FMCG Ontology | `fmcg_example/ontology/prism_fmcg.yaml` | FMCG domain ontology (71 classes, ~50 relationships) |
| Handlers | `src/virt_graph/handlers/` | Graph operations (traversal, pathfinding, network) |
| FMCG Example | `fmcg_example/` | Complete FMCG use case with tests and data generation |
| Data Generation | `fmcg_example/scripts/data_generation/` | Modular generators with chaos injection |

### Metamodel Features (v2.1)

The metamodel supports advanced patterns:

| Feature | Annotation | Description |
|---------|------------|-------------|
| Composite Keys | `vg:primary_key: '["col1", "col2"]'` | Multi-column primary/foreign keys |
| AI Context | `vg:context` | Structured hints with definition, business_logic, data_quality_notes |
| Edge Filtering | `vg:sql_filter` | SQL WHERE clause for edge tables |
| Edge Properties | `vg:edge_attributes` | Property Graph style edge data |
| Polymorphism | `vg:type_discriminator` | Native YAML format for multi-class domain/range |

### Operation Types

The ontology classifies relationships by what operations they support:

| Category | Handlers | Use Case |
|----------|----------|----------|
| **Direct** | SQL joins | Simple lookups, aggregations |
| **Traversal** | `traverse()` | Recursive paths (supplier networks, hierarchies) |
| **Aggregation** | `path_aggregate()` | Value aggregation along paths (e.g., BOM explosion) |
| **Algorithm** | `shortest_path()`, `centrality()` | Weighted pathfinding, graph algorithms |


# FMCG Use Case: Prism Consumer Goods

### Data Overview

**PostgreSQL** contains 70 tables + 8 views (~11.4M rows total) organized by SCOR-DS domains:

| Domain | Tables | Description |
|--------|--------|-------------|
| **SOURCE** | 8 | Ingredients, suppliers, certifications, purchase orders, goods receipts |
| **TRANSFORM** | 9 | Plants, production lines, formulas, work orders, batches |
| **PRODUCT** | 5 | Products, packaging, SKUs (~2,000), substitutes |
| **ORDER** | 7 | Channels, promotions, orders (~200K), order lines (~3.2M) |
| **FULFILL** | 11 | Divisions, DCs, retail locations (~10K), shipments, inventory |
| **LOGISTICS** | 7 | Carriers, contracts, routes, shipment legs |
| **ESG** | 5 | Emission factors, sustainability targets, supplier ESG scores |
| **PLAN** | 9 | POS sales (~500K), demand forecasts, supply plans |
| **RETURN** | 4 | RMA authorizations, returns, disposition logs |
| **ORCHESTRATE** | 6 | KPI thresholds/actuals, OSA metrics, risk events, audit log |

**Key Scale Points**:
- ~11.4M rows across 70 tables
- ~3.2M order lines (vectorized generation)
- ~1M shipment lines
- ~500K POS sales with multi-promo effects
- ~10K retail locations with hub concentration (MegaMart = 25% of orders)

### Named Test Entities

Deterministic fixtures for reproducible benchmarking:

| Entity ID | Description | Tests |
|-----------|-------------|-------|
| `B-2024-RECALL-001` | Contaminated batch | Recall trace (1 batch → 47K orders) |
| `ACCT-MEGA-001` | MegaMart hub (4,500 stores) | Hub concentration, 25% of orders |
| `SUP-PALM-MY-001` | Single-source Palm Oil supplier | SPOF detection, resilience analysis |
| `DC-NAM-CHI-001` | Chicago DC (40% NAM volume) | Bottleneck analysis, centrality |
| `PROMO-BF-2024` | Black Friday promotion | Bullwhip effect, promo lift |
| `LANE-SH-LA-001` | Seasonal Shanghai→LA lane | Temporal route queries |


### Data Generation

The FMCG example includes a modular data generation system (`fmcg_example/scripts/data_generation/`) that produces realistic supply chain data:

```bash
# Generate seed data (~11.4M rows in ~2-3 minutes)
poetry run python fmcg_example/scripts/generate_data.py
```

**Architecture** (v0.9.40):
- **15 Level Generators** (Level 0-14): Each level generates tables with proper FK dependencies
- **Vectorized Generation**: NumPy-based generators for high-volume tables (85K rows/sec)
- **Streaming Writer**: Memory-efficient PostgreSQL COPY output with 10MB buffer

**Chaos Injection** - Realistic supply chain disruptions:

| Component | Description |
|-----------|-------------|
| **RiskEventManager** | 5 risk events (contamination, port strike, cyber outage, SPOF failure, carbon tax) |
| **QuirksManager** | 6 behavioral quirks (bullwhip, phantom inventory, port congestion, optimism bias) |
| **PromoCalendar** | Multi-promo system with 29% penetration, lift effects, hangover periods |

**Validation Suite** - 8 automated checks ensure data realism:
- Pareto distribution (top 20% SKUs = 80% volume)
- Hub concentration (MegaMart = 25% of orders)
- Referential integrity across all 70 tables
- Chaos injection verification

### Workflow (with Claude Code)

1. **Read the ontology** (`fmcg_example/ontology/prism_fmcg.yaml`) to understand available entities and relationships
2. **Dispatch** the question: determine if a handler is needed based on operation types
3. **Generate query on-the-fly**: Direct SQL for simple joins, handler call for traversals/algorithms
4. **Execute and return results**

All queries are generated on-the-fly by the agentic system—no hardcoded templates.

## Designed for Agentic Systems

VG/SQL is built for a new paradigm: **tools running in a loop** ([Willison, 2025](https://simonwillison.net/2025/Sep/18/agents/)). General-purpose agentic systems like **Claude Code** provide a complete environment—file access, code execution, web search, reasoning—with batteries included.

VG/SQL leverages these native capabilities:
- **Ontology discovery**: Introspect database schema, generate LinkML ontology
- **Dispatch**: Natural language question → determine if handler is needed
- **Query generation**: On-the-fly SQL or handler calls (not templates)

The ontology + handlers are the contribution; Claude Code is the enabler.

## Documentation

Serve the full documentation locally:

```bash
poetry run mkdocs serve
```

Documentation covers:
- **[Architecture](docs/concepts/architecture.md)** - System design and dispatch pattern
- **[Operation Types](docs/concepts/ontology.md)** - How operations are classified
- **[Handlers](docs/handlers/overview.md)** - All available graph operations
- **[Creating Ontologies](docs/ontology/creating-ontologies.md)** - 4-round discovery protocol
- **[FMCG Example](fmcg_example/FMCG_README.md)** - Complete domain documentation and usage

## Research Validation

*Validation methodology (benchmark results to be updated):*

- Benchmark questions across different operation categories
- Same ontology defines BOTH VG/SQL handlers AND Neo4j schema
- Both systems queried with on-the-fly generated queries
- FMCG domain proves the concept; approach generalizes to any relational schema

See `benchmark_comparison.md` for detailed results.
