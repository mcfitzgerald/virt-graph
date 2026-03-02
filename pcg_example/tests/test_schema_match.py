"""
Integration tests for schema match validation.

Validates the PCG ontology against the live database schema.
Skipped when the PCG database is not available.

Run with: poetry run pytest pcg_example/tests/test_schema_match.py -v
"""

from pathlib import Path

import pytest


def _db_available() -> bool:
    """Check if the PCG database is reachable."""
    try:
        from virt_graph.db import get_connection

        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


skip_no_db = pytest.mark.skipif(
    not _db_available(),
    reason="PCG database not available (set DATABASE_URL or create .env)",
)

PCG_ONTOLOGY = Path(__file__).parent.parent / "ontology" / "pcg.yaml"


@skip_no_db
class TestSchemaMatch:
    """Tests that require a live database to validate ontology against schema."""

    def _get_ontology(self):
        from virt_graph.ontology import OntologyAccessor

        return OntologyAccessor(PCG_ONTOLOGY)

    def _get_conn(self):
        from virt_graph.db import get_connection

        return get_connection()

    def test_full_schema_validation(self):
        """Run the full schema match validation and assert no failures."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from validate_schema_match import validate_schema_match

        ontology = self._get_ontology()
        conn = self._get_conn()
        try:
            results = validate_schema_match(ontology, conn)
        finally:
            conn.close()

        if results["failed"]:
            failure_msgs = [msg for _, msg in results["failed"]]
            pytest.fail(
                f"Schema match validation failed with {len(failure_msgs)} error(s):\n"
                + "\n".join(f"  - {msg}" for msg in failure_msgs)
            )

    def test_all_ontology_tables_exist(self):
        """Every table declared in the ontology must exist in the database."""
        ontology = self._get_ontology()
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """)
                db_tables = {row[0] for row in cur.fetchall()}
        finally:
            conn.close()

        missing = []
        for cls_name, cls_info in ontology.classes.items():
            table = cls_info["table"]
            if table not in db_tables:
                missing.append(f"{cls_name} → {table}")

        assert not missing, f"Tables missing from database: {missing}"

    def test_primary_keys_match(self):
        """Primary keys in ontology must match database constraints."""
        ontology = self._get_ontology()
        conn = self._get_conn()
        try:
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
                db_pks: dict[str, list[str]] = {}
                for table, col in cur.fetchall():
                    db_pks.setdefault(table, []).append(col)
        finally:
            conn.close()

        mismatches = []
        for cls_name, cls_info in ontology.classes.items():
            table = cls_info["table"]
            ont_pk = cls_info["primary_key"]
            if table in db_pks:
                db_pk = db_pks[table]
                if sorted(ont_pk) != sorted(db_pk):
                    mismatches.append(
                        f"{cls_name} ({table}): ontology={ont_pk}, db={db_pk}"
                    )

        assert not mismatches, f"PK mismatches: {mismatches}"

    def test_core_tables_have_data(self):
        """Core PCG tables should have data loaded."""
        core_tables = [
            "suppliers",
            "ingredients",
            "skus",
            "orders",
            "plants",
            "distribution_centers",
        ]
        conn = self._get_conn()
        try:
            empty = []
            for table in core_tables:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
                    count = cur.fetchone()[0]
                    if count == 0:
                        empty.append(table)
        finally:
            conn.close()

        assert not empty, f"Core tables are empty (data still loading?): {empty}"
