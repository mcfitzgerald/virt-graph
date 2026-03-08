# Supply Chain Process Flows

How the PCG ontology models end-to-end supply chain processes, mapped to the [SCOR Digital Standard](https://www.ascm.org/globalassets/ascm_website_assets/docs/scor/information-model-scor-digital-standard-2025.pdf) (Plan, Source, Make, Deliver, Return, Enable).

These flows demonstrate the progression from **semantic traversal** (document chain joins) to **kinetic modeling** (state machines, graph algorithms, what-if scenarios) — the Phase 2 → Phase 3 bridge described in the [Virtual Twin strategic framework](../planning/Foundations_for_Ontological_Supply_Chain_Virtual_Twins.md).

## Overview

| # | Process Flow | SCOR Process | PCG Domains | VG Operations Used |
|---|---|---|---|---|
| 1 | [Order-to-Cash (O2C)](#1-order-to-cash-o2c) | Deliver | Order, Fulfill, Logistics, Finance | `direct_join`, state machines, financial flow |
| 2 | [Procure-to-Pay (P2P)](#2-procure-to-pay-p2p) | Source | Source, Finance | `direct_join`, axiom validation, three-way match |
| 3 | [BOM Explosion & Production (M2S)](#3-bom-explosion--production-m2s) | Make | Transform, Product | `path_aggregation`, `hierarchical_aggregation`, polymorphic production |
| 4 | [Network Resilience & Disruption](#4-network-resilience--disruption) | Deliver + Plan | Logistics, Fulfill | `shortest_path`, `centrality`, `connected_components`, `resilience_analysis` |
| 5 | [Return & Disposition](#5-return--disposition) | Return | Return, Fulfill, Finance | `direct_join`, state machine branching, reverse flow |

**Conservation groups** tag relationships that together form an end-to-end flow. The `order_to_cash` group tracks material (cases) converting to financial (USD) flow. The `procure_to_pay` group tracks the inverse.

---

## 1. Order-to-Cash (O2C)

**SCOR**: Deliver | **Domains**: Order, Fulfill, Logistics, Finance

The canonical demand-to-revenue cycle. A customer order is placed, fulfilled via shipment, invoiced, and payment collected.

### Entity Chain

```
Channel / RetailLocation
       |
       | OrderFromChannel (source_id, polymorphic: IDs 1-7)
       | OrderForRetailLocation (retail_location_id)
       v
    +--------+     OrderHasLines      +-----------+   OrderLineForSKU    +-----+
    | Order  |----------------------->| OrderLine |-------------------->| SKU |
    +---+----+                        +-----------+                     +--+--+
        |                                                                  ^
        |  (no direct FK -- linked via shared location + SKU context)      |
        v                                                                  |
   +----------+   ShipmentHasLines   +--------------+  ShipmentLineForSKU  |
   | Shipment |-------------------->| ShipmentLine  |----------------------+
   +----+-----+                     +--------------+
        |
        | ARInvoiceForShipment (ar_invoices.shipment_id)
        v
   +------------+   ARInvoiceHasLines   +----------------+  ARInvoiceLineForSKU
   | AR Invoice |--------------------->| ARInvoiceLine  |----------> SKU
   +-----+------+                      +----------------+
         |
         | ARReceiptForInvoice (ar_receipts.invoice_id)
         v
   +-----------+
   | ARReceipt |
   +-----------+
         |
         | GL traceability (gl_journal.reference_type = 'order'/'shipment'/etc.)
         v
   +------------+
   | GL Journal |
   +------------+
```

### Relationships and Joins

| Relationship | Join Path | Notes |
|---|---|---|
| `OrderFromChannel` | `orders.source_id -> channels.id` | Polymorphic: only valid when `source_id <= 7` |
| `OrderForRetailLocation` | `orders.retail_location_id -> retail_locations.id` | Non-polymorphic, preferred for store-level analysis |
| `OrderHasLines` | `order_lines.order_id -> orders.id` | flow_config: material, `order_to_cash` group |
| `OrderLineForSKU` | `order_lines.sku_id -> skus.id` | Product-level demand signal |
| `ShipmentFromOrigin` | `shipments.origin_id` | Polymorphic (no discriminator): parse `route_type` prefix |
| `ShipmentToDestination` | `shipments.destination_id` | Polymorphic (no discriminator): parse `route_type` suffix |
| `ShipmentHasLines` | `shipment_lines.shipment_id -> shipments.id` | flow_config: material, `order_to_cash` group |
| `ShipmentLineForSKU` | `shipment_lines.sku_id -> skus.id` | Fulfillment verification vs. order_lines |
| `ARInvoiceForShipment` | `ar_invoices.shipment_id -> shipments.id` | **Key link**: invoice triggered by delivery |
| `ARInvoiceForCustomer` | `ar_invoices.customer_location_id -> retail_locations.id` | Customer-level revenue |
| `ARInvoiceHasLines` | `ar_invoice_lines.invoice_id -> ar_invoices.id` | flow_config: financial, `order_to_cash` group |
| `ARInvoiceLineForSKU` | `ar_invoice_lines.sku_id -> skus.id` | **Source of truth** for SKU-level revenue |
| `ARReceiptForInvoice` | `ar_receipts.invoice_id -> ar_invoices.id` | flow_config: financial, `order_to_cash` group |

### State Machines

| Entity | State Column | Lifecycle | Data Distribution |
|---|---|---|---|
| Order | `status` | pending -> allocated -> shipped -> delivered | ~88% delivered, ~6% shipped, ~3% allocated, ~3% pending |
| Shipment | `status` | planned -> in_transit -> delivered | ~96% delivered, ~3% in_transit, ~1% planned |
| ARInvoice | `status` | open -> partial -> paid; open -> disputed -> paid / bad_debt | ~97% open, ~2% disputed, ~1% partial |

### VG Operations

All relationships use `direct_join`. The flow exercises:
- **State machines** on Order, Shipment, and ARInvoice
- **Financial flow conservation** via `order_to_cash` group (cases in = cases out; USD invoiced = USD collected)
- **GL traceability** via `gl_journal.reference_type` + `reference_id`
- **Axioms**: Shipment temporal ordering (`arrival_date >= ship_date`), GL daily balance

### Design Notes

**No direct Order -> Shipment FK.** This is realistic — in SAP, billing documents are generated from *delivery documents*, not directly from sales orders. You invoice what you *shipped*, not what was *ordered*, because partial shipments, backorders, and split deliveries mean a 1:1 order-to-invoice mapping doesn't hold. The `ARInvoiceForShipment` relationship captures this correctly.

**Revenue source of truth.** `ar_invoice_lines.line_amount` is the canonical revenue data. The `channel` column on `ar_invoices` is the cleanest path for channel-level revenue analysis (avoids `source_id` polymorphism on orders).

### What-If Scenario

> "What if order volume increases 20% for the MASS_RETAIL channel?"

- `Order.total_cases` has `scenario_params` with `default_perturbation: +20%`, `propagation: downstream`
- Propagation path: Order -> Shipment (freight_cost increases) -> ARInvoice (revenue increases) -> Inventory (stock drawdown accelerates)
- **Graph traversal**: For each affected Order, follow `OrderHasLines -> SKU -> InventoryForSKU` to check if current inventory can absorb the demand spike

---

## 2. Procure-to-Pay (P2P)

**SCOR**: Source | **Domains**: Source, Finance

The mirror image of O2C, on the inbound/supplier side. Raw materials are sourced, received, verified, and paid for.

### Entity Chain

```
   +----------+   SupplierOffersIngredient    +------------+
   | Supplier |----(supplier_ingredients)---->| Ingredient |
   +----+-----+   (edge attrs: unit_cost,    +------+-----+
        |          lead_time, min_order_qty)         |
        |                                           |
        | POForSupplier                             | POLineForIngredient
        v                                           v
   +----------------+   POHasLines   +--------------------+
   | PurchaseOrder  |-------------->| PurchaseOrderLine  |
   +-------+--------+              +--------------------+
           |
           | POAtPlant (purchase_orders.plant_id -> plants.id)
           |
           | GRForPO (goods_receipts linked via shipment)
           v
   +---------------+   GRHasLines   +--------------------+
   | GoodsReceipt  |-------------->| GoodsReceiptLine   |
   +-------+-------+              +--------------------+
           |
           | APInvoiceForGR (ap_invoices.gr_id -> goods_receipts.id)
           v
   +------------+   APInvoiceHasLines   +-----------------+
   | AP Invoice |--------------------->| APInvoiceLine   |
   +-----+------+                      +-----------------+
         |
         |  InvoiceVarianceForAPInvoice (variance detection)
         |
         | APPaymentForInvoice (ap_payments.invoice_id)
         v
   +------------+
   | AP Payment |
   +------------+
         |
         | GL traceability (reference_type = 'purchase_order'/'goods_receipt'/etc.)
         v
   +------------+
   | GL Journal |
   +------------+
```

### Relationships and Joins

| Relationship | Join Path | Notes |
|---|---|---|
| `SupplierOffersIngredient` | `supplier_ingredients` (junction) | **Edge attributes**: unit_cost, lead_time_days, min_order_qty |
| `POForSupplier` | `purchase_orders.supplier_id -> suppliers.id` | Functional (each PO for one supplier) |
| `POAtPlant` | `purchase_orders.plant_id -> plants.id` | Receiving plant |
| `POHasLines` | `purchase_order_lines.po_id -> purchase_orders.id` | flow_config: material, `procure_to_pay` group |
| `POLineForIngredient` | `purchase_order_lines.ingredient_id -> ingredients.id` | What was ordered |
| `GRForShipment` | `goods_receipts.shipment_id -> shipments.id` | Inbound logistics link |
| `GRAtPlant` | `goods_receipts.plant_id -> plants.id` | Where goods were received |
| `GRHasLines` | `goods_receipt_lines.gr_id -> goods_receipts.id` | What was actually received |
| `APInvoiceForGR` | `ap_invoices.gr_id -> goods_receipts.id` | Three-way match anchor |
| `APInvoiceForSupplier` | `ap_invoices.supplier_id -> suppliers.id` | Supplier billing |
| `APInvoiceHasLines` | `ap_invoice_lines.invoice_id -> ap_invoices.id` | What was invoiced |
| `InvoiceVarianceForAPInvoice` | `invoice_variances.invoice_id -> ap_invoices.id` | Price/quantity mismatches |
| `APPaymentForInvoice` | `ap_payments.invoice_id -> ap_invoices.id` | flow_config: financial, `procure_to_pay` group |

### State Machines

| Entity | State Column | Lifecycle | Data Distribution |
|---|---|---|---|
| PurchaseOrder | `status` | draft -> submitted -> confirmed -> received -> closed | ~79% closed, ~11% received, ~5% confirmed, ~3% submitted, ~2% draft |
| GoodsReceipt | `status` | received -> inspected -> posted | ~97% posted, ~2% inspected, ~1% received |
| APInvoice | `status` | open -> paid | 100% open (payments tracked in ap_payments) |

### VG Operations

All relationships use `direct_join`. The flow exercises:
- **Edge attributes** on `SupplierOffersIngredient` — the sourcing matrix with cost/lead time/MOQ for supplier evaluation
- **Three-way match** pattern: PO terms (expected) vs. GR quantities (received) vs. AP invoice amounts (billed)
- **Axiom validation**: `no_duplicate_invoices` on APInvoice (watch for `-DUP` suffix)
- **Financial flow conservation** via `procure_to_pay` group
- **Variance detection** through InvoiceVariance entity (~8% price variances, ~5% quantity variances)

### Design Notes

**Three-way match is a classic ERP audit pattern.** The ontology models it as three separate document entities (PO, GR, AP) linked by FKs, with `InvoiceVariance` capturing the delta. This is exactly how SAP's MM-FI integration works (EKKO/EKPO -> MKPF/MSEG -> RBKP/RSEG).

**Edge attributes on the sourcing junction.** `SupplierOffersIngredient` is one of only three relationships with `vg:edge_attributes`. The unit_cost, lead_time_days, and min_order_qty on `supplier_ingredients` are what make cheapest-supplier and supply-risk analyses possible.

### What-If Scenario

> "What if Supplier X raises prices 15%?"

- `SupplierOffersIngredient.unit_cost` perturbation propagates through PO line amounts -> AP invoice amounts -> GL expense postings
- `Supplier` has `scenario_params` with `default_perturbation: -1 supplier` (supplier loss scenario)
- **Graph traversal**: Follow `SupplierOffersIngredient -> Ingredient -> POLineForIngredient -> PurchaseOrder` to quantify total spend exposure, then `Ingredient -> FormulaHasIngredients -> Formula -> SKU` to identify all affected finished goods and their revenue impact

---

## 3. BOM Explosion & Production (M2S)

**SCOR**: Make | **Domains**: Transform, Product, Source

The manufacturing flow from raw ingredients through formulation to finished goods. This is the only flow that exercises the **hierarchical graph traversal** handlers.

### Entity Chain

```
   +------------+                              +------------+
   | Ingredient |<----FormulaHasIngredients----|  Formula   |
   +------------+   (edge attrs: sequence,     +-----+------+
                      quantity_kg)                    |
                                                     | FormulaForProduct (polymorphic)
                                                     v
                                              +------------------+
                                              | FinishedGood /   |
                                              | BulkIntermediate |
                                              +--------+---------+
                                                       |
                                                       | ProductHasSKUs
                                                       v
                         +-------+   BatchProducesProduct    +-------+
                         | Batch |----(polymorphic)--------->|  SKU  |
                         +---+---+   (type_discriminator:    +-------+
                             |        product_type)
                             |
                             | BatchConsumesIngredient
                             | (edge attrs: quantity_kg)
                             v
                        +------------+
                        | Ingredient |
                        +------------+

    Three-level BOM hierarchy:
    +-----------+     +-------------------+     +--------------+
    | bom_level | --> | bom_level 1       | --> | bom_level 0  |
    |    2      |     | BulkIntermediate  |     | FinishedGood |
    | (premix)  |     |                   |     |              |
    +-----------+     +-------------------+     +--------------+
```

### Relationships and Joins

| Relationship | Join Path | Notes |
|---|---|---|
| `FormulaHasIngredients` | `formula_ingredients` (junction) | **Edge attributes**: sequence, quantity_kg. Operations: `path_aggregation`, `hierarchical_aggregation` |
| `FormulaForProduct` | `formulas.product_id` | **Polymorphic** (`type_discriminator`: product_type -> finished_goods / bulk_intermediates) |
| `ProductHasSKUs` | `skus.product_id -> finished_goods.id` | Product-to-SKU mapping |
| `BatchAtPlant` | `batches.plant_id -> plants.id` | Where production happens |
| `BatchOnLine` | `batches.line_id -> production_lines.id` | Which production line |
| `BatchForWorkOrder` | `batches.work_order_id -> work_orders.id` | Production planning link |
| `BatchProducesProduct` | `batches.product_id` | **Polymorphic** (`type_discriminator`: product_type -> finished_good / bulk_intermediate / premix) |
| `BatchConsumesIngredient` | `batch_ingredients` (junction) | **Edge attributes**: quantity_kg. flow_config: material, `procure_to_pay` group |

### State Machines

| Entity | State Column | Lifecycle | Data Distribution |
|---|---|---|---|
| Batch | `status` | planned -> in_progress -> complete -> released | ~85% released, ~8% complete, ~5% in_progress, ~2% planned |
| WorkOrder | `status` | planned -> in_progress -> complete | Varies |

### VG Operations

This flow uniquely exercises the **traversal and aggregation handlers**:

- **`path_aggregation`** on `FormulaHasIngredients`: "How much of Ingredient X is needed to make 1 unit of Finished Good Y?" — traverse the BOM tree, multiply quantities at each level
- **`hierarchical_aggregation`**: Roll up costs, weights, or quantities through the 3-level BOM hierarchy (premix -> bulk intermediate -> finished good)
- **Polymorphic type discriminators**: `BatchProducesProduct` uses `product_type` to resolve whether the output is a finished_good, bulk_intermediate, or premix
- **Mass balance axiom**: Input ingredient quantity_kg should equal output batch quantity_kg (within variance tolerance)

### Design Notes

**Three-level BOM hierarchy.** Formulas have `bom_level`: 0 (finished good), 1 (bulk intermediate), 2 (premix). The `FormulaHasIngredients` relationship's `ingredient_id` is itself polymorphic — it can point to `ingredients` OR `bulk_intermediates`. This means a BOM explosion must traverse recursively.

**This is the graph traversal root-cause use case.** The Foundations paper describes: "If a customer order is at risk, an agent follows the edges backward from the Order to the Shipment, then to the Vehicle, and finally to a Risk Event." In PCG, the equivalent is: follow backward from a SKU through the BOM to find which ingredients it depends on, then forward through `SupplierOffersIngredient` to identify supplier risk.

### What-If Scenario

> "What if we lose access to Ingredient X (e.g., a key emulsifier)?"

1. **Identify impact**: `path_aggregate()` traverses `FormulaHasIngredients` upward from Ingredient X to find all Formulas that use it
2. **Cascade to products**: Follow `FormulaForProduct -> ProductHasSKUs` to identify all affected SKUs
3. **Quantify revenue exposure**: Follow `SKU -> ARInvoiceLineForSKU` to sum `line_amount` — total revenue at risk
4. **Find alternatives**: Query `SupplierOffersIngredient` for the same ingredient from different suppliers, compare `unit_cost` and `lead_time_days`

This is a single connected traversal across Source -> Transform -> Product -> Finance domains, demonstrating the ontology's cross-domain linking power.

---

## 4. Network Resilience & Disruption

**SCOR**: Deliver + Plan | **Domains**: Logistics, Fulfill

The transport network connecting plants, DCs, and retail locations. This is the **only flow that uses the graph algorithm handlers** — it treats `route_segments` as a weighted directed graph.

### Network Structure

```
   +----------+     +-------+     +-------+     +--------------+     +---------+
   | Supplier |---->| Plant |---->|  RDC  |---->| Customer DC  |---->|  Store  |
   +----------+     +---+---+     +---+---+     +------+-------+     +---------+
                        |             |  ^              |
                        |             +--+ lateral      |
                        |             RDC-to-RDC        |
                        |             (12 edges)        |
                        +-------------------------------+
                          plant_to_customer_dc (direct)

   4,025 directed edges in route_segments
   Edge weights: distance_km, transit_time_hours
   Node types: supplier, plant, rdc, customer_dc, store
```

### Relationships and Joins

| Relationship | Join Path | Notes |
|---|---|---|
| `RouteSegmentOrigin` | `route_segments.origin_id` | **Polymorphic** (`type_discriminator`: origin_type -> supplier/plant/rdc/customer_dc) |
| `RouteSegmentDestination` | `route_segments.destination_id` | **Polymorphic** (`type_discriminator`: destination_type -> plant/rdc/customer_dc/store) |
| `ShipmentFromOrigin` | `shipments.origin_id` | Polymorphic (no discriminator): infer from `route_type` |
| `ShipmentToDestination` | `shipments.destination_id` | Polymorphic (no discriminator): infer from `route_type` |

### VG Operations

This flow exercises all four **graph algorithm handlers**:

| Handler | Use Case | Weight Column |
|---|---|---|
| `shortest_path()` | Optimal route from Plant to Store | `distance_km` or `transit_time_hours` |
| `all_shortest_paths()` | Alternative routes when primary is disrupted | `distance_km` |
| `centrality()` | Identify critical hub nodes (betweenness, PageRank) | — |
| `connected_components()` | Find isolated subnetworks after a disruption | — |
| `resilience_analysis()` | Impact of removing a node (plant outage, DC closure) | — |

### Network Topology Details

- **6 RDCs** serve as regional consolidation hubs (Chicago, Allentown, Jacksonville, Memphis, Phoenix, Reno)
- **56 customer DCs** serve as retailer/channel warehouses
- **12 lateral RDC-to-RDC edges** (6 bidirectional pairs) enable transshipment between regions
- **~29% of customer DCs** are multi-source (served by 2 upstream RDCs)
- **4 plants** (Dallas, Columbus, Atlanta, Sacramento) are the origin points
- The network is **not a strict tree** — lateral links and multi-source DCs make shortest-path and centrality analyses non-trivial

### Design Notes

**Dual edge weights.** `distance_km` for cost optimization, `transit_time_hours` for speed optimization. Different what-if scenarios use different weights.

**Polymorphic endpoints with clean discriminators.** Unlike Shipment (which has no discriminator), `route_segments` has explicit `origin_type` and `destination_type` columns. The type values are: `supplier`, `plant`, `rdc`, `customer_dc`, `store` (NOT `dc` or `retail`).

**This is where graph databases traditionally shine.** The route_segments table is a classic adjacency list representing a weighted directed graph. VG/SQL's handlers (`shortest_path`, `centrality`, etc.) provide graph-database-equivalent operations directly over this SQL table, without migration to Neo4j.

### What-If Scenario

> "What if Plant-TX (Dallas) goes offline for 2 weeks?"

1. **`resilience_analysis()`**: Remove Plant-TX node, measure impact on network connectivity and reachability
2. **`connected_components()`**: Check if any customer DCs become unreachable (isolated subgraphs)
3. **`shortest_path()`**: For affected DCs, find alternative routes from remaining plants (Columbus, Atlanta, Sacramento)
4. **`centrality()`**: Identify which RDCs become critical bottlenecks under the rerouted flow
5. **Cascade to O2C**: Follow `ShipmentFromOrigin` to find all in-flight shipments from Plant-TX, trace to `ARInvoice` for revenue at risk

This is the canonical "stress test" scenario described in the [Databricks supply chain stress testing framework](https://www.databricks.com/blog/stress-testing-supply-chain-networks-scale-databricks) and the [McKinsey digital twin for supply chains](https://www.mckinsey.com/capabilities/quantumblack/our-insights/digital-twins-the-key-to-unlocking-end-to-end-supply-chain-growth).

---

## 5. Return & Disposition

**SCOR**: Return | **Domains**: Return, Fulfill, Finance

Reverse logistics — goods coming back from customers through inspection and disposition.

### Entity Chain

```
   +------------------+                    +---------------------+
   | RetailLocation   |                    | DistributionCenter  |
   | (source store)   |                    | (processing DC)     |
   +--------+---------+                    +----------+----------+
            |                                         ^
            | ReturnFromSource                        | ReturnAtDC
            | (returns.source_id)                     | (returns.dc_id)
            v                                         |
        +--------+       ReturnHasLines       +------------+
        | Return |--------------------------->| ReturnLine |
        +---+----+                            +-----+------+
            |                                       |
            |                                       | ReturnLineForSKU
            |                                       | (return_lines.sku_id)
            |                                       v
            |                                    +-----+
            |                                    | SKU |
            |                                    +-----+
            |
            | DispositionForReturn
            v
   +-----------------+
   | DispositionLog  |
   +-----------------+
         |
         | disposition outcome:
         |   restock  --> back to Inventory
         |   rework   --> new Batch
         |   destroy  --> write-off (GL)
         |   donate   --> write-off (GL)
         |
         v
   +------------+
   | GL Journal |  (reference_type = 'return')
   +------------+
```

### Relationships and Joins

| Relationship | Join Path | Notes |
|---|---|---|
| `ReturnFromSource` | `returns.source_id -> retail_locations.id` | Originating store |
| `ReturnAtDC` | `returns.dc_id -> distribution_centers.id` | Processing/inspection DC |
| `ReturnHasLines` | `return_lines.return_id -> returns.id` | What was returned |
| `ReturnLineForSKU` | `return_lines.sku_id -> skus.id` | Which product returned |
| `DispositionForReturn` | `disposition_logs.return_id -> returns.id` | Disposition outcome |

### State Machine

| Entity | State Column | Lifecycle | Data Distribution |
|---|---|---|---|
| Return | `status` | requested -> approved -> received -> processed | ~91% processed, ~4% received, ~2% approved, ~2% requested |

### VG Operations

All relationships use `direct_join`. The flow exercises:
- **Linear state machine** on Return (simplest lifecycle — good introductory example)
- **Condition-based branching**: `return_lines.condition` (sellable, damaged, expired) determines the disposition path
- **Reconnection to forward chain**: restocked items re-enter Inventory; reworked items create new Batches
- **Financial impact tracing**: disposition write-offs appear as GL entries

### Design Notes

**Shortest and simplest flow.** Only 5 entities and 5 relationships. Makes a good introductory example before tackling O2C or BOM explosion.

**Condition drives branching logic.** The `condition` column on `return_lines` is the decision point:
- `sellable` -> restock (back to inventory at the DC)
- `damaged` / `expired` -> destroy or donate (GL write-off)
- Other -> rework (new Batch in the Transform domain)

This is a real-world decision tree that an LLM agent would need to understand to answer questions like "What percentage of returns are restockable?" or "What's the financial impact of damaged goods returns?"

**Connects back to O2C.** Returns reference the original order implicitly (same SKU + same retail location). For credit memo analysis, trace `Return -> ReturnLineForSKU -> SKU -> ARInvoiceLineForSKU -> ARInvoice` to find the original revenue transaction.

### What-If Scenario

> "What if return rates double for damaged goods in the MASS_RETAIL channel?"

1. **Identify scope**: Filter `return_lines` where `condition = 'damaged'`, join through `Return -> ReturnFromSource -> RetailLocation` where `channel = 'MASS_RETAIL'`
2. **Financial impact**: Double the `disposition_logs.quantity_cases` for destroy/donate outcomes, trace to GL write-off amounts
3. **Inventory impact**: Fewer cases restocked -> inventory drawdown at DCs -> potential stockout cascade
4. **Revenue impact**: Trace to original ARInvoice for credit memo exposure

---

## Cross-Flow Connections

The five flows are not isolated — they connect through shared entities:

```
                    +-----+
          +-------->| SKU |<--------+
          |         +--+--+         |
          |            |            |
     OrderLineForSKU   |    ARInvoiceLineForSKU
          |            |            |
  +-------+--+   ProductHasSKUs  +-+----------+
  | OrderLine |        |         | ARInvLine  |
  +----------+   +----+----+    +------------+
                  |Fin.Good |
                  +----+----+
                       ^
                FormulaForProduct
                       |
                  +----+----+     FormulaHasIngredients    +------------+
                  | Formula |----------------------------->| Ingredient |
                  +---------+                              +-----+------+
                                                                 ^
                                                     SupplierOffersIngredient
                                                                 |
                                                           +-----+----+
                                                           | Supplier |
                                                           +----------+
```

**Example cross-flow query**: "Which suppliers should we worry about if MASS_RETAIL order volume increases 20%?"

1. **O2C**: Identify the top SKUs by volume in MASS_RETAIL orders
2. **M2S**: BOM-explode those SKUs to find their ingredient dependencies
3. **P2P**: Check `SupplierOffersIngredient` for each ingredient — are there alternative suppliers? What are the lead times?
4. **Network**: Run `resilience_analysis()` on the transport links from those suppliers' origins to our plants
5. **Return**: Check historical return rates for those SKUs to adjust the net demand forecast

This single question traverses all five flows and four of the five SCOR processes (Source, Make, Deliver, Return). The ontology's cross-domain relationships make this possible without any custom integration — just follow the edges.

---

## Mapping to the Virtual Twin Roadmap

These process flows bridge the strategic framework's implementation phases:

| Phase | What the Process Flows Demonstrate |
|---|---|
| **Phase 2: Semantic Mapping** | Every relationship is a named, typed, annotated semantic link from ontology to SQL |
| **Phase 3: Kinetic Modeling** | State machines (6 entities), axioms (mass balance, GL balance, temporal order), flow conservation groups |
| **Phase 4: Intelligence Layer** | `vg:context` blocks with `llm_prompt_hint` on all 88 elements enable Ontology Augmented Generation (OAG) |
| **Phase 5: Decision Support** | `vg:scenario_params` (6 entities) + `vg:actions` (6 entities) power what-if analysis |

The process flows are the **executable documentation** of the ontology — they show not just what entities exist, but how they participate in real business processes and how the VG operation types map to concrete analytical questions.
