# Quick Start

This guide shows how to use Virtual Graph handlers for common graph operations.

## Basic Usage

### Connect to Database

```python
from virt_graph.handlers import get_connection, traverse

conn = get_connection()
```

### Traverse a Graph

```python
from virt_graph.handlers import traverse

# Find all upstream suppliers for a company
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,  # Company ID
    direction="inbound",
    max_depth=10,
)

print(f"Found {result['nodes_visited']} suppliers")
print(f"Max depth reached: {result['depth_reached']}")
```

### BOM Explosion

```python
from virt_graph.handlers.traversal import bom_explode

# Get all components for a product
result = bom_explode(
    conn,
    start_part_id=789,
    max_depth=20,
    include_quantities=True,
)

for part in result['nodes']:
    qty = result['quantities'].get(part['id'], 1)
    print(f"Part {part['part_number']}: qty={qty}")
```

### Find Nodes Matching Condition

```python
from virt_graph.handlers.traversal import traverse_collecting

# Find all tier 3 suppliers reachable from Acme Corp
result = traverse_collecting(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    target_condition="tier = 3",
    direction="inbound",
)

print(f"Found {len(result['matching_nodes'])} tier 3 suppliers")
```

## Safety Limits

All handlers enforce safety limits:

| Limit | Value | Description |
|-------|-------|-------------|
| `MAX_DEPTH` | 50 | Maximum traversal depth |
| `MAX_NODES` | 10,000 | Maximum nodes to visit |
| `MAX_RESULTS` | 1,000 | Maximum rows returned |
| `QUERY_TIMEOUT` | 30s | Per-query timeout |

If a query would exceed limits, a `SubgraphTooLarge` exception is raised:

```python
from virt_graph.handlers import SubgraphTooLarge

try:
    result = traverse(conn, ..., max_depth=50)
except SubgraphTooLarge as e:
    print(f"Query too large: {e}")
    # Consider adding filters or reducing depth
```

## Common Patterns

### Upstream Traversal (Inbound)

Follow edges toward the start node:

```python
# Who supplies to company X?
traverse(..., direction="inbound")
```

### Downstream Traversal (Outbound)

Follow edges away from the start node:

```python
# Who does company X supply to?
traverse(..., direction="outbound")
```

### Bidirectional Traversal

Follow edges in both directions:

```python
# All connected entities
traverse(..., direction="both")
```

### Stop at Condition

Stop expanding nodes that match a condition:

```python
# Stop at tier 3 suppliers (but include them)
traverse(..., stop_condition="tier = 3")
```
