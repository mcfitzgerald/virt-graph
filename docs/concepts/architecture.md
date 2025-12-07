# Architecture

Virtual Graph uses a layered architecture that separates semantic understanding from physical execution.

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

### Layer 1: Semantic Layer (Ontology)

The ontology provides semantic mappings between business concepts and physical database objects.

**Location**: `ontology/`

```yaml
classes:
  # Entity class (TBox)
  Supplier:
    description: "Companies that provide materials/parts"
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: suppliers
      vg:primary_key: id
      vg:identifier: "[supplier_code]"

  # Relationship class (RBox)
  SuppliesTo:
    instantiates:
      - vg:SQLMappedRelationship
    annotations:
      vg:edge_table: supplier_relationships
      vg:domain_key: seller_id
      vg:range_key: buyer_id
      vg:domain_class: Supplier
      vg:range_class: Supplier
      vg:traversal_complexity: YELLOW
```

**Purpose**:

- Maps business terms to SQL tables/columns
- Defines relationship semantics
- Classifies traversal complexity (GREEN/YELLOW/RED)
- Serves as "always-loaded" context for query understanding

*For your domain: Create an ontology following `ontology/TEMPLATE.yaml`.*

### Layer 2: Physical Layer (Schema Introspection)

The schema skill provides live database introspection when needed.

**Location**: `.claude/skills/schema/`

**Purpose**:

- Resolves ontology concepts to actual SQL
- Provides column types for query generation
- Validates foreign key relationships
- Invoked on-demand via skill system

### Layer 3: Pattern Layer (Learned SQL)

Pattern templates capture reusable query structures.

**Location**: `patterns/templates/`

```yaml
# Example: BOM explosion pattern
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

### Layer 4: Handler Layer (Execution)

Schema-parameterized handlers execute graph operations.

**Location**: `src/virt_graph/handlers/`

**Purpose**:

- Execute traversal without knowing domain semantics
- Enforce safety limits
- Use efficient query patterns (frontier batching)
- Return structured results

## Traffic Light Routing

The routing system classifies queries by complexity:

```
┌─────────────────────────────────────────────────────────────────┐
│                        QUERY ROUTING                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐    Simple SQL     ┌─────────────────────────────┐ │
│  │ GREEN   │ ────────────────▶ │ Direct PostgreSQL Query     │ │
│  └─────────┘                    └─────────────────────────────┘ │
│                                                                  │
│  ┌─────────┐    traverse()     ┌─────────────────────────────┐ │
│  │ YELLOW  │ ────────────────▶ │ Frontier-Batched BFS        │ │
│  └─────────┘                    └─────────────────────────────┘ │
│                                                                  │
│  ┌─────────┐    NetworkX       ┌─────────────────────────────┐ │
│  │ RED     │ ────────────────▶ │ Graph Algorithm Handlers    │ │
│  └─────────┘                    └─────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### GREEN: Direct SQL

**Criteria**:
- Simple lookups (WHERE clause on single table)
- 1-2 hop joins with explicit foreign keys
- Aggregations on single tables
- No recursion or variable-length paths

**Examples**:
| Query | Route Reason |
|-------|--------------|
| "Find supplier Acme Corp" | Single table lookup |
| "Parts from supplier X" | One-hop FK join |
| "Products containing part Y" | Two-hop join |

### YELLOW: Recursive Traversal

**Criteria**:
- Variable-length paths (N-hop where N is unknown)
- Self-referential relationships (parent-child)
- Recursive patterns (BOM explosion, tier chains)
- Tree/DAG traversals

**Examples**:
| Query | Route Reason |
|-------|--------------|
| "All tier 3 suppliers for X" | Variable-depth supplier chain |
| "Full BOM for product Y" | Recursive part hierarchy |
| "Impact if supplier fails" | Cascading dependency traversal |

### RED: Network Algorithms

**Criteria**:
- Shortest path queries (with or without weights)
- Centrality calculations
- Connected component analysis
- Graph metrics

**Examples**:
| Query | Route Reason |
|-------|--------------|
| "Cheapest route from A to B" | Weighted shortest path |
| "Most critical facility" | Betweenness centrality |
| "Isolated suppliers" | Connected components |

### Route Selection Flow

```
                    ┌──────────────┐
                    │ Parse Query  │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Identify     │
                    │ Relationships│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ Ontology │ │ Keywords │ │ Pattern  │
       │ Lookup   │ │ Analysis │ │ Match    │
       └────┬─────┘ └────┬─────┘ └────┬─────┘
            │            │            │
            └────────────┼────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │ Resolve Conflicts│
              │ (prefer ontology)│
              └────────┬─────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
      ┌───────┐   ┌────────┐   ┌───────┐
      │ GREEN │   │ YELLOW │   │  RED  │
      │ SQL   │   │traverse│   │NetworkX│
      └───────┘   └────────┘   └───────┘
```

**Conflict Resolution Priority**:
1. Explicit ontology `traversal_complexity` (highest)
2. Query pattern match
3. Keyword analysis
4. Default to most conservative (lowest)

## Query Flow Example

**Query**: "Find all tier 3 suppliers for Acme Corp"

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

## Safety Infrastructure

### Non-Negotiable Limits

```python
MAX_DEPTH = 50          # Absolute traversal depth limit
MAX_NODES = 10_000      # Max nodes to visit in single traversal
MAX_RESULTS = 1_000     # Max rows to return
QUERY_TIMEOUT_SEC = 30  # Per-query timeout
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

### Estimator Module

Pre-traversal estimation prevents memory exhaustion:

```python
from virt_graph.estimator import GraphSampler, check_guards

# Sample and estimate before full traversal
sampler = GraphSampler(conn, "bill_of_materials", "parent_part_id", "child_part_id")
sample = sampler.sample(start_id, depth=5)

# Check guards
result = check_guards(sample, max_depth=20, max_nodes=10000)
if result.safe_to_proceed:
    # proceed with traversal
    pass
```

## Data Flow

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

**Note**: Virtual Graph is read-only. It queries existing data without modifying it.

## Performance Characteristics

| Query Type | Typical Latency | Bottleneck |
|------------|-----------------|------------|
| GREEN (simple) | 1-5ms | PostgreSQL query |
| YELLOW (traverse) | 2-10ms | Number of depth levels |
| RED (network) | 2-50ms | NetworkX graph loading |

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
