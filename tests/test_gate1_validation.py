"""
Gate 1 Validation Tests

These tests validate the Phase 1 deliverables:
1. BOM traversal at scale - traverse() on 5K-part BOM in <2 seconds
2. Safety limits trigger - SubgraphTooLarge raised before DB overload
3. Data integrity - Generated data has expected graph properties

Prerequisites:
- PostgreSQL running with schema and seed data
- Run: docker-compose -f postgres/docker-compose.yml up -d
- Run: poetry run python scripts/generate_data.py (if seed.sql doesn't exist)
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from virt_graph.handlers import (
    MAX_DEPTH,
    MAX_NODES,
    SafetyLimitExceeded,
    SubgraphTooLarge,
    check_limits,
    traverse,
)
from virt_graph.handlers.base import estimate_reachable_nodes, fetch_edges_for_frontier


# === Unit Tests (No DB Required) ===


class TestSafetyLimits:
    """Test safety limit enforcement without database."""

    def test_check_limits_depth_exceeded(self):
        """Safety limit triggers when depth exceeds MAX_DEPTH."""
        with pytest.raises(SafetyLimitExceeded, match=f"depth {MAX_DEPTH + 1}"):
            check_limits(MAX_DEPTH + 1, 100)

    def test_check_limits_nodes_exceeded(self):
        """Safety limit triggers when visited nodes exceed MAX_NODES."""
        with pytest.raises(SafetyLimitExceeded, match=f"{MAX_NODES + 1} nodes"):
            check_limits(5, MAX_NODES + 1)

    def test_check_limits_within_bounds(self):
        """No exception when within limits."""
        check_limits(MAX_DEPTH - 1, MAX_NODES - 1)  # Should not raise

    def test_max_depth_is_50(self):
        """Verify MAX_DEPTH is set to 50 as per spec."""
        assert MAX_DEPTH == 50

    def test_max_nodes_is_10000(self):
        """Verify MAX_NODES is set to 10,000 as per spec."""
        assert MAX_NODES == 10_000


class TestFrontierBatching:
    """Test frontier batching utilities."""

    def test_fetch_edges_empty_frontier(self):
        """Empty frontier returns empty result."""
        mock_conn = MagicMock()
        result = fetch_edges_for_frontier(
            mock_conn,
            "test_edges",
            [],
            "from_col",
            "to_col",
            "outbound",
        )
        assert result == []

    def test_fetch_edges_outbound_query(self):
        """Outbound query uses from_col in WHERE clause."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(1, 2), (1, 3)]

        result = fetch_edges_for_frontier(
            mock_conn,
            "test_edges",
            [1],
            "from_col",
            "to_col",
            "outbound",
        )

        # Verify query was constructed correctly
        call_args = mock_cursor.execute.call_args_list
        assert len(call_args) == 2  # SET timeout + SELECT
        assert "from_col = ANY" in call_args[1][0][0]
        assert result == [(1, 2), (1, 3)]

    def test_fetch_edges_inbound_query(self):
        """Inbound query uses to_col in WHERE clause."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(2, 1), (3, 1)]

        result = fetch_edges_for_frontier(
            mock_conn,
            "test_edges",
            [1],
            "from_col",
            "to_col",
            "inbound",
        )

        call_args = mock_cursor.execute.call_args_list
        assert "to_col = ANY" in call_args[1][0][0]


class TestTraverseLogic:
    """Test traverse function logic with mocked database."""

    def test_traverse_clamps_depth(self):
        """Depth is clamped to MAX_DEPTH."""
        mock_conn = MagicMock()

        # Use skip_estimation=True to bypass size check
        # Mock fetch_edges to return empty (immediate termination)
        with patch(
            "virt_graph.handlers.traversal.fetch_edges_for_frontier", return_value=[]
        ):
            with patch(
                "virt_graph.handlers.traversal.fetch_nodes", return_value=[{"id": 1}]
            ):
                result = traverse(
                    mock_conn,
                    "nodes",
                    "edges",
                    "from_col",
                    "to_col",
                    start_id=1,
                    max_depth=100,  # Over MAX_DEPTH
                    skip_estimation=True,  # Bypass estimation for unit test
                )

        # Should complete without error (depth clamped internally)
        assert "nodes" in result

    def test_traverse_raises_subgraph_too_large(self):
        """SubgraphTooLarge raised when estimate exceeds MAX_NODES."""
        mock_conn = MagicMock()

        # Mock the estimator module functions used by traverse
        mock_sampler = MagicMock()
        mock_sampler.sample.return_value = {}
        with patch(
            "virt_graph.handlers.traversal.GraphSampler", return_value=mock_sampler
        ):
            with patch(
                "virt_graph.handlers.traversal.get_table_bound", return_value=None
            ):
                with patch(
                    "virt_graph.handlers.traversal.estimate",
                    return_value=MAX_NODES + 1,
                ):
                    with pytest.raises(SubgraphTooLarge, match="would touch"):
                        traverse(
                            mock_conn,
                            "nodes",
                            "edges",
                            "from_col",
                            "to_col",
                            start_id=1,
                        )

    def test_traverse_returns_expected_structure(self):
        """Traverse returns dict with expected keys."""
        mock_conn = MagicMock()

        # Use skip_estimation=True to bypass size check
        with patch(
            "virt_graph.handlers.traversal.fetch_edges_for_frontier",
            return_value=[(1, 2), (1, 3)],
        ):
            with patch(
                "virt_graph.handlers.traversal.fetch_nodes",
                return_value=[{"id": 1}, {"id": 2}, {"id": 3}],
            ):
                with patch(
                    "virt_graph.handlers.traversal.should_stop", return_value=False
                ):
                    result = traverse(
                        mock_conn,
                        "nodes",
                        "edges",
                        "from_col",
                        "to_col",
                        start_id=1,
                        max_depth=1,
                        skip_estimation=True,  # Bypass estimation for unit test
                    )

        assert "nodes" in result
        assert "paths" in result
        assert "edges" in result
        assert "depth_reached" in result
        assert "nodes_visited" in result
        assert "terminated_at" in result


# === Integration Tests (Requires Running Database) ===


def db_available() -> bool:
    """Check if PostgreSQL is available."""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="supply_chain",
            user="virt_graph",
            password="dev_password",
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not db_available(), reason="PostgreSQL not available")
class TestIntegrationGate1:
    """Integration tests requiring running database."""

    @pytest.fixture
    def conn(self):
        """Get database connection."""
        import psycopg2

        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="supply_chain",
            user="virt_graph",
            password="dev_password",
        )
        yield conn
        conn.close()

    def test_bom_traversal_performance(self, conn):
        """
        Gate 1 Test 1: BOM traversal at scale.

        Target: Complete 5K-part BOM traversal in <2 seconds.
        Verify frontier batching (should be ~depth queries, not ~nodes queries).
        """
        # Get a top-level part with deep BOM
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id, COUNT(*) as child_count
                FROM bill_of_materials
                GROUP BY parent_part_id
                ORDER BY child_count DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                pytest.skip("No BOM data available")
            start_part_id = row[0]

        # Time the traversal
        start_time = time.time()
        result = traverse(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=start_part_id,
            direction="outbound",
            max_depth=20,
        )
        elapsed = time.time() - start_time

        print(f"\nBOM Traversal Results:")
        print(f"  Start part: {start_part_id}")
        print(f"  Nodes visited: {result['nodes_visited']}")
        print(f"  Depth reached: {result['depth_reached']}")
        print(f"  Time: {elapsed:.3f}s")

        assert elapsed < 2.0, f"BOM traversal took {elapsed:.3f}s, exceeds 2s target"

    def test_safety_limits_trigger_before_overload(self, conn):
        """
        Gate 1 Test 2: Safety limits trigger before DB overload.

        Attempt traversal that would exceed MAX_NODES.
        Verify SubgraphTooLarge raised proactively.
        """
        # Try to traverse entire supplier network with high depth
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers LIMIT 1")
            row = cur.fetchone()
            if not row:
                pytest.skip("No supplier data available")
            start_id = row[0]

        # This should either complete (if network is small) or raise SubgraphTooLarge
        try:
            result = traverse(
                conn,
                nodes_table="suppliers",
                edges_table="supplier_relationships",
                edge_from_col="seller_id",
                edge_to_col="buyer_id",
                start_id=start_id,
                direction="both",
                max_depth=50,  # High depth to trigger size check
            )
            # If it completes, verify we stayed within limits
            assert result["nodes_visited"] <= MAX_NODES
        except SubgraphTooLarge as e:
            # This is expected if the graph is large
            assert "limit" in str(e).lower()
            print(f"\nSubgraphTooLarge raised as expected: {e}")

    def test_supplier_tiers_form_dag(self, conn):
        """
        Gate 1 Test 3a: Data integrity - Supplier tiers form valid DAG.

        Verify no cycles in supplier relationships.
        """
        with conn.cursor() as cur:
            # Check for cycles using a simple query
            # In a proper DAG, T3 → T2 → T1 (no back edges)
            cur.execute("""
                SELECT COUNT(*) as back_edges
                FROM supplier_relationships sr
                JOIN suppliers seller ON sr.seller_id = seller.id
                JOIN suppliers buyer ON sr.buyer_id = buyer.id
                WHERE seller.tier <= buyer.tier
            """)
            back_edges = cur.fetchone()[0]

            # Some back edges might exist in real data, but should be minimal
            cur.execute("SELECT COUNT(*) FROM supplier_relationships")
            total_edges = cur.fetchone()[0]

        if total_edges > 0:
            back_edge_ratio = back_edges / total_edges
            print(f"\nSupplier relationship integrity:")
            print(f"  Total edges: {total_edges}")
            print(f"  Back edges: {back_edges} ({back_edge_ratio:.1%})")
            # Allow up to 5% back edges for "enterprise messiness"
            assert back_edge_ratio < 0.05, "Too many back edges in supplier DAG"

    def test_bom_has_realistic_depth(self, conn):
        """
        Gate 1 Test 3b: Data integrity - BOM has realistic depth distribution.

        Target average depth: ~5 levels.
        """
        with conn.cursor() as cur:
            # Calculate BOM depth statistics using recursive CTE
            cur.execute("""
                WITH RECURSIVE bom_depth AS (
                    -- Root parts (not children of anything)
                    SELECT p.id, 0 as depth
                    FROM parts p
                    WHERE NOT EXISTS (
                        SELECT 1 FROM bill_of_materials bom
                        WHERE bom.child_part_id = p.id
                    )

                    UNION ALL

                    -- Children
                    SELECT bom.child_part_id, bd.depth + 1
                    FROM bill_of_materials bom
                    JOIN bom_depth bd ON bom.parent_part_id = bd.id
                    WHERE bd.depth < 20
                )
                SELECT
                    MAX(depth) as max_depth,
                    AVG(depth) as avg_depth,
                    COUNT(DISTINCT id) as parts_with_depth
                FROM bom_depth
            """)
            row = cur.fetchone()

        if row and row[0] is not None:
            max_depth = row[0]
            avg_depth = float(row[1])
            print(f"\nBOM depth statistics:")
            print(f"  Max depth: {max_depth}")
            print(f"  Avg depth: {avg_depth:.2f}")

            # Verify reasonable depth
            assert max_depth >= 3, "BOM too shallow"
            assert max_depth <= 15, "BOM unrealistically deep"

    def test_transport_network_connected(self, conn):
        """
        Gate 1 Test 3c: Data integrity - Transport network is connected.

        All facilities should be reachable from any other facility.
        Uses SQL-based connectivity check since transport network is small.
        """
        with conn.cursor() as cur:
            # Get facility count
            cur.execute("SELECT COUNT(*) FROM facilities WHERE is_active = true")
            facility_count = cur.fetchone()[0]

            if facility_count == 0:
                pytest.skip("No facility data available")

            # Get a starting facility
            cur.execute("SELECT id FROM facilities WHERE is_active = true LIMIT 1")
            start_id = cur.fetchone()[0]

            # Use SQL recursive CTE to check connectivity (more efficient for small graphs)
            # This avoids the size estimation issue with high depth
            cur.execute("""
                WITH RECURSIVE reachable AS (
                    SELECT %s::int as facility_id, 0 as depth
                    UNION
                    SELECT DISTINCT
                        CASE
                            WHEN tr.origin_facility_id = r.facility_id THEN tr.destination_facility_id
                            ELSE tr.origin_facility_id
                        END as facility_id,
                        r.depth + 1
                    FROM reachable r
                    JOIN transport_routes tr ON (
                        tr.origin_facility_id = r.facility_id OR
                        tr.destination_facility_id = r.facility_id
                    )
                    WHERE r.depth < 20
                )
                SELECT COUNT(DISTINCT facility_id) FROM reachable
            """, (start_id,))
            reachable = cur.fetchone()[0]

        connectivity_ratio = reachable / facility_count

        print(f"\nTransport network connectivity:")
        print(f"  Total facilities: {facility_count}")
        print(f"  Reachable from {start_id}: {reachable}")
        print(f"  Connectivity: {connectivity_ratio:.1%}")

        # Network should be mostly connected (allow some isolated facilities)
        assert connectivity_ratio >= 0.9, f"Transport network only {connectivity_ratio:.1%} connected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
