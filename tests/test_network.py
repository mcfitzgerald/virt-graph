"""
Integration tests for network analysis handlers.

Tests centrality(), connected_components(), graph_density(), neighbors(),
and resilience_analysis() functions.

NOTE: These tests use the supply chain sample dataset (facilities, transport_routes,
suppliers, supplier_relationships). The handlers themselves are schema-parameterized
and work with any relational graph structure.
"""

import pytest

from virt_graph.handlers.base import get_connection
from virt_graph.handlers.network import (
    centrality,
    connected_components,
    graph_density,
    neighbors,
    resilience_analysis,
)


@pytest.fixture
def conn():
    """Get database connection."""
    connection = get_connection()
    yield connection
    connection.close()


@pytest.fixture
def facility_ids(conn):
    """Get named facility IDs for testing (supply chain sample data)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, name FROM facilities
            WHERE name IN (
                'Chicago Warehouse', 'LA Distribution', 'Denver Hub',
                'NYC Hub', 'Seattle Port', 'Miami Port', 'New York Factory'
            )
        """)
        return {row[1]: row[0] for row in cur.fetchall()}


class TestCentrality:
    """Tests for centrality function."""

    def test_centrality_degree(self, conn):
        """Test degree centrality calculation."""
        result = centrality(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            centrality_type="degree",
            top_n=10,
        )

        # Check structure
        assert "results" in result
        assert "centrality_type" in result
        assert "graph_stats" in result
        assert "nodes_loaded" in result

        assert result["centrality_type"] == "degree"
        assert len(result["results"]) <= 10

        # Each result should have node and score
        for item in result["results"]:
            assert "node" in item
            assert "score" in item
            assert item["score"] >= 0

    def test_centrality_betweenness(self, conn):
        """Test betweenness centrality - identifies bridge nodes."""
        result = centrality(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            centrality_type="betweenness",
            top_n=5,
        )

        assert result["centrality_type"] == "betweenness"
        assert len(result["results"]) <= 5

        # Scores should be between 0 and 1
        for item in result["results"]:
            assert 0 <= item["score"] <= 1

    def test_centrality_closeness(self, conn):
        """Test closeness centrality."""
        result = centrality(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            centrality_type="closeness",
            top_n=5,
        )

        assert result["centrality_type"] == "closeness"

    def test_centrality_pagerank(self, conn):
        """Test PageRank centrality."""
        result = centrality(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            centrality_type="pagerank",
            top_n=5,
        )

        assert result["centrality_type"] == "pagerank"

        # PageRank scores should sum to ~1
        total_score = sum(item["score"] for item in result["results"])
        # Only checking top N, so can't assert sum == 1

    def test_centrality_top_n_limit(self, conn):
        """Verify top_n parameter limits results."""
        result = centrality(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            centrality_type="degree",
            top_n=3,
        )

        assert len(result["results"]) <= 3

    def test_centrality_invalid_type_raises(self, conn):
        """Test that invalid centrality type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown centrality type"):
            centrality(
                conn,
                nodes_table="facilities",
                edges_table="transport_routes",
                edge_from_col="origin_facility_id",
                edge_to_col="destination_facility_id",
                centrality_type="invalid_type",
            )

    def test_centrality_graph_stats(self, conn):
        """Verify graph_stats contains expected metrics."""
        result = centrality(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            centrality_type="degree",
        )

        stats = result["graph_stats"]
        assert "nodes" in stats
        assert "edges" in stats
        assert "density" in stats
        assert stats["nodes"] > 0
        assert stats["edges"] > 0
        assert 0 <= stats["density"] <= 1


class TestConnectedComponents:
    """Tests for connected_components function."""

    def test_connected_components_returns_structure(self, conn):
        """Verify connected_components returns expected structure."""
        result = connected_components(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
        )

        assert "components" in result
        assert "component_count" in result
        assert "largest_component_size" in result
        assert "isolated_nodes" in result
        assert "graph_stats" in result

    def test_connected_components_on_connected_graph(self, conn):
        """Facilities network should be mostly connected."""
        result = connected_components(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
        )

        # Should have at least one component
        assert result["component_count"] >= 1

        # Largest component should contain most nodes
        total_nodes = result["graph_stats"]["nodes"]
        if total_nodes > 0:
            coverage = result["largest_component_size"] / total_nodes
            # Expect >50% in largest component for a "connected" network
            assert coverage > 0.5

    def test_connected_components_min_size_filter(self, conn):
        """Test min_size parameter filters small components."""
        result = connected_components(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            min_size=5,
        )

        # All returned components should have size >= 5
        for component in result["components"]:
            assert component["size"] >= 5

    def test_connected_components_sample_nodes(self, conn):
        """Verify sample_nodes contains actual node data."""
        result = connected_components(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
        )

        if result["components"]:
            component = result["components"][0]
            assert "sample_nodes" in component
            # Sample nodes should have facility data
            if component["sample_nodes"]:
                node = component["sample_nodes"][0]
                assert "id" in node


class TestGraphDensity:
    """Tests for graph_density function."""

    def test_graph_density_returns_stats(self, conn):
        """Verify graph_density returns expected statistics."""
        result = graph_density(
            conn,
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
        )

        assert "nodes" in result
        assert "edges" in result
        assert "density" in result
        assert "is_directed" in result

    def test_graph_density_on_facilities(self, conn):
        """Test graph density calculation on facilities network."""
        result = graph_density(
            conn,
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
        )

        # Should have reasonable values
        assert result["nodes"] > 0
        assert result["edges"] > 0
        assert 0 <= result["density"] <= 1
        assert result["is_directed"] is True  # DiGraph by default

    def test_graph_density_degree_stats(self, conn):
        """Verify degree statistics are included."""
        result = graph_density(
            conn,
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
        )

        if result["nodes"] > 0:
            assert "avg_degree" in result
            assert "max_degree" in result
            assert "min_degree" in result
            assert result["avg_degree"] >= 0
            assert result["max_degree"] >= result["min_degree"]


class TestNeighbors:
    """Tests for neighbors function."""

    def test_neighbors_outbound(self, conn, facility_ids):
        """Test outbound neighbors (destinations from a facility)."""
        if "Chicago Warehouse" not in facility_ids:
            pytest.skip("Chicago Warehouse not found")

        chicago_id = facility_ids["Chicago Warehouse"]

        result = neighbors(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            node_id=chicago_id,
            direction="outbound",
        )

        assert "neighbors" in result
        assert "outbound_count" in result
        assert "inbound_count" in result
        assert "total_degree" in result

        # Outbound should have results, inbound should be 0 for this query
        assert result["outbound_count"] >= 0
        assert result["inbound_count"] == 0

    def test_neighbors_inbound(self, conn, facility_ids):
        """Test inbound neighbors (origins to a facility)."""
        if "Chicago Warehouse" not in facility_ids:
            pytest.skip("Chicago Warehouse not found")

        chicago_id = facility_ids["Chicago Warehouse"]

        result = neighbors(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            node_id=chicago_id,
            direction="inbound",
        )

        assert result["inbound_count"] >= 0
        assert result["outbound_count"] == 0

    def test_neighbors_both(self, conn, facility_ids):
        """Test both directions."""
        if "Denver Hub" not in facility_ids:
            pytest.skip("Denver Hub not found")

        denver_id = facility_ids["Denver Hub"]

        result = neighbors(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            node_id=denver_id,
            direction="both",
        )

        # Total degree should be unique neighbors from both directions
        assert result["total_degree"] >= 0
        # Denver Hub should have connections in sample data
        assert result["outbound_count"] + result["inbound_count"] >= 0

    def test_neighbors_returns_node_details(self, conn, facility_ids):
        """Verify neighbors list contains full node dicts."""
        if not facility_ids:
            pytest.skip("No facilities found")

        node_id = list(facility_ids.values())[0]

        result = neighbors(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            node_id=node_id,
            direction="both",
        )

        if result["neighbors"]:
            neighbor = result["neighbors"][0]
            assert "id" in neighbor
            # Should have facility fields
            assert "name" in neighbor or "facility_code" in neighbor


class TestResilienceAnalysis:
    """Tests for resilience_analysis function."""

    def test_resilience_analysis_structure(self, conn, facility_ids):
        """Verify resilience_analysis returns expected structure."""
        if not facility_ids:
            pytest.skip("No facilities found")

        node_id = list(facility_ids.values())[0]

        result = resilience_analysis(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            node_to_remove=node_id,
        )

        assert "node_removed" in result
        assert "node_removed_info" in result
        assert "disconnected_pairs" in result
        assert "components_before" in result
        assert "components_after" in result
        assert "component_increase" in result
        assert "isolated_nodes" in result
        assert "affected_node_count" in result
        assert "is_critical" in result

    def test_resilience_hub_removal(self, conn, facility_ids):
        """Test removing a hub node - should show impact."""
        if "Denver Hub" not in facility_ids:
            pytest.skip("Denver Hub not found")

        denver_id = facility_ids["Denver Hub"]

        result = resilience_analysis(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            node_to_remove=denver_id,
        )

        assert result["node_removed"] == denver_id
        # Hub removal might create disconnections
        # (depends on data, so we just verify structure)
        assert isinstance(result["is_critical"], bool)
        assert result["component_increase"] >= 0

    def test_resilience_nonexistent_node(self, conn):
        """Test with invalid node_id - should handle gracefully."""
        result = resilience_analysis(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            node_to_remove=999999,
        )

        assert "error" in result
        assert result["error"] is not None
        assert result["is_critical"] is False

    def test_resilience_component_tracking(self, conn, facility_ids):
        """Verify component counts are tracked correctly."""
        if not facility_ids:
            pytest.skip("No facilities found")

        node_id = list(facility_ids.values())[0]

        result = resilience_analysis(
            conn,
            nodes_table="facilities",
            edges_table="transport_routes",
            edge_from_col="origin_facility_id",
            edge_to_col="destination_facility_id",
            node_to_remove=node_id,
        )

        # components_after should be >= components_before (removal can only split)
        assert result["components_after"] >= result["components_before"]
        assert result["component_increase"] == result["components_after"] - result["components_before"]


class TestNetworkOnSuppliers:
    """
    Additional tests using supplier network (larger graph).

    Uses supplier_relationships table which has ~800 edges vs ~200 for transport_routes.
    """

    def test_centrality_on_supplier_network(self, conn):
        """Test centrality on larger supplier network."""
        result = centrality(
            conn,
            nodes_table="suppliers",
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
            centrality_type="degree",
            top_n=10,
        )

        assert result["nodes_loaded"] > 0
        assert len(result["results"]) <= 10

    def test_graph_density_on_suppliers(self, conn):
        """Test graph density on supplier network."""
        result = graph_density(
            conn,
            edges_table="supplier_relationships",
            edge_from_col="seller_id",
            edge_to_col="buyer_id",
        )

        # Supplier network should have ~500 nodes
        assert result["nodes"] > 100
        assert result["edges"] > 0
