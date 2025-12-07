# Supply Chain Example

This worked example demonstrates Virtual Graph using a realistic supply chain domain. You'll see how graph-like queries work over relational data, from simple lookups to complex network analysis.

## What You'll Learn

By working through this example, you will:

1. **Set up the environment** - PostgreSQL database with ~130K rows of synthetic supply chain data
2. **Understand the ontology** - How LinkML defines entities and relationships with SQL mappings
3. **Explore query patterns** - Templates for common graph operations
4. **Execute queries** - Step-by-step walkthroughs of GREEN/YELLOW/RED complexity routes
5. **Run benchmarks** - Compare performance against Neo4j

## The Supply Chain Domain

The example models a multi-tier manufacturing supply chain:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUPPLY CHAIN DOMAIN                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Tier 3          Tier 2          Tier 1         Assembly      │
│  Suppliers  →   Suppliers  →   Suppliers  →    (Products)      │
│                                                                 │
│  ┌─────┐        ┌─────┐        ┌─────┐         ┌─────────┐    │
│  │Raw  │───────▶│Sub- │───────▶│Final│────────▶│ Product │    │
│  │Mat'l│        │Comp.│        │Parts│         │ SKU-001 │    │
│  └─────┘        └─────┘        └─────┘         └─────────┘    │
│                                                      │         │
│                    Bill of Materials (BOM)           │         │
│                    Recursive Part → Part             ▼         │
│                                               ┌─────────┐      │
│   ┌─────────┐    Transport    ┌─────────┐    │Customer │      │
│   │ Factory │───Routes (km,──▶│Warehouse│───▶│ Orders  │      │
│   └─────────┘    cost, time)  └─────────┘    └─────────┘      │
│                                                                 │
│                    Facility Network                             │
│                    Weighted Graph                               │
└─────────────────────────────────────────────────────────────────┘
```

### Key Entities

| Entity | Count | Description |
|--------|-------|-------------|
| Supplier | 500 | Organizations across 3 tiers |
| Part | 5,003 | Components with BOM relationships |
| Product | 200 | Finished goods (SKUs) |
| Facility | 50 | Warehouses, factories, distribution centers |
| Customer | 1,000 | B2B and B2C customers |
| Order | 20,000 | Purchase orders with line items |
| Shipment | 7,995 | Physical goods movement |

### Key Relationships

| Relationship | Type | Count | Description |
|--------------|------|-------|-------------|
| SuppliesTo | YELLOW | 817 | Tier-to-tier supplier relationships |
| ComponentOf | YELLOW | 14,283 | Bill of materials hierarchy |
| ConnectsTo | RED | 197 | Weighted transport routes |
| CanSupply | GREEN | 7,582 | Supplier-part approvals |
| OrderContains | GREEN | 60,241 | Order line items |

## Prerequisites

Before starting, ensure you have:

- **Python 3.12+** - The project uses modern Python features
- **Docker & Docker Compose** - For PostgreSQL (and optionally Neo4j)
- **Poetry** - Python package manager ([installation guide](https://python-poetry.org/docs/#installation))
- **~2GB disk space** - For Docker images and data

## Time Estimate

| Section | Activity |
|---------|----------|
| Setup | Install dependencies, start database |
| Ontology | Review supply_chain.yaml structure |
| Patterns | Explore pattern templates |
| Queries | Run example queries |
| Benchmark | Compare against Neo4j |

## Named Test Entities

The synthetic data includes named entities for consistent testing:

**Suppliers:**
- "Acme Corp" - Tier 1 supplier
- "GlobalTech Industries" - Tier 2 supplier
- "Pacific Components" - Tier 3 supplier

**Products:**
- "Turbo Encabulator" (SKU: TURBO-001) - Complex assembly
- "Flux Capacitor" (SKU: FLUX-001) - High-value product

**Facilities:**
- "Chicago Warehouse" (FAC-CHI) - Major distribution hub
- "LA Distribution Center" (FAC-LA) - West coast hub

These entities appear throughout the examples for reproducible queries.

## Next Steps

1. [**Setup**](setup.md) - Install dependencies and start the database
2. [**Ontology**](ontology.md) - Tour the supply chain ontology
3. [**Patterns**](patterns.md) - Learn query pattern templates
4. [**Queries**](queries.md) - Execute step-by-step examples
5. [**Benchmark**](benchmark.md) - Run performance comparisons
