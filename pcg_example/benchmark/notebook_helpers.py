"""
Shared helpers for PCG benchmark notebooks.

Provides reusable functions for database access, transport network graph
construction, multi-level BOM explosion, and display formatting.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

import networkx as nx
import pandas as pd
import psycopg

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from virt_graph.db import get_connection as _get_connection
from virt_graph.ontology import OntologyAccessor


def get_session():
    """Return (conn, ontology) for notebook use.

    The connection stays open — call conn.close() at end of notebook.
    """
    ontology = OntologyAccessor(
        _PROJECT_ROOT / "pcg_example" / "ontology" / "pcg.yaml"
    )
    conn = _get_connection()
    return conn, ontology


def run_sql(conn, sql, params=None):
    """Execute SQL and return a pandas DataFrame."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return pd.DataFrame()
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        # Convert Decimal to float for numeric display
        for col in df.columns:
            if df[col].dtype == object and len(df) > 0 and isinstance(df[col].iloc[0], Decimal):
                df[col] = df[col].astype(float)
        return df


# ---------------------------------------------------------------------------
# Transport network helpers
# ---------------------------------------------------------------------------

def build_transport_graph(conn):
    """Build NetworkX DiGraph from route_segments with composite 'type:id' node keys.

    Stores distance_km and transit_time_hours as edge attributes.
    Returns the graph.
    """
    G = nx.DiGraph()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT origin_type, origin_id, destination_type, destination_id,
                   distance_km, transit_time_hours, segment_code
            FROM route_segments
        """)
        for row in cur.fetchall():
            src = f"{row[0]}:{row[1]}"
            dst = f"{row[2]}:{row[3]}"
            dist = float(row[4]) if row[4] is not None else 99999.0
            time = float(row[5]) if row[5] is not None else 99999.0
            G.add_edge(
                src, dst,
                distance_km=dist,
                transit_time_hours=time,
                segment_code=row[6],
            )
    return G


def _build_location_cache(conn):
    """Build a dict mapping location codes to composite graph keys."""
    cache = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, plant_code FROM plants")
        for row in cur.fetchall():
            cache[row[1]] = f"plant:{row[0]}"

        cur.execute("SELECT id, dc_code, type FROM distribution_centers")
        for row in cur.fetchall():
            cache[row[1]] = f"{row[2]}:{row[0]}"

        cur.execute("SELECT id, location_code FROM retail_locations")
        for row in cur.fetchall():
            cache[row[1]] = f"store:{row[0]}"

        cur.execute("SELECT id, supplier_code FROM suppliers")
        for row in cur.fetchall():
            cache[row[1]] = f"supplier:{row[0]}"
    return cache


_LOCATION_CACHE = None


def resolve_location_key(conn, code):
    """Map a location code (e.g. 'PLANT-TX', 'RDC-MW', 'STORE-RET-001-0042') to a composite graph key."""
    global _LOCATION_CACHE
    if _LOCATION_CACHE is None:
        _LOCATION_CACHE = _build_location_cache(conn)
    return _LOCATION_CACHE.get(code)


def display_path(G, path, weight_col="distance_km"):
    """Pretty-print a network path with hop details and cumulative weight."""
    rows = []
    cumulative = 0.0
    for i, node in enumerate(path):
        hop_weight = 0.0
        if i > 0:
            try:
                edge = G[path[i - 1]][node]
                hop_weight = edge.get(weight_col, 0) or 0
            except KeyError:
                hop_weight = 0
            cumulative += hop_weight
        rows.append({
            "hop": i,
            "node": node,
            f"hop_{weight_col}": round(hop_weight, 2) if i > 0 else "",
            f"cumulative_{weight_col}": round(cumulative, 2),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# BOM explosion helpers
# ---------------------------------------------------------------------------

def explode_bom(conn, sku_code=None, formula_id=None, resolve_costs=False):
    """Multi-level BOM explosion handling polymorphic ingredient_id.

    Provide either sku_code (e.g. 'SKU-ORAL-001') or formula_id.

    Returns a list of dicts, one per leaf raw ingredient, with:
      - ingredient_id, ingredient_code, ingredient_name
      - cumulative_quantity_kg (product of quantities along the path)
      - bom_path: list of intermediate names from SKU to raw ingredient
      - level: depth in BOM tree
      - (if resolve_costs) cheapest_unit_cost, cheapest_supplier
    """
    with conn.cursor() as cur:
        if sku_code and not formula_id:
            cur.execute("""
                SELECT f.id FROM formulas f
                JOIN skus s ON f.product_id = s.id AND f.bom_level = 0
                WHERE s.sku_code = %s
            """, (sku_code,))
            row = cur.fetchone()
            if not row:
                return []
            formula_id = row[0]

    results = []
    _explode_recursive(conn, formula_id, 1.0, [], results, 0)

    if resolve_costs:
        _attach_costs(conn, results)

    return results


def _explode_recursive(conn, formula_id, parent_qty, path, results, depth):
    """Recursively explode a formula, resolving polymorphic ingredient_id."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fi.ingredient_id, fi.quantity_kg, fi.sequence,
                   i.id as raw_id, i.ingredient_code, i.name as raw_name,
                   bi.id as bulk_id, bi.bulk_code, bi.name as bulk_name, bi.bom_level as bi_level
            FROM formula_ingredients fi
            LEFT JOIN ingredients i ON fi.ingredient_id = i.id
            LEFT JOIN bulk_intermediates bi ON fi.ingredient_id = bi.id
            WHERE fi.formula_id = %s
            ORDER BY fi.sequence
        """, (formula_id,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    for row in rows:
        r = dict(zip(cols, row))
        qty = float(r["quantity_kg"]) * parent_qty

        if r["bulk_id"] is not None:
            # This ingredient is a bulk intermediate — find its formula and recurse
            new_path = path + [r["bulk_name"] or r["bulk_code"]]
            with conn.cursor() as cur2:
                # Find the formula for this bulk intermediate
                bom_level = r["bi_level"]
                cur2.execute("""
                    SELECT id FROM formulas
                    WHERE product_id = %s AND bom_level = %s
                """, (r["bulk_id"], bom_level))
                sub_formula = cur2.fetchone()
            if sub_formula:
                _explode_recursive(conn, sub_formula[0], qty, new_path, results, depth + 1)
            else:
                # No formula found — treat as leaf
                results.append({
                    "ingredient_id": r["ingredient_id"],
                    "ingredient_code": r["bulk_code"],
                    "ingredient_name": r["bulk_name"],
                    "cumulative_quantity_kg": qty,
                    "bom_path": new_path,
                    "level": depth + 1,
                    "is_intermediate": True,
                })
        else:
            # Raw ingredient
            results.append({
                "ingredient_id": r["ingredient_id"],
                "ingredient_code": r["ingredient_code"],
                "ingredient_name": r["raw_name"],
                "cumulative_quantity_kg": qty,
                "bom_path": path + [r["raw_name"] or r["ingredient_code"]],
                "level": depth + 1,
                "is_intermediate": False,
            })


def _attach_costs(conn, results):
    """Attach cheapest supplier cost to each raw ingredient in BOM results."""
    ingredient_ids = list({r["ingredient_id"] for r in results if not r.get("is_intermediate")})
    if not ingredient_ids:
        return

    with conn.cursor() as cur:
        placeholders = ",".join(["%s"] * len(ingredient_ids))
        cur.execute(f"""
            SELECT DISTINCT ON (si.ingredient_id)
                   si.ingredient_id, si.unit_cost, s.name as supplier_name, s.supplier_code
            FROM supplier_ingredients si
            JOIN suppliers s ON si.supplier_id = s.id
            WHERE si.ingredient_id IN ({placeholders})
            ORDER BY si.ingredient_id, si.unit_cost ASC
        """, ingredient_ids)
        cost_map = {}
        for row in cur.fetchall():
            cost_map[row[0]] = {
                "cheapest_unit_cost": float(row[1]),
                "cheapest_supplier": row[2],
                "cheapest_supplier_code": row[3],
            }

    for r in results:
        cost = cost_map.get(r["ingredient_id"], {})
        r["cheapest_unit_cost"] = cost.get("cheapest_unit_cost")
        r["cheapest_supplier"] = cost.get("cheapest_supplier")
        r["cheapest_supplier_code"] = cost.get("cheapest_supplier_code")


def display_bom_tree(bom_results):
    """Return a DataFrame showing the BOM explosion tree."""
    rows = []
    for r in bom_results:
        indent = "  " * r["level"]
        rows.append({
            "level": r["level"],
            "component": f"{indent}{r['ingredient_code']}",
            "name": r["ingredient_name"],
            "quantity_kg": round(r["cumulative_quantity_kg"], 6),
            "is_intermediate": r.get("is_intermediate", False),
        })
    return pd.DataFrame(rows)


def bom_to_df(bom_results):
    """Convert BOM explosion results to a flat DataFrame."""
    return pd.DataFrame(bom_results)
