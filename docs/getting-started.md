# Getting Started

This guide walks through setting up the Virtual Graph environment and running your first queries.

## Prerequisites

- Python 3.12+
- Docker
- Poetry (Python package manager)

## Installation

```bash
# Clone the repository
git clone https://github.com/mcfitzgerald/virt-graph.git
cd virt-graph

# Install Python dependencies
poetry install
```

## Start the Database

The supply chain database runs in Docker:

```bash
# Start PostgreSQL
make db-up

# Or using docker-compose directly:
docker-compose -f postgres/docker-compose.yml up -d
```

This starts PostgreSQL 14 with:

| Setting | Value |
|---------|-------|
| Database | `supply_chain` |
| User | `virt_graph` |
| Password | `dev_password` |
| Port | `5432` |
| Connection String | `postgresql://virt_graph:dev_password@localhost:5432/supply_chain` |

The schema and seed data (~130K rows) are automatically loaded on first start.

## Verify Installation

### Check Database Status

```bash
make db-logs
docker-compose -f postgres/docker-compose.yml ps
```

Expected output:
```
NAME                COMMAND                  STATUS
virt-graph-db       "docker-entrypoint.s…"   Up (healthy)
```

### Run Tests

```bash
# Run all tests
make test

# Or run Gate 1 tests only (database and handlers)
make test-gate1
```

### Validate the Ontology

```bash
make validate-ontology
```

Expected output:
```
Layer 1 (LinkML): PASS
Layer 2 (VG Annotations): PASS
  Entity classes (TBox): 9
  Relationship classes (RBox): 15
```

## Test a Simple Query

```bash
poetry run python -c "
from virt_graph.handlers import get_connection, traverse

conn = get_connection()

# Find upstream suppliers for a company
result = traverse(
    conn,
    nodes_table='suppliers',
    edges_table='supplier_relationships',
    edge_from_col='seller_id',
    edge_to_col='buyer_id',
    start_id=1,
    direction='inbound',
    max_depth=5,
)

print(f'Nodes visited: {result[\"nodes_visited\"]}')
print(f'Max depth reached: {result[\"depth_reached\"]}')
"
```

## Database Management

```bash
make db-logs    # View logs
make db-down    # Stop database
make db-reset   # Reset database (regenerate data)
```

## Named Test Entities

The database includes named entities for reproducible queries:

| Type | Names |
|------|-------|
| Suppliers | "Acme Corp", "GlobalTech Industries", "Pacific Components" |
| Products | "Turbo Encabulator" (TURBO-001), "Flux Capacitor" (FLUX-001) |
| Facilities | "Chicago Warehouse" (FAC-CHI), "LA Distribution Center" (FAC-LA) |

## Next Steps

- [Architecture](architecture.md) - Understand how Virtual Graph works
- [Ontology Guide](ontology-guide.md) - Learn to create and use ontologies
- [Benchmark Report](benchmark-report.md) - Review evaluation results
