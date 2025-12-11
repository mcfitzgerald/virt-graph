# Quick Start

Get VG/SQL running in 5 minutes.

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Poetry (`pip install poetry`)

## Installation

```bash
# Clone the repository
git clone https://github.com/mcfitzgerald/virt-graph.git
cd virt-graph

# Install dependencies
make install
```

## Start the Database

```bash
# Start PostgreSQL
make db-up

# Verify it's running
docker ps --format "table {{.Names}}\t{{.Status}}" | grep postgres
```

Expected output:
```
postgres-postgres-1   Up X minutes (healthy)
```

## Validate the Ontology

VG/SQL uses a LinkML ontology with VG extensions. Validate it:

```bash
# Validate all ontologies in the ontology/ directory
make validate-ontology
```

Expected output:
```
============================================================
Layer 1: LinkML Structure Validation
============================================================
File: ontology/supply_chain.yaml
✓ LinkML structure validation passed

============================================================
Layer 2: VG Annotation Validation
============================================================
File: ontology/supply_chain.yaml
✓ VG annotation validation passed
  - 9 entity classes (TBox)
  - 17 relationship classes (RBox)
```

## Run the Tests

```bash
# Run all tests
make test
```

## Your First Query

### YELLOW: Recursive Traversal

Find all upstream suppliers from a tier 1 supplier:

```python
import psycopg2
from virt_graph.handlers.traversal import traverse

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="supply_chain",
    user="virt_graph",
    password="dev_password"
)

# Get a tier 1 supplier ID
with conn.cursor() as cur:
    cur.execute("SELECT id FROM suppliers WHERE tier = 1 LIMIT 1")
    supplier_id = cur.fetchone()[0]

# Traverse upstream (who sells to this supplier?)
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=supplier_id,
    direction="inbound",
    max_depth=10,
)

print(f"Found {result['total_count']} upstream suppliers")
print(f"Reached depth {result['depth_reached']}")

conn.close()
```

### RED: Shortest Path

Find the shortest route between two facilities:

```python
import psycopg2
from virt_graph.handlers.pathfinding import shortest_path

conn = psycopg2.connect(
    host="localhost",
    database="supply_chain",
    user="virt_graph",
    password="dev_password"
)

# Get facility IDs
with conn.cursor() as cur:
    cur.execute("SELECT id FROM facilities WHERE name = 'Chicago Warehouse'")
    chicago_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM facilities WHERE name = 'LA Distribution Center'")
    la_id = cur.fetchone()[0]

# Find shortest path by distance
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

if result["path"]:
    print(f"Path: {' → '.join(str(n) for n in result['path'])}")
    print(f"Total distance: {result['distance']:.1f} km")
else:
    print(f"No path found: {result['error']}")

conn.close()
```

## Next Steps

- [Architecture](../concepts/architecture.md) - Understand the design
- [Ontology System](../concepts/ontology.md) - Define your own ontology
- [Handlers Overview](../handlers/overview.md) - All available handlers
- [Supply Chain Tutorial](../examples/supply-chain.md) - Complete example

## Common Commands

```bash
make help              # Show all commands
make db-up             # Start PostgreSQL
make db-down           # Stop PostgreSQL
make db-reset          # Reset database (regenerate data)
make validate-ontology # Validate all ontologies
make test              # Run tests
make serve-docs        # Serve documentation locally
```
