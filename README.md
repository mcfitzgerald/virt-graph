# VG/SQL: Virtual Graph over SQL

## What is VG/SQL?

**The problem**: Enterprise data lives in relational SQL databases. Graph databases offer powerful query patterns (traversals, pathfinding, centrality), but migrating data is cumbersome and often impractical.

**The solution**: VG/SQL ("VeeJee over Sequel") enables graph-like queries over relational data WITHOUT migration. It combines:

1. An **ontology** expressed in [LinkML](https://linkml.io) forma that maps graph concepts to relational structures and translates 1:1 to an annotated Tbox/Rbox ontological structure.
2. **Lightweight Python handlers** for recursive traversal and graph algorithms filling in gaps in native SQL for graph operations.
3. **Overall orchestration and on-the-fly query generation** via general-purpose agentic systems (in this case Claude Code)

This work extends the previously introduced [virtual-ontology](https://github.com/mcfitzgerald/virtual-ontology) concept by adopting LinkML for standardized, validatable ontology definitions and adding handlers for full graph operations.

**Proof of concept**: We share a toy example from supply chain domain to demonstrate the approach; the pattern generalizes to any relational schema

## Quick Start

**FIRST:Launch Claude Code session**

```bash
make install          # Install Python dependencies
make db-up            # Start PostgreSQL
make neo4j-up         # Start Neo4j (for benchmarking)
```

## Database Setup

While the general use case is on realtional SQL data, we compare two databases: **PostgreSQL** for relational data and **Neo4j** for validation/benchmarking

### Prerequisites

- Docker and Docker Compose installed
- Poetry installed (`pip install poetry`)
- Python dependencies: `make install`

### Starting the Databases

```bash
# Start PostgreSQL
make db-up

# Start Neo4j
make neo4j-up
```

### Checking Database Health

```bash
# Check running containers
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(postgres|neo4j)"
```

Expected output shows both as "healthy":
```
virt-graph-neo4j      Up X minutes (healthy)
postgres-postgres-1   Up X minutes (healthy)
```

### Stopping the Databases

```bash
# Stop PostgreSQL
make db-down

# Stop Neo4j
make neo4j-down
```

### Resetting PostgreSQL

To wipe and recreate the PostgreSQL database (re-runs schema and seed scripts):

```bash
make db-reset
```

### Viewing Logs

```bash
# PostgreSQL logs
make db-logs

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

| Database   | Host      | Port | User        | Password     | Database/DB   |
|------------|-----------|------|-------------|--------------|---------------|
| PostgreSQL | localhost | 5432 | virt_graph  | dev_password | supply_chain  |
| Neo4j      | localhost | 7687 | neo4j       | dev_password | neo4j         |

Neo4j also exposes a browser UI at http://localhost:7474

### Python Access

**Note:** Use psycopg2 for database access. The `psql` CLI may not be installed in all environments.

#### PostgreSQL

```python
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='supply_chain',
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
| Example Ontology | `supply_chain_example/ontology/supply_chain.yaml` | Supply chain domain ontology |
| Handlers | `src/virt_graph/handlers/` | Graph operations (traversal, pathfinding, network) |
| Example | `supply_chain_example/` | Complete supply chain use case with tests |

### Metamodel Features (v2.0)

The metamodel supports advanced patterns:

| Feature | Annotation | Description |
|---------|------------|-------------|
| Composite Keys | `vg:primary_key: '["col1", "col2"]'` | Multi-column primary/foreign keys |
| AI Context | `vg:context` | Structured hints for query generation |
| Edge Filtering | `vg:sql_filter` | SQL WHERE clause for edge tables |
| Edge Properties | `vg:edge_attributes` | Property Graph style edge data |
| Polymorphism | `vg:type_discriminator` | Multi-class domain/range support |

### Operation Types

The ontology classifies relationships by what operations they support:

| Category | Handlers | Use Case |
|----------|----------|----------|
| **Direct** | SQL joins | Simple lookups, aggregations |
| **Traversal** | `traverse()` | Recursive paths (supplier networks, hierarchies) |
| **Aggregation** | `path_aggregate()` | Value aggregation along paths (e.g., BOM explosion) |
| **Algorithm** | `shortest_path()`, `centrality()` | Weighted pathfinding, graph algorithms |


# Supply Chain Use Case

### Data Overview

**PostgreSQL** contains 16 relational tables:
`audit_log`, `bill_of_materials`, `customers`, `facilities`, `inventory`, `order_items`, `orders`, `part_suppliers`, `parts`, `product_components`, `products`, `shipments`, `supplier_certifications`, `supplier_relationships`, `suppliers`, `transport_routes`

**Neo4j** contains graph nodes:
| Node Type | Count |
|-----------|-------|
| Order | 20,000 |
| Inventory | 10,032 |
| Shipment | 7,995 |
| Part | 5,008 |
| Customer | 1,000 |
| Certification | 707 |
| Supplier | 500 |
| Product | 200 |
| Facility | 50 |


### Example Queries

These are real queries generated by Claude Code during benchmarking. See `supply_chain_example/questions.md` for the 60 benchmark questions.

**Direct SQL** (Q05: Which suppliers have ISO9001 certification?)
```sql
SELECT DISTINCT s.supplier_code, s.name, sc.certification_number
FROM suppliers s
JOIN supplier_certifications sc ON s.id = sc.supplier_id
WHERE sc.certification_type = 'ISO9001' AND sc.is_valid = true;
```

**Recursive Traversal** (Q12: Find all upstream suppliers of 'Acme Corp')
```python
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",  # Who sells TO Acme
    max_depth=10,
    include_start=False,
)
# Result: 33 upstream suppliers (7 tier 2, 26 tier 3)
```

**Path Aggregation - BOM Explosion** (Q19: Full BOM for 'Turbo Encabulator')
```python
result = path_aggregate(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="parent_part_id",
    edge_to_col="child_part_id",
    start_id=part_id,
    value_col="quantity",
    operation="multiply",  # Propagate quantities through hierarchy
    max_depth=20,
)
# Result: 1,024 unique parts with aggregated quantities
```

**Shortest Path** (Q29: Shortest route from Chicago to LA)
```python
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="distance_km",
)
# Result: 3,388.3 km, 3 hops
```

**Centrality** (Q36: Which facility is most central?)
```python
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10,
)
# Result: New York Factory (score=0.2327)
```

### Workflow (with Claude Code)

1. **Read the ontology** (e.g., `supply_chain_example/ontology/supply_chain.yaml`) to understand available entities and relationships
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
- **[Supply Chain Tutorial](docs/examples/supply-chain.md)** - Complete worked example

## Research Validation

*Validation methodology (benchmark results to be updated):*

- 60 benchmark questions across different operation categories
- GOLD questions test cross-domain polymorphism (BOM + Supplier + Logistics traversals)
- Same ontology defines BOTH VG/SQL handlers AND Neo4j schema
- Both systems queried with on-the-fly generated queries
- Supply chain domain proves the concept; approach generalizes

See `benchmark_comparison.md` for detailed results.
