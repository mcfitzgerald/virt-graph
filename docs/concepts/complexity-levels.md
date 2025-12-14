# Complexity Levels

VG/SQL classifies every relationship by the query strategy required to traverse it. This classification enables the agentic system to dispatch queries appropriately.

## The Three Levels

| Level | Color | Strategy | When to Use |
|-------|-------|----------|-------------|
| GREEN | Simple | Direct SQL | Single-hop joins, aggregations |
| YELLOW | Recursive | `traverse()`, `bom_explode()` | Multi-hop paths, hierarchies |
| RED | Algorithm | `shortest_path()`, `centrality()` | Weighted paths, network analysis |

## GREEN: Direct SQL

**Definition**: Relationships that can be queried with standard SQL joins.

**Characteristics**:
- Single-hop (entity A directly references entity B)
- No recursion needed
- Standard SQL is optimal

**Example Relationships**:
```yaml
# Part belongs to a category (simple FK)
BelongsToCategory:
  annotations:
    vg:edge_table: parts
    vg:domain_key: category_id
    vg:range_key: id
    vg:traversal_complexity: GREEN
    vg:functional: true  # Each part has exactly one category

# Order placed by customer (simple FK)
PlacedBy:
  annotations:
    vg:edge_table: orders
    vg:domain_key: customer_id
    vg:range_key: id
    vg:traversal_complexity: GREEN
```

**Query Pattern**:
```sql
-- Question: "Which parts are in category 'Electronics'?"
SELECT p.* FROM parts p
JOIN categories c ON p.category_id = c.id
WHERE c.name = 'Electronics';
```

**When GREEN**:
- FK in entity table pointing to another entity
- Junction tables with no recursive structure
- Any relationship where you don't need to "follow the chain"

## YELLOW: Recursive Traversal

**Definition**: Relationships that require multi-hop traversal through a hierarchy or network.

**Characteristics**:
- Self-referential (entity relates to same entity type)
- Variable depth (1 hop, 5 hops, N hops)
- Path tracking needed
- Recursive CTEs possible but handlers are cleaner

**Example Relationships**:
```yaml
# Supplier sells to another supplier (supply chain network)
SuppliesTo:
  annotations:
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id
    vg:range_key: buyer_id
    vg:domain_class: Supplier
    vg:range_class: Supplier
    vg:traversal_complexity: YELLOW
    vg:asymmetric: true
    vg:acyclic: true
    vg:is_hierarchical: true

# Part contains another part (bill of materials)
ComponentOf:
  annotations:
    vg:edge_table: bill_of_materials
    vg:domain_key: child_part_id
    vg:range_key: parent_part_id
    vg:domain_class: Part
    vg:range_class: Part
    vg:traversal_complexity: YELLOW
```

**Query Pattern**:
```python
from virt_graph.handlers.traversal import traverse

# Question: "Find all upstream suppliers of Acme Corp"
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",  # Who sells TO Acme
    max_depth=10,
)
# Returns: nodes at all depths, paths to each
```

**When YELLOW**:
- Self-referential FK (table references itself)
- Org charts, category trees, BOM structures
- "Find all ancestors/descendants" queries
- Path enumeration without weights

## RED: Network Algorithms

**Definition**: Relationships requiring graph algorithms that have no SQL equivalent.

**Characteristics**:
- Weighted edges (distance, cost, time)
- Global graph analysis (centrality, components)
- Optimization (shortest path)
- Requires loading subgraph into memory

**Example Relationships**:
```yaml
# Transport route between facilities (weighted network)
ConnectsTo:
  annotations:
    vg:edge_table: transport_routes
    vg:domain_key: origin_facility_id
    vg:range_key: destination_facility_id
    vg:domain_class: Facility
    vg:range_class: Facility
    vg:traversal_complexity: RED
    vg:is_weighted: true
    vg:weight_columns: '[{"name": "distance_km", "type": "decimal"}, {"name": "cost_usd", "type": "decimal"}]'
```

**Query Patterns**:
```python
from virt_graph.handlers.pathfinding import shortest_path
from virt_graph.handlers.network import centrality

# Question: "What's the shortest route from Chicago to LA?"
result = shortest_path(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=chicago_id,
    end_id=la_id,
    weight_col="distance_km",
)

# Question: "Which facility is most central to the network?"
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

**When RED**:
- Weighted shortest path
- Centrality analysis (betweenness, closeness, PageRank)
- Connected components
- Resilience analysis (single point of failure)
- Any question requiring NetworkX algorithms

## Decision Tree

```
Is the relationship self-referential (same entity type on both ends)?
├── NO → GREEN (direct SQL join)
└── YES → Does the query need weights or global analysis?
          ├── NO → YELLOW (recursive traversal)
          └── YES → RED (network algorithm)
```

More detailed:

```
What's the question asking?
│
├── "Which X belongs to Y?" → GREEN
│   Single hop, direct FK lookup
│
├── "Find all ancestors/descendants of X" → YELLOW
│   Multi-hop traversal, no weights
│
├── "What's in the BOM for product X?" → YELLOW
│   Recursive explosion with quantities
│
├── "What's the shortest/cheapest path from A to B?" → RED
│   Weighted pathfinding
│
├── "Which node is most important?" → RED
│   Centrality analysis
│
└── "What happens if node X fails?" → RED
    Resilience analysis
```

## Complexity vs. Handler Mapping

| Complexity | Available Handlers |
|------------|-------------------|
| GREEN | None (use SQL) |
| YELLOW | `traverse()`, `traverse_collecting()`, `bom_explode()` |
| RED | `shortest_path()`, `all_shortest_paths()`, `centrality()`, `connected_components()`, `neighbors()`, `resilience_analysis()`, `graph_density()` |

## Memory Considerations

| Complexity | Memory Usage | Safety |
|------------|--------------|--------|
| GREEN | Minimal | SQL handles it |
| YELLOW | Proportional to traversal | Frontier-batched, bounded by `max_nodes` |
| RED | Full subgraph in memory | Use Estimator for pre-flight checks |

RED handlers load the entire relevant subgraph into NetworkX. For large graphs, always estimate first:

```python
from virt_graph.estimator import GraphSampler, estimate

sampler = GraphSampler(conn, "transport_routes", "origin_facility_id", "destination_facility_id")
sample = sampler.sample(start_id, depth=3)
est = estimate(sample, target_depth=10)

if est["estimated_nodes"] > 10000:
    print("Warning: Large graph, consider filtering")
```

## Ontology Annotation

Set complexity in your ontology:

```yaml
MyRelationship:
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: my_edges
    vg:domain_key: from_id
    vg:range_key: to_id
    vg:domain_class: MyEntity
    vg:range_class: MyEntity
    vg:traversal_complexity: YELLOW  # or GREEN or RED
```

The `vg:traversal_complexity` annotation is **required** for all relationship classes.

## Next Steps

- [Handlers Overview](../handlers/overview.md) - Detailed handler documentation
- [Architecture](architecture.md) - How dispatch works
- [Creating Ontologies](../ontology/creating-ontologies.md) - Define your own
