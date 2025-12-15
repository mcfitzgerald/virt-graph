# Supply Chain Example

This directory contains a complete supply chain domain example for VG/SQL.

## Contents

- `ontology/supply_chain.yaml` - Domain ontology with VG annotations
- `postgres/` - PostgreSQL database setup
  - `schema.sql` - Database schema (15 tables)
  - `seed.sql` - Generated sample data (~130K rows)
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

The supply chain schema includes:

| Entity | Table | Description |
|--------|-------|-------------|
| Supplier | `suppliers` | 500 suppliers (50 T1, 150 T2, 300 T3) |
| Part | `parts` | 5,000 parts with BOM hierarchy |
| Product | `products` | 100 finished goods |
| Facility | `facilities` | 50 warehouses/plants |
| Order | `orders` | 20,000 purchase orders |
| Customer | `customers` | 1,000 customers |

Key relationships:
- `SuppliesTo` - Supplier network (self-referential)
- `ComponentOf` - Bill of Materials (self-referential)
- `ConnectsTo` - Transport routes between facilities

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
