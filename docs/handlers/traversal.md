# Traversal Handlers

The traversal module provides handlers for recursive graph traversal over relational data. These handlers support `recursive_traversal`, `temporal_traversal`, `path_aggregation`, and `hierarchical_aggregation` operation types.

## Overview

| Handler | Purpose |
|---------|---------|
| `traverse()` | Multi-hop BFS traversal with direction control |
| `traverse_collecting()` | Traverse while collecting nodes matching a condition |
| `path_aggregate()` | Aggregate values along paths (SUM/MAX/MIN/multiply) |

## traverse()

Multi-hop traversal from a starting node using frontier-batched BFS.

### Signature

```python
from virt_graph.handlers.traversal import traverse

result = traverse(
    conn,                          # Database connection
    nodes_table,                   # Node/entity table name
    edges_table,                   # Edge/relationship table name
    edge_from_col,                 # FK column for edge source
    edge_to_col,                   # FK column for edge target
    start_id,                      # Starting node ID
    direction="outbound",          # "inbound", "outbound", or "both"
    max_depth=10,                  # Maximum traversal depth
    stop_condition=None,           # SQL WHERE clause for terminal nodes
    collect_columns=None,          # Extra columns to collect from edges
    prefilter_sql=None,            # SQL WHERE clause to filter edges
    include_start=True,            # Include starting node in results
    max_nodes=None,                # Override default node limit
    skip_estimation=False,         # Skip size estimation
    estimation_config=None,        # Custom estimation parameters
    soft_delete_column=None,       # Column name for soft deletes
)
```

### Direction Explained

```
     A ──sells_to──▶ B ──sells_to──▶ C

Direction from B's perspective:
- "outbound": B → C (who does B sell to?)
- "inbound":  A → B (who sells to B?)
- "both":     A ↔ B ↔ C (all connections)
```

### Result Structure

```python
{
    "nodes": [                    # All discovered nodes
        {"id": 1, "name": "Acme", ...},
        {"id": 2, "name": "Bolt Co", ...},
    ],
    "paths": {                    # Path from start to each node
        2: [1, 2],               # Node 2 reached via: start → 1 → 2
        3: [1, 2, 3],
    },
    "edges": [                    # All traversed edges
        {"from": 1, "to": 2, ...},
    ],
    "depth_reached": 3,           # Maximum depth explored
    "nodes_visited": 45,          # Total nodes encountered
    "terminated_at": None,        # Stop condition node, if hit
}
```

### Example: Find Upstream Suppliers

```python
# "Find all suppliers that feed into Acme Corp"
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",      # Who sells
    edge_to_col="buyer_id",         # To whom
    start_id=acme_id,
    direction="inbound",            # Follow edges pointing TO Acme
    max_depth=10,
    include_start=False,            # Don't include Acme itself
)

print(f"Found {len(result['nodes'])} upstream suppliers")
for node in result['nodes']:
    depth = len(result['paths'][node['id']]) - 1
    print(f"  Tier {depth}: {node['name']}")
```

### Example: Find Downstream with Stop Condition

```python
# "Find all buyers of Acme, but stop at tier-3 suppliers"
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="outbound",           # Follow edges FROM Acme
    max_depth=10,
    stop_condition="tier = 3",      # Stop when hitting tier-3
)

if result['terminated_at']:
    print(f"Stopped at tier-3 supplier: {result['terminated_at']}")
```

## traverse_collecting()

Traverse the graph while collecting nodes that match a specific condition.

### Signature

```python
from virt_graph.handlers.traversal import traverse_collecting

result = traverse_collecting(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    start_id,
    target_condition,              # SQL WHERE clause for matching nodes
    direction="outbound",
    max_depth=10,
    max_nodes=None,
    skip_estimation=False,
    soft_delete_column=None,
)
```

### Result Structure

```python
{
    "matching_nodes": [...],       # Nodes matching the condition
    "matching_paths": {            # Paths to each matching node
        5: [1, 3, 5],
        8: [1, 2, 8],
    },
    "total_traversed": 45,         # Total nodes explored
    "depth_reached": 4,
}
```

### Example: Find All ISO-Certified Upstream Suppliers

```python
# "Find all ISO9001-certified suppliers in Acme's supply chain"
result = traverse_collecting(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    target_condition="id IN (SELECT supplier_id FROM supplier_certifications WHERE certification_type = 'ISO9001')",
    direction="inbound",
    max_depth=10,
)

print(f"Found {len(result['matching_nodes'])} certified suppliers")
```

## path_aggregate()

Aggregate values along paths in a graph. This is the generic handler for operations like bill of materials (BOM) explosion, cost rollups, and hierarchical aggregations.

### Signature

```python
from virt_graph.handlers.traversal import path_aggregate

result = path_aggregate(
    conn,                          # Database connection
    nodes_table,                   # Node/entity table name
    edges_table,                   # Edge/relationship table name
    edge_from_col,                 # FK column for edge source
    edge_to_col,                   # FK column for edge target
    start_id,                      # Starting node ID
    value_col,                     # Column containing values to aggregate
    operation="sum",               # "sum", "max", "min", "multiply", "count"
    direction="outbound",          # "inbound" or "outbound"
    max_depth=20,                  # Maximum traversal depth
    max_nodes=None,                # Override node limit
    skip_estimation=False,
    soft_delete_column=None,
)
```

### Operations

| Operation | Description | Use Case |
|-----------|-------------|----------|
| `sum` | Sum values at each depth | Cost rollups |
| `max` | Maximum value along path | Critical path duration |
| `min` | Minimum value along path | Bottleneck detection |
| `multiply` | Multiply quantities through hierarchy | BOM explosion |
| `count` | Count nodes at each depth | Network analysis |

### The Diamond Problem

Hierarchical structures often have shared components:

```
        Product A
        /       \
   Assy B      Assy C
   (qty: 2)    (qty: 1)
       \        /
        Part D
        (qty: 3 in B, 5 in C)

Total Part D needed: (2 × 3) + (1 × 5) = 11
```

`path_aggregate()` with `operation="multiply"` handles this correctly using a recursive CTE that aggregates quantities across all paths.

### Result Structure

```python
{
    "aggregates": [
        {
            "node_id": 123,
            "depth": 3,
            "aggregated_value": 48.0,  # Based on operation
        },
        ...
    ],
    "total_nodes": 1024,               # Unique nodes count
    "max_depth": 8,                    # Deepest level reached
    "nodes_visited": 2048,             # Total nodes traversed
}
```

### Example: BOM Explosion

```python
# "What parts do we need to build a Turbo Encabulator?"
result = path_aggregate(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="parent_part_id",
    edge_to_col="child_part_id",
    start_id=turbo_encabulator_id,
    value_col="quantity",
    operation="multiply",              # Propagate quantities through hierarchy
    max_depth=20,
)

print(f"BOM contains {result['total_nodes']} unique parts")
print(f"Maximum assembly depth: {result['max_depth']}")

# Group by depth level
from collections import defaultdict
by_depth = defaultdict(list)
for agg in result['aggregates']:
    by_depth[agg['depth']].append(agg)

for depth in sorted(by_depth.keys()):
    print(f"\nLevel {depth}: {len(by_depth[depth])} parts")
```

### Example: Cost Rollup

```python
# "Sum costs along the supply chain"
result = path_aggregate(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=end_customer_id,
    value_col="unit_price",
    operation="sum",                   # Sum costs
    direction="inbound",
    max_depth=10,
)
```

## Algorithm: Frontier-Batched BFS

All traversal handlers use the same core algorithm:

```python
# Pseudocode
visited = {start_id}
frontier = [start_id]
depth = 0

while frontier and depth < max_depth and len(visited) < max_nodes:
    # Single query for entire frontier
    query = """
        SELECT * FROM edges
        WHERE from_col = ANY(%s)  -- All frontier nodes at once
    """
    new_edges = execute(query, [frontier])

    # Build next frontier
    next_frontier = []
    for edge in new_edges:
        if edge.to_id not in visited:
            visited.add(edge.to_id)
            next_frontier.append(edge.to_id)

    frontier = next_frontier
    depth += 1
```

Key properties:
- **One query per depth level**, not one per node
- Uses PostgreSQL `= ANY(ARRAY[...])` for efficient IN clause
- Tracks visited nodes to avoid cycles
- Bounded by `max_depth` and `max_nodes`

## Safety Limits

Default limits (from `base.py`):

| Limit | Default | Purpose |
|-------|---------|---------|
| `MAX_DEPTH` | 50 | Absolute depth ceiling |
| `MAX_NODES` | 10,000 | Maximum nodes to visit |
| `MAX_RESULTS` | 100,000 | Maximum rows returned |
| `QUERY_TIMEOUT_SEC` | 30 | Per-query timeout |

Override per-call:

```python
result = traverse(
    ...,
    max_depth=5,        # Shallower than default
    max_nodes=100,      # Fewer nodes
)
```

## Pre-flight Estimation

For potentially large traversals, the handler automatically samples:

```python
# Estimation happens by default
result = traverse(conn, ..., skip_estimation=False)

# Skip if you know the graph is small
result = traverse(conn, ..., skip_estimation=True)

# Custom estimation config
from virt_graph.estimator import EstimationConfig

config = EstimationConfig(
    base_damping=0.85,
    safety_margin=1.5,
)
result = traverse(conn, ..., estimation_config=config)
```

## Next Steps

- [Pathfinding Handlers](pathfinding.md) - Shortest path algorithms
- [Network Handlers](network.md) - Centrality, components, resilience
- [Operation Types](../concepts/ontology.md) - When to use which handler
