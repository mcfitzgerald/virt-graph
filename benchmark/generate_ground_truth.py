"""
Generate ground truth for benchmark queries.

Runs queries against PostgreSQL to establish expected results for each
benchmark query. Ground truth is used to validate Virtual Graph and
Neo4j query results.

Usage:
    poetry run python benchmark/generate_ground_truth.py

Requirements:
    - PostgreSQL running with seed data
"""

import json
import os
import time
from pathlib import Path
from typing import Any

import psycopg2
import yaml

# Configuration
PG_DSN = "postgresql://virt_graph:dev_password@localhost:5432/supply_chain"
BENCHMARK_DIR = Path(__file__).parent
GROUND_TRUTH_DIR = BENCHMARK_DIR / "ground_truth"


def get_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(PG_DSN)


def execute_query(conn, query: str) -> list[dict]:
    """Execute query and return results as list of dicts."""
    with conn.cursor() as cur:
        cur.execute(query)
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        return []


def generate_query_1(conn) -> dict:
    """Find supplier Acme Corp."""
    results = execute_query(
        conn,
        """
        SELECT id, supplier_code, name, tier, country
        FROM suppliers
        WHERE name = 'Acme Corp' AND deleted_at IS NULL
        """,
    )
    return {
        "query_id": 1,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_2(conn) -> dict:
    """List all tier 1 suppliers."""
    results = execute_query(
        conn,
        """
        SELECT id, supplier_code, name, tier
        FROM suppliers
        WHERE tier = 1 AND is_active = true AND deleted_at IS NULL
        ORDER BY name
        """,
    )
    return {
        "query_id": 2,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_3(conn) -> dict:
    """Find parts with 'sensor' in description."""
    results = execute_query(
        conn,
        """
        SELECT id, part_number, description, category
        FROM parts
        WHERE LOWER(description) LIKE '%sensor%' AND deleted_at IS NULL
        ORDER BY part_number
        """,
    )
    return {
        "query_id": 3,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_4(conn) -> dict:
    """Parts from Acme Corp."""
    results = execute_query(
        conn,
        """
        SELECT p.id, p.part_number, p.description
        FROM parts p
        JOIN suppliers s ON p.primary_supplier_id = s.id
        WHERE s.name = 'Acme Corp' AND p.deleted_at IS NULL
        ORDER BY p.part_number
        """,
    )
    return {
        "query_id": 4,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_5(conn) -> dict:
    """Facilities in California."""
    results = execute_query(
        conn,
        """
        SELECT id, facility_code, name, city
        FROM facilities
        WHERE state = 'CA' AND is_active = true
        ORDER BY name
        """,
    )
    return {
        "query_id": 5,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_6(conn) -> dict:
    """Certifications for Acme Corp."""
    results = execute_query(
        conn,
        """
        SELECT c.id, c.certification_type, c.expiry_date
        FROM supplier_certifications c
        JOIN suppliers s ON c.supplier_id = s.id
        WHERE s.name = 'Acme Corp' AND c.is_valid = true
        ORDER BY c.expiry_date
        """,
    )
    return {
        "query_id": 6,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_7(conn) -> dict:
    """Products containing part PRT-000001."""
    results = execute_query(
        conn,
        """
        SELECT pr.id, pr.sku, pr.name
        FROM products pr
        JOIN product_components pc ON pr.id = pc.product_id
        JOIN parts p ON pc.part_id = p.id
        WHERE p.part_number = 'PRT-000001'
        ORDER BY pr.name
        """,
    )
    return {
        "query_id": 7,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_8(conn) -> dict:
    """Orders from Chicago Warehouse."""
    results = execute_query(
        conn,
        """
        SELECT o.id, o.order_number, o.status, o.total_amount
        FROM orders o
        JOIN facilities f ON o.shipping_facility_id = f.id
        WHERE f.name = 'Chicago Warehouse' AND o.status != 'cancelled'
        ORDER BY o.order_date DESC
        LIMIT 100
        """,
    )
    return {
        "query_id": 8,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_9(conn) -> dict:
    """Alternate suppliers for part PRT-000001."""
    results = execute_query(
        conn,
        """
        SELECT s.id, s.name, ps.unit_cost, ps.lead_time_days
        FROM suppliers s
        JOIN part_suppliers ps ON s.id = ps.supplier_id
        JOIN parts p ON ps.part_id = p.id
        WHERE p.part_number = 'PRT-000001' AND ps.is_approved = true
        ORDER BY ps.unit_cost
        """,
    )
    return {
        "query_id": 9,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:5],
    }


def generate_query_10(conn) -> dict:
    """Tier 3 suppliers for Acme Corp (recursive)."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE supply_chain AS (
            -- Start with Acme Corp
            SELECT s.id, s.name, s.tier, 0 as depth
            FROM suppliers s
            WHERE s.name = 'Acme Corp' AND s.deleted_at IS NULL

            UNION ALL

            -- Follow supplier relationships upstream
            SELECT sup.id, sup.name, sup.tier, sc.depth + 1
            FROM supply_chain sc
            JOIN supplier_relationships sr ON sr.buyer_id = sc.id
            JOIN suppliers sup ON sr.seller_id = sup.id
            WHERE sup.deleted_at IS NULL AND sc.depth < 10
        )
        SELECT DISTINCT id, name, tier
        FROM supply_chain
        WHERE tier = 3
        ORDER BY name
        """,
    )
    return {
        "query_id": 10,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:10],
    }


def generate_query_11(conn) -> dict:
    """Upstream suppliers of Pacific Components."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE upstream AS (
            SELECT s.id, s.name, s.tier, 0 as distance
            FROM suppliers s
            WHERE s.name = 'Pacific Components' AND s.deleted_at IS NULL

            UNION ALL

            SELECT sup.id, sup.name, sup.tier, u.distance + 1
            FROM upstream u
            JOIN supplier_relationships sr ON sr.buyer_id = u.id
            JOIN suppliers sup ON sr.seller_id = sup.id
            WHERE sup.deleted_at IS NULL AND u.distance < 10
        )
        SELECT DISTINCT id, name, tier, MIN(distance) as distance
        FROM upstream
        WHERE distance > 0
        GROUP BY id, name, tier
        ORDER BY distance, name
        """,
    )
    return {
        "query_id": 11,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:10],
    }


def generate_query_12(conn) -> dict:
    """Downstream customers of Eastern Electronics."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE downstream AS (
            SELECT s.id, s.name, s.tier, 0 as distance
            FROM suppliers s
            WHERE s.name = 'Eastern Electronics' AND s.deleted_at IS NULL

            UNION ALL

            SELECT sup.id, sup.name, sup.tier, d.distance + 1
            FROM downstream d
            JOIN supplier_relationships sr ON sr.seller_id = d.id
            JOIN suppliers sup ON sr.buyer_id = sup.id
            WHERE sup.deleted_at IS NULL AND d.distance < 10
        )
        SELECT DISTINCT id, name, tier, MIN(distance) as distance
        FROM downstream
        WHERE distance > 0
        GROUP BY id, name, tier
        ORDER BY distance, name
        """,
    )
    return {
        "query_id": 12,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:10],
    }


def generate_query_13(conn) -> dict:
    """BOM explosion for Turbo Encabulator."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE bom AS (
            -- Top-level parts from product
            SELECT p.id, p.part_number, p.description, 0 as depth
            FROM products prod
            JOIN product_components pc ON prod.id = pc.product_id
            JOIN parts p ON pc.part_id = p.id
            WHERE prod.name = 'Turbo Encabulator' AND p.deleted_at IS NULL

            UNION ALL

            -- Recursive components
            SELECT child.id, child.part_number, child.description, b.depth + 1
            FROM bom b
            JOIN bill_of_materials bm ON bm.parent_part_id = b.id
            JOIN parts child ON bm.child_part_id = child.id
            WHERE child.deleted_at IS NULL AND b.depth < 20
        )
        SELECT DISTINCT id, part_number, description, MIN(depth) as depth
        FROM bom
        GROUP BY id, part_number, description
        ORDER BY depth, part_number
        """,
    )
    return {
        "query_id": 13,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "expected_depth": max([r["depth"] for r in results]) if results else 0,
        "sample_results": results[:10],
    }


def generate_query_14(conn) -> dict:
    """Where is part PRT-000100 used?"""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE where_used AS (
            SELECT p.id, p.part_number, p.description, 0 as depth
            FROM parts p
            WHERE p.part_number = 'PRT-000100' AND p.deleted_at IS NULL

            UNION ALL

            SELECT parent.id, parent.part_number, parent.description, w.depth + 1
            FROM where_used w
            JOIN bill_of_materials bm ON bm.child_part_id = w.id
            JOIN parts parent ON bm.parent_part_id = parent.id
            WHERE parent.deleted_at IS NULL AND w.depth < 20
        )
        SELECT DISTINCT id, part_number, description, MIN(depth) as depth
        FROM where_used
        WHERE depth > 0
        GROUP BY id, part_number, description
        ORDER BY depth, part_number
        """,
    )
    return {
        "query_id": 14,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:10],
    }


def generate_query_15(conn) -> dict:
    """Products affected if Acme Corp fails (impact analysis)."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE affected_parts AS (
            -- Parts directly from Acme Corp
            SELECT p.id
            FROM parts p
            JOIN suppliers s ON p.primary_supplier_id = s.id
            WHERE s.name = 'Acme Corp' AND p.deleted_at IS NULL

            UNION

            -- Parts that use affected parts
            SELECT bm.parent_part_id
            FROM affected_parts ap
            JOIN bill_of_materials bm ON bm.child_part_id = ap.id
        )
        SELECT DISTINCT prod.id, prod.sku, prod.name
        FROM products prod
        JOIN product_components pc ON prod.id = pc.product_id
        WHERE pc.part_id IN (SELECT id FROM affected_parts)
        ORDER BY prod.name
        """,
    )
    return {
        "query_id": 15,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:10],
    }


def generate_query_16(conn) -> dict:
    """Supply chain depth from GlobalTech Industries."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE supply_chain AS (
            SELECT s.id, s.name, s.tier, 0 as chain_depth
            FROM suppliers s
            WHERE s.name = 'GlobalTech Industries' AND s.deleted_at IS NULL

            UNION ALL

            SELECT sup.id, sup.name, sup.tier, sc.chain_depth + 1
            FROM supply_chain sc
            JOIN supplier_relationships sr ON sr.buyer_id = sc.id
            JOIN suppliers sup ON sr.seller_id = sup.id
            WHERE sup.deleted_at IS NULL AND sc.chain_depth < 10
        )
        SELECT DISTINCT id, name, tier, MAX(chain_depth) as chain_depth
        FROM supply_chain
        WHERE chain_depth > 0
        GROUP BY id, name, tier
        ORDER BY chain_depth DESC, name
        """,
    )
    return {
        "query_id": 16,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "max_depth": max([r["chain_depth"] for r in results]) if results else 0,
        "sample_results": results[:10],
    }


def generate_query_17(conn) -> dict:
    """Leaf parts (raw materials) in Turbo Encabulator."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE bom AS (
            SELECT p.id, p.part_number, p.description
            FROM products prod
            JOIN product_components pc ON prod.id = pc.product_id
            JOIN parts p ON pc.part_id = p.id
            WHERE prod.name = 'Turbo Encabulator' AND p.deleted_at IS NULL

            UNION ALL

            SELECT child.id, child.part_number, child.description
            FROM bom b
            JOIN bill_of_materials bm ON bm.parent_part_id = b.id
            JOIN parts child ON bm.child_part_id = child.id
            WHERE child.deleted_at IS NULL
        )
        SELECT DISTINCT b.id, b.part_number, b.description
        FROM bom b
        WHERE NOT EXISTS (
            SELECT 1 FROM bill_of_materials bm
            WHERE bm.parent_part_id = b.id
        )
        ORDER BY b.part_number
        """,
    )
    return {
        "query_id": 17,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:10],
    }


def generate_query_18(conn) -> dict:
    """Common suppliers between Turbo Encabulator and Flux Capacitor."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE
        bom1 AS (
            SELECT p.id
            FROM products prod
            JOIN product_components pc ON prod.id = pc.product_id
            JOIN parts p ON pc.part_id = p.id
            WHERE prod.name = 'Turbo Encabulator'

            UNION ALL

            SELECT child.id
            FROM bom1 b
            JOIN bill_of_materials bm ON bm.parent_part_id = b.id
            JOIN parts child ON bm.child_part_id = child.id
        ),
        bom2 AS (
            SELECT p.id
            FROM products prod
            JOIN product_components pc ON prod.id = pc.product_id
            JOIN parts p ON pc.part_id = p.id
            WHERE prod.name = 'Flux Capacitor'

            UNION ALL

            SELECT child.id
            FROM bom2 b
            JOIN bill_of_materials bm ON bm.parent_part_id = b.id
            JOIN parts child ON bm.child_part_id = child.id
        )
        SELECT DISTINCT s.id, s.name, s.tier
        FROM suppliers s
        JOIN parts p1 ON p1.primary_supplier_id = s.id
        JOIN parts p2 ON p2.primary_supplier_id = s.id
        WHERE p1.id IN (SELECT id FROM bom1)
          AND p2.id IN (SELECT id FROM bom2)
          AND s.deleted_at IS NULL
        ORDER BY s.name
        """,
    )
    return {
        "query_id": 18,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:10],
    }


def generate_query_19_21(conn, facility_from: str, facility_to: str, weight_col: str) -> dict:
    """Generic shortest path query."""
    # Get facility IDs
    facilities = execute_query(
        conn,
        f"""
        SELECT id, name FROM facilities
        WHERE name IN ('{facility_from}', '{facility_to}')
        """,
    )
    facility_lookup = {f["name"]: f["id"] for f in facilities}

    if facility_from not in facility_lookup or facility_to not in facility_lookup:
        return {
            "error": f"Facility not found: {facility_from} or {facility_to}",
            "expected_count": 0,
        }

    # Simple BFS to find path (PostgreSQL doesn't have native Dijkstra)
    # For ground truth, we use a simplified approach
    start_id = facility_lookup[facility_from]
    end_id = facility_lookup[facility_to]

    results = execute_query(
        conn,
        f"""
        WITH RECURSIVE paths AS (
            SELECT
                origin_facility_id as current,
                destination_facility_id as next,
                CAST({weight_col} AS NUMERIC) as total_weight,
                ARRAY[origin_facility_id, destination_facility_id] as path
            FROM transport_routes
            WHERE origin_facility_id = {start_id} AND is_active = true

            UNION ALL

            SELECT
                p.next,
                tr.destination_facility_id,
                p.total_weight + CAST(tr.{weight_col} AS NUMERIC),
                p.path || tr.destination_facility_id
            FROM paths p
            JOIN transport_routes tr ON tr.origin_facility_id = p.next
            WHERE NOT (tr.destination_facility_id = ANY(p.path))
              AND tr.is_active = true
              AND array_length(p.path, 1) < 10
        )
        SELECT path, total_weight
        FROM paths
        WHERE next = {end_id}
        ORDER BY total_weight
        LIMIT 1
        """,
    )

    if results:
        path = results[0]["path"]
        return {
            "expected_path": path,
            "expected_distance": float(results[0]["total_weight"]),
            "expected_count": 1,
            "path_length": len(path),
        }
    return {
        "expected_path": None,
        "expected_distance": None,
        "expected_count": 0,
        "error": "No path found",
    }


def generate_query_22(conn) -> dict:
    """Critical facility by connections (simplified betweenness)."""
    results = execute_query(
        conn,
        """
        SELECT
            f.id,
            f.name,
            f.facility_type,
            COUNT(DISTINCT tr_out.id) as outbound,
            COUNT(DISTINCT tr_in.id) as inbound,
            COUNT(DISTINCT tr_out.id) + COUNT(DISTINCT tr_in.id) as total_connections
        FROM facilities f
        LEFT JOIN transport_routes tr_out ON tr_out.origin_facility_id = f.id AND tr_out.is_active = true
        LEFT JOIN transport_routes tr_in ON tr_in.destination_facility_id = f.id AND tr_in.is_active = true
        WHERE f.is_active = true
        GROUP BY f.id, f.name, f.facility_type
        ORDER BY total_connections DESC
        LIMIT 10
        """,
    )
    return {
        "query_id": 22,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "rankings": [{"id": r["id"], "name": r["name"], "score": r["total_connections"]} for r in results],
    }


def generate_query_23(conn) -> dict:
    """Most connected supplier by degree."""
    results = execute_query(
        conn,
        """
        SELECT
            s.id,
            s.name,
            s.tier,
            COUNT(DISTINCT sr_out.id) as supplies_to,
            COUNT(DISTINCT sr_in.id) as supplied_by,
            COUNT(DISTINCT p.id) as parts_provided,
            COUNT(DISTINCT sr_out.id) + COUNT(DISTINCT sr_in.id) + COUNT(DISTINCT p.id) as total_degree
        FROM suppliers s
        LEFT JOIN supplier_relationships sr_out ON sr_out.seller_id = s.id
        LEFT JOIN supplier_relationships sr_in ON sr_in.buyer_id = s.id
        LEFT JOIN parts p ON p.primary_supplier_id = s.id AND p.deleted_at IS NULL
        WHERE s.is_active = true AND s.deleted_at IS NULL
        GROUP BY s.id, s.name, s.tier
        ORDER BY total_degree DESC
        LIMIT 10
        """,
    )
    return {
        "query_id": 23,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "rankings": [{"id": r["id"], "name": r["name"], "tier": r["tier"], "degree": r["total_degree"]} for r in results],
    }


def generate_query_24(conn) -> dict:
    """Isolated or weakly connected facilities."""
    results = execute_query(
        conn,
        """
        SELECT
            f.id,
            f.name,
            f.facility_type,
            f.city,
            f.state,
            COUNT(DISTINCT tr_out.id) as outbound,
            COUNT(DISTINCT tr_in.id) as inbound
        FROM facilities f
        LEFT JOIN transport_routes tr_out ON tr_out.origin_facility_id = f.id AND tr_out.is_active = true
        LEFT JOIN transport_routes tr_in ON tr_in.destination_facility_id = f.id AND tr_in.is_active = true
        WHERE f.is_active = true
        GROUP BY f.id, f.name, f.facility_type, f.city, f.state
        HAVING COUNT(DISTINCT tr_out.id) + COUNT(DISTINCT tr_in.id) < 3
        ORDER BY COUNT(DISTINCT tr_out.id) + COUNT(DISTINCT tr_in.id)
        """,
    )
    return {
        "query_id": 24,
        "expected_count": len(results),
        "expected_node_ids": [r["id"] for r in results],
        "sample_results": results[:10],
    }


def generate_query_25(conn) -> dict:
    """All routes between Chicago and LA."""
    results = execute_query(
        conn,
        """
        WITH RECURSIVE paths AS (
            SELECT
                tr.origin_facility_id as start_id,
                tr.destination_facility_id as current_id,
                CAST(tr.cost_usd AS NUMERIC) as total_cost,
                CAST(tr.transit_time_hours AS NUMERIC) as total_time,
                ARRAY[tr.origin_facility_id, tr.destination_facility_id] as path
            FROM transport_routes tr
            JOIN facilities f ON tr.origin_facility_id = f.id
            WHERE f.name = 'Chicago Warehouse' AND tr.is_active = true

            UNION ALL

            SELECT
                p.start_id,
                tr.destination_facility_id,
                p.total_cost + CAST(tr.cost_usd AS NUMERIC),
                p.total_time + CAST(tr.transit_time_hours AS NUMERIC),
                p.path || tr.destination_facility_id
            FROM paths p
            JOIN transport_routes tr ON tr.origin_facility_id = p.current_id
            WHERE NOT (tr.destination_facility_id = ANY(p.path))
              AND tr.is_active = true
              AND array_length(p.path, 1) < 6
        )
        SELECT
            path,
            array_length(path, 1) - 1 as hops,
            total_cost,
            total_time
        FROM paths p
        JOIN facilities f ON p.current_id = f.id
        WHERE f.name = 'LA Distribution Center'
        ORDER BY array_length(path, 1), total_cost
        LIMIT 10
        """,
    )

    return {
        "query_id": 25,
        "expected_count": len(results),
        "routes": [
            {
                "path": r["path"],
                "hops": r["hops"],
                "cost": float(r["total_cost"]) if r["total_cost"] else None,
                "time": float(r["total_time"]) if r["total_time"] else None,
            }
            for r in results
        ],
    }


def serialize_for_json(obj: Any) -> Any:
    """Convert non-JSON-serializable types."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__float__"):
        return float(obj)
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    return obj


def main():
    """Generate ground truth for all queries."""
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()

    print("Generating ground truth for benchmark queries...")
    print("=" * 60)

    all_results = {}

    # GREEN queries (1-9)
    generators = [
        (1, generate_query_1),
        (2, generate_query_2),
        (3, generate_query_3),
        (4, generate_query_4),
        (5, generate_query_5),
        (6, generate_query_6),
        (7, generate_query_7),
        (8, generate_query_8),
        (9, generate_query_9),
    ]

    for query_id, generator in generators:
        print(f"Query {query_id}...", end=" ")
        start = time.time()
        result = generator(conn)
        elapsed = (time.time() - start) * 1000
        print(f"found {result.get('expected_count', 0)} results ({elapsed:.1f}ms)")
        result["generation_time_ms"] = elapsed
        all_results[query_id] = result

    # YELLOW queries (10-18)
    yellow_generators = [
        (10, generate_query_10),
        (11, generate_query_11),
        (12, generate_query_12),
        (13, generate_query_13),
        (14, generate_query_14),
        (15, generate_query_15),
        (16, generate_query_16),
        (17, generate_query_17),
        (18, generate_query_18),
    ]

    for query_id, generator in yellow_generators:
        print(f"Query {query_id}...", end=" ")
        start = time.time()
        result = generator(conn)
        elapsed = (time.time() - start) * 1000
        print(f"found {result.get('expected_count', 0)} results ({elapsed:.1f}ms)")
        result["generation_time_ms"] = elapsed
        all_results[query_id] = result

    # RED queries (19-25)
    print("Query 19 (cheapest route)...", end=" ")
    start = time.time()
    result = generate_query_19_21(conn, "Chicago Warehouse", "LA Distribution Center", "cost_usd")
    result["query_id"] = 19
    elapsed = (time.time() - start) * 1000
    print(f"path length {result.get('path_length', 'N/A')} ({elapsed:.1f}ms)")
    result["generation_time_ms"] = elapsed
    all_results[19] = result

    print("Query 20 (fastest route)...", end=" ")
    start = time.time()
    result = generate_query_19_21(conn, "Chicago Warehouse", "LA Distribution Center", "transit_time_hours")
    result["query_id"] = 20
    elapsed = (time.time() - start) * 1000
    print(f"path length {result.get('path_length', 'N/A')} ({elapsed:.1f}ms)")
    result["generation_time_ms"] = elapsed
    all_results[20] = result

    print("Query 21 (shortest distance)...", end=" ")
    start = time.time()
    result = generate_query_19_21(conn, "New York Factory", "LA Distribution Center", "distance_km")
    result["query_id"] = 21
    elapsed = (time.time() - start) * 1000
    print(f"path length {result.get('path_length', 'N/A')} ({elapsed:.1f}ms)")
    result["generation_time_ms"] = elapsed
    all_results[21] = result

    other_red = [
        (22, generate_query_22),
        (23, generate_query_23),
        (24, generate_query_24),
        (25, generate_query_25),
    ]

    for query_id, generator in other_red:
        print(f"Query {query_id}...", end=" ")
        start = time.time()
        result = generator(conn)
        elapsed = (time.time() - start) * 1000
        print(f"found {result.get('expected_count', 0)} results ({elapsed:.1f}ms)")
        result["generation_time_ms"] = elapsed
        all_results[query_id] = result

    conn.close()

    # Write individual files
    for query_id, result in all_results.items():
        filepath = GROUND_TRUTH_DIR / f"query_{query_id:02d}.json"
        with open(filepath, "w") as f:
            json.dump(serialize_for_json(result), f, indent=2)

    # Write combined file
    combined_path = GROUND_TRUTH_DIR / "all_ground_truth.json"
    with open(combined_path, "w") as f:
        json.dump(serialize_for_json(all_results), f, indent=2)

    print("=" * 60)
    print(f"Ground truth generated for {len(all_results)} queries")
    print(f"Output: {GROUND_TRUTH_DIR}")


if __name__ == "__main__":
    main()
