"""
Ontology-driven migration from PostgreSQL to Neo4j.

Reads schema from ontology/supply_chain.yaml to ensure
consistency with Virtual Graph approach. Both systems derive
from the same source of truth for a fair TCO comparison.

Usage:
    poetry run python neo4j/migrate.py

Requirements:
    - PostgreSQL running (docker-compose -f postgres/docker-compose.yml up -d)
    - Neo4j running (docker-compose -f neo4j/docker-compose.yml up -d)
"""

import json
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
from neo4j import GraphDatabase

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from virt_graph.ontology import OntologyAccessor

# Connection settings
PG_DSN = "postgresql://virt_graph:dev_password@localhost:5432/supply_chain"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "dev_password")


@dataclass
class MigrationMetrics:
    """Track migration effort and metrics."""

    start_time: float = 0
    end_time: float = 0
    nodes_created: dict[str, int] = field(default_factory=dict)
    relationships_created: dict[str, int] = field(default_factory=dict)
    decisions_made: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    @property
    def total_nodes(self) -> int:
        return sum(self.nodes_created.values())

    @property
    def total_relationships(self) -> int:
        return sum(self.relationships_created.values())


class OntologyDrivenMigrator:
    """
    Migrates supply chain data from PostgreSQL to Neo4j using ontology.

    The ontology defines:
    - classes -> Neo4j node labels
    - relationships -> Neo4j relationship types
    - sql_mapping -> source tables and keys
    """

    # Neo4j label mapping for special cases
    LABEL_MAPPING = {
        "SupplierCertification": "Certification",  # Shorter label
    }

    def __init__(self, pg_dsn: str, neo4j_uri: str, neo4j_auth: tuple[str, str]):
        self.pg_dsn = pg_dsn
        self.neo4j_uri = neo4j_uri
        self.neo4j_auth = neo4j_auth
        self.metrics = MigrationMetrics()
        self.pg_conn = None
        self.neo4j_driver = None
        self.ontology = OntologyAccessor()

    def connect(self):
        """Establish database connections."""
        self.pg_conn = psycopg2.connect(self.pg_dsn)
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_uri, auth=self.neo4j_auth
        )
        # Test Neo4j connection
        with self.neo4j_driver.session() as session:
            session.run("RETURN 1")

    def close(self):
        """Close database connections."""
        if self.pg_conn:
            self.pg_conn.close()
        if self.neo4j_driver:
            self.neo4j_driver.close()

    def clear_neo4j(self):
        """Clear all data from Neo4j database."""
        with self.neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Cleared existing Neo4j data")

    def _get_neo4j_label(self, class_name: str) -> str:
        """Get Neo4j label for an ontology class."""
        return self.LABEL_MAPPING.get(class_name, class_name)

    def _convert_value(self, value: Any) -> Any:
        """Convert Python/PostgreSQL types to Neo4j-compatible types."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        if hasattr(value, 'isoformat'):  # datetime, date
            return str(value)
        return value

    def create_constraints_from_ontology(self):
        """Create Neo4j constraints from ontology classes."""
        with self.neo4j_driver.session() as session:
            for class_name in self.ontology.classes:
                label = self._get_neo4j_label(class_name)
                pk = self.ontology.get_class_pk(class_name)

                try:
                    session.run(
                        f"CREATE CONSTRAINT {label.lower()}_{pk}_unique "
                        f"IF NOT EXISTS FOR (n:{label}) REQUIRE n.{pk} IS UNIQUE"
                    )
                except Exception:
                    pass  # Constraint may already exist

            # Additional indexes for common query patterns
            session.run(
                "CREATE INDEX supplier_tier IF NOT EXISTS FOR (s:Supplier) ON (s.tier)"
            )
            session.run(
                "CREATE INDEX supplier_name IF NOT EXISTS FOR (s:Supplier) ON (s.name)"
            )
            session.run(
                "CREATE INDEX facility_name IF NOT EXISTS FOR (f:Facility) ON (f.name)"
            )
            session.run(
                "CREATE INDEX part_number IF NOT EXISTS FOR (p:Part) ON (p.part_number)"
            )
            session.run(
                "CREATE INDEX product_sku IF NOT EXISTS FOR (p:Product) ON (p.sku)"
            )

        print("Created Neo4j constraints and indexes from ontology")
        self.metrics.decisions_made.append(
            "Created unique constraints on all node IDs for referential integrity"
        )

    def _get_table_columns(self, table: str) -> list[str]:
        """Get column names for a table from PostgreSQL."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            return [row[0] for row in cur.fetchall()]

    def migrate_nodes_from_ontology(self):
        """Migrate nodes using ontology class definitions."""
        for class_name in self.ontology.classes:
            table = self.ontology.get_class_table(class_name)
            label = self._get_neo4j_label(class_name)

            # Get all columns for this table
            columns = self._get_table_columns(table)

            # Build SELECT query
            soft_delete_enabled, soft_delete_col = self.ontology.get_class_soft_delete(class_name)
            if soft_delete_col is None:
                soft_delete_col = "deleted_at"  # fallback default

            column_list = ", ".join(columns)
            query = f"SELECT {column_list} FROM {table}"
            if soft_delete_enabled:
                query += f" WHERE {soft_delete_col} IS NULL"

            # Fetch data from PostgreSQL
            with self.pg_conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()

            # Create nodes in Neo4j
            with self.neo4j_driver.session() as session:
                for row in rows:
                    # Build properties dict with converted values
                    props = {}
                    for i, col in enumerate(columns):
                        value = self._convert_value(row[i])
                        if value is not None:
                            props[col] = value

                    # Build property string for Cypher
                    prop_assignments = ", ".join(
                        f"{k}: ${k}" for k in props.keys()
                    )

                    session.run(
                        f"CREATE (n:{label} {{{prop_assignments}}})",
                        **props
                    )

            count = len(rows)
            self.metrics.nodes_created[label] = count
            print(f"Migrated {count} {label} nodes from {table}")

            if soft_delete_enabled:
                self.metrics.decisions_made.append(
                    f"Filtered soft-deleted {class_name} ({soft_delete_col} IS NULL)"
                )

        self.metrics.edge_cases.append(
            "Converted Decimal types to float for Neo4j compatibility"
        )
        self.metrics.edge_cases.append(
            "Converted datetime/date types to string for Neo4j compatibility"
        )

    def migrate_relationships_from_ontology(self):
        """Migrate relationships using ontology role definitions."""
        for rel_name in self.ontology.roles:
            role_sql = self.ontology.get_role_sql(rel_name)
            table = role_sql["table"]
            domain_key, range_key = self.ontology.get_role_keys(rel_name)

            domain_class = self.ontology.get_role_domain(rel_name)
            range_class = self.ontology.get_role_range(rel_name)
            domain_label = self._get_neo4j_label(domain_class)
            range_label = self._get_neo4j_label(range_class)

            # Convert relationship name to UPPER_SNAKE_CASE
            neo4j_rel_type = rel_name.upper()

            # Get additional columns to include as relationship properties
            additional_cols = role_sql.get("additional_columns", [])

            # Determine if this is a junction table or FK relationship
            # Junction tables: separate table with both keys
            # FK relationships: domain_key and range_key in same table as domain

            domain_table = self.ontology.get_class_table(domain_class)
            domain_pk = self.ontology.get_class_pk(domain_class)

            range_pk = self.ontology.get_class_pk(range_class)

            if table == domain_table:
                # FK relationship: Create relationships from node properties
                count = self._migrate_fk_relationship(
                    rel_name, neo4j_rel_type,
                    domain_label, domain_pk, domain_key,
                    range_label, range_pk, range_key
                )
            else:
                # Junction table relationship: Read from junction table
                count = self._migrate_junction_relationship(
                    rel_name, neo4j_rel_type,
                    table, domain_key, range_key,
                    domain_label, domain_pk,
                    range_label, range_pk,
                    additional_cols
                )

            self.metrics.relationships_created[neo4j_rel_type] = count
            print(f"Created {count} {neo4j_rel_type} relationships")

    def _migrate_fk_relationship(
        self, rel_name: str, neo4j_rel_type: str,
        domain_label: str, domain_pk: str, domain_key: str,
        range_label: str, range_pk: str, range_key: str
    ) -> int:
        """Migrate FK-based relationships using Neo4j node properties."""
        with self.neo4j_driver.session() as session:
            result = session.run(
                f"""
                MATCH (d:{domain_label})
                WHERE d.{range_key} IS NOT NULL
                MATCH (r:{range_label} {{{range_pk}: d.{range_key}}})
                CREATE (d)-[:{neo4j_rel_type}]->(r)
                RETURN count(*) as count
                """
            )
            return result.single()["count"]

    def _migrate_junction_relationship(
        self, rel_name: str, neo4j_rel_type: str,
        table: str, domain_key: str, range_key: str,
        domain_label: str, domain_pk: str,
        range_label: str, range_pk: str,
        additional_cols: list[str]
    ) -> int:
        """Migrate junction table relationships with properties."""
        # Build column list for SELECT
        columns = [domain_key, range_key] + additional_cols
        column_list = ", ".join(columns)

        # Fetch junction table data
        with self.pg_conn.cursor() as cur:
            cur.execute(f"SELECT {column_list} FROM {table}")
            rows = cur.fetchall()

        # Create relationships in batches
        batch_size = 1000
        total_created = 0

        with self.neo4j_driver.session() as session:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]

                for row in batch:
                    domain_id = row[0]
                    range_id = row[1]

                    # Build relationship properties
                    props = {}
                    for j, col in enumerate(additional_cols):
                        value = self._convert_value(row[j + 2])
                        if value is not None:
                            props[col] = value

                    if props:
                        prop_assignments = ", ".join(
                            f"{k}: ${k}" for k in props.keys()
                        )
                        cypher = f"""
                            MATCH (d:{domain_label} {{{domain_pk}: $domain_id}})
                            MATCH (r:{range_label} {{{range_pk}: $range_id}})
                            CREATE (d)-[:{neo4j_rel_type} {{{prop_assignments}}}]->(r)
                        """
                    else:
                        cypher = f"""
                            MATCH (d:{domain_label} {{{domain_pk}: $domain_id}})
                            MATCH (r:{range_label} {{{range_pk}: $range_id}})
                            CREATE (d)-[:{neo4j_rel_type}]->(r)
                        """

                    session.run(cypher, domain_id=domain_id, range_id=range_id, **props)

                total_created += len(batch)
                if len(rows) > batch_size:
                    print(f"  Processed {rel_name} batch {min(i + batch_size, len(rows))}/{len(rows)}")

        return len(rows)

    def migrate_all(self):
        """Run complete ontology-driven migration with metrics tracking."""
        self.metrics.start_time = time.time()

        print("\n" + "=" * 60)
        print("Ontology-Driven PostgreSQL to Neo4j Migration")
        print("=" * 60)
        print(f"Ontology version: {self.ontology.version}")
        print(f"Domain: {self.ontology.name}")

        self.connect()
        print(f"Connected to PostgreSQL and Neo4j\n")

        # Clear and prepare
        self.clear_neo4j()
        self.create_constraints_from_ontology()

        print("\n--- Migrating Nodes from Ontology Classes ---")
        self.migrate_nodes_from_ontology()

        print("\n--- Migrating Relationships from Ontology ---")
        self.migrate_relationships_from_ontology()

        self.close()
        self.metrics.end_time = time.time()

        self.print_report()

    def print_report(self):
        """Print migration metrics report."""
        print("\n" + "=" * 60)
        print("Migration Complete - Metrics Report")
        print("=" * 60)

        print(f"\nDuration: {self.metrics.duration_seconds:.1f} seconds")

        print(f"\nNodes Created ({self.metrics.total_nodes:,} total):")
        for label, count in sorted(self.metrics.nodes_created.items()):
            print(f"  {label}: {count:,}")

        print(f"\nRelationships Created ({self.metrics.total_relationships:,} total):")
        for rel_type, count in sorted(self.metrics.relationships_created.items()):
            print(f"  {rel_type}: {count:,}")

        print("\nDesign Decisions:")
        for decision in self.metrics.decisions_made:
            print(f"  - {decision}")

        print("\nEdge Cases Handled:")
        for edge_case in self.metrics.edge_cases:
            print(f"  - {edge_case}")

        # Validate against ontology expected counts
        print("\n--- Validation Against Ontology ---")
        self._validate_counts()

        # Write metrics to file for benchmark
        self._save_metrics()

    def _validate_counts(self):
        """Validate migrated counts against ontology expectations."""
        all_valid = True

        # Validate node counts
        for class_name in self.ontology.classes:
            label = self._get_neo4j_label(class_name)
            expected = self.ontology.get_class_row_count(class_name)
            actual = self.metrics.nodes_created.get(label, 0)

            if expected:
                status = "✓" if actual == expected else "✗"
                if actual != expected:
                    all_valid = False
                print(f"  {status} {label}: {actual} (expected {expected})")

        # Validate relationship counts
        for rel_name in self.ontology.roles:
            neo4j_type = rel_name.upper()
            expected = self.ontology.get_role_row_count(rel_name)
            actual = self.metrics.relationships_created.get(neo4j_type, 0)

            if expected:
                status = "✓" if actual == expected else "✗"
                if actual != expected:
                    all_valid = False
                print(f"  {status} {neo4j_type}: {actual} (expected {expected})")

        if all_valid:
            print("\n✓ All counts match ontology expectations")
        else:
            print("\n✗ Some counts differ from ontology expectations")

    def _save_metrics(self):
        """Save metrics to JSON file."""
        metrics_data = {
            "duration_seconds": self.metrics.duration_seconds,
            "ontology_version": self.ontology.version,
            "nodes_created": self.metrics.nodes_created,
            "relationships_created": self.metrics.relationships_created,
            "total_nodes": self.metrics.total_nodes,
            "total_relationships": self.metrics.total_relationships,
            "decisions": self.metrics.decisions_made,
            "edge_cases": self.metrics.edge_cases,
        }

        metrics_path = Path(__file__).parent / "migration_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics_data, f, indent=2)
        print(f"\nMetrics saved to {metrics_path}")


def main():
    """Run ontology-driven migration."""
    migrator = OntologyDrivenMigrator(PG_DSN, NEO4J_URI, NEO4J_AUTH)
    migrator.migrate_all()


if __name__ == "__main__":
    main()
