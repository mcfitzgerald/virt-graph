---
name: virt-graph-schema
description: >
  Introspect PostgreSQL schema for physical table/column details. Use when
  generating SQL and need exact column names, foreign key relationships,
  data types, or sample data. Reconciles with ontology semantic mappings.
allowed-tools: Read, Bash
---

# Schema Introspection

## When to Use

Invoke when you need to translate ontology concepts to physical SQL:
- Mapping class names to table names
- Finding FK columns for relationships
- Checking column types for WHERE clauses
- Getting sample data to validate assumptions
- Understanding enterprise patterns (soft deletes, audit columns)

## Available Queries

Read `.claude/skills/schema/scripts/introspect.sql` for comprehensive queries:

### Core Discovery
1. **Tables and columns** - All columns with types, nullability, defaults
2. **Foreign keys** - Source/target relationships with constraint names
3. **Primary keys** - Identity columns for each table
4. **Unique constraints** - Potential natural identifiers

### Data Analysis
5. **Row counts** - Table sizes for query planning
6. **Check constraints** - Business rules encoded in schema
7. **Indexes** - Access patterns and optimization hints

### Graph Structure Detection
8. **Sample data template** - View actual data per table
9. **Self-referential relationships** - Detect graph edges (supplier_relationships, bill_of_materials, transport_routes)

### Enterprise Patterns
10. **Referential integrity template** - Check for orphaned records
11. **Column statistics** - Data distribution insights
12. **Soft delete tables** - Tables with `deleted_at` column
13. **Audit columns** - Tables with `created_at`, `updated_at`, etc.

## Instructions

### For SQL Generation

1. Run introspection queries against `information_schema`
2. Cross-reference with ontology `sql_mapping` sections
3. Return physical details needed for SQL generation:
   - Exact table name
   - Primary key column
   - Foreign key columns for joins
   - Data types for comparisons

### For Relationship Discovery

1. Query foreign keys to find explicit relationships
2. Look for self-referential patterns (same target table for multiple FKs)
3. Check for implicit relationships (matching column names without FK constraints)

### For Data Validation

1. Use row count queries to understand data volume
2. Run sample queries to verify assumptions
3. Check referential integrity for suspected relationships

## Connection

Use environment variable `DATABASE_URL` or default:
```
postgresql://virt_graph:dev_password@localhost:5432/supply_chain
```

## Example Usage

### Finding physical columns for an ontology class

```sql
-- Need to generate SQL for "Supplier" class
-- Step 1: Find the table
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'suppliers';
```

### Resolving a relationship to FK columns

```sql
-- Need to traverse "supplies_to" relationship
-- Step 1: Find FK columns in the edge table
SELECT source_column, target_column
FROM (
  SELECT kcu.column_name AS source_column,
         ccu.column_name AS target_column
  FROM information_schema.table_constraints tc
  JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
  JOIN information_schema.constraint_column_usage ccu
    ON tc.constraint_name = ccu.constraint_name
  WHERE tc.table_name = 'supplier_relationships'
    AND tc.constraint_type = 'FOREIGN KEY'
) fks;
-- Returns: seller_id -> id, buyer_id -> id
```

### Checking for soft-deleted records

```sql
-- Before querying suppliers, check soft delete pattern
SELECT COUNT(*) FROM suppliers WHERE deleted_at IS NOT NULL;
-- Add WHERE deleted_at IS NULL to active-only queries
```

## Supply Chain Schema Overview

The database contains 15 tables organized into domains:

| Domain | Tables | Graph Edges |
|--------|--------|-------------|
| Suppliers | suppliers, supplier_relationships, supplier_certifications | supplier_relationships (self-ref) |
| Parts | parts, bill_of_materials, part_suppliers | bill_of_materials (self-ref) |
| Products | products, product_components | product_components (parts -> products) |
| Facilities | facilities, transport_routes, inventory | transport_routes (self-ref) |
| Orders | customers, orders, order_items, shipments | shipments (uses transport_routes) |

Key self-referential edge tables:
- `supplier_relationships`: seller_id -> buyer_id (supplier tiers)
- `bill_of_materials`: child_part_id -> parent_part_id (BOM hierarchy)
- `transport_routes`: origin_facility_id -> destination_facility_id (logistics network)
