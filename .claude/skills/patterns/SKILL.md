---
name: virt-graph-patterns
description: >
  Load SQL pattern templates for graph operations. Use when query involves
  recursive traversal, BOM explosion, tier analysis, impact analysis,
  shortest path, or centrality calculations. Patterns are grouped by
  function: traversal, pathfinding, aggregation, network-analysis.
allowed-tools: Read, Glob, Grep
---

# Virtual Graph Pattern Templates

## Overview

This skill provides access to generalized pattern templates for graph operations over relational data. Patterns encode proven approaches discovered through query sessions and validated against ground truth.

## When to Use This Skill

Invoke this skill when the user's query matches graph operation patterns:

- **Traversal patterns**: Supply chain tiers, BOM explosion, where-used analysis
- **Pathfinding patterns**: Shortest/cheapest/fastest routes between nodes
- **Aggregation patterns**: Impact analysis, dependency chains
- **Network analysis patterns**: Centrality, connectivity, clustering

## Pattern Directory Structure

```
patterns/templates/
├── traversal/
│   ├── tier_traversal.yaml    # Supply chain tier navigation
│   ├── bom_explosion.yaml     # Bill of materials expansion
│   └── where_used.yaml        # Reverse BOM (part usage)
├── pathfinding/
│   ├── shortest_path.yaml     # Optimal route finding
│   └── all_paths.yaml         # Alternative routes
├── aggregation/
│   └── impact_analysis.yaml   # Failure impact assessment
└── network-analysis/
    ├── centrality.yaml        # Node importance measures
    └── components.yaml        # Cluster/connectivity analysis
```

## Instructions

### Step 1: Identify Query Category

Match the user's query to a pattern category:

| Query Signals | Pattern Category | File |
|---------------|------------------|------|
| "tier", "upstream", "downstream", "supply chain" | Tier Traversal | `traversal/tier_traversal.yaml` |
| "BOM", "components", "parts list", "explode" | BOM Explosion | `traversal/bom_explosion.yaml` |
| "where used", "what uses", "parent assemblies" | Where-Used | `traversal/where_used.yaml` |
| "shortest", "cheapest", "fastest", "route" | Shortest Path | `pathfinding/shortest_path.yaml` |
| "all routes", "alternatives", "options" | All Paths | `pathfinding/all_paths.yaml` |
| "impact", "affected if", "failure" | Impact Analysis | `aggregation/impact_analysis.yaml` |
| "critical", "important", "central", "hub" | Centrality | `network-analysis/centrality.yaml` |
| "isolated", "clusters", "connected" | Components | `network-analysis/components.yaml` |

### Step 2: Load Pattern Template

Read the appropriate pattern template file:

```bash
# Example: For a BOM query
Read patterns/templates/traversal/bom_explosion.yaml
```

### Step 3: Select Pattern Variant

Most patterns have variants for different use cases. Choose based on query specifics:

**Tier Traversal Variants:**
- `upstream_all`: Find all upstream suppliers
- `upstream_by_tier`: Find suppliers at specific tier (e.g., tier 3)
- `downstream_all`: Find all downstream customers
- `depth_analysis`: Measure supply chain depth

**Shortest Path Variants:**
- `cheapest`: Optimize by cost_usd
- `shortest_distance`: Optimize by distance_km
- `fastest`: Optimize by transit_time_hours
- `hop_count`: Minimize intermediate stops

**Centrality Variants:**
- `degree`: Most connections (fast)
- `betweenness`: Bridge/chokepoint nodes
- `closeness`: Best average access
- `pagerank`: Influence by incoming links

### Step 4: Resolve Parameters from Ontology

Pattern templates use ontology references for parameters. Resolve them:

1. Read ontology: `ontology/supply_chain.yaml`
2. Map template variables to actual values:

```yaml
# Template reference (TBox/RBox format)
nodes_table: "{ontology.tbox.classes.Supplier.sql.table}"

# Resolved value
nodes_table: suppliers
```

### Step 5: Construct Handler Call

Use the resolved parameters to build the handler invocation:

```python
# From pattern + ontology resolution
traverse(
    conn=db,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,  # From entity lookup
    direction="inbound",
    max_depth=10,
)
```

## Pattern Matching Examples

### Example 1: Tier Analysis

**User query:** "Find all tier 3 suppliers for Acme Corp"

**Match:** `traversal/tier_traversal.yaml` → `upstream_by_tier` variant

**Why:** Query mentions "tier 3" and "suppliers" which matches tier traversal pattern

**Handler:** `traverse_collecting` with `target_condition="tier = 3"`

### Example 2: BOM Explosion

**User query:** "Show me all components for the Turbo Encabulator"

**Match:** `traversal/bom_explosion.yaml` → `full_explosion` variant

**Why:** Query asks for "components" of a product

**Handler:** `bom_explode` with product's top-level part ID

### Example 3: Optimal Route

**User query:** "What's the cheapest way to ship from Chicago to LA?"

**Match:** `pathfinding/shortest_path.yaml` → `cheapest` variant

**Why:** Query asks for "cheapest" route between locations

**Handler:** `shortest_path` with `weight_col="cost_usd"`

### Example 4: Critical Node

**User query:** "Which facility is most critical to our network?"

**Match:** `network-analysis/centrality.yaml` → `betweenness` variant

**Why:** "Critical" suggests bottleneck identification

**Handler:** `centrality` with `centrality_type="betweenness"`

## Tie-Breaking Rules

When multiple patterns could match:

1. **Highest success_rate wins** - More reliable patterns preferred
2. **Lowest priority number wins** - More specific patterns first
3. **Most specific query signals win** - Exact match > partial match
4. **Ask for clarification** if still ambiguous

## Common Pitfalls

1. **Direction confusion in BOM:**
   - `component_of` is child→parent semantically
   - For explosion (parent→children), swap from/to columns

2. **Supply chain direction:**
   - `inbound` = upstream (toward raw materials)
   - `outbound` = downstream (toward assembly)

3. **Centrality selection:**
   - "Most connected" → degree
   - "Most critical" → betweenness
   - "Best located" → closeness

## See Also

- `handlers/SKILL.md` - Handler interfaces and parameters
- `schema/SKILL.md` - Schema introspection for entity lookups
- `ontology/supply_chain.yaml` - Relationship definitions
