# Ontology Guide

The ontology is the core semantic layer that maps business concepts to SQL tables and classifies query complexity.

## Overview

Virtual Graph uses LinkML format with custom extensions (`vg:` prefix). The ontology defines:

- **Entity Classes (TBox)** - What things exist (Supplier, Part, Facility)
- **Relationship Classes (RBox)** - How things connect (SuppliesTo, ComponentOf)

## File Structure

```
ontology/
  virt_graph.yaml     # Metamodel - defines VG annotations
  TEMPLATE.yaml       # Template for new ontologies
  supply_chain.yaml   # Supply chain domain ontology
```

## Entity Classes (TBox)

Entity classes map domain concepts to database tables using `vg:SQLMappedClass`.

```yaml
Supplier:
  description: "Organization that provides parts or services"
  instantiates:
    - vg:SQLMappedClass
  annotations:
    vg:table: suppliers           # SQL table name
    vg:primary_key: id            # Primary key column
    vg:identifier: "[supplier_code]"  # Human-readable identifier
    vg:row_count: 500             # Approximate count (for estimation)
  attributes:
    supplier_code:
      range: string
      required: true
    name:
      range: string
      required: true
    tier:
      range: integer
      description: "Supply chain tier (1, 2, or 3)"
```

### Required Annotations

| Annotation | Description |
|------------|-------------|
| `vg:table` | SQL table name |
| `vg:primary_key` | Primary key column |

### Optional Annotations

| Annotation | When to Use |
|------------|-------------|
| `vg:identifier` | Natural key as JSON array: `"[code]"` |
| `vg:soft_delete_column` | If `deleted_at` exists |
| `vg:row_count` | For size estimation |

## Relationship Classes (RBox)

Relationship classes define how entities connect using `vg:SQLMappedRelationship`.

### YELLOW Example: SuppliesTo

```yaml
SuppliesTo:
  description: "Supplier sells to another supplier (tiered network)"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: supplier_relationships
    vg:domain_key: seller_id      # FK from source
    vg:range_key: buyer_id        # FK to target
    vg:domain_class: Supplier
    vg:range_class: Supplier
    vg:traversal_complexity: YELLOW
    vg:acyclic: true              # No cycles (DAG)
    vg:is_hierarchical: true
```

### RED Example: ConnectsTo

```yaml
ConnectsTo:
  description: "Transport route connecting facilities (weighted)"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: transport_routes
    vg:domain_key: origin_facility_id
    vg:range_key: destination_facility_id
    vg:domain_class: Facility
    vg:range_class: Facility
    vg:traversal_complexity: RED
    vg:is_weighted: true
    vg:weight_columns: '[
      {"name": "distance_km", "type": "decimal"},
      {"name": "cost_usd", "type": "decimal"}
    ]'
```

### GREEN Example: CanSupply

```yaml
CanSupply:
  description: "Supplier is approved to supply a part"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: part_suppliers
    vg:domain_key: supplier_id
    vg:range_key: part_id
    vg:domain_class: Supplier
    vg:range_class: Part
    vg:traversal_complexity: GREEN
```

### Complexity Assignment

```
Is the relationship self-referential (domain_class == range_class)?
├── No → GREEN (simple FK join)
└── Yes → Does it have numeric weight columns?
    ├── Yes → RED (network algorithms)
    └── No → YELLOW (recursive traversal)
```

## Supply Chain Ontology Summary

### Entity Classes

| Class | Table | Rows | Description |
|-------|-------|------|-------------|
| Supplier | `suppliers` | 500 | Supply chain organizations |
| Part | `parts` | 5,003 | Components and materials |
| Product | `products` | 200 | Finished goods |
| Facility | `facilities` | 50 | Physical locations |
| Customer | `customers` | 1,000 | Order-placing entities |
| Order | `orders` | 20,000 | Purchase orders |

### Relationships by Complexity

| Complexity | Relationship | Edge Table |
|------------|--------------|------------|
| YELLOW | SuppliesTo | `supplier_relationships` |
| YELLOW | ComponentOf | `bill_of_materials` |
| RED | ConnectsTo | `transport_routes` |
| GREEN | CanSupply | `part_suppliers` |
| GREEN | ContainsComponent | `product_components` |

## Using the Ontology

### Programmatic Access

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor()  # Validates on load

# Get table for a class
table = ontology.get_class_table("Supplier")  # "suppliers"

# Get FK columns for a relationship
domain_key, range_key = ontology.get_role_keys("SuppliesTo")
# ("seller_id", "buyer_id")

# Get complexity for routing
complexity = ontology.get_role_complexity("ConnectsTo")  # "RED"
```

### Command Line

```bash
make show-tbox        # View entity classes
make show-rbox        # View relationships
make validate-ontology  # Two-layer validation
```

## Two-Layer Validation

### Layer 1: LinkML Structure

```bash
poetry run linkml-lint --validate-only ontology/supply_chain.yaml
```

Validates YAML syntax and LinkML schema structure.

### Layer 2: VG Annotations

```python
from virt_graph.ontology import OntologyAccessor
ontology = OntologyAccessor()  # Raises OntologyValidationError if invalid
```

Validates:
- Required VG annotations present
- `traversal_complexity` is GREEN/YELLOW/RED
- `domain_class`/`range_class` reference valid classes

## Creating a New Ontology

1. Copy `ontology/TEMPLATE.yaml` to `ontology/{domain}.yaml`
2. Update header (id, name, description)
3. Define entity classes for each table
4. Define relationship classes for each FK
5. Assign traversal complexity (GREEN/YELLOW/RED)
6. Run `make validate-ontology`

## Relationship Direction Reference

When using handlers, "inbound" and "outbound" refer to edge direction:

| Relationship | edge_from → edge_to | "inbound" means | "outbound" means |
|--------------|---------------------|-----------------|------------------|
| SuppliesTo | seller_id → buyer_id | Who sells to me (upstream) | Who I sell to (downstream) |
| ComponentOf | child_id → parent_id | My sub-components | What contains me |
| ConnectsTo | origin_id → dest_id | Routes arriving here | Routes departing here |
