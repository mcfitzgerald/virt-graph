# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Python environment and dependencies managed by poetry

Always use poetry to run python for this project

## Coding and Engineering Standards

Employ a judicious but robust testing strategy, and prefer integration tests versus unit tests unless unit test is critical

Always use context7 when I need code generation, setup or configuration steps (unless already documented in codebase), or
library/API documentation. This means you should automatically use the Context7 MCP
tools to resolve library id and get library docs without me having to explicitly ask.

Don't reinvent the wheel, search web for robust libraries and always opt for simple. Don't over-engineer!

Update `CHANGELOG.md`, `README.md`, and `pyproject.toml` and relevant documentation (`docs/`) when committing with git, use semantic versioning

Unless noted otherwise, do not plan for backwards compatibility

## Project Overview

VG/SQL ("VeeJee over Sequel") enables graph-like queries over relational SQL data WITHOUT migration. It combines:
1. An **ontology** in LinkML format mapping graph concepts to relational structures
2. **Python handlers** for recursive traversal and graph algorithms
3. **Claude Code** for orchestration and on-the-fly query generation

## Common Commands

```bash
# Setup
make install          # Install Python dependencies via Poetry

# Ontology validation
make validate-ontology  # Full two-layer validation (LinkML + VG)
make show-ontology      # Show TBox/RBox definitions

# Testing
make test-ontology      # Run ontology validation tests
poetry run pytest pcg_example/tests/ -v  # All tests

# Neo4j (for benchmarking)
make neo4j-up         # Start Neo4j
make neo4j-down       # Stop Neo4j
make neo4j-cycle      # Full reset (fixes PID issues)

# Documentation
make serve-docs       # Serve docs at localhost:8000
```

## Architecture

### Core Components

```
src/virt_graph/
├── ontology.py           # OntologyAccessor - reads LinkML ontology with VG extensions
├── handlers/             # Graph operation handlers
│   ├── base.py           # Safety limits, edge fetching, result TypedDicts
│   ├── traversal.py      # traverse(), path_aggregate(), traverse_collecting()
│   ├── pathfinding.py    # shortest_path(), all_shortest_paths()
│   └── network.py        # centrality(), connected_components(), resilience_analysis()
└── estimator/            # Runtime estimation and guards
    ├── sampler.py        # Graph sampling for property detection
    ├── models.py         # Estimation models with damping
    ├── bounds.py         # DDL-derived table statistics
    └── guards.py         # Runtime safety guards
```

### Schema Layers

```
virt_graph.yaml     ← VG extension vocabulary (domain-agnostic metamodel)
scm_base.yaml       ← Supply chain structural patterns (slots, enums, abstract classes, mixins)
pcg_example/
  ontology/
    pcg.yaml        ← Domain ontology (imports scm_base, uses is_a/mixins, has VG annotations)
```

**`scm_base.yaml`** provides reusable patterns: abstract classes (`Location`, `TransactionDocument`, `LineItem`), mixins (`HasActiveFlag`, `HasName`), shared slots, and `LocationType` enum. Domain ontologies import it via `imports: ../../scm_base`.

**`OntologyAccessor`** loads `SchemaView(merge_imports=True)` alongside raw YAML. Use `get_class_inherited_attributes(name)` to see all attributes including inherited ones.

### Key Concepts

**Two-layer validation**: Ontologies are validated first by LinkML (structure) then by VG metamodel (`virt_graph.yaml`) for required annotations.

**Operation types**: Relationships in the ontology declare which operations they support:
- `direct_join` → Standard SQL
- `recursive_traversal` → `traverse()` handler
- `path_aggregation`, `hierarchical_aggregation` → `path_aggregate()` handler
- `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` → Network handlers
- `flow_analysis`, `state_analysis`, `scenario_analysis` → Kinetic (ad-hoc SQL via Claude)

**Handler pattern**: All handlers are schema-parameterized—they take table/column names as arguments, not hardcoded SQL. Example:
```python
traverse(conn, nodes_table="skus", edges_table="skus",
         edge_from_col="id", edge_to_col="supersedes_sku_id", start_id=sku_id)
```

### Reference Ontology

`pcg_example/ontology/pcg.yaml` — PCG ERP supply chain ontology (38 classes, 50 relationships).

**Graph operations declared in the ontology:**

| Graph Pattern | Relationships | Operation Types | Handler |
|---|---|---|---|
| Transport network | `RouteSegmentOrigin`, `RouteSegmentDestination` | `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` | `shortest_path()`, `centrality()`, etc. |
| SKU alias chain | `SKUSupersedes` | `recursive_traversal` | `traverse()` |
| BOM explosion | `FormulaHasIngredients` | `path_aggregation`, `hierarchical_aggregation` | `path_aggregate()` |
| All other FKs | 47 relationships | `direct_join` | SQL joins |

**Polymorphic relationships** (5 with `type_discriminator`): `BatchProducesProduct`, `FormulaForProduct`, `RouteSegmentOrigin`, `RouteSegmentDestination`, `InventoryAtLocation`. Two more (`ShipmentFromOrigin`, `ShipmentToDestination`) are polymorphic without a clean discriminator column — use `vg:context` blocks instead.

**Edge attributes** on 3 junction tables: `SupplierOffersIngredient` (unit_cost, lead_time_days, min_order_qty), `FormulaHasIngredients` (sequence, quantity_kg), `BatchConsumesIngredient` (quantity_kg).

**Context blocks** on 6 entities (Batch, Order, Shipment, Inventory, RouteSegment, GLJournal) and 6 relationships — provide domain semantics for query generation.

### Database Access

Use `psycopg2` for PostgreSQL (psql CLI may not be available):
```python
import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, database='prism_fmcg',
                        user='virt_graph', password='dev_password')
```

## Metamodel

`virt_graph.yaml` (v3.0) is the single source of truth for VG extensions. The two core extension classes:
- `SQLMappedClass` (TBox): requires `vg:table`, `vg:primary_key`
- `SQLMappedRelationship` (RBox): requires `vg:edge_table`, `vg:domain_key`, `vg:range_key`, `vg:operation_types`

**Features used in the PCG ontology:**

| Feature | Annotation | Where Used |
|---|---|---|
| Polymorphism | `vg:type_discriminator` + `vg:range_class` as list | 5 relationships (BatchProducesProduct, FormulaForProduct, RouteSegment*, InventoryAtLocation) |
| Edge weights | `vg:weight_columns` | RouteSegmentOrigin/Destination (distance_km, transit_time_hours) |
| Edge properties | `vg:edge_attributes` | SupplierOffersIngredient, FormulaHasIngredients, BatchConsumesIngredient |
| Edge filtering | `vg:sql_filter` | ProductionLineAtPlant (`is_active = true`) |
| AI context | `vg:context` | 6 entities + 6 relationships |
| State machines | `vg:state_machine` | PurchaseOrder, Order, Batch, Shipment, GoodsReceipt, Return |
| Flow config | `vg:flow_config` | 10 relationships (material/financial/information flows) |
| Axioms | `vg:axioms` | Mass balance, temporal ordering, GL balance constraints |
| Actions | `vg:actions` | What-if mutation docs on Batch, Order, Plant, etc. |
| Scenario params | `vg:scenario_params` | Perturbable attributes on Plant, Supplier, RouteSegment, etc. |
| OWL 2 axioms | `vg:functional`, `vg:acyclic`, etc. | SKUSupersedes (asymmetric, irreflexive, acyclic), many functional FKs |

See `docs/ontology/vg-extensions.md` for full reference.

## Working with Ontologies

The `OntologyAccessor` class provides the API for reading ontologies:
```python
from virt_graph.ontology import OntologyAccessor
from pathlib import Path

ontology = OntologyAccessor(Path("pcg_example/ontology/pcg.yaml"))

# Basic lookups
table = ontology.get_class_table("Supplier")       # → "suppliers"
pk = ontology.get_class_pk("Order")                # → ["id"]
op_types = ontology.get_operation_types("SKUSupersedes")  # → ["direct_join", "recursive_traversal"]
domain_keys, range_keys = ontology.get_role_keys("BatchConsumesIngredient")

# Graph structure (v2.0)
disc = ontology.get_role_type_discriminator("RouteSegmentOrigin")  # → {"column": "origin_type", "mapping": {...}}
poly = ontology.is_role_polymorphic("InventoryAtLocation")        # → True
weights = ontology.get_role_weight_columns("RouteSegmentOrigin")  # → [{"name": "distance_km", ...}]
attrs = ontology.get_role_edge_attributes("SupplierOffersIngredient")  # → [{"name": "unit_cost", ...}]
filt = ontology.get_role_filter("ProductionLineAtPlant")          # → "is_active = true"
ctx = ontology.get_role_context("FormulaHasIngredients")          # → {"business_logic": "...", ...}
ctx = ontology.get_class_context("RouteSegment")                  # → {"definition": "...", ...}

# Kinetic extensions (v3.0)
sm = ontology.get_class_state_machine("Order")     # → {"state_column": "status", ...}
axioms = ontology.get_class_axioms("Shipment")     # → [{"name": "temporal_order", ...}]
fc = ontology.get_role_flow_config("BatchConsumesIngredient")  # → {"flow_type": "material", ...}
actions = ontology.get_class_actions("Batch")       # → [{"name": "start_production", ...}]
params = ontology.get_class_scenario_params("Plant") # → [{"attribute": "capacity_tons_per_day", ...}]

# Discovery queries
ontology.get_classes_with_state_machines()          # → ["PurchaseOrder", "Order", ...]
ontology.get_roles_with_flow_config()               # → ["BatchConsumesIngredient", ...]
ontology.get_conservation_groups()                  # → {"procure_to_pay": [...], ...}
```
