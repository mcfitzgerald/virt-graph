# Pattern Template Reference

Comprehensive reference for all Virtual Graph pattern templates.

## Traversal Patterns

### tier_traversal

Navigate supplier tiers in the supply chain hierarchy.

**File:** `patterns/templates/traversal/tier_traversal.yaml`

**Use for:**
- Finding upstream suppliers (raw materials direction)
- Finding downstream customers (assembly direction)
- Identifying suppliers at specific tiers
- Measuring supply chain depth

**Variants:**

| Variant | Description | Direction | Key Param |
|---------|-------------|-----------|-----------|
| `upstream_all` | All suppliers toward raw materials | inbound | - |
| `upstream_by_tier` | Suppliers at specific tier | inbound | `target_condition` |
| `downstream_all` | All customers toward assembly | outbound | - |
| `depth_analysis` | Measure supply chain depth | inbound | `max_depth=20` |

**Example queries:**
- "Find all tier 3 suppliers for Acme Corp"
- "Who supplies to GlobalTech Industries?"
- "What is the depth of supply chain from X?"

**Direction semantics:**
```
supplies_to: seller_id -> buyer_id
             (domain)     (range)

inbound  = follow seller_id (upstream suppliers)
outbound = follow buyer_id (downstream customers)
```

---

### bom_explosion

Explode bill of materials to find all components recursively.

**File:** `patterns/templates/traversal/bom_explosion.yaml`

**Use for:**
- Full parts list for a product/assembly
- Component breakdown with quantities
- Manufacturing planning

**Variants:**

| Variant | Description | Handler | Key Param |
|---------|-------------|---------|-----------|
| `full_explosion` | All components with quantities | `bom_explode` | `include_quantities=true` |
| `structure_only` | Component tree without quantities | `traverse` | - |
| `depth_limited` | Only N levels deep | `traverse` | `max_depth` |

**Direction note:** The `component_of` relationship is child→parent semantically. For BOM explosion (parent→children), we **swap** the from/to columns:
```yaml
# Semantic relationship: child is component_of parent
domain_key: child_part_id
range_key: parent_part_id

# For explosion, use:
edge_from_col: parent_part_id  # SWAPPED
edge_to_col: child_part_id     # SWAPPED
direction: outbound
```

---

### where_used

Find all assemblies that use a given part (reverse BOM).

**File:** `patterns/templates/traversal/where_used.yaml`

**Use for:**
- Change impact analysis
- Part substitution planning
- Finding affected products

**Variants:**

| Variant | Description | Max Depth |
|---------|-------------|-----------|
| `all_uses` | All parent assemblies at any level | 10 |
| `direct_uses` | Only immediate parents | 1 |
| `with_products` | Include final products | Multi-step |

**Example queries:**
- "Where is part X used?"
- "What products use this component?"

---

## Pathfinding Patterns

### shortest_path

Find optimal path between two nodes.

**File:** `patterns/templates/pathfinding/shortest_path.yaml`

**Use for:**
- Cheapest shipping route
- Shortest physical distance
- Fastest transit time

**Variants:**

| Variant | Weight Column | Semantics |
|---------|---------------|-----------|
| `cheapest` | `cost_usd` | Lowest cost route |
| `shortest_distance` | `distance_km` | Shortest physical path |
| `fastest` | `transit_time_hours` | Quickest transit |
| `hop_count` | `null` | Fewest intermediate stops |

**Example queries:**
- "Cheapest route from Chicago to LA"
- "Fastest shipping path from NYC to Munich"

**Output:**
```python
{
    "path": [1, 12, 18, 25],           # Node IDs in order
    "path_nodes": [...],                # Full node details
    "distance": 2450.00,                # Total weight
    "edges": [                          # Edge details
        {"from_id": 1, "to_id": 12, "weight": 800.00},
        ...
    ]
}
```

---

### all_paths

Find multiple alternative routes between nodes.

**File:** `patterns/templates/pathfinding/all_paths.yaml`

**Use for:**
- Backup route planning
- Comparing alternatives
- Redundancy analysis

**Cautions:**
- Can be computationally expensive
- May timeout on dense graphs
- Consider `shortest_path` first to verify connectivity

---

## Aggregation Patterns

### impact_analysis

Analyze downstream impact of entity failure.

**File:** `patterns/templates/aggregation/impact_analysis.yaml`

**Use for:**
- Supplier failure risk assessment
- Part discontinuation impact
- Facility shutdown planning

**Variants:**

| Variant | Start Entity | End Impact |
|---------|--------------|------------|
| `supplier_to_products` | Supplier | Products |
| `part_to_products` | Part | Products |
| `facility_to_orders` | Facility | Orders |

**Multi-step process for supplier impact:**
1. Find parts from supplier (GREEN: simple FK)
2. Traverse BOM to find assemblies (YELLOW: where-used)
3. Find affected products (GREEN: simple join)

**Example queries:**
- "What products are affected if Acme Corp fails?"
- "Impact if part X is discontinued"

---

## Network Analysis Patterns

### centrality

Calculate node importance using various centrality measures.

**File:** `patterns/templates/network-analysis/centrality.yaml`

**Use for:**
- Identifying critical nodes
- Finding network hubs
- Risk assessment (single points of failure)

**Variants:**

| Type | Meaning | Speed | Use When |
|------|---------|-------|----------|
| `degree` | Most connections | Fast | Finding busy hubs |
| `betweenness` | Bridge between clusters | Slow | Finding chokepoints |
| `closeness` | Best average access | Medium | Optimal placement |
| `pagerank` | Importance by incoming links | Medium | Understanding flow |

**Selection guide:**
- "Most connected" → `degree`
- "Most critical" / "bottleneck" → `betweenness`
- "Best located" / "optimal" → `closeness`
- "Most influential" → `pagerank`

**Caution:** Loads entire graph into memory. Only use for graphs under 10,000 nodes.

---

### components

Find connected components in the graph.

**File:** `patterns/templates/network-analysis/components.yaml`

**Use for:**
- Network health checks
- Finding isolated nodes
- Cluster identification

**Variants:**

| Variant | Min Size | Focus |
|---------|----------|-------|
| `all_components` | 1 | All groups |
| `isolated_nodes` | 1 | Nodes with no edges |
| `significant_clusters` | 5+ | Major segments only |
| `connectivity_check` | 1 | Verify full connectivity |

**Interpretation:**
- `component_count = 1` → Fully connected network
- `component_count > 1` → Disconnected segments exist
- `isolated_nodes` list → Facilities needing routes

---

## Pattern Selection Flowchart

```
Query arrives
    │
    ├─ Mentions "tier", "upstream", "downstream"?
    │   └─ tier_traversal
    │
    ├─ Mentions "BOM", "components", "parts list"?
    │   └─ bom_explosion
    │
    ├─ Mentions "where used", "what uses"?
    │   └─ where_used
    │
    ├─ Mentions "shortest", "cheapest", "fastest", "route"?
    │   └─ shortest_path
    │
    ├─ Mentions "all routes", "alternatives"?
    │   └─ all_paths
    │
    ├─ Mentions "impact", "affected", "failure"?
    │   └─ impact_analysis
    │
    ├─ Mentions "critical", "important", "hub"?
    │   └─ centrality
    │
    └─ Mentions "isolated", "connected", "clusters"?
        └─ components
```

## Handler Mapping

| Pattern | Primary Handler | Route |
|---------|-----------------|-------|
| tier_traversal | `traverse`, `traverse_collecting` | YELLOW |
| bom_explosion | `bom_explode`, `traverse` | YELLOW |
| where_used | `traverse` | YELLOW |
| shortest_path | `shortest_path` | RED |
| all_paths | `all_shortest_paths` | RED |
| impact_analysis | `traverse` (multi-step) | YELLOW |
| centrality | `centrality` | RED |
| components | `connected_components` | RED |
