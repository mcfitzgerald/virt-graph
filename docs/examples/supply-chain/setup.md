# Setup

This guide walks through setting up the supply chain example environment.

## 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/mcfitzgerald/virt-graph.git
cd virt-graph

# Install Python dependencies
poetry install
```

## 2. Start PostgreSQL

The supply chain database runs in Docker:

```bash
# Start the database
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

The schema and seed data are automatically loaded on first start.

## 3. Verify Installation

### Check Database Status

```bash
# View container status
make db-logs

# Or directly:
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

Expected output:
```
tests/test_gate1_validation.py::test_database_connection PASSED
tests/test_gate1_validation.py::test_bom_traversal PASSED
tests/test_gate1_validation.py::test_supplier_network PASSED
...
```

### Verify Data

Connect to the database and check row counts:

```bash
docker exec -it virt-graph-db psql -U virt_graph -d supply_chain -c "
SELECT
    'suppliers' as table_name, COUNT(*) as rows FROM suppliers
UNION ALL SELECT 'parts', COUNT(*) FROM parts
UNION ALL SELECT 'bill_of_materials', COUNT(*) FROM bill_of_materials
UNION ALL SELECT 'facilities', COUNT(*) FROM facilities
UNION ALL SELECT 'transport_routes', COUNT(*) FROM transport_routes
UNION ALL SELECT 'orders', COUNT(*) FROM orders;
"
```

Expected output:
```
    table_name     | rows
-------------------+-------
 suppliers         |   500
 parts             |  5003
 bill_of_materials | 14283
 facilities        |    50
 transport_routes  |   197
 orders            | 20000
```

## 4. Validate the Ontology

The supply chain ontology should pass two-layer validation:

```bash
# Full validation
make validate-ontology
```

Expected output:
```
Layer 1 (LinkML): PASS
Layer 2 (VG Annotations): PASS
  Entity classes (TBox): 9
  Relationship classes (RBox): 15
```

You can also view the ontology structure:

```bash
# Show all entity classes (TBox)
make show-tbox

# Show all relationships (RBox)
make show-rbox
```

## 5. Test a Simple Query

Verify handlers work by running a quick test in Python:

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

### View Logs

```bash
make db-logs
# Or: docker-compose -f postgres/docker-compose.yml logs -f
```

### Stop Database

```bash
make db-down
# Or: docker-compose -f postgres/docker-compose.yml down
```

### Reset Database

To delete all data and reload from seed files:

```bash
make db-reset
# Or:
docker-compose -f postgres/docker-compose.yml down -v
docker-compose -f postgres/docker-compose.yml up -d
```

### Regenerate Seed Data

If you need fresh synthetic data:

```bash
poetry run python scripts/generate_data.py

# Then reset the database to load new data
make db-reset
```

## Troubleshooting

### Port Already in Use

If port 5432 is in use:

```bash
# Find what's using the port
lsof -i :5432

# Or change the port in postgres/docker-compose.yml
```

### Container Won't Start

```bash
# Check logs for errors
docker-compose -f postgres/docker-compose.yml logs

# Remove and recreate
docker-compose -f postgres/docker-compose.yml down -v
docker-compose -f postgres/docker-compose.yml up -d
```

### Tests Failing

Ensure the database is healthy:

```bash
docker-compose -f postgres/docker-compose.yml ps
# Should show "healthy" status

# Wait for health check if just started
sleep 10 && make test
```

## Next Steps

Now that your environment is running:

1. [**Ontology Tour**](ontology.md) - Understand the data model
2. [**Query Patterns**](patterns.md) - Learn pattern templates
3. [**Query Examples**](queries.md) - Run example queries
