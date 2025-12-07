# Pattern Discovery

Pattern discovery is the second phase of the Virtual Graph workflow. It builds a library of reusable query patterns by systematically exploring the ontology space.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PATTERN DISCOVERY FLOW                        │
└─────────────────────────────────────────────────────────────────┘

    Pre-Discovery        Phase 1           Phase 2           Phase 3
    ┌──────────┐        ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Load     │   →    │ GREEN    │  →   │ YELLOW   │  →   │ RED      │
    │ Ontology │        │ Patterns │      │ Patterns │      │ Patterns │
    └──────────┘        └──────────┘      └──────────┘      └──────────┘
         │                   │                  │                 │
         ▼                   ▼                  ▼                 ▼
     Enumeration         [PAUSE]           [PAUSE]           [PAUSE]
     Checklist           Review            Review            Review

                                                                  │
                                                                  ▼
                                                            ┌──────────┐
                                                            │ MIXED    │
                                                            │ Patterns │
                                                            └──────────┘
```

## Prerequisites

- Completed ontology from Phase 1 (`ontology/{schema}.yaml`)
- Database running and accessible
- Pattern templates for reference (`patterns/templates/`)

```bash
# Start a fresh Claude session with the discovery protocol
cat prompts/pattern_discovery.md
```

## Pre-Discovery: Load Ontology

Enumerate all exploration targets from the ontology:

### TBox Classes (Entities)

List all entity classes - these are your entity exploration targets.

| Class | Table | Row Count |
|-------|-------|-----------|
| Supplier | suppliers | 500 |
| Part | parts | 5000 |
| Product | products | 100 |
| ... | ... | ... |

### RBox Classes (Relationships)

Group relationships by complexity - these are your relationship exploration targets.

| Complexity | Relationship | Edge Table |
|------------|--------------|------------|
| GREEN | Provides | parts (FK) |
| GREEN | CanSupply | approved_suppliers |
| YELLOW | SuppliesTo | supplier_relationships |
| YELLOW | ComponentOf | bill_of_materials |
| RED | ConnectsTo | transport_routes |

This enumeration becomes your **discovery checklist**.

**PAUSE**: Human reviews enumeration before exploration begins.

## Phase 1: GREEN Patterns

Discover patterns that don't require handlers - direct SQL queries.

### 1A: Entity Patterns (TBox)

For **each** entity class, discover patterns for:

| Pattern Type | Example |
|--------------|---------|
| Lookup by identifier | "Find supplier SUP-001" |
| Lookup by name | "Find supplier Acme Corp" |
| Filtered lists | "Active suppliers in USA" |
| Aggregations | "Count suppliers by country" |

### 1B: Relationship Patterns (GREEN roles)

For **each** GREEN relationship, discover patterns for:

| Pattern Type | Example |
|--------------|---------|
| Forward traversal | "Parts from supplier X" |
| Reverse traversal | "Supplier for part Y" |
| Filtered by attributes | "Active relationships only" |

### 1C: Multi-Hop Chains

Explore chains of GREEN relationships:

```
Supplier → Provides → Part → ContainsComponent → Product
```

Example: "Products containing parts from supplier X"

### Recording GREEN Patterns

```yaml
name: supplier_lookup_by_code
complexity: GREEN
description: "Find supplier by supplier code"
applicability:
  keywords: ["find", "lookup", "get"]
  intent: "Retrieve single supplier by identifier"
ontology_bindings:
  entity: Supplier
parameters:
  supplier_code:
    type: string
    description: "Supplier code (e.g., SUP-001)"
sql_template: |
  SELECT * FROM suppliers
  WHERE supplier_code = {{supplier_code}}
  AND deleted_at IS NULL
```

**PAUSE**: Human reviews GREEN patterns before proceeding.

## Phase 2: YELLOW Patterns

Discover patterns on self-referential relationships requiring traversal handlers.

### Exploration Targets

For **each** YELLOW relationship, explore:

| Pattern Type | Direction | Example |
|--------------|-----------|---------|
| Upstream traversal | Backward | "All suppliers upstream of X" |
| Downstream traversal | Forward | "All customers downstream of X" |
| Depth-limited | Either | "Tier 1-3 suppliers only" |
| Path tracking | Either | "Show supply chain path" |
| Impact analysis | Downstream | "What's affected if X fails?" |

### Handler Parameters

```python
result = traverse(
    conn=conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,
    direction="inbound",  # or "outbound"
    max_depth=10
)
```

### Recording YELLOW Patterns

```yaml
name: tier_traversal_upstream
complexity: YELLOW
description: "Find all upstream suppliers in tier network"
applicability:
  keywords: ["upstream", "suppliers", "supply chain", "tier"]
  intent: "Traverse supplier network toward sources"
ontology_bindings:
  node_class: Supplier
  edge_relationship: SuppliesTo
handler: traverse
handler_params:
  direction: inbound
  max_depth: 10
parameters:
  start_supplier_id:
    type: integer
    description: "Starting supplier ID"
  max_depth:
    type: integer
    default: 10
    description: "Maximum tiers to traverse"
```

**PAUSE**: Human reviews YELLOW patterns before proceeding.

## Phase 3: RED Patterns

Discover patterns requiring NetworkX handlers for weighted graph operations.

### Check Weight Columns

From the ontology, identify available weights:

```yaml
ConnectsTo:
  annotations:
    vg:weight_columns: '[{"name": "distance_km", "type": "decimal"},
                         {"name": "cost_usd", "type": "decimal"},
                         {"name": "transit_hours", "type": "decimal"}]'
```

### Exploration Targets

For **each** RED relationship and **each** weight column:

| Pattern Type | Example |
|--------------|---------|
| Shortest path (by distance) | "Shortest route from A to B" |
| Shortest path (by cost) | "Cheapest route from A to B" |
| Shortest path (by time) | "Fastest route from A to B" |
| All paths | "All routes between A and B" |
| Centrality (degree) | "Facilities with most connections" |
| Centrality (betweenness) | "Most critical routing hub" |
| Connected components | "Isolated facility clusters" |

### Handler Parameters

```python
# Shortest path
result = shortest_path(
    conn=conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=1,
    end_id=2,
    weight_col="cost_usd"
)

# Centrality
result = centrality(
    conn=conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10
)
```

### Recording RED Patterns

```yaml
name: cheapest_route
complexity: RED
description: "Find lowest cost shipping route between facilities"
applicability:
  keywords: ["cheapest", "lowest cost", "route", "shipping"]
  intent: "Optimize transport cost"
ontology_bindings:
  node_class: Facility
  edge_relationship: ConnectsTo
handler: shortest_path
handler_params:
  weight_col: cost_usd
parameters:
  origin_id:
    type: integer
    description: "Origin facility ID"
  destination_id:
    type: integer
    description: "Destination facility ID"
```

**PAUSE**: Human reviews RED patterns before proceeding.

## Phase 4: MIXED Patterns

Discover patterns combining multiple complexity levels.

### GREEN + YELLOW Combinations

```
Entity Lookup (GREEN) → Recursive Traversal (YELLOW)
```

Example: "Find Acme Corp, then show all their downstream customers"

### GREEN + RED Combinations

```
Entity Lookup (GREEN) → Network Algorithm (RED)
```

Example: "Find Chicago warehouse, then find cheapest route to LA"

### Recording MIXED Patterns

```yaml
name: supplier_impact_analysis
complexity: MIXED
description: "Full impact analysis for supplier failure"
steps:
  - name: lookup_supplier
    complexity: GREEN
    pattern: supplier_lookup
  - name: find_supplied_parts
    complexity: GREEN
    pattern: parts_from_supplier
  - name: traverse_downstream
    complexity: YELLOW
    pattern: downstream_customers
  - name: find_affected_products
    complexity: GREEN
    pattern: products_using_parts
```

**PAUSE**: Human reviews MIXED patterns.

## Validation Checklist

### Ontology Coverage

- [ ] Every TBox class has at least one entity lookup pattern
- [ ] Every RBox role has at least one relationship pattern
- [ ] YELLOW roles have upstream AND downstream patterns
- [ ] RED roles have patterns for each weight_column
- [ ] At least 2 multi-hop GREEN chains documented
- [ ] At least 2 cross-complexity patterns documented

### Technical Validation

- [ ] Each pattern has a unique name
- [ ] Complexity matches ontology relationship type
- [ ] Parameters are typed and documented
- [ ] SQL templates use `{{param}}` placeholders
- [ ] Handler configs reference valid functions

### Gate Tests

```bash
poetry run pytest tests/test_gate3_validation.py -v
```

## Pattern File Structure

Save discovered patterns in `patterns/raw/`:

```
patterns/
├── raw/                    # Discovered patterns
│   ├── green_001.yaml
│   ├── yellow_001.yaml
│   └── red_001.yaml
└── templates/              # Generalized templates
    ├── traversal/
    │   ├── tier_traversal.yaml
    │   └── bom_explosion.yaml
    ├── pathfinding/
    │   └── shortest_path.yaml
    └── network-analysis/
        └── centrality.yaml
```

## Quick Reference

### Available Handlers

| Handler | Complexity | Use Case |
|---------|------------|----------|
| `traverse()` | YELLOW | BFS on self-ref edges |
| `traverse_collecting()` | YELLOW | Collect matching nodes |
| `bom_explode()` | YELLOW | BOM with quantities |
| `shortest_path()` | RED | Dijkstra pathfinding |
| `all_shortest_paths()` | RED | All optimal routes |
| `centrality()` | RED | Node importance |
| `connected_components()` | RED | Cluster detection |

### Complexity Assignment

| Ontology Signal | Complexity | Handler |
|-----------------|------------|---------|
| Simple FK join | GREEN | None |
| `traversal_complexity: YELLOW` | YELLOW | `traverse()` |
| `traversal_complexity: RED` | RED | NetworkX |

## Next Steps

Once pattern discovery is complete:

1. Verify coverage against ontology enumeration
2. Run gate tests
3. Proceed to [Analysis Sessions](analysis-sessions.md)
