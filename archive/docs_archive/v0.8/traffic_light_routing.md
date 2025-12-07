# Traffic Light Query Routing

Virtual Graph uses a "traffic light" system to route queries based on their complexity, ensuring each query uses the most appropriate execution strategy.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        QUERY ROUTING                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐    Simple SQL     ┌─────────────────────────────┐ │
│  │ 🟢 GREEN │ ────────────────▶ │ Direct PostgreSQL Query     │ │
│  └─────────┘                    └─────────────────────────────┘ │
│                                                                  │
│  ┌─────────┐    traverse()     ┌─────────────────────────────┐ │
│  │ 🟡 YELLOW│ ────────────────▶ │ Frontier-Batched BFS        │ │
│  └─────────┘                    └─────────────────────────────┘ │
│                                                                  │
│  ┌─────────┐    NetworkX       ┌─────────────────────────────┐ │
│  │ 🔴 RED  │ ────────────────▶ │ Graph Algorithm Handlers    │ │
│  └─────────┘                    └─────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Route Definitions

### 🟢 GREEN: Direct SQL

**Criteria**:
- Simple lookups (WHERE clause on single table)
- 1-2 hop joins with explicit foreign keys
- Aggregations on single tables
- No recursion or variable-length paths

**Execution**:
- Generate SQL directly from ontology mappings
- Execute against PostgreSQL
- Return results without handler involvement

**Examples**:
| Query | Route Reason |
|-------|--------------|
| "Find supplier Acme Corp" | Single table lookup |
| "Parts from supplier X" | One-hop FK join |
| "Products containing part Y" | Two-hop join |
| "Facilities in California" | Single table filter |

### 🟡 YELLOW: Recursive Traversal

**Criteria**:
- Variable-length paths (N-hop where N is unknown)
- Self-referential relationships (parent-child)
- Recursive patterns (BOM explosion, tier chains)
- Tree/DAG traversals

**Execution**:
- Use `traverse()` handler with frontier batching
- One query per depth level
- Apply stop conditions and depth limits
- Collect results with path information

**Examples**:
| Query | Route Reason |
|-------|--------------|
| "All tier 3 suppliers for X" | Variable-depth supplier chain |
| "Full BOM for product Y" | Recursive part hierarchy |
| "Upstream suppliers of Z" | Unknown chain length |
| "Impact if supplier fails" | Cascading dependency traversal |

### 🔴 RED: Network Algorithms

**Criteria**:
- Shortest path queries (with or without weights)
- Centrality calculations (degree, betweenness, closeness)
- Connected component analysis
- Graph metrics (density, clustering)

**Execution**:
- Load relevant subgraph into NetworkX
- Execute graph algorithm
- Return algorithm-specific results
- Respect MAX_NODES safety limit

**Examples**:
| Query | Route Reason |
|-------|--------------|
| "Cheapest route from A to B" | Weighted shortest path |
| "Most critical facility" | Betweenness centrality |
| "Isolated suppliers" | Connected components |
| "Hub facilities" | Degree centrality |

## Classification Rules

### Ontology-Based Classification

The ontology defines `traversal_complexity` for each relationship:

```yaml
relationships:
  provides:
    traversal_complexity: GREEN  # Simple FK lookup

  supplies_to:
    traversal_complexity: YELLOW  # Recursive tier chain
    is_hierarchical: true

  connects_to:
    traversal_complexity: RED  # Weighted network
    when_weighted: true
```

### Query Pattern Classification

When ontology doesn't specify, use query patterns:

| Pattern | Classification |
|---------|----------------|
| `WHERE column = value` | GREEN |
| `JOIN ... ON fk = pk` (1-2 hops) | GREEN |
| "all", "every", "entire" + hierarchy | YELLOW |
| "path", "route", "connection" | YELLOW or RED |
| "shortest", "cheapest", "optimal" | RED |
| "critical", "central", "important" | RED |

### Keyword Signals

| Keyword | Likely Route |
|---------|--------------|
| find, get, list, show | GREEN |
| all, every, entire | YELLOW |
| upstream, downstream | YELLOW |
| explosion, cascade, propagate | YELLOW |
| shortest, fastest, cheapest | RED |
| critical, central, hub | RED |
| isolated, connected, clustered | RED |

## Route Selection Process

```
┌─────────────────────────────────────────────────────────────────┐
│                    ROUTE SELECTION FLOW                          │
└─────────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │ Parse Query  │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Identify     │
                    │ Relationships│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ Ontology │ │ Keywords │ │ Pattern  │
       │ Lookup   │ │ Analysis │ │ Match    │
       └────┬─────┘ └────┬─────┘ └────┬─────┘
            │            │            │
            └────────────┼────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │ Resolve Conflicts│
              │ (prefer ontology)│
              └────────┬─────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
      ┌───────┐   ┌────────┐   ┌───────┐
      │ GREEN │   │ YELLOW │   │  RED  │
      │ SQL   │   │traverse│   │NetworkX│
      └───────┘   └────────┘   └───────┘
```

### Conflict Resolution

When multiple signals conflict, use this priority:

1. **Explicit ontology `traversal_complexity`** (highest)
2. **Query pattern match** (e.g., BOM explosion)
3. **Keyword analysis**
4. **Default to most conservative** (lowest)

"Most conservative" means:
- GREEN if query involves only known FK joins
- YELLOW if any recursion is needed
- RED if any graph algorithm is needed

## Handler Selection

### YELLOW Route Handlers

| Handler | Use When |
|---------|----------|
| `traverse()` | General recursive traversal |
| `traverse_collecting()` | Collect specific nodes during traversal |
| `bom_explode()` | BOM with quantities |

### RED Route Handlers

| Handler | Use When |
|---------|----------|
| `shortest_path()` | Find optimal route between two nodes |
| `all_shortest_paths()` | Find all equally optimal routes |
| `centrality()` | Rank nodes by importance |
| `connected_components()` | Find isolated clusters |

## Examples with Annotations

### Example 1: GREEN Query

**Query**: "Find all parts from Acme Corp"

**Analysis**:
```
Relationship: Supplier → Parts (via primary_supplier_id)
Ontology: provides relationship, traversal_complexity = GREEN
Pattern: Single FK lookup
```

**Route**: GREEN

**SQL**:
```sql
SELECT p.* FROM parts p
JOIN suppliers s ON p.primary_supplier_id = s.id
WHERE s.name = 'Acme Corp' AND p.deleted_at IS NULL
```

### Example 2: YELLOW Query

**Query**: "Find all tier 3 suppliers in Acme Corp's supply chain"

**Analysis**:
```
Relationship: Supplier ←→ Supplier (via supplier_relationships)
Ontology: supplies_to relationship, traversal_complexity = YELLOW
Pattern: "all" + hierarchical + unknown depth
Keywords: "all", "supply chain" (hierarchy signal)
```

**Route**: YELLOW

**Handler**:
```python
result = traverse(
    conn=db,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,  # Acme Corp
    direction="inbound",
    max_depth=10
)
# Filter: tier = 3
tier3 = [n for n in result["nodes"] if n["tier"] == 3]
```

### Example 3: RED Query

**Query**: "What's the cheapest shipping route from Chicago to LA?"

**Analysis**:
```
Relationship: Facility → Facility (via transport_routes)
Ontology: connects_to relationship, traversal_complexity = RED, when_weighted = true
Pattern: "cheapest" + "route"
Keywords: "cheapest" (optimization), "route" (path)
```

**Route**: RED

**Handler**:
```python
result = shortest_path(
    conn=db,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=1,  # Chicago Warehouse
    end_id=2,    # LA Distribution Center
    weight_col="cost_usd",
    max_depth=10
)
```

### Example 4: Escalation from GREEN to YELLOW

**Query**: "Products using part PRT-000100 at any level"

**Initial Analysis**:
```
Relationship: Part → Product (via product_components)
Ontology: contains_component, traversal_complexity = GREEN
```

**But wait**: "at any level" indicates BOM recursion needed!

**Revised Analysis**:
```
Pattern: "any level" = recursive BOM traversal
Escalate: GREEN → YELLOW
```

**Handler**:
```python
# First: traverse BOM to find all assemblies containing the part
where_used = traverse(
    nodes_table="parts",
    edges_table="bill_of_materials",
    edge_from_col="child_part_id",
    edge_to_col="parent_part_id",
    start_id=100,  # PRT-000100
    direction="outbound",
    max_depth=20
)

# Then: find products using any of those assemblies
products = query("""
    SELECT DISTINCT prod.*
    FROM products prod
    JOIN product_components pc ON prod.id = pc.product_id
    WHERE pc.part_id = ANY(%s)
""", [list(where_used["nodes"].keys())])
```

## Performance Targets by Route

| Route | Accuracy Target | Latency Target | First-Attempt Target |
|-------|-----------------|----------------|----------------------|
| GREEN | 100% | <100ms | 90% |
| YELLOW | 90% | <2s | 70% |
| RED | 80% | <5s | 60% |

## Common Routing Mistakes

### Mistake 1: Treating Recursive as GREEN

**Query**: "All components of product X"

**Wrong**: Simple JOIN (only gets direct components)
**Right**: YELLOW traverse (gets full BOM tree)

### Mistake 2: Using YELLOW for Simple Paths

**Query**: "Products from supplier X"

**Wrong**: YELLOW traverse (overkill)
**Right**: GREEN SQL with FK join

### Mistake 3: YELLOW Instead of RED for Optimization

**Query**: "Most efficient shipping route"

**Wrong**: YELLOW traverse (finds all routes, no optimization)
**Right**: RED shortest_path with weight column

## Debugging Route Selection

If a query routes incorrectly:

1. **Check ontology**: Does relationship have correct `traversal_complexity`?
2. **Check pattern templates**: Is there a matching template?
3. **Analyze keywords**: Are there misleading signals?
4. **Review query structure**: Is recursion actually needed?

Use explicit route hints in patterns:
```yaml
# Force specific route for known query types
patterns:
  - name: simple_lookup
    force_route: GREEN
  - name: bom_explosion
    force_route: YELLOW
  - name: shortest_path
    force_route: RED
```
