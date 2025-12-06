# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

# Start PostgreSQL database
docker-compose -f postgres/docker-compose.yml up -d

# View database logs
docker-compose -f postgres/docker-compose.yml logs -f

# Reset database (regenerate data)
docker-compose -f postgres/docker-compose.yml down -v && docker-compose -f postgres/docker-compose.yml up -d

# Regenerate seed data
poetry run python scripts/generate_data.py

# Serve documentation
poetry run mkdocs serve

# Run benchmark suite (requires Neo4j running)
docker-compose -f neo4j/docker-compose.yml up -d
poetry run python neo4j/migrate.py
poetry run python benchmark/generate_ground_truth.py
poetry run python benchmark/run.py --system both

# Check database status
docker-compose -f postgres/docker-compose.yml ps
docker-compose -f postgres/docker-compose.yml logs -f

# Start Neo4j (for benchmarking)
docker-compose -f neo4j/docker-compose.yml up -d

# View Neo4j logs
docker-compose -f neo4j/docker-compose.yml logs -f
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

The ontology (`ontology/supply_chain.yaml`) uses TBox/RBox format (Description Logic inspired, LinkML-influenced):
- **TBox (Classes)**: 8 classes - Supplier, Part, Product, Facility, Customer, Order, Shipment, SupplierCertification
- **RBox (Roles)**: 13 relationships with traversal complexity (GREEN/YELLOW/RED)

### Accessing the Ontology

Use `OntologyAccessor` from `src/virt_graph/ontology.py` for programmatic access:

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor()
table = ontology.get_class_table("Supplier")  # "suppliers"
domain_key, range_key = ontology.get_role_keys("supplies_to")  # ("seller_id", "buyer_id")
complexity = ontology.get_role_complexity("connects_to")  # "RED"
```

### Ontology Structure

```yaml
tbox:
  classes:
    Supplier:
      sql:
        table: suppliers
        primary_key: id
      slots: {...}

rbox:
  roles:
    supplies_to:
      domain: Supplier
      range: Supplier
      sql:
        table: supplier_relationships
        domain_key: seller_id
        range_key: buyer_id
      traversal_complexity: YELLOW
```

Key relationship complexities:
- **GREEN**: Simple FK joins (provides, can_supply, contains_component, etc.)
- **YELLOW**: Recursive traversal (supplies_to, component_of)
- **RED**: Network algorithms with weights (connects_to)

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

## Project Management

- Update `CHANGELOG.md` and `pyproject.toml` with semantic versioning on every commit
- Run integration tests for each phase (prefer integration over unit tests)
- Documentation lives in `docs/` - update when adding features
- Update `CLAUDE.md` if needed
- Use Claude's todo list to manage complex tasks
- Current version: see `pyproject.toml` (follows semantic versioning)
