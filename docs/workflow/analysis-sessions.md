# Analysis Sessions

Analysis sessions are the interactive phase of Virtual Graph where users explore data through graph-like queries.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANALYSIS SESSION LOOP                         │
└─────────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │ User Question│
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Classify    │
                    │  Complexity  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
         ┌────────┐   ┌────────┐   ┌────────┐
         │ GREEN  │   │ YELLOW │   │  RED   │
         │  SQL   │   │traverse│   │NetworkX│
         └───┬────┘   └───┬────┘   └───┬────┘
              │            │            │
              └────────────┼────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Present    │
                    │   Results    │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Next Question│
                    └──────────────┘
```

## Starting a Session

```bash
# Start a fresh Claude session with the analysis protocol
cat prompts/analysis_session.md
```

### Session Setup

On session start, load and summarize the ontology:

```python
from virt_graph.ontology import OntologyAccessor
ontology = OntologyAccessor()
```

**Present domain summary**:

```
Domain: Supply Chain (8 entities, 13 relationships)

Entities: Supplier, Part, Product, Facility, Customer, Order, Shipment, Certification

Key Relationships:
  GREEN (simple SQL):  Provides, CanSupply, ContainsComponent, PlacedBy, ...
  YELLOW (recursive):  SuppliesTo (tier network), ComponentOf (BOM)
  RED (algorithms):    ConnectsTo (transport routes with distance/cost/time)

Ready to explore. What would you like to investigate?
```

## The Analysis Loop

For each user question, follow these steps:

### Step 1: Classify the Query

| Signal | Route | Handler |
|--------|-------|---------|
| Simple lookup, 1-2 hop join | GREEN | Direct SQL |
| "all upstream/downstream", "full BOM", recursive | YELLOW | `traverse()` |
| "shortest path", "most critical", weighted | RED | NetworkX |

**Classification keywords**:

| Keywords | Likely Route |
|----------|--------------|
| find, get, list, show | GREEN |
| all, every, entire, full | YELLOW |
| upstream, downstream | YELLOW |
| explosion, cascade, impact | YELLOW |
| shortest, fastest, cheapest | RED |
| critical, central, hub | RED |
| isolated, connected, cluster | RED |

### Step 2: Match to Pattern

Check `patterns/templates/` for applicable patterns:

| Category | Patterns |
|----------|----------|
| `traversal/` | tier_traversal, bom_explosion, where_used |
| `pathfinding/` | shortest_path, all_paths |
| `aggregation/` | impact_analysis |
| `network-analysis/` | centrality, components |

If a pattern matches, use its parameter mapping.

### Step 3: Resolve Parameters

Use the ontology to map concepts to SQL:

```python
# Entity → Table
table = ontology.get_class_table("Supplier")  # "suppliers"

# Relationship → Edge info
edge_table = ontology.get_role_table("SuppliesTo")  # "supplier_relationships"
domain_key, range_key = ontology.get_role_keys("SuppliesTo")  # ("seller_id", "buyer_id")

# Complexity
complexity = ontology.get_role_complexity("SuppliesTo")  # "YELLOW"
```

### Step 4: Execute Query

**GREEN Route** - Direct SQL:

```sql
SELECT s.* FROM suppliers s
WHERE s.name = 'Acme Corp'
AND s.deleted_at IS NULL
```

**YELLOW Route** - Traversal handler:

```python
from virt_graph.handlers.traversal import traverse

result = traverse(
    conn=conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,
    direction="inbound",
    max_depth=10
)
```

**RED Route** - Network handler:

```python
from virt_graph.handlers.pathfinding import shortest_path

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
```

### Step 5: Present Results

Format results clearly based on query type:

| Query Type | Presentation |
|------------|--------------|
| Entity lookup | Table of key attributes |
| Traversal | Count, depth reached, sample nodes |
| Path | Route with weights, total cost |
| Analysis | Rankings, insights |

**Always include**:
- Query classification (GREEN/YELLOW/RED)
- Execution time
- Result count
- Any safety limits triggered

## Safety Awareness

### Limits (Non-Negotiable)

| Limit | Value | What Happens |
|-------|-------|--------------|
| MAX_DEPTH | 50 | Traversal stops |
| MAX_NODES | 10,000 | SubgraphTooLarge raised |
| MAX_RESULTS | 1,000 | Results truncated |
| QUERY_TIMEOUT | 30s | Query cancelled |

### When Limits Trigger

If a query hits safety limits:

1. **Explain** why the limit was triggered
2. **Suggest** alternatives

**Example response**:

```
Safety limit triggered: Estimated 65,629 nodes exceeds MAX_NODES (10,000)

This BOM traversal would expand to the full parts tree. Suggestions:
1. Add depth limit: max_depth=5 (top 5 levels only)
2. Filter by category: stop_condition="category = 'electronics'"
3. Use aggregation: "How many parts at each level?" instead of full list

Which approach would you prefer?
```

## Common Analysis Patterns

### Supply Chain Questions

| Question Type | Route | Pattern |
|---------------|-------|---------|
| "Who supplies X?" | GREEN | Lookup + 1-hop |
| "All tier 3 suppliers for X" | YELLOW | tier_traversal |
| "What's affected if X fails?" | YELLOW | impact_analysis |
| "Full BOM for product X" | YELLOW | bom_explosion |
| "Where is part X used?" | YELLOW | where_used |
| "Cheapest route from A to B" | RED | shortest_path |
| "Most critical facility" | RED | centrality |

### Analysis Progressions

**Supplier Risk Analysis**:

```
1. Find the supplier (GREEN)
   → Found: Acme Corp, Tier 1, USA

2. What do they supply? (GREEN)
   → 27 parts as primary supplier

3. Who depends on them downstream? (YELLOW)
   → 4 direct customers, 12 indirect

4. What products are affected? (GREEN)
   → 8 products contain Acme-supplied parts

5. Are there alternate suppliers? (GREEN)
   → 3 of 27 parts have approved alternates
```

**Logistics Optimization**:

```
1. Current route cost (RED - shortest_path with cost)
2. Alternative routes (RED - all_paths)
3. Bottleneck facilities (RED - centrality)
4. Network connectivity (RED - components)
```

**BOM Analysis**:

```
1. Full explosion (YELLOW - may hit limits)
2. Depth-limited view (YELLOW with max_depth)
3. Leaf parts only (YELLOW with stop_condition)
4. Cost rollup (aggregation over traversal)
```

## Session Best Practices

### Do

- **Start broad, then narrow**: "Show me suppliers" → "tier 1 in USA" → "with ISO cert"
- **Use named entities**: "Acme Corp", "Turbo Encabulator", "Chicago Warehouse"
- **Ask follow-up questions**: Build on previous results
- **Request explanations**: Ask why results look a certain way

### Don't

- **Expect instant results for unbounded traversals**: Large graphs take time
- **Assume all queries need handlers**: Most queries are GREEN (simple SQL)
- **Ignore safety warnings**: They prevent system overload

## Example Conversation

```
User: "What would happen if Acme Corp went out of business?"

Claude: Let me analyze the impact of Acme Corp failing.

1. First, finding Acme Corp... (GREEN)
   → Found: Supplier #1, Tier 1, USA

2. What parts do they supply? (GREEN)
   → 27 parts as primary supplier

3. Who depends on them downstream? (YELLOW - traverse)
   → 4 direct customers, 12 indirect (tier 2-3)

4. What products would be affected? (YELLOW - impact_analysis)
   → 8 products contain Acme-supplied parts

5. Are there alternate suppliers? (GREEN)
   → 3 of 27 parts have approved alternates

Summary: Acme Corp failure would impact 8 products. 24 parts have
no approved alternate supplier - these are your critical risk areas.

Query stats: 5 queries, 0.02s total, GREEN×3, YELLOW×2

Would you like to see the specific parts without alternates?
```

## Recording New Patterns

When you discover a useful query pattern during analysis:

1. Note the query structure
2. Record it in `patterns/raw/` with:
   - Natural language intent
   - Complexity classification
   - Handler configuration (if YELLOW/RED)
   - Example parameters and results

This builds the pattern library for future sessions.

## Quick Reference

### Ontology API

```python
# Entity access
ontology.classes                     # All entity classes
ontology.get_class_table(name)       # SQL table name
ontology.get_class_pk(name)          # Primary key column

# Relationship access
ontology.roles                       # All relationships
ontology.get_role_table(name)        # Edge table
ontology.get_role_keys(name)         # (domain_key, range_key)
ontology.get_role_complexity(name)   # GREEN/YELLOW/RED
ontology.get_role_weight_columns(name)  # For RED routes
```

### Handler Quick Reference

| Handler | Import | Key Params |
|---------|--------|------------|
| `traverse` | `handlers.traversal` | direction, max_depth |
| `traverse_collecting` | `handlers.traversal` | target_condition |
| `bom_explode` | `handlers.traversal` | include_quantities |
| `shortest_path` | `handlers.pathfinding` | weight_col |
| `all_shortest_paths` | `handlers.pathfinding` | max_paths |
| `centrality` | `handlers.network` | centrality_type, top_n |
| `connected_components` | `handlers.network` | min_size |

### Complexity Decision Tree

```
Is it a simple lookup or 1-2 hop join?
├── Yes → GREEN (direct SQL)
└── No → Is it recursive/traversal?
    ├── Yes → Does it have weighted edges for optimization?
    │   ├── Yes → RED (NetworkX)
    │   └── No → YELLOW (traverse handler)
    └── No → Is it a graph algorithm (centrality, components)?
        ├── Yes → RED (NetworkX)
        └── No → GREEN (complex SQL)
```
