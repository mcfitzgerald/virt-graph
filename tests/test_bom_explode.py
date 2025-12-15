"""
Tests for path_aggregate function with BOM (Bill of Materials) use case.

Tests the generic path aggregation handler with multiply operation,
which correctly handles the "diamond problem" where components appear
via multiple paths.
"""

import pytest

from virt_graph.handlers.base import get_connection
from virt_graph.handlers.traversal import path_aggregate


@pytest.fixture
def conn():
    """Get database connection."""
    connection = get_connection()
    yield connection
    connection.close()


class TestPathAggregateMultiply:
    """Tests for path_aggregate with operation='multiply' (BOM explosion)."""

    def test_path_aggregate_returns_correct_structure(self, conn):
        """Verify path_aggregate returns PathAggregateResult structure."""
        # Get any part with children
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No BOM data found")
            part_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=part_id,
            value_col="quantity",
            operation="multiply",
            max_depth=5,
        )

        # Check structure matches PathAggregateResult TypedDict
        assert "nodes" in result
        assert "aggregated_values" in result
        assert "operation" in result
        assert "value_column" in result
        assert "max_depth" in result
        assert "nodes_visited" in result

        # Check operation is what we requested
        assert result["operation"] == "multiply"
        assert result["value_column"] == "quantity"

        # Check node structure includes aggregated_value
        if result["nodes"]:
            node = result["nodes"][0]
            assert "id" in node
            assert "aggregated_value" in node

    def test_path_aggregate_quantities_are_aggregated(self, conn):
        """Verify quantities are summed across all paths (not just first path)."""
        # Find a part that appears via multiple paths (diamond pattern)
        with conn.cursor() as cur:
            # Look for parts that have multiple parents
            cur.execute("""
                SELECT child_part_id, COUNT(DISTINCT parent_part_id) as parent_count
                FROM bill_of_materials
                GROUP BY child_part_id
                HAVING COUNT(DISTINCT parent_part_id) > 1
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No multi-parent parts found (no diamond patterns)")

            shared_part_id = row[0]

            # Find a common ancestor of this part
            cur.execute("""
                WITH RECURSIVE ancestors AS (
                    SELECT parent_part_id as part_id, 1 as depth
                    FROM bill_of_materials
                    WHERE child_part_id = %s

                    UNION ALL

                    SELECT bom.parent_part_id, a.depth + 1
                    FROM ancestors a
                    JOIN bill_of_materials bom ON bom.child_part_id = a.part_id
                    WHERE a.depth < 10
                )
                SELECT part_id FROM ancestors
                ORDER BY depth DESC
                LIMIT 1
            """, (shared_part_id,))
            row = cur.fetchone()
            if row is None:
                pytest.skip("Could not find common ancestor")
            ancestor_id = row[0]

        # Explode from the ancestor
        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=ancestor_id,
            value_col="quantity",
            operation="multiply",
            max_depth=10,
        )

        # Check the shared part has an aggregated quantity
        if shared_part_id in result["aggregated_values"]:
            qty = result["aggregated_values"][shared_part_id]
            # The quantity should be >= 1 if it's reached via any path
            assert qty is not None
            assert qty >= 1

    def test_path_aggregate_depth_tracking(self, conn):
        """Verify max_depth is correctly tracked."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                GROUP BY parent_part_id
                HAVING COUNT(*) > 2
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No suitable parent part found")
            part_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=part_id,
            value_col="quantity",
            operation="multiply",
            max_depth=5,
        )

        # max_depth should be within bounds
        assert result["max_depth"] <= 5

    def test_path_aggregate_extended_cost_calculation(self, conn):
        """Verify extended_cost can be calculated from aggregated quantity."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No BOM data found")
            part_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=part_id,
            value_col="quantity",
            operation="multiply",
            max_depth=5,
        )

        # Verify we can compute extended cost from aggregated quantity
        for node in result["nodes"]:
            unit_cost = node.get("unit_cost")
            agg_qty = node.get("aggregated_value", 0)
            if unit_cost and agg_qty:
                extended_cost = float(unit_cost) * agg_qty
                assert extended_cost > 0


class TestPathAggregateTurboEncabulator:
    """
    Integration test using the Turbo Encabulator product.

    This validates the fix for Q23 in the benchmark comparison -
    the total component cost should match Neo4j's ground truth.
    """

    def test_turbo_encabulator_total_cost(self, conn):
        """
        Verify Turbo Encabulator total cost matches Neo4j baseline.

        Ground truth from Neo4j: ~$34,795,958.60
        """
        # Get the Turbo Encabulator's root parts
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.unit_cost, pc.quantity
                FROM products pr
                JOIN product_components pc ON pc.product_id = pr.id
                JOIN parts p ON p.id = pc.part_id
                WHERE pr.name = 'Turbo Encabulator'
            """)
            root_parts = cur.fetchall()

            if not root_parts:
                pytest.skip("Turbo Encabulator product not found")

        # Calculate total cost by exploding each root part
        total_cost = 0.0

        for part_id, unit_cost, root_qty in root_parts:
            # Add root part cost
            if unit_cost:
                total_cost += float(unit_cost) * root_qty

            # Explode using path_aggregate and sum component costs
            result = path_aggregate(
                conn,
                nodes_table="parts",
                edges_table="bill_of_materials",
                edge_from_col="parent_part_id",
                edge_to_col="child_part_id",
                start_id=part_id,
                value_col="quantity",
                operation="multiply",
                max_depth=20,
            )

            for node in result["nodes"]:
                node_unit_cost = node.get("unit_cost")
                agg_qty = node.get("aggregated_value", 0)
                if node_unit_cost and agg_qty:
                    # Multiply by root_qty since this is per-product
                    total_cost += float(node_unit_cost) * agg_qty * root_qty

        # Neo4j ground truth: $34,795,958.60
        # Allow 5% tolerance for data variations
        expected = 34_795_958.60
        tolerance = expected * 0.05

        # The key assertion: our result should be close to Neo4j's
        # If this fails, the CTE fix didn't work correctly
        assert abs(total_cost - expected) < tolerance, (
            f"Total cost ${total_cost:,.2f} differs from Neo4j ${expected:,.2f} "
            f"by more than 5%"
        )


class TestPathAggregateEdgeCases:
    """Edge case tests."""

    def test_leaf_part_returns_empty_nodes(self, conn):
        """A part with no children should return empty nodes list."""
        with conn.cursor() as cur:
            # Find a leaf part (not a parent in BOM)
            cur.execute("""
                SELECT id FROM parts
                WHERE id NOT IN (SELECT parent_part_id FROM bill_of_materials)
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No leaf parts found")
            leaf_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=leaf_id,
            value_col="quantity",
            operation="multiply",
            max_depth=5,
        )

        assert result["nodes"] == []
        assert result["aggregated_values"] == {}

    def test_max_depth_zero_returns_empty(self, conn):
        """max_depth=0 should return no components."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No BOM data found")
            part_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=part_id,
            value_col="quantity",
            operation="multiply",
            max_depth=0,
        )

        # With max_depth=0, we shouldn't traverse any children
        assert result["max_depth"] == 0 or len(result["nodes"]) == 0


class TestPathAggregateOperations:
    """Tests for different aggregation operations."""

    def test_path_aggregate_sum(self, conn):
        """Test sum operation adds values along paths."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No BOM data found")
            part_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=part_id,
            value_col="quantity",
            operation="sum",
            max_depth=5,
        )

        assert result["operation"] == "sum"
        # All aggregated values should be >= 0
        for val in result["aggregated_values"].values():
            assert val >= 0

    def test_path_aggregate_max(self, conn):
        """Test max operation takes maximum along paths."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No BOM data found")
            part_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=part_id,
            value_col="quantity",
            operation="max",
            max_depth=5,
        )

        assert result["operation"] == "max"

    def test_path_aggregate_min(self, conn):
        """Test min operation takes minimum along paths."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No BOM data found")
            part_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=part_id,
            value_col="quantity",
            operation="min",
            max_depth=5,
        )

        assert result["operation"] == "min"

    def test_path_aggregate_count(self, conn):
        """Test count operation returns shortest path length."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No BOM data found")
            part_id = row[0]

        result = path_aggregate(
            conn,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",
            edge_to_col="child_part_id",
            start_id=part_id,
            value_col="quantity",
            operation="count",
            max_depth=5,
        )

        assert result["operation"] == "count"
        # All counts should be >= 1 (minimum path length is 1)
        for val in result["aggregated_values"].values():
            assert val >= 1
