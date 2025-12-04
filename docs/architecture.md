# Virtual Graph Architecture

This document describes the architecture of the Virtual Graph system, which enables graph-like queries over enterprise relational data without migration to a graph database.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLAUDE CODE SESSION                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    CONTEXT MANAGEMENT                            │    │
│  │                                                                  │    │
│  │   ALWAYS LOADED              ON-DEMAND (Skills)                 │    │
│  │   ┌──────────────┐          ┌──────────────┐                    │    │
│  │   │  Ontology    │          │   Patterns   │                    │    │
│  │   │  (semantic   │          │   (learned   │                    │    │
│  │   │   mappings)  │          │    SQL)      │                    │    │
│  │   └──────────────┘          └──────────────┘                    │    │
│  │                              ┌──────────────┐                    │    │
│  │                              │   Schema     │                    │    │
│  │                              │ (introspect) │                    │    │
│  │                              └──────────────┘                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    GENERIC HANDLERS                              │    │
│  │                    (schema-parameterized)                        │    │
│  │                                                                  │    │
│  │   traverse(nodes_table, edges_table, fk_from, fk_to,            │    │
│  │            direction, stop_condition, max_depth)                 │    │
│  │                                                                  │    │
│  │   shortest_path(nodes_table, edges_table, weight_col,           │    │
│  │                 start_id, end_id)                                │    │
│  │                                                                  │    │
│  │   centrality(nodes_table, edges_table, centrality_type)         │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         PostgreSQL                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Layer Separation

Virtual Graph uses a layered architecture with clear separation of concerns:

### Layer 1: Semantic Layer (Ontology)

**Location**: `ontology/supply_chain.yaml`

The ontology provides semantic mappings between business concepts and physical database objects:

```yaml
classes:
  Supplier:
    description: "Companies that provide materials/parts"
    sql_mapping:
      table: suppliers
      primary_key: id
      identifier_columns: [supplier_code, name]

relationships:
  supplies_to:
    domain: Supplier
    range: Supplier
    sql_mapping:
      table: supplier_relationships
      domain_key: seller_id
      range_key: buyer_id
    traversal_complexity: YELLOW
```

**Purpose**:
- Maps business terms to SQL tables/columns
- Defines relationship semantics (cardinality, directionality)
- Classifies traversal complexity (GREEN/YELLOW/RED)
- Serves as "always-loaded" context for query understanding

### Layer 2: Physical Layer (Schema Introspection)

**Location**: `.claude/skills/schema/`

The schema skill provides live database introspection:

```sql
-- Tables and columns
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public';

-- Foreign keys
SELECT tc.table_name AS source_table,
       kcu.column_name AS source_column,
       ccu.table_name AS target_table
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ...
WHERE tc.constraint_type = 'FOREIGN KEY';
```

**Purpose**:
- Resolves ontology concepts to actual SQL
- Provides column types for query generation
- Validates foreign key relationships
- Invoked on-demand via skill system

### Layer 3: Pattern Layer (Learned SQL)

**Location**: `patterns/templates/`

Pattern templates capture reusable query structures:

```yaml
# patterns/templates/traversal/bom_explosion.yaml
name: bom_explosion
description: "Explode bill of materials recursively"
handler: traverse
applicability:
  - query mentions "bill of materials", "BOM", "components"
  - relationship has is_recursive: true

ontology_bindings:
  node_class: Part
  edge_relationship: component_of
  direction: outbound

handler_params:
  direction: "outbound"
  max_depth: 20
```

**Purpose**:
- Accelerates query execution with known patterns
- Reduces LLM reasoning for common queries
- Documents successful query strategies
- Invoked on-demand via skill system

### Layer 4: Handler Layer (Execution)

**Location**: `src/virt_graph/handlers/`

Schema-parameterized handlers execute graph operations:

```python
# handlers/traversal.py
def traverse(
    conn,
    nodes_table: str,      # "suppliers"
    edges_table: str,      # "supplier_relationships"
    edge_from_col: str,    # "seller_id"
    edge_to_col: str,      # "buyer_id"
    start_id: int,
    direction: str = "outbound",
    max_depth: int = 10,
) -> dict:
    """Generic graph traversal using frontier-batched BFS."""
```

**Purpose**:
- Execute traversal without knowing domain semantics
- Enforce safety limits (MAX_NODES, MAX_DEPTH)
- Use efficient query patterns (frontier batching)
- Return structured results for display

## Query Flow

### Example: "Find all tier 3 suppliers for Acme Corp"

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. USER QUERY                                                     │
│    "Find all tier 3 suppliers for Acme Corp"                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. CONTEXT LOOKUP                                                 │
│    Ontology → supplies_to relationship is YELLOW (recursive)     │
│    Pattern → matches tier_traversal template                      │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. PARAMETER RESOLUTION                                           │
│    Schema Skill → suppliers table, supplier_relationships        │
│    Ontology → seller_id (domain), buyer_id (range)               │
│    Query → start_id = lookup("Acme Corp")                        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. HANDLER INVOCATION                                             │
│    traverse(                                                      │
│        nodes_table="suppliers",                                   │
│        edges_table="supplier_relationships",                      │
│        edge_from_col="seller_id",                                │
│        edge_to_col="buyer_id",                                   │
│        start_id=42,                                              │
│        direction="inbound",                                       │
│        max_depth=10                                              │
│    )                                                              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 5. RESULT FILTERING                                               │
│    Filter nodes where tier = 3                                    │
│    Return 26 tier 3 suppliers                                     │
└──────────────────────────────────────────────────────────────────┘
```

## Handler Architecture

### Safety Infrastructure

```python
# handlers/base.py

# Non-negotiable limits
MAX_DEPTH = 50          # Absolute traversal depth limit
MAX_NODES = 10_000      # Max nodes to visit in single traversal
MAX_RESULTS = 1_000     # Max rows to return
QUERY_TIMEOUT_SEC = 30  # Per-query timeout

class SafetyLimitExceeded(Exception):
    """Raised when a handler would exceed safety limits."""
    pass

class SubgraphTooLarge(Exception):
    """Raised when estimated subgraph exceeds MAX_NODES."""
    pass
```

### Frontier-Batched BFS

The traversal handler uses frontier batching for efficiency:

```python
def traverse(conn, edges_table, start_id, ...):
    frontier = {start_id}
    visited = {start_id}

    for depth in range(max_depth):
        if not frontier:
            break

        # ONE query for entire frontier (not per-node!)
        edges = fetch_edges_for_frontier(conn, edges_table, list(frontier), ...)

        next_frontier = set()
        for from_id, to_id in edges:
            if to_id not in visited:
                next_frontier.add(to_id)
                visited.add(to_id)

        frontier = next_frontier

    return fetch_nodes(conn, nodes_table, list(visited))
```

**Key Principle**: One SQL query per depth level, never one query per node.

### Handler Catalog

| Handler | Route | Purpose | Key Parameters |
|---------|-------|---------|----------------|
| `traverse` | YELLOW | BFS/DFS traversal | direction, max_depth, stop_condition |
| `shortest_path` | RED | Dijkstra via NetworkX | weight_col, max_depth |
| `centrality` | RED | Node importance | centrality_type, top_n |
| `connected_components` | RED | Cluster detection | min_size |

## Skills System

Skills provide on-demand context loading:

### Schema Skill
```markdown
# .claude/skills/schema/SKILL.md
---
name: virt-graph-schema
description: Introspect PostgreSQL schema for physical table/column details
allowed-tools: Read, Bash
---

## When to Use
Invoke when translating ontology concepts to physical SQL.

## Available Queries
- Tables and columns with types
- Foreign key relationships
- Primary keys and unique constraints
```

### Patterns Skill
```markdown
# .claude/skills/patterns/SKILL.md
---
name: virt-graph-patterns
description: Load SQL pattern templates for graph operations
allowed-tools: Read, Glob, Grep
---

## Pattern Groups
- traversal/: BOM explosion, tier traversal
- pathfinding/: Shortest path, all paths
- network-analysis/: Centrality, connectivity
```

### Handlers Skill
```markdown
# .claude/skills/handlers/SKILL.md
---
name: virt-graph-handlers
description: Generic graph operation handlers
allowed-tools: Read, Bash
---

## Handler Groups
- traversal: traverse() - BFS/DFS
- pathfinding: shortest_path() - Dijkstra
- network-analysis: centrality() - NetworkX
```

## Data Flow

### Write Path (Not Applicable)
Virtual Graph is read-only - it queries existing data without modifying it.

### Read Path

```
User Query
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Claude    │────▶│   Handler   │────▶│  PostgreSQL │
│   (LLM)     │◀────│             │◀────│             │
└─────────────┘     └─────────────┘     └─────────────┘
    │                                         │
    │  (reasoning)                            │  (SQL)
    ▼                                         ▼
┌─────────────┐                         ┌─────────────┐
│  Ontology   │                         │   Results   │
│  Patterns   │                         │             │
│  Schema     │                         │             │
└─────────────┘                         └─────────────┘
```

## Extension Points

### Adding New Domains

1. **Create Ontology**: Define classes and relationships in YAML
2. **Record Patterns**: Capture successful query patterns
3. **Configure Handlers**: Map ontology relationships to handler parameters

### Adding New Handlers

1. **Implement Handler**: Schema-parameterized function in `handlers/`
2. **Add Safety Checks**: Use `check_limits()` and size estimation
3. **Document in Skill**: Update handlers skill reference

### Adding New Patterns

1. **Record Raw Pattern**: Capture in `patterns/raw/`
2. **Generalize**: Extract template with ontology bindings
3. **Add to Catalog**: Place in appropriate `patterns/templates/` group

## Security Considerations

### SQL Injection Prevention
- All handler parameters are validated
- Table/column names are checked against schema
- User values are parameterized in queries

### Resource Protection
- MAX_NODES prevents graph explosion
- QUERY_TIMEOUT prevents runaway queries
- Pre-traversal estimation catches large graphs early

### Access Control
- Handlers use provided database connection
- Connection credentials managed externally
- No credential storage in handlers

## Performance Characteristics

### Latency Profile

| Query Type | Typical Latency | Bottleneck |
|------------|-----------------|------------|
| GREEN (simple) | 1-5ms | PostgreSQL query |
| YELLOW (traverse) | 2-10ms | Number of depth levels |
| RED (network) | 2-50ms | NetworkX graph loading |

### Scaling Considerations

- Frontier batching scales with depth, not node count
- NetworkX loading bounded by MAX_NODES
- PostgreSQL indexes critical for FK lookups

## Future Architecture

### Potential Enhancements

1. **Incremental Loading**: Load NetworkX graphs on-demand
2. **Caching Layer**: Cache frequent traversal results
3. **Distributed Handlers**: Scale across multiple workers
4. **Query Planning**: Optimize handler selection automatically
