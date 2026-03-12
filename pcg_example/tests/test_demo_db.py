"""Integration tests for CTS demo database generator."""

import importlib.util
import tempfile
from pathlib import Path

import pytest

# Import from scripts/ (not a package)
_spec = importlib.util.spec_from_file_location(
    "generate_demo_db",
    Path(__file__).resolve().parents[2] / "scripts" / "generate_demo_db.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
insert_all = _mod.insert_all


@pytest.fixture(scope="session")
def demo_conn():
    """Generate demo DB to tempfile, yield connection, cleanup."""
    import duckdb

    schema_path = Path(__file__).resolve().parents[2] / "erp_schema_duckdb.sql"
    db_path = Path(tempfile.mkdtemp()) / "test_demo.duckdb"

    conn = duckdb.connect(str(db_path))
    conn.execute(schema_path.read_text())
    insert_all(conn)
    yield conn
    conn.close()
    db_path.unlink(missing_ok=True)


class TestRowCounts:
    """Verify each table has expected row count."""

    EXPECTED = {
        "suppliers": 5,
        "ingredients": 15,
        "supplier_ingredients": 22,
        "plants": 3,
        "production_lines": 6,
        "channels": 3,
        "chart_of_accounts": 12,
        "bulk_intermediates": 6,
        "formulas": 14,
        "skus": 10,
        "distribution_centers": 6,
        "retail_locations": 8,
        "route_segments": 25,
        "purchase_orders": 20,
        "purchase_order_lines": 35,
        "goods_receipts": 20,
        "goods_receipt_lines": 35,
        "work_orders": 18,
        "batches": 30,
        "orders": 60,
        "returns": 10,
        "return_lines": 15,
        "disposition_logs": 15,
        "ap_invoices": 20,
        "ap_payments": 18,
        "invoice_variances": 8,
        "trade_programs": 10,
        "promo_events": 8,
    }

    @pytest.mark.parametrize("table,expected", EXPECTED.items())
    def test_table_count(self, demo_conn, table, expected):
        actual = demo_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert actual == expected, f"{table}: expected {expected}, got {actual}"

    def test_all_41_tables_populated(self, demo_conn):
        tables = demo_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        assert len(tables) == 41
        for (table,) in tables:
            count = demo_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count > 0, f"{table} is empty"

    def test_total_rows_under_3000(self, demo_conn):
        tables = demo_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        total = sum(
            demo_conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for (t,) in tables
        )
        assert 1500 < total < 3000, f"Total rows {total} outside expected range"


class TestCTSWaterfall:
    """Verify margin targets by channel for hero SKU."""

    def _channel_margins(self, conn):
        """Return {channel: margin_pct} using all-leg freight."""
        result = conn.execute("""
            WITH channel_revenue AS (
                SELECT ai.channel,
                       SUM(ail.line_amount) AS net_revenue,
                       SUM(ail.quantity_cases) AS total_cases
                FROM ar_invoices ai
                JOIN ar_invoice_lines ail ON ai.id = ail.invoice_id
                WHERE ail.sku_id = 1
                GROUP BY ai.channel
            ),
            shipment_with_cases AS (
                SELECT s.id, s.freight_cost,
                       SUM(sl.quantity_cases) AS total_cases
                FROM shipments s
                JOIN shipment_lines sl ON s.id = sl.shipment_id
                GROUP BY s.id, s.freight_cost
            ),
            leg3_channel AS (
                SELECT s.id AS leg3_id, rl.channel, swc.total_cases
                FROM shipments s
                JOIN retail_locations rl ON s.destination_id = rl.id
                JOIN shipment_with_cases swc ON s.id = swc.id
                WHERE s.route_type = 'customer_dc_to_store'
            ),
            all_leg_freight AS (
                SELECT lc.channel,
                       (SELECT SUM(swc2.freight_cost) FROM shipment_with_cases swc2
                        WHERE swc2.id BETWEEN lc.leg3_id - 2 AND lc.leg3_id) AS chain_freight,
                       lc.total_cases
                FROM leg3_channel lc
            ),
            channel_freight AS (
                SELECT channel,
                       SUM(chain_freight) AS total_freight,
                       SUM(total_cases) AS total_cases
                FROM all_leg_freight GROUP BY channel
            )
            SELECT cr.channel,
                   (cr.net_revenue / cr.total_cases - 18.00 - cf.total_freight / cf.total_cases)
                   / (cr.net_revenue / cr.total_cases) * 100 AS margin_pct
            FROM channel_revenue cr
            JOIN channel_freight cf ON cr.channel = cf.channel
        """).fetchall()
        return {row[0]: float(row[1]) for row in result}

    def test_club_margin(self, demo_conn):
        margins = self._channel_margins(demo_conn)
        assert 50.0 < margins["CLUB"] < 57.0, f"Club margin {margins['CLUB']:.1f}%"

    def test_grocery_margin(self, demo_conn):
        margins = self._channel_margins(demo_conn)
        assert 33.0 < margins["GROCERY"] < 42.0, f"Grocery margin {margins['GROCERY']:.1f}%"

    def test_convenience_margin(self, demo_conn):
        margins = self._channel_margins(demo_conn)
        assert 15.0 < margins["CONVENIENCE"] < 26.0, f"Conv margin {margins['CONVENIENCE']:.1f}%"

    def test_club_beats_convenience(self, demo_conn):
        margins = self._channel_margins(demo_conn)
        assert margins["CLUB"] > margins["CONVENIENCE"] + 20, \
            f"Club-Conv spread only {margins['CLUB'] - margins['CONVENIENCE']:.1f}pp"


class TestCategoryMargins:
    """Verify category margin patterns through Grocery."""

    def test_oral_care_highest(self, demo_conn):
        result = demo_conn.execute("""
            SELECT s.category,
                   SUM(ail.line_amount) / SUM(ail.quantity_cases) - AVG(s.cost_per_case) AS margin
            FROM ar_invoices ai
            JOIN ar_invoice_lines ail ON ai.id = ail.invoice_id
            JOIN skus s ON ail.sku_id = s.id
            WHERE ai.channel = 'GROCERY'
            GROUP BY s.category
        """).fetchall()
        margins = {row[0]: float(row[1]) for row in result}
        assert margins["ORAL_CARE"] > margins["HOME_CARE"]
        assert margins["ORAL_CARE"] > margins["PERSONAL_WASH"]

    def test_personal_wash_lowest(self, demo_conn):
        result = demo_conn.execute("""
            SELECT s.category,
                   SUM(ail.line_amount) / SUM(ail.quantity_cases) - AVG(s.cost_per_case) AS margin
            FROM ar_invoices ai
            JOIN ar_invoice_lines ail ON ai.id = ail.invoice_id
            JOIN skus s ON ail.sku_id = s.id
            WHERE ai.channel = 'GROCERY'
            GROUP BY s.category
        """).fetchall()
        margins = {row[0]: float(row[1]) for row in result}
        assert margins["PERSONAL_WASH"] < margins["HOME_CARE"]


class TestStoryNuggets:
    """Verify the 6 CTS story dimensions exist in the data."""

    def test_hdpe_price_variance(self, demo_conn):
        """AmeriPack HDPE bottles: PO $0.68, AP $0.72."""
        po_price = demo_conn.execute(
            "SELECT AVG(unit_cost) FROM purchase_order_lines WHERE ingredient_id = 11"
        ).fetchone()[0]
        ap_price = demo_conn.execute(
            "SELECT AVG(unit_cost) FROM ap_invoice_lines WHERE ingredient_id = 11"
        ).fetchone()[0]
        assert float(po_price) == pytest.approx(0.68, abs=0.01)
        assert float(ap_price) == pytest.approx(0.72, abs=0.01)

    def test_invoice_variances_open(self, demo_conn):
        count = demo_conn.execute(
            "SELECT COUNT(*) FROM invoice_variances WHERE resolution_status = 'open'"
        ).fetchone()[0]
        assert count >= 6

    def test_bad_yield_batches(self, demo_conn):
        """Citrus premix batches with yield < 90%."""
        bad = demo_conn.execute(
            "SELECT COUNT(*) FROM batches WHERE formula_id = 2 AND yield_percent < 90"
        ).fetchone()[0]
        assert bad >= 4

    def test_all_channels_have_orders(self, demo_conn):
        channels = demo_conn.execute(
            "SELECT DISTINCT source_id FROM orders"
        ).fetchall()
        assert {r[0] for r in channels} == {1, 2, 3}

    def test_dso_ordering(self, demo_conn):
        """Club DSO < Grocery DSO < Convenience DSO."""
        result = demo_conn.execute("""
            SELECT ai.channel, AVG(ar.receipt_date - ai.invoice_date) AS dso
            FROM ar_invoices ai
            JOIN ar_receipts ar ON ai.id = ar.invoice_id
            GROUP BY ai.channel
        """).fetchall()
        dso = {row[0]: float(row[1]) for row in result}
        assert dso["CLUB"] < dso["GROCERY"] < dso["CONVENIENCE"]

    def test_sku_supersedes_chain(self, demo_conn):
        """SKU 9 superseded by 1, SKU 10 superseded by 5."""
        s9 = demo_conn.execute("SELECT supersedes_sku_id FROM skus WHERE id = 9").fetchone()[0]
        s10 = demo_conn.execute("SELECT supersedes_sku_id FROM skus WHERE id = 10").fetchone()[0]
        assert s9 == 1
        assert s10 == 5

    def test_convenience_store_freight_spread(self, demo_conn):
        """NYC freight/case > Philly freight/case."""
        result = demo_conn.execute("""
            WITH leg3 AS (
                SELECT s.id, s.freight_cost, s.destination_id,
                       SUM(sl.quantity_cases) AS cases
                FROM shipments s
                JOIN shipment_lines sl ON s.id = sl.shipment_id
                WHERE s.route_type = 'customer_dc_to_store'
                GROUP BY s.id, s.freight_cost, s.destination_id
            )
            SELECT rl.city, SUM(l.freight_cost) / SUM(l.cases) AS fpc
            FROM leg3 l
            JOIN retail_locations rl ON l.destination_id = rl.id
            WHERE rl.channel = 'CONVENIENCE'
            GROUP BY rl.city
        """).fetchall()
        fpc = {row[0]: float(row[1]) for row in result}
        assert fpc["New York"] > fpc["Philadelphia"]


class TestFKIntegrity:
    """Verify no orphan references across key FK relationships."""

    FK_CHECKS = [
        ("purchase_orders", "supplier_id", "suppliers", "id"),
        ("purchase_order_lines", "po_id", "purchase_orders", "id"),
        ("goods_receipt_lines", "gr_id", "goods_receipts", "id"),
        ("batches", "formula_id", "formulas", "id"),
        ("order_lines", "order_id", "orders", "id"),
        ("shipment_lines", "shipment_id", "shipments", "id"),
        ("ar_invoice_lines", "invoice_id", "ar_invoices", "id"),
        ("ap_invoice_lines", "invoice_id", "ap_invoices", "id"),
        ("ap_payments", "invoice_id", "ap_invoices", "id"),
        ("ar_receipts", "invoice_id", "ar_invoices", "id"),
        ("return_lines", "return_id", "returns", "id"),
        ("disposition_logs", "return_id", "returns", "id"),
        ("invoice_variances", "invoice_id", "ap_invoices", "id"),
        ("trade_programs", "channel_id", "channels", "id"),
        ("promo_events", "trade_program_id", "trade_programs", "id"),
        ("promo_events", "sku_id", "skus", "id"),
        ("trade_deductions", "trade_program_id", "trade_programs", "id"),
        ("trade_deductions", "ar_invoice_id", "ar_invoices", "id"),
        ("trade_deductions", "sku_id", "skus", "id"),
    ]

    @pytest.mark.parametrize("child,fk_col,parent,pk_col", FK_CHECKS)
    def test_no_orphans(self, demo_conn, child, fk_col, parent, pk_col):
        orphans = demo_conn.execute(f"""
            SELECT COUNT(*) FROM {child} c
            WHERE c.{fk_col} IS NOT NULL
              AND c.{fk_col} NOT IN (SELECT {pk_col} FROM {parent})
        """).fetchone()[0]
        assert orphans == 0, f"{child}.{fk_col} has {orphans} orphan references"


class TestGLBalance:
    """Verify GL journal integrity."""

    def test_debits_equal_credits(self, demo_conn):
        result = demo_conn.execute("""
            SELECT SUM(debit_amount), SUM(credit_amount) FROM gl_journal
        """).fetchone()
        debits = float(result[0])
        credits = float(result[1])
        assert debits == pytest.approx(credits, rel=1e-6), \
            f"GL imbalanced: debits={debits:.2f}, credits={credits:.2f}"

    def test_gl_has_entries(self, demo_conn):
        count = demo_conn.execute("SELECT COUNT(*) FROM gl_journal").fetchone()[0]
        assert count > 200


class TestTradeManagement:
    """Verify trade management tables and invariants."""

    def test_trade_programs_by_channel(self, demo_conn):
        """Club has 3 programs, Grocery has 4, Convenience has 3."""
        result = demo_conn.execute("""
            SELECT c.name, COUNT(*) FROM trade_programs tp
            JOIN channels c ON tp.channel_id = c.id
            GROUP BY c.name ORDER BY c.name
        """).fetchall()
        counts = {row[0]: row[1] for row in result}
        assert counts["Club"] == 3
        assert counts["Convenience"] == 3
        assert counts["Grocery"] == 4

    def test_trade_rates_sum_to_discount(self, demo_conn):
        """Per channel, SUM(rate_pct) = expected discount."""
        result = demo_conn.execute("""
            SELECT channel_id, SUM(rate_pct) FROM trade_programs
            GROUP BY channel_id ORDER BY channel_id
        """).fetchall()
        rates = {row[0]: float(row[1]) for row in result}
        assert rates[1] == pytest.approx(0.12, abs=0.001)  # Club
        assert rates[2] == pytest.approx(0.25, abs=0.001)  # Grocery
        assert rates[3] == pytest.approx(0.15, abs=0.001)  # Convenience

    def test_deduction_amounts_match_invoice_discount(self, demo_conn):
        """Per invoice, SUM(deductions) ≈ gross - net revenue."""
        result = demo_conn.execute("""
            WITH invoice_gross AS (
                SELECT ai.id,
                       SUM(s.price_per_case * ail.quantity_cases) AS gross_rev,
                       SUM(ail.line_amount) AS net_rev
                FROM ar_invoices ai
                JOIN ar_invoice_lines ail ON ai.id = ail.invoice_id
                JOIN skus s ON ail.sku_id = s.id
                GROUP BY ai.id
            ),
            invoice_deductions AS (
                SELECT ar_invoice_id, SUM(deduction_amount) AS total_ded
                FROM trade_deductions
                GROUP BY ar_invoice_id
            )
            SELECT ig.id,
                   ig.gross_rev - ig.net_rev AS expected_gap,
                   id2.total_ded AS actual_deductions
            FROM invoice_gross ig
            JOIN invoice_deductions id2 ON ig.id = id2.ar_invoice_id
        """).fetchall()
        assert len(result) > 0
        for inv_id, expected, actual in result:
            assert float(actual) == pytest.approx(float(expected), rel=1e-4), \
                f"Invoice {inv_id}: deductions {actual} != gap {expected}"

    def test_grocery_highest_trade_spend(self, demo_conn):
        """Grocery has higher total trade rate than Club and Convenience."""
        result = demo_conn.execute("""
            SELECT channel_id, SUM(rate_pct) as total_rate
            FROM trade_programs GROUP BY channel_id
        """).fetchall()
        rates = {row[0]: float(row[1]) for row in result}
        assert rates[2] > rates[1]  # Grocery > Club
        assert rates[2] > rates[3]  # Grocery > Convenience

    def test_promo_events_link_to_promo_fund(self, demo_conn):
        """All promo events reference a promo_fund program."""
        orphans = demo_conn.execute("""
            SELECT COUNT(*) FROM promo_events pe
            JOIN trade_programs tp ON pe.trade_program_id = tp.id
            WHERE tp.program_type != 'promo_fund'
        """).fetchone()[0]
        assert orphans == 0, f"{orphans} promo events not linked to promo_fund"

    def test_promo_deductions_have_event_id(self, demo_conn):
        """Promo_fund deductions within event windows have non-null promo_event_id."""
        # At least some promo_fund deductions should have event linkage
        linked = demo_conn.execute("""
            SELECT COUNT(*) FROM trade_deductions td
            JOIN trade_programs tp ON td.trade_program_id = tp.id
            WHERE tp.program_type = 'promo_fund' AND td.promo_event_id IS NOT NULL
        """).fetchone()[0]
        assert linked > 0, "No promo_fund deductions linked to promo events"

    def test_gl_trade_spend_posted(self, demo_conn):
        """GL account 5200 (Trade Spend) has entries."""
        count = demo_conn.execute(
            "SELECT COUNT(*) FROM gl_journal WHERE account_code = '5200'"
        ).fetchone()[0]
        assert count > 0, "No GL entries for Trade Spend (5200)"

    def test_trade_deductions_count(self, demo_conn):
        """Trade deductions table has substantial rows."""
        count = demo_conn.execute("SELECT COUNT(*) FROM trade_deductions").fetchone()[0]
        assert 300 < count < 800, f"Trade deductions count {count} outside expected range"
