#!/usr/bin/env python3
"""
Schema Match Validation Script

Cross-references a VG ontology against a live PostgreSQL database to verify:
1. Tables declared in the ontology exist in the database
2. Columns declared as attributes exist in the correct tables
3. Primary keys match
4. Foreign key relationships exist
5. Row counts are plausible

Usage:
    poetry run python scripts/validate_schema_match.py [ontology_path]
    poetry run python scripts/validate_schema_match.py --all
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virt_graph.ontology import OntologyAccessor


def _connect():
    """Get a database connection, or None if unavailable."""
    try:
        from virt_graph.db import get_connection

        conn = get_connection()
        return conn
    except Exception as e:
        print(f"Could not connect to database: {e}")
        return None


def _query_db_tables(conn) -> set[str]:
    """Get all public tables from information_schema."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """)
        return {row[0] for row in cur.fetchall()}


def _query_db_columns(conn) -> dict[str, set[str]]:
    """Get columns per table from information_schema."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        result: dict[str, set[str]] = {}
        for table, col in cur.fetchall():
            result.setdefault(table, set()).add(col)
        return result


def _query_db_primary_keys(conn) -> dict[str, list[str]]:
    """Get primary key columns per table."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.ordinal_position
        """)
        result: dict[str, list[str]] = {}
        for table, col in cur.fetchall():
            result.setdefault(table, []).append(col)
        return result


def _query_db_foreign_keys(conn) -> set[tuple[str, str, str, str]]:
    """Get FK relationships as (source_table, source_col, target_table, target_col) tuples."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                tc.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        """)
        return {(row[0], row[1], row[2], row[3]) for row in cur.fetchall()}


def _query_row_counts(conn, tables: list[str]) -> dict[str, int]:
    """Get actual row counts for specified tables."""
    result = {}
    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            result[table] = cur.fetchone()[0]
    return result


def validate_schema_match(ontology: OntologyAccessor, conn) -> dict:
    """
    Validate an ontology against a live database.

    Returns a dict with:
        passed: list of (check_type, message) tuples
        failed: list of (check_type, message) tuples
        warnings: list of (check_type, message) tuples
    """
    passed = []
    failed = []
    warnings = []

    # Fetch database metadata
    db_tables = _query_db_tables(conn)
    db_columns = _query_db_columns(conn)
    db_pks = _query_db_primary_keys(conn)
    db_fks = _query_db_foreign_keys(conn)

    # --- Check 1: Tables exist ---
    tables_with_counts = []
    for cls_name, cls_info in ontology.classes.items():
        table = cls_info["table"]
        if table in db_tables:
            passed.append(("table_exists", f"{cls_name} → {table}"))
            # Collect for row count check
            row_count = cls_info.get("row_count")
            if row_count is not None:
                tables_with_counts.append((cls_name, table, int(row_count)))
        else:
            failed.append(("table_exists", f"{cls_name} → {table} NOT FOUND in database"))

    # --- Check 2: Columns exist ---
    for cls_name, cls_info in ontology.classes.items():
        table = cls_info["table"]
        if table not in db_columns:
            continue  # Already reported as missing table

        db_cols = db_columns[table]
        ont_attrs = ontology.get_class_inherited_attributes(cls_name)

        for attr_name in ont_attrs:
            if attr_name in db_cols:
                passed.append(("column_exists", f"{table}.{attr_name}"))
            else:
                failed.append(
                    ("column_exists", f"{table}.{attr_name} NOT FOUND (declared in {cls_name})")
                )

    # --- Check 3: Primary keys match ---
    for cls_name, cls_info in ontology.classes.items():
        table = cls_info["table"]
        ont_pk = cls_info["primary_key"]  # Already a list

        if table not in db_pks:
            if table in db_tables:
                warnings.append(("primary_key", f"{table}: no PK constraint found in database"))
            continue

        db_pk = db_pks[table]
        if sorted(ont_pk) == sorted(db_pk):
            passed.append(("primary_key", f"{cls_name}: PK matches ({', '.join(ont_pk)})"))
        else:
            failed.append(
                (
                    "primary_key",
                    f"{cls_name}: PK mismatch — ontology={ont_pk}, database={db_pk}",
                )
            )

    # --- Check 4: FK relationships exist ---
    # Build a lookup of DB FKs by (table, column)
    db_fk_lookup = {}
    for src_table, src_col, tgt_table, tgt_col in db_fks:
        db_fk_lookup.setdefault((src_table, src_col), []).append((tgt_table, tgt_col))

    for role_name, role_info in ontology.roles.items():
        edge_table = role_info["edge_table"]
        domain_keys = role_info["domain_key"]
        range_keys = role_info["range_key"]

        if edge_table not in db_tables:
            failed.append(("fk_exists", f"{role_name}: edge_table '{edge_table}' NOT FOUND"))
            continue

        # Check domain_key columns exist
        for dk in domain_keys:
            table_cols = db_columns.get(edge_table, set())
            if dk not in table_cols:
                failed.append(
                    ("fk_exists", f"{role_name}: domain_key '{dk}' not in {edge_table}")
                )

        # Check range_key columns exist
        for rk in range_keys:
            table_cols = db_columns.get(edge_table, set())
            if rk not in table_cols:
                failed.append(("fk_exists", f"{role_name}: range_key '{rk}' not in {edge_table}"))

        # Check if a FK constraint exists for the main FK columns.
        # Skip: "id" (domain_key=id means edge_table IS the entity table),
        # PK columns of the edge table (e.g., line_number in composite PKs),
        # and columns that are clearly part of a composite PK reference.
        edge_pk = set(db_pks.get(edge_table, []))
        fk_cols_to_check = set()
        for dk in domain_keys:
            if dk != "id" and dk not in edge_pk:
                fk_cols_to_check.add(dk)
        for rk in range_keys:
            if rk != "id" and rk not in edge_pk:
                fk_cols_to_check.add(rk)

        for col in fk_cols_to_check:
            fk_targets = db_fk_lookup.get((edge_table, col))
            if fk_targets:
                passed.append(("fk_exists", f"{role_name}: FK {edge_table}.{col} exists"))
            else:
                # Not necessarily an error — some FKs are implicit (e.g., polymorphic)
                warnings.append(
                    ("fk_exists", f"{role_name}: no FK constraint for {edge_table}.{col}")
                )

    # --- Check 5: Row count plausibility ---
    if tables_with_counts:
        actual_tables = [t for _, t, _ in tables_with_counts if t in db_tables]
        if actual_tables:
            actual_counts = _query_row_counts(conn, actual_tables)
            for cls_name, table, expected in tables_with_counts:
                if table not in actual_counts:
                    continue
                actual = actual_counts[table]
                if expected == 0:
                    if actual == 0:
                        passed.append(
                            ("row_count", f"{cls_name}: both ontology and DB show 0 rows")
                        )
                    else:
                        warnings.append(
                            (
                                "row_count",
                                f"{cls_name}: ontology says 0, DB has {actual:,}",
                            )
                        )
                else:
                    ratio = actual / expected
                    if 0.1 <= ratio <= 10.0:
                        passed.append(
                            (
                                "row_count",
                                f"{cls_name}: {actual:,} rows (ontology: {expected:,}, ratio: {ratio:.1f}x)",
                            )
                        )
                    else:
                        warnings.append(
                            (
                                "row_count",
                                f"{cls_name}: {actual:,} rows vs ontology {expected:,} (ratio: {ratio:.1f}x)",
                            )
                        )

    return {"passed": passed, "failed": failed, "warnings": warnings}


def print_results(results: dict, ontology_path: Path) -> bool:
    """Print validation results. Returns True if all checks passed."""
    passed = results["passed"]
    failed = results["failed"]
    warnings = results["warnings"]

    print(f"\n{'='*60}")
    print(f"Schema Match Validation")
    print(f"{'='*60}")
    print(f"Ontology: {ontology_path}")

    # Group by check type
    check_types = ["table_exists", "column_exists", "primary_key", "fk_exists", "row_count"]
    check_labels = {
        "table_exists": "Table Existence",
        "column_exists": "Column Existence",
        "primary_key": "Primary Key Match",
        "fk_exists": "FK Relationship",
        "row_count": "Row Count Plausibility",
    }

    for check_type in check_types:
        type_passed = [msg for ct, msg in passed if ct == check_type]
        type_failed = [msg for ct, msg in failed if ct == check_type]
        type_warnings = [msg for ct, msg in warnings if ct == check_type]

        total = len(type_passed) + len(type_failed) + len(type_warnings)
        if total == 0:
            continue

        label = check_labels[check_type]
        print(f"\n--- {label} ---")

        for msg in type_failed:
            print(f"  FAIL  {msg}")
        for msg in type_warnings:
            print(f"  WARN  {msg}")
        for msg in type_passed:
            print(f"  pass  {msg}")

    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"  Passed:   {len(passed)}")
    print(f"  Failed:   {len(failed)}")
    print(f"  Warnings: {len(warnings)}")

    if failed:
        print(f"\n{'='*60}")
        print("RESULT: FAIL")
        print(f"{'='*60}")
        return False
    elif warnings:
        print(f"\n{'='*60}")
        print("RESULT: PASS (with warnings)")
        print(f"{'='*60}")
        return True
    else:
        print(f"\n{'='*60}")
        print("RESULT: PASS")
        print(f"{'='*60}")
        return True


def main():
    example_ontology_dir = Path(__file__).parent.parent / "pcg_example" / "ontology"

    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            ontology_files = sorted(example_ontology_dir.glob("pcg.yaml"))
            if not ontology_files:
                print(f"No ontology files found in {example_ontology_dir}")
                sys.exit(1)
        else:
            ontology_files = [Path(sys.argv[1])]
    else:
        print("Usage:")
        print("  poetry run python scripts/validate_schema_match.py <ontology_path>")
        print("  poetry run python scripts/validate_schema_match.py --all")
        print()
        print("Examples:")
        print(
            "  poetry run python scripts/validate_schema_match.py pcg_example/ontology/pcg.yaml"
        )
        print("  poetry run python scripts/validate_schema_match.py --all")
        sys.exit(1)

    # Connect to database
    conn = _connect()
    if conn is None:
        print("\nDatabase not available. Set DATABASE_URL or configure .env")
        sys.exit(2)

    all_passed = True
    try:
        for ontology_path in ontology_files:
            if not ontology_path.exists():
                print(f"Error: {ontology_path} not found")
                sys.exit(1)

            ontology = OntologyAccessor(ontology_path)
            results = validate_schema_match(ontology, conn)
            if not print_results(results, ontology_path):
                all_passed = False
    finally:
        conn.close()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
