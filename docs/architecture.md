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
│  │   ALWAYS LOADED                                                  │    │
│  │   ┌──────────────┐                                               │    │
│  │   │  Ontology    │                                               │    │
│  │   │  (semantic   │                                               │    │
│  │   │   mappings)  │                                               │    │
│  │   └──────────────┘                                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    GENERIC HANDLERS                              │    │
│  │                    (schema-parameterized)                        │    │
│  │                                                                  │    │
│  │   traverse(nodes_table, edges_table, fk_from, fk_to,            │    │
│  │            direction, max_depth)                                 │    │
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

## Traffic Light Routing

The routing system classifies queries by complexity:

| Route | Complexity | Handler | Example |
|-------|------------|---------|---------|
| **GREEN** | Simple SQL | Direct query | "Find supplier Acme Corp" |
| **YELLOW** | Recursive traversal | `traverse()` | "Find all tier 3 suppliers" |
| **RED** | Network algorithms | NetworkX | "Cheapest route Chicago→LA" |

### GREEN: Direct SQL

- Simple lookups (WHERE clause on single table)
- 1-2 hop joins with explicit foreign keys
- Aggregations on single tables
- No recursion or variable-length paths

### YELLOW: Recursive Traversal

- Variable-length paths (N-hop where N is unknown)
- Self-referential relationships (parent-child)
- Recursive patterns (BOM explosion, tier chains)
- Tree/DAG traversals

### RED: Network Algorithms

- Shortest path queries (with or without weights)
- Centrality calculations
- Connected component analysis
- Graph metrics

## Layer Architecture

### Layer 1: Semantic Layer (Ontology)

The ontology (`ontology/supply_chain.yaml`) provides semantic mappings between business concepts and physical database objects.

```yaml
Supplier:
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: suppliers
    vg:primary_key: id

SuppliesTo:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id
    vg:range_key: buyer_id
    vg:traversal_complexity: YELLOW
```

### Layer 2: Handler Layer (Execution)

Schema-parameterized handlers execute graph operations (`src/virt_graph/handlers/`):

- `traverse()` - Frontier-batched BFS traversal
- `shortest_path()` - Dijkstra via NetworkX
- `centrality()` - Degree/betweenness/closeness/PageRank

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

## Query Flow Example

**Query**: "Find all tier 3 suppliers for Acme Corp"

1. **Context Lookup**: Ontology identifies `supplies_to` as YELLOW (recursive)
2. **Parameter Resolution**: Map to `suppliers` table, `supplier_relationships` edges
3. **Handler Invocation**: `traverse(direction="inbound", max_depth=10)`
4. **Result Filtering**: Filter nodes where `tier = 3`

## Performance Characteristics

| Query Type | Typical Latency | Bottleneck |
|------------|-----------------|------------|
| GREEN (simple) | 1-5ms | PostgreSQL query |
| YELLOW (traverse) | 2-10ms | Number of depth levels |
| RED (network) | 2-50ms | NetworkX graph loading |

## Handlers Reference

### YELLOW (Recursive Traversal)

- `traverse(conn, nodes_table, edges_table, edge_from_col, edge_to_col, start_id, direction, max_depth, max_nodes)`
- `traverse_collecting(conn, ..., target_condition)` - Collect nodes matching condition
- `bom_explode(conn, start_part_id, max_depth, include_quantities, max_nodes)`

### RED (Network Algorithms)

- `shortest_path(conn, ..., start_id, end_id, weight_col, excluded_nodes)`
- `all_shortest_paths(conn, ..., max_paths, excluded_nodes)`
- `centrality(conn, ..., centrality_type, top_n)` - degree/betweenness/closeness/pagerank
- `connected_components(conn, ..., min_size)`
- `resilience_analysis(conn, ..., node_to_remove)`
