# Phase 3: Query Execution Paths

Phase 3 implements all three query execution routes (GREEN/YELLOW/RED) with validated handlers and pattern recordings.

## Overview

**Goal**: Working query execution for all three complexity routes

**Deliverables**:

| Deliverable | Description |
|-------------|-------------|
| `handlers/pathfinding.py` | Dijkstra shortest path via NetworkX |
| `handlers/network.py` | Centrality, connected components |
| `patterns/raw/*.yaml` | 10 raw pattern recordings |
| `tests/test_gate3_validation.py` | 32 validation tests |

## Query Routes

### GREEN Path (Simple SQL)

Direct SQL queries using ontology mappings. No handlers needed.

**Use cases**:
- Lookup by ID or name
- Simple FK joins
- Filtering and aggregation

**Example queries**:
```sql
-- Find supplier by name
SELECT * FROM suppliers WHERE name = 'Acme Corp';

-- Parts from a supplier
SELECT * FROM parts WHERE primary_supplier_id = 1;

-- Count orders by status
SELECT status, COUNT(*) FROM orders GROUP BY status;
```

**Performance**: <100ms target, actual <7ms

### YELLOW Path (Recursive Traversal)

Uses `traverse()` handler for multi-hop graph traversal.

**Use cases**:
- Supplier tier traversal (upstream/downstream)
- BOM explosion and where-used analysis
- Impact analysis for supplier failures
- Any recursive relationship traversal

**Available handlers**:

```python
from virt_graph.handlers import traverse, traverse_collecting, bom_explode

# Generic traversal
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,
    direction="inbound",  # upstream suppliers
    max_depth=10,
)

# Traverse and collect matching nodes
result = traverse_collecting(
    conn,
    ...,
    target_condition="tier = 3",  # Find all tier 3 suppliers
)

# BOM-specific with quantities
result = bom_explode(
    conn,
    start_part_id=123,
    max_depth=20,
    include_quantities=True,
)
```

**Performance**: <2s target, actual <86ms

### RED Path (Network Algorithms)

Uses NetworkX handlers for graph algorithms.

**Use cases**:
- Shortest path (cost, distance, time)
- Critical node identification (centrality)
- Network connectivity analysis
- Cluster detection

**Available handlers**:

```python
from virt_graph.handlers import (
    shortest_path,
    all_shortest_paths,
    centrality,
    connected_components,
    graph_density,
    neighbors,
)

# Dijkstra shortest path
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=1,
    end_id=25,
    weight_col="cost_usd",  # or distance_km, transit_time_hours
)

# Centrality analysis
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",  # or degree, closeness, pagerank
    top_n=10,
)

# Connected components
result = connected_components(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    min_size=1,
)
```

**Performance**: <5s target, actual <2.9s

## Handlers Reference

### Pathfinding Handlers

#### `shortest_path()`

Finds shortest path between two nodes using Dijkstra's algorithm.

```python
def shortest_path(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    end_id: int,
    weight_col: str | None = None,  # None = hop count
    max_depth: int = 20,
    id_column: str = "id",
) -> dict[str, Any]:
    """
    Returns:
        path: list of node IDs (None if no path)
        path_nodes: list of node dicts
        distance: total path weight
        edges: list of edge dicts along path
        nodes_explored: nodes loaded into graph
        error: error message if no path
    """
```

#### `all_shortest_paths()`

Finds all equally optimal paths between two nodes.

```python
def all_shortest_paths(
    conn, ...,
    max_paths: int = 10,
) -> dict[str, Any]:
    """
    Returns:
        paths: list of paths
        distance: common distance
        path_count: number found
    """
```

### Network Handlers

#### `centrality()`

Calculates node centrality scores.

```python
def centrality(
    conn: PgConnection,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    centrality_type: str = "degree",  # degree, betweenness, closeness, pagerank
    top_n: int = 10,
    weight_col: str | None = None,
    id_column: str = "id",
) -> dict[str, Any]:
    """
    Returns:
        results: list of {node, score} sorted desc
        centrality_type: type calculated
        graph_stats: nodes, edges, density, connectivity
        nodes_loaded: total nodes
    """
```

**Centrality types**:
- `degree`: Number of connections (fast, local)
- `betweenness`: Bridge nodes between clusters (slower, global)
- `closeness`: Average distance to all nodes (medium)
- `pagerank`: Importance by incoming links (medium)

#### `connected_components()`

Identifies isolated clusters in the graph.

```python
def connected_components(
    conn, ...,
    min_size: int = 1,
) -> dict[str, Any]:
    """
    Returns:
        components: list with node_ids, size, sample_nodes
        component_count: total components
        largest_component_size: biggest cluster
        isolated_nodes: nodes with no connections
    """
```

#### `graph_density()`

Calculates graph statistics without node details.

```python
def graph_density(
    conn, edges_table, edge_from_col, edge_to_col, weight_col=None
) -> dict[str, Any]:
    """
    Returns:
        nodes, edges, density, is_directed
        is_connected/is_weakly_connected
        avg_degree, max_degree, min_degree
    """
```

#### `neighbors()`

Gets direct neighbors of a node.

```python
def neighbors(
    conn, ...,
    node_id: int,
    direction: str = "both",  # outbound, inbound, both
) -> dict[str, Any]:
    """
    Returns:
        neighbors: list of node dicts
        outbound_count, inbound_count, total_degree
    """
```

## Pattern Recordings

Raw pattern recordings in `patterns/raw/` document handler usage:

| Pattern | Category | Route |
|---------|----------|-------|
| `supplier_tier_traversal_001.yaml` | n-hop-recursive | YELLOW |
| `bom_explosion_001.yaml` | bom-traversal | YELLOW |
| `where_used_001.yaml` | bom-traversal | YELLOW |
| `impact_analysis_001.yaml` | impact-analysis | YELLOW |
| `upstream_suppliers_001.yaml` | n-hop-recursive | YELLOW |
| `downstream_customers_001.yaml` | n-hop-recursive | YELLOW |
| `supply_chain_depth_001.yaml` | n-hop-recursive | YELLOW |
| `shortest_path_cost_001.yaml` | pathfinding | RED |
| `centrality_betweenness_001.yaml` | network-analysis | RED |
| `connected_components_001.yaml` | network-analysis | RED |

### Pattern Structure

```yaml
discovered: "2024-12-04"
query: "Find all tier 3 suppliers for Acme Corp"
category: n-hop-recursive
route: YELLOW

handler_used: traverse_collecting
handler_params:
  nodes_table: suppliers
  edges_table: supplier_relationships
  edge_from_col: seller_id
  edge_to_col: buyer_id
  start_id: 42
  target_condition: "tier = 3"
  direction: inbound
  max_depth: 10

ontology_bindings:
  relationship: supplies_to
  domain_class: Supplier
  range_class: Supplier
  direction_semantic: "upstream supplier chain"

result_correct: true
execution_time_ms: 45
```

## Gate 3 Validation

### Targets

| Route | Correctness | First-attempt | Latency |
|-------|-------------|---------------|---------|
| GREEN | 100% | 90% | <100ms |
| YELLOW | 90% | 70% | <2s |
| RED | 80% | 60% | <5s |

### Results

All 32 tests passed:

| Route | Queries | Correctness | Target | Actual |
|-------|---------|-------------|--------|--------|
| GREEN | 10 | 100% | <100ms | <7ms ✅ |
| YELLOW | 10 | 100% | <2s | <86ms ✅ |
| RED | 10 | 100% | <5s | <2.9s ✅ |

### Key Findings

- **Most critical facility**: New York Factory (betweenness: 0.23)
- **Network connectivity**: Fully connected (1 component, 0 isolated)
- **Cheapest Chicago→LA route**: $9,836.64 (4 hops)
- **BOM explosion**: 188 parts in 86ms

### Running Tests

```bash
# All Phase 3 tests
poetry run pytest tests/test_gate3_validation.py -v

# GREEN path only
poetry run pytest tests/test_gate3_validation.py::TestGreenPath -v

# YELLOW path only
poetry run pytest tests/test_gate3_validation.py::TestYellowPath -v

# RED path only
poetry run pytest tests/test_gate3_validation.py::TestRedPath -v
```

## Implementation Notes

### Safety Limits

All handlers enforce non-negotiable limits:

- `MAX_DEPTH = 50` - Absolute traversal depth limit
- `MAX_NODES = 10,000` - Max nodes in single operation
- `MAX_RESULTS = 1,000` - Max rows returned
- `QUERY_TIMEOUT = 30s` - Per-query timeout

### Size Estimation

The `estimate_reachable_nodes()` function samples the first 3 levels and extrapolates. This can be conservative with high branching factors - use appropriate `max_depth` values for your data.

### Graph Loading

RED path handlers use incremental loading:
- `shortest_path()` uses bidirectional search
- Only loads nodes reachable within `max_depth`
- `centrality()` loads full graph (use only for small-medium graphs)

## Next Steps

With all three query routes working, Phase 4 will implement:

1. **LLM Integration**: Route classification and query generation
2. **Pattern Learning**: Extracting patterns from successful queries
3. **End-to-end Pipeline**: Natural language → SQL/Handler → Results
