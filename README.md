# Virtual Graph

**Graph-like queries over relational data using LLM reasoning**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 14+](https://img.shields.io/badge/postgresql-14+-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Virtual Graph enables graph-like queries over enterprise relational data **without migrating to a graph database**. Query your existing PostgreSQL data using natural language—find supply chain tiers, explode bills of materials, calculate shortest paths, and identify critical nodes—all while keeping your data where it is.

## Key Results

| Metric | Virtual Graph | Neo4j Baseline | Advantage |
|--------|---------------|----------------|-----------|
| **Accuracy** | 92% | 100%* | Competitive |
| **Avg Latency** | 2ms | 53ms | **26x faster** |
| **Setup Effort** | 4 hours | 44 hours | **90% reduction** |
| **Year 1 TCO** | $1,500 | $12,400 | **88% savings** |

*Neo4j is the accuracy reference; Virtual Graph is 26x faster due to no network hop to a separate database.

## How It Works

Virtual Graph routes queries through three paths based on complexity:

```
┌─────────────────────────────────────────────────────────────────┐
│                        QUERY ROUTING                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  "Find supplier Acme Corp"                                      │
│  ┌─────────┐                    ┌──────────────────────────────┐│
│  │ 🟢 GREEN │ ─── Simple SQL ──▶│ SELECT * FROM suppliers ...  ││
│  └─────────┘                    └──────────────────────────────┘│
│                                                                 │
│  "All tier 3 suppliers for Acme"                                │
│  ┌─────────┐                    ┌──────────────────────────────┐│
│  │ 🟡 YELLOW│ ── traverse() ───▶│ Frontier-batched BFS         ││
│  └─────────┘                    └──────────────────────────────┘│
│                                                                 │
│  "Cheapest route from Chicago to LA"                            │
│  ┌─────────┐                    ┌──────────────────────────────┐│
│  │ 🔴 RED  │ ── NetworkX ──────▶│ Dijkstra shortest path       ││
│  └─────────┘                    └──────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

| Route | Use Case | Handler | Latency |
|-------|----------|---------|---------|
| **GREEN** | Simple lookups, 1-2 hop joins | Direct SQL | 1-5ms |
| **YELLOW** | Recursive traversal, BOM explosion, tier chains | `traverse()` | 2-10ms |
| **RED** | Shortest path, centrality, connected components | NetworkX | 2-50ms |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/virt-graph.git
cd virt-graph

# Start PostgreSQL with sample data
docker-compose -f postgres/docker-compose.yml up -d

# Install dependencies
poetry install

# Run tests to verify setup
poetry run pytest
```

### Example Queries

```python
from virt_graph.handlers import traverse, shortest_path, centrality
from virt_graph.handlers.base import get_connection

conn = get_connection()

# YELLOW: Find all tier 3 suppliers upstream of Acme Corp
result = traverse(
    conn=conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=42,  # Acme Corp
    direction="inbound",
    max_depth=10
)
tier3 = [n for n in result["nodes"] if n["tier"] == 3]

# RED: Find cheapest shipping route
route = shortest_path(
    conn=conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    start_id=1,    # Chicago Warehouse
    end_id=2,      # LA Distribution Center
    weight_col="cost_usd"
)

# RED: Find most critical facility (betweenness centrality)
critical = centrality(
    conn=conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=5
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VIRTUAL GRAPH                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    CONTEXT MANAGEMENT                            │    │
│  │                                                                  │    │
│  │   ALWAYS LOADED              ON-DEMAND (Skills)                 │    │
│  │   ┌──────────────┐          ┌──────────────┐                    │    │
│  │   │  Ontology    │          │   Patterns   │                    │    │
│  │   │  (semantic   │          │   (learned   │                    │    │
│  │   │   mappings)  │          │    SQL)      │                    │    │
│  │   └──────────────┘          └──────────────┘                    │    │
│  │                              ┌──────────────┐                    │    │
│  │                              │   Schema     │                    │    │
│  │                              │ (introspect) │                    │    │
│  │                              └──────────────┘                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    GENERIC HANDLERS                              │    │
│  │                    (schema-parameterized)                        │    │
│  │                                                                  │    │
│  │   traverse()        shortest_path()        centrality()         │    │
│  │   bom_explode()     all_shortest_paths()   connected_components()│   │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         PostgreSQL                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Ontology** | `ontology/supply_chain.yaml` | Maps business concepts to SQL tables/columns |
| **Handlers** | `src/virt_graph/handlers/` | Schema-parameterized graph operations |
| **Patterns** | `patterns/templates/` | Reusable query templates |
| **Skills** | `.claude/skills/` | On-demand context for LLM reasoning |

## Safety Limits

Virtual Graph enforces **non-negotiable safety limits** to prevent runaway queries:

```python
MAX_DEPTH = 50          # Maximum traversal depth
MAX_NODES = 10,000      # Maximum nodes per traversal
MAX_RESULTS = 1,000     # Maximum rows returned
QUERY_TIMEOUT = 30s     # Per-query timeout
```

Queries that would exceed these limits are blocked **before execution**:

```python
# This query would touch ~65K nodes in the BOM tree
# Virtual Graph blocks it with SubgraphTooLarge exception
traverse(start_id=product_id, max_depth=20)
# → SubgraphTooLarge: Query would touch ~65,629 nodes (limit: 10,000)
```

## Benchmark Results

Tested against a supply chain database with 15 tables and ~130K rows:

### Accuracy by Route

| Route | Queries | Accuracy | Target | Status |
|-------|---------|----------|--------|--------|
| GREEN | 9 | 88.9% | 100% | MISS |
| YELLOW | 9 | 100%* | 90% | **PASS** |
| RED | 7 | 85.7% | 80% | **PASS** |
| **Overall** | 25 | **92%** | 85% | **PASS** |

*Includes queries correctly blocked by safety limits

### Performance vs Neo4j

| Route | Virtual Graph | Neo4j | VG Speed Advantage |
|-------|---------------|-------|-------------------|
| GREEN | 2ms | 43ms | 21x faster |
| YELLOW | 2ms | 71ms | 35x faster |
| RED | 1ms | 41ms | 41x faster |

Virtual Graph is faster because queries run directly on PostgreSQL—no network hop to a separate graph database.

## When to Use Virtual Graph

### Choose Virtual Graph When:

- You have data in relational databases you don't want to migrate
- 90%+ accuracy is acceptable for graph queries
- Real-time data freshness is critical
- Budget constraints preclude new infrastructure
- You need rapid prototyping of graph queries

### Choose Neo4j When:

- Complex graph patterns are your primary use case
- 100% accuracy is required
- Heavy graph workloads (majority of queries are traversals)
- Building a new system from scratch

## Project Structure

```
virt-graph/
├── src/virt_graph/
│   └── handlers/           # Graph operation handlers
│       ├── base.py         # Safety limits, utilities
│       ├── traversal.py    # BFS traversal
│       ├── pathfinding.py  # Dijkstra, shortest paths
│       └── network.py      # Centrality, components
├── ontology/
│   └── supply_chain.yaml   # Semantic mappings
├── patterns/
│   ├── raw/                # Discovered patterns
│   └── templates/          # Generalized templates
├── .claude/skills/         # LLM context skills
├── postgres/               # Database setup
├── neo4j/                  # Baseline comparison
├── benchmark/              # Benchmark harness
├── tests/                  # Gate validation tests
└── docs/                   # Documentation
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design and layer separation |
| [Traffic Light Routing](docs/traffic_light_routing.md) | Query classification rules |
| [Benchmark Results](docs/benchmark_results.md) | Detailed accuracy and latency analysis |
| [TCO Analysis](docs/tco_analysis.md) | Cost comparison with Neo4j |

## Development

```bash
# Run all tests
poetry run pytest

# Run specific gate validation
poetry run pytest tests/test_gate1_validation.py -v

# Run benchmark (requires Neo4j for comparison)
docker-compose -f neo4j/docker-compose.yml up -d
poetry run python neo4j/migrate.py
poetry run python benchmark/run.py --system both

# Serve documentation
poetry run mkdocs serve
```

## Sample Database

The project includes a synthetic supply chain database:

| Entity | Count | Description |
|--------|-------|-------------|
| Suppliers | 500 | Tiered (50 T1, 150 T2, 300 T3) |
| Parts | 5,003 | With BOM hierarchy (avg depth ~5) |
| Products | 200 | Finished goods |
| Facilities | 50 | Warehouses and factories |
| Orders | 20,000 | With shipments |
| **Total** | ~130K | rows |

Named test entities for consistent queries:
- **Suppliers**: "Acme Corp", "GlobalTech Industries", "Pacific Components"
- **Products**: "Turbo Encabulator" (TURBO-001), "Flux Capacitor" (FLUX-001)
- **Facilities**: "Chicago Warehouse" (FAC-CHI), "LA Distribution Center" (FAC-LA)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `poetry run pytest`
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Virtual Graph** is a proof-of-concept demonstrating that graph-like queries can be executed efficiently over relational data. For enterprises with existing SQL infrastructure, this approach delivers 92% of graph query capabilities at 88% lower cost than migrating to a dedicated graph database.
