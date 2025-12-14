# VG/SQL: Virtual Graph over SQL

**Graph queries without migration**

## The Problem

Enterprise data lives in relational SQL databases. Graph databases offer powerful query patterns—traversals, pathfinding, centrality analysis—but migrating data is cumbersome and often impractical.

## The Solution

VG/SQL ("VeeJee over Sequel") enables graph-like queries over relational data **without migration**. It combines:

1. **Ontology** in [LinkML](https://linkml.io) format that maps graph concepts to relational structures
2. **Lightweight Python handlers** for recursive traversal and graph algorithms
3. **Orchestration** via general-purpose agentic systems (e.g., Claude Code)

```
┌─────────────────────────────────────────────────────────────┐
│                     Agentic System                          │
│                   (Claude Code, etc.)                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    VG/SQL Layer                             │
│  ┌─────────────────┐    ┌─────────────────────────────┐    │
│  │    Ontology     │    │         Handlers            │    │
│  │   (LinkML +     │    │  traverse(), shortest_path()│    │
│  │  VG extensions) │    │  centrality(), neighbors()  │    │
│  └─────────────────┘    └─────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Relational Database                         │
│                   (PostgreSQL, etc.)                        │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### Complexity Classification

VG/SQL classifies graph operations by query strategy:

| Complexity | Strategy | Description |
|------------|----------|-------------|
| **GREEN** | Direct SQL | Simple joins, aggregations—no handler needed |
| **YELLOW** | Recursive handlers | Multi-hop traversals, BOM explosion |
| **RED** | Graph algorithms | Shortest path, centrality, connected components |

The ontology annotates each relationship with its complexity level, enabling the agentic system to dispatch queries appropriately.

### The Handlers

Schema-parameterized Python functions that enable full graph operations over SQL:

| Handler | Complexity | Description |
|---------|------------|-------------|
| `traverse()` | YELLOW | BFS/DFS traversal with direction control |
| `bom_explode()` | YELLOW | Bill of materials explosion with quantities |
| `shortest_path()` | RED | Dijkstra weighted shortest path |
| `all_shortest_paths()` | RED | All shortest paths between nodes |
| `centrality()` | RED | Betweenness/closeness/degree/PageRank |
| `connected_components()` | RED | Find connected subgraphs |
| `neighbors()` | RED | Direct neighbors of a node |
| `resilience_analysis()` | RED | Impact analysis of node removal |

Handlers are **schema-parameterized**—they accept table and column names as arguments, making them reusable across any relational schema.

### The Ontology

VG/SQL uses [LinkML](https://linkml.io) with custom extensions (`vg:` prefix) to define:

- **Entity classes** (TBox): Map to SQL tables via `vg:SQLMappedClass`
- **Relationship classes** (RBox): Map to foreign keys via `vg:SQLMappedRelationship`
- **Complexity annotations**: `vg:traversal_complexity` marks GREEN/YELLOW/RED

See [Ontology System](concepts/ontology.md) for details.

## Quick Start

```bash
# Install dependencies
make install

# Start PostgreSQL
make db-up

# Validate your ontology
poetry run python scripts/validate_ontology.py ontology/your_ontology.yaml
```

See [Quick Start Guide](getting-started/quickstart.md) for a complete walkthrough.

## Example: Supply Chain Domain

VG/SQL includes a supply chain proof-of-concept with 500 suppliers, 50 facilities, and complex relationships.

**YELLOW - Recursive Traversal** (Find upstream suppliers):
```python
from virt_graph.handlers.traversal import traverse

result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",
    max_depth=10,
)
```

**RED - Shortest Path** (Find optimal route):
```python
from virt_graph.handlers.pathfinding import shortest_path

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
```

See [Supply Chain Tutorial](examples/supply-chain.md) for the complete example.

## Designed for Agentic Systems

VG/SQL is built for **tools running in a loop** ([Willison, 2025](https://simonwillison.net/2025/Sep/18/agents/)). General-purpose agentic systems like Claude Code provide a complete environment with:

- **Ontology discovery**: Introspect schema, understand relationships
- **Dispatch**: Determine if handler is needed based on complexity
- **Query generation**: On-the-fly SQL or handler calls

The ontology + handlers are the contribution; the agentic system is the enabler.

## Project Structure

```
virt-graph/
├── src/virt_graph/
│   ├── handlers/          # Graph operation handlers
│   │   ├── traversal.py   # traverse(), bom_explode()
│   │   ├── pathfinding.py # shortest_path(), all_shortest_paths()
│   │   └── network.py     # centrality(), neighbors(), etc.
│   ├── ontology.py        # OntologyAccessor class
│   └── estimator.py       # Pre-flight size estimation
├── ontology/
│   ├── virt_graph.yaml    # VG metamodel (single source of truth)
│   └── *.yaml             # Domain ontologies
├── scripts/
│   └── validate_ontology.py  # Two-layer validation
└── tests/                 # Integration tests
```

## Next Steps

- [Quick Start](getting-started/quickstart.md) - Get running in 5 minutes
- [Architecture](concepts/architecture.md) - Understand the design
- [Ontology System](concepts/ontology.md) - Define your own ontology
- [Handlers Overview](handlers/overview.md) - Available graph operations
