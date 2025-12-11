# VG/SQL: Virtual Graph over SQL

## What is VG/SQL?

**The problem**: Enterprise data lives in relational SQL databases. Graph databases offer powerful query patterns (traversals, pathfinding, centrality), but migrating data is cumbersome and often impractical.

**The solution**: VG/SQL ("VeeJee over Sequel") enables graph-like queries over relational data WITHOUT migration. It combines:

1. A **LinkML ontology** that maps graph concepts to relational structures
2. **Lightweight Python handlers** for recursive traversal and graph algorithms
3. **On-the-fly query generation** via a general-purpose agentic system like Claude Code

This work extends [virtual-ontology](https://github.com/mcfitzgerald/virtual-ontology) by adopting LinkML for standardized, validatable ontology definitions and adding handlers for full graph operations.

**Proof of concept**: The supply chain domain demonstrates the approach; the pattern generalizes to any relational schema with graph-like relationships.

## Quick Start

```bash
make install          # Install Python dependencies
make db-up            # Start PostgreSQL
make neo4j-up         # Start Neo4j (for benchmarking)
```

## Reference Documentation

| Document | Description |
|----------|-------------|
| `question_inventory.md` | 50 benchmark questions |
| `queries.md` | VG/SQL query catalogue with results |
| `benchmark_comparison.md` | VG/SQL vs Neo4j comparison |
| `ontology/supply_chain.yaml` | LinkML ontology definition |

## Database Setup

VG/SQL uses two databases: **PostgreSQL** for relational data and **Neo4j** for validation/benchmarking.

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

### Database Credentials

| Database   | Host      | Port | User        | Password     | Database/DB   |
|------------|-----------|------|-------------|--------------|---------------|
| PostgreSQL | localhost | 5432 | virt_graph  | dev_password | supply_chain  |
| Neo4j      | localhost | 7687 | neo4j       | dev_password | neo4j         |

Neo4j also exposes a browser UI at http://localhost:7474

### Python Access

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

## How VG/SQL Works

VG/SQL enables graph-like queries over relational data through three components:

### The Handlers (Key Contribution)

Lightweight, generic Python tools that enable full graph operations over SQL—a small price to pay for graph capabilities without migration:

| Handler | Complexity | Description |
|---------|------------|-------------|
| `traverse()` | YELLOW | BFS/DFS with direction control |
| `bom_explode()` | YELLOW | Bill of materials explosion with quantities |
| `shortest_path()` | RED | Dijkstra weighted shortest path |
| `all_shortest_paths()` | RED | All shortest paths between nodes |
| `centrality()` | RED | Betweenness/closeness/degree centrality |
| `connected_components()` | RED | Find connected subgraphs |
| `neighbors()` | RED | Direct neighbors of a node |
| `resilience_analysis()` | RED | Impact analysis of node removal |

These handlers are easily extended or new ones created for domain-specific graph operations.

### Key Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| Ontology | `ontology/supply_chain.yaml` | Defines entities, relationships, and complexity levels |
| Handlers | `src/virt_graph/handlers/` | Graph operations (traversal, pathfinding, network) |

### Complexity Classification

The ontology classifies relationships by query strategy:

| Complexity | Strategy | Use Case |
|------------|----------|----------|
| **GREEN** | Direct SQL | Simple joins, aggregations |
| **YELLOW** | `traverse()`, `bom_explode()` | Recursive paths (supplier network, BOM) |
| **RED** | `shortest_path()`, `centrality()` | Weighted pathfinding, graph algorithms |

### Example Queries

These are real queries generated by Claude Code during benchmarking. See `question_inventory.md` for all 50 benchmark questions and `queries.md` for the complete query catalogue.

**GREEN - Direct SQL** (Q05: Which suppliers have ISO9001 certification?)
```sql
SELECT DISTINCT s.supplier_code, s.name, sc.certification_number
FROM suppliers s
JOIN supplier_certifications sc ON s.id = sc.supplier_id
WHERE sc.certification_type = 'ISO9001' AND sc.is_valid = true;
```

**YELLOW - Recursive Traversal** (Q12: Find all upstream suppliers of 'Acme Corp')
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

**YELLOW - BOM Explosion** (Q19: Full BOM for 'Turbo Encabulator')
```python
result = bom_explode(
    conn,
    start_part_id=part_id,
    max_depth=20,
    include_quantities=True,
)
# Result: 1,024 unique parts
```

**RED - Shortest Path** (Q29: Shortest route from Chicago to LA)
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

**RED - Centrality** (Q36: Which facility is most central?)
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

1. **Read the ontology** (`ontology/supply_chain.yaml`) to understand available entities and relationships
2. **Dispatch** the question: determine if a handler is needed based on complexity (GREEN/YELLOW/RED)
3. **Generate query on-the-fly**: Direct SQL for GREEN, handler call for YELLOW/RED
4. **Execute and return results**

All queries are generated on-the-fly by the agentic system—no hardcoded templates.

## Designed for Agentic Systems

VG/SQL is built for a new paradigm: **tools running in a loop** ([Willison, 2025](https://simonwillison.net/2025/Sep/18/agents/)). General-purpose agentic systems like **Claude Code** provide a complete environment—file access, code execution, web search, reasoning—with batteries included.

VG/SQL leverages these native capabilities:
- **Ontology discovery**: Introspect database schema, generate LinkML ontology
- **Dispatch**: Natural language question → determine if handler is needed
- **Query generation**: On-the-fly SQL or handler calls (not templates)

The ontology + handlers are the contribution; Claude Code is the enabler.

## Research Validation

*Validation methodology (benchmark results to be updated):*

- 50 benchmark questions generated by Claude
- Same ontology defines BOTH VG/SQL handlers AND Neo4j schema
- Both systems queried with on-the-fly generated queries
- Supply chain domain proves the concept; approach generalizes

See `benchmark_comparison.md` for detailed results.
