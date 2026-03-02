# Ontology System

VG/SQL uses an ontology to map graph concepts to relational database structures. The ontology is expressed in [LinkML](https://linkml.io) format with VG-specific extensions.

## Core Concepts

### TBox and RBox

The ontology separates entity definitions from relationship definitions:

| Layer | Description | VG Extension |
|-------|-------------|--------------|
| **TBox** (Entity Classes) | Concepts that map to database tables | `vg:SQLMappedClass` |
| **RBox** (Relationship Classes) | Roles that map to foreign key relationships | `vg:SQLMappedRelationship` |

This separation follows description logic conventions and enables clear reasoning about:
- What entities exist (TBox)
- How entities relate (RBox)
- What operations are needed to traverse relationships (operation type annotations)

### Operation Types

Each relationship is annotated with operation types that determine which handlers can be used:

| Category | Operation Types | Handler |
|----------|-----------------|---------|
| **Direct** | `direct_join` | None needed (SQL) |
| **Traversal** | `recursive_traversal`, `temporal_traversal` | `traverse()` |
| **Aggregation** | `path_aggregation`, `hierarchical_aggregation` | `path_aggregate()` |
| **Algorithm** | `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` | NetworkX-based handlers |
| **Kinetic** | `flow_analysis`, `state_analysis`, `scenario_analysis` | Ad-hoc SQL via Claude (handlers planned) |

This classification enables the agentic system to dispatch queries appropriately.

### Kinetic Extensions (v3.0)

The metamodel supports virtual kinetics — declaring dynamic behavior (state machines, flows, actions) as metadata annotations on the existing SQL data. No new handlers are required; Claude generates ad-hoc SQL using the metadata.

| Feature | Annotation | Description |
|---------|------------|-------------|
| Axioms | `vg:axioms` | SQL-evaluable constraints (mass balance, temporal order, GL balance) |
| State Machines | `vg:state_machine` | Lifecycle states and valid transitions |
| Flow Config | `vg:flow_config` | Material/financial flow metadata for throughput analysis |
| Actions | `vg:actions` | Semantic mutation docs for what-if reasoning |
| Scenario Params | `vg:scenario_params` | Perturbable attributes with propagation direction |

See [VG Extensions](vg-extensions.md) for complete reference.

## Class Hierarchy and Base Schema

Domain ontologies can import `scm_base.yaml` for reusable structural patterns via LinkML's native `imports:` mechanism. This provides:

- **Abstract classes**: `Location`, `TransactionDocument`, `LineItem` — common patterns with shared slots
- **Mixins**: `HasActiveFlag` (is_active soft-delete), `HasName` (display name) — cross-cutting concerns
- **Shared slots**: `name`, `status`, `is_active`, `day`, `quantity_kg`, `line_amount`, `total_amount`
- **Enums**: `LocationType` (`plant`, `dc`, `retail`) for polymorphic location references

Abstract classes do NOT have `instantiates: vg:SQLMappedClass` — they have `abstract: true`. Only concrete children in the domain ontology get `instantiates`. The `OntologyAccessor` automatically excludes abstract and mixin classes from TBox/RBox.

Use `get_class_inherited_attributes(name)` to see all attributes including inherited ones from parent classes and mixins.

## LinkML Format

VG/SQL ontologies are valid [LinkML schemas](https://linkml.io/linkml/schemas/) with VG extensions. This provides:

- Standard YAML format
- Tooling for validation, documentation, and code generation
- Compatibility with the LinkML ecosystem

## Metamodel Reference

The VG metamodel is defined in `virt_graph.yaml` (at project root) and serves as the **single source of truth** for:

- **Extension classes**: `vg:SQLMappedClass`, `vg:SQLMappedRelationship`
- **Validation rules**: Required fields are derived from the metamodel automatically
- **Enums**: `vg:OperationType`, `vg:AxiomType`, `vg:FlowType`, `vg:ActionEffectType`, `vg:PropagationDirection`
- **Supporting types**: `vg:WeightColumn`, `vg:DatabaseConnection`, `vg:Axiom`, `vg:StateMachine`, `vg:FlowConfig`, `vg:Action`, `vg:ScenarioParam`

The `OntologyAccessor` reads `virt_graph.yaml` (from project root) via LinkML's SchemaView to dynamically extract validation rules. This means:
- Adding a required field to `SQLMappedClass` in the metamodel automatically updates validation
- No hardcoded duplication between YAML and Python code

### Basic Structure

```yaml
# Schema metadata
id: https://virt-graph.dev/schemas/my_domain
name: my_domain
version: "1.0"
description: "My domain ontology"

# Required prefixes
prefixes:
  linkml: https://w3id.org/linkml/
  vg: https://virt-graph.dev/

imports:
  - linkml:types

default_range: string

# Database connection (optional)
annotations:
  vg:database_type: postgresql
  vg:database_version: "14"

# Define classes
classes:
  # Entity classes (TBox)
  MyEntity:
    instantiates:
      - vg:SQLMappedClass
    # ...

  # Relationship classes (RBox)
  MyRelationship:
    instantiates:
      - vg:SQLMappedRelationship
    # ...
```

## VG Extensions

VG extensions use the `vg:` prefix and are expressed as LinkML annotations.

### Entity Classes (TBox)

Entity classes represent database tables. They must instantiate `vg:SQLMappedClass`.

**Required annotations** (defined in `virt_graph.yaml` SQLMappedClass):
- `vg:table` - SQL table name
- `vg:primary_key` - Primary key column(s) - supports composite keys via JSON array

**Optional annotations** (also from SQLMappedClass):
- `vg:identifier` - Natural key column(s) as JSON array
- `vg:soft_delete_column` - Soft delete timestamp column
- `vg:row_count` - Estimated row count for query planning
- `vg:context` - Structured context for AI query generation (ContextBlock)

**Example:**
```yaml
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
    name:
      range: string
      required: true
    tier:
      range: integer
```

### Relationship Classes (RBox)

Relationship classes represent foreign key relationships. They must instantiate `vg:SQLMappedRelationship`.

**Required annotations** (defined in `virt_graph.yaml` SQLMappedRelationship):
- `vg:edge_table` - Junction/edge table name
- `vg:domain_key` - FK column(s) pointing to domain class - list for composite keys
- `vg:range_key` - FK column(s) pointing to range class - list for composite keys
- `vg:domain_class` - Name(s) of the domain class(es) - list for polymorphism
- `vg:range_class` - Name(s) of the range class(es) - list for polymorphism
- `vg:operation_types` - List of supported operations (from OperationType enum)

**Optional annotations** (also from SQLMappedRelationship):

*OWL 2 Role Axioms:*
- `vg:transitive` - R(x,y) and R(y,z) implies R(x,z)
- `vg:symmetric` - R(x,y) implies R(y,x)
- `vg:asymmetric` - R(x,y) implies NOT R(y,x)
- `vg:reflexive` - R(x,x) always holds
- `vg:irreflexive` - R(x,x) never holds (no self-loops)
- `vg:functional` - At most one range per domain
- `vg:inverse_functional` - At most one domain per range

*VG Extensions:*
- `vg:acyclic` - DAG constraint (no cycles)
- `vg:is_hierarchical` - Has tier/level structure
- `vg:is_weighted` - Has numeric edge weights
- `vg:inverse_of` - Name of inverse relationship
- `vg:weight_columns` - JSON array of weight column definitions
- `vg:sql_filter` - SQL WHERE clause to filter edges during traversal
- `vg:edge_attributes` - Property Graph style edge properties (non-weight columns)
- `vg:context` - Structured AI context (ContextBlock) for query generation
- `vg:type_discriminator` - Polymorphic target type resolution configuration

*Cardinality:*
- `vg:cardinality_domain` - e.g., "0..*", "1..1"
- `vg:cardinality_range` - e.g., "0..*", "0..1"

**Example (Direct - Simple FK):**
```yaml
BelongsToCategory:
  description: "Entity belongs to a category"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: entities
    vg:domain_key: category_id
    vg:range_key: id
    vg:domain_class: Entity
    vg:range_class: Category
    vg:operation_types: "[direct_join]"
    vg:functional: true
```

**Example (Traversal - Recursive)** *PCG Supply Chain Use Case:*
```yaml
SKUSupersedes:
  description: "SKU supersedes another SKU (alias/replacement chain)"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: skus
    vg:domain_key: id
    vg:range_key: supersedes_sku_id
    vg:domain_class: SKU
    vg:range_class: SKU
    vg:operation_types: '["direct_join", "recursive_traversal"]'
    vg:asymmetric: true
    vg:irreflexive: true
    vg:acyclic: true
```

**Example (Algorithm - Network)** *PCG Transport Network:*
```yaml
RouteSegmentOrigin:
  description: "Route segment originates from a location (polymorphic)"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: route_segments
    vg:domain_key: id
    vg:range_key: origin_id
    vg:domain_class: RouteSegment
    vg:range_class: '["Plant", "DistributionCenter", "RetailLocation"]'
    vg:operation_types: '["direct_join", "shortest_path", "centrality", "connected_components", "resilience_analysis"]'
    vg:is_weighted: true
    vg:weight_columns: '[{"name": "distance_km", "type": "decimal", "unit": "km"}, {"name": "transit_time_hours", "type": "decimal", "unit": "hours"}]'
```

## Cardinality Notation

| Notation | Meaning |
|----------|---------|
| `"1..1"` | Exactly one (required) |
| `"0..1"` | Zero or one (optional) |
| `"1..*"` | One or more |
| `"0..*"` | Zero or more |

## Validation

VG/SQL uses two-layer validation:

### Layer 1: LinkML Structure

Validates YAML syntax and LinkML schema structure:

```bash
poetry run linkml-lint --validate-only ontology/my_domain.yaml
```

### Layer 2: VG Annotations

Validates VG-specific annotations. Rules are derived from `virt_graph.yaml`:

```python
from virt_graph.ontology import OntologyAccessor

# Raises OntologyValidationError if invalid
ontology = OntologyAccessor("ontology/my_domain.yaml", validate=True)
```

The `OntologyAccessor` loads `virt_graph.yaml` via LinkML's SchemaView to:
- Extract required fields from `SQLMappedClass` and `SQLMappedRelationship`
- Extract valid values from `OperationType` enum
- Validate domain ontologies against these dynamically-loaded rules

### Full Validation Script

```bash
# Validate all ontologies
poetry run python scripts/validate_ontology.py --all

# Validate specific ontology
poetry run python scripts/validate_ontology.py ontology/my_domain.yaml
```

## Accessing the Ontology

Use `OntologyAccessor` to programmatically access ontology data:

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor("ontology/my_domain.yaml")

# Get all entity classes (TBox)
for cls in ontology.classes:
    print(f"{cls['name']}: {cls['table']}")

# Get all relationship classes (RBox)
for role in ontology.roles:
    op_types = ontology.get_operation_types(role['name'])
    print(f"{role['name']}: {op_types}")

# Get relationships by operation type
traversal_roles = [r for r in ontology.roles
                   if 'recursive_traversal' in ontology.get_operation_types(r['name'])]
```

## Creating a New Ontology

Ontologies are created through an interactive, guided process using Claude. The process follows a 4-round discovery protocol that automatically introspects your database schema and generates a complete LinkML ontology.

### The Discovery Process

1. **Round 1: Schema Introspection** - Claude queries `information_schema` to discover tables, columns, foreign keys, constraints, and patterns (soft deletes, natural keys, etc.)

2. **Round 2: Entity Class Discovery (TBox)** - For each entity table, Claude proposes LinkML classes with `vg:SQLMappedClass`, including required annotations (`vg:table`, `vg:primary_key`) and optional ones (`vg:identifier`, `vg:soft_delete_column`, `vg:row_count`)

3. **Round 3: Relationship Class Discovery (RBox)** - For each foreign key relationship, Claude proposes LinkML classes with `vg:SQLMappedRelationship`, determining operation types and OWL 2 role axioms based on the schema structure

4. **Round 4: Draft, Validate & Finalize** - Claude writes the complete ontology file, performs two-layer validation (LinkML structure + VG annotations), and fixes any errors

After each round, you review and provide corrections before proceeding. The process uses the discovery protocol defined in `prompts/ontology_discovery.md`.

See [Creating Ontologies](ontology-creation.md) for a detailed guide.

---

## LinkML Format Reference

VG/SQL ontologies are written in [LinkML](https://linkml.io), a modeling language for linked data. This section covers the basics of LinkML as used in VG/SQL.

### Why LinkML?

- **Standard YAML format** - Human-readable, version-controllable
- **Validation tooling** - Built-in linting and schema validation
- **Ecosystem compatibility** - Export to JSON Schema, OWL, SHACL
- **Extensibility** - Custom annotations via prefixes

### Ontology File Structure

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

### Defining Entity Classes (TBox)

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

#### Key Elements

| Element | Purpose |
|---------|---------|
| `instantiates: [vg:SQLMappedClass]` | Marks this as an entity class |
| `annotations` | VG-specific metadata (table mapping, etc.) |
| `attributes` | Column definitions |
| `range` | Attribute data type |
| `required` | Whether NULL is allowed |

### Defining Relationship Classes (RBox)

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
      vg:operation_types: "[recursive_traversal, temporal_traversal]"
      vg:asymmetric: true
      vg:irreflexive: true
      vg:acyclic: true
    attributes:
      relationship_type:
        range: string
      contract_value:
        range: decimal
```

#### Key Elements

| Element | Purpose |
|---------|---------|
| `instantiates: [vg:SQLMappedRelationship]` | Marks this as a relationship class |
| `vg:edge_table` | Junction/edge table name |
| `vg:domain_key` | FK pointing to source entity |
| `vg:range_key` | FK pointing to target entity |
| `vg:domain_class` / `vg:range_class` | Entity classes at each end |
| `vg:operation_types` | Supported operations (direct_join, recursive_traversal, etc.) |

### Attribute Ranges (Data Types)

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

### Attribute Modifiers

#### Required Fields

```yaml
attributes:
  supplier_code:
    range: string
    required: true      # NOT NULL
```

#### Multivalued (Arrays)

```yaml
attributes:
  tags:
    range: string
    multivalued: true   # Array of strings
```

#### Identifiers

```yaml
attributes:
  supplier_code:
    range: string
    identifier: true    # Natural key (unique)
```

### Enums

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

### Inheritance

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

### Slots (Shared Attributes)

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

### Complete Example

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
      vg:operation_types: "[direct_join]"
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
      vg:operation_types: "[recursive_traversal]"
      vg:acyclic: true
```

### LinkML Validation

Validate your LinkML syntax:

```bash
# Check LinkML structure
poetry run linkml-lint ontology/my_domain.yaml

# Or use the full validation script
poetry run python scripts/validate_ontology.py --all
```

## Next Steps

- [VG Extensions](vg-extensions.md) - Complete reference for VG annotations
- [Creating Ontologies](ontology-creation.md) - Step-by-step guide
- [Validation](validation.md) - Two-layer validation process
