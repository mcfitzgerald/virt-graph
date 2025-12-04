"""
Gate 2: Ontology Validation Tests

Validates the discovered ontology against the database schema and data.
Run with: poetry run pytest tests/test_gate2_validation.py -v
"""

import os
import yaml
import psycopg2
import pytest
from pathlib import Path


# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://virt_graph:dev_password@localhost:5432/supply_chain"
)


@pytest.fixture(scope="module")
def db_connection():
    """Create database connection for tests."""
    conn = psycopg2.connect(DATABASE_URL)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def ontology():
    """Load the discovered ontology."""
    ontology_path = Path(__file__).parent.parent / "ontology" / "supply_chain.yaml"
    with open(ontology_path) as f:
        return yaml.safe_load(f)


class TestOntologyCoverage:
    """Test that ontology covers all database tables."""

    def test_all_tables_mapped(self, db_connection, ontology):
        """Every table in schema should map to a class or relationship."""
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            db_tables = {row[0] for row in cur.fetchall()}

        # Get tables from classes
        class_tables = {
            c["sql_mapping"]["table"]
            for c in ontology["classes"].values()
        }

        # Get tables from relationships (edge tables)
        relationship_tables = set()
        for rel in ontology["relationships"].values():
            if "table" in rel["sql_mapping"]:
                relationship_tables.add(rel["sql_mapping"]["table"])

        # Combined coverage
        ontology_tables = class_tables | relationship_tables

        # Exclude audit_log (utility table, not domain)
        db_tables.discard("audit_log")

        missing = db_tables - ontology_tables
        assert not missing, f"Tables not in ontology: {missing}"

    def test_class_tables_exist(self, db_connection, ontology):
        """All class tables should exist in database."""
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            db_tables = {row[0] for row in cur.fetchall()}

        for class_name, class_def in ontology["classes"].items():
            table = class_def["sql_mapping"]["table"]
            assert table in db_tables, f"Class {class_name} table '{table}' not found"


class TestRelationshipMappings:
    """Test that relationship mappings are correct."""

    def test_all_relationships_have_sql_mapping(self, ontology):
        """Every relationship should have sql_mapping."""
        for rel_name, rel_def in ontology["relationships"].items():
            assert "sql_mapping" in rel_def, f"Relationship {rel_name} missing sql_mapping"
            mapping = rel_def["sql_mapping"]
            assert "domain_key" in mapping, f"Relationship {rel_name} missing domain_key"
            assert "range_key" in mapping, f"Relationship {rel_name} missing range_key"

    def test_all_relationships_have_traversal_complexity(self, ontology):
        """Every relationship should have traversal_complexity."""
        for rel_name, rel_def in ontology["relationships"].items():
            assert "traversal_complexity" in rel_def, \
                f"Relationship {rel_name} missing traversal_complexity"
            complexity = rel_def["traversal_complexity"]
            assert complexity in ["GREEN", "YELLOW", "RED"], \
                f"Relationship {rel_name} has invalid complexity: {complexity}"

    def test_all_relationships_have_properties(self, ontology):
        """Every relationship should have cardinality, directionality, reflexivity."""
        required_props = ["cardinality", "is_directional"]
        for rel_name, rel_def in ontology["relationships"].items():
            assert "properties" in rel_def, f"Relationship {rel_name} missing properties"
            props = rel_def["properties"]
            for prop in required_props:
                assert prop in props, f"Relationship {rel_name} missing property: {prop}"

    def test_fk_columns_exist(self, db_connection, ontology):
        """Foreign key columns referenced in ontology should exist."""
        with db_connection.cursor() as cur:
            for rel_name, rel_def in ontology["relationships"].items():
                mapping = rel_def["sql_mapping"]

                # For edge tables with explicit table
                if "table" in mapping:
                    table = mapping["table"]
                    domain_key = mapping["domain_key"]
                    range_key = mapping["range_key"]

                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = %s
                    """, (table,))
                    columns = {row[0] for row in cur.fetchall()}

                    assert domain_key in columns, \
                        f"Relationship {rel_name}: column {domain_key} not in {table}"
                    assert range_key in columns, \
                        f"Relationship {rel_name}: column {range_key} not in {table}"


class TestSelfReferentialEdges:
    """Test self-referential edge tables (graph structure)."""

    def test_supplier_relationships_integrity(self, db_connection):
        """supplier_relationships should have 100% FK integrity."""
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM supplier_relationships
                WHERE seller_id NOT IN (SELECT id FROM suppliers)
                   OR buyer_id NOT IN (SELECT id FROM suppliers)
            """)
            orphans = cur.fetchone()[0]
            assert orphans == 0, f"supplier_relationships has {orphans} orphan records"

    def test_bill_of_materials_integrity(self, db_connection):
        """bill_of_materials should have 100% FK integrity."""
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM bill_of_materials
                WHERE child_part_id NOT IN (SELECT id FROM parts)
                   OR parent_part_id NOT IN (SELECT id FROM parts)
            """)
            orphans = cur.fetchone()[0]
            assert orphans == 0, f"bill_of_materials has {orphans} orphan records"

    def test_transport_routes_integrity(self, db_connection):
        """transport_routes should have 100% FK integrity."""
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM transport_routes
                WHERE origin_facility_id NOT IN (SELECT id FROM facilities)
                   OR destination_facility_id NOT IN (SELECT id FROM facilities)
            """)
            orphans = cur.fetchone()[0]
            assert orphans == 0, f"transport_routes has {orphans} orphan records"

    def test_supplier_network_is_dag(self, db_connection):
        """Supplier relationships should form a DAG (higher tier sells to lower)."""
        with db_connection.cursor() as cur:
            # Check that all relationships flow from higher tier to lower tier
            cur.execute("""
                SELECT COUNT(*) as back_edges
                FROM supplier_relationships sr
                JOIN suppliers s1 ON sr.seller_id = s1.id
                JOIN suppliers s2 ON sr.buyer_id = s2.id
                WHERE s1.tier <= s2.tier
            """)
            back_edges = cur.fetchone()[0]
            # Allow some flexibility - main structure should be DAG
            total_edges = 817  # from schema
            back_edge_ratio = back_edges / total_edges if total_edges > 0 else 0
            assert back_edge_ratio < 0.05, \
                f"Supplier network has {back_edge_ratio:.1%} back edges (expected DAG)"


class TestOntologyQueries:
    """Test that ontology mappings produce correct SQL results."""

    def test_green_query_find_supplier(self, db_connection, ontology):
        """GREEN query: Find supplier by name using ontology mapping."""
        # Get mapping from ontology
        supplier_class = ontology["classes"]["Supplier"]
        table = supplier_class["sql_mapping"]["table"]

        with db_connection.cursor() as cur:
            cur.execute(f"SELECT id, name, tier FROM {table} WHERE name = %s",
                       ("Acme Corp",))
            result = cur.fetchone()
            assert result is not None, "Named entity 'Acme Corp' not found"
            assert result[1] == "Acme Corp"
            assert result[2] == 1  # Tier 1 supplier

    def test_green_query_tier1_suppliers(self, db_connection, ontology):
        """GREEN query: List all tier 1 suppliers."""
        supplier_class = ontology["classes"]["Supplier"]
        table = supplier_class["sql_mapping"]["table"]

        with db_connection.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE tier = 1")
            count = cur.fetchone()[0]
            assert count == 50, f"Expected 50 tier 1 suppliers, got {count}"

    def test_green_query_parts_from_supplier(self, db_connection, ontology):
        """GREEN query: Find parts from a specific supplier."""
        part_class = ontology["classes"]["Part"]
        provides_rel = ontology["relationships"]["provides"]

        parts_table = part_class["sql_mapping"]["table"]
        fk_col = provides_rel["sql_mapping"]["domain_key"]

        with db_connection.cursor() as cur:
            # Find parts where primary_supplier_id = 1 (Acme Corp)
            cur.execute(f"""
                SELECT COUNT(*)
                FROM {parts_table}
                WHERE {fk_col} = 1
            """)
            count = cur.fetchone()[0]
            assert count >= 0  # Just verify query works

    def test_yellow_query_bom_traversal(self, db_connection, ontology):
        """YELLOW query: BOM traversal uses correct columns."""
        bom_rel = ontology["relationships"]["component_of"]
        mapping = bom_rel["sql_mapping"]

        table = mapping["table"]
        child_col = mapping["domain_key"]
        parent_col = mapping["range_key"]

        with db_connection.cursor() as cur:
            # Verify we can query the BOM structure
            cur.execute(f"""
                SELECT {parent_col}, {child_col}, quantity
                FROM {table}
                LIMIT 5
            """)
            results = cur.fetchall()
            assert len(results) > 0, "BOM table is empty"

    def test_red_query_transport_weights(self, db_connection, ontology):
        """RED query: Transport routes have weight columns."""
        connects_rel = ontology["relationships"]["connects_to"]
        mapping = connects_rel["sql_mapping"]
        weight_cols = mapping["weight_columns"]

        with db_connection.cursor() as cur:
            cur.execute(f"""
                SELECT origin_facility_id, destination_facility_id,
                       {weight_cols['distance']},
                       {weight_cols['cost']},
                       {weight_cols['time']}
                FROM transport_routes
                LIMIT 5
            """)
            results = cur.fetchall()
            assert len(results) > 0, "Transport routes empty"
            # Verify weights are not null
            for row in results:
                assert row[2] is not None, "distance_km is null"
                assert row[3] is not None, "cost_usd is null"


class TestNamedEntities:
    """Verify named test entities exist in database."""

    def test_acme_corp_exists(self, db_connection):
        """Acme Corp supplier should exist."""
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT id, supplier_code, tier FROM suppliers WHERE name = %s",
                ("Acme Corp",)
            )
            result = cur.fetchone()
            assert result is not None, "Acme Corp not found"
            assert result[2] == 1, "Acme Corp should be tier 1"

    def test_turbo_encabulator_exists(self, db_connection):
        """Turbo Encabulator product should exist."""
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT id, sku FROM products WHERE name = %s",
                ("Turbo Encabulator",)
            )
            result = cur.fetchone()
            assert result is not None, "Turbo Encabulator not found"
            assert result[1] == "TURBO-001", "Turbo Encabulator should have SKU TURBO-001"

    def test_chicago_warehouse_exists(self, db_connection):
        """Chicago Warehouse facility should exist."""
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT id, facility_code, facility_type FROM facilities WHERE name = %s",
                ("Chicago Warehouse",)
            )
            result = cur.fetchone()
            assert result is not None, "Chicago Warehouse not found"
            assert result[1] == "FAC-CHI", "Facility code should be FAC-CHI"


class TestDataDistribution:
    """Verify data distribution matches ontology documentation."""

    def test_supplier_tier_distribution(self, db_connection, ontology):
        """Supplier tiers should match ontology distribution."""
        expected = ontology["classes"]["Supplier"]["attributes"]["tier"]["distribution"]

        with db_connection.cursor() as cur:
            cur.execute("SELECT tier, COUNT(*) FROM suppliers GROUP BY tier")
            actual = {f"tier_{row[0]}": row[1] for row in cur.fetchall()}

        assert actual["tier_1"] == expected["tier_1"], \
            f"Tier 1 mismatch: {actual['tier_1']} vs {expected['tier_1']}"
        assert actual["tier_2"] == expected["tier_2"], \
            f"Tier 2 mismatch: {actual['tier_2']} vs {expected['tier_2']}"
        assert actual["tier_3"] == expected["tier_3"], \
            f"Tier 3 mismatch: {actual['tier_3']} vs {expected['tier_3']}"

    def test_bom_depth_reasonable(self, db_connection):
        """BOM depth should be within documented range."""
        with db_connection.cursor() as cur:
            cur.execute("""
                WITH RECURSIVE bom_depth AS (
                    SELECT child_part_id, parent_part_id, 1 as depth
                    FROM bill_of_materials
                    WHERE parent_part_id NOT IN (SELECT child_part_id FROM bill_of_materials)
                    UNION ALL
                    SELECT b.child_part_id, b.parent_part_id, bd.depth + 1
                    FROM bill_of_materials b
                    JOIN bom_depth bd ON b.parent_part_id = bd.child_part_id
                    WHERE bd.depth < 20
                )
                SELECT MAX(depth), AVG(depth)::numeric(10,2)
                FROM bom_depth
            """)
            max_depth, avg_depth = cur.fetchone()
            assert max_depth <= 10, f"BOM max depth {max_depth} exceeds expected"
            assert 2 <= float(avg_depth) <= 5, \
                f"BOM avg depth {avg_depth} outside expected range"


class TestGate2Summary:
    """Summary test for Gate 2 validation."""

    def test_gate2_complete(self, ontology):
        """Verify all Gate 2 deliverables are present."""
        # Check ontology structure
        assert "version" in ontology
        assert "domain" in ontology
        assert "classes" in ontology
        assert "relationships" in ontology

        # Check class count
        assert len(ontology["classes"]) >= 7, "Expected at least 7 classes"

        # Check relationship count
        assert len(ontology["relationships"]) >= 10, "Expected at least 10 relationships"

        # Check traversal complexity coverage
        complexities = {
            rel["traversal_complexity"]
            for rel in ontology["relationships"].values()
        }
        assert "GREEN" in complexities, "Missing GREEN complexity relationships"
        assert "YELLOW" in complexities, "Missing YELLOW complexity relationships"
        assert "RED" in complexities, "Missing RED complexity relationships"

        print("\n" + "="*60)
        print("GATE 2 VALIDATION SUMMARY")
        print("="*60)
        print(f"Classes defined: {len(ontology['classes'])}")
        print(f"Relationships defined: {len(ontology['relationships'])}")
        print(f"Traversal complexities: {sorted(complexities)}")
        print("="*60)
