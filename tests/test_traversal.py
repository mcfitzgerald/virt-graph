"""
Integration tests for traversal handlers.

NOTE: These tests use the supply chain sample dataset (suppliers, supplier_relationships).
The handlers themselves are schema-parameterized and work with any relational graph
structure.
"""

import pytest

from virt_graph.handlers.base import get_connection
from virt_graph.handlers.traversal import traverse_collecting


@pytest.fixture
def conn():
    """Get database connection."""
    connection = get_connection()
    yield connection
    connection.close()


@pytest.fixture
def supplier_ids(conn):
    """Get named supplier IDs for testing (supply chain sample data)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, name, tier FROM suppliers
            WHERE name IN (
                'Acme Corp', 'GlobalTech Industries', 'Pacific Components',
                'Eastern Electronics', 'Delta Supplies'
            )
        """)
        return {row[1]: {"id": row[0], "tier": row[1]} for row in cur.fetchall()}


class TestTraverseCollecting:
    """Tests for traverse_collecting function."""

    def test_traverse_collecting_returns_structure(self, conn):
        """Verify traverse_collecting returns expected structure."""
        # Get any supplier to start from
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers WHERE tier = 1 LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No tier 1 suppliers found")
            start_id = row[0]

        result = traverse_collecting(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=start_id,
            target_condition="tier = 3",
            direction="inbound",
            max_depth=10,
        )

        # Check expected keys
        assert "matching_nodes" in result
        assert "matching_paths" in result
        assert "total_traversed" in result
        assert "depth_reached" in result

    def test_traverse_collecting_tier3_suppliers(self, conn):
        """Find all tier 3 suppliers upstream from a tier 1 supplier."""
        # Get a tier 1 supplier
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers WHERE tier = 1 LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No tier 1 suppliers found")
            t1_id = row[0]

        result = traverse_collecting(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=t1_id,
            target_condition="tier = 3",
            direction="inbound",  # Follow edges backward to find sellers
            max_depth=10,
        )

        # All matching nodes should be tier 3
        for node in result["matching_nodes"]:
            assert node.get("tier") == 3

    def test_traverse_collecting_no_matches(self, conn):
        """Test with impossible condition - should return empty matches."""
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No suppliers found")
            start_id = row[0]

        result = traverse_collecting(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=start_id,
            target_condition="tier = 999",  # Impossible condition
            direction="inbound",
            max_depth=5,
        )

        assert result["matching_nodes"] == []

    def test_traverse_collecting_path_tracking(self, conn):
        """Verify matching_paths contains valid paths to matched nodes."""
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers WHERE tier = 1 LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No tier 1 suppliers found")
            start_id = row[0]

        result = traverse_collecting(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=start_id,
            target_condition="tier = 2",  # Find tier 2 suppliers
            direction="inbound",
            max_depth=5,
        )

        # Each matching node should have a corresponding path
        if result["matching_nodes"]:
            assert len(result["matching_paths"]) > 0

            # Paths should start from start_id
            for node_id, path in result["matching_paths"].items():
                assert path[0] == start_id
                # Path should end at the matching node
                assert path[-1] == node_id

    def test_traverse_collecting_depth_limit(self, conn):
        """Test that max_depth is respected."""
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers WHERE tier = 1 LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No tier 1 suppliers found")
            start_id = row[0]

        result = traverse_collecting(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=start_id,
            target_condition="tier = 3",
            direction="inbound",
            max_depth=2,  # Limit depth
        )

        # Depth reached should be <= max_depth
        assert result["depth_reached"] <= 2

    def test_traverse_collecting_outbound_direction(self, conn):
        """Test outbound traversal (following edges forward)."""
        # Get a tier 3 supplier to traverse outbound (to find their buyers)
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers WHERE tier = 3 LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No tier 3 suppliers found")
            t3_id = row[0]

        result = traverse_collecting(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=t3_id,
            target_condition="tier = 1",
            direction="outbound",  # Follow edges forward to find buyers
            max_depth=10,
        )

        # All matching nodes should be tier 1
        for node in result["matching_nodes"]:
            assert node.get("tier") == 1

    def test_traverse_collecting_total_traversed(self, conn):
        """Verify total_traversed count is accurate."""
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers WHERE tier = 1 LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No tier 1 suppliers found")
            start_id = row[0]

        result = traverse_collecting(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=start_id,
            target_condition="tier = 3",
            direction="inbound",
            max_depth=10,
        )

        # Total traversed should be >= matching nodes
        assert result["total_traversed"] >= len(result["matching_nodes"])
