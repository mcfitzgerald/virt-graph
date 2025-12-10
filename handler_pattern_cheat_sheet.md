# Handler Pattern Cheat Sheet

Quick reference for Virtual Graph handlers. All handlers are schema-parameterized (tables/columns passed as arguments).

---

## YELLOW Handlers (Traversal)

### traverse()
Generic BFS traversal with configurable direction and stop conditions.

```python
from virt_graph.handlers import traverse

result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,
    direction="inbound",      # "outbound", "inbound", "both"
    max_depth=10,
    stop_condition="tier = 1", # SQL WHERE fragment (optional)
    include_start=False,
)
```

**Returns**: `nodes`, `paths`, `edges`, `depth_reached`, `nodes_visited`, `terminated_at`

**Direction semantics**:
| direction | meaning |
|-----------|---------|
| `outbound` | Follow edges away from start (from→to) |
| `inbound` | Follow edges toward start (to→from) |
| `both` | Follow both directions |

---

### bom_explode()
Specialized BOM traversal with quantity aggregation.

```python
from virt_graph.handlers import bom_explode

result = bom_explode(
    conn,
    start_part_id=123,
    max_depth=20,
    include_quantities=True,
)
```

**Returns**: `nodes`, `paths`, `edges`, `depth_reached`, `quantities` (dict: part_id → qty)

**Note**: Hardcoded to `parts` table and `bill_of_materials` edges.

---

### traverse_collecting()
Traverse and filter nodes matching a condition.

```python
from virt_graph.handlers import traverse_collecting

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
```

**Returns**: `matching_nodes`, `matching_paths`, `total_traversed`, `depth_reached`

---

## RED Handlers (Pathfinding)

### shortest_path()
Dijkstra shortest path with optional weights.

```python
from virt_graph.handlers import shortest_path

result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="distance_km",  # or "cost_usd", "transit_time_hours", None
    excluded_nodes=[denver_id], # optional: route around these
)
```

**Returns**: `path`, `path_nodes`, `distance`, `edges`, `nodes_explored`, `error`

**Weight options**:
| weight_col | finds |
|------------|-------|
| `"distance_km"` | Shortest distance |
| `"cost_usd"` | Cheapest route |
| `"transit_time_hours"` | Fastest route |
| `None` | Minimum hops |

---

### all_shortest_paths()
Find all optimal paths between two nodes.

```python
from virt_graph.handlers import all_shortest_paths

result = all_shortest_paths(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="distance_km",
    max_paths=5,
    excluded_nodes=[denver_id],
)
```

**Returns**: `paths`, `distance`, `path_count`, `nodes_explored`

---

## RED Handlers (Network Analysis)

### centrality()
Calculate node importance using graph algorithms.

```python
from virt_graph.handlers import centrality

result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10,
)
```

**Returns**: `results` (list of `{node, score}`), `centrality_type`, `graph_stats`, `nodes_loaded`

**Centrality types**:
| type | meaning | use case |
|------|---------|----------|
| `degree` | Connection count | Find hubs |
| `betweenness` | Bridge nodes | Find chokepoints |
| `closeness` | Average distance | Find central locations |
| `pagerank` | Importance score | Rank by influence |

---

### connected_components()
Find isolated clusters in the graph.

```python
from virt_graph.handlers import connected_components

result = connected_components(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    min_size=1,
)
```

**Returns**: `components`, `component_count`, `largest_component_size`, `isolated_nodes`

---

### neighbors()
Get direct connections of a node (1-hop).

```python
from virt_graph.handlers import neighbors

result = neighbors(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_id=chicago_id,
    direction="both",
)
```

**Returns**: `neighbors`, `outbound_count`, `inbound_count`, `total_degree`

---

### resilience_analysis()
Simulate node removal to find single points of failure.

```python
from virt_graph.handlers import resilience_analysis

result = resilience_analysis(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    node_to_remove=denver_id,
)
```

**Returns**: `node_removed`, `disconnected_pairs`, `components_before`, `components_after`, `isolated_nodes`, `is_critical`

---

### graph_density()
Get graph statistics without node details.

```python
from virt_graph.handlers import graph_density

result = graph_density(
    conn,
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
)
```

**Returns**: `nodes`, `edges`, `density`, `avg_degree`, `max_degree`, `is_connected`

---

## Safety Limits

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_DEPTH` | 50 | Maximum traversal depth |
| `MAX_NODES` | 10,000 | Maximum nodes to load |
| `MAX_RESULTS` | 1,000 | Maximum results to return |
| `QUERY_TIMEOUT_SEC` | 30 | SQL query timeout |

**Override limits**:
```python
result = traverse(..., max_nodes=50_000)       # Increase limit
result = traverse(..., skip_estimation=True)   # Bypass size check
```

**Exceptions**:
- `SubgraphTooLarge` - Estimated traversal exceeds limit
- `SafetyLimitExceeded` - Actual traversal exceeded limit

---

## Common Patterns

### Upstream suppliers (who sells TO me)
```python
traverse(..., direction="inbound")
```

### Downstream buyers (who do I sell TO)
```python
traverse(..., direction="outbound")
```

### BOM explosion (parent → children)
```python
bom_explode(conn, start_part_id=part_id)
```

### Where-used (child → parents)
```python
traverse(
    conn,
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="child_part_id",
    edge_to_col="parent_part_id",
    start_id=part_id,
    direction="outbound",
)
```

### Find chokepoints
```python
centrality(..., centrality_type="betweenness")
```

### Route avoiding a hub
```python
shortest_path(..., excluded_nodes=[hub_id])
```
