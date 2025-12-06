# Pattern Discovery Protocol

You are starting an interactive pattern discovery session. Your goal is to explore the database and ontology to discover query patterns, achieving near-exhaustive coverage of the ontological space.

**Begin with Pre-Discovery: Load and enumerate the ontology.**

---

## Session Setup

**Database**: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
**Ontology**: `ontology/supply_chain.yaml` (must exist)
**Output**: `patterns/raw/{pattern_name}_{seq}.yaml`
**Template reference**: See existing patterns in `patterns/templates/`

---

## Pre-Discovery: Load Ontology

Read `ontology/supply_chain.yaml` and enumerate:

1. **All TBox classes** - These are your entity exploration targets
2. **All RBox roles grouped by complexity** - These are your relationship exploration targets
   - GREEN roles → Phase 1 (simple SQL)
   - YELLOW roles → Phase 2 (recursive traversal)
   - RED roles → Phase 3 (network algorithms)

Present your enumeration as a table. This becomes your discovery checklist.

**Pause for human review before proceeding.**

---

## Discovery Protocol (4 Phases)

### Phase 1: GREEN Patterns (Simple SQL)

Discover patterns that don't require handlers.

**1A. Entity Patterns (TBox exploration)**

For EACH class in TBox, discover patterns for:
- Lookup by identifier (the `identifier` field in ontology)
- Lookup by name/description
- Filtered lists with common predicates from slots
- Aggregations (counts, sums by relevant groupings)

**1B. Relationship Patterns (RBox GREEN roles)**

For EACH role where `traversal_complexity: GREEN`, discover patterns for:
- Forward traversal (domain → range)
- Reverse traversal (range → domain)
- Filtered by `additional_columns` if present

**1C. Multi-Hop Chains**

Explore chains of GREEN roles that form common query paths (e.g., entity → relationship → entity → relationship).

**For each pattern, record**:
- Natural language query intent
- Tables and joins involved
- Filter parameters
- Execution time and row count

**Pause for human review.**

---

### Phase 2: YELLOW Patterns (Recursive Traversal)

Discover patterns on self-referential relationships that require `traverse()` handlers.

For EACH role where `traversal_complexity: YELLOW`, explore:
- Upstream traversal (follow edges backward toward sources)
- Downstream traversal (follow edges forward toward targets)
- Depth-limited queries (max_depth parameter)
- Path tracking (record traversal path)
- Impact analysis (what's affected if X fails?)

**For each pattern, record**:
- Direction (upstream/downstream)
- Max depth explored
- Path tracking approach
- Edge properties collected

**Pause for human review.**

---

### Phase 3: RED Patterns (Network Algorithms)

Discover patterns requiring NetworkX handlers for weighted graph operations.

For EACH role where `traversal_complexity: RED`, explore:
- Check `weight_columns` in ontology for available metrics
- Shortest path by each weight (distance, cost, time)
- All paths between nodes
- Centrality measures (degree, betweenness, PageRank)
- Connected components (cluster detection)
- Network density and statistics

**For each pattern, record**:
- Algorithm type
- Weight column(s) used
- Graph size (nodes, edges)
- Performance characteristics

**Pause for human review.**

---

### Phase 4: MIXED Patterns (Cross-Complexity)

Discover patterns that combine GREEN lookups with YELLOW/RED traversals.

**GREEN + YELLOW combinations**:
- Start from entity lookup → recursive traversal
- Filter traversal results by entity attributes

**GREEN + RED combinations**:
- Entity lookup → network algorithm
- Combine pathfinding with entity filters

**For each pattern, record**:
- Entry point (which GREEN pattern)
- Traversal/algorithm (which YELLOW/RED pattern)
- Combined query intent

**Pause for human review.**

---

## Pattern Documentation

For each discovered pattern, create a YAML file in `patterns/raw/`.

**Required fields**:
| Field | Description |
|-------|-------------|
| `name` | Pattern identifier |
| `complexity` | GREEN, YELLOW, or RED |
| `description` | What this pattern does |
| `applicability.keywords` | Query keywords that match |
| `applicability.intent` | User intent description |
| `ontology_bindings` | Classes and roles used |
| `parameters` | Input parameters with types |
| `sql_template` | Parameterized SQL (GREEN) or handler config (YELLOW/RED) |
| `handler` | Handler name and params (YELLOW/RED only) |

See `patterns/templates/` for full examples.

---

## Validation Checklist

### Ontology Coverage (verify against your enumeration)
- [ ] Every TBox class has at least one entity lookup pattern
- [ ] Every RBox role has at least one relationship pattern
- [ ] YELLOW roles have upstream AND downstream patterns
- [ ] RED roles have patterns for each weight_column
- [ ] At least 2 multi-hop GREEN chains documented
- [ ] At least 2 cross-complexity patterns documented

### Technical Validation
- [ ] Each pattern has a unique name
- [ ] Complexity matches the relationship type in ontology
- [ ] Parameters are typed and documented
- [ ] SQL templates use `{{param}}` placeholders
- [ ] Handler configs reference valid handler functions
- [ ] Gate tests pass: `poetry run pytest tests/test_gate3_validation.py -v`

---

## Quick Reference

### Complexity Assignment
| Ontology Signal | Complexity | Handler |
|-----------------|------------|---------|
| Simple FK join | GREEN | None |
| `traversal_complexity: YELLOW` | YELLOW | `traverse()` |
| `traversal_complexity: RED` | RED | NetworkX |

### Available Handlers
| Handler | Use Case |
|---------|----------|
| `traverse()` | BFS traversal on self-ref edges |
| `traverse_collecting()` | Traverse and collect matching nodes |
| `bom_explode()` | BOM with quantities |
| `shortest_path()` | Dijkstra pathfinding |
| `centrality()` | Degree/betweenness/PageRank |
| `connected_components()` | Cluster detection |

### Template Categories
| Category | Location |
|----------|----------|
| Traversal | `patterns/templates/traversal/` |
| Pathfinding | `patterns/templates/pathfinding/` |
| Aggregation | `patterns/templates/aggregation/` |
| Network | `patterns/templates/network-analysis/` |
