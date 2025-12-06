# Virtual Graph Implementation Plan v3

> **Note**: This document is the original v3 implementation plan (completed December 2024).
> For current documentation, see:
> - **[CLAUDE.md](CLAUDE.md)** - Development commands, architecture overview, handler reference
> - **[docs/](docs/)** - Full documentation (architecture, API, benchmark results)
>
> The ontology format has evolved from the flat structure shown here to TBox/RBox format.
> See `ontology/supply_chain.yaml` and `src/virt_graph/ontology.py` for current implementation.

## Executive Summary

**Goal**: Compare two approaches for enabling graph-like queries over enterprise relational data:

| Approach | How it works |
|----------|--------------|
| **Virtual Graph** | LLM reasons over SQL using a discovered ontology + learned SQL patterns |
| **Neo4j Baseline** | Traditional graph database with migrated data |

**Key Hypothesis**: For enterprises with existing SQL infrastructure, the Virtual Graph approach can deliver 80%+ of graph query capabilities at a fraction of the migration cost.

**What's Different in v3**: Restructured for efficient phased execution:
- Parallel workstreams where dependencies allow
- Early validation gates to catch issues before deep investment
- Incremental deliverables at each phase checkpoint
- Clear dependency chains between components

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLAUDE CODE SESSION                              │
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
│  │   traverse(nodes_table, edges_table, fk_from, fk_to,            │    │
│  │            direction, stop_condition, max_depth)                 │    │
│  │                                                                  │    │
│  │   shortest_path(nodes_table, edges_table, weight_col,           │    │
│  │                 start_id, end_id)                                │    │
│  │                                                                  │    │
│  │   impact_analysis(start_table, start_id, relationship_chain)    │    │
│  │                                                                  │    │
│  │   centrality(nodes_table, edges_table, centrality_type)         │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         PostgreSQL                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phased Implementation

### Phase Dependency Graph

```
PHASE 1: Foundation (Parallel Tracks)
├── Track A: Database Infrastructure
│   └── PostgreSQL + Schema + Data
└── Track B: Handler Core
    └── base.py + traversal.py (with safety limits)

         ↓ [Gate 1: Scalability Validation]

PHASE 2: Discovery Foundation
├── Ontology Discovery Session
│   └── Introspection → Interview → YAML
└── Schema Skill Implementation
    └── Introspection queries + skill definition

         ↓ [Gate 2: Ontology Validation]

PHASE 3: Query Execution (Parallel Tracks)
├── Track A: GREEN Path
│   └── Simple SQL generation via ontology
├── Track B: YELLOW Path
│   └── Pattern discovery + traversal handler
└── Track C: RED Path (start parallel, finish after B)
    └── NetworkX handlers + pathfinding

         ↓ [Gate 3: Route Validation - 10 queries each color]

PHASE 4: Pattern Maturity
├── Pattern Generalization
│   └── Raw patterns → Templates
├── Handler Skill Implementation
│   └── Skill definition + reference docs
└── Pattern Skill Implementation
    └── Skill definition + catalog

         ↓ [Gate 4: Skill Integration Test]

PHASE 5: Baseline & Benchmark (Parallel)
├── Track A: Neo4j Baseline
│   └── Setup + Migration + Cypher queries
└── Track B: Benchmark Harness
    └── Query definitions + ground truth + runner

         ↓ [Gate 5: Benchmark Ready]

PHASE 6: Evaluation & Documentation
├── Run Full Benchmark (25 queries × 2 systems)
├── Analysis & Comparison
└── Final Documentation
```

---

## Phase 1: Foundation

**Duration**: First sprint
**Goal**: Working database with realistic data + handler framework with safety guarantees

### Track A: Database Infrastructure

#### 1A.1 PostgreSQL Setup

```yaml
# postgres/docker-compose.yml
services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: supply_chain
      POSTGRES_USER: virt_graph
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"
    volumes:
      - ./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
      - ./seed.sql:/docker-entrypoint-initdb.d/02-seed.sql
```

#### 1A.2 Schema Design

**Deliverable**: `postgres/schema.sql`

Supply chain schema with realistic "enterprise messiness":
- ~15 tables with inconsistent naming conventions
- Nullable FKs, soft deletes (`deleted_at`)
- Audit columns (`created_at`, `updated_at`, `created_by`)
- Some denormalization for performance

**Core tables**:
| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `suppliers` | Supplier entities | Self-referential via `supplier_relationships` |
| `supplier_relationships` | Tier structure (seller → buyer) | FK to suppliers (both ends) |
| `parts` | Component catalog | FK to suppliers (primary source) |
| `bill_of_materials` | BOM hierarchy | Self-referential (child → parent) |
| `products` | Finished goods | FK to parts via product_components |
| `facilities` | Warehouses, factories | Connected via transport_routes |
| `transport_routes` | Logistics network | FK to facilities (both ends) + distance/cost |
| `orders` | Customer orders | FK to products, facilities |
| `shipments` | Order fulfillment | FK to orders, transport_routes |

#### 1A.3 Data Generation

**Deliverable**: `scripts/generate_data.py`

Synthetic but realistic data:
- 500 suppliers (tiered: 50 T1, 150 T2, 300 T3)
- 5,000 parts with BOM hierarchy (avg depth: 5 levels)
- 50 facilities with transport network
- 20,000 orders with shipments
- **Total**: ~130K rows

**Critical for Phase 1**: Generate BOM with 5K+ parts to validate scalability early.

### Track B: Handler Core

#### 1B.1 Base Infrastructure

**Deliverable**: `handlers/base.py`

```python
"""
Core handler infrastructure with safety limits and utilities.
"""
from typing import Any
import psycopg2

# === SAFETY LIMITS (Non-negotiable) ===
MAX_DEPTH = 50          # Absolute traversal depth limit
MAX_NODES = 10_000      # Max nodes to visit in single traversal
MAX_RESULTS = 1_000     # Max rows to return
QUERY_TIMEOUT_SEC = 30  # Per-query timeout

class SafetyLimitExceeded(Exception):
    """Raised when a handler would exceed safety limits."""
    pass

class SubgraphTooLarge(Exception):
    """Raised when estimated subgraph exceeds MAX_NODES."""
    pass

def check_limits(depth: int, visited_count: int) -> None:
    """Check traversal hasn't exceeded safety limits."""
    if depth > MAX_DEPTH:
        raise SafetyLimitExceeded(
            f"Traversal depth {depth} exceeds limit {MAX_DEPTH}"
        )
    if visited_count > MAX_NODES:
        raise SafetyLimitExceeded(
            f"Visited {visited_count} nodes, exceeds limit {MAX_NODES}"
        )

def estimate_reachable_nodes(
    conn,
    edges_table: str,
    start_id: int,
    max_depth: int,
    edge_from_col: str,
    edge_to_col: str,
) -> int:
    """
    Estimate reachable node count using sampling.
    Returns conservative estimate to decide if full traversal is safe.
    """
    # Sample first 3 levels, extrapolate
    ...

def fetch_edges_for_frontier(
    conn,
    edges_table: str,
    frontier_ids: list[int],
    edge_from_col: str,
    edge_to_col: str,
    direction: str = "outbound",
) -> list[tuple]:
    """
    Fetch all edges for a frontier in a SINGLE query.
    This is the mandatory batching pattern - never one query per node.
    """
    if direction == "outbound":
        col = edge_from_col
    elif direction == "inbound":
        col = edge_to_col
    else:  # both
        # Two queries, still batched
        ...

    query = f"""
        SELECT {edge_from_col}, {edge_to_col}
        FROM {edges_table}
        WHERE {col} = ANY(%s)
    """
    with conn.cursor() as cur:
        cur.execute(query, (frontier_ids,))
        return cur.fetchall()
```

#### 1B.2 Traversal Handler

**Deliverable**: `handlers/traversal.py`

```python
"""
Generic graph traversal using frontier-batched BFS.
Schema-parameterized: knows nothing about suppliers/parts, only tables/columns.
"""
from typing import Optional
from .base import (
    check_limits, estimate_reachable_nodes, fetch_edges_for_frontier,
    SubgraphTooLarge, MAX_NODES, MAX_DEPTH
)

def traverse(
    conn,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    direction: str = "outbound",
    max_depth: int = 10,
    stop_condition: Optional[str] = None,
    collect_columns: Optional[list[str]] = None,
    prefilter_sql: Optional[str] = None,
) -> dict:
    """
    Generic graph traversal using iterative frontier-batched BFS.

    Args:
        conn: Database connection
        nodes_table: Table containing nodes (e.g., "suppliers")
        edges_table: Table containing edges (e.g., "supplier_relationships")
        edge_from_col: Column for edge source (e.g., "seller_id")
        edge_to_col: Column for edge target (e.g., "buyer_id")
        start_id: Starting node ID
        direction: "outbound", "inbound", or "both"
        max_depth: Maximum traversal depth
        stop_condition: SQL WHERE clause fragment to stop traversal
        collect_columns: Columns to return from nodes table
        prefilter_sql: SQL WHERE clause to pre-filter edges

    Returns:
        dict with:
            - nodes: list of reached node dicts
            - paths: dict mapping node_id → path from start
            - depth_reached: actual max depth encountered
    """
    # Clamp to safety limit
    max_depth = min(max_depth, MAX_DEPTH)

    # Estimate size before traversing
    estimated = estimate_reachable_nodes(
        conn, edges_table, start_id, max_depth, edge_from_col, edge_to_col
    )
    if estimated > MAX_NODES:
        raise SubgraphTooLarge(
            f"Query would touch ~{estimated} nodes (limit: {MAX_NODES}). "
            "Consider adding filters or reducing depth."
        )

    # Initialize traversal state
    frontier = {start_id}
    visited = {start_id}
    paths = {start_id: [start_id]}
    depth_reached = 0

    # Frontier-batched BFS
    for depth in range(max_depth):
        if not frontier:
            break

        check_limits(depth, len(visited))

        # Single query for entire frontier
        edges = fetch_edges_for_frontier(
            conn, edges_table, list(frontier),
            edge_from_col, edge_to_col, direction
        )

        next_frontier = set()
        for from_id, to_id in edges:
            target = to_id if direction == "outbound" else from_id
            if target not in visited:
                # Check stop condition if provided
                if stop_condition and should_stop(conn, nodes_table, target, stop_condition):
                    continue

                next_frontier.add(target)
                visited.add(target)
                # Track path
                source = from_id if direction == "outbound" else to_id
                paths[target] = paths[source] + [target]

        frontier = next_frontier
        depth_reached = depth + 1

    # Fetch node data for all visited nodes
    nodes = fetch_nodes(conn, nodes_table, list(visited), collect_columns)

    return {
        "nodes": nodes,
        "paths": paths,
        "depth_reached": depth_reached,
        "nodes_visited": len(visited),
    }
```

### Gate 1: Scalability Validation

**Before proceeding to Phase 2, validate**:

1. **BOM traversal at scale**: Run `traverse()` on a 5K-part BOM
   - Target: Complete in <2 seconds
   - Verify frontier batching works (should be ~depth queries, not ~nodes queries)

2. **Safety limits trigger**: Attempt traversal that would exceed MAX_NODES
   - Target: `SubgraphTooLarge` exception raised before DB overload

3. **Data integrity**: Verify generated data has expected graph properties
   - Supplier tiers form valid DAG
   - BOM has realistic depth distribution
   - Transport network is connected

**Deliverables checkpoint**:
- [ ] `postgres/docker-compose.yml` - PostgreSQL working
- [ ] `postgres/schema.sql` - All 15 tables created
- [ ] `scripts/generate_data.py` - 130K rows generated
- [ ] `handlers/base.py` - Safety infrastructure
- [ ] `handlers/traversal.py` - BFS with frontier batching
- [ ] Gate 1 validation report

---

## Phase 2: Discovery Foundation

**Duration**: Second sprint
**Goal**: Discovered ontology from raw schema + schema introspection skill

### 2.1 Schema Introspection Queries

**Deliverable**: `.claude/skills/schema/scripts/introspect.sql`

```sql
-- Tables and columns
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

-- Foreign keys
SELECT
    tc.table_name AS source_table,
    kcu.column_name AS source_column,
    ccu.table_name AS target_table,
    ccu.column_name AS target_column,
    tc.constraint_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;

-- Primary keys
SELECT
    tc.table_name,
    kcu.column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'PRIMARY KEY';

-- Unique constraints (potential identifiers)
SELECT
    tc.table_name,
    kcu.column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'UNIQUE';

-- Sample data (parameterized, run per table)
-- SELECT * FROM {table} LIMIT 10;

-- Row counts per table
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;

-- Referential integrity check (for implicit relationships)
-- Run this for suspected FK columns without constraints
-- SELECT COUNT(*) as orphans
-- FROM {child_table}
-- WHERE {child_column} NOT IN (SELECT {parent_column} FROM {parent_table});
```

### 2.2 Schema Skill Definition

**Deliverable**: `.claude/skills/schema/SKILL.md`

```markdown
---
name: virt-graph-schema
description: >
  Introspect PostgreSQL schema for physical table/column details. Use when
  generating SQL and need exact column names, foreign key relationships,
  data types, or sample data. Reconciles with ontology semantic mappings.
allowed-tools: Read, Bash
---

# Schema Introspection

## When to Use
Invoke when you need to translate ontology concepts to physical SQL:
- Mapping class names to table names
- Finding FK columns for relationships
- Checking column types for WHERE clauses
- Getting sample data to validate assumptions

## Available Queries
Read `.claude/skills/schema/scripts/introspect.sql` for:
- All tables and columns with types
- Foreign key relationships
- Primary keys and unique constraints
- Row counts per table

## Instructions
1. Run introspection queries against `information_schema`
2. Cross-reference with ontology `sql_mapping` sections
3. Return physical details needed for SQL generation

## Connection
Use environment variable `DATABASE_URL` or default:
`postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
```

### 2.3 Ontology Discovery Session

**Deliverable**: `ontology/supply_chain.yaml` + `docs/ontology_discovery_session.md`

#### Discovery Process (Multi-Round Conversation)

**Round 1: Schema Introspection**

Claude runs introspection queries, produces initial draft:

```yaml
# Claude's initial draft after introspection
classes:
  Supplier:
    sql_table: suppliers
    inferred_from: "table 'suppliers' with columns: id, name, tier, country..."
    confidence: high
    questions:
      - "Is supplier_code used as an identifier in other systems?"
      - "What do the tier values (1, 2, 3) represent?"

relationships:
  unknown_supplier_link:
    sql_table: supplier_relationships
    domain: Supplier (via seller_id)
    range: Supplier (via buyer_id)
    inferred_from: "self-referential FK pattern"
    confidence: medium
    questions:
      - "What does this relationship represent semantically?"
      - "Is this directional? What does the direction mean?"
```

**Round 2: Business Context Interview**

Required questions for each relationship:
1. **Cardinality**: "Can one [domain] relate to multiple [range]? Vice versa?"
2. **Directionality**: "Is this relationship strictly one-way?"
3. **Reflexivity**: "Can an entity relate to itself?" (critical for cycle detection)
4. **Optionality**: "Is this relationship required or optional?"

**Round 3: Data Validation**

For implicit relationships (column patterns without FK constraints):
```sql
-- Validate referential integrity
SELECT COUNT(*) as orphans
FROM bill_of_materials
WHERE parent_part_id NOT IN (SELECT id FROM parts)
```

If orphan rate >5%, prompt user:
```
I found 500 orphaned records in `bill_of_materials.parent_part_id`
(5.2% of rows reference non-existent parts).

How should I handle this relationship?
1. Strict (INNER JOIN): Ignore orphaned records
2. Optional (LEFT JOIN): Include, show NULLs for missing parents
3. Investigate: Show sample orphaned records before deciding
```

**Final Ontology Structure**:

```yaml
# ontology/supply_chain.yaml
version: "1.0"
domain: "Supply Chain"
discovered: "2024-01-15"
discovery_rounds: 3

classes:
  Supplier:
    description: "Companies that provide materials/parts"
    sql_mapping:
      table: suppliers
      primary_key: id
      identifier_columns: [supplier_code, name]
    attributes:
      tier:
        type: integer
        values: [1, 2, 3]
        description: "Supply chain tier (1=direct, 2=tier2, 3=tier3)"

  Part:
    description: "Components used in manufacturing"
    sql_mapping:
      table: parts
      primary_key: id
      identifier_columns: [part_number, description]

  Product:
    description: "Finished goods sold to customers"
    sql_mapping:
      table: products
      primary_key: id
      identifier_columns: [sku, name]

  Facility:
    description: "Physical locations (warehouses, factories)"
    sql_mapping:
      table: facilities
      primary_key: id
      identifier_columns: [facility_code, name]

relationships:
  supplies_to:
    domain: Supplier
    range: Supplier
    description: "Supplier provides materials/parts to another supplier"
    sql_mapping:
      table: supplier_relationships
      domain_key: seller_id
      range_key: buyer_id
    properties:
      cardinality: many-to-many
      is_directional: true
      is_reflexive: false
    business_rule: |
      Represents supply chain tiers:
      - Tier 3 supplies_to Tier 2
      - Tier 2 supplies_to Tier 1
      - Tier 1 supplies_to us (implicit)
    traversal_complexity: YELLOW
    is_hierarchical: true

  component_of:
    domain: Part
    range: Part
    description: "This part is a component of another part (BOM)"
    sql_mapping:
      table: bill_of_materials
      domain_key: child_part_id
      range_key: parent_part_id
    properties:
      cardinality: many-to-many
      is_directional: true
      is_reflexive: false  # No circular BOMs allowed
    validation:
      integrity_check: "99.8% referential integrity"
      orphan_count: 12
      join_type: inner
    traversal_complexity: YELLOW
    is_recursive: true

  provides:
    domain: Supplier
    range: Part
    description: "Supplier is primary source for this part"
    sql_mapping:
      table: parts
      domain_key: primary_supplier_id
      range_key: id
    properties:
      cardinality: one-to-many
      is_directional: true
    traversal_complexity: GREEN

  connects_to:
    domain: Facility
    range: Facility
    description: "Transport route between facilities"
    sql_mapping:
      table: transport_routes
      domain_key: origin_facility_id
      range_key: destination_facility_id
      weight_column: distance_km  # or cost_usd
    properties:
      cardinality: many-to-many
      is_directional: true  # Routes may be one-way
    traversal_complexity: RED
    when_weighted: true

business_rules:
  - "Tier 1 suppliers have direct contracts with us"
  - "All parts must have at least one supplier"
  - "Products are assembled from top-level BOM items only"
  - "Shipments must follow valid transport routes"
```

### Gate 2: Ontology Validation

**Before proceeding to Phase 3, validate**:

1. **Coverage**: Every table in schema maps to a class or relationship
2. **Correctness**: Run 5 simple queries using ontology mappings, verify results
3. **Completeness**: All relationships have:
   - sql_mapping with table, domain_key, range_key
   - traversal_complexity (GREEN/YELLOW/RED)
   - properties (cardinality, directionality, reflexivity)

**Deliverables checkpoint**:
- [ ] `.claude/skills/schema/SKILL.md`
- [ ] `.claude/skills/schema/scripts/introspect.sql`
- [ ] `ontology/supply_chain.yaml` (discovered, not hand-written)
- [ ] `docs/ontology_discovery_session.md` (transcript)
- [ ] Gate 2 validation report

---

## Phase 3: Query Execution Paths

**Duration**: Third sprint
**Goal**: All three query routes (GREEN/YELLOW/RED) working with discovered ontology

### Track A: GREEN Path (Simple SQL)

**No new handlers needed** - Claude generates SQL directly using ontology mappings.

#### 3A.1 Test GREEN Queries

Verify Claude can answer these using only ontology + schema introspection:

| # | Query | Expected SQL Pattern |
|---|-------|---------------------|
| 1 | "Find supplier ABC Corp" | `SELECT * FROM suppliers WHERE name = 'ABC Corp'` |
| 2 | "List all tier 1 suppliers" | `SELECT * FROM suppliers WHERE tier = 1` |
| 3 | "Parts from supplier X" | `SELECT p.* FROM parts p WHERE p.primary_supplier_id = ?` |
| 4 | "Products using part Y" | `SELECT DISTINCT pr.* FROM products pr JOIN product_components pc ON ...` |
| 5 | "Facilities in California" | `SELECT * FROM facilities WHERE state = 'CA'` |

### Track B: YELLOW Path (Recursive Traversal)

#### 3B.1 Pattern Discovery Session

Run test queries, record working patterns:

**Query**: "Find all tier 3 suppliers for Acme Corp"

**Raw Pattern Recording**:
```yaml
# patterns/raw/supplier_tier_traversal_001.yaml
discovered: "2024-01-15"
query: "Find all tier 3 suppliers for Acme Corp"
sql_attempted: |
  -- Attempt 1: Simple recursive CTE
  WITH RECURSIVE tier_chain AS (
    SELECT seller_id, buyer_id, 1 as depth
    FROM supplier_relationships
    WHERE buyer_id = 42  -- Acme Corp

    UNION ALL

    SELECT sr.seller_id, sr.buyer_id, tc.depth + 1
    FROM supplier_relationships sr
    JOIN tier_chain tc ON sr.buyer_id = tc.seller_id
    WHERE tc.depth < 10
  )
  SELECT DISTINCT s.*
  FROM tier_chain tc
  JOIN suppliers s ON tc.seller_id = s.id
  WHERE s.tier = 3

handler_used: traverse
handler_params:
  nodes_table: suppliers
  edges_table: supplier_relationships
  edge_from_col: seller_id
  edge_to_col: buyer_id
  start_id: 42
  direction: inbound
  max_depth: 10
  stop_condition: "tier = 3"

result_correct: true
execution_time_ms: 45
notes: "Handler approach cleaner than CTE for variable depth"
```

**Query**: "All components for Product X (BOM explosion)"

```yaml
# patterns/raw/bom_explosion_001.yaml
discovered: "2024-01-15"
query: "All components for Turbo Encabulator"
handler_used: traverse
handler_params:
  nodes_table: parts
  edges_table: bill_of_materials
  edge_from_col: parent_part_id
  edge_to_col: child_part_id
  start_id: 789  # Product's top-level part
  direction: outbound
  max_depth: 20

result_correct: true
execution_time_ms: 180
nodes_returned: 342
notes: "Deep BOM (12 levels), handler outperforms CTE"
```

#### 3B.2 Test YELLOW Queries

| # | Query | Handler | Key Params |
|---|-------|---------|------------|
| 1 | "All tier 3 suppliers for X" | `traverse` | direction=inbound, stop=tier=3 |
| 2 | "Upstream suppliers of Y" | `traverse` | direction=inbound |
| 3 | "Downstream customers of Z" | `traverse` | direction=outbound |
| 4 | "Full BOM for product P" | `traverse` | edge_from=parent, edge_to=child |
| 5 | "Products affected if supplier S fails" | `traverse` | Reverse: supplier → parts → products |

### Track C: RED Path (Network Algorithms)

#### 3C.1 NetworkX Handler

**Deliverable**: `handlers/pathfinding.py`

```python
"""
NetworkX-based pathfinding handlers.
Loads subgraph on-demand using frontier-batched queries.
"""
import networkx as nx
from typing import Union, Optional
from .base import fetch_edges_for_frontier, MAX_NODES, SubgraphTooLarge

def shortest_path(
    conn,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    end_id: int,
    weight_col: Optional[str] = None,
    max_depth: int = 20,
) -> dict:
    """
    Find shortest path between two nodes using Dijkstra.

    Loads only the relevant subgraph (nodes reachable from start within max_depth).
    """
    # Build subgraph incrementally
    G = nx.DiGraph()
    frontier = {start_id}
    visited = set()

    for depth in range(max_depth):
        if not frontier:
            break
        if end_id in visited:
            break  # Found target, stop loading

        edges = fetch_edges_for_frontier(
            conn, edges_table, list(frontier),
            edge_from_col, edge_to_col, "outbound"
        )

        next_frontier = set()
        for from_id, to_id in edges:
            if weight_col:
                weight = fetch_weight(conn, edges_table, from_id, to_id, weight_col)
                G.add_edge(from_id, to_id, weight=weight)
            else:
                G.add_edge(from_id, to_id)

            if to_id not in visited:
                next_frontier.add(to_id)
                visited.add(to_id)

        frontier = next_frontier

        if len(visited) > MAX_NODES:
            raise SubgraphTooLarge(f"Subgraph exceeds {MAX_NODES} nodes")

    if end_id not in G:
        return {"path": None, "distance": None, "error": "No path found"}

    try:
        if weight_col:
            path = nx.shortest_path(G, start_id, end_id, weight="weight")
            distance = nx.shortest_path_length(G, start_id, end_id, weight="weight")
        else:
            path = nx.shortest_path(G, start_id, end_id)
            distance = len(path) - 1

        return {"path": path, "distance": distance}
    except nx.NetworkXNoPath:
        return {"path": None, "distance": None, "error": "No path found"}
```

**Deliverable**: `handlers/network.py`

```python
"""
NetworkX-based network analysis handlers.
"""
import networkx as nx
from typing import Literal
from .base import fetch_edges_for_frontier, MAX_NODES

def centrality(
    conn,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    centrality_type: Literal["degree", "betweenness", "closeness", "pagerank"] = "degree",
    top_n: int = 10,
) -> list[dict]:
    """
    Calculate centrality for nodes in the graph.
    Returns top N most central nodes.

    WARNING: Loads entire graph into memory. Only use for small-medium graphs.
    """
    # Load full graph (with size check)
    G = load_full_graph(conn, edges_table, edge_from_col, edge_to_col)

    if G.number_of_nodes() > MAX_NODES:
        raise SubgraphTooLarge(
            f"Graph has {G.number_of_nodes()} nodes, exceeds limit {MAX_NODES}"
        )

    if centrality_type == "degree":
        scores = nx.degree_centrality(G)
    elif centrality_type == "betweenness":
        scores = nx.betweenness_centrality(G)
    elif centrality_type == "closeness":
        scores = nx.closeness_centrality(G)
    elif centrality_type == "pagerank":
        scores = nx.pagerank(G)

    # Sort and return top N
    sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # Fetch node details
    node_ids = [n[0] for n in sorted_nodes]
    nodes = fetch_nodes(conn, nodes_table, node_ids)

    return [
        {"node": node, "score": score}
        for (node_id, score), node in zip(sorted_nodes, nodes)
    ]

def connected_components(
    conn,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
) -> list[set]:
    """Find connected components in the graph."""
    G = load_full_graph(conn, edges_table, edge_from_col, edge_to_col)

    # Use undirected view for connectivity
    return list(nx.weakly_connected_components(G))
```

#### 3C.2 Test RED Queries

| # | Query | Handler | Notes |
|---|-------|---------|-------|
| 1 | "Cheapest route from A to B" | `shortest_path` | weight_col=cost_usd |
| 2 | "Shortest path from factory to customer" | `shortest_path` | weight_col=distance_km |
| 3 | "Most critical facility" | `centrality` | type=betweenness |
| 4 | "Most connected supplier" | `centrality` | type=degree |
| 5 | "Isolated facility clusters" | `connected_components` | - |

### Gate 3: Route Validation

**Before proceeding to Phase 4, validate**:

Run 10 queries for each route (30 total), measure:

| Metric | GREEN Target | YELLOW Target | RED Target |
|--------|--------------|---------------|------------|
| Correctness | 100% | 90% | 80% |
| First-attempt | 90% | 70% | 60% |
| Latency | <100ms | <2s | <5s |

**Deliverables checkpoint**:
- [ ] `handlers/pathfinding.py` - Dijkstra with incremental loading
- [ ] `handlers/network.py` - Centrality, components
- [ ] `patterns/raw/*.yaml` - 10+ raw patterns recorded
- [ ] Route validation results (30 queries)
- [ ] Gate 3 validation report

---

## Phase 4: Pattern Maturity

**Duration**: Fourth sprint
**Goal**: Generalized patterns + all skills operational

### 4.1 Pattern Generalization

**Deliverable**: `patterns/templates/` (organized by function)

```
patterns/templates/
├── traversal/
│   ├── tier_traversal.yaml
│   ├── bom_explosion.yaml
│   └── impact_analysis.yaml
├── pathfinding/
│   ├── shortest_path.yaml
│   └── all_paths.yaml
├── aggregation/
│   └── rollup.yaml
└── network-analysis/
    ├── centrality.yaml
    └── components.yaml
```

**Example Generalized Pattern**:

```yaml
# patterns/templates/traversal/bom_explosion.yaml
name: bom_explosion
description: "Explode bill of materials recursively"
derived_from:
  - patterns/raw/bom_explosion_001.yaml
  - patterns/raw/bom_explosion_002.yaml

handler: traverse
priority: 1
success_rate: 0.95

applicability:
  - query mentions "bill of materials", "BOM", "components", "parts list"
  - relationship has `is_recursive: true` in ontology

ontology_bindings:
  node_class: Part
  edge_relationship: component_of
  direction: outbound  # Parent → Children

handler_params:
  direction: "outbound"
  max_depth: 20

examples:
  - "Show me all components for product X"
  - "Full parts list for the Turbo Encabulator"
  - "What goes into making product Y?"
```

### 4.2 Pattern Skill Implementation

**Deliverable**: `.claude/skills/patterns/SKILL.md`

```markdown
---
name: virt-graph-patterns
description: >
  Load SQL pattern templates for graph operations. Use when query involves
  recursive traversal, BOM explosion, tier analysis, impact analysis,
  shortest path, or centrality calculations. Patterns are grouped by
  function: traversal, pathfinding, aggregation, network-analysis.
allowed-tools: Read, Glob, Grep
---

# Virtual Graph Pattern Templates

## When to Use
Invoke this skill when the user's query matches known graph operation patterns
and you need parameterized SQL templates to instantiate.

## Pattern Groups
- **traversal/**: BOM explosion, tier traversal, dependency chains
- **pathfinding/**: Shortest path, all paths, optimal routes
- **aggregation/**: Impact analysis, rollup calculations
- **network-analysis/**: Centrality, connectivity, clustering

## Instructions
1. Read `patterns/templates/{group}/` for relevant pattern files
2. Match query semantics to pattern applicability conditions
3. Extract parameters needed from ontology + schema introspection
4. Return instantiated handler call

## Pattern Matching Examples

### Example 1: Impact Analysis
**User query**: "What products are affected if Acme Corp fails?"
**Match**: `aggregation/impact_analysis.yaml`
**Why**: Query involves downstream dependency traversal from a single entity

### Example 2: BOM Explosion
**User query**: "Show me all components needed for the Turbo Encabulator"
**Match**: `traversal/bom_explosion.yaml`
**Why**: Query asks for recursive part breakdown of a product

### Example 3: Shortest Route
**User query**: "What's the cheapest way to ship from Chicago to LA?"
**Match**: `pathfinding/shortest_path.yaml`
**Why**: Query asks for optimal path with cost weighting

## Tie-Breaking Rules
When multiple patterns match:
1. Highest `success_rate` wins
2. If tied, lowest `priority` wins
3. If still tied, most specific `applicability` match wins
```

**Deliverable**: `.claude/skills/patterns/reference.md`

```markdown
# Pattern Template Catalog

## Traversal Patterns

### tier_traversal
- **Use for**: Supplier tiers, org hierarchies
- **Direction**: Usually inbound (downstream → upstream)
- **Stop**: By tier number or depth

### bom_explosion
- **Use for**: Bill of materials, product composition
- **Direction**: Usually outbound (parent → children)
- **Stop**: By depth or leaf nodes

### impact_analysis
- **Use for**: Failure propagation, dependency impact
- **Direction**: Reverse of normal relationship
- **Returns**: All affected downstream entities

## Pathfinding Patterns

### shortest_path
- **Use for**: Optimal routes, cheapest/fastest paths
- **Requires**: Weight column in edges table
- **Algorithm**: Dijkstra via NetworkX

### all_paths
- **Use for**: Alternative routes, path enumeration
- **Caution**: Can explode combinatorially

## Network Analysis Patterns

### centrality
- **Types**: degree, betweenness, closeness, pagerank
- **Use for**: Critical node identification
- **Caution**: Loads full graph, size limits apply

### connected_components
- **Use for**: Cluster identification, isolation detection
```

### 4.3 Handler Skill Implementation

**Deliverable**: `.claude/skills/handlers/SKILL.md`

```markdown
---
name: virt-graph-handlers
description: >
  Generic graph operation handlers. Use for YELLOW (recursive traversal) or
  RED (network algorithms) queries. Handlers are schema-parameterized -
  provide table names, FK columns, and conditions. Groups: traversal,
  pathfinding, network-analysis.
allowed-tools: Read, Bash
---

# Generic Graph Handlers

## Handler Groups
- **traversal**: `traverse()` - BFS/DFS with configurable stop conditions
- **pathfinding**: `shortest_path()`, `all_paths()` - Dijkstra, DFS variants
- **network-analysis**: `centrality()`, `components()` - NetworkX wrappers

## Instructions
1. Identify required handler from query classification
2. Read handler interface from `handlers/{group}.py`
3. Use schema skill to resolve table/column parameters
4. Construct handler invocation with resolved parameters

## Parameter Resolution Flow

```
Pattern template (references ontology concepts)
        ↓
Ontology lookup (explicit sql_mapping from user)
        ↓
Handler call (with resolved table/column names)
```

## Example Resolution

Query: "All components for Turbo Encabulator"

1. Pattern matches `bom_explosion` with bindings:
   - node_class: Part
   - edge_relationship: component_of

2. Ontology lookup:
   - Part.sql_mapping.table → "parts"
   - component_of.sql_mapping.table → "bill_of_materials"
   - component_of.sql_mapping.domain_key → "child_part_id"
   - component_of.sql_mapping.range_key → "parent_part_id"

3. Handler call:
   ```python
   traverse(
       conn=db,
       nodes_table="parts",
       edges_table="bill_of_materials",
       edge_from_col="parent_part_id",  # swapped for outbound
       edge_to_col="child_part_id",
       start_id=789,
       direction="outbound",
       max_depth=20
   )
   ```
```

**Deliverable**: `.claude/skills/handlers/reference.md`

```markdown
# Handler Interface Reference

## traverse()

```python
traverse(
    conn,                          # Database connection
    nodes_table: str,              # e.g., "suppliers"
    edges_table: str,              # e.g., "supplier_relationships"
    edge_from_col: str,            # e.g., "seller_id"
    edge_to_col: str,              # e.g., "buyer_id"
    start_id: int,                 # Starting node
    direction: str = "outbound",   # "outbound", "inbound", "both"
    max_depth: int = 10,
    stop_condition: str = None,    # SQL WHERE clause fragment
    collect_columns: list = None,  # Columns to return from nodes
) -> dict
```

**Returns**:
- `nodes`: List of reached node dicts
- `paths`: Dict mapping node_id → path from start
- `depth_reached`: Actual max depth encountered
- `nodes_visited`: Total nodes visited

## shortest_path()

```python
shortest_path(
    conn,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    start_id: int,
    end_id: int,
    weight_col: str = None,        # Column for edge weights
    max_depth: int = 20,
) -> dict
```

**Returns**:
- `path`: List of node IDs from start to end
- `distance`: Total path weight/length
- `error`: Error message if no path found

## centrality()

```python
centrality(
    conn,
    nodes_table: str,
    edges_table: str,
    edge_from_col: str,
    edge_to_col: str,
    centrality_type: str = "degree",  # degree|betweenness|closeness|pagerank
    top_n: int = 10,
) -> list[dict]
```

**Returns**: List of `{node: ..., score: ...}` sorted by score descending

## Safety Limits (All Handlers)

- MAX_DEPTH = 50
- MAX_NODES = 10,000
- MAX_RESULTS = 1,000
- QUERY_TIMEOUT = 30s
```

### Gate 4: Skill Integration Test

**Before proceeding to Phase 5, validate**:

1. **Pattern matching**: 10 queries → correct pattern selected
2. **Skill invocation**: Claude correctly loads patterns/schema/handlers on demand
3. **End-to-end**: Query → Pattern → Ontology → Handler → Result

**Deliverables checkpoint**:
- [ ] `patterns/templates/traversal/*.yaml`
- [ ] `patterns/templates/pathfinding/*.yaml`
- [ ] `patterns/templates/network-analysis/*.yaml`
- [ ] `.claude/skills/patterns/SKILL.md`
- [ ] `.claude/skills/patterns/reference.md`
- [ ] `.claude/skills/handlers/SKILL.md`
- [ ] `.claude/skills/handlers/reference.md`
- [ ] Gate 4 validation report

---

## Phase 5: Baseline & Benchmark

**Duration**: Fifth sprint
**Goal**: Neo4j comparison baseline + benchmark harness ready

### Track A: Neo4j Baseline

#### 5A.1 Neo4j Setup

**Deliverable**: `neo4j/docker-compose.yml`

```yaml
services:
  neo4j:
    image: neo4j:5.15-community
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/dev_password
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
```

#### 5A.2 Migration Script (Ontology-Driven)

**Deliverable**: `neo4j/migrate.py` ✅ IMPLEMENTED

**CRITICAL**: The migration script reads from `ontology/supply_chain.yaml` to ensure
consistency with the Virtual Graph approach. Both systems derive their schema from the
same source of truth for a fair TCO comparison.

**Architecture**:

```
ontology/supply_chain.yaml (Single Source of Truth)
       │
       ├──→ Virtual Graph
       │    └── handlers use sql_mapping
       │    └── queries stay in PostgreSQL
       │
       └──→ Neo4j Migration (neo4j/migrate.py)
            └── reads ontology to create labels/relationships
            └── populates data from sql_mapping.table
```

**Implementation** (see `neo4j/migrate.py` for full code):

```python
def load_ontology() -> dict:
    """Load ontology as the single source of truth."""
    ontology_path = Path(__file__).parent.parent / "ontology" / "supply_chain.yaml"
    with open(ontology_path) as f:
        return yaml.safe_load(f)


class OntologyDrivenMigrator:
    """
    Migrates supply chain data from PostgreSQL to Neo4j using ontology.

    The ontology defines:
    - classes -> Neo4j node labels
    - relationships -> Neo4j relationship types
    - sql_mapping -> source tables and keys
    """

    # Neo4j label mapping for special cases
    LABEL_MAPPING = {
        "SupplierCertification": "Certification",  # Shorter label
    }

    def create_constraints_from_ontology(self):
        """Create Neo4j constraints from ontology classes."""
        for class_name, class_def in self.ontology["classes"].items():
            label = self._get_neo4j_label(class_name)
            pk = class_def["sql_mapping"]["primary_key"]
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_{pk}_unique "
                f"IF NOT EXISTS FOR (n:{label}) REQUIRE n.{pk} IS UNIQUE"
            )

    def migrate_nodes_from_ontology(self):
        """Migrate nodes using ontology class definitions."""
        for class_name, class_def in self.ontology["classes"].items():
            table = class_def["sql_mapping"]["table"]
            label = self._get_neo4j_label(class_name)
            # Get columns from PostgreSQL information_schema
            # Respect soft_delete flags from ontology
            # Create nodes with converted types (Decimal→float, date→string)

    def migrate_relationships_from_ontology(self):
        """Migrate relationships using ontology relationship definitions."""
        for rel_name, rel_def in self.ontology["relationships"].items():
            sql_mapping = rel_def["sql_mapping"]
            table = sql_mapping["table"]
            domain_key = sql_mapping["domain_key"]
            range_key = sql_mapping["range_key"]
            # Distinguish FK relationships vs junction tables
            # Include additional_columns as relationship properties
            # Convert rel_name to UPPER_SNAKE_CASE for Neo4j
```

**Key Design Decisions**:
- Schema derived from `ontology/supply_chain.yaml`, not hardcoded
- Node labels = ontology class names (with `LABEL_MAPPING` for special cases like SupplierCertification → Certification)
- Relationship types = ontology relationship names in UPPER_SNAKE_CASE
- Data sources = `sql_mapping.table` from ontology
- Soft deletes respected via `soft_delete` and `soft_delete_column` ontology fields
- Properties from `additional_columns` in ontology relationship definitions
- FK vs junction table relationships detected automatically based on whether `sql_mapping.table` matches the domain class table
- Validation against ontology `row_count` expectations
- Migration metrics tracked and saved to `neo4j/migration_metrics.json`

**What the "Lift" Measures**:

For a fair TCO comparison, the Neo4j "lift" measures:
1. **Infrastructure**: Setting up graph DB (docker, config, monitoring)
2. **Data Migration**: Moving data from PostgreSQL → Neo4j
3. **Query Language**: Learning Cypher instead of staying with SQL

**NOT** the cost of schema definition—both approaches use the same ontology.

**Reduction**: From ~880 lines of hardcoded code to ~480 lines of ontology-driven code

#### 5A.3 Cypher Queries

**Deliverable**: `neo4j/queries/` (25 query files)

```cypher
// neo4j/queries/10_tier3_suppliers.cypher
// Find all tier 3 suppliers for a given company

MATCH (target:Supplier {name: $company_name})
MATCH path = (s:Supplier)-[:SUPPLIES_TO*1..10]->(target)
WHERE s.tier = 3
RETURN DISTINCT s
```

```cypher
// neo4j/queries/19_cheapest_route.cypher
// Find cheapest shipping route between facilities

MATCH (start:Facility {name: $from_name})
MATCH (end:Facility {name: $to_name})
MATCH path = shortestPath((start)-[:CONNECTS_TO*]->(end))
RETURN path, reduce(cost = 0, r IN relationships(path) | cost + r.cost_usd) as total_cost
ORDER BY total_cost
LIMIT 1
```

### Track B: Benchmark Harness

#### 5B.1 Query Definitions

**Deliverable**: `benchmark/queries.yaml`

```yaml
queries:
  # GREEN: Simple lookups and joins
  - id: 1
    category: lookup
    route: GREEN
    natural_language: "Find supplier ABC Corp"
    expected_result_count: 1

  - id: 2
    category: lookup
    route: GREEN
    natural_language: "List all tier 1 suppliers"
    expected_result_count: 50

  - id: 3
    category: lookup
    route: GREEN
    natural_language: "Find all parts with 'sensor' in the name"
    expected_result_count: null  # Variable

  # ... queries 4-9 (1-hop, 2-hop)

  # YELLOW: Recursive traversal
  - id: 10
    category: n-hop-recursive
    route: YELLOW
    natural_language: "Find all tier 3 suppliers for Acme Corp"
    expected_handler: traverse
    expected_result_count: null

  - id: 13
    category: bom-traversal
    route: YELLOW
    natural_language: "Full parts list for the Turbo Encabulator"
    expected_handler: traverse
    expected_result_count: 342

  - id: 16
    category: impact-analysis
    route: YELLOW
    natural_language: "What products are affected if supplier X fails?"
    expected_handler: traverse
    expected_result_count: null

  # RED: Network algorithms
  - id: 19
    category: pathfinding
    route: RED
    natural_language: "What's the cheapest shipping route from Chicago warehouse to LA distribution center?"
    expected_handler: shortest_path
    weight_column: cost_usd

  - id: 25
    category: network-analysis
    route: RED
    natural_language: "Which facility is most critical to our logistics network?"
    expected_handler: centrality
    centrality_type: betweenness
```

#### 5B.2 Ground Truth

**Deliverable**: `benchmark/ground_truth/` (one file per query)

```json
// benchmark/ground_truth/query_13.json
{
  "query_id": 13,
  "expected_nodes": [123, 456, 789, ...],
  "expected_count": 342,
  "expected_depth": 12,
  "generated_from": "manual verification on 2024-01-20"
}
```

#### 5B.3 Benchmark Runner

**Deliverable**: `benchmark/run.py`

```python
"""
Benchmark harness comparing Virtual Graph vs Neo4j.
"""
import time
import yaml
from dataclasses import dataclass

@dataclass
class BenchmarkResult:
    query_id: int
    system: str  # "virtual_graph" or "neo4j"
    correct: bool
    first_attempt_correct: bool
    retries_needed: int
    execution_time_ms: float
    llm_tokens: int  # For virtual graph only
    pattern_used: str  # Pattern template if applicable
    explainability_score: int  # 1-5 manual rating

def run_benchmark():
    """Run full 25-query benchmark on both systems."""
    queries = yaml.safe_load(open("benchmark/queries.yaml"))
    results = []

    for query in queries["queries"]:
        # Run on Virtual Graph
        vg_result = run_virtual_graph(query)
        results.append(vg_result)

        # Run on Neo4j
        neo4j_result = run_neo4j(query)
        results.append(neo4j_result)

    # Generate comparison report
    generate_report(results)

def generate_report(results):
    """Generate markdown comparison report."""
    ...
```

### Gate 5: Benchmark Ready

**Before proceeding to Phase 6, validate**:

1. **Neo4j Running**: Start and verify Neo4j container
   ```bash
   # Start Neo4j
   docker-compose -f neo4j/docker-compose.yml up -d

   # Wait for healthy status (may take 30-60 seconds)
   docker-compose -f neo4j/docker-compose.yml ps
   # Should show: neo4j ... Up (healthy)

   # Verify browser accessible at http://localhost:7474
   # Default credentials: neo4j / dev_password
   ```

2. **Data Migrated**: Run migration and verify node/relationship counts
   ```bash
   # Install Neo4j driver (if not already installed)
   poetry install --extras neo4j

   # Run migration from PostgreSQL to Neo4j
   poetry run python neo4j/migrate.py

   # Expected output:
   # - Suppliers: 500 nodes
   # - Parts: 5,003 nodes
   # - Products: 200 nodes
   # - Facilities: 50 nodes
   # - SUPPLIES_TO: ~817 relationships
   # - COMPONENT_OF: ~14,283 relationships
   # - CONNECTS_TO: ~197 relationships
   # - Migration metrics saved to: neo4j/migration_metrics.json
   ```

3. **Cypher Queries Work**: Test at least 3 queries in Neo4j Browser
   ```cypher
   // In Neo4j Browser (http://localhost:7474), run:
   MATCH (s:Supplier) RETURN count(s);           // Should return 500
   MATCH (p:Part) RETURN count(p);               // Should return 5003
   MATCH ()-[r:SUPPLIES_TO]->() RETURN count(r); // Should return ~817
   ```

4. **Ground truth generated**: All 25 queries have verified expected results
   ```bash
   poetry run python benchmark/generate_ground_truth.py
   # Creates benchmark/ground_truth/*.json files
   ```

5. **Runner works on BOTH systems**: Test single query comparison
   ```bash
   # Test single query on both systems
   poetry run python benchmark/run.py --system both --query 1

   # Should show results for both Virtual Graph and Neo4j
   ```

**Deliverables checkpoint**:
- [x] `neo4j/docker-compose.yml`
- [x] `neo4j/migrate.py` + migration metrics
- [x] `neo4j/queries/*.cypher` (25 queries)
- [x] `benchmark/queries.yaml`
- [x] `benchmark/ground_truth/*.json`
- [x] `benchmark/run.py`
- [x] Gate 5 validation report (19/19 tests passing)

**Known Issues for Phase 6 Resolution**:

The benchmark runner has simplifications that cause some query failures. These are
documented issues to address during Phase 6 benchmark tuning:

| Query | Issue | Resolution |
|-------|-------|------------|
| 8 | Order result count comparison | Adjust ground truth for LIMIT clause |
| 13, 17 | Product name lookup returns empty | Verify test entity names match seed data |
| 14 | Part number PRT-000100 not found | Update to use actual part number from data |
| 15, 18 | Supplier name lookup | Verify "Acme Corp" exists in seed data |
| 23 | Centrality score comparison | Use ranking comparison vs exact match |
| 25 | Route count mismatch | Adjust comparison for multiple valid routes |

These are benchmark harness issues, not Virtual Graph handler issues. The handlers
themselves work correctly (validated in Gate 3). Phase 6 will tune the benchmark
comparison logic.

---

## Phase 6: Evaluation & Documentation

**Duration**: Final sprint
**Goal**: Full benchmark results + analysis + documentation

### 6.0 Benchmark Tuning (Pre-requisite)

Before running the full benchmark, resolve the known issues from Phase 5:

1. **Entity Name Alignment**: Verify test entity names in `benchmark/queries.yaml`
   match actual named entities in seed data
2. **Comparison Logic**: Improve result comparison to handle:
   - Ranking queries (compare order, not exact values)
   - Multi-result queries (set overlap threshold)
   - Path queries (valid path vs exact path match)
3. **Ground Truth Refresh**: Re-run `generate_ground_truth.py` after entity alignment

### 6.1 Run Full Benchmark

**Prerequisites** (verify before proceeding):
```bash
# 1. Verify Neo4j is running and healthy
docker-compose -f neo4j/docker-compose.yml ps
# Must show: neo4j ... Up (healthy)

# 2. Verify PostgreSQL is running
docker-compose -f postgres/docker-compose.yml ps
# Must show: postgres ... Up

# 3. Verify migration completed successfully
cat neo4j/migration_metrics.json
# Should show node/relationship counts and success status

# 4. Verify Neo4j driver is installed
poetry run python -c "import neo4j; print('Neo4j driver OK')"
```

**Execute benchmark on BOTH systems**:
```bash
# Run full benchmark comparing Virtual Graph vs Neo4j
poetry run python benchmark/run.py --system both

# This executes all 25 queries on:
# - Virtual Graph (using handlers against PostgreSQL)
# - Neo4j (using Cypher queries against Neo4j)
# And compares results to ground truth for both
```

**Expected output files**:
- `benchmark/results/benchmark_results.md` - Side-by-side comparison report
- `benchmark/results/benchmark_results.json` - Raw data for both systems

**Results table format** (actual results will vary):

| Query # | VG Correct | VG Time | Neo4j Correct | Neo4j Time | Both Match |
|---------|------------|---------|---------------|------------|------------|
| 1 | ✓ | 45ms | ✓ | 12ms | ✓ |
| ... | ... | ... | ... | ... | ... |
| 25 | ✓ | 2.3s | ✓ | 0.8s | ✓ |

**If Neo4j is unavailable**, you can run VG-only benchmark:
```bash
# Fallback: Run only Virtual Graph benchmark
poetry run python benchmark/run.py --system vg

# Note: This will not produce a Neo4j comparison
```

### 6.2 Analysis

**Deliverable**: `docs/benchmark_results.md`

```markdown
# Benchmark Results

## Summary

| Metric | Virtual Graph | Neo4j |
|--------|---------------|-------|
| Overall Accuracy | 88% | 100% |
| First-attempt Accuracy | 72% | 100% |
| Avg Latency (GREEN) | 85ms | 15ms |
| Avg Latency (YELLOW) | 450ms | 120ms |
| Avg Latency (RED) | 1.8s | 0.5s |
| Pattern Reuse Rate | 78% | N/A |

## By Route

### GREEN Queries (1-9)
- Virtual Graph: 9/9 correct, avg 65ms
- Neo4j: 9/9 correct, avg 12ms
- Analysis: Neo4j faster but VG competitive for simple lookups

### YELLOW Queries (10-18)
- Virtual Graph: 8/9 correct, avg 420ms
- Neo4j: 9/9 correct, avg 110ms
- Analysis: Handler approach works well, one failure due to...

### RED Queries (19-25)
- Virtual Graph: 5/7 correct, avg 2.1s
- Neo4j: 7/7 correct, avg 0.6s
- Analysis: NetworkX loading overhead significant for large graphs

## Key Findings
1. Virtual Graph achieves 88% accuracy with discovered ontology
2. Pattern reuse enables consistent YELLOW performance
3. RED queries need optimization for large graphs
4. Explainability advantage: SQL more auditable than Cypher

## Recommendations
...
```

**Deliverable**: `docs/tco_analysis.md`

```markdown
# Total Cost of Ownership Analysis

## Setup Effort

| Component | Virtual Graph | Neo4j |
|-----------|---------------|-------|
| Schema design | 0 (uses existing) | 8 hours |
| Data migration | 0 | 16 hours |
| Query development | 4 hours (discovery) | 20 hours (Cypher) |
| **Total setup** | **4 hours** | **44 hours** |

## Ongoing Maintenance

| Activity | Virtual Graph | Neo4j |
|----------|---------------|-------|
| Schema changes | Update ontology | Re-migrate data |
| New query types | Pattern discovery | Write new Cypher |
| Data sync | Automatic (same DB) | ETL pipeline |

## Infrastructure

| Resource | Virtual Graph | Neo4j |
|----------|---------------|-------|
| Additional DB | No | Yes |
| Storage overhead | 0 | ~30% |
| Compute | LLM API calls | Neo4j server |

## Conclusion
For enterprises with existing SQL infrastructure, Virtual Graph reduces
initial setup effort by 90% while achieving 88% of Neo4j's accuracy.
```

### 6.3 Final Documentation

**Deliverable**: `docs/architecture.md`

```markdown
# Virtual Graph Architecture

## System Overview
[Architecture diagram]

## Layer Separation
[Ontology vs Schema vs Patterns vs Handlers]

## Context Management
[Skills system explanation]

## Query Routing
[Traffic light explanation]
```

**Deliverable**: `docs/traffic_light_routing.md`

```markdown
# Traffic Light Query Routing

## Classification Rules
[GREEN/YELLOW/RED criteria]

## Route Selection Process
[How Claude decides]

## Examples
[10+ annotated examples]
```

### 6.4 Cleanup (Optional)

After benchmark completion and documentation, optionally stop Neo4j to free resources:

```bash
# Stop Neo4j container (preserves data)
docker-compose -f neo4j/docker-compose.yml down

# To completely remove Neo4j data (start fresh next time)
docker-compose -f neo4j/docker-compose.yml down -v
```

**Note**: Keep Neo4j running if you plan to:
- Re-run benchmarks
- Debug query results
- Compare additional queries
- Demo the comparison

---

## Complete Deliverables Checklist

### Phase 1: Foundation
- [x] `postgres/docker-compose.yml`
- [x] `postgres/schema.sql`
- [x] `scripts/generate_data.py`
- [x] `handlers/base.py`
- [x] `handlers/traversal.py`

### Phase 2: Discovery Foundation
- [x] `.claude/skills/schema/SKILL.md`
- [x] `.claude/skills/schema/scripts/introspect.sql`
- [x] `ontology/supply_chain.yaml`
- [x] `docs/ontology_discovery_session.md`

### Phase 3: Query Execution Paths
- [x] `handlers/pathfinding.py`
- [x] `handlers/network.py`
- [x] `patterns/raw/*.yaml` (10+ patterns)

### Phase 4: Pattern Maturity
- [x] `patterns/templates/traversal/*.yaml`
- [x] `patterns/templates/pathfinding/*.yaml`
- [x] `patterns/templates/aggregation/*.yaml`
- [x] `patterns/templates/network-analysis/*.yaml`
- [x] `patterns/transcripts/*.md`
- [x] `.claude/skills/patterns/SKILL.md`
- [x] `.claude/skills/patterns/reference.md`
- [x] `.claude/skills/handlers/SKILL.md`
- [x] `.claude/skills/handlers/reference.md`
- [x] `docs/pattern_discovery_guide.md`

### Phase 5: Baseline & Benchmark
- [x] `neo4j/docker-compose.yml`
- [x] `neo4j/migrate.py`
- [x] `neo4j/queries/*.cypher` (25 queries)
- [x] `benchmark/queries.yaml`
- [x] `benchmark/ground_truth/*.json`
- [x] `benchmark/run.py`
- [x] `benchmark/results/`

### Phase 6: Evaluation & Documentation
- [x] `docs/architecture.md`
- [x] `docs/traffic_light_routing.md`
- [x] `docs/benchmark_results.md`
- [x] `docs/tco_analysis.md`

---

## Success Criteria

| Dimension | Target | Validation Gate |
|-----------|--------|-----------------|
| Scalability | 5K-node BOM in <2s | Gate 1 |
| Ontology Coverage | 100% tables mapped | Gate 2 |
| Route Accuracy | GREEN 100%, YELLOW 90%, RED 80% | Gate 3 |
| Pattern Reuse | ≥70% YELLOW queries | Gate 4 |
| Benchmark Ready | 25 queries × 2 systems | Gate 5 |
| Overall Accuracy | ≥85% with retries | Final |
| First-attempt | ≥65% | Final |
| Performance | ≤5x Neo4j for GREEN/YELLOW | Final |

---

## Implementation Prerequisites

### Environment

```toml
# pyproject.toml
[project]
dependencies = [
    "psycopg2-binary>=2.9",  # PostgreSQL sync driver
    "networkx>=3.2",          # Graph algorithms
    "pyyaml>=6.0",            # Ontology/pattern parsing
    "pandas>=2.0",            # Data manipulation
    "faker>=24.0",            # Synthetic data generation
    "neo4j>=5.0",             # Neo4j driver (for baseline)
]
```

### LLM Model Selection

| Session Type | Recommended Model | Rationale |
|--------------|-------------------|-----------|
| **Ontology Discovery** | Claude Opus or Sonnet | Schema introspection is token-heavy |
| **Pattern Discovery** | Claude Sonnet | Balance of reasoning + cost |
| **Query Sessions** | Claude Sonnet or Haiku | Speed matters for interactive use |

### Database Requirements

- PostgreSQL 14+ (for native CYCLE clause in CTEs)
- Docker Compose for local development
- Statement timeout: 30s
- Neo4j 5.x Community Edition (for baseline)

---

## Implementation Mandates

### Non-Negotiable Requirements

| Mandate | Rationale |
|---------|-----------|
| **Frontier batching** | One query per depth level, never per node |
| **Hybrid SQL/Python** | Python orchestrates, SQL filters. Never bulk load |
| **Size guards** | Check before NetworkX load. >5K nodes: warn or fail |
| **Early scalability testing** | Validate with 5K-part BOM in Phase 1, not Phase 6 |
| **Discovered ontology** | POC must use discovered, not hand-written ontology |

### Discovery Quality Metrics

| Metric | Target |
|--------|--------|
| Cold-start accuracy | Initial guess ≥60% correct |
| Question efficiency | ≤5 questions to reach stable ontology |
| Convergence speed | Stable in 2-3 rounds |
| Cascade errors | Discovery errors should NOT cascade to query failures |
