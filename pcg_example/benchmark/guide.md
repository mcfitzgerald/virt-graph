# Benchmark Execution Guide

How to answer natural-language supply chain questions using the VG/SQL ontology as a virtual twin.

## The Core Loop

```
Question (natural language)
      |
      v
1. IDENTIFY — What entities and relationships does this touch?
      |          Read the ontology. Find the classes, look at vg:context.
      v
2. DISPATCH — SQL or handler?
      |          Check vg:operation_types on each relationship involved.
      |          direct_join → write SQL
      |          recursive_traversal → call traverse()
      |          path_aggregation / hierarchical_aggregation → call path_aggregate()
      |          shortest_path → call shortest_path() or all_shortest_paths()
      |          centrality → call centrality()
      |          connected_components → call connected_components()
      |          resilience_analysis → call resilience_analysis()
      |          flow_analysis / state_analysis / scenario_analysis → write ad-hoc SQL
      v
3. PARAMETERIZE — Build the query from ontology metadata
      |          Tables, PKs, FKs, edge attributes, weight columns,
      |          type discriminators, sql_filters — all declared in the ontology.
      v
4. EXECUTE — Run against the live database
      |          Use virt_graph.db.connection() for SQL.
      |          Import handlers from virt_graph.handlers.* for graph ops.
      v
5. INTERPRET — Explain results using business context from the ontology
```

## Session Setup

At the start of a session, load these into context:

```python
# 1. The ontology — this IS the virtual twin
from virt_graph.ontology import OntologyAccessor
from pathlib import Path
ontology = OntologyAccessor(Path("pcg_example/ontology/pcg.yaml"))

# 2. Database connection
from virt_graph.db import connection

# 3. Handlers (import as needed)
from virt_graph.handlers.traversal import traverse, traverse_collecting, path_aggregate
from virt_graph.handlers.pathfinding import shortest_path, all_shortest_paths
from virt_graph.handlers.network import centrality, connected_components, resilience_analysis
```

Read the ontology file directly (`pcg_example/ontology/pcg.yaml`) to get the full picture — every class has a `vg:context` block with business logic and prompt hints.

## Step 1: IDENTIFY

Read the question. Map business language to ontology classes:

| Business Term | Ontology Class | Table |
|---|---|---|
| "supplier" | Supplier | suppliers |
| "ingredient", "raw material" | Ingredient | ingredients |
| "formula", "recipe", "BOM" | Formula + FormulaIngredient | formulas + formula_ingredients |
| "SKU", "product", "finished good" | SKU | skus |
| "bulk intermediate", "compound" | BulkIntermediate | bulk_intermediates |
| "plant", "factory" | Plant | plants |
| "production line" | ProductionLine | production_lines |
| "work order" | WorkOrder | work_orders |
| "batch", "production run" | Batch | batches |
| "order", "demand" | Order + OrderLine | orders + order_lines |
| "shipment", "delivery" | Shipment + ShipmentLine | shipments + shipment_lines |
| "inventory", "stock" | Inventory | inventory |
| "route", "lane", "transport" | RouteSegment | route_segments |
| "DC", "warehouse", "distribution center" | DistributionCenter | distribution_centers |
| "store", "retail location" | RetailLocation | retail_locations |
| "channel" | Channel | channels |
| "purchase order", "PO" | PurchaseOrder + PurchaseOrderLine | purchase_orders + purchase_order_lines |
| "goods receipt", "GR" | GoodsReceipt + GoodsReceiptLine | goods_receipts + goods_receipt_lines |
| "AP invoice" | APInvoice + APInvoiceLine | ap_invoices + ap_invoice_lines |
| "AR invoice", "revenue" | ARInvoice + ARInvoiceLine | ar_invoices + ar_invoice_lines |
| "payment" | APPayment | ap_payments |
| "receipt" (cash collection) | ARReceipt | ar_receipts |
| "return" | Return + ReturnLine | returns + return_lines |
| "GL", "journal", "ledger" | GLJournal | gl_journal |
| "variance", "three-way match" | InvoiceVariance | invoice_variances |

Then find the **relationships** that connect these entities. Use `ontology.get_operation_types()` on each relationship to determine the dispatch.

## Step 2: DISPATCH

The operation type tells you what tool to use:

### SQL-only (direct_join)

47 of 50 relationships are `direct_join`. Write SQL using table/column mappings from the ontology.

```python
# Example: Q01 — supplier lookup
table = ontology.get_class_table("Supplier")  # → "suppliers"
pk = ontology.get_class_pk("Supplier")          # → ["id"]
# Generate: SELECT * FROM suppliers WHERE supplier_code = 'SUP-0012'
```

### Recursive traversal (traverse handler)

For self-referential chains. The PCG ontology has one: **SKUSupersedes** (skus.supersedes_sku_id).

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

The handler returns `{nodes, paths, edges, depth_reached, nodes_visited, terminated_at}`. Node objects include all columns from the table.

### BOM explosion (path_aggregate handler)

For hierarchical traversal with aggregation. Used on **FormulaHasIngredients**.

```python
result = path_aggregate(
    conn,
    nodes_table="ingredients",
    edges_table="formula_ingredients",
    edge_from_col="formula_id",
    edge_to_col="ingredient_id",
    start_id=formula_id,
    value_col="quantity_kg",
    operation="multiply",  # or "sum", "max", "min"
    max_depth=20,
)
```

Note: `ingredient_id` is **polymorphic** — it can point to `ingredients` or `bulk_intermediates`. For full multi-level BOM explosion, resolve bulk intermediates at level 0, find their level-1 formula, and recurse.

### Network algorithms (shortest_path, centrality, etc.)

For the transport network (**RouteSegmentOrigin/Destination**). The network has **polymorphic endpoints** — nodes are identified by composite keys `(type, id)`.

Build the NetworkX graph manually with composite node keys:

```python
import networkx as nx

with conn.cursor() as cur:
    cur.execute("""
        SELECT origin_type, origin_id, destination_type, destination_id,
               distance_km, transit_time_hours
        FROM route_segments
        WHERE distance_km IS NOT NULL
    """)
    G = nx.DiGraph()
    for row in cur.fetchall():
        src = f"{row[0]}:{row[1]}"
        dst = f"{row[2]}:{row[3]}"
        G.add_edge(src, dst,
                   distance_km=float(row[4]),
                   transit_time_hours=float(row[5]) if row[5] else None)

# Shortest path by distance
path = nx.shortest_path(G, "plant:45", "store:860", weight="distance_km")
```

The `shortest_path()` handler also works but requires globally unique node IDs. For polymorphic networks, the manual NetworkX approach with `type:id` composite keys is more reliable.

### Multi-step composition

Many questions require chaining: BOM explosion → supplier lookup → transport routing. Decompose into sub-problems, execute each with the appropriate tool, and join results in Python.

## Step 3: PARAMETERIZE

Every query parameter comes from the ontology:

| Parameter | Ontology Source |
|---|---|
| Table name | `ontology.get_class_table(class_name)` |
| Primary key | `ontology.get_class_pk(class_name)` |
| FK columns | `ontology.get_role_keys(relationship_name)` |
| Edge table | relationship's `vg:edge_table` |
| Weight columns | `ontology.get_role_weight_columns(rel)` |
| Edge attributes | `ontology.get_role_edge_attributes(rel)` |
| SQL filter | `ontology.get_role_filter(rel)` (e.g., `is_active = true`) |
| Type discriminator | `ontology.get_role_type_discriminator(rel)` |
| Context / hints | `ontology.get_class_context(class)` or `ontology.get_role_context(rel)` |

## Step 4: EXECUTE

```python
from virt_graph.db import connection

with connection() as conn:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
```

For handlers:

```python
from virt_graph.db import connection
from virt_graph.handlers.traversal import traverse

with connection() as conn:
    result = traverse(conn, ...)
```

## Step 5: INTERPRET

Use the `vg:context` blocks to explain results in business terms. The ontology context provides:
- **business_logic**: What the data means (e.g., "revenue lives in AR invoices, not order lines")
- **llm_prompt_hint**: Practical guidance (e.g., "join source_id to channels for IDs 1-7")
- **traversal_semantics**: What inbound/outbound traversal means in business terms

## Key Patterns by Question Tier

### Tier 1: Single SQL query (Q01–Q10)

Read the question → identify entity → look up table/columns → write SQL → execute.

### Tier 2: Single handler (Q11–Q40)

SKU chains (Q11–Q18): `traverse()` on `skus.supersedes_sku_id`
BOM (Q19–Q28): `path_aggregate()` on `formula_ingredients`, with polymorphic ingredient resolution
Network (Q29–Q40): Build NetworkX graph from `route_segments` with composite node keys

### Tier 3: Handler + SQL (Q41–Q50, Q61–Q68, Q69–Q76)

Decompose into sub-problems. Example for landed cost (Q42):
1. `path_aggregate()` → BOM explosion (get ingredient list + quantities)
2. SQL → find cheapest supplier for each ingredient
3. NetworkX `shortest_path()` → inbound freight from each supplier to plant
4. Python → sum material cost + freight cost

### Tier 4: Multi-handler chains (Q51–Q60, Q77–Q85)

Full end-to-end traceability. Multiple decomposition steps. Example for blast radius (Q58):
1. SQL → find supplier + any -ALT duplicates
2. SQL → find ingredients they supply
3. SQL → find formulas using those ingredients
4. SQL → find batches using those formulas
5. SQL → find SKUs those batches produce
6. SQL → find order lines with those SKUs
7. SQL → find shipments for those orders
8. SQL → quantify revenue exposure via AR invoices

## Reference Files

| File | Purpose |
|---|---|
| `pcg_example/ontology/pcg.yaml` | The ontology — read this first |
| `pcg_example/ontology/scm_base.yaml` | Base schema (class hierarchy, mixins) |
| `pcg_example/pcg_schema.sql` | DDL for column-level reference |
| `pcg_example/benchmark/questions.md` | The 85 benchmark questions |
| `pcg_example/benchmark/question_categories.md` | Category mappings (Q→handler/operation/feature) |
| `src/virt_graph/handlers/` | Handler implementations |
| `src/virt_graph/ontology.py` | OntologyAccessor API |
| `src/virt_graph/db.py` | Database connection |
