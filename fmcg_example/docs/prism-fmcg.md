# Prism Consumer Goods (PCG) - Domain Documentation

## Overview

Prism Consumer Goods is a **surrogate FMCG supply chain** modeled after companies like Colgate-Palmolive. It demonstrates the "Formula-to-Shelf" pipeline with high-velocity, massive-volume patterns.

**Spec Reference**: `magical-launching-forest.md`

## Company Profile

- **Company**: Prism Consumer Goods (PCG)
- **Revenue**: ~$15B global CPG
- **HQ**: Knoxville, TN
- **Product Lines**:
  - **PrismWhite** (Oral Care) - Toothpaste
  - **ClearWave** (Home Care) - Dish Soap
  - **AquaPure** (Personal Care) - Body Wash

## Global Structure

### 5 Divisions

| Division | HQ | Plants | Markets |
|----------|-----|--------|---------
| NAM | Knoxville | 2 (Tennessee, Texas) | US, Canada |
| LATAM | São Paulo | 1 (Brazil) | Brazil, Mexico, Andean |
| APAC | Singapore | 2 (China, India) | China, India, SEA, ANZ |
| EUR | Paris | 1 (Poland) | Western EU, UK, Nordics |
| AFR-EUR | Dubai | 1 (Turkey) | MENA, Sub-Saharan, CIS |

### Channel Mix

| Channel | Volume Share | Archetypes |
|---------|--------------|------------|
| B&M Large | 40% | MegaMart, ValueClub, UrbanEssential |
| B&M Distributor | 30% | RegionalGrocers, IndieRetail |
| E-commerce | 20% | DigitalFirst, OmniRetailer |
| DTC | 10% | PrismDirect |

## SCOR-DS Domain Model

PCG implements the full SCOR-DS (Supply Chain Operations Reference - Digital Standard) framework:

```
                              ┌─────────────────┐
                              │      PLAN       │
                              │  demand_forecasts│
                              │  capacity_plans  │
                              │  supply_plans    │
                              └────────┬────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             │                             ▼
┌─────────────────┐                    │                    ┌─────────────────┐
│     ORDER       │                    │                    │     SOURCE      │
│  orders         │◄───── DEMAND ──────┼────── SUPPLY ─────►│  purchase_orders│
│  promotions     │                    │                    │  suppliers      │
└────────┬────────┘                    │                    └────────┬────────┘
         │                    ┌────────┴────────┐                    │
         │                    │   ORCHESTRATE   │                    │
         │                    │  kpi_thresholds │                    │
         │                    │  risk_events    │                    │
         │                    └────────┬────────┘                    │
         │                             │                             │
         ▼                             │                             ▼
┌─────────────────┐                    │                    ┌─────────────────┐
│     FULFILL     │                    │                    │    TRANSFORM    │
│  shipments      │◄───── OUTPUT ──────┼────── INPUT ──────►│  batches        │
│  inventory      │                    │                    │  formulas       │
└────────┬────────┘                    │                    └────────┬────────┘
         │                             │                             │
         └─────────────────────────────┼─────────────────────────────┘
                                       │
                              ┌────────┴────────┐
                              │     RETURN      │
                              │  returns        │
                              │  disposition_logs│
                              └─────────────────┘
```

## Key Differentiators from Aerospace Example

| Aspect | Original (supply_chain_example) | FMCG (fmcg_example) |
|--------|--------------------------------|---------------------|
| Graph Shape | Deep BOM recursion (25+ levels) | Horizontal fan-out (1 → 50,000) |
| Volume | Low volume, high complexity | High velocity, massive volume |
| Stress Test | "Can VG/SQL traverse deep?" | "Can VG/SQL traverse wide?" |
| Products | Industrial components | Consumer goods |
| Key Metric | BOM explosion cost | Recall trace speed |

## The Desmet Triangle

Every edge in the PCG model carries three dimensions:

1. **Service** - OTIF (On-Time In-Full), OSA (On-Shelf Availability)
2. **Cost** - Landed cost, freight cost, handling cost
3. **Cash** - Inventory days, payment terms, working capital

These are in constant tension: improving service often increases cost and ties up cash.

## Named Entities for Testing

| Entity | Code | Purpose |
|--------|------|---------|
| Contaminated Batch | B-2024-RECALL-001 | Recall trace testing |
| MegaMart (Hub) | ACCT-MEGA-001 | Hub stress test (4,500 stores) |
| Palm Oil Supplier | SUP-PALM-MY-001 | SPOF detection (single source) |
| Chicago DC | DC-NAM-CHI-001 | Centrality testing (2,000 stores) |
| Black Friday Promo | PROMO-BF-2024 | Bullwhip effect testing |
| Seasonal Lane | LANE-SH-LA-001 | Temporal routing (50% capacity Jan-Feb) |

## FMCG Benchmarks

| Metric | Industrial | FMCG (Target) |
|--------|-----------|---------------|
| Inventory Turns | 3-5/year | 8-12/year |
| Perfect Order (OTIF) | 80-85% | 95-98% |
| On-Shelf Availability | N/A | 92-95% |
| Batch Yield | 60-85% | 95-99% |
| Forecast Accuracy (MAPE) | N/A | 20-30% |

## Implementation Status

- [ ] Phase 1: Directory Structure - **SCAFFOLD COMPLETE**
- [ ] Phase 2: Schema (~60 tables)
- [ ] Phase 3: Ontology (LinkML + VG extensions)
- [ ] Phase 4: Data Generator (~4M rows)
- [ ] Phase 5: Beast Mode Tests
- [ ] Phase 6: Neo4j Comparison

## Related Documents

- Full specification: `magical-launching-forest.md`
- Ontology: `ontology/prism_fmcg.yaml`
- Schema: `postgres/schema.sql`
- Validation queries: `scripts/validate_realism.sql`
