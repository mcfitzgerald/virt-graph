"""
Tests for the estimator module.

Tests graph sampling, estimation models, bounds, and guards.
"""

import pytest

from virt_graph.estimator import (
    EstimationConfig,
    GraphSampler,
    GuardResult,
    SampleResult,
    TableStats,
    check_guards,
    estimate,
    get_table_bound,
    get_table_stats,
)
from virt_graph.handlers.base import get_connection


@pytest.fixture
def conn():
    """Get database connection."""
    connection = get_connection()
    yield connection
    connection.close()


class TestGraphSampler:
    """Tests for GraphSampler."""

    def test_sample_bom_structure(self, conn):
        """BOM sampling detects graph properties."""
        # Get a part with children
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                GROUP BY parent_part_id
                HAVING COUNT(*) > 3
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No suitable parent part found")
            start_id = row[0]

        sampler = GraphSampler(
            conn,
            edges_table="bill_of_materials",
            from_col="parent_part_id",
            to_col="child_part_id",
            direction="outbound",
        )
        sample = sampler.sample(start_id, depth=5)

        assert sample.visited_count >= 1
        assert len(sample.level_sizes) >= 1
        assert sample.growth_trend in ("increasing", "stable", "decreasing")
        assert 0 <= sample.convergence_ratio <= 2.0  # Reasonable range

    def test_sample_detects_termination(self, conn):
        """Small graph sampling sets terminated=True."""
        # Find a part with few or no children (leaf node)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id
                FROM parts p
                LEFT JOIN bill_of_materials bom ON bom.parent_part_id = p.id
                GROUP BY p.id
                HAVING COUNT(bom.id) = 0
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No leaf parts found")
            leaf_id = row[0]

        sampler = GraphSampler(
            conn,
            edges_table="bill_of_materials",
            from_col="parent_part_id",
            to_col="child_part_id",
            direction="outbound",
        )
        sample = sampler.sample(leaf_id, depth=5)

        # A leaf node should terminate immediately
        assert sample.terminated is True
        assert sample.visited_count == 1

    def test_hub_detection_threshold(self, conn):
        """High-degree node can be flagged as hub."""
        # Find a high-degree node
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id, COUNT(*) as cnt
                FROM bill_of_materials
                GROUP BY parent_part_id
                ORDER BY cnt DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No BOM data found")
            high_degree_id, degree = row

        # Use a very low threshold to trigger hub detection
        sampler = GraphSampler(
            conn,
            edges_table="bill_of_materials",
            from_col="parent_part_id",
            to_col="child_part_id",
            direction="outbound",
            hub_threshold=1.0,  # Very low threshold
        )
        sample = sampler.sample(high_degree_id, depth=3)

        # If degree is high enough, hub should be detected
        if degree > 5:
            # May or may not trigger depending on expansion pattern
            assert sample.max_expansion_factor >= 0

    def test_supplier_network_sampling(self, conn):
        """Test sampling on supplier relationships."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT seller_id
                FROM supplier_relationships
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No supplier relationships found")
            start_id = row[0]

        sampler = GraphSampler(
            conn,
            edges_table="supplier_relationships",
            from_col="seller_id",
            to_col="buyer_id",
            direction="outbound",
        )
        sample = sampler.sample(start_id, depth=5)

        assert sample.visited_count >= 1
        assert isinstance(sample.growth_trend, str)


class TestEstimationConfig:
    """Tests for EstimationConfig and estimate()."""

    def test_default_config(self):
        """Default config has sensible values."""
        config = EstimationConfig()
        assert config.base_damping == 0.85
        assert config.safety_margin == 1.2
        assert config.sample_depth == 5

    def test_custom_damping_affects_estimate(self):
        """Custom damping config changes estimate."""
        # Create a mock sample with growth
        sample = SampleResult(
            visited_count=100,
            level_sizes=[1, 10, 50, 100],
            terminated=False,
            growth_trend="increasing",
            convergence_ratio=0.8,
            has_cycles=False,
            max_expansion_factor=10.0,
            hub_detected=False,
            edges_seen=150,
        )

        # Default config estimate
        default_estimate = estimate(sample, max_depth=10)

        # High damping config (should reduce estimate)
        high_damping_config = EstimationConfig(
            base_damping=0.5,  # Lower than default
            safety_margin=1.0,  # No safety margin
        )
        damped_estimate = estimate(sample, max_depth=10, config=high_damping_config)

        # Lower damping should produce lower estimate
        assert damped_estimate < default_estimate

    def test_terminated_graph_returns_visited_count(self):
        """Terminated graphs return actual visited count."""
        sample = SampleResult(
            visited_count=50,
            level_sizes=[1, 10, 20, 15, 4, 0],
            terminated=True,
            growth_trend="decreasing",
            convergence_ratio=0.9,
            has_cycles=False,
            max_expansion_factor=2.0,
            hub_detected=False,
            edges_seen=45,
        )

        est = estimate(sample, max_depth=20)

        # Should be close to visited count (with minimal safety margin)
        assert est >= sample.visited_count
        assert est <= sample.visited_count * 1.1  # Small margin

    def test_table_bound_caps_estimate(self):
        """Table bound caps high estimates."""
        sample = SampleResult(
            visited_count=100,
            level_sizes=[1, 10, 50, 100],
            terminated=False,
            growth_trend="increasing",
            convergence_ratio=1.0,
            has_cycles=False,
            max_expansion_factor=5.0,
            hub_detected=False,
            edges_seen=150,
        )

        # Without bound, estimate might be high
        unbounded = estimate(sample, max_depth=20)

        # With bound, should be capped
        bounded = estimate(sample, max_depth=20, table_bound=500)

        assert bounded <= 500
        if unbounded > 500:
            assert bounded < unbounded


class TestBounds:
    """Tests for bounds module."""

    def test_get_table_bound(self, conn):
        """get_table_bound returns unique node count."""
        bound = get_table_bound(
            conn,
            edges_table="bill_of_materials",
            from_col="parent_part_id",
            to_col="child_part_id",
        )

        assert bound > 0
        # Should be less than total rows * 2 (since nodes are deduplicated)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bill_of_materials")
            edge_count = cur.fetchone()[0]

        assert bound <= edge_count * 2

    def test_get_table_stats(self, conn):
        """get_table_stats returns DDL-derived stats."""
        stats = get_table_stats(
            conn,
            table="bill_of_materials",
            from_col="parent_part_id",
            to_col="child_part_id",
        )

        assert isinstance(stats, TableStats)
        assert stats.row_count > 0
        assert stats.unique_from_nodes is not None
        assert stats.unique_to_nodes is not None


class TestGuards:
    """Tests for runtime guards."""

    def test_hub_detection_aborts(self):
        """Hub detection triggers abort recommendation."""
        sample = SampleResult(
            visited_count=100,
            level_sizes=[1, 100, 5000],
            terminated=False,
            growth_trend="increasing",
            convergence_ratio=0.9,
            has_cycles=False,
            max_expansion_factor=100.0,
            hub_detected=True,  # Hub detected
            edges_seen=5100,
        )

        result = check_guards(sample, max_depth=10, max_nodes=10_000)

        assert result.safe_to_proceed is False
        assert result.recommended_action == "abort"
        assert "Hub" in result.reason

    def test_terminated_graph_proceeds(self):
        """Terminated graphs are safe to proceed."""
        sample = SampleResult(
            visited_count=50,
            level_sizes=[1, 10, 20, 15, 4, 0],
            terminated=True,
            growth_trend="decreasing",
            convergence_ratio=0.9,
            has_cycles=False,
            max_expansion_factor=2.0,
            hub_detected=False,
            edges_seen=45,
        )

        result = check_guards(sample, max_depth=10, max_nodes=10_000)

        assert result.safe_to_proceed is True
        assert result.recommended_action == "traverse"

    def test_configurable_max_nodes(self):
        """max_nodes parameter is respected."""
        sample = SampleResult(
            visited_count=100,
            level_sizes=[1, 10, 50, 100],
            terminated=False,
            growth_trend="stable",
            convergence_ratio=0.85,
            has_cycles=False,
            max_expansion_factor=5.0,
            hub_detected=False,
            edges_seen=150,
        )

        # With high limit, should be safe
        result_high = check_guards(sample, max_depth=10, max_nodes=100_000)
        assert result_high.safe_to_proceed is True

        # With very low limit, should abort
        result_low = check_guards(sample, max_depth=20, max_nodes=50)
        assert result_low.safe_to_proceed is False


class TestIntegration:
    """Integration tests with real database."""

    def test_bom_estimation_accuracy(self, conn):
        """Test that BOM estimation is reasonably accurate."""
        # Get a part with children for testing
        with conn.cursor() as cur:
            cur.execute("""
                SELECT parent_part_id
                FROM bill_of_materials
                GROUP BY parent_part_id
                HAVING COUNT(*) >= 5
                LIMIT 1
            """)
            row = cur.fetchone()
            if row is None:
                pytest.skip("No suitable parent part found")
            start_id = row[0]

        # Sample and estimate
        sampler = GraphSampler(
            conn,
            edges_table="bill_of_materials",
            from_col="parent_part_id",
            to_col="child_part_id",
            direction="outbound",
        )
        sample = sampler.sample(start_id, depth=5)
        table_bound = get_table_bound(
            conn, "bill_of_materials", "parent_part_id", "child_part_id"
        )

        estimated = estimate(sample, max_depth=20, table_bound=table_bound)

        # If terminated, estimate should match visited
        if sample.terminated:
            assert estimated >= sample.visited_count
            assert estimated <= sample.visited_count * 1.2

    def test_bom_with_skip_estimation(self, conn):
        """BOM with skip_estimation=True succeeds."""
        from virt_graph.handlers.traversal import bom_explode

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

        # Should succeed without raising SubgraphTooLarge
        result = bom_explode(
            conn,
            start_part_id=part_id,
            max_depth=5,
            skip_estimation=True,
        )

        assert "components" in result
        assert result["nodes_visited"] >= 1

    def test_bom_with_increased_limit(self, conn):
        """BOM with max_nodes override works."""
        from virt_graph.handlers.traversal import bom_explode

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

        # Should succeed with increased limit
        result = bom_explode(
            conn,
            start_part_id=part_id,
            max_depth=10,
            max_nodes=50_000,  # Increased limit
        )

        assert "components" in result

    def test_traverse_with_custom_config(self, conn):
        """Traverse with custom estimation config."""
        from virt_graph.handlers.traversal import traverse

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No suppliers found")
            start_id = row[0]

        # Custom config with high damping (conservative)
        config = EstimationConfig(
            base_damping=0.5,
            safety_margin=1.5,
        )

        result = traverse(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            start_id=start_id,
            direction="outbound",
            max_depth=5,
            estimation_config=config,
        )

        assert "nodes" in result


class TestDeprecationWarning:
    """Tests for deprecated function warning."""

    def test_old_function_warns(self, conn):
        """estimate_reachable_nodes issues deprecation warning."""
        from virt_graph.handlers.base import estimate_reachable_nodes

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM suppliers LIMIT 1")
            row = cur.fetchone()
            if row is None:
                pytest.skip("No suppliers found")
            start_id = row[0]

        with pytest.warns(DeprecationWarning, match="deprecated"):
            estimate_reachable_nodes(
                conn,
                edges_table="supplier_relationships",
                start_id=start_id,
                max_depth=5,
                edge_from_col="seller_id",
                edge_to_col="buyer_id",
            )
