# Project History

Virtual Graph evolved through six development phases, from database foundation to benchmark validation. This page distills that journey into key milestones and decisions.

## Timeline Overview

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| 1 | Foundation | Database infrastructure + handler core |
| 2 | Discovery | Ontology system + schema introspection |
| 3 | Execution | All three query routes (GREEN/YELLOW/RED) |
| 4 | Patterns | Template system + skills integration |
| 5 | Baseline | Neo4j comparison + benchmark harness |
| 6 | Evaluation | Full benchmark + documentation |

---

## Phase 1: Foundation

**Goal:** Establish database infrastructure and core safety mechanisms.

### Track A: Database Infrastructure

Created a PostgreSQL-based supply chain schema for testing:

- **15 tables** with realistic enterprise patterns
- **~130K rows** of synthetic data via Faker
- Named test entities (Acme Corp, Turbo Encabulator, etc.)
- Docker Compose setup for reproducible environments

### Track B: Handler Core

Implemented non-negotiable safety infrastructure:

```python
MAX_DEPTH = 50          # Absolute traversal depth limit
MAX_NODES = 10_000      # Max nodes per operation
MAX_RESULTS = 1_000     # Max rows returned
QUERY_TIMEOUT_SEC = 30  # Per-query timeout
```

**Key Decision:** Frontier-batched BFS (one SQL query per depth level, never per node) became the mandatory traversal pattern.

### Gate 1 Validation

| Metric | Target | Result |
|--------|--------|--------|
| BOM traversal | <2s | 0.006s |
| Safety limits | Trigger correctly | Passed |
| DAG integrity | <5% back edges | 0% |

---

## Phase 2: Discovery

**Goal:** Create ontology system mapping semantic concepts to SQL.

### Ontology Architecture

Chose LinkML format with custom `vg:` extensions:

```yaml
# Entity class (TBox)
Supplier:
  instantiates: [vg:SQLMappedClass]
  annotations:
    vg:table: suppliers
    vg:primary_key: id

# Relationship class (RBox)
SuppliesTo:
  instantiates: [vg:SQLMappedRelationship]
  annotations:
    vg:edge_table: supplier_relationships
    vg:traversal_complexity: YELLOW
```

### Three-File Structure

| File | Purpose |
|------|---------|
| `virt_graph.yaml` | Metamodel defining extension types |
| `TEMPLATE.yaml` | Starter template with examples |
| `supply_chain.yaml` | Domain instance for supply chain |

### Two-Layer Validation

LinkML doesn't validate custom annotations, so we added:

1. **Layer 1:** LinkML structure validation
2. **Layer 2:** VG annotation validation via `OntologyAccessor`

### Gate 2 Validation

- 8 entity classes discovered
- 13 relationships mapped
- 100% FK integrity verified

---

## Phase 3: Query Execution

**Goal:** Implement all three query routes.

### Traffic Light Routing

| Route | Complexity | Handler |
|-------|------------|---------|
| GREEN | Simple FK join | Direct SQL |
| YELLOW | Recursive traversal | `traverse()` |
| RED | Network algorithms | NetworkX |

### Handler Implementation

**YELLOW Handlers:**
- `traverse()` - Generic BFS traversal
- `traverse_collecting()` - Traverse with target condition
- `bom_explode()` - Bill of Materials expansion

**RED Handlers:**
- `shortest_path()` - Dijkstra pathfinding
- `all_shortest_paths()` - Multiple optimal routes
- `centrality()` - Node importance metrics
- `connected_components()` - Cluster detection
- `neighbors()` - Direct neighbor lookup

### Gate 3 Validation

| Route | Accuracy | Latency Target | Actual |
|-------|----------|----------------|--------|
| GREEN | 100% | <100ms | <7ms |
| YELLOW | 100% | <2s | <86ms |
| RED | 100% | <5s | <2.9s |

---

## Phase 4: Pattern Maturity

**Goal:** Generalize raw patterns into reusable templates.

### Pattern Templates

Organized templates by function:

```
patterns/templates/
├── traversal/       # tier_traversal, bom_explosion, where_used
├── pathfinding/     # shortest_path, all_paths
├── aggregation/     # impact_analysis
└── network-analysis/ # centrality, components
```

### Skills System

Created Claude Code skills for:

- **Schema skill:** Database introspection queries
- **Pattern skill:** Query → pattern template matching
- **Handler skill:** Parameter resolution and invocation

### Pattern Matching Flow

```
Query → Match Template → Select Variant → Resolve from Ontology → Invoke Handler
```

### Gate 4 Validation

- 8 pattern templates validated
- End-to-end flow working
- 43/43 tests passed

---

## Phase 5: Baseline & Benchmark

**Goal:** Establish Neo4j comparison baseline.

### Neo4j Migration

Migrated PostgreSQL data to Neo4j:

- **29,669 nodes** across 8 labels
- **91,735 relationships** across 11 types
- Migration script: ~600 lines, ~45 seconds

### Benchmark Harness

Created systematic benchmark infrastructure:

- **25 queries** across GREEN/YELLOW/RED routes
- Ground truth generation from PostgreSQL
- Automated comparison runner

### Cypher Queries

Wrote equivalent Cypher for all benchmark queries:

```cypher
// Query 10: Find tier 3 suppliers for Acme Corp
MATCH (target:Supplier {name: $company_name})
MATCH path = (s:Supplier)-[:SUPPLIES_TO*1..10]->(target)
WHERE s.tier = 3
RETURN DISTINCT s
```

### Gate 5 Validation

- Neo4j loads successfully
- All 25 Cypher queries valid
- Benchmark runner functional

---

## Phase 6: Evaluation

**Goal:** Complete benchmark and document findings.

### Benchmark Tuning

Improved comparison logic for fair evaluation:

| Query Type | Comparison Method |
|------------|-------------------|
| Path queries | Any valid path with matching endpoints |
| Ranking queries | Top-5 overlap (40% threshold) |
| Count queries | 10% variance allowed |
| Set queries | 70% recall AND 50% precision |

### Final Results

| Metric | Target | Achieved |
|--------|--------|----------|
| Overall Accuracy | ≥85% | **92%** |
| GREEN Performance | ≤5x Neo4j | <1x |
| YELLOW Performance | ≤5x Neo4j | <1x |
| RED Performance | ≤5x Neo4j | <1x |

### Safety Limit Behavior

Five YELLOW queries correctly hit MAX_NODES:

| Query | Estimated Nodes | Behavior |
|-------|-----------------|----------|
| BOM explosion | ~65,629 | Blocked |
| Where used | ~42,931 | Blocked |
| Supplier impact | ~24,786 | Blocked |

These are **correct behaviors** - the full BOM tree exceeds safe limits.

---

## Key Architectural Decisions

### 1. Frontier Batching (Phase 1)

**Decision:** One SQL query per depth level, never per node.

**Rationale:** N queries vs N×branching_factor queries. Critical for performance.

### 2. LinkML + Custom Extensions (Phase 2)

**Decision:** Use LinkML format with `vg:` annotation namespace.

**Rationale:** Standard format with tooling, extensible for SQL mappings.

### 3. Three-Route Classification (Phase 3)

**Decision:** GREEN/YELLOW/RED based on relationship properties.

**Rationale:** Complexity determines handler selection automatically.

### 4. Improved Estimation (Phase 6)

**Decision:** Adaptive damping based on graph structure detection.

**Rationale:** Naive exponential extrapolation over-estimated DAGs.

---

## Version History

| Version | Phase | Highlights |
|---------|-------|------------|
| 0.1.0 | 1 | Database schema, safety limits |
| 0.2.0 | 2 | Ontology system, validation |
| 0.3.0 | 3 | YELLOW/RED handlers |
| 0.4.0 | 4 | Pattern templates, skills |
| 0.5.0 | 5 | Neo4j baseline, benchmark |
| 0.6.0 | 6 | Full benchmark, documentation |
| 0.7.0 | - | Estimator improvements |
| 0.8.0 | - | Configurable limits, two-layer validation |

---

## Lessons Learned

### What Worked Well

1. **Phased development** with gate validation ensured quality
2. **Safety limits** prevented runaway queries from day one
3. **Ontology abstraction** cleanly separated semantics from SQL
4. **Pattern templates** enabled consistent handler invocation

### Challenges Overcome

1. **Over-estimation** - Solved with adaptive damping in estimator
2. **LinkML validation** - Added custom Layer 2 validation
3. **Benchmark fairness** - Improved comparison logic for edge cases
4. **Direction semantics** - Documented domain/range conventions

### Future Directions

1. **Additional domains** - Beyond supply chain
2. **Query planning** - Automatic route optimization
3. **Caching** - Result caching for repeated patterns
4. **Visualization** - Graph result visualization

---

## See Also

- [Concepts Overview](../concepts/overview.md) - Project vision
- [Architecture](../concepts/architecture.md) - System design
- [API Reference](api/handlers.md) - Handler documentation
