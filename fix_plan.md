# Fix Plan: Ontology-Driven Neo4j Migration

## Problem Statement

The current `neo4j/migrate.py` has the graph schema **hardcoded** independently of the ontology. For a fair TCO comparison between Virtual Graph and Neo4j, both approaches must derive from the **same source of truth**: `ontology/supply_chain.yaml`.

### Current State (Incorrect)
```
PostgreSQL Schema
       │
       ├──→ Virtual Graph: uses ontology/supply_chain.yaml
       │
       └──→ Neo4j Migration: hardcoded schema in migrate.py (WRONG)
```

### Target State (Correct)
```
ontology/supply_chain.yaml (Single Source of Truth)
       │
       ├──→ Virtual Graph
       │    └── handlers use sql_mapping
       │    └── queries stay in PostgreSQL
       │
       └──→ Neo4j Migration
            └── reads ontology to create labels/relationships
            └── populates data from sql_mapping.table
```

## What the "Lift" Actually Is

For a fair comparison, the Neo4j "lift" should measure:
1. **Infrastructure**: Setting up graph DB (docker, config, monitoring)
2. **Data Migration**: Moving data from PostgreSQL → Neo4j
3. **Query Language**: Learning Cypher instead of staying with SQL

**NOT**: Manually defining a schema (both should use the same ontology)

## Fix Steps

### Step 1: Refactor `neo4j/migrate.py`

Replace hardcoded schema with ontology-driven approach:

```python
"""
Ontology-driven migration from PostgreSQL to Neo4j.

Reads schema from ontology/supply_chain.yaml to ensure
consistency with Virtual Graph approach.
"""
import yaml
from pathlib import Path

def load_ontology() -> dict:
    """Load ontology as the single source of truth."""
    ontology_path = Path(__file__).parent.parent / "ontology" / "supply_chain.yaml"
    with open(ontology_path) as f:
        return yaml.safe_load(f)

def create_constraints_from_ontology(session, ontology: dict):
    """Create Neo4j constraints from ontology classes."""
    for class_name, class_def in ontology["classes"].items():
        pk = class_def["sql_mapping"]["primary_key"]
        session.run(
            f"CREATE CONSTRAINT {class_name.lower()}_{pk}_unique "
            f"IF NOT EXISTS FOR (n:{class_name}) REQUIRE n.{pk} IS UNIQUE"
        )

def migrate_nodes_from_ontology(pg_conn, neo4j_session, ontology: dict):
    """Migrate nodes using ontology class definitions."""
    for class_name, class_def in ontology["classes"].items():
        table = class_def["sql_mapping"]["table"]
        # Build SELECT from attributes defined in ontology
        # Handle soft_delete if specified
        # Create nodes with class_name as label
        ...

def migrate_relationships_from_ontology(pg_conn, neo4j_session, ontology: dict):
    """Migrate relationships using ontology relationship definitions."""
    for rel_name, rel_def in ontology["relationships"].items():
        sql_mapping = rel_def["sql_mapping"]
        table = sql_mapping["table"]
        domain_key = sql_mapping["domain_key"]
        range_key = sql_mapping["range_key"]
        # Convert rel_name to UPPER_SNAKE_CASE
        neo4j_rel_type = rel_name.upper()
        # Include additional_columns as relationship properties
        ...
```

### Step 2: Update `implementation_plan3.md` Phase 5A.2

Replace the hardcoded migration example with ontology-driven approach.

### Step 3: Execute Operations

After code fix:
1. Start Neo4j container
2. Run ontology-driven migration
3. Verify counts match ontology expectations
4. Run benchmark with `--system both`
5. Update documentation with comparison results

## Files to Modify

| File | Change |
|------|--------|
| `neo4j/migrate.py` | Refactor to read from ontology |
| `implementation_plan3.md` | Update Section 5A.2 with ontology-driven approach |

## Files to Create/Update After Fix

| File | Action |
|------|--------|
| `neo4j/migration_metrics.json` | Created by running migration |
| `benchmark/results/benchmark_results.md` | Updated with VG vs Neo4j comparison |
| `benchmark/results/benchmark_results.json` | Updated with both systems' data |
| `docs/benchmark_results.md` | Updated with comparative analysis |
| `docs/tco_analysis.md` | Updated with actual migration metrics |

## Success Criteria

- [x] `neo4j/migrate.py` reads from `ontology/supply_chain.yaml`
- [x] Node labels match ontology `classes` names
- [x] Relationship types match ontology `relationships` names (UPPER_SNAKE_CASE)
- [x] Data sources come from `sql_mapping.table`
- [x] Neo4j node counts match ontology `row_count` values
- [x] Benchmark runs on BOTH systems with `--system both`
- [x] Results show side-by-side VG vs Neo4j comparison
- [x] `implementation_plan3.md` is consistent with this fix

**All criteria verified on 2025-12-04**

## Architectural Consistency Check

After fix, verify:

| Ontology Class | Neo4j Label | Expected Count |
|----------------|-------------|----------------|
| Supplier | :Supplier | 500 |
| Part | :Part | 5003 |
| Product | :Product | 200 |
| Facility | :Facility | 50 |
| Customer | :Customer | 1000 |
| Order | :Order | 20000 |
| Shipment | :Shipment | 7995 |
| SupplierCertification | :Certification | 721 |

| Ontology Relationship | Neo4j Type | Expected Count |
|-----------------------|------------|----------------|
| supplies_to | SUPPLIES_TO | 817 |
| component_of | COMPONENT_OF | 14283 |
| connects_to | CONNECTS_TO | 197 |
| can_supply | CAN_SUPPLY | 7582 |
| contains_component | CONTAINS_COMPONENT | 619 |
| contains_item | CONTAINS_ITEM | 60241 |
| stores_at | STORES_AT | 10056 |

## Execution Order

1. **Code Change**: Refactor `neo4j/migrate.py` to use ontology
2. **Doc Update**: Update `implementation_plan3.md` Section 5A.2
3. **Start Neo4j**: `docker-compose -f neo4j/docker-compose.yml up -d`
4. **Run Migration**: `poetry run python neo4j/migrate.py`
5. **Verify**: Check counts in Neo4j Browser
6. **Benchmark**: `poetry run python benchmark/run.py --system both`
7. **Document**: Update benchmark results and TCO analysis
