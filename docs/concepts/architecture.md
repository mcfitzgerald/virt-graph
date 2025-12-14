# Architecture

VG/SQL enables graph queries over relational data through three components working together: an ontology, handlers, and an orchestrating agentic system.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   User Question                             │
│           "Who supplies Acme Corp?"                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Agentic System                            │
│                 (Claude Code, etc.)                         │
│                                                             │
│  1. Read ontology → understand entities & relationships     │
│  2. Determine complexity → GREEN/YELLOW/RED                 │
│  3. Generate query → SQL or handler call                    │
│  4. Execute → return results                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Ontology   │   │  Handlers   │   │  Estimator  │
│  (LinkML)   │   │  (Python)   │   │  (Sampler)  │
└─────────────┘   └─────────────┘   └─────────────┘
          │               │               │
          └───────────────┼───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Relational Database                         │
│                   (PostgreSQL)                              │
└─────────────────────────────────────────────────────────────┘
```

## The Three Components

### 1. Ontology (What Exists)

The ontology defines the domain model using [LinkML](https://linkml.io) with VG extensions:

- **TBox (Entity Classes)**: What things exist (Supplier, Part, Facility)
- **RBox (Relationship Classes)**: How things relate (SuppliesTo, ComponentOf, ConnectsTo)
- **Complexity Annotations**: What strategy each relationship requires

The ontology maps graph concepts to SQL structures without requiring data migration:

| Ontology Concept | SQL Mapping |
|-----------------|-------------|
| Entity class | Table |
| Entity instance | Row |
| Relationship | Foreign key(s) |
| Traversal | Recursive query or handler |

### 2. Handlers (How to Query)

Schema-parameterized Python functions that fill gaps in native SQL:

| Complexity | Handlers | Why Not Plain SQL? |
|------------|----------|-------------------|
| YELLOW | `traverse()`, `bom_explode()` | Recursive CTEs are complex; handlers provide consistent interface |
| RED | `shortest_path()`, `centrality()` | No native SQL support for graph algorithms |

Handlers accept table/column names as arguments—they know nothing about "suppliers" or "parts", only about tables and foreign keys. This makes them reusable across any schema.

### 3. Estimator (Safety First)

Before executing potentially expensive operations, the estimator samples the graph structure:

```python
from virt_graph.estimator import GraphSampler

sampler = GraphSampler(conn, edges_table, edge_from_col, edge_to_col)
estimate = sampler.estimate(start_id, sample_depth=3)

# Properties detected:
# - growth_trend: "increasing", "stable", "decreasing"
# - has_cycles: True/False
# - hub_detected: True/False
# - convergence_ratio: node sharing rate
```

This prevents runaway queries that would load millions of nodes into memory.

## The Dispatch Pattern

The agentic system uses complexity annotations to dispatch queries:

```
┌──────────────────────────────────────────────────────────────┐
│                     Question                                  │
│     "Which suppliers have ISO9001 certification?"            │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  Read Ontology                                │
│                                                               │
│  HasCertification:                                           │
│    vg:traversal_complexity: GREEN  ←── Simple FK join        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  Generate SQL                                 │
│                                                               │
│  SELECT s.name, c.certification_type                         │
│  FROM suppliers s                                            │
│  JOIN supplier_certifications c ON s.id = c.supplier_id      │
│  WHERE c.certification_type = 'ISO9001';                     │
└──────────────────────────────────────────────────────────────┘
```

For YELLOW/RED complexity:

```
┌──────────────────────────────────────────────────────────────┐
│                     Question                                  │
│          "Find all upstream suppliers of Acme"               │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  Read Ontology                                │
│                                                               │
│  SuppliesTo:                                                 │
│    vg:traversal_complexity: YELLOW  ←── Recursive traversal  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  Call Handler                                 │
│                                                               │
│  traverse(conn,                                              │
│      nodes_table="suppliers",                                │
│      edges_table="supplier_relationships",                   │
│      edge_from_col="seller_id",                             │
│      edge_to_col="buyer_id",                                │
│      start_id=acme_id,                                       │
│      direction="inbound")                                    │
└──────────────────────────────────────────────────────────────┘
```

## Design Principles

### Schema Parameterization

Handlers never hardcode table names:

```python
# Good: Schema-parameterized
traverse(conn, nodes_table="suppliers", edges_table="supplier_relationships", ...)

# Bad: Hardcoded (we don't do this)
traverse_suppliers(conn, start_id=123)
```

This enables reuse: the same `traverse()` works for supplier networks, org charts, social graphs—any recursive structure.

### Frontier-Batched BFS

All traversal handlers use batched queries instead of one-query-per-node:

```sql
-- One query for entire frontier (good)
SELECT * FROM edges WHERE from_id = ANY(ARRAY[1,2,3,4,5])

-- NOT one query per node (bad)
SELECT * FROM edges WHERE from_id = 1
SELECT * FROM edges WHERE from_id = 2
...
```

This is mandatory throughout the codebase for performance.

### Soft-Delete Support

Handlers accept an optional `soft_delete_column` parameter:

```python
result = traverse(
    conn,
    nodes_table="suppliers",
    soft_delete_column="deleted_at",  # Filters out soft-deleted rows
    ...
)
```

This prevents traversing through logically deleted nodes.

## Single Source of Truth

The VG metamodel (`ontology/virt_graph.yaml`) defines:

- Required annotations for entity/relationship classes
- Valid values for `traversal_complexity` enum
- Validation rules

The `OntologyAccessor` reads this file to dynamically validate domain ontologies—no hardcoded rules in Python.

## Next Steps

- [Complexity Levels](complexity-levels.md) - Deep dive on GREEN/YELLOW/RED
- [Handlers Overview](../handlers/overview.md) - Available operations
- [Ontology System](ontology.md) - Defining your domain
