# Quick Start

Get VG/SQL running in 5 minutes.

## Prerequisites

- Python 3.12+
- Poetry (`pip install poetry`)
- PostgreSQL database (for live queries)

## Installation

```bash
git clone https://github.com/mcfitzgerald/virt-graph.git
cd virt-graph
poetry install
```

## Database Setup

```bash
cp .env.example .env
# Edit .env with your PostgreSQL connection string:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/erp_db
```

## Validate the Ontology

VG/SQL uses a LinkML ontology with VG extensions. Validate it:

```bash
poetry run python scripts/validate_ontology.py --all
```

Expected output:
```
Layer 1: LinkML Structure Validation — ✓ passed
Layer 2: VG Annotation Validation — ✓ passed
  - 38 entity classes (TBox)
  - 50 relationship classes (RBox)
```

## Run the Tests

```bash
poetry run pytest pcg_example/tests/ -v
```

## Your First Query

### Recursive Traversal

Find all upstream suppliers from a tier 1 supplier:

```python
from virt_graph.db import connection
from virt_graph.handlers.traversal import traverse

with connection() as conn:
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
```

### Algorithm: Shortest Path

Find the shortest route between two facilities:

```python
from virt_graph.db import connection
from virt_graph.handlers.pathfinding import shortest_path

with connection() as conn:
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
