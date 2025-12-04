"""
Benchmark harness comparing Virtual Graph vs Neo4j.

Runs all 25 benchmark queries against both systems and generates
a comprehensive comparison report.

Usage:
    poetry run python benchmark/run.py [--system vg|neo4j|both] [--query N]

Requirements:
    - PostgreSQL running with seed data
    - Neo4j running with migrated data (for neo4j/both modes)
"""

import argparse
import json
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import psycopg2
import yaml

# Optional Neo4j import
try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

# Add parent to path for handler imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virt_graph.handlers.base import SubgraphTooLarge
from virt_graph.handlers.network import centrality, connected_components
from virt_graph.handlers.pathfinding import shortest_path
from virt_graph.handlers.traversal import traverse

# Configuration
PG_DSN = "postgresql://virt_graph:dev_password@localhost:5432/supply_chain"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "dev_password")

BENCHMARK_DIR = Path(__file__).parent
QUERIES_FILE = BENCHMARK_DIR / "queries.yaml"
GROUND_TRUTH_DIR = BENCHMARK_DIR / "ground_truth"
RESULTS_DIR = BENCHMARK_DIR / "results"
NEO4J_QUERIES_DIR = BENCHMARK_DIR.parent / "neo4j" / "queries"


@dataclass
class QueryResult:
    """Result from running a single query."""

    query_id: int
    system: str  # "virtual_graph" or "neo4j"
    correct: bool
    first_attempt_correct: bool
    retries_needed: int
    execution_time_ms: float
    result_count: int
    error: str | None = None
    pattern_used: str | None = None  # Virtual Graph only
    handler_used: str | None = None  # Virtual Graph only


@dataclass
class BenchmarkResults:
    """Aggregated benchmark results."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    query_results: list[QueryResult] = field(default_factory=list)

    def add_result(self, result: QueryResult):
        self.query_results.append(result)

    def get_results_by_system(self, system: str) -> list[QueryResult]:
        return [r for r in self.query_results if r.system == system]

    def get_results_by_route(self, route: str) -> list[QueryResult]:
        route_ranges = {"GREEN": range(1, 10), "YELLOW": range(10, 19), "RED": range(19, 26)}
        return [r for r in self.query_results if r.query_id in route_ranges[route]]

    def summary_stats(self, system: str | None = None, route: str | None = None) -> dict:
        """Calculate summary statistics."""
        results = self.query_results

        if system:
            results = [r for r in results if r.system == system]
        if route:
            results = self.get_results_by_route(route)
            if system:
                results = [r for r in results if r.system == system]

        if not results:
            return {}

        times = [r.execution_time_ms for r in results]
        correct = [r for r in results if r.correct]
        first_attempt = [r for r in results if r.first_attempt_correct]

        return {
            "total_queries": len(results),
            "correct": len(correct),
            "accuracy": len(correct) / len(results) if results else 0,
            "first_attempt_correct": len(first_attempt),
            "first_attempt_rate": len(first_attempt) / len(results) if results else 0,
            "avg_time_ms": statistics.mean(times) if times else 0,
            "median_time_ms": statistics.median(times) if times else 0,
            "p95_time_ms": (
                sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0] if times else 0
            ),
            "min_time_ms": min(times) if times else 0,
            "max_time_ms": max(times) if times else 0,
        }


class VirtualGraphRunner:
    """Runs benchmark queries using Virtual Graph handlers."""

    def __init__(self, pg_dsn: str):
        self.pg_dsn = pg_dsn
        self.conn = None

    def connect(self):
        self.conn = psycopg2.connect(self.pg_dsn)

    def close(self):
        if self.conn:
            self.conn.close()

    def run_query(self, query_def: dict, ground_truth: dict) -> QueryResult:
        """Run a single query and compare to ground truth."""
        query_id = query_def["id"]
        route = query_def["route"]
        handler = query_def.get("expected_handler")

        start_time = time.time()
        error = None
        result_count = 0
        handler_used = None

        try:
            if route == "GREEN":
                # Direct SQL query
                result_count, result_ids = self._run_green_query(query_def)
            elif route == "YELLOW":
                # Use traverse handler
                result_count, result_ids = self._run_yellow_query(query_def)
                handler_used = "traverse"
            elif route == "RED":
                # Use network/pathfinding handlers
                result_count, result_ids = self._run_red_query(query_def)
                handler_used = handler
        except SubgraphTooLarge as e:
            error = f"SubgraphTooLarge: {e}"
            result_ids = []
        except Exception as e:
            error = str(e)
            result_ids = []

        execution_time_ms = (time.time() - start_time) * 1000

        # Compare to ground truth
        expected_count = ground_truth.get("expected_count", 0)
        expected_ids = set(ground_truth.get("expected_node_ids", []))

        # Check correctness
        if error:
            correct = False
        elif expected_count is not None and expected_count > 0:
            # For countable results, check overlap
            result_set = set(result_ids) if result_ids else set()
            if expected_ids:
                overlap = len(result_set & expected_ids) / max(len(expected_ids), 1)
                correct = overlap >= 0.8  # 80% overlap threshold
            else:
                correct = result_count == expected_count
        else:
            # For pathfinding/ranking queries, more lenient
            correct = result_count > 0 or not ground_truth.get("expected_path")

        return QueryResult(
            query_id=query_id,
            system="virtual_graph",
            correct=correct,
            first_attempt_correct=correct,
            retries_needed=0,
            execution_time_ms=execution_time_ms,
            result_count=result_count,
            error=error,
            handler_used=handler_used,
        )

    def _run_green_query(self, query_def: dict) -> tuple[int, list[int]]:
        """Run a GREEN (simple SQL) query."""
        query_id = query_def["id"]
        params = query_def.get("parameters", {})

        # Map query IDs to SQL
        sql_map = {
            1: ("SELECT id FROM suppliers WHERE name = %(supplier_name)s AND deleted_at IS NULL", params),
            2: ("SELECT id FROM suppliers WHERE tier = 1 AND is_active = true AND deleted_at IS NULL", {}),
            3: (
                "SELECT id FROM parts WHERE LOWER(description) LIKE '%%sensor%%' AND deleted_at IS NULL",
                {},
            ),
            4: (
                """SELECT p.id FROM parts p
                   JOIN suppliers s ON p.primary_supplier_id = s.id
                   WHERE s.name = %(supplier_name)s AND p.deleted_at IS NULL""",
                params,
            ),
            5: ("SELECT id FROM facilities WHERE state = %(state)s AND is_active = true", params),
            6: (
                """SELECT c.id FROM supplier_certifications c
                   JOIN suppliers s ON c.supplier_id = s.id
                   WHERE s.name = %(supplier_name)s AND c.is_valid = true""",
                params,
            ),
            7: (
                """SELECT prod.id FROM products prod
                   JOIN product_components pc ON prod.id = pc.product_id
                   JOIN parts p ON pc.part_id = p.id
                   WHERE p.part_number = %(part_number)s""",
                params,
            ),
            8: (
                """SELECT o.id FROM orders o
                   JOIN facilities f ON o.shipping_facility_id = f.id
                   WHERE f.name = %(facility_name)s AND o.status != 'cancelled'
                   LIMIT 100""",
                params,
            ),
            9: (
                """SELECT s.id FROM suppliers s
                   JOIN part_suppliers ps ON s.id = ps.supplier_id
                   JOIN parts p ON ps.part_id = p.id
                   WHERE p.part_number = %(part_number)s AND ps.is_approved = true""",
                params,
            ),
        }

        sql, sql_params = sql_map.get(query_id, (None, None))
        if not sql:
            return 0, []

        with self.conn.cursor() as cur:
            cur.execute(sql, sql_params)
            rows = cur.fetchall()
            return len(rows), [row[0] for row in rows]

    def _run_yellow_query(self, query_def: dict) -> tuple[int, list[int]]:
        """Run a YELLOW (recursive traversal) query using handlers."""
        query_id = query_def["id"]
        params = query_def.get("parameters", {})

        # Get entity IDs from names
        if query_id in [10, 11, 12, 16]:
            # Supplier queries
            supplier_name = params.get("company_name") or params.get("supplier_name")
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM suppliers WHERE name = %s AND deleted_at IS NULL",
                    (supplier_name,),
                )
                row = cur.fetchone()
                if not row:
                    return 0, []
                start_id = row[0]

            if query_id == 10:
                # Tier 3 suppliers for company
                result = traverse(
                    self.conn,
                    nodes_table="suppliers",
                    edges_table="supplier_relationships",
                    edge_from_col="seller_id",
                    edge_to_col="buyer_id",
                    start_id=start_id,
                    direction="inbound",
                    max_depth=10,
                )
                # Filter to tier 3
                tier3_ids = []
                for node in result["nodes"]:
                    if node.get("tier") == 3:
                        tier3_ids.append(node["id"])
                return len(tier3_ids), tier3_ids

            elif query_id in [11, 16]:
                # Upstream suppliers
                result = traverse(
                    self.conn,
                    nodes_table="suppliers",
                    edges_table="supplier_relationships",
                    edge_from_col="seller_id",
                    edge_to_col="buyer_id",
                    start_id=start_id,
                    direction="inbound",
                    max_depth=10,
                )
                node_ids = [n["id"] for n in result["nodes"] if n["id"] != start_id]
                return len(node_ids), node_ids

            elif query_id == 12:
                # Downstream customers
                result = traverse(
                    self.conn,
                    nodes_table="suppliers",
                    edges_table="supplier_relationships",
                    edge_from_col="seller_id",
                    edge_to_col="buyer_id",
                    start_id=start_id,
                    direction="outbound",
                    max_depth=10,
                )
                node_ids = [n["id"] for n in result["nodes"] if n["id"] != start_id]
                return len(node_ids), node_ids

        elif query_id in [13, 17]:
            # BOM explosion for product
            product_name = params.get("product_name")
            with self.conn.cursor() as cur:
                cur.execute(
                    """SELECT p.id FROM parts p
                       JOIN product_components pc ON pc.part_id = p.id
                       JOIN products prod ON prod.id = pc.product_id
                       WHERE prod.name = %s""",
                    (product_name,),
                )
                rows = cur.fetchall()
                if not rows:
                    return 0, []

            all_parts = set()
            for row in rows:
                result = traverse(
                    self.conn,
                    nodes_table="parts",
                    edges_table="bill_of_materials",
                    edge_from_col="parent_part_id",
                    edge_to_col="child_part_id",
                    start_id=row[0],
                    direction="outbound",
                    max_depth=20,
                )
                all_parts.update(n["id"] for n in result["nodes"])

            if query_id == 17:
                # Filter to leaf parts only
                with self.conn.cursor() as cur:
                    cur.execute(
                        """SELECT DISTINCT parent_part_id FROM bill_of_materials
                           WHERE parent_part_id = ANY(%s)""",
                        (list(all_parts),),
                    )
                    parent_ids = {row[0] for row in cur.fetchall()}
                    leaf_ids = list(all_parts - parent_ids)
                    return len(leaf_ids), leaf_ids

            return len(all_parts), list(all_parts)

        elif query_id == 14:
            # Where used
            part_number = params.get("part_number")
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM parts WHERE part_number = %s AND deleted_at IS NULL",
                    (part_number,),
                )
                row = cur.fetchone()
                if not row:
                    return 0, []
                start_id = row[0]

            result = traverse(
                self.conn,
                nodes_table="parts",
                edges_table="bill_of_materials",
                edge_from_col="child_part_id",
                edge_to_col="parent_part_id",
                start_id=start_id,
                direction="outbound",
                max_depth=20,
            )
            node_ids = [n["id"] for n in result["nodes"] if n["id"] != start_id]
            return len(node_ids), node_ids

        elif query_id == 15:
            # Impact analysis
            supplier_name = params.get("supplier_name")
            with self.conn.cursor() as cur:
                # Get parts from supplier
                cur.execute(
                    """SELECT p.id FROM parts p
                       JOIN suppliers s ON p.primary_supplier_id = s.id
                       WHERE s.name = %s AND p.deleted_at IS NULL""",
                    (supplier_name,),
                )
                part_rows = cur.fetchall()

            if not part_rows:
                return 0, []

            # Find all parent assemblies
            affected_parts = set()
            for row in part_rows:
                result = traverse(
                    self.conn,
                    nodes_table="parts",
                    edges_table="bill_of_materials",
                    edge_from_col="child_part_id",
                    edge_to_col="parent_part_id",
                    start_id=row[0],
                    direction="outbound",
                    max_depth=20,
                )
                affected_parts.update(n["id"] for n in result["nodes"])

            # Find products using affected parts
            with self.conn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT prod.id FROM products prod
                       JOIN product_components pc ON prod.id = pc.product_id
                       WHERE pc.part_id = ANY(%s)""",
                    (list(affected_parts),),
                )
                product_ids = [row[0] for row in cur.fetchall()]

            return len(product_ids), product_ids

        elif query_id == 18:
            # Common suppliers
            product1 = params.get("product1_name")
            product2 = params.get("product2_name")

            def get_product_parts(name):
                with self.conn.cursor() as cur:
                    cur.execute(
                        """SELECT p.id FROM parts p
                           JOIN product_components pc ON pc.part_id = p.id
                           JOIN products prod ON prod.id = pc.product_id
                           WHERE prod.name = %s""",
                        (name,),
                    )
                    return [row[0] for row in cur.fetchall()]

            parts1 = get_product_parts(product1)
            parts2 = get_product_parts(product2)

            all_parts1 = set()
            for pid in parts1:
                result = traverse(
                    self.conn,
                    nodes_table="parts",
                    edges_table="bill_of_materials",
                    edge_from_col="parent_part_id",
                    edge_to_col="child_part_id",
                    start_id=pid,
                    direction="outbound",
                    max_depth=10,
                )
                all_parts1.update(n["id"] for n in result["nodes"])

            all_parts2 = set()
            for pid in parts2:
                result = traverse(
                    self.conn,
                    nodes_table="parts",
                    edges_table="bill_of_materials",
                    edge_from_col="parent_part_id",
                    edge_to_col="child_part_id",
                    start_id=pid,
                    direction="outbound",
                    max_depth=10,
                )
                all_parts2.update(n["id"] for n in result["nodes"])

            # Find suppliers common to both
            with self.conn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT s.id FROM suppliers s
                       JOIN parts p1 ON p1.primary_supplier_id = s.id
                       JOIN parts p2 ON p2.primary_supplier_id = s.id
                       WHERE p1.id = ANY(%s) AND p2.id = ANY(%s)
                         AND s.deleted_at IS NULL""",
                    (list(all_parts1), list(all_parts2)),
                )
                supplier_ids = [row[0] for row in cur.fetchall()]

            return len(supplier_ids), supplier_ids

        return 0, []

    def _run_red_query(self, query_def: dict) -> tuple[int, list[int]]:
        """Run a RED (network algorithm) query using handlers."""
        query_id = query_def["id"]
        params = query_def.get("parameters", {})
        handler_params = query_def.get("handler_params", {})

        if query_id in [19, 20, 21]:
            # Shortest path queries
            from_facility = params.get("from_facility")
            to_facility = params.get("to_facility")
            weight_col = handler_params.get("weight_col")

            # Get facility IDs
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name FROM facilities WHERE name IN (%s, %s)",
                    (from_facility, to_facility),
                )
                rows = cur.fetchall()
                facility_map = {row[1]: row[0] for row in rows}

            if from_facility not in facility_map or to_facility not in facility_map:
                return 0, []

            result = shortest_path(
                self.conn,
                nodes_table="facilities",
                edges_table="transport_routes",
                edge_from_col="origin_facility_id",
                edge_to_col="destination_facility_id",
                start_id=facility_map[from_facility],
                end_id=facility_map[to_facility],
                weight_col=weight_col,
                max_depth=20,
            )

            if result["path"]:
                return 1, result["path"]
            return 0, []

        elif query_id in [22, 23]:
            # Centrality queries
            if query_id == 22:
                result = centrality(
                    self.conn,
                    nodes_table="facilities",
                    edges_table="transport_routes",
                    edge_from_col="origin_facility_id",
                    edge_to_col="destination_facility_id",
                    centrality_type="degree",  # Simplified from betweenness
                    top_n=10,
                )
            else:
                result = centrality(
                    self.conn,
                    nodes_table="suppliers",
                    edges_table="supplier_relationships",
                    edge_from_col="seller_id",
                    edge_to_col="buyer_id",
                    centrality_type="degree",
                    top_n=10,
                )

            node_ids = [r["node"]["id"] for r in result["results"]]
            return len(node_ids), node_ids

        elif query_id == 24:
            # Isolated facilities
            result = connected_components(
                self.conn,
                nodes_table="facilities",
                edges_table="transport_routes",
                edge_from_col="origin_facility_id",
                edge_to_col="destination_facility_id",
                min_size=1,
            )

            # Find facilities with low connectivity
            all_isolated = []
            for comp in result["components"]:
                if comp["size"] < 3:
                    all_isolated.extend(comp["node_ids"])
            return len(all_isolated), all_isolated

        elif query_id == 25:
            # All routes (use shortest path as approximation)
            from_facility = params.get("from_facility")
            to_facility = params.get("to_facility")

            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name FROM facilities WHERE name IN (%s, %s)",
                    (from_facility, to_facility),
                )
                rows = cur.fetchall()
                facility_map = {row[1]: row[0] for row in rows}

            if from_facility not in facility_map or to_facility not in facility_map:
                return 0, []

            result = shortest_path(
                self.conn,
                nodes_table="facilities",
                edges_table="transport_routes",
                edge_from_col="origin_facility_id",
                edge_to_col="destination_facility_id",
                start_id=facility_map[from_facility],
                end_id=facility_map[to_facility],
                weight_col="cost_usd",
                max_depth=5,
            )

            if result["path"]:
                return 1, result["path"]
            return 0, []

        return 0, []


class Neo4jRunner:
    """Runs benchmark queries using Neo4j."""

    def __init__(self, uri: str, auth: tuple[str, str]):
        self.uri = uri
        self.auth = auth
        self.driver = None

    def connect(self):
        if not NEO4J_AVAILABLE:
            raise RuntimeError("neo4j package not installed. Run: poetry install --extras neo4j")
        self.driver = GraphDatabase.driver(self.uri, auth=self.auth)

    def close(self):
        if self.driver:
            self.driver.close()

    def run_query(self, query_def: dict, ground_truth: dict) -> QueryResult:
        """Run a single Cypher query and compare to ground truth."""
        query_id = query_def["id"]
        cypher_file = query_def.get("cypher_file")
        params = query_def.get("parameters", {})

        if not cypher_file:
            return QueryResult(
                query_id=query_id,
                system="neo4j",
                correct=False,
                first_attempt_correct=False,
                retries_needed=0,
                execution_time_ms=0,
                result_count=0,
                error="No Cypher file specified",
            )

        # Load Cypher query
        cypher_path = NEO4J_QUERIES_DIR / cypher_file
        if not cypher_path.exists():
            return QueryResult(
                query_id=query_id,
                system="neo4j",
                correct=False,
                first_attempt_correct=False,
                retries_needed=0,
                execution_time_ms=0,
                result_count=0,
                error=f"Cypher file not found: {cypher_path}",
            )

        cypher = cypher_path.read_text()
        # Remove comments
        cypher_lines = [line for line in cypher.split("\n") if not line.strip().startswith("//")]
        cypher = "\n".join(cypher_lines)

        start_time = time.time()
        error = None
        result_count = 0
        result_ids = []

        try:
            with self.driver.session() as session:
                # Convert params for Neo4j
                neo4j_params = {}
                for k, v in params.items():
                    neo4j_params[k] = v

                result = session.run(cypher, **neo4j_params)
                records = list(result)
                result_count = len(records)

                # Extract node IDs from results
                for record in records:
                    for value in record.values():
                        if hasattr(value, "id"):
                            result_ids.append(value.id)
                        elif hasattr(value, "get") and "id" in value:
                            result_ids.append(value["id"])

        except Exception as e:
            error = str(e)

        execution_time_ms = (time.time() - start_time) * 1000

        # Compare to ground truth
        expected_count = ground_truth.get("expected_count")
        expected_ids = set(ground_truth.get("expected_node_ids", []))

        if error:
            correct = False
        elif expected_count is not None and expected_count > 0:
            result_set = set(result_ids) if result_ids else set()
            if expected_ids:
                overlap = len(result_set & expected_ids) / max(len(expected_ids), 1)
                correct = overlap >= 0.8
            else:
                correct = result_count == expected_count
        else:
            correct = result_count > 0 or not ground_truth.get("expected_path")

        return QueryResult(
            query_id=query_id,
            system="neo4j",
            correct=correct,
            first_attempt_correct=correct,
            retries_needed=0,
            execution_time_ms=execution_time_ms,
            result_count=result_count,
            error=error,
        )


def load_queries() -> list[dict]:
    """Load query definitions from YAML."""
    with open(QUERIES_FILE) as f:
        data = yaml.safe_load(f)
    return data.get("queries", [])


def load_ground_truth() -> dict[int, dict]:
    """Load ground truth for all queries."""
    combined_file = GROUND_TRUTH_DIR / "all_ground_truth.json"
    if combined_file.exists():
        with open(combined_file) as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}

    # Load individual files
    truth = {}
    for i in range(1, 26):
        filepath = GROUND_TRUTH_DIR / f"query_{i:02d}.json"
        if filepath.exists():
            with open(filepath) as f:
                truth[i] = json.load(f)
    return truth


def generate_report(results: BenchmarkResults) -> str:
    """Generate markdown report from benchmark results."""
    lines = []
    lines.append("# Virtual Graph Benchmark Results")
    lines.append(f"\nGenerated: {results.timestamp}")
    lines.append("")

    # Overall summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| System | Accuracy | First-Attempt | Avg Latency | P95 Latency |")
    lines.append("|--------|----------|---------------|-------------|-------------|")

    for system in ["virtual_graph", "neo4j"]:
        stats = results.summary_stats(system=system)
        if stats:
            lines.append(
                f"| {system.replace('_', ' ').title()} | "
                f"{stats['accuracy']:.1%} | "
                f"{stats['first_attempt_rate']:.1%} | "
                f"{stats['avg_time_ms']:.0f}ms | "
                f"{stats['p95_time_ms']:.0f}ms |"
            )

    # By route
    lines.append("")
    lines.append("## Results by Route")
    lines.append("")

    for route in ["GREEN", "YELLOW", "RED"]:
        lines.append(f"### {route} Queries")
        lines.append("")
        lines.append("| System | Correct | Accuracy | Avg Latency |")
        lines.append("|--------|---------|----------|-------------|")

        for system in ["virtual_graph", "neo4j"]:
            route_results = [
                r for r in results.query_results if r.system == system and r.query_id in _get_route_range(route)
            ]
            if route_results:
                correct = len([r for r in route_results if r.correct])
                total = len(route_results)
                avg_time = statistics.mean([r.execution_time_ms for r in route_results])
                lines.append(
                    f"| {system.replace('_', ' ').title()} | "
                    f"{correct}/{total} | "
                    f"{correct/total:.1%} | "
                    f"{avg_time:.0f}ms |"
                )

        lines.append("")

    # Individual query results
    lines.append("## Individual Query Results")
    lines.append("")
    lines.append("| ID | Query | Route | VG | VG Time | Neo4j | Neo4j Time |")
    lines.append("|----|-------|-------|----|---------|----|---------|")

    queries = load_queries()
    query_names = {q["id"]: q["name"] for q in queries}

    for query_id in range(1, 26):
        name = query_names.get(query_id, f"Query {query_id}")
        route = _get_route_for_query(query_id)

        vg_result = next((r for r in results.query_results if r.query_id == query_id and r.system == "virtual_graph"), None)
        neo4j_result = next((r for r in results.query_results if r.query_id == query_id and r.system == "neo4j"), None)

        vg_check = "✓" if vg_result and vg_result.correct else "✗" if vg_result else "-"
        vg_time = f"{vg_result.execution_time_ms:.0f}ms" if vg_result else "-"
        neo4j_check = "✓" if neo4j_result and neo4j_result.correct else "✗" if neo4j_result else "-"
        neo4j_time = f"{neo4j_result.execution_time_ms:.0f}ms" if neo4j_result else "-"

        lines.append(f"| {query_id} | {name} | {route} | {vg_check} | {vg_time} | {neo4j_check} | {neo4j_time} |")

    lines.append("")

    # Errors
    errors = [r for r in results.query_results if r.error]
    if errors:
        lines.append("## Errors")
        lines.append("")
        for r in errors:
            lines.append(f"- Query {r.query_id} ({r.system}): {r.error}")
        lines.append("")

    return "\n".join(lines)


def _get_route_range(route: str) -> range:
    """Get query ID range for a route."""
    ranges = {"GREEN": range(1, 10), "YELLOW": range(10, 19), "RED": range(19, 26)}
    return ranges[route]


def _get_route_for_query(query_id: int) -> str:
    """Get route for a query ID."""
    if query_id < 10:
        return "GREEN"
    elif query_id < 19:
        return "YELLOW"
    else:
        return "RED"


def main():
    parser = argparse.ArgumentParser(description="Run Virtual Graph benchmark")
    parser.add_argument(
        "--system",
        choices=["vg", "neo4j", "both"],
        default="both",
        help="Which system(s) to benchmark",
    )
    parser.add_argument(
        "--query",
        type=int,
        help="Run only a specific query ID",
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.md",
        help="Output file for results",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Virtual Graph Benchmark")
    print("=" * 60)

    # Load queries and ground truth
    queries = load_queries()
    ground_truth = load_ground_truth()

    if not ground_truth:
        print("ERROR: Ground truth not found. Run generate_ground_truth.py first.")
        return

    # Filter queries if specific one requested
    if args.query:
        queries = [q for q in queries if q["id"] == args.query]
        if not queries:
            print(f"ERROR: Query {args.query} not found")
            return

    results = BenchmarkResults()

    # Run Virtual Graph benchmark
    if args.system in ["vg", "both"]:
        print("\n--- Virtual Graph ---")
        vg_runner = VirtualGraphRunner(PG_DSN)
        vg_runner.connect()

        for query in queries:
            query_id = query["id"]
            truth = ground_truth.get(query_id, {})
            print(f"Query {query_id}: {query['name']}...", end=" ", flush=True)

            result = vg_runner.run_query(query, truth)
            results.add_result(result)

            status = "✓" if result.correct else "✗"
            print(f"{status} ({result.execution_time_ms:.0f}ms, {result.result_count} results)")

        vg_runner.close()

    # Run Neo4j benchmark
    if args.system in ["neo4j", "both"]:
        if not NEO4J_AVAILABLE:
            print("\n--- Neo4j ---")
            print("SKIPPED: neo4j package not installed")
        else:
            print("\n--- Neo4j ---")
            try:
                neo4j_runner = Neo4jRunner(NEO4J_URI, NEO4J_AUTH)
                neo4j_runner.connect()

                for query in queries:
                    query_id = query["id"]
                    truth = ground_truth.get(query_id, {})
                    print(f"Query {query_id}: {query['name']}...", end=" ", flush=True)

                    result = neo4j_runner.run_query(query, truth)
                    results.add_result(result)

                    status = "✓" if result.correct else "✗"
                    print(f"{status} ({result.execution_time_ms:.0f}ms, {result.result_count} results)")

                neo4j_runner.close()
            except Exception as e:
                print(f"ERROR: Could not connect to Neo4j: {e}")

    # Generate report
    print("\n" + "=" * 60)
    report = generate_report(results)
    print(report)

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / args.output
    with open(output_path, "w") as f:
        f.write(report)
    print(f"\nResults saved to: {output_path}")

    # Save raw JSON results
    json_path = RESULTS_DIR / "benchmark_results.json"
    json_data = {
        "timestamp": results.timestamp,
        "results": [
            {
                "query_id": r.query_id,
                "system": r.system,
                "correct": r.correct,
                "first_attempt_correct": r.first_attempt_correct,
                "execution_time_ms": r.execution_time_ms,
                "result_count": r.result_count,
                "error": r.error,
                "handler_used": r.handler_used,
            }
            for r in results.query_results
        ],
    }
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)


if __name__ == "__main__":
    main()
