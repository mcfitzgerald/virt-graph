# Pattern Discovery Protocol

You are starting an interactive pattern discovery session. Follow the 3-phase protocol below, pausing after each phase for human review before proceeding.

**Begin with Phase 1: GREEN Patterns.**

---

## Session Setup

**Database**: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
**Ontology**: `ontology/supply_chain.yaml` (must exist)
**Output**: `patterns/raw/{pattern_name}_{seq}.yaml`
**Template reference**: See existing patterns in `patterns/templates/`

---

## Discovery Protocol (3 Phases)

### Phase 1: GREEN Patterns (Simple SQL)

Discover direct lookup and join patterns that don't require handlers.

**What to explore**:
- Entity lookups by name, code, or ID
- One-hop FK joins (e.g., parts by supplier)
- Filtered queries with common predicates
- Aggregations (counts, sums by group)

**For each pattern, record**:
- Natural language query intent
- Tables and joins involved
- Filter parameters
- Execution time and row count

**Pause for human review.**

---

### Phase 2: YELLOW Patterns (Recursive Traversal)

Discover patterns on self-referential relationships that require `traverse()` handlers.

**What to explore**:
- Upstream traversal (follow edges backward)
- Downstream traversal (follow edges forward)
- BOM explosion (parent → children recursively)
- Where-used analysis (child → parents recursively)
- Impact analysis (what's affected if X fails?)

**Key relationships** (from ontology):
- `supplies_to`: Supplier → Supplier (tier network)
- `component_of`: Part → Part (BOM structure)

**For each pattern, record**:
- Direction (upstream/downstream)
- Max depth explored
- Path tracking approach
- Edge properties collected

**Pause for human review.**

---

### Phase 3: RED Patterns (Network Algorithms)

Discover patterns requiring NetworkX handlers for weighted graph operations.

**What to explore**:
- Shortest path (by distance, cost, or time)
- All paths between nodes
- Centrality measures (degree, betweenness, PageRank)
- Connected components (cluster detection)
- Network density and statistics

**Key relationships** (from ontology):
- `connects_to`: Facility → Facility (weighted transport network)

**For each pattern, record**:
- Algorithm type
- Weight column(s) used
- Graph size (nodes, edges)
- Performance characteristics

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

After documenting patterns:

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
