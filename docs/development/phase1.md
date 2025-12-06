# Phase 1: Foundation

Phase 1 establishes the foundation for Virtual Graph with two parallel tracks:

- **Track A**: Database Infrastructure
- **Track B**: Handler Core

## Deliverables

### Track A: Database Infrastructure

| Deliverable | Status | Description |
|-------------|--------|-------------|
| `postgres/docker-compose.yml` | ✅ | PostgreSQL 14 development setup |
| `postgres/schema.sql` | ✅ | 15-table supply chain schema |
| `postgres/seed.sql` | ✅ | ~130K rows of synthetic data |
| `scripts/generate_data.py` | ✅ | Faker-based data generator |

### Track B: Handler Core

| Deliverable | Status | Description |
|-------------|--------|-------------|
| `handlers/base.py` | ✅ | Safety limits + batching utilities |
| `handlers/traversal.py` | ✅ | Frontier-batched BFS |

## Database Schema

The supply chain schema includes 15 tables with realistic "enterprise messiness":

### Design Note: Schema Comments and Realism

The schema file includes comments using graph terminology (e.g., "weighted edges", "self-referential edges"). This is a **realism trade-off**—a truly "found" enterprise schema would not have these helpful labels.

In a production deployment, this graph-awareness would come from:

1. **SME annotation**: A domain expert reviews the schema and identifies which junction tables represent traversable relationships. This is low-effort work—typically a few hours for a schema of this size.

2. **User input during discovery**: The Phase 2 ontology discovery session asks the user questions like "Which tables represent relationships between entities?" The LLM proposes candidates based on FK patterns; the user confirms or corrects.

Either approach requires minimal lift. The structural patterns (junction tables with dual FKs, self-referential relationships) are detectable automatically; the semantic labeling ("this is a supply chain tier relationship") requires human input.

For this POC, we embedded the labels in schema comments to accelerate development, but the discovery process in Phase 2 demonstrates how these patterns would be identified from raw introspection.

```
┌─────────────────┐      ┌─────────────────────────┐
│    suppliers    │◄────►│  supplier_relationships │
│  (500 rows)     │      │      (817 edges)        │
└────────┬────────┘      └─────────────────────────┘
         │
         │ primary_supplier_id
         ▼
┌─────────────────┐      ┌─────────────────────────┐
│     parts       │◄────►│    bill_of_materials    │
│  (5,003 rows)   │      │     (14,283 edges)      │
└────────┬────────┘      └─────────────────────────┘
         │
         │ part_id
         ▼
┌─────────────────┐      ┌─────────────────────────┐
│    products     │◄────►│   product_components    │
│   (200 rows)    │      │      (619 edges)        │
└─────────────────┘      └─────────────────────────┘

┌─────────────────┐      ┌─────────────────────────┐
│   facilities    │◄────►│    transport_routes     │
│   (50 rows)     │      │      (197 edges)        │
└─────────────────┘      └─────────────────────────┘
```

### Table Summary

| Table | Rows | Purpose |
|-------|------|---------|
| suppliers | 500 | Supplier entities (tiered) |
| supplier_relationships | 817 | T3→T2→T1 edges |
| parts | 5,003 | Component catalog |
| bill_of_materials | 14,283 | BOM hierarchy edges |
| part_suppliers | 7,582 | Alternate suppliers |
| products | 200 | Finished goods |
| product_components | 619 | Product→part links |
| facilities | 50 | Warehouses, factories |
| transport_routes | 197 | Logistics edges |
| inventory | 10,056 | Stock levels |
| customers | 1,000 | Customer entities |
| orders | 20,000 | Customer orders |
| order_items | 60,241 | Order line items |
| shipments | 7,995 | Order fulfillment |
| supplier_certifications | 721 | Quality certs |

## Handler Implementation

### Safety Infrastructure

```python
# Non-negotiable limits
MAX_DEPTH = 50          # Absolute traversal depth limit
MAX_NODES = 10_000      # Max nodes to visit
MAX_RESULTS = 1_000     # Max rows to return
QUERY_TIMEOUT_SEC = 30  # Per-query timeout
```

### Frontier Batching

The key implementation pattern - one query per depth:

```python
for depth in range(max_depth):
    # Single query for ALL nodes at this depth
    edges = fetch_edges_for_frontier(
        conn, edges_table, list(frontier),
        edge_from_col, edge_to_col, direction
    )
    # Process results...
```

### Size Estimation

Before traversing, estimate reachable nodes:

```python
estimated = estimate_reachable_nodes(
    conn, edges_table, start_id, max_depth,
    edge_from_col, edge_to_col, direction
)
if estimated > MAX_NODES:
    raise SubgraphTooLarge(...)
```

## Gate 1 Validation

Gate 1 validates Phase 1 deliverables with these tests:

### Test Results

| Test | Target | Result |
|------|--------|--------|
| BOM traversal performance | <2s | ✅ 0.006s |
| Safety limits trigger | Exception before overload | ✅ SubgraphTooLarge raised |
| Supplier DAG integrity | <5% back edges | ✅ 0% back edges |
| BOM depth | Avg ~5 levels | ✅ Avg 3.48, Max 5 |
| Transport connectivity | >90% connected | ✅ 100% connected |

### Running Tests

```bash
# All tests
poetry run pytest tests/test_gate1_validation.py -v

# Integration tests only (requires database)
poetry run pytest tests/test_gate1_validation.py::TestIntegrationGate1 -v -s
```

## Next Steps

Phase 2: Discovery Foundation

- Schema introspection skill
- Ontology discovery session
- Supply chain ontology YAML
