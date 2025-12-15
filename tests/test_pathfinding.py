"""
Integration tests for pathfinding handlers.

Tests shortest_path() and all_shortest_paths() using the facility/transport_routes
network from the supply chain dataset.

NOTE: These tests use the supply chain sample dataset (facilities, transport_routes).
The handlers themselves are schema-parameterized and work with any relational graph
structure.
"""

import pytest

from virt_graph.handlers.base import get_connection
from virt_graph.handlers.pathfinding import shortest_path, all_shortest_paths


@pytest.fixture
def conn():
    """Get database connection."""
    connection = get_connection()
    yield connection
    connection.close()


@pytest.fixture
def connected_facilities(conn):
    """Get facility IDs that are actually connected by routes."""
    with conn.cursor() as cur:
        # Find facilities that appear in transport_routes (as origin or destination)
        cur.execute("""
            SELECT DISTINCT f.id, f.name
            FROM facilities f
            WHERE f.id IN (
                SELECT origin_facility_id FROM transport_routes
                UNION
                SELECT destination_facility_id FROM transport_routes
            )
            LIMIT 10
        """)
        return [(row[0], row[1]) for row in cur.fetchall()]


@pytest.fixture
def route_pair(conn):
    """Get a pair of facilities that have a direct or indirect path."""
    with conn.cursor() as cur:
        # Find two facilities connected by at least one route
        cur.execute("""
            SELECT DISTINCT tr.origin_facility_id, tr.destination_facility_id
            FROM transport_routes tr
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return (row[0], row[1])
        return None


@pytest.fixture
def intermediate_node(conn):
    """Find a facility that's an intermediate node (both incoming and outgoing routes)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT f.id
            FROM facilities f
            WHERE f.id IN (SELECT origin_facility_id FROM transport_routes)
              AND f.id IN (SELECT destination_facility_id FROM transport_routes)
            LIMIT 1
        """)
        row = cur.fetchone()
        return row[0] if row else None


class TestShortestPath:
    """Tests for shortest_path function."""

    def test_shortest_path_returns_correct_structure(self, conn, connected_facilities):
        """Verify shortest_path returns expected result structure."""
        if len(connected_facilities) < 2:
            pytest.skip("Not enough connected facilities found")

        start_id = connected_facilities[0][0]
        end_id = connected_facilities[1][0]

        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
        )

        # Check all expected keys are present
        assert "path" in result
        assert "path_nodes" in result
        assert "distance" in result
        assert "edges" in result
        assert "nodes_explored" in result
        assert "error" in result

    def test_shortest_path_unweighted(self, conn, route_pair):
        """Find path using hop count (unweighted)."""
        if route_pair is None:
            pytest.skip("No connected facility pair found")

        start_id, end_id = route_pair

        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
        )

        # Path should exist for directly connected facilities
        assert result["path"] is not None
        assert len(result["path"]) >= 2  # At least start and end
        assert result["path"][0] == start_id
        assert result["path"][-1] == end_id
        assert result["distance"] == len(result["path"]) - 1  # Hop count

    def test_shortest_path_weighted_by_distance(self, conn, connected_facilities):
        """Find path using distance_km weight column."""
        if len(connected_facilities) < 2:
            pytest.skip("Not enough facilities found")

        start_id = connected_facilities[0][0]
        end_id = connected_facilities[1][0]

        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
            weight_col="distance_km",
        )

        if result["path"] is None:
            pytest.skip("No path found between facilities")

        # Distance should be a positive number (sum of edge weights)
        assert result["distance"] is not None
        assert result["distance"] > 0

        # Edge weights should be included
        assert len(result["edges"]) == len(result["path"]) - 1
        for edge in result["edges"]:
            assert "weight" in edge
            assert edge["weight"] > 0

    def test_shortest_path_with_excluded_nodes(self, conn, connected_facilities, intermediate_node):
        """Find path while excluding a specific node."""
        if intermediate_node is None:
            pytest.skip("No intermediate node found")

        # Find two facilities that aren't the intermediate node
        other_facilities = [f for f in connected_facilities if f[0] != intermediate_node]
        if len(other_facilities) < 2:
            pytest.skip("Not enough non-intermediate facilities")

        start_id = other_facilities[0][0]
        end_id = other_facilities[1][0]

        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
            excluded_nodes=[intermediate_node],
        )

        # If path found, excluded node should not be in it
        if result["path"]:
            assert intermediate_node not in result["path"]
            assert result["excluded_nodes"] == [intermediate_node]

    def test_shortest_path_no_path_exists(self, conn):
        """Test error handling when no path exists."""
        # Use a non-existent node ID
        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=999999,
            end_id=999998,
        )

        assert result["path"] is None
        assert result["error"] is not None

    def test_shortest_path_same_start_and_end(self, conn, connected_facilities):
        """Edge case: start_id equals end_id."""
        if not connected_facilities:
            pytest.skip("No facilities found")

        node_id = connected_facilities[0][0]

        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=node_id,
            end_id=node_id,
        )

        # Should return path with just the single node
        if result["path"] is not None:
            assert result["path"] == [node_id]
            assert result["distance"] == 0

    def test_shortest_path_nodes_explored(self, conn, connected_facilities):
        """Verify nodes_explored is tracked."""
        if len(connected_facilities) < 2:
            pytest.skip("Not enough facilities")

        start_id = connected_facilities[0][0]
        end_id = connected_facilities[1][0]

        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
        )

        assert result["nodes_explored"] >= 1


class TestAllShortestPaths:
    """Tests for all_shortest_paths function."""

    def test_all_shortest_paths_returns_structure(self, conn, connected_facilities):
        """Verify all_shortest_paths returns expected structure."""
        if len(connected_facilities) < 2:
            pytest.skip("Not enough facilities")

        start_id = connected_facilities[0][0]
        end_id = connected_facilities[1][0]

        result = all_shortest_paths(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
        )

        assert "paths" in result
        assert "distance" in result
        assert "path_count" in result
        assert "nodes_explored" in result
        assert "excluded_nodes" in result

    def test_all_shortest_paths_multiple_routes(self, conn, connected_facilities):
        """Test finding multiple equal-length paths if they exist."""
        if len(connected_facilities) < 2:
            pytest.skip("Not enough facilities")

        start_id = connected_facilities[0][0]
        end_id = connected_facilities[1][0]

        result = all_shortest_paths(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
        )

        if result["paths"]:
            # All paths should have the same length (shortest path property)
            path_lengths = [len(p) for p in result["paths"]]
            assert len(set(path_lengths)) == 1  # All same length

            # Each path should start and end correctly
            for path in result["paths"]:
                assert path[0] == start_id
                assert path[-1] == end_id

    def test_all_shortest_paths_max_paths_limit(self, conn, connected_facilities):
        """Verify max_paths parameter limits results."""
        if len(connected_facilities) < 2:
            pytest.skip("Not enough facilities")

        start_id = connected_facilities[0][0]
        end_id = connected_facilities[1][0]

        result = all_shortest_paths(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
            max_paths=3,
        )

        assert result["path_count"] <= 3

    def test_all_shortest_paths_with_excluded_nodes(self, conn, connected_facilities, intermediate_node):
        """Verify excluded nodes not in any returned path."""
        if intermediate_node is None:
            pytest.skip("No intermediate node found")

        other_facilities = [f for f in connected_facilities if f[0] != intermediate_node]
        if len(other_facilities) < 2:
            pytest.skip("Not enough non-intermediate facilities")

        start_id = other_facilities[0][0]
        end_id = other_facilities[1][0]

        result = all_shortest_paths(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
            excluded_nodes=[intermediate_node],
        )

        # No path should contain the excluded node
        for path in result["paths"]:
            assert intermediate_node not in path

    def test_all_shortest_paths_no_path(self, conn):
        """Verify empty paths list when no path exists."""
        result = all_shortest_paths(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=999999,
            end_id=999998,
        )

        assert result["paths"] == []
        assert result["path_count"] == 0
        assert result["error"] is not None


class TestPathfindingWithWeights:
    """Tests comparing weighted vs unweighted pathfinding."""

    def test_different_weights_may_produce_different_paths(self, conn, connected_facilities):
        """Compare paths using different weight columns."""
        if len(connected_facilities) < 2:
            pytest.skip("Not enough facilities")

        start_id = connected_facilities[0][0]
        end_id = connected_facilities[1][0]

        # Path by distance
        result_distance = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
            weight_col="distance_km",
        )

        # Path by cost
        result_cost = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
            weight_col="cost_usd",
        )

        # Both should find paths (if connected)
        if result_distance["path"] and result_cost["path"]:
            # Paths may or may not be different depending on data
            # Just verify both are valid
            assert result_distance["distance"] > 0
            assert result_cost["distance"] > 0
