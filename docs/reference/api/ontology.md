# Ontology API Reference

This reference documents the `OntologyAccessor` class and related utilities for programmatic access to Virtual Graph ontologies.

## Overview

The ontology system maps semantic concepts to physical SQL schema:

```
Semantic Concept  →  OntologyAccessor  →  SQL Parameters
   "Supplier"     →                    →  table="suppliers"
   "SuppliesTo"   →                    →  edge_table="supplier_relationships"
```

---

## Module: `virt_graph.ontology`

### `OntologyAccessor`

```python
class OntologyAccessor:
    """
    Provides programmatic access to LinkML ontology with VG extensions.

    Validates ontology on load and provides typed access to entity
    classes (TBox) and relationship classes (RBox).
    """
```

#### Constructor

```python
def __init__(
    self,
    ontology_path: Path | None = None,
    validate: bool = True,
)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `ontology_path` | `Path \| None` | `None` | Path to ontology YAML. None = default `supply_chain.yaml` |
| `validate` | `bool` | `True` | Run VG annotation validation on load |

**Raises:** `ValueError` if validation fails.

**Example:**

```python
from pathlib import Path
from virt_graph.ontology import OntologyAccessor

# Load default ontology (supply_chain.yaml)
ontology = OntologyAccessor()

# Load custom ontology
ontology = OntologyAccessor(Path("ontology/my_domain.yaml"))

# Load without validation (for debugging)
ontology = OntologyAccessor(validate=False)
```

---

## Properties

### `classes`

```python
@property
def classes(self) -> dict[str, dict]
```

All entity classes (TBox) in the ontology.

**Returns:** Dictionary of class name to class definition.

```python
ontology.classes
# {'Supplier': {...}, 'Part': {...}, 'Product': {...}, ...}
```

### `roles`

```python
@property
def roles(self) -> dict[str, dict]
```

All relationship classes (RBox) in the ontology.

**Returns:** Dictionary of role name to role definition.

```python
ontology.roles
# {'SuppliesTo': {...}, 'ComponentOf': {...}, 'ConnectsTo': {...}, ...}
```

---

## Entity Class Methods (TBox)

### `get_class_table()`

```python
def get_class_table(self, class_name: str) -> str
```

Get the SQL table name for an entity class.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `class_name` | `str` | Entity class name (e.g., `"Supplier"`) |

**Returns:** Table name string.

**Raises:** `KeyError` if class not found.

```python
ontology.get_class_table("Supplier")  # "suppliers"
ontology.get_class_table("Part")      # "parts"
```

---

### `get_class_pk()`

```python
def get_class_pk(self, class_name: str) -> str
```

Get the primary key column for an entity class.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `class_name` | `str` | Entity class name |

**Returns:** Primary key column name.

```python
ontology.get_class_pk("Supplier")  # "id"
```

---

### `get_class_identifier()`

```python
def get_class_identifier(self, class_name: str) -> list[str]
```

Get natural key columns for an entity class.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `class_name` | `str` | Entity class name |

**Returns:** List of column names forming the natural key.

```python
ontology.get_class_identifier("Supplier")  # ["supplier_code"]
ontology.get_class_identifier("Part")      # ["part_number"]
```

---

### `get_class_row_count()`

```python
def get_class_row_count(self, class_name: str) -> int | None
```

Get estimated row count for an entity class.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `class_name` | `str` | Entity class name |

**Returns:** Row count estimate, or `None` if not specified.

```python
ontology.get_class_row_count("Supplier")  # 500
ontology.get_class_row_count("Order")     # 20000
```

---

### `get_class_soft_delete()`

```python
def get_class_soft_delete(self, class_name: str) -> tuple[bool, str | None]
```

Get soft delete configuration for an entity class.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `class_name` | `str` | Entity class name |

**Returns:** Tuple of `(has_soft_delete, column_name)`.

```python
ontology.get_class_soft_delete("Supplier")
# (True, "deleted_at")

ontology.get_class_soft_delete("Order")
# (False, None)
```

---

## Relationship Class Methods (RBox)

### `get_role_table()`

```python
def get_role_table(self, role_name: str) -> str
```

Get the edge table name for a relationship.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `role_name` | `str` | Relationship name (supports PascalCase or snake_case) |

**Returns:** Edge table name.

```python
ontology.get_role_table("SuppliesTo")    # "supplier_relationships"
ontology.get_role_table("supplies_to")   # "supplier_relationships" (alias)
ontology.get_role_table("ComponentOf")   # "bill_of_materials"
```

---

### `get_role_keys()`

```python
def get_role_keys(self, role_name: str) -> tuple[str, str]
```

Get foreign key columns for a relationship.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `role_name` | `str` | Relationship name |

**Returns:** Tuple of `(domain_key, range_key)`.

```python
ontology.get_role_keys("SuppliesTo")
# ("seller_id", "buyer_id")

ontology.get_role_keys("ComponentOf")
# ("child_part_id", "parent_part_id")

ontology.get_role_keys("ConnectsTo")
# ("origin_facility_id", "destination_facility_id")
```

---

### `get_role_domain()`

```python
def get_role_domain(self, role_name: str) -> str
```

Get the domain (source) entity class for a relationship.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `role_name` | `str` | Relationship name |

**Returns:** Domain class name.

```python
ontology.get_role_domain("SuppliesTo")   # "Supplier"
ontology.get_role_domain("ConnectsTo")   # "Facility"
```

---

### `get_role_range()`

```python
def get_role_range(self, role_name: str) -> str
```

Get the range (target) entity class for a relationship.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `role_name` | `str` | Relationship name |

**Returns:** Range class name.

```python
ontology.get_role_range("SuppliesTo")    # "Supplier"
ontology.get_role_range("Provides")      # "Part"
```

---

### `get_role_complexity()`

```python
def get_role_complexity(self, role_name: str) -> str
```

Get the traversal complexity classification.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `role_name` | `str` | Relationship name |

**Returns:** `"GREEN"`, `"YELLOW"`, or `"RED"`.

```python
ontology.get_role_complexity("Provides")     # "GREEN"
ontology.get_role_complexity("SuppliesTo")   # "YELLOW"
ontology.get_role_complexity("ConnectsTo")   # "RED"
```

**Complexity Meanings:**

| Complexity | Handler | Description |
|------------|---------|-------------|
| GREEN | Direct SQL | Simple FK join |
| YELLOW | `traverse()` | Recursive BFS |
| RED | NetworkX | Network algorithms |

---

### `get_role_properties()`

```python
def get_role_properties(self, role_name: str) -> dict[str, bool]
```

Get OWL 2 and VG properties for a relationship.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `role_name` | `str` | Relationship name |

**Returns:** Dictionary of property flags.

```python
ontology.get_role_properties("SuppliesTo")
# {
#     'transitive': False,
#     'symmetric': False,
#     'asymmetric': True,
#     'reflexive': False,
#     'irreflexive': True,
#     'functional': False,
#     'inverse_functional': False,
#     'acyclic': True,
#     'is_hierarchical': True,
#     'is_weighted': False,
# }
```

---

### `get_role_weight_columns()`

```python
def get_role_weight_columns(self, role_name: str) -> list[dict[str, str]]
```

Get weight columns for RED complexity relationships.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `role_name` | `str` | Relationship name |

**Returns:** List of weight column definitions.

```python
ontology.get_role_weight_columns("ConnectsTo")
# [
#     {'name': 'distance_km', 'type': 'decimal'},
#     {'name': 'cost_usd', 'type': 'decimal'},
#     {'name': 'transit_time_hours', 'type': 'decimal'},
# ]

ontology.get_role_weight_columns("SuppliesTo")
# []  (YELLOW complexity, no weights)
```

---

### `get_role_cardinality()`

```python
def get_role_cardinality(self, role_name: str) -> tuple[str, str]
```

Get cardinality constraints for a relationship.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `role_name` | `str` | Relationship name |

**Returns:** Tuple of `(domain_cardinality, range_cardinality)`.

```python
ontology.get_role_cardinality("SuppliesTo")
# ("0..*", "0..*")

ontology.get_role_cardinality("Provides")
# ("1..1", "0..*")  # Each part has exactly one primary supplier
```

---

## Name Resolution

The accessor supports both PascalCase class names and snake_case aliases:

```python
# Both work identically
ontology.get_role_keys("SuppliesTo")
ontology.get_role_keys("supplies_to")

ontology.get_role_complexity("ComponentOf")
ontology.get_role_complexity("component_of")
```

---

## Validation

### Two-Layer Validation

Virtual Graph uses two validation layers:

**Layer 1: LinkML Structure**
```bash
poetry run linkml-lint --validate-only ontology/supply_chain.yaml
```

**Layer 2: VG Annotations**
```bash
poetry run python -c "from virt_graph.ontology import OntologyAccessor; OntologyAccessor()"
```

### What Layer 2 Validates

- Entity classes have required `vg:table`, `vg:primary_key`
- Relationships have all 6 required annotations:
  - `vg:edge_table`
  - `vg:domain_key`
  - `vg:range_key`
  - `vg:domain_class`
  - `vg:range_class`
  - `vg:traversal_complexity`
- `vg:traversal_complexity` is GREEN, YELLOW, or RED
- `vg:domain_class` and `vg:range_class` reference valid entity classes

### Running Validation

```bash
# Full two-layer validation
make validate-ontology

# Or use the script
poetry run python scripts/validate_ontology.py

# Validate specific file
poetry run python scripts/validate_ontology.py ontology/my_domain.yaml
```

---

## Usage Examples

### Complete Handler Parameter Resolution

```python
from virt_graph.ontology import OntologyAccessor
from virt_graph.handlers import traverse

ontology = OntologyAccessor()

# Get all parameters needed for traverse()
nodes_table = ontology.get_class_table("Supplier")
edges_table = ontology.get_role_table("SuppliesTo")
domain_key, range_key = ontology.get_role_keys("SuppliesTo")

# Execute traversal
result = traverse(
    conn,
    nodes_table=nodes_table,           # "suppliers"
    edges_table=edges_table,           # "supplier_relationships"
    edge_from_col=domain_key,          # "seller_id"
    edge_to_col=range_key,             # "buyer_id"
    start_id=42,
    direction="inbound",
)
```

### Route Classification

```python
def classify_route(ontology: OntologyAccessor, role_name: str) -> str:
    """Determine which handler to use for a relationship."""
    complexity = ontology.get_role_complexity(role_name)

    if complexity == "GREEN":
        return "direct_sql"
    elif complexity == "YELLOW":
        return "traverse"
    else:  # RED
        weights = ontology.get_role_weight_columns(role_name)
        if weights:
            return "shortest_path"
        return "centrality"

# Usage
route = classify_route(ontology, "ConnectsTo")  # "shortest_path"
```

### Building Query Parameters from Ontology

```python
def build_traversal_params(
    ontology: OntologyAccessor,
    relationship: str,
    start_class: str,
    start_id: int,
) -> dict:
    """Build traverse() parameters from ontology lookup."""
    return {
        "nodes_table": ontology.get_class_table(start_class),
        "edges_table": ontology.get_role_table(relationship),
        "edge_from_col": ontology.get_role_keys(relationship)[0],
        "edge_to_col": ontology.get_role_keys(relationship)[1],
        "start_id": start_id,
    }

params = build_traversal_params(ontology, "SuppliesTo", "Supplier", 42)
```

---

## Supply Chain Ontology Reference

### TBox: Entity Classes

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

### RBox: Relationships by Complexity

**GREEN (Simple FK Join):**

| Relationship | Edge Table | Domain → Range |
|--------------|------------|----------------|
| Provides | parts | Supplier → Part |
| CanSupply | part_suppliers | Supplier → Part |
| ContainsComponent | product_components | Product → Part |
| HoldsCertification | supplier_certifications | Supplier → Certification |
| PlacedBy | orders | Order → Customer |
| ContainsItem | order_items | Order → Product |
| ShipsFrom | orders | Order → Facility |
| Fulfills | shipments | Shipment → Order |
| OriginatesAt | shipments | Shipment → Facility |
| Stores | inventory | Facility → Part |

**YELLOW (Recursive Traversal):**

| Relationship | Edge Table | Domain → Range |
|--------------|------------|----------------|
| SuppliesTo | supplier_relationships | Supplier → Supplier |
| ComponentOf | bill_of_materials | Part → Part |

**RED (Network Algorithms):**

| Relationship | Edge Table | Domain → Range | Weights |
|--------------|------------|----------------|---------|
| ConnectsTo | transport_routes | Facility → Facility | distance_km, cost_usd, transit_time_hours |

---

## See Also

- [Handlers API Reference](handlers.md) - Handler function signatures
- [Estimator API Reference](estimator.md) - Size estimation
- [Concepts Overview](../../concepts/overview.md) - System overview
