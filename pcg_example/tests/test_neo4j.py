"""
Integration tests for Neo4j schema generator and data loader.

Requires both PostgreSQL (PCG database) and Neo4j to be running.
Skipped when either is unavailable.

Run with: poetry run pytest pcg_example/tests/test_neo4j.py -v

Setup:
    docker compose -f pcg_example/neo4j/docker-compose.yml up -d
"""

import os
from pathlib import Path

import pytest

PCG_ONTOLOGY = Path(__file__).parent.parent / "ontology" / "pcg.yaml"


def _db_available() -> bool:
    """Check if the PCG PostgreSQL database is reachable."""
    try:
        from virt_graph.db import get_connection

        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


def _neo4j_available() -> bool:
    """Check if Neo4j is reachable."""
    try:
        from neo4j import GraphDatabase

        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        auth_str = os.environ.get("NEO4J_AUTH", "neo4j/dev_password")
        user, password = auth_str.split("/", 1)
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        return True
    except Exception:
        return False


skip_no_db = pytest.mark.skipif(
    not _db_available(),
    reason="PCG database not available",
)

skip_no_neo4j = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j not available (run: docker compose -f pcg_example/neo4j/docker-compose.yml up -d)",
)


def _get_neo4j_driver():
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    auth_str = os.environ.get("NEO4J_AUTH", "neo4j/dev_password")
    user, password = auth_str.split("/", 1)
    return GraphDatabase.driver(uri, auth=(user, password))


class TestNeo4jSchema:
    """Tests for schema generation that only require Neo4j (no PG)."""

    def test_generate_schema_returns_statements(self):
        """Schema generator produces Cypher DDL from ontology."""
        from virt_graph.neo4j.schema import generate_schema
        from virt_graph.ontology import OntologyAccessor

        ontology = OntologyAccessor(PCG_ONTOLOGY)
        statements = generate_schema(ontology)

        assert len(statements) > 0
        # Should have one constraint per entity class
        assert len(statements) == len(ontology.classes)

        # Each statement should be a CREATE CONSTRAINT
        for stmt in statements:
            assert "CREATE CONSTRAINT" in stmt

    def test_schema_includes_key_classes(self):
        """Schema constraints include key PCG classes."""
        from virt_graph.neo4j.schema import generate_schema
        from virt_graph.ontology import OntologyAccessor

        ontology = OntologyAccessor(PCG_ONTOLOGY)
        statements = generate_schema(ontology)
        joined = "\n".join(statements)

        for cls_name in ["Supplier", "SKU", "Order", "Plant"]:
            assert cls_name in joined, f"Missing constraint for {cls_name}"

    @skip_no_neo4j
    def test_execute_schema_against_neo4j(self):
        """Schema can be executed against a live Neo4j instance."""
        from virt_graph.neo4j.schema import generate_schema
        from virt_graph.ontology import OntologyAccessor

        ontology = OntologyAccessor(PCG_ONTOLOGY)
        driver = _get_neo4j_driver()
        try:
            # Clear first
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")

            statements = generate_schema(ontology, driver=driver)
            assert len(statements) > 0
        finally:
            driver.close()


@skip_no_db
@skip_no_neo4j
class TestNeo4jLoader:
    """Full integration tests requiring both PG and Neo4j."""

    def test_full_migration(self):
        """Full ontology-driven migration from PG to Neo4j."""
        from virt_graph.db import get_connection
        from virt_graph.neo4j.loader import load_data
        from virt_graph.ontology import OntologyAccessor

        ontology = OntologyAccessor(PCG_ONTOLOGY)
        pg_conn = get_connection()
        driver = _get_neo4j_driver()
        try:
            metrics = load_data(ontology, pg_conn, driver, clear=True)

            # Should have created nodes for each entity class
            assert metrics.total_nodes > 0
            assert metrics.total_relationships > 0
            assert len(metrics.nodes_created) > 0
            assert len(metrics.relationships_created) > 0

            # Verify some nodes exist in Neo4j
            with driver.session() as session:
                result = session.run("MATCH (s:Supplier) RETURN count(s) AS cnt")
                count = result.single()["cnt"]
                assert count > 0, "No Supplier nodes created"

                result = session.run("MATCH (o:Order) RETURN count(o) AS cnt")
                count = result.single()["cnt"]
                assert count > 0, "No Order nodes created"
        finally:
            pg_conn.close()
            driver.close()
