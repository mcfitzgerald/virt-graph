-- =============================================================================
-- Validation Queries for Realistic Supply Chain Data
-- Run after data generation to verify industry benchmarks
-- =============================================================================

-- Turn on timing and formatting
\timing on
\pset format aligned

-- =============================================================================
-- 1. PARETO 80/20: Top 20% products should have ~80% of order volume
-- Expected: 75-85% (targeting ~80%)
-- =============================================================================
\echo '=== 1. PARETO 80/20 VALIDATION ==='

WITH product_order_counts AS (
    SELECT
        product_id,
        COUNT(*) as order_count,
        SUM(quantity) as total_qty
    FROM order_items
    GROUP BY product_id
),
ranked_products AS (
    SELECT
        product_id,
        order_count,
        total_qty,
        ROW_NUMBER() OVER (ORDER BY order_count DESC) as rank,
        COUNT(*) OVER () as total_products,
        SUM(order_count) OVER () as grand_total_orders
    FROM product_order_counts
),
top_20_pct AS (
    SELECT
        SUM(order_count) as top_20_orders,
        MAX(grand_total_orders) as total_orders,
        MAX(total_products) as total_products
    FROM ranked_products
    WHERE rank <= (SELECT CEIL(COUNT(*) * 0.2) FROM product_order_counts)
)
SELECT
    'Pareto 80/20' as metric,
    ROUND(100.0 * top_20_orders / total_orders, 1) as actual_pct,
    '75-85%' as expected,
    CASE
        WHEN 100.0 * top_20_orders / total_orders BETWEEN 75 AND 85 THEN 'PASS'
        ELSE 'FAIL'
    END as status,
    total_products as total_products,
    CEIL(total_products * 0.2) as top_20_count
FROM top_20_pct;

-- =============================================================================
-- 2. OEE DISTRIBUTION: Average should be 60-66% (industry average)
-- Expected: avg 60-66%, with poor performers (40-55%) and world-class (80-92%)
-- =============================================================================
\echo ''
\echo '=== 2. OEE DISTRIBUTION VALIDATION ==='

SELECT
    'OEE Distribution' as metric,
    ROUND(AVG(efficiency_rating) * 100, 1) as avg_oee_pct,
    ROUND(MIN(efficiency_rating) * 100, 1) as min_oee_pct,
    ROUND(MAX(efficiency_rating) * 100, 1) as max_oee_pct,
    CASE
        WHEN AVG(efficiency_rating) BETWEEN 0.60 AND 0.66 THEN 'PASS'
        ELSE 'FAIL'
    END as avg_status,
    COUNT(*) as total_work_centers
FROM work_centers
WHERE is_active = true;

-- Detailed OEE distribution buckets
SELECT
    CASE
        WHEN efficiency_rating < 0.55 THEN '1. Poor (<55%)'
        WHEN efficiency_rating < 0.65 THEN '2. Below Avg (55-65%)'
        WHEN efficiency_rating < 0.72 THEN '3. Average (65-72%)'
        WHEN efficiency_rating < 0.80 THEN '4. Good (72-80%)'
        ELSE '5. World-class (80%+)'
    END as oee_bucket,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct_of_total
FROM work_centers
WHERE is_active = true
GROUP BY 1
ORDER BY 1;

-- Named problem work centers should exist
SELECT
    'Problem Work Centers' as metric,
    COUNT(*) as count,
    STRING_AGG(wc_code || ' (' || ROUND(efficiency_rating * 100, 0) || '%)', ', ') as work_centers
FROM work_centers
WHERE wc_code LIKE 'WC-PROB-%';

-- =============================================================================
-- 3. PERFECT ORDER RATE: ~82% (industry average 80-85%)
-- Perfect = shipped_date <= required_date
-- =============================================================================
\echo ''
\echo '=== 3. PERFECT ORDER RATE VALIDATION ==='

WITH order_timeliness AS (
    SELECT
        id,
        CASE
            WHEN shipped_date IS NULL THEN 'not_shipped'
            WHEN shipped_date::date <= required_date THEN 'on_time'
            ELSE 'late'
        END as delivery_status
    FROM orders
    WHERE required_date IS NOT NULL
      AND status IN ('shipped', 'delivered')
)
SELECT
    'Perfect Order Rate' as metric,
    ROUND(100.0 * SUM(CASE WHEN delivery_status = 'on_time' THEN 1 ELSE 0 END) / COUNT(*), 1) as perfect_order_pct,
    '80-85%' as expected,
    CASE
        WHEN 100.0 * SUM(CASE WHEN delivery_status = 'on_time' THEN 1 ELSE 0 END) / COUNT(*) BETWEEN 80 AND 85 THEN 'PASS'
        ELSE 'FAIL'
    END as status,
    COUNT(*) as total_shipped_orders,
    SUM(CASE WHEN delivery_status = 'late' THEN 1 ELSE 0 END) as late_orders
FROM order_timeliness;

-- =============================================================================
-- 4. SCALE-FREE NETWORK: Hub suppliers should have 25x+ median connections
-- Barabási-Albert preferential attachment creates "super hubs" on buyer side
-- =============================================================================
\echo ''
\echo '=== 4. SCALE-FREE NETWORK VALIDATION ==='

WITH connection_counts AS (
    SELECT
        buyer_id as supplier_id,  -- Hubs form on BUYER side (rich-get-richer)
        COUNT(*) as connections
    FROM supplier_relationships
    GROUP BY buyer_id
),
stats AS (
    SELECT
        MAX(connections) as max_connections,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY connections) as median_connections,
        AVG(connections) as avg_connections
    FROM connection_counts
)
SELECT
    'Scale-Free Network' as metric,
    max_connections,
    ROUND(median_connections, 1) as median_connections,
    ROUND(max_connections / NULLIF(median_connections, 0), 1) as hub_ratio,
    '>25x' as expected,
    CASE
        WHEN max_connections / NULLIF(median_connections, 0) > 25 THEN 'PASS'
        ELSE 'FAIL'
    END as status
FROM stats;

-- Top 5 hub suppliers (by inbound connections - buyers who receive from many sellers)
SELECT
    s.supplier_code,
    s.name,
    s.tier,
    COUNT(*) as inbound_connections
FROM supplier_relationships sr
JOIN suppliers s ON sr.buyer_id = s.id
GROUP BY s.id, s.supplier_code, s.name, s.tier
ORDER BY inbound_connections DESC
LIMIT 5;

-- =============================================================================
-- 5. BOM DEPTH: Maximum should be >= 22 levels (Aerospace hierarchy)
-- =============================================================================
\echo ''
\echo '=== 5. BOM DEPTH VALIDATION ==='

WITH RECURSIVE bom_depth AS (
    -- Start with root parts (not children of anything)
    SELECT
        p.id as part_id,
        p.part_number,
        1 as depth,
        ARRAY[p.id] as path
    FROM parts p
    WHERE NOT EXISTS (
        SELECT 1 FROM bill_of_materials bom
        WHERE bom.child_part_id = p.id
        AND (bom.effective_to IS NULL OR bom.effective_to > CURRENT_DATE)
    )

    UNION ALL

    -- Recurse through BOM
    SELECT
        bom.child_part_id,
        p.part_number,
        bd.depth + 1,
        bd.path || bom.child_part_id
    FROM bom_depth bd
    JOIN bill_of_materials bom ON bom.parent_part_id = bd.part_id
    JOIN parts p ON p.id = bom.child_part_id
    WHERE NOT bom.child_part_id = ANY(bd.path)  -- Prevent cycles
      AND (bom.effective_to IS NULL OR bom.effective_to > CURRENT_DATE)
      AND bd.depth < 30  -- Safety limit
)
SELECT
    'BOM Depth' as metric,
    MAX(depth) as max_depth,
    '>=22' as expected,
    CASE WHEN MAX(depth) >= 22 THEN 'PASS' ELSE 'FAIL' END as status
FROM bom_depth;

-- Deepest parts (should be aerospace)
WITH RECURSIVE bom_depth AS (
    SELECT
        p.id as part_id,
        p.part_number,
        1 as depth,
        ARRAY[p.id] as path
    FROM parts p
    WHERE NOT EXISTS (
        SELECT 1 FROM bill_of_materials bom
        WHERE bom.child_part_id = p.id
        AND (bom.effective_to IS NULL OR bom.effective_to > CURRENT_DATE)
    )

    UNION ALL

    SELECT
        bom.child_part_id,
        p.part_number,
        bd.depth + 1,
        bd.path || bom.child_part_id
    FROM bom_depth bd
    JOIN bill_of_materials bom ON bom.parent_part_id = bd.part_id
    JOIN parts p ON p.id = bom.child_part_id
    WHERE NOT bom.child_part_id = ANY(bd.path)
      AND (bom.effective_to IS NULL OR bom.effective_to > CURRENT_DATE)
      AND bd.depth < 30
)
SELECT part_number, depth
FROM bom_depth
ORDER BY depth DESC
LIMIT 5;

-- =============================================================================
-- 6. SEASONAL ROUTES: ~10% of routes should be seasonal
-- =============================================================================
\echo ''
\echo '=== 6. SEASONAL ROUTES VALIDATION ==='

SELECT
    'Seasonal Routes' as metric,
    ROUND(100.0 * SUM(CASE WHEN route_status = 'seasonal' THEN 1 ELSE 0 END) / COUNT(*), 1) as seasonal_pct,
    '8-12%' as expected,
    CASE
        WHEN 100.0 * SUM(CASE WHEN route_status = 'seasonal' THEN 1 ELSE 0 END) / COUNT(*) BETWEEN 8 AND 12 THEN 'PASS'
        ELSE 'FAIL'
    END as status,
    COUNT(*) as total_routes,
    SUM(CASE WHEN route_status = 'seasonal' THEN 1 ELSE 0 END) as seasonal_count
FROM transport_routes;

-- Route status distribution
SELECT
    route_status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM transport_routes
GROUP BY route_status
ORDER BY count DESC;

-- =============================================================================
-- 7. SUPPLIER FROM HELL: ID=9 should have ~50% late deliveries
-- "Reliable Parts Co" with 50% late, BB rating, long lead times
-- =============================================================================
\echo ''
\echo '=== 7. SUPPLIER FROM HELL VALIDATION ==='

-- Supplier info
SELECT
    'Supplier From Hell' as metric,
    s.id,
    s.name,
    s.credit_rating,
    s.tier
FROM suppliers s
WHERE s.id = 9;

-- Late delivery rate for Supplier from Hell
WITH po_timeliness AS (
    SELECT
        po.supplier_id,
        po.id as po_id,
        CASE
            WHEN po.received_date IS NULL THEN 'not_received'
            WHEN po.received_date <= po.expected_date THEN 'on_time'
            ELSE 'late'
        END as delivery_status
    FROM purchase_orders po
    WHERE po.expected_date IS NOT NULL
      AND po.status IN ('shipped', 'received')
)
SELECT
    supplier_id,
    ROUND(100.0 * SUM(CASE WHEN delivery_status = 'late' THEN 1 ELSE 0 END) / COUNT(*), 1) as late_pct,
    '45-55%' as expected,
    CASE
        WHEN 100.0 * SUM(CASE WHEN delivery_status = 'late' THEN 1 ELSE 0 END) / COUNT(*) BETWEEN 45 AND 55 THEN 'PASS'
        ELSE 'FAIL'
    END as status,
    COUNT(*) as total_pos,
    SUM(CASE WHEN delivery_status = 'late' THEN 1 ELSE 0 END) as late_pos
FROM po_timeliness
WHERE supplier_id = 9
GROUP BY supplier_id;

-- Compare to other suppliers
SELECT
    'Comparison' as metric,
    ROUND(AVG(CASE WHEN supplier_id = 9 THEN late_pct ELSE NULL END), 1) as supplier_from_hell_late_pct,
    ROUND(AVG(CASE WHEN supplier_id != 9 THEN late_pct ELSE NULL END), 1) as other_suppliers_late_pct
FROM (
    SELECT
        supplier_id,
        100.0 * SUM(CASE WHEN received_date > expected_date THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) as late_pct
    FROM purchase_orders
    WHERE expected_date IS NOT NULL AND received_date IS NOT NULL
    GROUP BY supplier_id
) sub;

-- =============================================================================
-- 8. LUMPY DEMAND: ~5% of forecasts should have demand spikes (>2x baseline)
-- =============================================================================
\echo ''
\echo '=== 8. LUMPY DEMAND VALIDATION ==='

-- Check for demand spikes using seasonality factor as proxy
-- (Spikes are encoded as high forecast_quantity relative to product baseline)
WITH product_baselines AS (
    SELECT
        product_id,
        AVG(forecast_quantity) as avg_qty,
        STDDEV(forecast_quantity) as stddev_qty
    FROM demand_forecasts
    GROUP BY product_id
),
spike_detection AS (
    SELECT
        df.id,
        df.product_id,
        df.forecast_quantity,
        pb.avg_qty,
        CASE
            WHEN df.forecast_quantity > pb.avg_qty * 2 THEN true
            ELSE false
        END as is_spike
    FROM demand_forecasts df
    JOIN product_baselines pb ON df.product_id = pb.product_id
)
SELECT
    'Lumpy Demand (Spikes)' as metric,
    ROUND(100.0 * SUM(CASE WHEN is_spike THEN 1 ELSE 0 END) / COUNT(*), 1) as spike_pct,
    '3-7%' as expected,
    CASE
        WHEN 100.0 * SUM(CASE WHEN is_spike THEN 1 ELSE 0 END) / COUNT(*) BETWEEN 3 AND 7 THEN 'PASS'
        ELSE 'FAIL'
    END as status,
    COUNT(*) as total_forecasts,
    SUM(CASE WHEN is_spike THEN 1 ELSE 0 END) as spike_count
FROM spike_detection;

-- Check Medical category (designated bottleneck - 2.5x demand multiplier)
SELECT
    'Medical Bottleneck' as metric,
    p.category,
    COUNT(df.id) as forecast_count,
    ROUND(AVG(df.forecast_quantity), 0) as avg_forecast_qty
FROM demand_forecasts df
JOIN products p ON df.product_id = p.id
WHERE p.category = 'Medical'
GROUP BY p.category;

-- =============================================================================
-- SUMMARY
-- =============================================================================
\echo ''
\echo '=== VALIDATION SUMMARY ==='
\echo 'Run this script after data generation to verify industry benchmarks.'
\echo 'Expected results:'
\echo '  1. Pareto 80/20: Top 20% products = 75-85% of orders'
\echo '  2. OEE Average: 60-66%'
\echo '  3. Perfect Order Rate: 80-85%'
\echo '  4. Scale-Free Hub Ratio: >25x median'
\echo '  5. BOM Depth: >=22 levels'
\echo '  6. Seasonal Routes: 8-12%'
\echo '  7. Supplier From Hell Late: 45-55%'
\echo '  8. Demand Spikes: 3-7%'
