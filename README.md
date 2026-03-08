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
poetry install                                    # Install dependencies
poetry run python scripts/validate_ontology.py --all   # Validate the reference ontology
poetry run python scripts/show_ontology.py             # View TBox/RBox definitions
```

### Database Setup

```bash
cp .env.example .env   # Configure DATABASE_URL
# Edit .env with your PostgreSQL connection string
poetry run pytest pcg_example/tests/test_db_connection.py -v  # Verify connection
```

### Prerequisites

- Poetry installed (`pip install poetry`)
- Python 3.12+
- PostgreSQL database (for live queries)
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
| Base Schema | `scm_base.yaml` | Supply chain structural patterns (abstract classes, mixins, enums) |
| Reference Ontology | `pcg_example/ontology/pcg.yaml` | PCG supply chain ontology (38 classes, 50 relationships) |
| Benchmark | `pcg_example/benchmark/` | 85 natural-language questions + category mappings |
| Handlers | `src/virt_graph/handlers/` | Graph operations (traversal, pathfinding, network) |
| Estimator | `src/virt_graph/estimator/` | Runtime estimation and safety guards |
| Neo4j Tools | `src/virt_graph/neo4j/` | Ontology-driven schema generation and PG→Neo4j data loading |

### The Virtual Twin

The ontology doesn't just map tables — it declares the **graph structure** that lives in the agentic system's reasoning. The PCG reference ontology demonstrates this with three distinct graph patterns:

| Graph Pattern | What It Is | Operation Types | Handler |
|---|---|---|---|
| **Transport network** | `route_segments` with polymorphic origin/destination across Plants, DCs, RetailLocations | `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` | Network handlers |
| **SKU alias chain** | Self-referential `skus.supersedes_sku_id` forming replacement chains | `recursive_traversal` | `traverse()` |
| **BOM hierarchy** | `formula_ingredients` linking formulas to ingredients with quantity rollup | `path_aggregation`, `hierarchical_aggregation` | `path_aggregate()` |

These declarations drive the **dispatch pattern**: the agentic system reads the ontology, sees the operation type, and knows whether to generate SQL or call a handler.

### Class Hierarchy

Domain ontologies import `scm_base.yaml` for reusable structural patterns via LinkML's native `imports:` mechanism:

| Pattern | Base Class/Mixin | Children in PCG |
|---------|------------------|-----------------|
| **Locations** | `Location` (abstract) | Plant, DistributionCenter, RetailLocation |
| **Documents** | `TransactionDocument` (abstract) | PurchaseOrder, Order, Shipment, Return, APInvoice, ARInvoice, ... |
| **Line items** | `LineItem` (abstract) | PurchaseOrderLine, OrderLine, ShipmentLine, ... |
| **Active flag** | `HasActiveFlag` (mixin) | Supplier, Ingredient, SKU, Channel, Plant, ... |
| **Display name** | `HasName` (mixin) | Supplier, Ingredient, SKU, Channel, Plant, ... |

Abstract classes and mixins live in `scm_base.yaml` — domain-agnostic and reusable. Concrete classes with VG annotations live in the domain ontology. The `OntologyAccessor` uses LinkML's `SchemaView(merge_imports=True)` to resolve inherited slots.

### Ontology Features

The metamodel (`virt_graph.yaml` v3.0) supports rich graph declarations. Here's what the PCG ontology actually uses:

| Feature | What It Does | PCG Usage |
|---------|-------------|-----------|
| **Polymorphism** | `vg:type_discriminator` resolves FKs that point to multiple table types | 5 relationships — route segments, batches, formulas, inventory |
| **Edge weights** | `vg:weight_columns` for pathfinding algorithms | `distance_km`, `transit_time_hours` on transport network |
| **Edge properties** | `vg:edge_attributes` for Property Graph style data on edges | `unit_cost`/`lead_time_days` on supplier offers, `quantity_kg` on BOM |
| **Context blocks** | `vg:context` provides domain semantics for AI query generation | All 38 classes + all 50 relationships with business logic, traversal semantics, and prompt hints |
| **State machines** | `vg:state_machine` declares lifecycle states and transitions | Orders, POs, batches, shipments, goods receipts, returns |
| **Flow config** | `vg:flow_config` declares material/financial/information flows | 10 relationships with conservation groups |
| **Axioms** | `vg:axioms` are SQL-evaluable integrity constraints | Mass balance, temporal ordering, GL balance |
| **Actions** | `vg:actions` document mutations for what-if reasoning | Production start, order fulfillment, capacity changes |
| **OWL 2 axioms** | `vg:functional`, `vg:acyclic`, etc. | SKU chain (asymmetric, irreflexive, acyclic), many functional FKs |

### Operation Types

The ontology classifies relationships by what operations they support (8 of 11 types used in PCG):

| Category | Handlers | Use Case |
|----------|----------|----------|
| **Direct** | SQL joins | Simple lookups, aggregations (47 relationships) |
| **Traversal** | `traverse()` | Recursive paths — SKU alias chains |
| **Aggregation** | `path_aggregate()` | Value rollup along paths — BOM explosion |
| **Algorithm** | `shortest_path()`, `centrality()`, etc. | Transport network analysis |
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

The ontology is the key artifact — it tells the agentic system everything it needs to answer graph questions over SQL:

```
User: "What's the shortest transport route from Plant 7 to RetailLocation 42?"

Claude reads ontology → sees RouteSegmentOrigin/Destination:
  - operation_types: [shortest_path, centrality, ...]
  - weight_columns: [distance_km, transit_time_hours]
  - type_discriminator: {column: origin_type, mapping: {plant: Plant, dc: DC, ...}}

Claude dispatches → shortest_path(conn, nodes_table="route_segments", ...)
```

No hardcoded query templates. The ontology declares what's possible; the agentic system figures out how.

- **Ontology discovery**: Introspect database schema, generate LinkML ontology via 4-round protocol
- **Dispatch**: Read operation types → SQL join or handler call
- **Context blocks**: Domain semantics (business logic, traversal hints) guide query generation
- **Polymorphism**: Type discriminators let the system resolve FKs that point to multiple table types

The ontology + handlers are the contribution; Claude Code is the enabler.

## Documentation

Documentation lives in `docs/` and covers:
- **[Architecture](docs/architecture.md)** - System design and dispatch pattern
- **[Ontology System](docs/ontology-system.md)** - How operations are classified
- **[Handlers](docs/handlers.md)** - All available graph operations
- **[Process Flows](docs/process-flows.md)** - End-to-end supply chain process flows (O2C, P2P, BOM, Network, Returns) mapped to SCOR
- **[Creating Ontologies](docs/ontology-creation.md)** - 5-phase discovery protocol
- **[VG Extensions](docs/vg-extensions.md)** - Complete metamodel annotation reference
- **[Validation](docs/validation.md)** - Three-layer validation (LinkML + VG + schema match)
- **Demos** (`pcg_example/demos/`) - Runnable scripts demonstrating ontology-driven queries
