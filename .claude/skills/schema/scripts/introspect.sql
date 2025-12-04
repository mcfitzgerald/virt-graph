-- Virtual Graph Schema Introspection Queries
-- Run these against information_schema to discover physical schema details

-- ============================================================================
-- 1. Tables and columns with types
-- ============================================================================
SELECT
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.column_default,
    c.character_maximum_length,
    c.numeric_precision,
    c.numeric_scale
FROM information_schema.columns c
JOIN information_schema.tables t
    ON c.table_name = t.table_name
    AND c.table_schema = t.table_schema
WHERE c.table_schema = 'public'
    AND t.table_type = 'BASE TABLE'
ORDER BY c.table_name, c.ordinal_position;

-- ============================================================================
-- 2. Foreign key relationships
-- ============================================================================
SELECT
    tc.table_name AS source_table,
    kcu.column_name AS source_column,
    ccu.table_name AS target_table,
    ccu.column_name AS target_column,
    tc.constraint_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON tc.constraint_name = ccu.constraint_name
    AND tc.table_schema = ccu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;

-- ============================================================================
-- 3. Primary keys
-- ============================================================================
SELECT
    tc.table_name,
    kcu.column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'PRIMARY KEY'
    AND tc.table_schema = 'public'
ORDER BY tc.table_name;

-- ============================================================================
-- 4. Unique constraints (potential identifiers)
-- ============================================================================
SELECT
    tc.table_name,
    kcu.column_name,
    tc.constraint_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'UNIQUE'
    AND tc.table_schema = 'public'
ORDER BY tc.table_name, tc.constraint_name;

-- ============================================================================
-- 5. Row counts per table
-- ============================================================================
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;

-- ============================================================================
-- 6. Check constraints (for business rules)
-- ============================================================================
SELECT
    tc.table_name,
    tc.constraint_name,
    cc.check_clause
FROM information_schema.table_constraints tc
JOIN information_schema.check_constraints cc
    ON tc.constraint_name = cc.constraint_name
    AND tc.table_schema = cc.constraint_schema
WHERE tc.constraint_type = 'CHECK'
    AND tc.table_schema = 'public'
    AND tc.constraint_name NOT LIKE '%_not_null'
ORDER BY tc.table_name;

-- ============================================================================
-- 7. Indexes (for understanding access patterns)
-- ============================================================================
SELECT
    tablename AS table_name,
    indexname AS index_name,
    indexdef AS index_definition
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- ============================================================================
-- 8. Sample data query template (parameterized - run per table)
-- ============================================================================
-- Usage: Replace {table_name} with actual table name
-- SELECT * FROM {table_name} LIMIT 10;

-- ============================================================================
-- 9. Self-referential relationships (graph edges within same entity)
-- ============================================================================
SELECT
    tc.table_name AS edge_table,
    kcu.column_name AS from_column,
    ccu.table_name AS node_table,
    ccu.column_name AS to_column,
    tc.constraint_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON tc.constraint_name = ccu.constraint_name
    AND tc.table_schema = ccu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
    AND tc.table_name IN (
        SELECT t1.table_name
        FROM information_schema.table_constraints t1
        JOIN information_schema.constraint_column_usage c1 ON t1.constraint_name = c1.constraint_name
        JOIN information_schema.table_constraints t2 ON t1.table_name = t2.table_name AND t1.constraint_name != t2.constraint_name
        JOIN information_schema.constraint_column_usage c2 ON t2.constraint_name = c2.constraint_name
        WHERE t1.constraint_type = 'FOREIGN KEY'
            AND t2.constraint_type = 'FOREIGN KEY'
            AND c1.table_name = c2.table_name
            AND t1.table_schema = 'public'
    )
ORDER BY tc.table_name;

-- ============================================================================
-- 10. Referential integrity check template (for implicit relationships)
-- ============================================================================
-- Usage: Replace placeholders to check for orphaned records
-- SELECT COUNT(*) as orphan_count
-- FROM {child_table}
-- WHERE {child_column} IS NOT NULL
--     AND {child_column} NOT IN (SELECT {parent_column} FROM {parent_table});

-- ============================================================================
-- 11. Column statistics (for understanding data distribution)
-- ============================================================================
SELECT
    schemaname,
    tablename AS table_name,
    attname AS column_name,
    n_distinct,
    most_common_vals,
    most_common_freqs
FROM pg_stats
WHERE schemaname = 'public'
    AND n_distinct IS NOT NULL
ORDER BY tablename, attname;

-- ============================================================================
-- 12. Tables with soft delete pattern
-- ============================================================================
SELECT DISTINCT table_name
FROM information_schema.columns
WHERE table_schema = 'public'
    AND column_name = 'deleted_at'
ORDER BY table_name;

-- ============================================================================
-- 13. Tables with audit columns
-- ============================================================================
SELECT
    table_name,
    array_agg(column_name ORDER BY column_name) AS audit_columns
FROM information_schema.columns
WHERE table_schema = 'public'
    AND column_name IN ('created_at', 'updated_at', 'created_by', 'updated_by')
GROUP BY table_name
ORDER BY table_name;
