# Ontology System

Virtual Graph uses a LinkML-based ontology with custom extensions to map semantic concepts to physical SQL schema. This enables graph-like queries over relational data.

## Overview

The ontology serves as the **bridge** between:
- **Semantic concepts**: Supplier, Part, SuppliesTo, ComponentOf
- **Physical SQL**: tables, columns, foreign keys

```
┌─────────────────────────────────────────────────────────────┐
│  Natural Language Query                                      │
│  "Find all tier 3 suppliers for Acme Corp"                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Ontology Lookup                                             │
│  - SuppliesTo → supplier_relationships table                 │
│  - domain_key: seller_id, range_key: buyer_id                │
│  - traversal_complexity: YELLOW (recursive BFS)              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Handler Invocation                                          │
│  traverse(edges_table="supplier_relationships",              │
│           edge_from_col="seller_id", ...)                    │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
ontology/
  virt_graph.yaml     # Metamodel - defines extension types
  TEMPLATE.yaml       # Template - starter for new ontologies
  supply_chain.yaml   # Instance - domain-specific ontology
```

### File Purposes

| File | Type | Purpose |
|------|------|---------|
| `virt_graph.yaml` | **Metamodel** | Defines `SQLMappedClass`, `SQLMappedRelationship`, enums. Reference for available annotations. |
| `TEMPLATE.yaml` | **Template** | Commented examples. Copy to create new domain ontology. |
| `supply_chain.yaml` | **Instance** | Actual domain ontology. Load via `OntologyAccessor`. |

### Relationship Diagram

```
┌─────────────────────┐
│  virt_graph.yaml    │  Defines: SQLMappedClass, SQLMappedRelationship,
│  (Metamodel)        │           TraversalComplexity, WeightColumn
└─────────────────────┘
          │
          │ references
          ▼
┌─────────────────────┐
│  TEMPLATE.yaml      │  Shows: How to use vg:table, vg:edge_table,
│  (Starter Template) │         vg:traversal_complexity, etc.
└─────────────────────┘
          │
          │ copy & customize
          ▼
┌─────────────────────┐
│  supply_chain.yaml  │  Contains: Supplier, Part, SuppliesTo,
│  (Domain Instance)  │            ComponentOf, ConnectsTo, etc.
└─────────────────────┘
```

## Ontology Concepts

### TBox: Entity Classes

Entity classes represent **database tables** containing domain objects. They use `instantiates: [vg:SQLMappedClass]`.

**Required annotations:**
| Annotation | Description |
|------------|-------------|
| `vg:table` | SQL table name |
| `vg:primary_key` | Primary key column |

**Optional annotations:**
| Annotation | Description |
|------------|-------------|
| `vg:identifier` | Natural key columns (JSON array) |
| `vg:soft_delete_column` | Soft delete timestamp column |
| `vg:row_count` | Estimated row count |

**Example:**
```yaml
Supplier:
  description: "Organizations that supply parts"
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

### RBox: Relationship Classes

Relationship classes represent **edges/connections** between entities. They use `instantiates: [vg:SQLMappedRelationship]`.

**Required annotations:**
| Annotation | Description |
|------------|-------------|
| `vg:edge_table` | Junction/edge table name |
| `vg:domain_key` | FK column pointing to source |
| `vg:range_key` | FK column pointing to target |
| `vg:domain_class` | Source entity class name |
| `vg:range_class` | Target entity class name |
| `vg:traversal_complexity` | GREEN, YELLOW, or RED |

**Optional annotations (OWL 2 axioms):**
| Annotation | Description |
|------------|-------------|
| `vg:transitive` | R(x,y) ∧ R(y,z) → R(x,z) |
| `vg:symmetric` | R(x,y) → R(y,x) |
| `vg:asymmetric` | R(x,y) → ¬R(y,x) |
| `vg:reflexive` | R(x,x) always valid |
| `vg:irreflexive` | R(x,x) never valid |
| `vg:functional` | At most one target per source |
| `vg:inverse_functional` | At most one source per target |

**Optional annotations (VG extensions):**
| Annotation | Description |
|------------|-------------|
| `vg:acyclic` | DAG constraint (no cycles) |
| `vg:is_hierarchical` | Has tier/level structure |
| `vg:is_weighted` | Has numeric edge weights |
| `vg:inverse_of` | Name of inverse relationship |
| `vg:weight_columns` | JSON array of weight column definitions |

**Example:**
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
    vg:traversal_complexity: YELLOW
    vg:asymmetric: true
    vg:irreflexive: true
    vg:acyclic: true
    vg:cardinality_domain: "0..*"
    vg:cardinality_range: "0..*"
```

### Traversal Complexity

Each relationship is classified by query complexity:

| Complexity | When to Use | Handler |
|------------|-------------|---------|
| **GREEN** | Simple FK join (A → B) | Direct SQL |
| **YELLOW** | Self-referential, needs recursion | `traverse()` |
| **RED** | Self-referential with weights | NetworkX |

**Decision tree:**
```
Is relationship self-referential (domain_class == range_class)?
├── No → GREEN (simple FK join)
└── Yes → Does it have numeric weight columns?
    ├── Yes → RED (network algorithms)
    └── No → YELLOW (recursive traversal)
```

## Discovery Process

Ontology discovery follows a **4-round interactive protocol** defined in `prompts/ontology_discovery.md`.

### End-to-End Workflow

```
┌──────────────────────────────────────────────────────────────┐
│  1. START SESSION                                             │
│     cat prompts/ontology_discovery.md                         │
│     Provide: database connection, schema name                 │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  2. ROUND 1: Schema Introspection                             │
│     - Query information_schema                                │
│     - Identify tables, columns, FKs, constraints              │
│     - Detect self-referential patterns                        │
│     → PAUSE for human review                                  │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  3. ROUND 2: Entity Class Discovery (TBox)                    │
│     - Propose classes with vg:SQLMappedClass                  │
│     - Set vg:table, vg:primary_key, vg:row_count              │
│     - Define attributes with types                            │
│     → PAUSE for human corrections                             │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  4. ROUND 3: Relationship Class Discovery (RBox)              │
│     - Propose classes with vg:SQLMappedRelationship           │
│     - Determine traversal complexity                          │
│     - Set OWL 2 axioms (asymmetric, acyclic, etc.)            │
│     → PAUSE for human corrections                             │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  5. ROUND 4: Draft, Validate & Finalize                       │
│     - Write ontology to ontology/<schema>.yaml                │
│     - Run two-layer validation                                │
│     - Fix errors, run gate tests                              │
│     → PAUSE for human approval                                │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  6. DONE                                                      │
│     Ontology ready for pattern discovery and analysis         │
└──────────────────────────────────────────────────────────────┘
```

### Starting a Discovery Session

```bash
# 1. Ensure database is running
make db-up

# 2. Start Claude Code with the discovery prompt
cat prompts/ontology_discovery.md

# 3. Provide session parameters:
#    Database: postgresql://user:pass@localhost:5432/mydb
#    Schema Name: mydb
```

## Validation

Virtual Graph uses **two-layer validation** because LinkML doesn't validate custom `vg:` annotations.

### Layer 1: LinkML Structure

Validates YAML syntax and LinkML schema structure:

```bash
poetry run linkml-lint --validate-only ontology/supply_chain.yaml
```

**What it checks:**
- YAML syntax is correct
- Classes have valid structure
- Attribute types are valid
- Imports work

### Layer 2: VG Annotations

Validates Virtual Graph-specific requirements:

```bash
poetry run python -c "from virt_graph.ontology import OntologyAccessor; OntologyAccessor()"
```

**What it checks:**
- Entity classes have `vg:table`, `vg:primary_key`
- Relationships have all 6 required annotations
- `vg:traversal_complexity` is GREEN/YELLOW/RED
- `vg:domain_class`/`vg:range_class` reference valid entities

### Running Both Layers

```bash
# Full validation
make validate-ontology

# Or use the script directly
poetry run python scripts/validate_ontology.py

# Validate specific file
poetry run python scripts/validate_ontology.py ontology/my_domain.yaml
```

### Validation Output

```
============================================================
Layer 1: LinkML Structure Validation
============================================================
File: ontology/supply_chain.yaml
✓ LinkML structure validation passed

============================================================
Layer 2: VG Annotation Validation
============================================================
File: ontology/supply_chain.yaml
✓ VG annotation validation passed
  - 8 entity classes (TBox)
  - 13 relationship classes (RBox)

============================================================
Validation Summary
============================================================
  Layer 1 (LinkML Structure): ✓ PASS
  Layer 2 (VG Annotations):   ✓ PASS
============================================================
```

## Programmatic Access

Use `OntologyAccessor` to access ontology data in Python:

```python
from virt_graph.ontology import OntologyAccessor

# Load default ontology (supply_chain.yaml)
ontology = OntologyAccessor()

# Load custom ontology
ontology = OntologyAccessor(Path("ontology/my_domain.yaml"))

# Load without validation (for debugging)
ontology = OntologyAccessor(validate=False)
```

### Accessing Entity Classes (TBox)

```python
# List all entity classes
ontology.classes  # {'Supplier': {...}, 'Part': {...}, ...}

# Get table name
ontology.get_class_table("Supplier")  # "suppliers"

# Get primary key
ontology.get_class_pk("Supplier")  # "id"

# Get natural key columns
ontology.get_class_identifier("Supplier")  # ["supplier_code"]

# Get row count estimate
ontology.get_class_row_count("Supplier")  # 500

# Get soft delete config
ontology.get_class_soft_delete("Supplier")  # (True, "deleted_at")
```

### Accessing Relationship Classes (RBox)

```python
# List all relationships
ontology.roles  # {'SuppliesTo': {...}, 'ComponentOf': {...}, ...}

# Get edge table
ontology.get_role_table("SuppliesTo")  # "supplier_relationships"

# Get FK columns
ontology.get_role_keys("SuppliesTo")  # ("seller_id", "buyer_id")

# Get domain/range classes
ontology.get_role_domain("SuppliesTo")  # "Supplier"
ontology.get_role_range("SuppliesTo")   # "Supplier"

# Get traversal complexity
ontology.get_role_complexity("SuppliesTo")  # "YELLOW"

# Get OWL 2 properties
ontology.get_role_properties("SuppliesTo")
# {'transitive': False, 'symmetric': False, 'asymmetric': True,
#  'reflexive': False, 'irreflexive': True, 'acyclic': True, ...}

# Get weight columns (for RED complexity)
ontology.get_role_weight_columns("ConnectsTo")
# [{'name': 'distance_km', 'type': 'decimal'}, ...]

# Snake_case aliases work too
ontology.get_role_keys("supplies_to")  # Same as "SuppliesTo"
```

### Quick TBox/RBox Summary

```bash
# Show TBox/RBox summary from command line
make show-ontology

# Or use Python
poetry run python -c "
from virt_graph.ontology import OntologyAccessor
o = OntologyAccessor()
print('TBox (Entity Classes):')
for name in o.classes:
    print(f'  {name} -> {o.get_class_table(name)}')
print()
print('RBox (Relationships):')
for name in o.roles:
    print(f'  {name} [{o.get_role_complexity(name)}] -> {o.get_role_table(name)}')
"
```

## Supply Chain Ontology Reference

### TBox: Entity Classes (8)

| Class | Table | PK | Row Count |
|-------|-------|-----|-----------|
| Supplier | suppliers | id | 500 |
| Part | parts | id | 5,003 |
| Product | products | id | 200 |
| Facility | facilities | id | 50 |
| Customer | customers | id | 1,000 |
| Order | orders | id | 20,000 |
| Shipment | shipments | id | 7,995 |
| SupplierCertification | supplier_certifications | id | 721 |

### RBox: Relationships (13)

**YELLOW Complexity (Recursive Traversal):**

| Relationship | Edge Table | Domain → Range |
|--------------|------------|----------------|
| SuppliesTo | supplier_relationships | Supplier → Supplier |
| ComponentOf | bill_of_materials | Part → Part |

**RED Complexity (Network Algorithms):**

| Relationship | Edge Table | Domain → Range | Weight Columns |
|--------------|------------|----------------|----------------|
| ConnectsTo | transport_routes | Facility → Facility | distance_km, cost_usd, transit_time_hours |

**GREEN Complexity (Simple FK Joins):**

| Relationship | Edge Table | Domain → Range |
|--------------|------------|----------------|
| Provides | parts | Supplier → Part |
| CanSupply | part_suppliers | Supplier → Part |
| HoldsCertification | supplier_certifications | Supplier → SupplierCertification |
| ContainsComponent | product_components | Product → Part |
| PlacedBy | orders | Order → Customer |
| ContainsItem | order_items | Order → Product |
| ShipsFrom | orders | Order → Facility |
| Fulfills | shipments | Shipment → Order |
| OriginatesAt | shipments | Shipment → Facility |
| Stores | inventory | Facility → Part |

## Creating a New Ontology

1. **Copy the template:**
   ```bash
   cp ontology/TEMPLATE.yaml ontology/my_domain.yaml
   ```

2. **Update schema metadata:**
   ```yaml
   id: https://virt-graph.dev/schemas/my_domain
   name: my_domain
   version: "1.0"
   description: >-
     My domain ontology for Virtual Graph.

   annotations:
     vg:database_type: postgresql
     vg:connection_string: "postgresql://..."
   ```

3. **Add entity classes** using `vg:SQLMappedClass`

4. **Add relationship classes** using `vg:SQLMappedRelationship`

5. **Validate:**
   ```bash
   poetry run python scripts/validate_ontology.py ontology/my_domain.yaml
   ```

6. **Use in code:**
   ```python
   from virt_graph.ontology import OntologyAccessor
   ontology = OntologyAccessor(Path("ontology/my_domain.yaml"))
   ```

## See Also

- [Ontology Discovery Prompt](../../prompts/ontology_discovery.md) - 4-round discovery protocol
- [Phase 2 Development](../development/phase2.md) - Discovery foundation details
- [Traffic Light Routing](../traffic_light_routing.md) - How complexity maps to handlers
- [Handlers API](../api/handlers.md) - Handler function signatures
