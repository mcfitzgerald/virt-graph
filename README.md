# VG/SQL: Virtual Graph over SQL

## What is VG/SQL?

**The problem**: Enterprise data lives in relational SQL databases. Graph databases offer powerful query patterns (traversals, pathfinding, centrality), but migrating data is cumbersome and often impractical.

**The solution**: VG/SQL ("VeeJee over Sequel") enables graph-like queries over relational data WITHOUT migration. It combines:

1. An **ontology** expressed in [LinkML](https://linkml.io) format that maps graph concepts to relational structures and translates 1:1 to an annotated TBox/RBox ontological structure.
2. **Lightweight Python handlers** for recursive traversal and graph algorithms filling in gaps in native SQL for graph operations.
3. **Overall orchestration and on-the-fly query generation** via general-purpose agentic systems (in this case Claude Code)

This work extends the previously introduced [virtual-ontology](https://github.com/mcfitzgerald/virtual-ontology) concept by adopting LinkML for standardized, validatable ontology definitions and adding handlers for full graph operations.

## Quick Start

```bash
make install          # Install Python dependencies
make validate-ontology  # Validate the reference ontology
make show-ontology      # View TBox/RBox definitions
```

### Prerequisites

- Poetry installed (`pip install poetry`)
- Python 3.12+
- Docker (for Neo4j benchmarking only)

## How VG/SQL Works

VG/SQL enables graph-like queries over relational data through three components:

### The Handlers (Key Contribution)

Lightweight, generic Python tools that enable full graph operations over SQL—a small price to pay for graph capabilities without migration:

| Handler | Category | Description |
|---------|----------|-------------|
| `traverse()` | Traversal | BFS/DFS with direction control |
| `path_aggregate()` | Aggregation | Aggregate values along paths (SUM/MAX/MIN/multiply) |
| `shortest_path()` | Algorithm | Dijkstra weighted shortest path |
| `all_shortest_paths()` | Algorithm | All shortest paths between nodes |
| `centrality()` | Algorithm | Betweenness/closeness/degree centrality |
| `connected_components()` | Algorithm | Find connected subgraphs |
| `neighbors()` | Algorithm | Direct neighbors of a node |
| `resilience_analysis()` | Algorithm | Impact analysis of node removal |

These handlers are easily extended or new ones created for domain-specific graph operations.

### Key Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| Metamodel | `virt_graph.yaml` | VG extensions (single source of truth for validation rules) |
| Reference Ontology | `pcg_example/ontology/pcg.yaml` | PCG supply chain ontology (38 classes, 50 relationships) |
| Handlers | `src/virt_graph/handlers/` | Graph operations (traversal, pathfinding, network) |
| Estimator | `src/virt_graph/estimator/` | Runtime estimation and safety guards |

### Metamodel Features (v3.0)

The metamodel supports advanced patterns:

| Feature | Annotation | Description |
|---------|------------|-------------|
| Composite Keys | `vg:primary_key: '["col1", "col2"]'` | Multi-column primary/foreign keys |
| AI Context | `vg:context` | Structured hints with definition, business_logic, data_quality_notes |
| Edge Filtering | `vg:sql_filter` | SQL WHERE clause for edge tables |
| Edge Properties | `vg:edge_attributes` | Property Graph style edge data |
| Polymorphism | `vg:type_discriminator` | Native YAML format for multi-class domain/range |
| Axioms | `vg:axioms` | SQL-evaluable data integrity constraints |
| State Machines | `vg:state_machine` | Lifecycle states and valid transitions |
| Flow Config | `vg:flow_config` | Material/financial flow metadata for throughput analysis |
| Actions | `vg:actions` | Semantic mutation docs for what-if reasoning |
| Scenario Params | `vg:scenario_params` | Perturbable attributes with propagation direction |

### Operation Types

The ontology classifies relationships by what operations they support:

| Category | Handlers | Use Case |
|----------|----------|----------|
| **Direct** | SQL joins | Simple lookups, aggregations |
| **Traversal** | `traverse()` | Recursive paths (supplier networks, hierarchies) |
| **Aggregation** | `path_aggregate()` | Value aggregation along paths (e.g., BOM explosion) |
| **Algorithm** | `shortest_path()`, `centrality()` | Weighted pathfinding, graph algorithms |
| **Kinetic** | Ad-hoc SQL via Claude | Flow/state/scenario analysis (handlers planned) |

### Example Handler Usage

**Recursive Traversal** (Follow SKU alias chain)
```python
result = traverse(
    conn,
    nodes_table="skus",
    edges_table="skus",
    edge_from_col="id",
    edge_to_col="supersedes_sku_id",
    start_id=sku_id,
    direction="outbound",
    max_depth=10,
)
```

**Path Aggregation - BOM Explosion**
```python
result = path_aggregate(
    conn,
    nodes_table="ingredients",
    edges_table="formula_ingredients",
    edge_from_col="formula_id",
    edge_to_col="ingredient_id",
    start_id=formula_id,
    value_col="quantity_kg",
    operation="multiply",
    max_depth=20,
)
```

**Shortest Path** (Transport network)
```python
result = shortest_path(
    conn,
    nodes_table="route_segments",
    edges_table="route_segments",
    edge_from_col="origin_id",
    edge_to_col="destination_id",
    start_id=origin_id,
    end_id=dest_id,
    weight_col="distance_km",
)
```

### Workflow (with Claude Code)

1. **Read the ontology** to understand available entities and relationships
2. **Dispatch** the question: determine if a handler is needed based on operation types
3. **Generate query on-the-fly**: Direct SQL for simple joins, handler call for traversals/algorithms
4. **Execute and return results**

All queries are generated on-the-fly by the agentic system—no hardcoded templates.

## Designed for Agentic Systems

VG/SQL is built for a new paradigm: **tools running in a loop** ([Willison, 2025](https://simonwillison.net/2025/Sep/18/agents/)). General-purpose agentic systems like **Claude Code** provide a complete environment—file access, code execution, web search, reasoning—with batteries included.

VG/SQL leverages these native capabilities:
- **Ontology discovery**: Introspect database schema, generate LinkML ontology
- **Dispatch**: Natural language question → determine if handler is needed
- **Query generation**: On-the-fly SQL or handler calls (not templates)

The ontology + handlers are the contribution; Claude Code is the enabler.

## Documentation

Serve the full documentation locally:

```bash
make serve-docs
```

Documentation covers:
- **[Architecture](docs/concepts/architecture.md)** - System design and dispatch pattern
- **[Operation Types](docs/concepts/ontology.md)** - How operations are classified
- **[Handlers](docs/handlers/overview.md)** - All available graph operations
- **[Creating Ontologies](docs/ontology/creating-ontologies.md)** - 4-round discovery protocol
- **[VG Extensions](docs/ontology/vg-extensions.md)** - Complete metamodel annotation reference
