-- ============================================================================
-- Prism Consumer Goods (PCG) - FMCG Supply Chain Schema
-- ============================================================================
--
-- Spec: magical-launching-forest.md Phase 2
-- Target: ~60 tables, ~4M rows after seeding
--
-- SCOR-DS Domains:
--   A. SOURCE (Procurement & Inbound)
--   B. TRANSFORM (Manufacturing)
--   C. PRODUCT (SKU Master)
--   D. ORDER (Demand Signal)
--   E. FULFILL (Outbound)
--   E2. LOGISTICS (Transport Network)
--   E3. ESG/SUSTAINABILITY
--   F. PLAN (Demand & Supply Planning)
--   G. RETURN (Regenerate)
--   H. ORCHESTRATE (Hub)
--
-- Implementation Status: SCAFFOLD
-- TODO: Implement full DDL in Phase 2
-- ============================================================================

-- ============================================================================
-- DOMAIN A: SOURCE (Procurement & Inbound) - SCOR: Source
-- ============================================================================
-- Tables: ingredients, suppliers, supplier_ingredients, certifications,
--         purchase_orders, purchase_order_lines, goods_receipts, goods_receipt_lines

-- TODO: ingredients - Raw chemicals with CAS numbers, purity, storage requirements
-- TODO: suppliers - Global supplier network (Tier 1/2/3) with qualification status
-- TODO: supplier_ingredients - M:M with lead times, MOQs, costs
-- TODO: certifications - ISO, GMP, Halal, Kosher, RSPO certifications
-- TODO: purchase_orders - POs to suppliers (the procurement cycle)
-- TODO: purchase_order_lines - PO line items with ingredient, qty, price
-- TODO: goods_receipts - Receipt of goods from suppliers (closes SOURCE loop)
-- TODO: goods_receipt_lines - Actual received qty, lot numbers, quality status

-- ============================================================================
-- DOMAIN B: TRANSFORM (Manufacturing) - SCOR: Transform
-- ============================================================================
-- Tables: plants, production_lines, formulas, formula_ingredients,
--         work_orders, work_order_materials, batches, batch_ingredients, batch_cost_ledger

-- TODO: plants - 7 manufacturing facilities globally
-- TODO: production_lines - Manufacturing line capacity (resource side of Plan)
-- TODO: formulas - Recipe/BOM definitions with yield parameters
-- TODO: formula_ingredients - Composition with sequence, quantities (composite PK)
-- TODO: work_orders - Scheduled production (links Plan to Transform)
-- TODO: work_order_materials - Planned material consumption per work order
-- TODO: batches - Production lots with QC status, expiry
-- TODO: batch_ingredients - Actual consumption for mass balance
-- TODO: batch_cost_ledger - Material, labor, energy, overhead costs

-- ============================================================================
-- DOMAIN C: PRODUCT (SKU Master) - Shared across ORDER/FULFILL
-- ============================================================================
-- Tables: products, packaging_types, skus, sku_costs, sku_substitutes

-- TODO: products - Product families (PrismWhite, ClearWave, AquaPure)
-- TODO: packaging_types - Tubes, bottles, sizes, regional variants
-- TODO: skus - The explosion point (~2,000 SKUs)
-- TODO: sku_costs - Standard costs by type
-- TODO: sku_substitutes - Substitute/equivalent SKUs (symmetric relationship)

-- ============================================================================
-- DOMAIN D: ORDER (Demand Signal) - SCOR: Order
-- ============================================================================
-- Tables: channels, promotions, orders, order_lines, order_allocations

-- TODO: channels - 4 channel types (B&M Large, B&M Dist, Ecom, DTC)
-- TODO: promotions - Trade promos with lift multipliers and hangover effects
-- TODO: orders - Customer orders (~200K)
-- TODO: order_lines - Line items with SKU, qty, price (composite PK)
-- TODO: order_allocations - ATP/allocation of inventory to orders

-- ============================================================================
-- DOMAIN E: FULFILL (Outbound) - SCOR: Fulfill
-- ============================================================================
-- Tables: divisions, distribution_centers, ports, retail_accounts,
--         retail_locations, shipments, shipment_lines, inventory, pick_waves

-- TODO: divisions - 5 global divisions (NAM, LATAM, APAC, EUR, AFR-EUR)
-- TODO: distribution_centers - ~25 DCs globally
-- TODO: ports - Ocean/air freight nodes for multi-leg routing
-- TODO: retail_accounts - Archetype-based accounts (~100)
-- TODO: retail_locations - Individual stores (~10,000)
-- TODO: shipments - Physical movements (~180K)
-- TODO: shipment_lines - Items with batch numbers for lot tracking (~540K)
-- TODO: inventory - Stock by location with aging buckets
-- TODO: pick_waves - Picking/packing execution (optional detail)

-- ============================================================================
-- DOMAIN E2: LOGISTICS (Transport Network)
-- ============================================================================
-- Tables: carriers, carrier_contracts, carrier_rates, route_segments,
--         routes, route_segment_assignments, shipment_legs

-- TODO: carriers - Carrier profiles with sustainability ratings
-- TODO: carrier_contracts - Rate agreements with date effectivity
-- TODO: carrier_rates - Rate tables by mode, weight break, lane
-- TODO: route_segments - Atomic legs: origin -> destination (enables multi-leg)
-- TODO: routes - Composed routes (multiple segments for Plant -> Port -> Ocean -> DC)
-- TODO: route_segment_assignments - Links routes to segments in sequence
-- TODO: shipment_legs - Actual execution: which segments used per shipment

-- ============================================================================
-- DOMAIN E3: ESG/SUSTAINABILITY (2030 KPIs) - Part of ORCHESTRATE
-- ============================================================================
-- Tables: emission_factors, shipment_emissions, supplier_esg_scores,
--         sustainability_targets, modal_shift_opportunities

-- TODO: emission_factors - CO2/km by mode, fuel type, carrier
-- TODO: shipment_emissions - Calculated CO2 per shipment (Scope 3 Category 4 & 9)
-- TODO: supplier_esg_scores - EcoVadis, CDP, ISO14001 status, SBTi commitment
-- TODO: sustainability_targets - Division/account-level carbon reduction targets
-- TODO: modal_shift_opportunities - Identified truck->rail/intermodal opportunities

-- ============================================================================
-- DOMAIN F: PLAN (Demand & Supply Planning) - SCOR: Plan
-- ============================================================================
-- Tables: pos_sales, demand_forecasts, forecast_accuracy, consensus_adjustments,
--         replenishment_params, demand_allocation, capacity_plans, supply_plans, plan_exceptions

-- TODO: pos_sales - Point-of-sale signals (actual demand at store/SKU level)
-- TODO: demand_forecasts - Statistical/ML forecasts by SKU/location
-- TODO: forecast_accuracy - MAPE, bias tracking by SKU/account
-- TODO: consensus_adjustments - S&OP overrides to statistical forecast
-- TODO: replenishment_params - Safety stock, reorder points, review cycles by node
-- TODO: demand_allocation - How forecasted demand is allocated down the network
-- TODO: capacity_plans - Available capacity by plant/line/period (resource side)
-- TODO: supply_plans - Planned production/procurement to meet demand (closes Plan loop)
-- TODO: plan_exceptions - Gap identification when demand > capacity

-- ============================================================================
-- DOMAIN G: RETURN (Regenerate) - SCOR: Return
-- ============================================================================
-- Tables: returns, return_lines, disposition_logs, rma_authorizations

-- TODO: returns - Return events
-- TODO: return_lines - Return items with condition assessment
-- TODO: disposition_logs - Restock, scrap, regenerate, donate decisions
-- TODO: rma_authorizations - Return Merchandise Authorization workflow

-- ============================================================================
-- DOMAIN H: ORCHESTRATE (Hub) - SCOR: Orchestrate
-- ============================================================================
-- Tables: kpi_thresholds, kpi_actuals, osa_metrics, business_rules,
--         risk_events, audit_log

-- TODO: kpi_thresholds - Desmet Triangle targets (Service, Cost, Cash)
-- TODO: kpi_actuals - Calculated KPI values vs thresholds
-- TODO: osa_metrics - On-shelf availability (~500K measurements)
-- TODO: business_rules - Policy management (min order qty, allocation priority, etc.)
-- TODO: risk_events - Risk registry (supplier disruption, quality hold, etc.)
-- TODO: audit_log - Change tracking for governance

-- ============================================================================
-- VIEWS (UoM Normalization, Hierarchy Flattening, Shortcut Edges)
-- ============================================================================
-- Spec: magical-launching-forest.md Section 3.2, 3.5, 3.6

-- TODO: v_location_divisions - Flattened hierarchy for aggregation
-- TODO: v_transport_normalized - Normalize distances/costs to base units
-- TODO: v_batch_destinations - Shortcut edge for recall tracing
-- TODO: v_weights_normalized - Normalize weights to kg
-- TODO: v_inventory_normalized - Normalize qty to eaches

-- ============================================================================
-- NAMED ENTITIES (Deterministic Testing)
-- ============================================================================
-- Spec: magical-launching-forest.md Section 4.8
--
-- These specific entities are created by generate_data.py for deterministic tests:
--   B-2024-RECALL-001    - Contaminated batch for recall trace testing
--   ACCT-MEGA-001        - MegaMart hot node (4,500 stores, 25% of orders)
--   SUP-PALM-MY-001      - Single-source Palm Oil supplier (SPOF detection)
--   DC-NAM-CHI-001       - Bottleneck DC Chicago (serves 2,000 stores)
--   PROMO-BF-2024        - Black Friday 2024 promotion (bullwhip effect)
--   LANE-SH-LA-001       - Seasonal ocean lane Shanghai->LA
--   ING-PALM-001         - Palm Oil (single source, long lead time)
--   ING-SORB-001         - Sorbitol (goes into ALL toothpaste, single qualified supplier)
--   ING-PEPP-001         - Peppermint Oil (seasonal availability)

-- Schema implementation pending Phase 2
SELECT 'Schema scaffold created - implement DDL in Phase 2' AS status;
