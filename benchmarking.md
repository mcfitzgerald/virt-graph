# Virtual Graph Benchmarking Guide

This guide documents the methodology used to benchmark Virtual Graph's ability to answer graph-style questions over relational data. It serves as both a research artifact and a replication guide.

---

## Introduction

### Research Context

Virtual Graph explores whether an LLM, equipped with a domain ontology and specialized handlers, can effectively answer graph-style questions over relational databases—without migrating data to a native graph database.

The hypothesis: By combining:
1. **A discovered ontology** that maps graph concepts to relational structures
2. **Specialized handlers** for recursive traversal and network algorithms
3. **LLM reasoning** to route questions and generate queries

...we can achieve comparable functionality to graph databases for common enterprise use cases.

### What This Guide Covers

This guide walks through the complete benchmarking process:
1. Database setup with synthetic supply chain data
2. Ontology discovery and validation
3. Question inventory design (50 questions across complexity levels)
4. Real-time query execution by Claude Code
5. Results analysis and validation

---

## Phase 1: Database Foundation

### Schema Overview

The benchmark uses a supply chain domain with 15 tables (~130K rows):

| Table | Rows | Purpose |
|-------|------|---------|
| `suppliers` | 500 | Tiered supplier network (tier 1, 2, 3) |
| `supplier_relationships` | 817 | Supplier-to-supplier edges |
| `parts` | 5,003 | Components and raw materials |
| `bill_of_materials` | 14,283 | BOM hierarchy (parent-child) |
| `products` | 200 | Finished goods |
| `product_components` | 619 | Product-to-part links |
| `facilities` | 50 | Warehouses, factories, hubs |
| `transport_routes` | 197 | Weighted routes between facilities |
| `customers` | 1,000 | B2B customers |
| `orders` | 20,000 | Purchase orders |
| `order_items` | 60,241 | Order line items |
| `inventory` | 10,056 | Stock levels per part/facility |
| `shipments` | 7,995 | Shipment records |
| `supplier_certifications` | 721 | Quality certifications |
| `part_suppliers` | 7,582 | Approved supplier-part links |

### Synthetic Data Generation

Data is generated via `scripts/generate_data.py` using the Faker library:

```bash
# Regenerate seed data
poetry run python scripts/generate_data.py
```

Key design choices:
- **Named test entities**: Specific entities for reproducible queries (e.g., "Acme Corp", "Turbo Encabulator")
- **Realistic distributions**: Tiered suppliers, multi-level BOMs (up to 5 levels deep)
- **Graph properties**: Supplier network is a DAG, transport network is fully connected

### Database Setup

```bash
# Start PostgreSQL
make db-up

# Connection string
postgresql://virt_graph:dev_password@localhost:5432/supply_chain
```

---

## Phase 2: Ontology Discovery

### The Discovery Process

The ontology was created through an interactive discovery protocol:

1. **Round 1: Schema Introspection** — Extract tables, columns, foreign keys
2. **Round 2: Entity Classification** — Identify node tables vs. edge tables
3. **Round 3: Relationship Mapping** — Map FKs to graph edges with directionality
4. **Round 4: Complexity Classification** — Assign GREEN/YELLOW/RED based on traversal needs

### Ontology Structure

The resulting ontology (`ontology/supply_chain.yaml`) defines:

**Entity Classes (TBox)** — 9 classes:
- Supplier, Part, Product, Facility, Customer, Order, Shipment, Inventory, SupplierCertification

**Relationship Classes (RBox)** — 15 relationships with complexity:

| Relationship | Domain → Range | Complexity | Edge Table |
|--------------|----------------|------------|------------|
| `SuppliesTo` | Supplier → Supplier | YELLOW | supplier_relationships |
| `HasComponent` | Part → Part | YELLOW | bill_of_materials |
| `ComponentOf` | Part → Part | YELLOW | bill_of_materials |
| `ConnectsTo` | Facility → Facility | RED | transport_routes |
| `CanSupply` | Supplier → Part | GREEN | part_suppliers |
| `ContainsComponent` | Product → Part | GREEN | product_components |
| `PrimarySupplier` | Part → Supplier | GREEN | parts.primary_supplier_id |
| ... | ... | ... | ... |

### Complexity Classification

The key insight: **complexity determines query strategy**:

| Complexity | Strategy | When Used |
|------------|----------|-----------|
| **GREEN** | Direct SQL | Simple FK joins, no recursion |
| **YELLOW** | `traverse()` handler | Recursive paths through self-referencing tables |
| **RED** | NetworkX handlers | Weighted pathfinding, centrality, connectivity |

### Validation

```bash
# Validate ontology structure
make validate-ontology

# View definitions
make show-tbox   # Entity classes
make show-rbox   # Relationships
```

---

## Phase 3: Question Inventory Design

### Design Rationale

The 50 questions were designed to:
1. **Cover all relationships** in the ontology
2. **Test each complexity level** with realistic business questions
3. **Include cross-domain patterns** (MIXED) combining multiple complexities
4. **Use named entities** for reproducibility

### Distribution

| Complexity | Count | Rationale |
|------------|-------|-----------|
| GREEN | 10 (20%) | Representative SQL patterns—if these work, hundreds more will |
| YELLOW | 18 (36%) | Deep coverage of recursive traversal (supplier network + BOM) |
| RED | 12 (24%) | Pathfinding variants + centrality/connectivity algorithms |
| MIXED | 10 (20%) | Cross-domain patterns combining GREEN + YELLOW/RED |

### Question Categories

**GREEN (Q01-Q10)**: Entity lookups, joins, aggregations
- "Find the supplier with code 'SUP00001'"
- "Which suppliers have ISO9001 certification?"
- "Total revenue by customer for last quarter"

**YELLOW - Supplier Network (Q11-Q18)**: Recursive traversal of tiered suppliers
- "Find all tier 2 suppliers of 'Acme Corp'"
- "Trace supply path from 'Eastern Electronics' to any tier 1"
- "What is the maximum depth of our supplier network?"

**YELLOW - BOM (Q19-Q28)**: Bill of materials explosion and where-used
- "Full BOM explosion for 'Turbo Encabulator'"
- "Where is part 'PRT-000001' used?"
- "Find the critical path (longest chain) in BOM"

**RED (Q29-Q40)**: Network algorithms on transport routes
- "Shortest route by distance from Chicago to LA"
- "Which facility is most central (betweenness)?"
- "Are there any isolated facilities?"

**MIXED (Q41-Q50)**: Cross-complexity patterns
- "Sufficient inventory to build 100 units of 'Turbo Encabulator'?"
- "Single points of failure in supply chain"
- "If a hub fails, cost increase for pending orders?"

### Named Test Entities

These entities are created by the data generator for reproducible queries:

| Type | Entities |
|------|----------|
| Suppliers | "Acme Corp" (tier 1), "GlobalTech Industries" (tier 1), "Pacific Components" (tier 2), "Eastern Electronics" (tier 3) |
| Products | "Turbo Encabulator" (TURBO-001), "Flux Capacitor" (FLUX-001) |
| Facilities | "Chicago Warehouse" (FAC-CHI), "LA Distribution Center" (FAC-LA), "New York Factory" (FAC-NYC) |

---

## Phase 4: Query Execution

### The Reasoning Approach

This is where Virtual Graph differs from traditional approaches. Rather than pattern matching against pre-recorded templates, Claude Code:

1. **Reads the question** and identifies the business intent
2. **Consults the ontology** to understand which tables/relationships are involved
3. **Classifies complexity** based on relationship annotations
4. **Generates the query** (SQL or handler call) in real-time
5. **Executes and validates** the results

This approach relies on the LLM's ability to:
- Parse the ontology YAML structure
- Understand handler signatures
- Generate syntactically correct SQL/Python
- Reason about traversal direction (inbound vs. outbound)

### GREEN: Direct SQL Generation

For simple queries, Claude generates SQL directly:

```sql
-- Q05: Which suppliers have ISO9001 certification?
SELECT DISTINCT s.supplier_code, s.name
FROM suppliers s
JOIN supplier_certifications sc ON s.id = sc.supplier_id
WHERE sc.certification_type = 'ISO9001' AND sc.is_valid = true;
```

The ontology provides:
- Table names (`suppliers`, `supplier_certifications`)
- Join keys (`HasCertification` relationship: `supplier_id → id`)
- Filter columns (`certification_type`, `is_valid`)

### YELLOW: Handler Invocation

For recursive traversal, Claude invokes the `traverse()` or `bom_explode()` handlers:

```python
# Q12: Find all tier 2 AND tier 3 suppliers upstream from 'Acme Corp'
result = traverse(
    conn,
    nodes_table="suppliers",
    edges_table="supplier_relationships",
    edge_from_col="seller_id",
    edge_to_col="buyer_id",
    start_id=acme_id,
    direction="inbound",  # Who sells TO Acme
    max_depth=10,
    include_start=False,
)
```

Key reasoning required:
- **Direction**: "upstream suppliers" = who sells TO this company = `inbound`
- **Parameters from ontology**: `SuppliesTo` relationship defines `seller_id → buyer_id`

```python
# Q19: Full BOM explosion for 'Turbo Encabulator'
result = bom_explode(
    conn,
    start_part_id=part_id,
    max_depth=20,
    include_quantities=True,
)
```

### RED: NetworkX Handlers

For weighted pathfinding and centrality:

```python
# Q29: Shortest route by distance from Chicago to LA
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

# Q36: Which facility is most central?
result = centrality(
    conn,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col="origin_facility_id",
    edge_to_col="destination_facility_id",
    centrality_type="betweenness",
    top_n=10,
)
```

### MIXED: Combined Approaches

Cross-domain queries require sequencing multiple operations:

```python
# Q41: Sufficient inventory to build 100 units of 'Turbo Encabulator'?

# Step 1: GREEN - Get product parts
cur.execute("""
    SELECT pc.part_id, pc.quantity
    FROM products pr
    JOIN product_components pc ON pr.id = pc.product_id
    WHERE pr.name = 'Turbo Encabulator'
""")
product_parts = cur.fetchall()

# Step 2: YELLOW - Explode BOM for each part
for part_id, qty in product_parts:
    result = bom_explode(conn, part_id, include_quantities=True)

    # Step 3: GREEN - Check inventory
    for node in result['nodes']:
        qty_needed = result['quantities'][node['id']] * qty * BUILD_QUANTITY
        cur.execute("""
            SELECT SUM(quantity_on_hand - quantity_reserved)
            FROM inventory WHERE part_id = %s
        """, (node['id'],))
        available = cur.fetchone()[0]

        if available < qty_needed:
            shortages.append((node['part_number'], qty_needed, available))
```

---

## Phase 5: Results & Validation

### Accuracy Summary

| Complexity | Questions | Accuracy | Notes |
|------------|-----------|----------|-------|
| GREEN | 10 | 100% | All SQL patterns work correctly |
| YELLOW | 18 | 100% | `traverse()` handles all directions |
| RED | 12 | ~92% | Minor limitations in constrained pathfinding |
| MIXED | 10 | 100% | Cross-domain patterns work well |
| **Total** | **50** | **~98%** | |

### Key Findings

**Data Metrics:**
- Maximum BOM depth: 5 levels
- Supplier network depth: 3 levels (tier 1 → 2 → 3)
- Transport network: 50 nodes, 193 edges, fully connected
- Most central facility: New York Factory (betweenness = 0.23)
- Single-source parts in Turbo Encabulator: 306 (30% of BOM)

**Observations:**
1. Ontology-driven parameter resolution works reliably
2. Handler direction semantics require careful reasoning
3. MIXED queries successfully chain multiple complexity levels
4. Real-time query generation is practical for this domain

### Limitations Discovered

1. **Constrained pathfinding**: No built-in way to find paths avoiding specific nodes
2. **Resilience analysis**: Graph modification for "what-if" scenarios not supported
3. **Decimal type handling**: Python `decimal.Decimal` from PostgreSQL requires conversion

See `REPORT.md` for full details.

---

## Reproducing This Benchmark

### Prerequisites

```bash
# Clone repository
git clone https://github.com/mcfitzgerald/virt-graph.git
cd virt-graph

# Install dependencies
poetry install

# Start database
make db-up

# Verify data
poetry run python -c "
import psycopg2
conn = psycopg2.connect('postgresql://virt_graph:dev_password@localhost:5432/supply_chain')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM suppliers')
print(f'Suppliers: {cur.fetchone()[0]}')
"
```

### Running the Benchmark

The benchmark was executed interactively via Claude Code. To replicate:

1. **Load the context**:
   - `CLAUDE.md` — Project instructions
   - `ontology/supply_chain.yaml` — The domain ontology
   - `question_inventory.md` — The 50 questions

2. **Execute questions**:
   For each question, Claude Code:
   - Classifies complexity (GREEN/YELLOW/RED)
   - Generates appropriate SQL or handler call
   - Executes against the database
   - Reports results

3. **Validate results**:
   - Compare to expected behavior
   - Check for errors or edge cases

### Artifacts

| File | Description |
|------|-------------|
| `question_inventory.md` | The 50 benchmark questions |
| `REPORT.md` | Execution results and analysis |
| `benchmarking.md` | This methodology guide |

---

## Conclusion

This benchmarking exercise demonstrates that:

1. **Ontology + Handlers + LLM reasoning** can effectively answer graph-style questions over relational data
2. **Complexity classification** (GREEN/YELLOW/RED) provides a practical routing strategy
3. **Real-time query generation** by an LLM is viable for this domain
4. **98% accuracy** across 50 diverse questions validates the approach

The key enabler is the ontology: it bridges the semantic gap between graph concepts (nodes, edges, traversal) and relational structures (tables, foreign keys, joins), allowing the LLM to reason about queries without explicit pattern templates.
