# Phase 2: Discovery Foundation

Phase 2 establishes the ontology discovery foundation that enables Virtual Graph to understand the semantic meaning of the database schema.

## Overview

**Goal**: Discovered ontology from raw schema + schema introspection skill

**Deliverables**:

| Deliverable | Description |
|-------------|-------------|
| `.claude/skills/schema/scripts/introspect.sql` | Schema introspection queries |
| `.claude/skills/schema/SKILL.md` | Schema skill definition |
| `ontology/supply_chain.yaml` | Discovered ontology |
| `docs/ontology_discovery_session.md` | Discovery session transcript |

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

The ontology was discovered through a 3-round process:

### Round 1: Schema Introspection

- Query `information_schema` for tables, columns, constraints
- Identify foreign key relationships
- Detect self-referential patterns (graph edges)
- Generate initial ontology draft with questions

### Round 2: Business Context Interview

Required questions for each relationship:

1. **Cardinality**: One-to-many or many-to-many?
2. **Directionality**: Is this strictly one-way?
3. **Reflexivity**: Can entities relate to themselves?
4. **Optionality**: Required or optional?

Example for `supplier_relationships`:

> Q: What does seller_id → buyer_id represent?
> A: Tiered supply chain - seller supplies to buyer

### Round 3: Data Validation

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
