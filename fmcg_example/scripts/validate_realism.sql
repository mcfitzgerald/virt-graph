-- ============================================================================
-- Prism Consumer Goods (PCG) - Data Realism Validation
-- ============================================================================
--
-- Spec: magical-launching-forest.md Section 4.7
--
-- Purpose: Validate that generated data matches FMCG benchmarks and
--          realistic distribution patterns.
--
-- Usage:
--   psql -h localhost -p 5433 -U virt_graph -d prism_fmcg -f validate_realism.sql
--
-- Implementation Status: SCAFFOLD
-- TODO: Uncomment and run after data generation complete
-- ============================================================================

-- ============================================================================
-- SECTION 1: Pareto Distribution Validation (80/20 Rule)
-- ============================================================================
-- Spec Section 4.2: Top 20% of SKUs = 80% of Revenue

-- 1.1 SKU Volume Concentration
-- Expected: Quintile 1 (top 20%) should have ~80% of total volume
/*
WITH sku_volumes AS (
    SELECT
        sku_id,
        SUM(quantity) as total_qty,
        NTILE(5) OVER (ORDER BY SUM(quantity) DESC) as quintile
    FROM order_lines
    GROUP BY sku_id
)
SELECT
    quintile,
    COUNT(*) as sku_count,
    SUM(total_qty) as quintile_volume,
    ROUND(SUM(total_qty) * 100.0 / (SELECT SUM(total_qty) FROM sku_volumes), 1) as volume_pct
FROM sku_volumes
GROUP BY quintile
ORDER BY quintile;
-- Quintile 1 should be ~80%
*/

-- 1.2 Store Order Concentration
-- Expected: Top 20% of stores should generate ~80% of orders
/*
WITH store_orders AS (
    SELECT
        o.retail_location_id,
        COUNT(*) as order_count,
        NTILE(5) OVER (ORDER BY COUNT(*) DESC) as quintile
    FROM orders o
    GROUP BY o.retail_location_id
)
SELECT
    quintile,
    COUNT(*) as store_count,
    SUM(order_count) as quintile_orders,
    ROUND(SUM(order_count) * 100.0 / (SELECT SUM(order_count) FROM store_orders), 1) as order_pct
FROM store_orders
GROUP BY quintile
ORDER BY quintile;
*/

-- 1.3 Supplier Spend Concentration
-- Expected: Top 20% of suppliers should represent ~80% of spend
/*
WITH supplier_spend AS (
    SELECT
        s.id as supplier_id,
        SUM(pol.quantity * pol.unit_price) as total_spend,
        NTILE(5) OVER (ORDER BY SUM(pol.quantity * pol.unit_price) DESC) as quintile
    FROM suppliers s
    JOIN purchase_orders po ON po.supplier_id = s.id
    JOIN purchase_order_lines pol ON pol.purchase_order_id = po.id
    GROUP BY s.id
)
SELECT
    quintile,
    COUNT(*) as supplier_count,
    SUM(total_spend) as quintile_spend,
    ROUND(SUM(total_spend) * 100.0 / (SELECT SUM(total_spend) FROM supplier_spend), 1) as spend_pct
FROM supplier_spend
GROUP BY quintile
ORDER BY quintile;
*/

-- ============================================================================
-- SECTION 2: FMCG-Specific KPI Benchmarks
-- ============================================================================
-- Spec Section 4.7: FMCG benchmarks vs Industrial

-- 2.1 Inventory Turns (Target: 8-12 for FMCG)
/*
SELECT
    ROUND(
        (SELECT SUM(ol.quantity * ol.unit_price) FROM order_lines ol
         JOIN orders o ON ol.order_id = o.id
         WHERE o.order_date >= CURRENT_DATE - INTERVAL '1 year')
        /
        NULLIF((SELECT AVG(i.quantity_on_hand * sc.standard_cost)
                FROM inventory i
                JOIN sku_costs sc ON i.sku_id = sc.sku_id), 0)
    , 1) as inventory_turns;
-- Should be 8-12, not 3-5 (industrial)
*/

-- 2.2 Perfect Order Rate / OTIF (Target: 95-98%)
/*
SELECT
    COUNT(*) as total_orders,
    SUM(CASE WHEN is_on_time AND is_complete THEN 1 ELSE 0 END) as perfect_orders,
    ROUND(SUM(CASE WHEN is_on_time AND is_complete THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as otif_pct
FROM (
    SELECT
        o.id,
        s.actual_delivery_date <= o.requested_delivery_date as is_on_time,
        sl.delivered_qty >= ol.quantity as is_complete
    FROM orders o
    JOIN order_lines ol ON ol.order_id = o.id
    JOIN order_allocations oa ON oa.order_line_id = ol.id
    JOIN shipment_lines sl ON sl.shipment_id = oa.shipment_id
    JOIN shipments s ON s.id = sl.shipment_id
    WHERE s.status = 'DELIVERED'
) order_metrics;
-- Should be 95-98%
*/

-- 2.3 On-Shelf Availability / OSA (Target: 92-95%)
/*
SELECT
    division_code,
    COUNT(*) as measurement_count,
    SUM(CASE WHEN is_in_stock THEN 1 ELSE 0 END) as in_stock_count,
    ROUND(SUM(CASE WHEN is_in_stock THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as osa_pct
FROM osa_metrics om
JOIN retail_locations rl ON om.retail_location_id = rl.id
JOIN retail_accounts ra ON rl.retail_account_id = ra.id
JOIN divisions d ON ra.division_id = d.id
GROUP BY division_code
ORDER BY osa_pct;
-- Should be 92-95% overall
*/

-- 2.4 Batch Yield / OEE (Target: 95-99%)
/*
SELECT
    p.code as plant_code,
    COUNT(*) as batch_count,
    AVG(b.actual_yield / b.planned_yield * 100) as avg_yield_pct,
    ROUND(SUM(CASE WHEN b.status = 'COMPLETED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as success_rate
FROM batches b
JOIN production_lines pl ON b.production_line_id = pl.id
JOIN plants p ON pl.plant_id = p.id
GROUP BY p.code
ORDER BY avg_yield_pct;
-- Should be 95-99%
*/

-- 2.5 Forecast Accuracy / MAPE (Target: 20-30%)
/*
SELECT
    AVG(ABS(actual_qty - forecast_qty) / NULLIF(actual_qty, 0) * 100) as mape_pct,
    AVG(actual_qty - forecast_qty) / NULLIF(AVG(actual_qty), 0) * 100 as bias_pct
FROM forecast_accuracy;
-- MAPE should be 20-30%
*/

-- ============================================================================
-- SECTION 3: Network Topology Validation
-- ============================================================================
-- Spec Section 4.1: Barabasi-Albert preferential attachment

-- 3.1 DC Store Distribution (Should show hub pattern)
/*
SELECT
    dc.code as dc_code,
    COUNT(DISTINCT rl.id) as stores_served,
    ROUND(COUNT(DISTINCT rl.id) * 100.0 / (SELECT COUNT(*) FROM retail_locations), 1) as store_pct
FROM distribution_centers dc
JOIN shipments s ON s.origin_dc_id = dc.id
JOIN retail_locations rl ON s.destination_location_id = rl.id
GROUP BY dc.code
ORDER BY stores_served DESC
LIMIT 10;
-- Top DC should serve 40x+ more stores than smallest
*/

-- 3.2 Retail Account Store Distribution
/*
SELECT
    ra.code as account_code,
    ra.archetype,
    COUNT(rl.id) as store_count
FROM retail_accounts ra
JOIN retail_locations rl ON rl.retail_account_id = ra.id
GROUP BY ra.code, ra.archetype
ORDER BY store_count DESC
LIMIT 10;
-- MegaMart (ACCT-MEGA-001) should have 4,500 stores
*/

-- 3.3 Supplier Ingredient Coverage
/*
SELECT
    s.code as supplier_code,
    COUNT(DISTINCT si.ingredient_id) as ingredient_count
FROM suppliers s
JOIN supplier_ingredients si ON si.supplier_id = s.id
GROUP BY s.code
ORDER BY ingredient_count DESC
LIMIT 10;
-- Top supplier should cover 25x more ingredients than smallest
*/

-- ============================================================================
-- SECTION 4: Named Entity Validation
-- ============================================================================
-- Spec Section 4.8: Deterministic test entities

-- 4.1 Contaminated Batch B-2024-RECALL-001
/*
SELECT
    b.code,
    b.status,
    COUNT(DISTINCT sl.shipment_id) as shipments,
    COUNT(DISTINCT s.destination_location_id) as stores_affected
FROM batches b
JOIN shipment_lines sl ON sl.batch_id = b.id
JOIN shipments s ON s.id = sl.shipment_id
WHERE b.code = 'B-2024-RECALL-001'
GROUP BY b.code, b.status;
-- Should affect ~500 stores
*/

-- 4.2 MegaMart Hub ACCT-MEGA-001
/*
SELECT
    ra.code,
    COUNT(DISTINCT rl.id) as store_count,
    COUNT(DISTINCT o.id) as order_count,
    ROUND(COUNT(DISTINCT o.id) * 100.0 / (SELECT COUNT(*) FROM orders), 1) as order_share_pct
FROM retail_accounts ra
JOIN retail_locations rl ON rl.retail_account_id = ra.id
LEFT JOIN orders o ON o.retail_location_id = rl.id
WHERE ra.code = 'ACCT-MEGA-001'
GROUP BY ra.code;
-- Should have 4,500 stores and ~25% of orders
*/

-- 4.3 Single-Source Palm Oil SUP-PALM-MY-001
/*
SELECT
    i.code as ingredient_code,
    i.name as ingredient_name,
    COUNT(DISTINCT si.supplier_id) as supplier_count,
    STRING_AGG(s.code, ', ') as supplier_codes
FROM ingredients i
LEFT JOIN supplier_ingredients si ON si.ingredient_id = i.id
LEFT JOIN suppliers s ON s.id = si.supplier_id
WHERE i.code = 'ING-PALM-001'
GROUP BY i.code, i.name;
-- Should have exactly 1 supplier (SUP-PALM-MY-001)
*/

-- 4.4 Bottleneck DC Chicago DC-NAM-CHI-001
/*
SELECT
    dc.code,
    dc.division_id,
    COUNT(DISTINCT s.destination_location_id) as stores_served,
    ROUND(SUM(sl.quantity_cases) * 100.0 /
          (SELECT SUM(quantity_cases) FROM shipment_lines), 1) as volume_share_pct
FROM distribution_centers dc
JOIN shipments s ON s.origin_dc_id = dc.id
JOIN shipment_lines sl ON sl.shipment_id = s.id
WHERE dc.code = 'DC-NAM-CHI-001'
GROUP BY dc.code, dc.division_id;
-- Should serve ~2,000 stores and ~40% of NAM volume
*/

-- ============================================================================
-- SECTION 5: Temporal Patterns Validation
-- ============================================================================
-- Spec Section 4.4, 4.6: Lumpy demand and temporal flickering

-- 5.1 Promotion Effect with Hangover (Black Friday)
/*
SELECT
    EXTRACT(WEEK FROM o.order_date) as week,
    COUNT(*) as order_count,
    SUM(ol.quantity) as total_qty,
    ROUND(SUM(ol.quantity) * 1.0 /
          LAG(SUM(ol.quantity)) OVER (ORDER BY EXTRACT(WEEK FROM o.order_date)), 2) as week_over_week
FROM orders o
JOIN order_lines ol ON ol.order_id = o.id
WHERE EXTRACT(WEEK FROM o.order_date) BETWEEN 45 AND 50
  AND EXTRACT(YEAR FROM o.order_date) = 2024
GROUP BY EXTRACT(WEEK FROM o.order_date)
ORDER BY week;
-- Week 47 should be 3x baseline, Week 48 should be 0.6x baseline (hangover)
*/

-- 5.2 Seasonal Route Capacity (Shanghai-LA)
/*
SELECT
    EXTRACT(MONTH FROM s.ship_date) as month,
    COUNT(*) as shipment_count,
    AVG(sl.weight_kg) as avg_weight
FROM route_segments rs
JOIN shipment_legs sleg ON sleg.route_segment_id = rs.id
JOIN shipments s ON s.id = sleg.shipment_id
JOIN shipment_lines sl ON sl.shipment_id = s.id
WHERE rs.code = 'LANE-SH-LA-001'
GROUP BY EXTRACT(MONTH FROM s.ship_date)
ORDER BY month;
-- Jan-Feb should show 50% lower volume than peak months
*/

-- 5.3 Ingredient Seasonal Availability (Peppermint Oil)
/*
SELECT
    EXTRACT(QUARTER FROM gr.receipt_date) as quarter,
    SUM(grl.received_qty) as received_qty,
    AVG(grl.unit_cost) as avg_unit_cost
FROM ingredients i
JOIN goods_receipt_lines grl ON grl.ingredient_id = i.id
JOIN goods_receipts gr ON gr.id = grl.goods_receipt_id
WHERE i.code = 'ING-PEPP-001'
GROUP BY EXTRACT(QUARTER FROM gr.receipt_date)
ORDER BY quarter;
-- Q1 should show 3x higher cost, Q2-Q3 should have most volume
*/

-- ============================================================================
-- SECTION 6: Mass Balance Validation
-- ============================================================================
-- Spec Section 4.5.1: Batch splitting integrity

-- 6.1 Batch Fraction Sum (Should not exceed 1.0)
/*
SELECT
    batch_id,
    SUM(batch_fraction) as total_allocated,
    CASE
        WHEN SUM(batch_fraction) > 1.0 THEN 'OVER-ALLOCATED'
        WHEN SUM(batch_fraction) = 1.0 THEN 'FULLY ALLOCATED'
        ELSE 'PARTIAL'
    END as allocation_status
FROM shipment_lines
WHERE batch_fraction IS NOT NULL
GROUP BY batch_id
HAVING SUM(batch_fraction) > 1.0;
-- Should return 0 rows (no over-allocation)
*/

-- 6.2 Batch Ingredient Mass Balance
/*
SELECT
    b.code as batch_code,
    b.actual_yield as batch_output_kg,
    SUM(bi.quantity_kg) as input_kg,
    ROUND(b.actual_yield / NULLIF(SUM(bi.quantity_kg), 0) * 100, 1) as yield_pct
FROM batches b
JOIN batch_ingredients bi ON bi.batch_id = b.id
GROUP BY b.code, b.actual_yield
HAVING b.actual_yield > SUM(bi.quantity_kg) * 1.1;
-- Should return 0 rows (output should not exceed input significantly)
*/

-- ============================================================================
-- SUMMARY REPORT
-- ============================================================================

SELECT 'Data realism validation scaffold created.' as status;
SELECT 'Uncomment queries after Phase 4 data generation is complete.' as next_step;
SELECT 'Reference: magical-launching-forest.md Section 4.7' as spec_reference;
