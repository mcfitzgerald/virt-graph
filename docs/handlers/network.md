# Network Analysis Handlers

The network module provides handlers for graph-wide analysis algorithms. These are algorithm operations that load the full graph into NetworkX.

## Overview

| Handler | Purpose |
|---------|---------|
| `centrality()` | Calculate node importance (degree, betweenness, closeness, PageRank) |
| `connected_components()` | Find disconnected subgraphs |
| `graph_density()` | Calculate graph statistics |
| `neighbors()` | Get direct neighbors of a node |
| `resilience_analysis()` | Analyze impact of removing a node |

## centrality()

Calculate centrality scores to identify important nodes in the network.

### Signature

```python
from virt_graph.handlers.network import centrality

result = centrality(
    conn,                          # Database connection
    nodes_table,                   # Node/entity table name
    edges_table,                   # Edge/relationship table name
    edge_from_col,                 # FK column for edge source
    edge_to_col,                   # FK column for edge target
    centrality_type="betweenness", # Algorithm to use
    top_n=10,                      # Number of results to return
    weight_col=None,               # Edge weight column (optional)
    id_column="id",                # Node ID column name
    soft_delete_column=None,
)
```

### Centrality Types

| Type | Measures | Best For |
|------|----------|----------|
| `degree` | Number of connections | Finding highly connected nodes |
| `betweenness` | How often node is on shortest paths | Finding bridges/gatekeepers |
| `closeness` | Average distance to all other nodes | Finding central locations |
| `pagerank` | Importance based on incoming links | Finding influential nodes |

### Result Structure

```python
{
    "results": [
        {"node": {"id": 1, "name": "New York Factory", ...}, "score": 0.2327},
        {"node": {"id": 5, "name": "Chicago Hub", ...}, "score": 0.1854},
        ...
    ],
    "centrality_type": "betweenness",
    "graph_stats": {
        "nodes": 50,
        "edges": 197,
        "density": 0.08,
    },
    "nodes_loaded": 50,
}
```

### Example: Find Most Central Facility

```python
# "Which facility is most central to our logistics network?"
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10,
)

print("Top 10 most central facilities:")
for item in result['results']:
    print(f"  {item['node']['name']}: {item['score']:.4f}")
```

### Example: Find Hub Suppliers

```python
# "Which suppliers have the most connections?"
result = centrality(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    centrality_type="degree",
    top_n=10,
)
```

### Example: Weighted Centrality

```python
# "Which facility handles the most shipping volume?"
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    weight_col="volume",           # Weight by shipping volume
    top_n=5,
)
```

## connected_components()

Find groups of nodes that are connected to each other but disconnected from other groups.

### Signature

```python
from virt_graph.handlers.network import connected_components

result = connected_components(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    min_size=1,                    # Minimum component size to return
    id_column="id",
    soft_delete_column=None,
)
```

### Result Structure

```python
{
    "components": [
        {
            "component_id": 0,
            "size": 45,
            "node_ids": [1, 2, 3, ...],
            "sample_nodes": [          # First few nodes with details
                {"id": 1, "name": "Acme", ...},
                ...
            ],
        },
        {
            "component_id": 1,
            "size": 5,
            "node_ids": [46, 47, 48, 49, 50],
            "sample_nodes": [...],
        },
    ],
    "component_count": 2,
    "largest_component_size": 45,
    "isolated_nodes": 0,               # Nodes with no connections
    "nodes_loaded": 50,
}
```

### Example: Find Isolated Supplier Networks

```python
# "Are there disconnected supplier networks?"
result = connected_components(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    min_size=2,                    # Ignore singletons
)

if result['component_count'] > 1:
    print(f"Warning: {result['component_count']} disconnected networks")
    for comp in result['components']:
        print(f"  Component {comp['component_id']}: {comp['size']} suppliers")
else:
    print("All suppliers are connected")
```

## graph_density()

Calculate overall graph statistics.

### Signature

```python
from virt_graph.handlers.network import graph_density

result = graph_density(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    id_column="id",
    soft_delete_column=None,
)
```

### Result Structure

```python
{
    "nodes": 50,
    "edges": 197,
    "density": 0.0804,             # edges / possible_edges
    "avg_degree": 7.88,            # average connections per node
    "is_connected": True,          # single component?
    "components": 1,
    "diameter": 5,                 # longest shortest path (if connected)
}
```

### Example: Network Health Check

```python
result = graph_density(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
)

print(f"Network has {result['nodes']} facilities, {result['edges']} routes")
print(f"Density: {result['density']:.2%}")
print(f"Average connections per facility: {result['avg_degree']:.1f}")
print(f"Connected: {result['is_connected']}")
```

## neighbors()

Get the direct neighbors of a specific node.

### Signature

```python
from virt_graph.handlers.network import neighbors

result = neighbors(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    node_id,                       # Node to find neighbors of
    direction="both",              # "inbound", "outbound", or "both"
    id_column="id",
    soft_delete_column=None,
)
```

### Result Structure

```python
{
    "neighbors": [
        {"id": 5, "name": "Denver", "direction": "outbound", ...},
        {"id": 8, "name": "Detroit", "direction": "inbound", ...},
        ...
    ],
    "outbound_count": 3,           # Nodes this node connects TO
    "inbound_count": 5,            # Nodes that connect to THIS node
    "total_degree": 8,             # Total connections
}
```

### Example: Direct Connections

```python
# "What facilities connect directly to Chicago?"
result = neighbors(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_id=chicago_id,
    direction="both",
)

print(f"Chicago has {result['total_degree']} direct connections")
print(f"  Ships to: {result['outbound_count']} facilities")
print(f"  Receives from: {result['inbound_count']} facilities")
```

## resilience_analysis()

Analyze the impact of removing a node from the network. Identifies single points of failure.

### Signature

```python
from virt_graph.handlers.network import resilience_analysis

result = resilience_analysis(
    conn,
    nodes_table,
    edges_table,
    edge_from_col,
    edge_to_col,
    node_to_remove,                # Node ID to simulate removing
    id_column="id",
    soft_delete_column=None,
)
```

### Result Structure

```python
{
    "node_removed": 5,
    "node_removed_info": {"id": 5, "name": "Chicago Hub", ...},
    "disconnected_pairs": 156,     # Node pairs that can no longer reach each other
    "components_before": 1,
    "components_after": 3,
    "component_increase": 2,
    "isolated_nodes": 2,           # Nodes with no remaining connections
    "affected_node_count": 15,     # Nodes whose connectivity changed
    "is_critical": True,           # True if removal splits the graph
}
```

### Example: Single Point of Failure Analysis

```python
# "What happens if our Chicago hub goes offline?"
result = resilience_analysis(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_to_remove=chicago_id,
)

if result['is_critical']:
    print(f"CRITICAL: Removing {result['node_removed_info']['name']} would:")
    print(f"  - Split network into {result['components_after']} pieces")
    print(f"  - Disconnect {result['disconnected_pairs']} facility pairs")
    print(f"  - Isolate {result['isolated_nodes']} facilities completely")
else:
    print("This node is not a single point of failure")
```

### Example: Find All Critical Nodes

```python
# "Which facilities are single points of failure?"
from virt_graph.handlers.network import centrality, resilience_analysis

# Start with most central nodes (likely candidates)
central = centrality(conn, ..., centrality_type="betweenness", top_n=10)

critical_nodes = []
for item in central['results']:
    node_id = item['node']['id']
    analysis = resilience_analysis(conn, ..., node_to_remove=node_id)
    if analysis['is_critical']:
        critical_nodes.append({
            'node': item['node'],
            'disconnected_pairs': analysis['disconnected_pairs'],
        })

print(f"Found {len(critical_nodes)} critical nodes")
```

## Memory Warning

All network handlers load the **full graph** into memory. This is unavoidable for algorithms like centrality and connected components that need global visibility.

### Mitigation Strategies

1. **Check size first**:
   ```python
   result = graph_density(conn, ...)
   if result['nodes'] > 10000:
       print(f"Warning: {result['nodes']} nodes will be loaded")
   ```

2. **Use soft deletes** to exclude inactive nodes:
   ```python
   result = centrality(conn, ..., soft_delete_column="deleted_at")
   ```

3. **Consider sampling** for very large graphs (not yet implemented in VG/SQL).

## Next Steps

- [Pathfinding Handlers](pathfinding.md) - Shortest path without loading full graph
- [Traversal Handlers](traversal.md) - BFS without loading full graph
- [Ontology System](../concepts/ontology.md) - Understanding operation types
