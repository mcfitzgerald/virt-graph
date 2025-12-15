# Ontology Generation Comparison Report

This report compares a fresh ontology generated via the discovery protocol (`supply_chain_test.yaml`) against the existing hand-crafted ontology (`supply_chain.yaml`).

## Test Execution Summary

| Test | Description | Result |
|------|-------------|--------|
| Test 1 | Validate metamodel (virt_graph.yaml) | **PASS** |
| Test 2 | Validate existing ontology (supply_chain.yaml) | **PASS** |
| Test 3 | Verify dynamic rule loading | **PASS** |
| Test 4 | Create new ontology via discovery protocol | **PASS** |
| Test 5 | Validate new ontology (supply_chain_test.yaml) | **PASS** |
| Test 6 | Compare ontologies | **PASS** |
| Test 7 | Run full validation script | **PASS** |
| Test 8 | Run ontology validation tests (28 tests) | **PASS** |

## Validation Results

### Test 3: Dynamic Rule Loading
Validation rules correctly derived from `virt_graph.yaml` metamodel:
```
Entity required fields: {'primary_key', 'table'}
Relationship required fields: {'range_key', 'range_class', 'edge_table', 'traversal_complexity', 'domain_class', 'domain_key'}
Valid complexities: {'RED', 'YELLOW', 'GREEN'}
```

### Test 5: New Ontology Validation
- **Layer 1 (LinkML Structure):** No problems found
- **Layer 2 (VG Annotations):** Loaded 16 classes, 21 roles

## Comparison: Existing vs Fresh Ontology

### Entity Classes (TBox)

| Metric | Existing | Fresh | Delta |
|--------|----------|-------|-------|
| Total Classes | 9 | 16 | +7 |

**Existing Ontology Classes:**
```
Customer, Facility, Inventory, Order, Part, Product, Shipment, Supplier, SupplierCertification
```

**Fresh Ontology Classes:**
```
AuditLog, BillOfMaterials, Customer, Facility, Inventory, Order, OrderItem, Part,
PartSupplier, Product, ProductComponent, Shipment, Supplier, SupplierCertification,
SupplierRelationship, TransportRoute
```

**Additional Classes in Fresh Ontology:**
- `AuditLog` - Audit tracking table
- `BillOfMaterials` - Junction table exposed as entity
- `OrderItem` - Order line items exposed as entity
- `PartSupplier` - Junction table exposed as entity
- `ProductComponent` - Junction table exposed as entity
- `SupplierRelationship` - Junction table exposed as entity
- `TransportRoute` - Transport route entity

### Relationship Classes (RBox)

| Metric | Existing | Fresh | Delta |
|--------|----------|-------|-------|
| Total Roles | 16 | 21 | +5 |

**Existing Ontology Relationships:**
```
CanSupply, ComponentOf, ConnectsTo, ContainsComponent, ForOrder, HasCertification,
HasComponent, InventoryAt, InventoryOf, OrderContains, OriginatesAt, PlacedBy,
PrimarySupplier, ShipsFrom, SuppliesTo, UsesRoute
```

**Fresh Ontology Relationships:**
```
CanSupply, ComponentOf, Comprises, ConnectedFrom, ConnectsTo, Contains, FulfillsOrder,
HasCertification, HasComponent, HasPrimarySupplier, OrdersProduct, PlacedBy, ShipsFrom,
ShipsFromFacility, ShipsToFacility, SoldAs, StoredAt, Stores, SuppliedBy, SuppliesTo, UsesRoute
```

### Complexity Distribution

| Complexity | Existing | Fresh | Description |
|------------|----------|-------|-------------|
| **GREEN** | 12 | 15 | Simple FK joins (direct SQL) |
| **YELLOW** | 3 | 4 | Recursive traversal (BFS handlers) |
| **RED** | 1 | 2 | Network algorithms (NetworkX) |

### Key Differences

#### 1. Junction Tables as Entities
The fresh ontology exposes junction tables as first-class entities:
- `BillOfMaterials`, `PartSupplier`, `ProductComponent`, `SupplierRelationship`

This is a modeling choice - both approaches are valid. The existing ontology treats these as pure relationships.

#### 2. Inverse Relationships
The fresh ontology created additional inverse pairs:
- `SuppliedBy` (inverse of `SuppliesTo`)
- `ConnectedFrom` (inverse of `ConnectsTo`)
- `Stores` (inverse of `StoredAt`)
- `SoldAs` (inverse of `Comprises`)

This provides bidirectional traversal semantics for common query patterns.

#### 3. Naming Conventions
Some relationships have different names but similar semantics:
| Existing | Fresh | Semantic Equivalent |
|----------|-------|---------------------|
| `PrimarySupplier` | `HasPrimarySupplier` | Yes |
| `ContainsComponent` | `Comprises` | Yes |
| `ForOrder` | `FulfillsOrder` | Yes |
| `OriginatesAt` | `ShipsFromFacility` | Yes |
| `OrderContains` | `Contains` + `OrdersProduct` | Split differently |
| `InventoryAt`, `InventoryOf` | `StoredAt`, `Stores` | Renamed |

#### 4. Additional Coverage
Fresh ontology includes:
- `ShipsToFacility` - Shipment destination relationship
- `OrderItem` entity - Order line items as separate entity

## Conclusions

### Strengths of Fresh Ontology
1. **More complete coverage** - All tables including junction tables mapped
2. **Bidirectional traversal** - Inverse relationships for all self-referential tables
3. **Accurate row counts** - Derived directly from database statistics
4. **Full DDL metadata** - Index and constraint information captured

### Strengths of Existing Ontology
1. **Cleaner abstraction** - Junction tables hidden behind relationships
2. **Simpler class count** - 9 vs 16 classes easier to understand
3. **Human-curated semantics** - Names like `ContainsComponent` are more intuitive

### Recommendation
Both ontologies are valid and pass all validation layers. The choice depends on use case:
- **Fresh ontology**: Better for complete database mapping and bidirectional queries
- **Existing ontology**: Better for abstracted domain model with cleaner semantics

The discovery protocol successfully generates a valid, comprehensive ontology that captures all schema relationships with correct complexity classifications.

## Test Evidence

### Full Validation Script Output
```
Found 3 ontology file(s) to validate
  - supply_chain_test.yaml: PASS (16 entity classes, 21 relationship classes)
  - supply_chain.yaml: PASS (9 entity classes, 16 relationship classes)
  - virt_graph.yaml: PASS (metamodel)
```

### Gate Tests (28/28 passed)
```
tests/test_ontology_validation.py - 28 passed in 2.28s
```
- LinkML structure validation
- VG annotation validation
- Table coverage validation
- FK column existence validation
- Self-referential edge integrity
- Query complexity classification
- Named entity existence
- Data distribution sanity checks
