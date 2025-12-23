# VG/SQL: Virtual Graph over SQL

## Project Overview

**VG/SQL** (Virtual Graph over SQL) is a system enabling graph-like queries (traversals, pathfinding, centrality) directly over relational SQL databases without data migration. It bridges the gap between relational storage and graph analysis by combining:

1.  **LinkML Ontologies**: Maps graph concepts (nodes, edges) to relational structures (tables, foreign keys) using [LinkML](https://linkml.io) with custom `vg:` extensions.
2.  **Lightweight Python Handlers**: Schema-parameterized functions that execute graph algorithms (BFS, Dijkstra, etc.) by generating and orchestrating efficient, batched SQL queries.
3.  **Agentic Orchestration**: Designed for AI agents (like Claude Code) to autonomously discover the ontology, dispatch requests to the appropriate handlers, and generate queries on the fly.
4.  **Pre-flight Estimation**: A sampling-based estimator to prevent runaway queries by analyzing graph growth and connectivity before execution.

## Core Architecture

### 1. Ontology System
*   **TBox (Entity Classes)**: Defined via `vg:SQLMappedClass`, mapping entities to SQL tables.
*   **RBox (Relationship Classes)**: Defined via `vg:SQLMappedRelationship`, mapping graph edges to foreign keys or edge tables.
*   **Operation Types**: Annotations (`vg:operation_types`) that tell the agent which handler is needed (e.g., `recursive_traversal`, `shortest_path`, `direct_join`).
*   **Metamodel**: `virt_graph.yaml` (project root) is the single source of truth for all ontology validation rules.

### 2. Handlers (`src/virt_graph/handlers/`)
*   **`base.py`**: Infrastructure for all handlers. Enforces non-negotiable safety limits (`MAX_DEPTH=50`, `MAX_NODES=10,000`) and provides mandatory batching utilities (Frontier-Batched BFS).
*   **`traversal.py`**: Implements `traverse()` (BFS/DFS) and `path_aggregate()` (e.g., BOM cost rollups).
*   **`pathfinding.py`**: Implements `shortest_path()` (Dijkstra) and `all_shortest_paths()`.
*   **`network.py`**: Implements centrality measures (`betweenness`, `closeness`, `degree`), `connected_components()`, and `resilience_analysis()`.

### 3. Estimator (`src/virt_graph/estimator/`)
*   Prevents `SubgraphTooLarge` errors by sampling the graph structure.
*   Detects growth trends, cycles, and hubs to provide proactive warnings.

## Primary Example: FMCG (Prism Consumer Goods)

Located in `fmcg_example/`, this is a high-velocity, massive-volume supply chain simulation inspired by Colgate-Palmolive.

*   **Scale**: ~13.6M rows across 70 tables (SCOR-DS model: Plan, Source, Transform, Order, Fulfill, Return).
*   **Graph Shape**: "Horizontal Explosion" (1 batch → 20 SKUs → 50,000 retail orders).
*   **Physics Engine**: Implements SKU-level micro-physics (demand-pull supply distribution, emergent logistics, and dynamic safety stock policies).
*   **Key Stress Test**: Recall Trace (tracing a contaminated batch through the entire network in < 5s).
*   **Benchmarking Source of Truth**: All validation tolerances and chaos effect signatures are centralized in `fmcg_example/scripts/data_generation/benchmark_manifest.json`.
*   **Chaos Injection**: Realistic disruptions like port strikes, cyber outages, and "bullwhip effect" demand volatility.

## Building and Running

### Prerequisites
*   Python 3.12+ (managed by Poetry)
*   Docker & Docker Compose

### Common Commands (via `Makefile`)

*   **Setup**: `make install`
*   **FMCG Database**:
    *   `make fmcg-db-up`: Start Postgres on port 5433.
    *   `make fmcg-generate`: Generate the ~13.6M row seed dataset.
    *   `make fmcg-test`: Run FMCG-specific integration tests.
    *   `make fmcg-db-reset`: Wipe and reload the entire FMCG DB.
*   **Core Testing**: `make test` (Legacy supply chain) or `make test-handlers`.
*   **Documentation**: `make serve-docs` (Serves MkDocs on localhost:8000).
*   **Neo4j (Benchmark)**: `make neo4j-up` (Starts Neo4j on ports 7475/7688).

## Development Conventions

*   **Schema Parameterization**: Handlers MUST NOT hardcode table or column names. They accept these as arguments based on ontology discovery.
*   **Batching Pattern**: "One query per node" is strictly forbidden. Use `fetch_edges_for_frontier` from `base.py` to fetch edges for an entire frontier using `ANY` or `IN`.
*   **Safety Limits**: Handlers enforce non-negotiable limits: `MAX_DEPTH=50`, `MAX_NODES=10,000`.
*   **Soft-Delete & Temporal Support**: Always respect `deleted_at` columns and `valid_at` temporal bounds if specified in the ontology.
*   **UoM Normalization**: Complex unit conversions (kg, liters, cases) should be handled in SQL Views, and the ontology should map to these views.
*   **Dual Modeling**: Large concepts (like Contracts) should be modeled as both Nodes (for detail) and Shortcut Edges (for traversal speed).

## Agentic Workflow Guidelines

As an AI agent, you should follow this protocol:

1.  **Discovery**: Read `fmcg_example/ontology/prism_fmcg.yaml` to understand available entities and relationships.
2.  **Estimation**: For deep or wide traversals, use the `estimator` to check if the query will hit safety limits.
3.  **Dispatch**:
    *   Use **Direct SQL** for `direct_join` operations.
    *   Use **Handlers** for `recursive_traversal`, `path_aggregation`, or `algorithm` operations.
4.  **Execution**: Call the appropriate Python handler with the connection and schema parameters discovered from the ontology.
5.  **Validation**: Verify results against the "Named Test Entities" (e.g., `B-2024-RECALL-001` for recall tracing) and consult `benchmark_manifest.json` for validation tolerances.
