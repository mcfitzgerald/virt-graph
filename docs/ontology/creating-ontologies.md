# Creating Ontologies

VG/SQL ontologies are created through an interactive discovery process with Claude. This guide walks through the 4-round protocol.

## Overview

The discovery protocol introspects your database schema and generates a complete LinkML ontology with VG extensions. Claude handles the technical details; you provide domain knowledge.

```
Round 1: Schema Introspection    → Discover tables, FKs, constraints
Round 2: Entity Discovery (TBox) → Propose entity classes
Round 3: Relationship Discovery  → Propose relationship classes
Round 4: Draft & Validate        → Write ontology, run validation
```

After each round, you review and correct before proceeding.

## Prerequisites

- PostgreSQL database running and accessible
- VG/SQL installed (`make install`)
- Claude Code session active

## Starting a Discovery Session

Tell Claude the database connection details:

```
Create an ontology for my database at postgresql://user:pass@localhost:5432/mydb
```

Claude will begin with Round 1 automatically.

## Round 1: Schema Introspection

Claude queries `information_schema` to discover:

- Tables with columns and data types
- Foreign key relationships
- Self-referential tables (same table on both ends of FK)
- Check constraints (especially self-reference prevention)
- Unique constraints (natural key candidates)

### Pattern Recognition

| Pattern | Interpretation |
|---------|----------------|
| `deleted_at` column | Soft delete enabled |
| `_id` suffix columns | Foreign keys |
| Two FKs to same table | Edge/relationship table |
| `code`, `number` unique columns | Natural key candidates |

### Your Input

Review the table summary. Correct any misunderstandings:

- "The `audit_log` table is for logging, not a domain entity"
- "The `supplier_code` column is the business identifier"
- "The `supplier_relationships` table represents a DAG, not a general graph"

## Round 2: Entity Discovery (TBox)

Claude proposes entity classes for each table. Example:

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

### Your Input

Review class proposals:

- "Rename `SupplierRelationship` to `SupplierNetwork` for clarity"
- "The `tier` attribute should have a description explaining 1=direct, 2=second-level"
- "Don't include `audit_log` as an entity class"

## Round 3: Relationship Discovery (RBox)

Claude proposes relationship classes for each FK. This is the most critical round.

### Complexity Determination

| Pattern | Complexity |
|---------|------------|
| Simple FK (A → B) | GREEN |
| Self-referential (A → A) | YELLOW |
| Self-referential + weights | RED |

### Example GREEN Relationship

```yaml
PlacedBy:
  description: "Order was placed by customer"
  instantiates:
    - vg:SQLMappedRelationship
  annotations:
    vg:edge_table: orders
    vg:domain_key: customer_id
    vg:range_key: id
    vg:domain_class: Order
    vg:range_class: Customer
    vg:traversal_complexity: GREEN
    vg:functional: true
```

### Example YELLOW Relationship

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
    vg:is_hierarchical: true
```

### Example RED Relationship

```yaml
ConnectsTo:
  description: "Transport route between facilities"
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
    vg:weight_columns: '[{"name": "distance_km", "type": "decimal"}]'
```

### Key Questions Claude Will Ask

For YELLOW/RED relationships:

1. **Inverse pairs**: "Do users need to traverse in both directions?"
   - YES → Create inverse (e.g., `ComponentOf` / `HasComponent`)
   - NO → Single relationship is sufficient

2. **Traversal semantics**: "What do inbound/outbound mean in business terms?"
   - Document clearly (e.g., inbound = "upstream suppliers")

3. **Transitivity**: "If A→B and B→C, does A→C hold?"
   - Usually NO for supply chains, YES for `partOf` relationships

4. **Symmetry**: "If A→B, does B→A always hold?"
   - Symmetric relationships don't need inverses

### Your Input

Review relationship proposals:

- "The `SuppliesTo` relationship should be `acyclic: true` since we don't allow circular supplier chains"
- "Add an inverse `SuppliedBy` relationship"
- "The `distance_km` weight column is the one used for routing"

## Round 4: Draft & Validate

Claude writes the complete ontology and runs validation.

### Two-Layer Validation

**Layer 1: LinkML Structure**
```bash
poetry run linkml-lint --validate-only ontology/my_domain.yaml
```
Checks YAML syntax and LinkML schema structure.

**Layer 2: VG Annotations**
```python
from virt_graph.ontology import OntologyAccessor

# Raises OntologyValidationError if invalid
ontology = OntologyAccessor("ontology/my_domain.yaml", validate=True)
```
Checks VG-specific requirements (required annotations, valid complexity values, etc.).

### Common Validation Errors

| Error | Fix |
|-------|-----|
| "Missing required annotation: vg:table" | Add `vg:table` to entity class |
| "Invalid traversal_complexity: Yellow" | Use uppercase: `YELLOW` |
| "Unknown domain_class: supplier" | Match class name exactly: `Supplier` |

### Your Input

Review the complete ontology file. Request changes if needed:

- "Add a description to the `ConnectsTo` relationship"
- "The row count for suppliers is outdated, please re-query"

## Post-Discovery

After the ontology is created:

### Verify with Tests

```bash
# Run validation tests
poetry run pytest tests/test_gate2_validation.py -v

# Run all tests
make test
```

### View the Ontology

```bash
# Show TBox/RBox summary
make show-ontology
```

### Use in Queries

```python
from virt_graph.ontology import OntologyAccessor

ontology = OntologyAccessor("ontology/my_domain.yaml")

# Get table for entity
table = ontology.get_class_table("Supplier")

# Get complexity for relationship
complexity = ontology.get_role_complexity("SuppliesTo")

# List all relationships by complexity
yellow_roles = ontology.get_roles_by_complexity("YELLOW")
```

## Tips for Good Ontologies

### 1. Be Specific About Semantics

Don't just accept default names. Use domain-specific terminology:
- `SuppliesTo` instead of `SupplierToSupplier`
- `ComponentOf` instead of `PartToPart`

### 2. Document Traversal Direction

For YELLOW/RED relationships, always clarify what inbound/outbound means:
```yaml
SuppliesTo:
  description: "Supplier sells to another supplier. Inbound = upstream (who sells to me), Outbound = downstream (who do I sell to)"
```

### 3. Consider Inverse Pairs

If users will ask questions in both directions, create inverse relationships:
- "What parts make up this assembly?" → `HasComponent`
- "What assemblies use this part?" → `ComponentOf`

### 4. Set Realistic Complexity

- Don't mark simple FKs as YELLOW
- Don't mark hierarchies without weights as RED
- The complexity determines handler dispatch

### 5. Include Row Counts

Row counts help with query planning:
```yaml
vg:row_count: 500
```

Re-query if data volume changes significantly.

## Discovery Protocol Reference

The full protocol is defined in `prompts/ontology_discovery.md`. It includes:

- Detailed SQL queries for schema introspection
- Complete annotation reference
- Robustness checklist for quality assurance
- OOPS! pitfall avoidance guidelines

## Next Steps

- [LinkML Format](linkml-format.md) - LinkML basics
- [VG Extensions](vg-extensions.md) - Complete annotation reference
- [Validation](validation.md) - Validation details
