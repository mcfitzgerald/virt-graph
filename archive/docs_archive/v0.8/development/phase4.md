# Phase 4: Pattern Maturity

Phase 4 generalizes raw patterns into reusable templates and implements skills for pattern matching and handler invocation.

## Objectives

1. **Pattern Generalization**: Convert raw patterns to parameterized templates
2. **Pattern Skill**: Enable Claude to select correct patterns for queries
3. **Handler Skill**: Enable Claude to invoke handlers with resolved parameters
4. **Skill Integration**: End-to-end: Query → Pattern → Ontology → Handler → Result

## Deliverables

### Pattern Templates

Generalized pattern templates organized by function:

```
patterns/templates/
├── traversal/
│   ├── tier_traversal.yaml    # Supply chain tier navigation
│   ├── bom_explosion.yaml     # Bill of materials expansion
│   └── where_used.yaml        # Reverse BOM analysis
├── pathfinding/
│   ├── shortest_path.yaml     # Optimal route finding
│   └── all_paths.yaml         # Multiple alternative routes
├── aggregation/
│   └── impact_analysis.yaml   # Failure impact assessment
└── network-analysis/
    ├── centrality.yaml        # Node importance measures
    └── components.yaml        # Cluster/connectivity analysis
```

### Pattern Template Structure

Each template includes:

- **name**: Pattern identifier
- **description**: What the pattern does
- **handler**: Primary handler to use
- **applicability**: Query signals and relationship properties
- **ontology_bindings**: How to map to schema
- **variants**: Different use cases with specific parameters
- **example**: Concrete instantiation example

Example from `tier_traversal.yaml`:

```yaml
name: tier_traversal
description: "Navigate supplier tiers upstream or downstream"
handler: traverse
applicability:
  query_signals:
    - "tier 1|2|3 supplier"
    - "upstream supplier"
    - "downstream customer"
ontology_bindings:
  node_class: Supplier
  edge_relationship: supplies_to
variants:
  upstream_all:
    direction: inbound
  downstream_all:
    direction: outbound
```

### Skills

Two new skills added to `.claude/skills/`:

#### Pattern Skill (`patterns/`)

- `SKILL.md` - Skill definition with:
  - Pattern directory structure
  - Pattern matching instructions
  - Query signal → pattern mapping
  - Variant selection rules
  - Parameter resolution from ontology

- `reference.md` - Comprehensive reference:
  - All 8 pattern templates documented
  - Handler mapping table
  - Pattern selection flowchart

#### Handler Skill (`handlers/`)

- `SKILL.md` - Skill definition with:
  - Handler group descriptions
  - Parameter resolution flow
  - Safety limits documentation
  - Quick reference signatures

- `reference.md` - Complete API reference:
  - Full function signatures
  - Parameter descriptions
  - Return value structures
  - Usage examples

## Pattern Matching Flow

```
1. Query arrives
   "Find all tier 3 suppliers for Acme Corp"

2. Match to pattern template
   Signal "tier" + "suppliers" → tier_traversal.yaml

3. Select variant
   "tier 3" → upstream_by_tier variant

4. Resolve from ontology
   Supplier → suppliers table
   supplies_to → supplier_relationships table

5. Construct handler call
   traverse_collecting(
     nodes_table="suppliers",
     edges_table="supplier_relationships",
     edge_from_col="seller_id",
     edge_to_col="buyer_id",
     start_id=42,
     target_condition="tier = 3",
     direction="inbound",
   )

6. Execute and return results
```

## Direction Semantics

Understanding traversal direction is critical:

### Supply Chain (supplies_to)

```
seller_id → buyer_id
(domain)    (range)

inbound  = upstream (toward raw materials)
outbound = downstream (toward assembly)
```

### BOM (component_of)

```
child_part_id → parent_part_id
(domain)         (range)

For explosion (parent→children):
  Swap from/to columns
  direction = outbound
```

### Transport (connects_to)

```
origin_facility_id → destination_facility_id
(domain)              (range)

Natural direction for route finding
```

## Pattern Categories

| Category | Patterns | Route |
|----------|----------|-------|
| Traversal | tier_traversal, bom_explosion, where_used | YELLOW |
| Pathfinding | shortest_path, all_paths | RED |
| Aggregation | impact_analysis | YELLOW |
| Network | centrality, components | RED |

## Gate 4 Validation

All 43 tests passed:

| Test Category | Tests | Result |
|--------------|-------|--------|
| Pattern Template Structure | 5 | ✅ |
| Pattern Matching | 17 | ✅ |
| Ontology Resolution | 5 | ✅ |
| End-to-End Integration | 4 | ✅ |
| Skill File Structure | 6 | ✅ |
| Gate 4 Summary | 1 | ✅ |

### Key Validations

1. **Template Structure**: All 8 templates have required fields
2. **Pattern Matching**: Queries match expected patterns
3. **Ontology Resolution**: Bindings resolve to valid parameters
4. **End-to-End**: Complete flow from query to result

## Usage Example

### Using Patterns Skill

1. Read pattern template:
   ```
   Read patterns/templates/traversal/tier_traversal.yaml
   ```

2. Match query to variant:
   - "Find all tier 3 suppliers" → `upstream_by_tier`
   - "Who supplies to X" → `upstream_all`
   - "Downstream customers" → `downstream_all`

3. Get handler parameters from ontology:
   ```yaml
   nodes_table: suppliers
   edges_table: supplier_relationships
   edge_from_col: seller_id
   edge_to_col: buyer_id
   ```

### Using Handlers Skill

1. Read handler interface:
   ```
   Read src/virt_graph/handlers/traversal.py
   ```

2. Construct invocation:
   ```python
   from virt_graph.handlers.traversal import traverse_collecting

   result = traverse_collecting(
       conn=db,
       nodes_table="suppliers",
       edges_table="supplier_relationships",
       edge_from_col="seller_id",
       edge_to_col="buyer_id",
       start_id=42,
       target_condition="tier = 3",
       direction="inbound",
       max_depth=10,
   )
   ```

## Next Steps

Phase 5 will implement the Neo4j baseline and benchmark harness for comparison.
