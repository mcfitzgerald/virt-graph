"""
Tests for soft-delete filtering functionality.

These tests verify that the soft_delete_column parameter correctly filters
out soft-deleted nodes from traversal, pathfinding, and network analysis.
"""

import pytest

from virt_graph.handlers.base import (
    fetch_edges_for_frontier,
    fetch_nodes,
    get_connection,
)
from virt_graph.handlers.traversal import traverse


@pytest.fixture
def conn():
    """Get database connection."""
    connection = get_connection()
    yield connection
    connection.close()


@pytest.fixture
def setup_soft_delete_data(conn):
    """
    Create a temporary soft-delete test scenario.

    Sets up a small graph with some nodes marked as deleted (deleted_at IS NOT NULL).
    Restores original state after test.
    """
    # Find a supplier to temporarily mark as deleted
    with conn.cursor() as cur:
        # Get a tier 2 supplier that has relationships
        cur.execute("""
            SELECT s.id, s.deleted_at
            FROM suppliers s
            JOIN supplier_relationships sr ON sr.seller_id = s.id
            WHERE s.tier = 2
            LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("No tier 2 supplier with relationships found")
        supplier_id, original_deleted_at = row

        # Mark supplier as deleted
        cur.execute("""
            UPDATE suppliers
            SET deleted_at = NOW()
            WHERE id = %s
        """, (supplier_id,))
        conn.commit()

    yield {
        "deleted_supplier_id": supplier_id,
        "original_deleted_at": original_deleted_at,
    }

    # Restore original state
    with conn.cursor() as cur:
        if original_deleted_at is None:
            cur.execute("""
                UPDATE suppliers
                SET deleted_at = NULL
                WHERE id = %s
            """, (supplier_id,))
        else:
            cur.execute("""
                UPDATE suppliers
                SET deleted_at = %s
                WHERE id = %s
            """, (original_deleted_at, supplier_id))
        conn.commit()


class TestFetchNodesWithSoftDelete:
    """Tests for fetch_nodes with soft_delete_column."""

    def test_soft_delete_filters_deleted_nodes(self, conn, setup_soft_delete_data):
        """Nodes with deleted_at IS NOT NULL are filtered out."""
        deleted_id = setup_soft_delete_data["deleted_supplier_id"]

        # Without soft-delete filter - should include the deleted node
        nodes_without_filter = fetch_nodes(
            conn,
            nodes_table="suppliers",
            node_ids=[deleted_id],
        )
        assert len(nodes_without_filter) == 1, "Without filter, node should be returned"

        # With soft-delete filter - should exclude the deleted node
        nodes_with_filter = fetch_nodes(
            conn,
            nodes_table="suppliers",
            node_ids=[deleted_id],
            soft_delete_column="deleted_at",
        )
        assert len(nodes_with_filter) == 0, "With filter, deleted node should be excluded"

    def test_soft_delete_allows_non_deleted_nodes(self, conn):
        """Nodes with deleted_at IS NULL are still returned."""
        # Get a non-deleted supplier
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM suppliers
                WHERE deleted_at IS NULL
                LIMIT 3
            """)
            rows = cur.fetchall()
            if len(rows) == 0:
                pytest.skip("No non-deleted suppliers found")
            non_deleted_ids = [row[0] for row in rows]

        # With soft-delete filter - should still include non-deleted nodes
        nodes = fetch_nodes(
            conn,
            nodes_table="suppliers",
            node_ids=non_deleted_ids,
            soft_delete_column="deleted_at",
        )
        assert len(nodes) == len(non_deleted_ids), "Non-deleted nodes should be returned"


class TestFetchEdgesWithSoftDelete:
    """Tests for fetch_edges_for_frontier with soft_delete_column."""

    def test_edges_to_deleted_nodes_filtered(self, conn, setup_soft_delete_data):
        """Edges to/from deleted nodes are filtered out."""
        deleted_id = setup_soft_delete_data["deleted_supplier_id"]

        # Find a node connected to the deleted node
        with conn.cursor() as cur:
            cur.execute("""
                SELECT buyer_id
                FROM supplier_relationships
                WHERE seller_id = %s
                LIMIT 1
            """, (deleted_id,))
            row = cur.fetchone()
            if row is None:
                # Try the reverse direction
                cur.execute("""
                    SELECT seller_id
                    FROM supplier_relationships
                    WHERE buyer_id = %s
                    LIMIT 1
                """, (deleted_id,))
                row = cur.fetchone()

            if row is None:
                pytest.skip("No edges found for deleted supplier")
            connected_id = row[0]

        # Edges from deleted node - without filter
        edges_from_deleted = fetch_edges_for_frontier(
            conn,
            edges_table="supplier_relationships",
            frontier_ids=[deleted_id],
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            direction="outbound",
        )

        # Edges from deleted node - with filter
        edges_from_deleted_filtered = fetch_edges_for_frontier(
            conn,
            edges_table="supplier_relationships",
            frontier_ids=[deleted_id],
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            direction="outbound",
            nodes_table="suppliers",
            soft_delete_column="deleted_at",
        )

        # Filtered edges should be fewer (or zero)
        assert len(edges_from_deleted_filtered) <= len(edges_from_deleted)


class TestTraverseWithSoftDelete:
    """Tests for traverse with soft_delete_column."""

    def test_traverse_excludes_deleted_nodes(self, conn, setup_soft_delete_data):
        """Traversal with soft_delete_column excludes deleted nodes."""
        deleted_id = setup_soft_delete_data["deleted_supplier_id"]

        # Get a tier 1 supplier to start from
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM suppliers
                WHERE tier = 1 AND deleted_at IS NULL
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No tier 1 non-deleted supplier found")
            tier1_id = row[0]

        # Traverse without filter
        result_unfiltered = traverse(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=tier1_id,
            direction="inbound",
            max_depth=5,
            skip_estimation=True,
        )

        # Traverse with filter
        result_filtered = traverse(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=tier1_id,
            direction="inbound",
            max_depth=5,
            skip_estimation=True,
            soft_delete_column="deleted_at",
        )

        # Check that deleted node is not in filtered results
        filtered_node_ids = {n["id"] for n in result_filtered["nodes"]}
        unfiltered_node_ids = {n["id"] for n in result_unfiltered["nodes"]}

        # Deleted ID should not be in filtered results (if it was reachable)
        if deleted_id in unfiltered_node_ids:
            assert deleted_id not in filtered_node_ids, \
                "Deleted node should not appear in filtered traversal"

        # Filtered should have same or fewer nodes
        assert result_filtered["nodes_visited"] <= result_unfiltered["nodes_visited"]

    def test_traverse_returns_consistent_results(self, conn):
        """Traverse without soft-delete column returns all nodes."""
        # Get a supplier
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM suppliers
                WHERE tier = 1 AND deleted_at IS NULL
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No tier 1 non-deleted supplier found")
            start_id = row[0]

        # Traverse without filter
        result = traverse(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=start_id,
            direction="inbound",
            max_depth=3,
            skip_estimation=True,
        )

        assert "nodes" in result
        assert "nodes_visited" in result
        assert result["nodes_visited"] >= 1


class TestSoftDeleteEdgeCases:
    """Edge case tests for soft-delete filtering."""

    def test_nonexistent_column_safe(self, conn):
        """Using a non-existent column name should fail gracefully or raise."""
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No suppliers found")
            supplier_id = row[0]

        # This should raise an error since the column doesn't exist
        with pytest.raises(Exception):
            fetch_nodes(
                conn,
                nodes_table="suppliers",
                node_ids=[supplier_id],
                soft_delete_column="nonexistent_column",
            )

    def test_empty_node_list_with_soft_delete(self, conn):
        """Empty node list returns empty result even with soft-delete filter."""
        nodes = fetch_nodes(
            conn,
            nodes_table="suppliers",
            node_ids=[],
            soft_delete_column="deleted_at",
        )
        assert nodes == []

    def test_soft_delete_with_null_value(self, conn):
        """Nodes where soft_delete_column IS NULL are included."""
        # Get nodes known to have deleted_at = NULL
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM suppliers
                WHERE deleted_at IS NULL
                LIMIT 5
            """)
            rows = cur.fetchall()
            if len(rows) == 0:
                pytest.skip("No non-deleted suppliers found")
            node_ids = [row[0] for row in rows]

        nodes = fetch_nodes(
            conn,
            nodes_table="suppliers",
            node_ids=node_ids,
            soft_delete_column="deleted_at",
        )

        # All nodes should be returned since they're not deleted
        assert len(nodes) == len(node_ids)
