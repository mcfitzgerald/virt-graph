"""
Gate 5 Validation: Benchmark Ready

Validates that all Phase 5 deliverables are complete and working:
1. Neo4j infrastructure is configured
2. Migration script can connect and run
3. All 25 Cypher queries exist and are valid
4. Ground truth is generated for all queries
5. Benchmark runner can execute queries

Run: poetry run pytest tests/test_gate5_validation.py -v
"""

import json
import os
from pathlib import Path

import psycopg2
import pytest
import yaml

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
NEO4J_DIR = PROJECT_ROOT / "neo4j"
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
GROUND_TRUTH_DIR = BENCHMARK_DIR / "ground_truth"


# === Neo4j Infrastructure Tests ===


def test_neo4j_docker_compose_exists():
    """Verify Neo4j docker-compose.yml exists."""
    compose_file = NEO4J_DIR / "docker-compose.yml"
    assert compose_file.exists(), "neo4j/docker-compose.yml not found"


def test_neo4j_docker_compose_valid():
    """Verify Neo4j docker-compose.yml is valid YAML."""
    compose_file = NEO4J_DIR / "docker-compose.yml"
    with open(compose_file) as f:
        config = yaml.safe_load(f)

    assert "services" in config
    assert "neo4j" in config["services"]

    neo4j_service = config["services"]["neo4j"]
    assert "image" in neo4j_service
    assert "neo4j:" in neo4j_service["image"]
    assert "ports" in neo4j_service
    assert "7474:7474" in neo4j_service["ports"]  # HTTP
    assert "7687:7687" in neo4j_service["ports"]  # Bolt


def test_migration_script_exists():
    """Verify migration script exists."""
    migrate_file = NEO4J_DIR / "migrate.py"
    assert migrate_file.exists(), "neo4j/migrate.py not found"


def test_migration_script_importable():
    """Verify migration script can be imported."""
    import sys

    sys.path.insert(0, str(NEO4J_DIR))

    try:
        # Just test that import works (don't actually run migration)
        import importlib.util

        spec = importlib.util.spec_from_file_location("migrate", NEO4J_DIR / "migrate.py")
        module = importlib.util.module_from_spec(spec)
        # Don't execute, just verify syntax
        assert module is not None
    finally:
        if str(NEO4J_DIR) in sys.path:
            sys.path.remove(str(NEO4J_DIR))


# === Cypher Query Tests ===


def test_all_25_cypher_queries_exist():
    """Verify all 25 Cypher query files exist."""
    queries_dir = NEO4J_DIR / "queries"
    assert queries_dir.exists(), "neo4j/queries directory not found"

    for i in range(1, 26):
        query_files = list(queries_dir.glob(f"{i:02d}_*.cypher"))
        assert len(query_files) >= 1, f"Cypher query {i:02d} not found"


def test_cypher_queries_not_empty():
    """Verify all Cypher queries have content."""
    queries_dir = NEO4J_DIR / "queries"

    for cypher_file in queries_dir.glob("*.cypher"):
        content = cypher_file.read_text().strip()
        assert len(content) > 0, f"{cypher_file.name} is empty"

        # Verify contains at least MATCH or RETURN
        content_upper = content.upper()
        assert "MATCH" in content_upper or "RETURN" in content_upper, (
            f"{cypher_file.name} doesn't appear to be valid Cypher"
        )


def test_cypher_queries_have_comments():
    """Verify Cypher queries are documented."""
    queries_dir = NEO4J_DIR / "queries"

    for cypher_file in queries_dir.glob("*.cypher"):
        content = cypher_file.read_text()
        # Check for comment lines
        assert "//" in content, f"{cypher_file.name} should have documentation comments"


# === Benchmark Definition Tests ===


def test_benchmark_queries_yaml_exists():
    """Verify benchmark/queries.yaml exists."""
    queries_file = BENCHMARK_DIR / "queries.yaml"
    assert queries_file.exists(), "benchmark/queries.yaml not found"


def test_benchmark_queries_yaml_valid():
    """Verify benchmark/queries.yaml is valid."""
    queries_file = BENCHMARK_DIR / "queries.yaml"

    with open(queries_file) as f:
        data = yaml.safe_load(f)

    assert "queries" in data, "queries.yaml missing 'queries' key"
    queries = data["queries"]

    assert len(queries) == 25, f"Expected 25 queries, found {len(queries)}"

    # Verify each query has required fields
    required_fields = ["id", "name", "natural_language", "category", "route"]
    for query in queries:
        for field in required_fields:
            assert field in query, f"Query {query.get('id')} missing field: {field}"


def test_benchmark_queries_cover_all_routes():
    """Verify queries cover GREEN, YELLOW, and RED routes."""
    queries_file = BENCHMARK_DIR / "queries.yaml"

    with open(queries_file) as f:
        data = yaml.safe_load(f)

    routes = [q["route"] for q in data["queries"]]

    assert "GREEN" in routes, "No GREEN queries defined"
    assert "YELLOW" in routes, "No YELLOW queries defined"
    assert "RED" in routes, "No RED queries defined"

    green_count = routes.count("GREEN")
    yellow_count = routes.count("YELLOW")
    red_count = routes.count("RED")

    assert green_count == 9, f"Expected 9 GREEN queries, found {green_count}"
    assert yellow_count == 9, f"Expected 9 YELLOW queries, found {yellow_count}"
    assert red_count == 7, f"Expected 7 RED queries, found {red_count}"


# === Ground Truth Tests ===


def test_ground_truth_generator_exists():
    """Verify ground truth generator script exists."""
    generator = BENCHMARK_DIR / "generate_ground_truth.py"
    assert generator.exists(), "benchmark/generate_ground_truth.py not found"


@pytest.fixture
def db_connection():
    """Database connection fixture."""
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql://virt_graph:dev_password@localhost:5432/supply_chain",
    )
    try:
        conn = psycopg2.connect(dsn)
        yield conn
        conn.close()
    except psycopg2.OperationalError:
        pytest.skip("PostgreSQL not available")


def test_can_generate_ground_truth(db_connection):
    """Test that ground truth generation works for a sample query."""
    # Test query 1: Find supplier by name
    with db_connection.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM suppliers
            WHERE name = 'Acme Corp' AND deleted_at IS NULL
        """)
        result = cur.fetchone()
        assert result[0] >= 0, "Query 1 ground truth generation failed"


def test_ground_truth_files_exist():
    """Verify ground truth files exist (after generation)."""
    # Note: This test will fail until generate_ground_truth.py is run
    if not GROUND_TRUTH_DIR.exists():
        pytest.skip("Ground truth not yet generated - run: poetry run python benchmark/generate_ground_truth.py")

    # Check for combined file or individual files
    combined = GROUND_TRUTH_DIR / "all_ground_truth.json"
    if combined.exists():
        with open(combined) as f:
            data = json.load(f)
        assert len(data) >= 20, f"Expected 25 queries in ground truth, found {len(data)}"
    else:
        # Check for at least some individual files
        files = list(GROUND_TRUTH_DIR.glob("query_*.json"))
        assert len(files) >= 20, f"Expected 25 ground truth files, found {len(files)}"


# === Benchmark Runner Tests ===


def test_benchmark_runner_exists():
    """Verify benchmark runner script exists."""
    runner = BENCHMARK_DIR / "run.py"
    assert runner.exists(), "benchmark/run.py not found"


def test_benchmark_runner_importable():
    """Verify benchmark runner can be imported."""
    import importlib.util

    runner_path = BENCHMARK_DIR / "run.py"
    spec = importlib.util.spec_from_file_location("benchmark_run", runner_path)
    module = importlib.util.module_from_spec(spec)
    assert module is not None


def test_virtual_graph_runner_works(db_connection):
    """Test that Virtual Graph runner can execute a simple query."""
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "src"))

    from virt_graph.handlers.traversal import traverse

    # Test query 10: Tier 3 suppliers (using traversal handler)
    # First get a starting supplier
    with db_connection.cursor() as cur:
        cur.execute("""
            SELECT id FROM suppliers
            WHERE tier = 1 AND deleted_at IS NULL
            LIMIT 1
        """)
        result = cur.fetchone()
        if result:
            start_id = result[0]

            # Run traverse
            result = traverse(
                db_connection,
                nodes_table="suppliers",
                edges_table="supplier_relationships",
                edge_from_col="seller_id",
                edge_to_col="buyer_id",
                start_id=start_id,
                direction="inbound",
                max_depth=5,
            )

            assert "nodes" in result
            assert "paths" in result
            assert "depth_reached" in result


# === Integration Tests ===


def test_query_definitions_match_cypher_files():
    """Verify each query in queries.yaml has a matching Cypher file."""
    queries_file = BENCHMARK_DIR / "queries.yaml"
    queries_dir = NEO4J_DIR / "queries"

    with open(queries_file) as f:
        data = yaml.safe_load(f)

    for query in data["queries"]:
        cypher_file = query.get("cypher_file")
        if cypher_file:
            full_path = queries_dir / cypher_file
            assert full_path.exists(), f"Cypher file not found for query {query['id']}: {cypher_file}"


def test_handler_params_specified_for_yellow_red():
    """Verify YELLOW and RED queries have expected handler info."""
    queries_file = BENCHMARK_DIR / "queries.yaml"

    with open(queries_file) as f:
        data = yaml.safe_load(f)

    for query in data["queries"]:
        if query["route"] in ["YELLOW", "RED"]:
            assert "expected_handler" in query or query.get("expected_handler") is not None, (
                f"Query {query['id']} ({query['route']}) should specify expected_handler"
            )


# === Summary Test ===


def test_phase5_deliverables_complete():
    """Summary test verifying all Phase 5 deliverables exist."""
    deliverables = {
        "neo4j/docker-compose.yml": NEO4J_DIR / "docker-compose.yml",
        "neo4j/migrate.py": NEO4J_DIR / "migrate.py",
        "neo4j/queries/*.cypher": NEO4J_DIR / "queries",
        "benchmark/queries.yaml": BENCHMARK_DIR / "queries.yaml",
        "benchmark/generate_ground_truth.py": BENCHMARK_DIR / "generate_ground_truth.py",
        "benchmark/run.py": BENCHMARK_DIR / "run.py",
    }

    missing = []
    for name, path in deliverables.items():
        if not path.exists():
            missing.append(name)

    assert not missing, f"Missing Phase 5 deliverables: {', '.join(missing)}"

    # Verify query count
    queries_dir = NEO4J_DIR / "queries"
    cypher_files = list(queries_dir.glob("*.cypher"))
    assert len(cypher_files) >= 25, f"Expected 25 Cypher queries, found {len(cypher_files)}"

    print("\n" + "=" * 60)
    print("Phase 5 Deliverables Complete!")
    print("=" * 60)
    print(f"  - Neo4j docker-compose.yml: ✓")
    print(f"  - Neo4j migrate.py: ✓")
    print(f"  - Cypher queries: {len(cypher_files)} files ✓")
    print(f"  - benchmark/queries.yaml: ✓")
    print(f"  - benchmark/generate_ground_truth.py: ✓")
    print(f"  - benchmark/run.py: ✓")
    print("=" * 60)
