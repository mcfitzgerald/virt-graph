# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Management

- Commit and push changes at logical points (e.g., completed a phase, changed functionality, etc)
- Update `CHANGELOG.md` and `pyproject.toml` with semantic versioning on every commit
- Run integration tests for new code components (prefer integration over unit tests)
- Update tests when code changes and new test added
- Create and maintain robust documentation using mkdocs. Documentation lives in `docs/` - review frequently and update when comitting
- Update `CLAUDE.md` if needed
- Use Claude's todo list to manage complex tasks
- Current version: see `pyproject.toml` (follows semantic versioning)

## Development Commands

```bash
# Environment setup
poetry install

# Add dependencies
poetry add <package>

# Run Python in project environment
poetry run python <script.py>

# Run tests
poetry run pytest

# Run single test
poetry run pytest tests/test_file.py::test_function -v

# Makefile shortcuts (recommended)
make help                 # Show all available commands
make test                 # Run all tests
make test-gate1           # Run Gate 1 tests
make test-gate2           # Run Gate 2 tests (ontology)
make db-up                # Start PostgreSQL
make db-down              # Stop PostgreSQL
make db-reset             # Reset database (regenerate data)
make db-logs              # View database logs
make neo4j-up             # Start Neo4j (for benchmarking)
make neo4j-down           # Stop Neo4j
make neo4j-logs           # View Neo4j logs
make serve-docs           # Serve documentation locally
make validate-ontology    # Full two-layer validation
make validate-linkml      # Layer 1 only (LinkML structure)
make validate-vg          # Layer 2 only (VG annotations)
make show-ontology        # Show TBox/RBox definitions
make show-tbox            # Show entity classes only
make show-rbox            # Show relationships only
make gen-jsonschema       # Generate JSON-Schema from ontology

# Database (raw commands)
docker-compose -f postgres/docker-compose.yml up -d      # Start PostgreSQL
docker-compose -f postgres/docker-compose.yml logs -f    # View logs
docker-compose -f postgres/docker-compose.yml down -v && docker-compose -f postgres/docker-compose.yml up -d  # Reset

# Regenerate seed data
poetry run python scripts/generate_data.py

# Run benchmark suite (requires Neo4j running)
docker-compose -f neo4j/docker-compose.yml up -d
poetry run python neo4j/migrate.py
poetry run python benchmark/generate_ground_truth.py
poetry run python benchmark/run.py --system both

# Archive benchmark results before fresh runs
./scripts/archive_benchmark.sh
```

## Project Overview

Virtual Graph enables graph-like queries over enterprise relational data without migrating to a graph database. The system uses an LLM to reason over SQL using a discovered ontology and learned SQL patterns.

## Architecture

The system routes queries through three paths based on complexity:

- **GREEN**: Simple SQL - direct lookups/joins, no handlers needed
- **YELLOW**: Recursive traversal - uses `traverse()` handler with frontier-batched BFS
- **RED**: Network algorithms - uses NetworkX handlers for pathfinding/centrality

Key components in `src/virt_graph/`:
- `handlers/base.py` - Safety limits, frontier batching utilities, exceptions
- `handlers/traversal.py` - Generic BFS traversal, schema-parameterized
- `handlers/pathfinding.py` - Dijkstra shortest path via NetworkX
- `handlers/network.py` - Centrality, connected components
- `estimator/` - Graph size estimation and runtime guards

## Session Prompts

Three-phase workflow session starters in `prompts/`:
- `ontology_discovery.md` - Database introspection and ontology creation
- `pattern_discovery.md` - Query pattern exploration and recording
- `analysis_session.md` - Interactive data analysis with ontology

Start a fresh Claude session with: `cat prompts/analysis_session.md`

## Handlers

Available handlers for graph operations:

**YELLOW (Recursive Traversal)**:
- `traverse(conn, nodes_table, edges_table, edge_from_col, edge_to_col, start_id, direction, max_depth, max_nodes, skip_estimation, estimation_config)` - Generic BFS traversal
- `traverse_collecting(conn, ..., target_condition)` - Traverse and collect nodes matching condition
- `bom_explode(conn, start_part_id, max_depth, include_quantities, max_nodes, skip_estimation, estimation_config)` - BOM explosion with quantities

**Configurable Limits** (new in v0.8.0):
- `max_nodes` - Override default 10,000 node limit per-call
- `skip_estimation` - Bypass size check (caller takes responsibility)
- `estimation_config` - Fine-tune estimation parameters (damping, margins)

**RED (Network Algorithms)**:
- `shortest_path(conn, nodes_table, edges_table, ..., start_id, end_id, weight_col)` - Dijkstra shortest path
- `all_shortest_paths(conn, ..., max_paths)` - Find all optimal routes
- `centrality(conn, ..., centrality_type, top_n)` - Degree/betweenness/closeness/PageRank
- `connected_components(conn, ..., min_size)` - Find graph clusters
- `graph_density(conn, edges_table, ...)` - Network statistics
- `neighbors(conn, ..., node_id, direction)` - Direct neighbor lookup

## Patterns

**Raw patterns** in `patterns/raw/` - discovered query patterns with recorded parameters.

**Pattern templates** in `patterns/templates/` - generalized, reusable patterns:
- `traversal/` - tier_traversal, bom_explosion, where_used
- `pathfinding/` - shortest_path, all_paths
- `aggregation/` - impact_analysis
- `network-analysis/` - centrality, components

Each template includes applicability signals, ontology bindings, variants, and examples.

## Estimator Module

The estimator module (`src/virt_graph/estimator/`) provides intelligent graph size estimation:

```python
from virt_graph.estimator import GraphSampler, estimate, EstimationConfig, check_guards

# Sample graph and detect properties
sampler = GraphSampler(conn, "bill_of_materials", "parent_part_id", "child_part_id")
sample = sampler.sample(start_id, depth=5)

# Estimate with adaptive damping
est = estimate(sample, max_depth=20, table_bound=5000)

# Check guards for safe traversal
result = check_guards(sample, max_depth=20, max_nodes=10000)
if result.safe_to_proceed:
    # proceed with traversal
    pass
```

Key features:
- **Auto-detection**: Detects convergence, growth trends, hub nodes from sampling
- **Adaptive damping**: Reduces over-estimation for DAGs with node sharing
- **Table bounds**: Caps estimates using DDL-derived node counts
- **Runtime guards**: Recommends action (traverse, abort, switch to NetworkX)

## Critical Implementation Rules

- **Frontier batching mandatory**: One SQL query per depth level, never per node
- **Size guards**: Check before NetworkX load; >5K nodes must warn or fail
- **Hybrid SQL/Python**: Python orchestrates traversal, SQL filters; never bulk load entire tables
- **Safety limits are non-negotiable**: MAX_DEPTH=50, MAX_NODES=10,000, MAX_RESULTS=1,000, QUERY_TIMEOUT=30s
- **Configurable limits**: Handlers accept `max_nodes`, `skip_estimation`, `estimation_config` for overrides

## Database

PostgreSQL 14 with supply chain schema (15 tables, ~130K rows):
- Connection: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
- Key tables: suppliers, supplier_relationships, parts, bill_of_materials, facilities, transport_routes

Named test entities for queries:
- Suppliers: "Acme Corp", "GlobalTech Industries", "Pacific Components"
- Products: "Turbo Encabulator" (TURBO-001), "Flux Capacitor" (FLUX-001)
- Facilities: "Chicago Warehouse" (FAC-CHI), "LA Distribution Center" (FAC-LA)

## Ontology

The ontology uses **LinkML format with Virtual Graph extensions**. Three files work together:

```
ontology/
  virt_graph.yaml     # Metamodel - defines SQLMappedClass, SQLMappedRelationship
  TEMPLATE.yaml       # Template - copy to create new domain ontologies
  supply_chain.yaml   # Instance - the supply chain domain ontology
```

| File | Purpose | When to Use |
|------|---------|-------------|
| `virt_graph.yaml` | Defines extension types and available annotations | Reference for annotation meanings |
| `TEMPLATE.yaml` | Commented examples of all annotation patterns | Copy when creating new ontology |
| `supply_chain.yaml` | Actual domain ontology | Load via `OntologyAccessor` |

**Supply Chain Ontology Summary:**
- **Entity Classes (TBox)**: 8 classes - Supplier, Part, Product, Facility, Customer, Order, Shipment, SupplierCertification
- **Relationship Classes (RBox)**: 13 relationships with traversal complexity (GREEN/YELLOW/RED)

View current definitions: `make show-ontology` (or `make show-tbox` / `make show-rbox`)

### Ontology Validation

Two-layer validation is required:

```bash
# Layer 1: LinkML structure (YAML syntax, schema structure)
poetry run linkml-lint --validate-only ontology/supply_chain.yaml

# Layer 2: VG annotations (required fields, valid references)
poetry run python -c "from virt_graph.ontology import OntologyAccessor; OntologyAccessor()"

# Both layers at once
make validate-ontology
```

### Accessing the Ontology

Use `OntologyAccessor` from `src/virt_graph/ontology.py` for programmatic access:

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor()  # Validates on load by default
table = ontology.get_class_table("Supplier")  # "suppliers"
domain_key, range_key = ontology.get_role_keys("SuppliesTo")  # ("seller_id", "buyer_id")
complexity = ontology.get_role_complexity("ConnectsTo")  # "RED"

# Also supports snake_case aliases for backward compatibility
ontology.get_role_keys("supplies_to")  # Same as "SuppliesTo"
```

### Ontology Structure (LinkML Format)

```yaml
classes:
  # Entity class (TBox) - uses vg:SQLMappedClass
  Supplier:
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: suppliers
      vg:primary_key: id
      vg:identifier: "[supplier_code]"
      vg:row_count: 500
    attributes:
      name:
        range: string
        required: true

  # Relationship class (RBox) - uses vg:SQLMappedRelationship
  SuppliesTo:
    instantiates:
      - vg:SQLMappedRelationship
    annotations:
      vg:edge_table: supplier_relationships
      vg:domain_key: seller_id
      vg:range_key: buyer_id
      vg:domain_class: Supplier
      vg:range_class: Supplier
      vg:traversal_complexity: YELLOW
      vg:acyclic: true
```

Key relationship complexities:
- **GREEN**: Simple FK joins (Provides, CanSupply, ContainsComponent, etc.)
- **YELLOW**: Recursive traversal (SuppliesTo, ComponentOf)
- **RED**: Network algorithms with weights (ConnectsTo)

## Skills

Claude Code skills in `.claude/skills/`:
- `schema/` - Schema introspection queries and skill definition
- `patterns/` - Pattern template matching and selection
- `handlers/` - Handler invocation and parameter resolution

Use skills to:
1. Match queries to pattern templates (`patterns/SKILL.md`)
2. Resolve parameters from ontology
3. Invoke handlers with resolved parameters (`handlers/SKILL.md`)

## MCP Integration

Always use Context7 MCP tools (`resolve-library-id` → `get-library-docs`) when generating code, configuration, or needing library documentation.

## Testing

Gate validation tests in `tests/`:
- `test_gate1_validation.py` - Database and core handler tests
- `test_gate2_validation.py` - Ontology and traversal tests
- `test_gate3_validation.py` - Pattern matching tests
- `test_gate4_validation.py` - Pathfinding and network tests
- `test_gate5_validation.py` - Benchmark infrastructure tests
- `test_estimator.py` - Graph estimator and guards tests

Run specific test: `poetry run pytest tests/test_gate1_validation.py::test_bom_traversal -v`


