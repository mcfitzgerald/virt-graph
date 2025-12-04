---
name: virt-graph-handlers
description: >
  Generic graph operation handlers. Use for YELLOW (recursive traversal) or
  RED (network algorithms) queries. Handlers are schema-parameterized -
  provide table names, FK columns, and conditions. Groups: traversal,
  pathfinding, network-analysis.
allowed-tools: Read, Bash
---

# Generic Graph Handlers

## Overview

This skill provides access to schema-parameterized graph operation handlers. Handlers know nothing about specific domains (suppliers, parts, facilities) - they operate on generic tables and columns.

## Handler Groups

| Group | Handlers | Route | Use Case |
|-------|----------|-------|----------|
| **Traversal** | `traverse`, `traverse_collecting`, `bom_explode` | YELLOW | Recursive graph traversal |
| **Pathfinding** | `shortest_path`, `all_shortest_paths` | RED | Optimal route finding |
| **Network Analysis** | `centrality`, `connected_components`, `graph_density`, `neighbors` | RED | Graph-level analytics |

## When to Use This Skill

Invoke this skill when:
1. Query requires recursive traversal (YELLOW route)
2. Query requires network algorithms (RED route)
3. You need handler interface documentation
4. You're resolving pattern template parameters

## Instructions

### Step 1: Identify Required Handler

From pattern template or query classification:

| Query Type | Handler |
|------------|---------|
| Recursive traversal (tiers, BOM) | `traverse` |
| Find nodes matching condition | `traverse_collecting` |
| BOM with quantities | `bom_explode` |
| Optimal path (cost/distance/time) | `shortest_path` |
| Multiple equivalent paths | `all_shortest_paths` |
| Node importance | `centrality` |
| Network clusters | `connected_components` |
| Graph statistics | `graph_density` |
| Direct neighbors | `neighbors` |

### Step 2: Read Handler Interface

Read handler source for exact signature:

```bash
Read src/virt_graph/handlers/traversal.py   # traverse, traverse_collecting, bom_explode
Read src/virt_graph/handlers/pathfinding.py # shortest_path, all_shortest_paths
Read src/virt_graph/handlers/network.py     # centrality, connected_components, etc.
```

### Step 3: Resolve Parameters from Schema/Ontology

Use the schema skill to get physical table/column names:

```python
# From ontology
nodes_table = "suppliers"  # from Supplier.sql_mapping.table
edges_table = "supplier_relationships"  # from supplies_to.sql_mapping.table
edge_from_col = "seller_id"  # from supplies_to.sql_mapping.domain_key
edge_to_col = "buyer_id"  # from supplies_to.sql_mapping.range_key
```

### Step 4: Construct Handler Invocation

```python
from virt_graph.handlers.traversal import traverse

result = traverse(
    conn=db_connection,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,
    direction="inbound",
    max_depth=10,
)
```

## Parameter Resolution Flow

```
Pattern template (references ontology concepts)
        ↓
Ontology lookup (get sql_mapping from relationship)
        ↓
Schema introspection (verify tables/columns exist)
        ↓
Handler call (with resolved physical names)
```

## Resolution Example

**Query:** "All components for Turbo Encabulator"

1. **Pattern matches:** `bom_explosion`

2. **Ontology lookup:**
   - node_class: `Part` → table: `parts`
   - relationship: `component_of`
     - table: `bill_of_materials`
     - domain_key: `child_part_id`
     - range_key: `parent_part_id`

3. **Direction note:** For explosion (parent→children), swap from/to:
   - edge_from_col: `parent_part_id` (was range_key)
   - edge_to_col: `child_part_id` (was domain_key)

4. **Handler call:**
   ```python
   result = traverse(
       conn=db,
       nodes_table="parts",
       edges_table="bill_of_materials",
       edge_from_col="parent_part_id",  # swapped for outbound
       edge_to_col="child_part_id",      # swapped for outbound
       start_id=789,  # Product's top-level part
       direction="outbound",
       max_depth=20,
   )
   ```

## Safety Limits (All Handlers)

These limits are **non-negotiable** and enforced at runtime:

| Limit | Value | Purpose |
|-------|-------|---------|
| `MAX_DEPTH` | 50 | Prevent infinite recursion |
| `MAX_NODES` | 10,000 | Prevent memory exhaustion |
| `MAX_RESULTS` | 1,000 | Limit response size |
| `QUERY_TIMEOUT` | 30 seconds | Prevent runaway queries |

### Safety Exceptions

| Exception | Meaning | Action |
|-----------|---------|--------|
| `SafetyLimitExceeded` | Traversal hit depth/node limit | Add filters or reduce max_depth |
| `SubgraphTooLarge` | Estimated size exceeds MAX_NODES | Add prefilter or target_condition |

## Quick Reference

### Traversal Handlers

```python
# Generic traversal
traverse(conn, nodes_table, edges_table, edge_from_col, edge_to_col,
         start_id, direction="outbound", max_depth=10, stop_condition=None,
         collect_columns=None, prefilter_sql=None, include_start=True)

# Traversal with target filtering
traverse_collecting(conn, nodes_table, edges_table, edge_from_col, edge_to_col,
                   start_id, target_condition, direction="outbound", max_depth=10)

# BOM-specific with quantities
bom_explode(conn, start_part_id, max_depth=20, include_quantities=True)
```

### Pathfinding Handlers

```python
# Single optimal path
shortest_path(conn, nodes_table, edges_table, edge_from_col, edge_to_col,
              start_id, end_id, weight_col=None, max_depth=20)

# Multiple optimal paths
all_shortest_paths(conn, nodes_table, edges_table, edge_from_col, edge_to_col,
                   start_id, end_id, weight_col=None, max_depth=20, max_paths=10)
```

### Network Analysis Handlers

```python
# Node importance
centrality(conn, nodes_table, edges_table, edge_from_col, edge_to_col,
           centrality_type="degree", top_n=10, weight_col=None)

# Cluster detection
connected_components(conn, nodes_table, edges_table, edge_from_col, edge_to_col,
                     min_size=1)

# Graph statistics
graph_density(conn, edges_table, edge_from_col, edge_to_col, weight_col=None)

# Direct neighbors
neighbors(conn, nodes_table, edges_table, edge_from_col, edge_to_col,
          node_id, direction="both")
```

## See Also

- `patterns/SKILL.md` - Pattern templates that use these handlers
- `schema/SKILL.md` - Schema introspection for table/column names
- `handlers/reference.md` - Detailed handler documentation
