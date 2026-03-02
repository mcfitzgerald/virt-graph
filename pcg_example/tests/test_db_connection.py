"""
Integration tests for database connectivity.

Skipped when the PCG database is not available.
Run with: poetry run pytest pcg_example/tests/test_db_connection.py -v
"""

import os

import pytest

# Expected PCG tables (from pcg.yaml ontology — 38 entity classes)
PCG_TABLES = [
    "suppliers",
    "ingredients",
    "supplier_ingredients",
    "formulas",
    "formula_ingredients",
    "skus",
    "channels",
    "plants",
    "distribution_centers",
    "retail_locations",
    "production_lines",
    "route_segments",
    "purchase_orders",
    "purchase_order_lines",
    "goods_receipts",
    "goods_receipt_lines",
    "work_orders",
    "batches",
    "batch_ingredients",
    "bulk_intermediates",
    "orders",
    "order_lines",
    "shipments",
    "shipment_lines",
    "returns",
    "return_lines",
    "disposition_logs",
    "inventory",
    "demand_forecasts",
    "ap_invoices",
    "ap_invoice_lines",
    "ar_invoices",
    "ar_invoice_lines",
    "gl_journal",
    "chart_of_accounts",
    "invoice_variances",
    "ap_payments",
    "ar_receipts",
]


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


@skip_no_db
class TestDBConnection:
    """Tests that require a live database connection."""

    def test_connection_opens(self):
        """Verify we can open and close a connection."""
        from virt_graph.db import get_connection

        conn = get_connection()
        assert conn is not None
        conn.close()

    def test_connection_context_manager(self):
        """Verify the context manager works."""
        from virt_graph.db import connection

        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
                assert row[0] == 1

    def test_pcg_tables_exist(self):
        """Verify expected PCG tables exist in the database."""
        from virt_graph.db import connection

        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                """)
                db_tables = {row[0] for row in cur.fetchall()}

        missing = [t for t in PCG_TABLES if t not in db_tables]
        assert not missing, f"Missing tables: {missing}"

    def test_tables_have_data(self):
        """Verify at least some core tables contain rows."""
        from virt_graph.db import connection

        core_tables = ["suppliers", "ingredients", "skus", "orders"]
        with connection() as conn:
            for table in core_tables:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    assert count > 0, f"Table {table} is empty"

    def test_database_url_from_env(self):
        """Verify DATABASE_URL is read from environment."""
        from virt_graph.db import get_database_url

        url = get_database_url()
        assert url.startswith("postgresql://")
