# Phase 2: Discovery Foundation

Phase 2 establishes the ontology discovery foundation that enables Virtual Graph to understand the semantic meaning of the database schema.

## Overview

**Goal**: Discovered ontology from raw schema + schema introspection skill

**Deliverables**:

| Deliverable | Description |
|-------------|-------------|
| `.claude/skills/schema/scripts/introspect.sql` | Schema introspection queries |
| `.claude/skills/schema/SKILL.md` | Schema skill definition |
| `ontology/virt_graph.yaml` | VG metamodel extension (defines annotation types) |
| `ontology/TEMPLATE.yaml` | Starter template for new ontologies |
| `ontology/supply_chain.yaml` | Discovered domain ontology |
| `prompts/ontology_discovery.md` | 4-round discovery protocol |

## Schema Introspection

The schema skill provides SQL queries to discover physical database structure:

### Available Queries

```sql
-- 1. Tables and columns
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public';

-- 2. Foreign key relationships
SELECT source_table, source_column, target_table, target_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ...
WHERE tc.constraint_type = 'FOREIGN KEY';

-- 3. Self-referential patterns (graph edges)
-- Detects tables with two FKs to the same table
```

### Using the Schema Skill

The schema skill is invoked when Claude needs to:

1. **Translate ontology concepts to SQL**: Map "Supplier" class to `suppliers` table
2. **Resolve relationships**: Find FK columns for `supplies_to` relationship
3. **Validate queries**: Check column types before generating WHERE clauses
4. **Understand patterns**: Identify soft deletes, audit columns, etc.

## Ontology Files

Virtual Graph uses three ontology files with distinct purposes:

```
ontology/
  virt_graph.yaml     # Metamodel - defines extension types
  TEMPLATE.yaml       # Template - starter for new ontologies
  supply_chain.yaml   # Instance - domain-specific ontology
```

### File Relationships

| File | Purpose | When to Use |
|------|---------|-------------|
| `virt_graph.yaml` | Defines `SQLMappedClass`, `SQLMappedRelationship`, `TraversalComplexity` enum, `WeightColumn` | Reference when understanding available annotations |
| `TEMPLATE.yaml` | Commented examples showing how to use each annotation | Copy when creating a new domain ontology |
| `supply_chain.yaml` | Actual domain ontology with real tables, columns, row counts | Load via `OntologyAccessor` for queries |

### Metamodel Extension (`virt_graph.yaml`)

Defines the abstract types that domain ontologies instantiate:

- **SQLMappedClass**: For entity tables (TBox)
  - Required: `vg:table`, `vg:primary_key`
  - Optional: `vg:identifier`, `vg:soft_delete_column`, `vg:row_count`

- **SQLMappedRelationship**: For relationship edges (RBox)
  - Required: `vg:edge_table`, `vg:domain_key`, `vg:range_key`, `vg:domain_class`, `vg:range_class`, `vg:traversal_complexity`
  - Optional: OWL 2 axioms (`vg:transitive`, `vg:symmetric`, etc.), cardinality, weight columns

- **TraversalComplexity**: GREEN | YELLOW | RED

- **WeightColumn**: For RED complexity edges with numeric weights

## Ontology Structure

The ontology uses **LinkML format with Virtual Graph extensions** to map semantic concepts to physical SQL:

### Entity Classes (TBox)

Entity classes use `instantiates: [vg:SQLMappedClass]`:

```yaml
classes:
  Supplier:
    description: "Companies that provide materials/parts"
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: suppliers
      vg:primary_key: id
      vg:identifier: "[supplier_code]"
      vg:row_count: 500
    attributes:
      tier:
        range: integer
        required: true
        description: "Supply chain tier (1=direct, 2=tier2, 3=raw materials)"
```

### Relationship Classes (RBox)

Relationship classes use `instantiates: [vg:SQLMappedRelationship]`:

```yaml
classes:
  SuppliesTo:
    description: "Supplier sells to another supplier"
    instantiates:
      - vg:SQLMappedRelationship
    annotations:
      vg:edge_table: supplier_relationships
      vg:domain_key: seller_id
      vg:range_key: buyer_id
      vg:domain_class: Supplier
      vg:range_class: Supplier
      vg:traversal_complexity: YELLOW
      vg:asymmetric: true
      vg:acyclic: true
      vg:cardinality_domain: "0..*"
      vg:cardinality_range: "0..*"
```

### Traversal Complexity

Each relationship is classified by query complexity:

| Complexity | Description | Handler |
|------------|-------------|---------|
| **GREEN** | Simple SQL joins | None (direct SQL) |
| **YELLOW** | Recursive traversal | `traverse()` |
| **RED** | Network algorithms | NetworkX handlers |

## Discovery Process

The ontology is discovered through a **4-round interactive protocol** (see `prompts/ontology_discovery.md`):

### Round 1: Schema Introspection

- Query `information_schema` for tables, columns, constraints
- Identify foreign key relationships
- Detect self-referential patterns (graph edges)
- Identify patterns: `deleted_at` (soft delete), `_id` suffix (FKs), unique constraints (natural keys)
- **Pause for human review**

### Round 2: Entity Class Discovery (TBox)

- Propose LinkML classes with `instantiates: [vg:SQLMappedClass]`
- Determine required annotations (`vg:table`, `vg:primary_key`)
- Query `COUNT(*)` for row counts
- **Pause for human corrections**

### Round 3: Relationship Class Discovery (RBox)

- Propose relationship classes with `instantiates: [vg:SQLMappedRelationship]`
- Determine traversal complexity (GREEN/YELLOW/RED)
- Set OWL 2 axioms for self-referential relationships
- **Pause for human corrections**

Example questions for `supplier_relationships`:

> Q: What does seller_id → buyer_id represent?
> A: Tiered supply chain - seller supplies to buyer

### Round 4: Draft, Validate & Finalize

1. Write complete ontology to `ontology/<schema_name>.yaml`
2. Run two-layer validation (see below)
3. Fix any validation errors
4. Run gate tests
5. **Human approves or requests changes**

Verify discovered structure against actual data:

```sql
-- Check FK integrity (should be 0 orphans)
SELECT COUNT(*) FROM supplier_relationships
WHERE seller_id NOT IN (SELECT id FROM suppliers);

-- Verify DAG structure
SELECT s1.tier, s2.tier, COUNT(*)
FROM supplier_relationships sr
JOIN suppliers s1 ON sr.seller_id = s1.id
JOIN suppliers s2 ON sr.buyer_id = s2.id
GROUP BY s1.tier, s2.tier;
```

## Two-Layer Validation

LinkML doesn't validate custom `vg:` annotations, so Virtual Graph uses two-layer validation:

### Layer 1: LinkML Structure

Validates YAML syntax and LinkML schema structure:

```bash
poetry run linkml-lint --validate-only ontology/supply_chain.yaml
```

### Layer 2: VG Annotations

Validates Virtual Graph-specific requirements:

```bash
poetry run python -c "from virt_graph.ontology import OntologyAccessor; OntologyAccessor()"
```

**What Layer 2 validates:**

- Entity classes have required `vg:table`, `vg:primary_key`
- Relationship classes have required `vg:edge_table`, `vg:domain_key`, `vg:range_key`, `vg:domain_class`, `vg:range_class`, `vg:traversal_complexity`
- `vg:traversal_complexity` is GREEN, YELLOW, or RED
- `vg:domain_class` and `vg:range_class` reference valid entity classes

### Running Both Layers

```bash
# Full two-layer validation
make validate-ontology

# Or run the validation script directly
poetry run python scripts/validate_ontology.py
```

## Discovered Entities

### Classes (8)

| Class | Table | Row Count |
|-------|-------|-----------|
| Supplier | suppliers | 500 |
| Part | parts | 5,003 |
| Product | products | 200 |
| Facility | facilities | 50 |
| Customer | customers | 1,000 |
| Order | orders | 20,000 |
| Shipment | shipments | 7,995 |
| SupplierCertification | supplier_certifications | 721 |

### Graph Edges (Self-Referential)

| Relationship | Edge Table | Complexity |
|--------------|------------|------------|
| supplies_to | supplier_relationships | YELLOW |
| component_of | bill_of_materials | YELLOW |
| connects_to | transport_routes | RED |

### Simple FK Relationships (9)

| Relationship | Complexity |
|--------------|------------|
| provides | GREEN |
| can_supply | GREEN |
| contains_component | GREEN |
| has_certification | GREEN |
| stores_at | GREEN |
| placed_by | GREEN |
| ships_from | GREEN |
| contains_item | GREEN |
| fulfills | GREEN |

## Gate 2 Validation

Validation criteria:

1. **Coverage**: Every table maps to a class or relationship ✅
2. **Correctness**: 5 simple queries validate ontology mappings ✅
3. **Completeness**: All relationships have required properties ✅

Test results:

```
tests/test_gate2_validation.py - 21 tests passed

TestOntologyCoverage: 2 passed
TestRelationshipMappings: 4 passed
TestSelfReferentialEdges: 4 passed
TestOntologyQueries: 5 passed
TestNamedEntities: 3 passed
TestDataDistribution: 2 passed
TestGate2Summary: 1 passed
```

## Usage Examples

### GREEN Query (Simple SQL)

```python
# "Find supplier Acme Corp"
from virt_graph.ontology import OntologyAccessor
ontology = OntologyAccessor()
table = ontology.get_class_table("Supplier")  # "suppliers"
# Generated SQL:
# SELECT * FROM suppliers WHERE name = 'Acme Corp';
```

### YELLOW Query (Recursive)

```python
# "Find all tier 3 suppliers for Acme Corp"
from virt_graph.ontology import OntologyAccessor
ontology = OntologyAccessor()

# Ontology lookup
domain_key, range_key = ontology.get_role_keys("SuppliesTo")
table = ontology.get_role_table("SuppliesTo")

# Use traverse() handler with resolved params:
traverse(
    conn=db,
    nodes_table="suppliers",
    edges_table=table,  # "supplier_relationships"
    edge_from_col=domain_key,  # "seller_id"
    edge_to_col=range_key,  # "buyer_id"
    start_id=1,  # Acme Corp
    direction="inbound",
    stop_condition="tier = 3"
)
```

### RED Query (Network Algorithm)

```python
# "Cheapest route from Chicago to LA"
from virt_graph.ontology import OntologyAccessor
ontology = OntologyAccessor()

# Ontology lookup
weight_cols = ontology.get_role_weight_columns("ConnectsTo")
domain_key, range_key = ontology.get_role_keys("ConnectsTo")

# Use shortest_path() handler with:
shortest_path(
    conn=db,
    nodes_table="facilities",
    edges_table="transport_routes",
    edge_from_col=domain_key,  # "origin_facility_id"
    edge_to_col=range_key,  # "destination_facility_id"
    start_id=1,  # Chicago
    end_id=2,    # LA
    weight_col="cost_usd"  # from weight_cols
)
```

## Next Steps

With the ontology complete, Phase 3 implements:

1. **GREEN Path**: Claude generates SQL using ontology mappings
2. **YELLOW Path**: Pattern discovery + traversal handler integration
3. **RED Path**: NetworkX handlers for pathfinding and centrality
