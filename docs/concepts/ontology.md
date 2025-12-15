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

This classification enables the agentic system to dispatch queries appropriately.

## LinkML Format

VG/SQL ontologies are valid [LinkML schemas](https://linkml.io/linkml/schemas/) with VG extensions. This provides:

- Standard YAML format
- Tooling for validation, documentation, and code generation
- Compatibility with the LinkML ecosystem

## Metamodel Reference

The VG metamodel is defined in `virt_graph.yaml` (at project root) and serves as the **single source of truth** for:

- **Extension classes**: `vg:SQLMappedClass`, `vg:SQLMappedRelationship`
- **Validation rules**: Required fields are derived from the metamodel automatically
- **Enums**: `vg:OperationType` (direct_join, recursive_traversal, etc.)
- **Supporting types**: `vg:WeightColumn`, `vg:DatabaseConnection`

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

**Example (Traversal - Recursive)** *Supply Chain Use Case:*
```yaml
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
    vg:is_hierarchical: true
```

**Example (Algorithm - Network)** *Supply Chain Use Case:*
```yaml
TransportRoute:
  description: "Transport connection between facilities"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: transport_routes
    vg:domain_key: origin_facility_id
    vg:range_key: destination_facility_id
    vg:domain_class: Facility
    vg:range_class: Facility
    vg:operation_types: "[shortest_path, centrality, connected_components, resilience_analysis]"
    vg:is_weighted: true
    vg:weight_columns: '[{"name": "distance_km", "type": "decimal"}, {"name": "cost_usd", "type": "decimal"}]'
  attributes:
    distance_km:
      range: decimal
    cost_usd:
      range: decimal
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

See [Creating Ontologies](../ontology/creating-ontologies.md) for a detailed guide.

