# LinkML Format

VG/SQL ontologies are written in [LinkML](https://linkml.io), a modeling language for linked data. This page covers the basics of LinkML as used in VG/SQL.

## Why LinkML?

- **Standard YAML format** - Human-readable, version-controllable
- **Validation tooling** - Built-in linting and schema validation
- **Ecosystem compatibility** - Export to JSON Schema, OWL, SHACL
- **Extensibility** - Custom annotations via prefixes

## Basic Structure

Every VG/SQL ontology follows this structure:

```yaml
# Schema metadata
id: https://example.com/schemas/my_domain
name: my_domain
version: "1.0"
description: "My domain ontology"

# Prefixes for namespaces
prefixes:
  linkml: https://w3id.org/linkml/
  vg: https://virt-graph.dev/

# Required imports
imports:
  - linkml:types

# Default attribute type
default_range: string

# Optional: Database metadata
annotations:
  vg:database_type: postgresql
  vg:database_version: "14"

# Class definitions
classes:
  # ... entity and relationship classes
```

## Defining Entity Classes (TBox)

Entity classes map to database tables. They represent the "things" in your domain.

```yaml
classes:
  Supplier:
    description: "A supplier in the network"
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: suppliers
      vg:primary_key: id
      vg:identifier: "[supplier_code]"
      vg:soft_delete_column: deleted_at
      vg:row_count: 500
    attributes:
      supplier_code:
        range: string
        required: true
        description: "Unique business identifier"
      name:
        range: string
        required: true
      tier:
        range: integer
        description: "Supply chain tier (1=direct, 2=second-level, etc.)"
      active:
        range: boolean
```

### Key Elements

| Element | Purpose |
|---------|---------|
| `instantiates: [vg:SQLMappedClass]` | Marks this as an entity class |
| `annotations` | VG-specific metadata (table mapping, etc.) |
| `attributes` | Column definitions |
| `range` | Attribute data type |
| `required` | Whether NULL is allowed |

## Defining Relationship Classes (RBox)

Relationship classes map to foreign key relationships between entities.

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
      vg:irreflexive: true
      vg:acyclic: true
    attributes:
      relationship_type:
        range: string
      contract_value:
        range: decimal
```

### Key Elements

| Element | Purpose |
|---------|---------|
| `instantiates: [vg:SQLMappedRelationship]` | Marks this as a relationship class |
| `vg:edge_table` | Junction/edge table name |
| `vg:domain_key` | FK pointing to source entity |
| `vg:range_key` | FK pointing to target entity |
| `vg:domain_class` / `vg:range_class` | Entity classes at each end |
| `vg:traversal_complexity` | GREEN, YELLOW, or RED |

## Attribute Ranges (Data Types)

LinkML provides standard data types:

| Range | SQL Type | Example |
|-------|----------|---------|
| `string` | VARCHAR, TEXT | `name: "Acme Corp"` |
| `integer` | INT, BIGINT | `tier: 2` |
| `decimal` | DECIMAL, NUMERIC | `price: 99.99` |
| `boolean` | BOOLEAN | `active: true` |
| `date` | DATE | `start_date: "2024-01-15"` |
| `datetime` | TIMESTAMP | `created_at: "2024-01-15T10:30:00"` |

```yaml
attributes:
  name:
    range: string
  quantity:
    range: integer
  unit_price:
    range: decimal
  is_active:
    range: boolean
  effective_date:
    range: date
  created_at:
    range: datetime
```

## Attribute Modifiers

### Required Fields

```yaml
attributes:
  supplier_code:
    range: string
    required: true      # NOT NULL
```

### Multivalued (Arrays)

```yaml
attributes:
  tags:
    range: string
    multivalued: true   # Array of strings
```

### Identifiers

```yaml
attributes:
  supplier_code:
    range: string
    identifier: true    # Natural key (unique)
```

## Enums

Define constrained value sets:

```yaml
enums:
  SupplierTier:
    permissible_values:
      TIER_1:
        description: "Direct supplier"
      TIER_2:
        description: "Second-level supplier"
      TIER_3:
        description: "Third-level supplier"

classes:
  Supplier:
    attributes:
      tier:
        range: SupplierTier   # Constrained to enum values
```

## Inheritance

Classes can inherit from other classes:

```yaml
classes:
  BaseEntity:
    abstract: true
    attributes:
      id:
        range: integer
        identifier: true
      created_at:
        range: datetime
      updated_at:
        range: datetime

  Supplier:
    is_a: BaseEntity         # Inherits id, created_at, updated_at
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: suppliers
      vg:primary_key: id
    attributes:
      name:
        range: string
```

## Slots (Shared Attributes)

Define attributes once, reuse across classes:

```yaml
slots:
  name:
    range: string
    required: true
  description:
    range: string

classes:
  Supplier:
    slots:
      - name
      - description
    attributes:
      supplier_code:
        range: string

  Product:
    slots:
      - name
      - description
    attributes:
      sku:
        range: string
```

## Complete Example

```yaml
id: https://example.com/schemas/inventory
name: inventory
version: "1.0"
description: "Simple inventory domain"

prefixes:
  linkml: https://w3id.org/linkml/
  vg: https://virt-graph.dev/

imports:
  - linkml:types

default_range: string

classes:
  # Entity Classes (TBox)
  Product:
    description: "A product in inventory"
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: products
      vg:primary_key: id
      vg:identifier: "[sku]"
    attributes:
      sku:
        range: string
        required: true
      name:
        range: string
        required: true
      price:
        range: decimal

  Category:
    description: "Product category"
    instantiates:
      - vg:SQLMappedClass
    annotations:
      vg:table: categories
      vg:primary_key: id
    attributes:
      name:
        range: string
        required: true

  # Relationship Classes (RBox)
  BelongsTo:
    description: "Product belongs to category"
    instantiates:
      - vg:SQLMappedRelationship
    annotations:
      vg:edge_table: products
      vg:domain_key: category_id
      vg:range_key: id
      vg:domain_class: Product
      vg:range_class: Category
      vg:traversal_complexity: GREEN
      vg:functional: true

  SubcategoryOf:
    description: "Category hierarchy"
    instantiates:
      - vg:SQLMappedRelationship
    annotations:
      vg:edge_table: categories
      vg:domain_key: parent_id
      vg:range_key: id
      vg:domain_class: Category
      vg:range_class: Category
      vg:traversal_complexity: YELLOW
      vg:acyclic: true
```

## Validation

Validate your LinkML syntax:

```bash
# Check LinkML structure
poetry run linkml-lint ontology/my_domain.yaml

# Or use the full validation script
make validate-ontology
```

## Next Steps

- [VG Extensions](vg-extensions.md) - Complete reference for VG annotations
- [Creating Ontologies](creating-ontologies.md) - Step-by-step guide
- [Validation](validation.md) - Two-layer validation process
