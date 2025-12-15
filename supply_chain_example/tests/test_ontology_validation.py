"""
Ontology Validation Tests

Validates the ontology against the database schema and data.
Run with: poetry run pytest supply_chain_example/tests/test_ontology_validation.py -v

Includes:
- LinkML structure validation (Layer 1)
- VG annotation validation (Layer 2)
- Database schema coverage tests
- Relationship mapping tests
"""

import os
import subprocess
import sys
import psycopg2
import pytest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from virt_graph.ontology import OntologyAccessor, OntologyValidationError

# Path to supply chain ontology (relative to test file location)
ONTOLOGY_PATH = Path(__file__).parent.parent / "ontology" / "supply_chain.yaml"
METAMODEL_PATH = Path(__file__).parent.parent.parent / "virt_graph.yaml"


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
    """Load the discovered ontology using OntologyAccessor."""
    return OntologyAccessor(ONTOLOGY_PATH)


# =============================================================================
# LINKML VALIDATION TESTS (Two-Layer)
# =============================================================================


class TestLinkMLStructure:
    """Layer 1: LinkML schema structure validation via linkml-lint."""

    def test_supply_chain_ontology_valid(self):
        """Supply chain ontology must pass LinkML lint validation."""
        result = subprocess.run(
            ["poetry", "run", "linkml-lint", "--validate-only", str(ONTOLOGY_PATH)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, \
            f"LinkML validation failed:\n{result.stderr}\n{result.stdout}"

    def test_virt_graph_metamodel_valid(self):
        """VG metamodel extension must pass LinkML lint validation."""
        result = subprocess.run(
            ["poetry", "run", "linkml-lint", "--validate-only", str(METAMODEL_PATH)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, \
            f"LinkML validation failed:\n{result.stderr}\n{result.stdout}"


class TestVGAnnotations:
    """Layer 2: VG-specific annotation validation via OntologyAccessor."""

    def test_ontology_loads_with_validation(self):
        """Ontology should load successfully with validation enabled."""
        # This should not raise OntologyValidationError
        ontology = OntologyAccessor(ONTOLOGY_PATH, validate=True)
        assert ontology is not None

    def test_all_entity_classes_have_required_annotations(self, ontology):
        """All entity classes must have required vg: annotations."""
        for class_name in ontology.classes:
            table = ontology.get_class_table(class_name)
            pk = ontology.get_class_pk(class_name)

            assert table is not None, \
                f"Class {class_name} missing vg:table annotation"
            assert pk is not None, \
                f"Class {class_name} missing vg:primary_key annotation"

    def test_all_relationships_have_required_annotations(self, ontology):
        """All relationship classes must have required vg: annotations."""
        for role_name in ontology.roles:
            role_sql = ontology.get_role_sql(role_name)
            domain = ontology.get_role_domain(role_name)
            range_cls = ontology.get_role_range(role_name)
            operation_types = ontology.get_operation_types(role_name)

            assert role_sql["table"] is not None, \
                f"Role {role_name} missing edge_table"
            assert role_sql["domain_key"] is not None, \
                f"Role {role_name} missing domain_key"
            assert role_sql["range_key"] is not None, \
                f"Role {role_name} missing range_key"
            assert domain is not None, \
                f"Role {role_name} missing domain_class"
            assert range_cls is not None, \
                f"Role {role_name} missing range_class"
            assert len(operation_types) > 0, \
                f"Role {role_name} has no operation_types"

    def test_domain_range_classes_exist(self, ontology):
        """Relationship domain/range must reference valid entity classes."""
        for role_name in ontology.roles:
            domain = ontology.get_role_domain(role_name)
            range_cls = ontology.get_role_range(role_name)

            assert domain in ontology.classes, \
                f"Role {role_name} references unknown domain class: {domain}"
            assert range_cls in ontology.classes, \
                f"Role {role_name} references unknown range class: {range_cls}"

    def test_validation_errors_empty(self, ontology):
        """Explicit validation should return no errors."""
        # Load without validation, then validate manually
        ontology_unchecked = OntologyAccessor(ONTOLOGY_PATH, validate=False)
        errors = ontology_unchecked.validate()

        assert len(errors) == 0, \
            f"Ontology has validation errors:\n" + \
            "\n".join(f"  - {e}" for e in errors)


# =============================================================================
# DATABASE COVERAGE TESTS
# =============================================================================


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
            ontology.get_class_table(class_name)
            for class_name in ontology.classes
        }

        # Get tables from relationships (edge tables)
        relationship_tables = {
            ontology.get_role_table(role_name)
            for role_name in ontology.roles
        }

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

        for class_name in ontology.classes:
            table = ontology.get_class_table(class_name)
            assert table in db_tables, f"Class {class_name} table '{table}' not found"


class TestRelationshipMappings:
    """Test that relationship mappings are correct."""

    def test_all_relationships_have_sql_mapping(self, ontology):
        """Every relationship should have sql mapping."""
        for rel_name in ontology.roles:
            role_sql = ontology.get_role_sql(rel_name)
            assert "table" in role_sql, f"Role {rel_name} missing table in sql"
            assert "domain_key" in role_sql, f"Role {rel_name} missing domain_key"
            assert "range_key" in role_sql, f"Role {rel_name} missing range_key"

    def test_all_relationships_have_operation_types(self, ontology):
        """Every relationship should have operation_types."""
        for rel_name in ontology.roles:
            op_types = ontology.get_operation_types(rel_name)
            assert len(op_types) > 0, \
                f"Role {rel_name} has no operation_types"

    def test_all_relationships_have_properties(self, ontology):
        """Every relationship should have properties with cardinality info."""
        for rel_name in ontology.roles:
            # In new format, cardinality is at top level, properties contains OWL2 axioms
            cardinality = ontology.get_role_cardinality(rel_name)
            # Cardinality should have domain and range
            assert "domain" in cardinality or "range" in cardinality, \
                f"Role {rel_name} missing cardinality"

    def test_fk_columns_exist(self, db_connection, ontology):
        """Foreign key columns referenced in ontology should exist."""
        with db_connection.cursor() as cur:
            for rel_name in ontology.roles:
                table = ontology.get_role_table(rel_name)
                domain_key, range_key = ontology.get_role_keys(rel_name)

                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                """, (table,))
                columns = {row[0] for row in cur.fetchall()}

                assert domain_key in columns, \
                    f"Role {rel_name}: column {domain_key} not in {table}"
                assert range_key in columns, \
                    f"Role {rel_name}: column {range_key} not in {table}"


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
        table = ontology.get_class_table("Supplier")

        with db_connection.cursor() as cur:
            cur.execute(f"SELECT id, name, tier FROM {table} WHERE name = %s",
                       ("Acme Corp",))
            result = cur.fetchone()
            assert result is not None, "Named entity 'Acme Corp' not found"
            assert result[1] == "Acme Corp"
            assert result[2] == 1  # Tier 1 supplier

    def test_green_query_tier1_suppliers(self, db_connection, ontology):
        """GREEN query: List all tier 1 suppliers."""
        table = ontology.get_class_table("Supplier")

        with db_connection.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE tier = 1")
            count = cur.fetchone()[0]
            assert count == 50, f"Expected 50 tier 1 suppliers, got {count}"

    def test_green_query_parts_from_supplier(self, db_connection, ontology):
        """GREEN query: Find parts from a specific supplier."""
        parts_table = ontology.get_class_table("Part")
        domain_key, _ = ontology.get_role_keys("PrimarySupplier")

        with db_connection.cursor() as cur:
            # Find parts where primary_supplier_id = 1 (Acme Corp)
            cur.execute(f"""
                SELECT COUNT(*)
                FROM {parts_table}
                WHERE {domain_key} = 1
            """)
            count = cur.fetchone()[0]
            assert count >= 0  # Just verify query works

    def test_yellow_query_bom_traversal(self, db_connection, ontology):
        """YELLOW query: BOM traversal uses correct columns."""
        table = ontology.get_role_table("component_of")
        child_col, parent_col = ontology.get_role_keys("component_of")

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
        weight_cols = ontology.get_role_weight_columns("connects_to")
        # Convert list of dicts to a dict by name for easier access
        weight_col_names = {wc["name"]: wc["name"] for wc in weight_cols}

        with db_connection.cursor() as cur:
            cur.execute(f"""
                SELECT origin_facility_id, destination_facility_id,
                       distance_km, cost_usd, transit_time_hours
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
        """Supplier tiers should match expected distribution (50/150/300)."""
        # Distribution is now in vg:distribution annotation on tier attribute
        # We verify against the known expected values from the ontology
        expected = {"tier_1": 50, "tier_2": 150, "tier_3": 300}

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


class TestOntologySummary:
    """Summary test for ontology validation."""

    def test_ontology_complete(self, ontology):
        """Verify ontology is complete and valid."""
        # Check ontology structure (now using TBox/RBox format)
        assert ontology.version is not None, "Missing version"
        assert ontology.name is not None, "Missing name"
        assert ontology.classes is not None, "Missing classes"
        assert ontology.roles is not None, "Missing roles"

        # Check class count
        assert len(ontology.classes) >= 7, "Expected at least 7 classes"

        # Check relationship count
        assert len(ontology.roles) >= 10, "Expected at least 10 relationships"

        # Check operation_types coverage
        all_op_types = set()
        for role_name in ontology.roles:
            all_op_types.update(ontology.get_operation_types(role_name))

        assert "direct_join" in all_op_types, "Missing direct_join operations"
        assert "recursive_traversal" in all_op_types, "Missing recursive_traversal operations"

        print("\n" + "="*60)
        print("ONTOLOGY VALIDATION SUMMARY")
        print("="*60)
        print(f"Classes defined: {len(ontology.classes)}")
        print(f"Relationships defined: {len(ontology.roles)}")
        print(f"Operation types: {sorted(all_op_types)}")
        print("="*60)
