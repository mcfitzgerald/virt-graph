# Query Patterns

Pattern templates capture common graph query structures. They bind to the ontology to resolve parameters automatically and guide the LLM to correct handler selection.

## Pattern Template Structure

Each pattern template in `patterns/templates/` includes:

```yaml
name: bom_explosion
description: "Explode bill of materials to find all components"
handler: bom_explode

# When this pattern applies
applicability:
  query_signals:      # Keywords that trigger this pattern
    - "bill of materials"
    - "components for"
    - "what goes into"
  relationship_properties:
    is_recursive: true
    traversal_complexity: YELLOW

# Ontology bindings - resolve from supply_chain.yaml
ontology_bindings:
  node_class: Part
  edge_relationship: component_of

# Handler parameters
handler_params:
  max_depth: 20
  include_quantities: true
```

## Supply Chain Patterns

### Tier Traversal (YELLOW)

**Pattern:** `patterns/templates/traversal/tier_traversal.yaml`

Navigates the supplier tier hierarchy (tier 3 → tier 2 → tier 1).

| Variant | Direction | Use Case |
|---------|-----------|----------|
| `upstream_all` | inbound | Find all suppliers upstream of a company |
| `upstream_by_tier` | inbound | Find tier 3 suppliers for a company |
| `downstream_all` | outbound | Find who a supplier delivers to |
| `depth_analysis` | inbound | Measure supply chain depth |

**Query Signals:**
- "tier 1/2/3 supplier"
- "upstream supplier"
- "downstream customer"
- "supply chain depth"
- "who supplies to"

**Example:**
```
Query: "Find all tier 3 suppliers for Acme Corp"
Pattern: tier_traversal (upstream_by_tier variant)
Handler: traverse_collecting
Parameters:
  - nodes_table: suppliers
  - edges_table: supplier_relationships
  - edge_from_col: seller_id
  - edge_to_col: buyer_id
  - direction: inbound
  - target_condition: "tier = 3"
```

### BOM Explosion (YELLOW)

**Pattern:** `patterns/templates/traversal/bom_explosion.yaml`

Explodes a bill of materials to find all components recursively.

| Variant | Description |
|---------|-------------|
| `full_explosion` | All components with quantities |
| `structure_only` | Component tree without quantities |
| `depth_limited` | Only N levels deep |

**Query Signals:**
- "bill of materials"
- "BOM"
- "components for"
- "parts list"
- "what goes into"
- "explode"

**Example:**
```
Query: "Full parts list for the Turbo Encabulator"
Pattern: bom_explosion (full_explosion variant)
Handler: bom_explode
Parameters:
  - start_part_id: <resolved from product>
  - max_depth: 20
  - include_quantities: true
```

**Direction Note:**

The `ComponentOf` relationship means "child is component OF parent" (child → parent). For BOM explosion (finding all children of a parent), we traverse in the *opposite* direction:

```yaml
# Semantic: child_part_id → parent_part_id (child is component of parent)
# Explosion: parent_part_id → child_part_id (what does parent contain?)
edge_from_col: parent_part_id  # SWAPPED
edge_to_col: child_part_id     # SWAPPED
direction: outbound
```

### Where Used (YELLOW)

**Pattern:** `patterns/templates/traversal/where_used.yaml`

Finds all assemblies that contain a given part (reverse of BOM explosion).

**Query Signals:**
- "where is ... used"
- "what uses part"
- "parent assemblies"
- "impact of part"

**Example:**
```
Query: "Where is sensor XYZ used?"
Pattern: where_used
Handler: traverse
Parameters:
  - edge_from_col: child_part_id   # Normal direction
  - edge_to_col: parent_part_id
  - direction: outbound
```

### Shortest Path (RED)

**Pattern:** `patterns/templates/pathfinding/shortest_path.yaml`

Finds optimal routes through the transport network.

| Variant | Weight Column | Use Case |
|---------|---------------|----------|
| `cheapest` | `cost_usd` | Lowest shipping cost |
| `shortest_distance` | `distance_km` | Shortest physical distance |
| `fastest` | `transit_time_hours` | Quickest delivery |
| `hop_count` | (none) | Fewest intermediate stops |

**Query Signals:**
- "shortest"
- "cheapest"
- "fastest"
- "optimal route"
- "route from ... to"

**Example:**
```
Query: "Cheapest route from Chicago Warehouse to LA Distribution Center"
Pattern: shortest_path (cheapest variant)
Handler: shortest_path
Parameters:
  - nodes_table: facilities
  - edges_table: transport_routes
  - edge_from_col: origin_facility_id
  - edge_to_col: destination_facility_id
  - start_id: <Chicago ID>
  - end_id: <LA ID>
  - weight_col: cost_usd
```

### All Paths (RED)

**Pattern:** `patterns/templates/pathfinding/all_paths.yaml`

Finds all optimal routes (when multiple paths have the same cost).

**Example:**
```
Query: "All cheapest routes from Chicago to New York"
Handler: all_shortest_paths
Parameters:
  - max_paths: 10
```

### Centrality (RED)

**Pattern:** `patterns/templates/network-analysis/centrality.yaml`

Identifies critical nodes in the network.

| Type | Description |
|------|-------------|
| `degree` | Most connected nodes |
| `betweenness` | Bridge nodes on many paths |
| `closeness` | Nodes closest to all others |
| `pagerank` | Important nodes (link-weighted) |

**Query Signals:**
- "most connected"
- "critical"
- "central"
- "important"
- "hub"

**Example:**
```
Query: "Which facility is most critical to the network?"
Pattern: centrality (betweenness variant)
Handler: centrality
Parameters:
  - centrality_type: betweenness
  - top_n: 10
```

### Connected Components (RED)

**Pattern:** `patterns/templates/network-analysis/components.yaml`

Finds disconnected subgraphs.

**Query Signals:**
- "isolated"
- "disconnected"
- "clusters"
- "separate networks"

**Example:**
```
Query: "Are there any isolated facilities?"
Handler: connected_components
Parameters:
  - min_size: 1  # Find all components including singletons
```

## Pattern Matching Flow

When an LLM receives a query:

1. **Signal Matching** - Check query against `query_signals` patterns
2. **Ontology Lookup** - Resolve `node_class` and `edge_relationship`
3. **Parameter Resolution** - Map ontology properties to handler params
4. **Handler Selection** - Use `handler` or `handler_override` from variant

```
Query: "Find tier 3 suppliers for Acme Corp"
        │
        ▼
┌──────────────────────┐
│ Match: tier_traversal │  (signal: "tier 3 supplier")
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Variant: upstream_by  │  (pattern: "tier N suppliers for")
│         _tier         │
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Resolve parameters:   │
│ - nodes: suppliers    │  (from Supplier class)
│ - edges: supplier_    │  (from SuppliesTo relationship)
│         relationships │
│ - target: tier = 3    │  (from query)
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Handler:              │
│ traverse_collecting   │  (from handler_override)
└──────────────────────┘
```

## Using Patterns in Analysis

During an analysis session, the LLM:

1. Interprets the natural language query
2. Matches to appropriate pattern
3. Resolves parameters from ontology
4. Generates handler call or SQL
5. Executes and formats results

The patterns provide guardrails:
- Prevent incorrect handler usage
- Ensure safety limits are applied
- Guide parameter resolution

## Next Steps

See patterns in action:

1. [**Query Examples**](queries.md) - Step-by-step query execution
