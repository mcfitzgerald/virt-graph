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
def facility_ids(conn):
    """Get named facility IDs for testing."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, name FROM facilities
            WHERE name IN (
                'Chicago Warehouse', 'LA Distribution', 'Denver Hub',
                'NYC Hub', 'Seattle Port', 'Miami Port'
            )
        """)
        return {row[1]: row[0] for row in cur.fetchall()}


class TestShortestPath:
    """Tests for shortest_path function."""

    def test_shortest_path_returns_correct_structure(self, conn, facility_ids):
        """Verify shortest_path returns expected result structure."""
        if len(facility_ids) < 2:
            pytest.skip("Not enough named facilities found")

        start_id = list(facility_ids.values())[0]
        end_id = list(facility_ids.values())[1]

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

    def test_shortest_path_unweighted(self, conn, facility_ids):
        """Find path using hop count (unweighted)."""
        if "Chicago Warehouse" not in facility_ids or "LA Distribution" not in facility_ids:
            pytest.skip("Chicago or LA facility not found")

        chicago_id = facility_ids["Chicago Warehouse"]
        la_id = facility_ids["LA Distribution"]

        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=chicago_id,
            end_id=la_id,
        )

        if result["path"] is None:
            pytest.skip("No path between Chicago and LA in test data")

        # Path should exist and have reasonable hop count
        assert result["path"] is not None
        assert len(result["path"]) >= 2  # At least start and end
        assert result["path"][0] == chicago_id
        assert result["path"][-1] == la_id
        assert result["distance"] == len(result["path"]) - 1  # Hop count

    def test_shortest_path_weighted_by_distance(self, conn, facility_ids):
        """Find path using distance_km weight column."""
        if len(facility_ids) < 2:
            pytest.skip("Not enough facilities found")

        start_id = list(facility_ids.values())[0]
        end_id = list(facility_ids.values())[1]

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

    def test_shortest_path_with_excluded_nodes(self, conn, facility_ids):
        """Find path while excluding a specific node."""
        if "Denver Hub" not in facility_ids:
            pytest.skip("Denver Hub not found")

        denver_id = facility_ids["Denver Hub"]
        other_ids = [fid for name, fid in facility_ids.items() if name != "Denver Hub"]

        if len(other_ids) < 2:
            pytest.skip("Not enough non-Denver facilities")

        start_id = other_ids[0]
        end_id = other_ids[1]

        result = shortest_path(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
            excluded_nodes=[denver_id],
        )

        # If path found, Denver should not be in it
        if result["path"]:
            assert denver_id not in result["path"]
            assert result["excluded_nodes"] == [denver_id]

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

    def test_shortest_path_same_start_and_end(self, conn, facility_ids):
        """Edge case: start_id equals end_id."""
        if not facility_ids:
            pytest.skip("No facilities found")

        node_id = list(facility_ids.values())[0]

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

    def test_shortest_path_nodes_explored(self, conn, facility_ids):
        """Verify nodes_explored is tracked."""
        if len(facility_ids) < 2:
            pytest.skip("Not enough facilities")

        start_id = list(facility_ids.values())[0]
        end_id = list(facility_ids.values())[1]

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

    def test_all_shortest_paths_returns_structure(self, conn, facility_ids):
        """Verify all_shortest_paths returns expected structure."""
        if len(facility_ids) < 2:
            pytest.skip("Not enough facilities")

        start_id = list(facility_ids.values())[0]
        end_id = list(facility_ids.values())[1]

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

    def test_all_shortest_paths_multiple_routes(self, conn, facility_ids):
        """Test finding multiple equal-length paths if they exist."""
        if len(facility_ids) < 2:
            pytest.skip("Not enough facilities")

        start_id = list(facility_ids.values())[0]
        end_id = list(facility_ids.values())[1]

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

    def test_all_shortest_paths_max_paths_limit(self, conn, facility_ids):
        """Verify max_paths parameter limits results."""
        if len(facility_ids) < 2:
            pytest.skip("Not enough facilities")

        start_id = list(facility_ids.values())[0]
        end_id = list(facility_ids.values())[1]

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

    def test_all_shortest_paths_with_excluded_nodes(self, conn, facility_ids):
        """Verify excluded nodes not in any returned path."""
        if "Denver Hub" not in facility_ids:
            pytest.skip("Denver Hub not found")

        denver_id = facility_ids["Denver Hub"]
        other_ids = [fid for name, fid in facility_ids.items() if name != "Denver Hub"]

        if len(other_ids) < 2:
            pytest.skip("Not enough non-Denver facilities")

        start_id = other_ids[0]
        end_id = other_ids[1]

        result = all_shortest_paths(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            start_id=start_id,
            end_id=end_id,
            excluded_nodes=[denver_id],
        )

        # No path should contain Denver
        for path in result["paths"]:
            assert denver_id not in path

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

    def test_different_weights_may_produce_different_paths(self, conn, facility_ids):
        """Compare paths using different weight columns."""
        if len(facility_ids) < 2:
            pytest.skip("Not enough facilities")

        start_id = list(facility_ids.values())[0]
        end_id = list(facility_ids.values())[1]

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
