# Supply Chain Example

This directory contains a complete supply chain domain example for VG/SQL.

## Contents

- `ontology/supply_chain.yaml` - Domain ontology with VG annotations
- `postgres/` - PostgreSQL database setup
  - `schema.sql` - Database schema (16 tables)
  - `seed.sql` - Generated sample data (~488K rows)
  - `docker-compose.yml` - PostgreSQL container
- `neo4j/` - Neo4j setup for benchmarking
  - `docker-compose.yml` - Neo4j container
  - `migrate.py` - PostgreSQL to Neo4j migration
- `scripts/generate_data.py` - Data generation script
- `tests/` - Integration tests
- `questions.md` - 60 benchmark business questions

## Quick Start

```bash
# From project root
make db-up        # Start PostgreSQL
make test         # Run tests
make db-down      # Stop PostgreSQL
```

## Database Schema

The supply chain schema includes ~488K rows across 16 tables:

| Entity | Table | Rows | Description |
|--------|-------|------|-------------|
| Order | `orders` | 80,000 | Customer purchase orders |
| Order Item | `order_items` | 239,985 | Composite key (order_id, line_number) |
| Shipment | `shipments` | 45,737 | 70% fulfillment, 20% transfer, 10% replenishment |
| BOM | `bill_of_materials` | 42,706 | With effectivity dates |
| Inventory | `inventory` | 30,054 | Part × Facility |
| Part | `parts` | 15,008 | 5-level BOM hierarchy |
| Customer | `customers` | 5,000 | Retail, wholesale, enterprise |
| Supplier | `suppliers` | 1,000 | Tiered (100 T1, 300 T2, 600 T3) |
| Facility | `facilities` | 100 | Warehouses, factories, DCs |
| Product | `products` | 500 | Finished goods |

### Schema Enhancements (v0.9.9)

- **Composite Keys**: `order_items` uses SAP-style `(order_id, line_number)` PK
- **Shipment Types**: `order_fulfillment`, `transfer`, `replenishment`
- **BOM Effectivity**: `effective_from`/`effective_to` dates (80% current, 15% superseded, 5% future)
- **Relationship Status**: `supplier_relationships.relationship_status` (active/suspended/terminated)
- **Route Status**: `transport_routes.route_status` (active/seasonal/suspended/discontinued)

Key relationships:
- `SuppliesTo` - Supplier network (self-referential, ~10% inactive)
- `ComponentOf` - Bill of Materials (self-referential, with effectivity)
- `ConnectsTo` - Transport routes between facilities (~5% non-active)

## Regenerating Data

To regenerate the seed data:

```bash
cd supply_chain_example
poetry run python scripts/generate_data.py
```

This creates a new `postgres/seed.sql` with fresh synthetic data.

## Running Tests

```bash
# All tests
poetry run pytest supply_chain_example/tests/

# Specific test file
poetry run pytest supply_chain_example/tests/test_traversal.py -v

# Single test
poetry run pytest supply_chain_example/tests/test_bom_explode.py::test_bom_depth -v
```

## Benchmark Questions

See `questions.md` for 60 business questions organized by complexity:
- Q1-Q20: Direct queries (GREEN)
- Q21-Q40: Traversal queries (YELLOW)
- Q41-Q60: Algorithm queries (RED)
