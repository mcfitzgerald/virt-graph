"""
DDL introspection and table statistics for estimation bounds.

Provides hard bounds on graph size from database metadata,
which caps estimation to prevent wild over-estimates.
"""

from dataclasses import dataclass

from psycopg2.extensions import connection as PgConnection


@dataclass
class TableStats:
    """DDL-derived table statistics."""

    row_count: int
    is_junction: bool  # Composite PK (M:M pattern)
    has_self_ref: bool  # Self-referencing FK
    has_no_self_ref_constraint: bool  # CHECK constraint preventing self-ref
    indexed_columns: list[str]
    unique_from_nodes: int | None  # Distinct values in from column
    unique_to_nodes: int | None  # Distinct values in to column
    density: float | None  # edges/nodes^2 if calculable


def get_table_stats(
    conn: PgConnection,
    table: str,
    from_col: str | None = None,
    to_col: str | None = None,
) -> TableStats:
    """
    Introspect DDL via information_schema and pg_stat.

    Args:
        conn: Database connection
        table: Table name
        from_col: Optional edge source column (for distinct counts)
        to_col: Optional edge target column (for distinct counts)

    Returns:
        TableStats with DDL-derived properties
    """
    with conn.cursor() as cur:
        # Get row count from pg_stat_user_tables (approximate but fast)
        cur.execute(
            """
            SELECT COALESCE(n_live_tup, 0)
            FROM pg_stat_user_tables
            WHERE relname = %s
            """,
            (table,),
        )
        row = cur.fetchone()
        row_count = row[0] if row else 0

        # If pg_stat is empty, get actual count (slower but accurate)
        if row_count == 0:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            row_count = cur.fetchone()[0]

        # Check for composite primary key (junction table indicator)
        cur.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
                ON kcu.constraint_name = tc.constraint_name
            WHERE tc.table_name = %s
                AND tc.constraint_type = 'PRIMARY KEY'
            """,
            (table,),
        )
        pk_cols = cur.fetchone()[0]
        is_junction = pk_cols >= 2

        # Check for self-referencing foreign key
        cur.execute(
            """
            SELECT COUNT(*) > 0
            FROM information_schema.referential_constraints rc
            JOIN information_schema.constraint_column_usage ccu
                ON rc.constraint_name = ccu.constraint_name
            WHERE rc.unique_constraint_catalog = ccu.constraint_catalog
                AND ccu.table_name = %s
            """,
            (table,),
        )
        has_self_ref = cur.fetchone()[0]

        # Check for CHECK constraints (simplified - just check if any exist)
        cur.execute(
            """
            SELECT COUNT(*) > 0
            FROM information_schema.check_constraints cc
            JOIN information_schema.constraint_column_usage ccu
                ON cc.constraint_name = ccu.constraint_name
            WHERE ccu.table_name = %s
            """,
            (table,),
        )
        has_no_self_ref_constraint = cur.fetchone()[0]

        # Get indexed columns
        cur.execute(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
            WHERE c.relname = %s
            """,
            (table,),
        )
        indexed_columns = [row[0] for row in cur.fetchall()]

        # Get distinct node counts if columns specified
        unique_from = None
        unique_to = None
        density = None

        if from_col and to_col:
            cur.execute(
                f"SELECT COUNT(DISTINCT {from_col}) FROM {table}"  # noqa: S608
            )
            unique_from = cur.fetchone()[0]

            cur.execute(
                f"SELECT COUNT(DISTINCT {to_col}) FROM {table}"  # noqa: S608
            )
            unique_to = cur.fetchone()[0]

            # Calculate density if we have both
            if unique_from and unique_to:
                total_nodes = unique_from + unique_to  # Approximate
                if total_nodes > 0:
                    density = row_count / (total_nodes**2)

    return TableStats(
        row_count=row_count,
        is_junction=is_junction,
        has_self_ref=has_self_ref,
        has_no_self_ref_constraint=has_no_self_ref_constraint,
        indexed_columns=indexed_columns,
        unique_from_nodes=unique_from,
        unique_to_nodes=unique_to,
        density=density,
    )


def get_table_bound(
    conn: PgConnection,
    edges_table: str,
    from_col: str,
    to_col: str,
) -> int:
    """
    Get absolute upper bound from unique nodes in table.

    This is the maximum possible nodes that could be reached
    by traversing all edges in the table.

    Args:
        conn: Database connection
        edges_table: Edge table name
        from_col: Source column
        to_col: Target column

    Returns:
        Upper bound on reachable nodes
    """
    with conn.cursor() as cur:
        # Count unique nodes appearing in either column
        # Using UNION to deduplicate across columns
        query = f"""
            SELECT COUNT(*) FROM (
                SELECT {from_col} AS node_id FROM {edges_table}
                UNION
                SELECT {to_col} AS node_id FROM {edges_table}
            ) nodes
        """  # noqa: S608
        cur.execute(query)
        return cur.fetchone()[0]


def get_cardinality_stats(
    conn: PgConnection,
    edges_table: str,
    from_col: str,
    to_col: str,
) -> dict[str, float]:
    """
    Get cardinality statistics for edges.

    Useful for understanding graph density and potential
    for hub nodes.

    Args:
        conn: Database connection
        edges_table: Edge table name
        from_col: Source column
        to_col: Target column

    Returns:
        Dict with avg_out_degree, max_out_degree, avg_in_degree, max_in_degree
    """
    with conn.cursor() as cur:
        # Outbound degree stats
        cur.execute(
            f"""
            SELECT
                AVG(cnt)::float as avg_out,
                MAX(cnt)::float as max_out
            FROM (
                SELECT {from_col}, COUNT(*) as cnt
                FROM {edges_table}
                GROUP BY {from_col}
            ) degree_counts
            """  # noqa: S608
        )
        out_row = cur.fetchone()
        avg_out, max_out = out_row if out_row else (0.0, 0.0)

        # Inbound degree stats
        cur.execute(
            f"""
            SELECT
                AVG(cnt)::float as avg_in,
                MAX(cnt)::float as max_in
            FROM (
                SELECT {to_col}, COUNT(*) as cnt
                FROM {edges_table}
                GROUP BY {to_col}
            ) degree_counts
            """  # noqa: S608
        )
        in_row = cur.fetchone()
        avg_in, max_in = in_row if in_row else (0.0, 0.0)

    return {
        "avg_out_degree": avg_out or 0.0,
        "max_out_degree": max_out or 0.0,
        "avg_in_degree": avg_in or 0.0,
        "max_in_degree": max_in or 0.0,
    }
