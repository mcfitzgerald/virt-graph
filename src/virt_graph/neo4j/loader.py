"""
Neo4j data loader — ontology-driven.

Reads a VG ontology and PostgreSQL source database, loads data into Neo4j.
Generic — works with any VG ontology, not hardcoded to a specific domain.

Handles:
- Composite primary keys (multi-property node key)
- Polymorphic relationships (type discriminator → label routing)
- Edge attributes (relationship properties)
- Batch UNWIND for performance (configurable batch size)

Usage:
    from virt_graph.neo4j.loader import load_data
    from virt_graph.ontology import OntologyAccessor

    ontology = OntologyAccessor(Path("ontology.yaml"))
    load_data(ontology, pg_conn, neo4j_driver)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from virt_graph.ontology import OntologyAccessor

from .schema import get_label_for_class, get_rel_type_for_role


BATCH_SIZE = 2000


@dataclass
class MigrationMetrics:
    """Track migration metrics."""

    start_time: float = 0
    end_time: float = 0
    nodes_created: dict[str, int] = field(default_factory=dict)
    relationships_created: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    @property
    def total_nodes(self) -> int:
        return sum(self.nodes_created.values())

    @property
    def total_relationships(self) -> int:
        return sum(self.relationships_created.values())


def _convert_value(value: Any) -> Any:
    """Convert Python/PostgreSQL types to Neo4j-compatible types."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):  # datetime, date
        return str(value)
    return value


def _get_table_columns(pg_conn, table: str) -> list[str]:
    """Get column names for a table from PostgreSQL."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return [row[0] for row in cur.fetchall()]


def _fetch_table_data(pg_conn, table: str, columns: list[str], where: str | None = None) -> list[tuple]:
    """Fetch all rows from a table."""
    col_list = ", ".join(columns)
    query = f"SELECT {col_list} FROM {table}"  # noqa: S608
    if where:
        query += f" WHERE {where}"
    with pg_conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def load_nodes(
    ontology: OntologyAccessor,
    pg_conn,
    neo4j_driver,
    metrics: MigrationMetrics,
    batch_size: int = BATCH_SIZE,
) -> None:
    """Load all entity classes as Neo4j nodes."""
    for cls_name, cls_info in ontology.classes.items():
        table = cls_info["table"]
        label = get_label_for_class(cls_name)

        # Get columns
        columns = _get_table_columns(pg_conn, table)
        if not columns:
            metrics.warnings.append(f"No columns found for table {table}")
            continue

        # Check for soft delete
        soft_delete = cls_info.get("soft_delete_column")
        where = f"{soft_delete} IS NULL" if soft_delete else None

        # Fetch data
        rows = _fetch_table_data(pg_conn, table, columns, where)

        # Build property map template
        # Filter out None values at insert time
        prop_keys = columns

        # Insert in batches using UNWIND
        with neo4j_driver.session() as session:
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]

                # Build batch data
                batch_data = []
                for row in batch:
                    props = {}
                    for j, col in enumerate(prop_keys):
                        val = _convert_value(row[j])
                        if val is not None:
                            props[col] = val
                    batch_data.append(props)

                # Use UNWIND for batch insert
                # We use SET n += props to handle variable property sets
                session.run(
                    f"UNWIND $batch AS props CREATE (n:{label}) SET n += props",
                    batch=batch_data,
                )

        count = len(rows)
        metrics.nodes_created[label] = count
        print(f"  {label}: {count:,} nodes from {table}")


def load_relationships(
    ontology: OntologyAccessor,
    pg_conn,
    neo4j_driver,
    metrics: MigrationMetrics,
    batch_size: int = BATCH_SIZE,
) -> None:
    """Load all relationship classes as Neo4j relationships."""
    for role_name, role_info in ontology.roles.items():
        edge_table = role_info["edge_table"]
        domain_keys = role_info["domain_key"]
        range_keys = role_info["range_key"]
        rel_type = get_rel_type_for_role(role_name)

        # Get domain/range info
        domain_classes = role_info.get("domain_class", [])
        range_classes = role_info.get("range_class", [])
        if isinstance(domain_classes, str):
            domain_classes = [domain_classes]
        if isinstance(range_classes, str):
            range_classes = [range_classes]

        # Check for polymorphic relationship
        is_polymorphic = ontology.is_role_polymorphic(role_name)
        type_disc = None
        if is_polymorphic:
            type_disc = ontology.get_role_type_discriminator(role_name)

        # Get edge attributes (Property Graph style)
        edge_attrs = ontology.get_role_edge_attributes(role_name)
        edge_attr_names = [a["name"] for a in edge_attrs] if edge_attrs else []

        # Determine if FK or junction table relationship
        domain_table = None
        if domain_classes:
            try:
                domain_table = ontology.get_class_table(domain_classes[0])
            except KeyError:
                pass

        domain_pk = ["id"]
        if domain_classes:
            try:
                domain_pk = ontology.get_class_pk(domain_classes[0])
            except KeyError:
                pass

        range_pk = ["id"]
        if range_classes:
            try:
                range_pk = ontology.get_class_pk(range_classes[0])
            except KeyError:
                pass

        if edge_table == domain_table:
            # FK relationship: edge_table IS the domain entity table
            count = _load_fk_relationship(
                pg_conn,
                neo4j_driver,
                role_name,
                rel_type,
                edge_table,
                domain_keys,
                range_keys,
                domain_classes,
                range_classes,
                domain_pk,
                range_pk,
                is_polymorphic,
                type_disc,
                batch_size,
                metrics,
            )
        else:
            # Junction table relationship
            count = _load_junction_relationship(
                pg_conn,
                neo4j_driver,
                role_name,
                rel_type,
                edge_table,
                domain_keys,
                range_keys,
                domain_classes,
                range_classes,
                domain_pk,
                range_pk,
                edge_attr_names,
                is_polymorphic,
                type_disc,
                batch_size,
                metrics,
            )

        metrics.relationships_created[rel_type] = metrics.relationships_created.get(rel_type, 0) + count
        print(f"  {rel_type}: {count:,} relationships")


def _load_fk_relationship(
    pg_conn,
    neo4j_driver,
    role_name: str,
    rel_type: str,
    edge_table: str,
    domain_keys: list[str],
    range_keys: list[str],
    domain_classes: list[str],
    range_classes: list[str],
    domain_pk: list[str],
    range_pk: list[str],
    is_polymorphic: bool,
    type_disc: dict | None,
    batch_size: int,
    metrics: MigrationMetrics,
) -> int:
    """Load FK-based relationships using MATCH on existing nodes."""
    # For FK relationships, domain_key is typically "id" (the node's own PK)
    # and range_key is the FK column pointing to the target
    domain_label = get_label_for_class(domain_classes[0]) if domain_classes else "Unknown"

    # Build columns to fetch: domain PK + range FK + discriminator (if polymorphic)
    fetch_cols = list(domain_pk)
    for rk in range_keys:
        if rk not in fetch_cols:
            fetch_cols.append(rk)
    disc_col = None
    if is_polymorphic and type_disc and "column" in type_disc:
        disc_col = type_disc["column"]
        if disc_col not in fetch_cols:
            fetch_cols.append(disc_col)

    # Fetch FK data
    rows = _fetch_table_data(pg_conn, edge_table, fetch_cols)

    if is_polymorphic and type_disc and "mapping" in type_disc:
        # Group rows by target type
        mapping = type_disc["mapping"]
        by_type: dict[str, list] = {}
        for row in rows:
            row_dict = dict(zip(fetch_cols, row))
            # Get the FK value
            fk_val = row_dict.get(range_keys[0])
            if fk_val is None:
                continue
            # Get discriminator value
            disc_val = str(row_dict.get(disc_col, "")).lower() if disc_col else None
            target_class = mapping.get(disc_val) if disc_val else None
            if target_class is None:
                continue
            by_type.setdefault(target_class, []).append(row_dict)

        total = 0
        for target_class, typed_rows in by_type.items():
            range_label = get_label_for_class(target_class)
            count = _create_fk_rels_batch(
                neo4j_driver,
                rel_type,
                domain_label,
                domain_pk,
                range_label,
                range_pk,
                range_keys,
                typed_rows,
                batch_size,
            )
            total += count
        return total
    else:
        # Non-polymorphic
        range_label = get_label_for_class(range_classes[0]) if range_classes else "Unknown"
        row_dicts = [dict(zip(fetch_cols, row)) for row in rows if dict(zip(fetch_cols, row)).get(range_keys[0]) is not None]
        return _create_fk_rels_batch(
            neo4j_driver,
            rel_type,
            domain_label,
            domain_pk,
            range_label,
            range_pk,
            range_keys,
            row_dicts,
            batch_size,
        )


def _create_fk_rels_batch(
    neo4j_driver,
    rel_type: str,
    domain_label: str,
    domain_pk: list[str],
    range_label: str,
    range_pk: list[str],
    range_keys: list[str],
    row_dicts: list[dict],
    batch_size: int,
) -> int:
    """Create FK-based relationships in batches using UNWIND."""
    if not row_dicts:
        return 0

    # Build MATCH clauses
    d_pk = domain_pk[0]
    r_pk = range_pk[0]
    r_fk = range_keys[0]

    total = 0
    with neo4j_driver.session() as session:
        for i in range(0, len(row_dicts), batch_size):
            batch = row_dicts[i : i + batch_size]
            batch_data = [
                {"d_id": _convert_value(rd[d_pk]), "r_id": _convert_value(rd[r_fk])}
                for rd in batch
                if rd.get(r_fk) is not None
            ]
            if not batch_data:
                continue
            session.run(
                f"UNWIND $batch AS row "
                f"MATCH (d:{domain_label} {{{d_pk}: row.d_id}}) "
                f"MATCH (r:{range_label} {{{r_pk}: row.r_id}}) "
                f"CREATE (d)-[:{rel_type}]->(r)",
                batch=batch_data,
            )
            total += len(batch_data)
    return total


def _load_junction_relationship(
    pg_conn,
    neo4j_driver,
    role_name: str,
    rel_type: str,
    edge_table: str,
    domain_keys: list[str],
    range_keys: list[str],
    domain_classes: list[str],
    range_classes: list[str],
    domain_pk: list[str],
    range_pk: list[str],
    edge_attr_names: list[str],
    is_polymorphic: bool,
    type_disc: dict | None,
    batch_size: int,
    metrics: MigrationMetrics,
) -> int:
    """Load junction table relationships with edge properties."""
    domain_label = get_label_for_class(domain_classes[0]) if domain_classes else "Unknown"

    # Columns to fetch from junction table
    fetch_cols = list(domain_keys) + list(range_keys) + edge_attr_names
    # Deduplicate while preserving order
    seen = set()
    unique_cols = []
    for c in fetch_cols:
        if c not in seen:
            seen.add(c)
            unique_cols.append(c)
    fetch_cols = unique_cols

    disc_col = None
    if is_polymorphic and type_disc and "column" in type_disc:
        disc_col = type_disc["column"]
        if disc_col not in fetch_cols:
            fetch_cols.append(disc_col)

    rows = _fetch_table_data(pg_conn, edge_table, fetch_cols)

    d_fk = domain_keys[0]
    r_fk = range_keys[0]
    d_pk = domain_pk[0]
    r_pk = range_pk[0]

    if is_polymorphic and type_disc and "mapping" in type_disc:
        mapping = type_disc["mapping"]
        by_type: dict[str, list] = {}
        for row in rows:
            rd = dict(zip(fetch_cols, row))
            disc_val = str(rd.get(disc_col, "")).lower() if disc_col else None
            target_class = mapping.get(disc_val) if disc_val else None
            if target_class is None:
                continue
            by_type.setdefault(target_class, []).append(rd)

        total = 0
        for target_class, typed_rows in by_type.items():
            range_label = get_label_for_class(target_class)
            count = _create_junction_rels_batch(
                neo4j_driver, rel_type, domain_label, d_pk, d_fk,
                range_label, r_pk, r_fk, edge_attr_names, typed_rows, batch_size,
            )
            total += count
        return total
    else:
        range_label = get_label_for_class(range_classes[0]) if range_classes else "Unknown"
        row_dicts = [dict(zip(fetch_cols, row)) for row in rows]
        return _create_junction_rels_batch(
            neo4j_driver, rel_type, domain_label, d_pk, d_fk,
            range_label, r_pk, r_fk, edge_attr_names, row_dicts, batch_size,
        )


def _create_junction_rels_batch(
    neo4j_driver,
    rel_type: str,
    domain_label: str,
    d_pk: str,
    d_fk: str,
    range_label: str,
    r_pk: str,
    r_fk: str,
    edge_attr_names: list[str],
    row_dicts: list[dict],
    batch_size: int,
) -> int:
    """Create junction-table relationships with properties in batches."""
    if not row_dicts:
        return 0

    # Build property SET clause for edge attributes
    if edge_attr_names:
        props_clause = ", ".join(f"{attr}: row.{attr}" for attr in edge_attr_names)
        rel_props = f" {{{props_clause}}}"
    else:
        rel_props = ""

    total = 0
    with neo4j_driver.session() as session:
        for i in range(0, len(row_dicts), batch_size):
            batch = row_dicts[i : i + batch_size]
            batch_data = []
            for rd in batch:
                d_val = _convert_value(rd.get(d_fk))
                r_val = _convert_value(rd.get(r_fk))
                if d_val is None or r_val is None:
                    continue
                item = {"d_id": d_val, "r_id": r_val}
                for attr in edge_attr_names:
                    item[attr] = _convert_value(rd.get(attr))
                batch_data.append(item)

            if not batch_data:
                continue

            session.run(
                f"UNWIND $batch AS row "
                f"MATCH (d:{domain_label} {{{d_pk}: row.d_id}}) "
                f"MATCH (r:{range_label} {{{r_pk}: row.r_id}}) "
                f"CREATE (d)-[:{rel_type}{rel_props}]->(r)",
                batch=batch_data,
            )
            total += len(batch_data)
    return total


def load_data(
    ontology: OntologyAccessor,
    pg_conn,
    neo4j_driver,
    clear: bool = True,
    batch_size: int = BATCH_SIZE,
) -> MigrationMetrics:
    """
    Load data from PostgreSQL into Neo4j using a VG ontology.

    Args:
        ontology: OntologyAccessor instance
        pg_conn: psycopg connection to PostgreSQL
        neo4j_driver: neo4j.Driver instance
        clear: If True, clear Neo4j data before loading
        batch_size: Number of rows per UNWIND batch

    Returns:
        MigrationMetrics with counts and timing
    """
    metrics = MigrationMetrics()
    metrics.start_time = time.time()

    print("=" * 60)
    print("VG/SQL → Neo4j Data Loader")
    print("=" * 60)

    if clear:
        print("\nClearing existing Neo4j data...")
        with neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    # Create schema (constraints/indexes)
    from .schema import generate_schema

    print("\nCreating schema...")
    generate_schema(ontology, driver=neo4j_driver)

    # Load nodes
    print(f"\nLoading nodes ({len(ontology.classes)} classes)...")
    load_nodes(ontology, pg_conn, neo4j_driver, metrics, batch_size)

    # Load relationships
    print(f"\nLoading relationships ({len(ontology.roles)} roles)...")
    load_relationships(ontology, pg_conn, neo4j_driver, metrics, batch_size)

    metrics.end_time = time.time()

    # Print summary
    print(f"\n{'='*60}")
    print("Migration Complete")
    print(f"{'='*60}")
    print(f"  Duration: {metrics.duration_seconds:.1f}s")
    print(f"  Nodes:    {metrics.total_nodes:,}")
    print(f"  Rels:     {metrics.total_relationships:,}")
    if metrics.warnings:
        print(f"\n  Warnings:")
        for w in metrics.warnings:
            print(f"    - {w}")

    return metrics
