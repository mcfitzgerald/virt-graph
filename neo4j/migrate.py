"""
Migrate data from PostgreSQL to Neo4j.

This script:
1. Exports data from PostgreSQL to the existing database
2. Creates Neo4j nodes and relationships
3. Tracks migration metrics for TCO analysis

Usage:
    poetry run python neo4j/migrate.py

Requirements:
    - PostgreSQL running (docker-compose up -d from root)
    - Neo4j running (docker-compose -f neo4j/docker-compose.yml up -d)
"""

import time
from dataclasses import dataclass, field
from typing import Any

import psycopg2
from neo4j import GraphDatabase

# Connection settings
PG_DSN = "postgresql://virt_graph:dev_password@localhost:5432/supply_chain"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "dev_password")


@dataclass
class MigrationMetrics:
    """Track migration effort and metrics."""

    start_time: float = 0
    end_time: float = 0
    lines_of_code: int = 0
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


class PostgreSQLToNeo4jMigrator:
    """Migrates supply chain data from PostgreSQL to Neo4j."""

    def __init__(self, pg_dsn: str, neo4j_uri: str, neo4j_auth: tuple[str, str]):
        self.pg_dsn = pg_dsn
        self.neo4j_uri = neo4j_uri
        self.neo4j_auth = neo4j_auth
        self.metrics = MigrationMetrics()
        self.pg_conn = None
        self.neo4j_driver = None

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
            # Delete all relationships and nodes
            session.run("MATCH (n) DETACH DELETE n")
            print("Cleared existing Neo4j data")

    def create_constraints(self):
        """Create Neo4j constraints and indexes for performance."""
        constraints = [
            ("Supplier", "id"),
            ("Part", "id"),
            ("Product", "id"),
            ("Facility", "id"),
            ("Customer", "id"),
            ("Order", "id"),
            ("Shipment", "id"),
            ("Certification", "id"),
        ]

        with self.neo4j_driver.session() as session:
            for label, prop in constraints:
                try:
                    session.run(
                        f"CREATE CONSTRAINT {label.lower()}_{prop}_unique "
                        f"IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                    )
                except Exception as e:
                    # Constraint may already exist
                    pass

            # Additional indexes for common queries
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

        print("Created Neo4j constraints and indexes")
        self.metrics.decisions_made.append(
            "Created unique constraints on all node IDs for referential integrity"
        )

    def migrate_suppliers(self):
        """Migrate suppliers table to Supplier nodes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT id, supplier_code, name, tier, country, city,
                       contact_email, credit_rating, is_active
                FROM suppliers
                WHERE deleted_at IS NULL
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                session.run(
                    """
                    CREATE (s:Supplier {
                        id: $id,
                        supplier_code: $supplier_code,
                        name: $name,
                        tier: $tier,
                        country: $country,
                        city: $city,
                        contact_email: $contact_email,
                        credit_rating: $credit_rating,
                        is_active: $is_active
                    })
                    """,
                    id=row[0],
                    supplier_code=row[1],
                    name=row[2],
                    tier=row[3],
                    country=row[4],
                    city=row[5],
                    contact_email=row[6],
                    credit_rating=row[7],
                    is_active=row[8],
                )

        count = len(rows)
        self.metrics.nodes_created["Supplier"] = count
        print(f"Migrated {count} suppliers")
        self.metrics.decisions_made.append(
            "Filtered soft-deleted suppliers (deleted_at IS NULL)"
        )

    def migrate_parts(self):
        """Migrate parts table to Part nodes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT id, part_number, description, category, unit_cost,
                       weight_kg, lead_time_days, primary_supplier_id,
                       is_critical, min_stock_level
                FROM parts
                WHERE deleted_at IS NULL
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                # Convert Decimal to float for Neo4j
                unit_cost = float(row[4]) if row[4] else None
                weight_kg = float(row[5]) if row[5] else None

                session.run(
                    """
                    CREATE (p:Part {
                        id: $id,
                        part_number: $part_number,
                        description: $description,
                        category: $category,
                        unit_cost: $unit_cost,
                        weight_kg: $weight_kg,
                        lead_time_days: $lead_time_days,
                        primary_supplier_id: $primary_supplier_id,
                        is_critical: $is_critical,
                        min_stock_level: $min_stock_level
                    })
                    """,
                    id=row[0],
                    part_number=row[1],
                    description=row[2],
                    category=row[3],
                    unit_cost=unit_cost,
                    weight_kg=weight_kg,
                    lead_time_days=row[6],
                    primary_supplier_id=row[7],
                    is_critical=row[8],
                    min_stock_level=row[9],
                )

        count = len(rows)
        self.metrics.nodes_created["Part"] = count
        print(f"Migrated {count} parts")
        self.metrics.edge_cases.append(
            "Converted Decimal types to float for Neo4j compatibility"
        )

    def migrate_products(self):
        """Migrate products table to Product nodes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT id, sku, name, description, category, list_price,
                       is_active, launch_date
                FROM products
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                list_price = float(row[5]) if row[5] else None
                launch_date = str(row[7]) if row[7] else None

                session.run(
                    """
                    CREATE (p:Product {
                        id: $id,
                        sku: $sku,
                        name: $name,
                        description: $description,
                        category: $category,
                        list_price: $list_price,
                        is_active: $is_active,
                        launch_date: $launch_date
                    })
                    """,
                    id=row[0],
                    sku=row[1],
                    name=row[2],
                    description=row[3],
                    category=row[4],
                    list_price=list_price,
                    is_active=row[6],
                    launch_date=launch_date,
                )

        count = len(rows)
        self.metrics.nodes_created["Product"] = count
        print(f"Migrated {count} products")

    def migrate_facilities(self):
        """Migrate facilities table to Facility nodes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT id, facility_code, name, facility_type, city, state,
                       country, latitude, longitude, capacity_units, is_active
                FROM facilities
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                latitude = float(row[7]) if row[7] else None
                longitude = float(row[8]) if row[8] else None

                session.run(
                    """
                    CREATE (f:Facility {
                        id: $id,
                        facility_code: $facility_code,
                        name: $name,
                        facility_type: $facility_type,
                        city: $city,
                        state: $state,
                        country: $country,
                        latitude: $latitude,
                        longitude: $longitude,
                        capacity_units: $capacity_units,
                        is_active: $is_active
                    })
                    """,
                    id=row[0],
                    facility_code=row[1],
                    name=row[2],
                    facility_type=row[3],
                    city=row[4],
                    state=row[5],
                    country=row[6],
                    latitude=latitude,
                    longitude=longitude,
                    capacity_units=row[9],
                    is_active=row[10],
                )

        count = len(rows)
        self.metrics.nodes_created["Facility"] = count
        print(f"Migrated {count} facilities")

    def migrate_customers(self):
        """Migrate customers table to Customer nodes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT id, customer_code, name, customer_type, city, country
                FROM customers
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                session.run(
                    """
                    CREATE (c:Customer {
                        id: $id,
                        customer_code: $customer_code,
                        name: $name,
                        customer_type: $customer_type,
                        city: $city,
                        country: $country
                    })
                    """,
                    id=row[0],
                    customer_code=row[1],
                    name=row[2],
                    customer_type=row[3],
                    city=row[4],
                    country=row[5],
                )

        count = len(rows)
        self.metrics.nodes_created["Customer"] = count
        print(f"Migrated {count} customers")

    def migrate_orders(self):
        """Migrate orders table to Order nodes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT id, order_number, customer_id, order_date, status,
                       shipping_facility_id, total_amount
                FROM orders
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                order_date = str(row[3]) if row[3] else None
                total_amount = float(row[6]) if row[6] else None

                session.run(
                    """
                    CREATE (o:Order {
                        id: $id,
                        order_number: $order_number,
                        customer_id: $customer_id,
                        order_date: $order_date,
                        status: $status,
                        shipping_facility_id: $shipping_facility_id,
                        total_amount: $total_amount
                    })
                    """,
                    id=row[0],
                    order_number=row[1],
                    customer_id=row[2],
                    order_date=order_date,
                    status=row[4],
                    shipping_facility_id=row[5],
                    total_amount=total_amount,
                )

        count = len(rows)
        self.metrics.nodes_created["Order"] = count
        print(f"Migrated {count} orders")

    def migrate_shipments(self):
        """Migrate shipments table to Shipment nodes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT id, shipment_number, order_id, carrier, tracking_number,
                       status, weight_kg, cost_usd
                FROM shipments
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                weight_kg = float(row[6]) if row[6] else None
                cost_usd = float(row[7]) if row[7] else None

                session.run(
                    """
                    CREATE (s:Shipment {
                        id: $id,
                        shipment_number: $shipment_number,
                        order_id: $order_id,
                        carrier: $carrier,
                        tracking_number: $tracking_number,
                        status: $status,
                        weight_kg: $weight_kg,
                        cost_usd: $cost_usd
                    })
                    """,
                    id=row[0],
                    shipment_number=row[1],
                    order_id=row[2],
                    carrier=row[3],
                    tracking_number=row[4],
                    status=row[5],
                    weight_kg=weight_kg,
                    cost_usd=cost_usd,
                )

        count = len(rows)
        self.metrics.nodes_created["Shipment"] = count
        print(f"Migrated {count} shipments")

    def migrate_certifications(self):
        """Migrate supplier_certifications to Certification nodes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT id, supplier_id, certification_type, certification_number,
                       issued_date, expiry_date, is_valid
                FROM supplier_certifications
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                issued_date = str(row[4]) if row[4] else None
                expiry_date = str(row[5]) if row[5] else None

                session.run(
                    """
                    CREATE (c:Certification {
                        id: $id,
                        supplier_id: $supplier_id,
                        certification_type: $certification_type,
                        certification_number: $certification_number,
                        issued_date: $issued_date,
                        expiry_date: $expiry_date,
                        is_valid: $is_valid
                    })
                    """,
                    id=row[0],
                    supplier_id=row[1],
                    certification_type=row[2],
                    certification_number=row[3],
                    issued_date=issued_date,
                    expiry_date=expiry_date,
                    is_valid=row[6],
                )

        count = len(rows)
        self.metrics.nodes_created["Certification"] = count
        print(f"Migrated {count} certifications")

    def migrate_supplier_relationships(self):
        """Create SUPPLIES_TO relationships between suppliers."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT seller_id, buyer_id, relationship_type, is_primary
                FROM supplier_relationships
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                session.run(
                    """
                    MATCH (seller:Supplier {id: $seller_id})
                    MATCH (buyer:Supplier {id: $buyer_id})
                    CREATE (seller)-[:SUPPLIES_TO {
                        relationship_type: $relationship_type,
                        is_primary: $is_primary
                    }]->(buyer)
                    """,
                    seller_id=row[0],
                    buyer_id=row[1],
                    relationship_type=row[2],
                    is_primary=row[3],
                )

        count = len(rows)
        self.metrics.relationships_created["SUPPLIES_TO"] = count
        print(f"Created {count} SUPPLIES_TO relationships")

    def migrate_bom(self):
        """Create COMPONENT_OF relationships for bill of materials."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT child_part_id, parent_part_id, quantity, is_optional
                FROM bill_of_materials
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            # Batch process for better performance
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                for row in batch:
                    session.run(
                        """
                        MATCH (child:Part {id: $child_id})
                        MATCH (parent:Part {id: $parent_id})
                        CREATE (child)-[:COMPONENT_OF {
                            quantity: $quantity,
                            is_optional: $is_optional
                        }]->(parent)
                        """,
                        child_id=row[0],
                        parent_id=row[1],
                        quantity=row[2],
                        is_optional=row[3],
                    )
                print(f"  Processed BOM batch {i + len(batch)}/{len(rows)}")

        count = len(rows)
        self.metrics.relationships_created["COMPONENT_OF"] = count
        print(f"Created {count} COMPONENT_OF relationships")

    def migrate_transport_routes(self):
        """Create CONNECTS_TO relationships for transport routes."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT origin_facility_id, destination_facility_id,
                       transport_mode, distance_km, transit_time_hours,
                       cost_usd, capacity_tons, is_active
                FROM transport_routes
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                distance_km = float(row[3]) if row[3] else None
                transit_time_hours = float(row[4]) if row[4] else None
                cost_usd = float(row[5]) if row[5] else None
                capacity_tons = float(row[6]) if row[6] else None

                session.run(
                    """
                    MATCH (origin:Facility {id: $origin_id})
                    MATCH (dest:Facility {id: $dest_id})
                    CREATE (origin)-[:CONNECTS_TO {
                        transport_mode: $transport_mode,
                        distance_km: $distance_km,
                        transit_time_hours: $transit_time_hours,
                        cost_usd: $cost_usd,
                        capacity_tons: $capacity_tons,
                        is_active: $is_active
                    }]->(dest)
                    """,
                    origin_id=row[0],
                    dest_id=row[1],
                    transport_mode=row[2],
                    distance_km=distance_km,
                    transit_time_hours=transit_time_hours,
                    cost_usd=cost_usd,
                    capacity_tons=capacity_tons,
                    is_active=row[7],
                )

        count = len(rows)
        self.metrics.relationships_created["CONNECTS_TO"] = count
        print(f"Created {count} CONNECTS_TO relationships")

    def migrate_provides_relationship(self):
        """Create PROVIDES relationships (primary supplier -> part)."""
        with self.neo4j_driver.session() as session:
            result = session.run(
                """
                MATCH (p:Part)
                WHERE p.primary_supplier_id IS NOT NULL
                MATCH (s:Supplier {id: p.primary_supplier_id})
                CREATE (s)-[:PROVIDES]->(p)
                RETURN count(*) as count
                """
            )
            count = result.single()["count"]

        self.metrics.relationships_created["PROVIDES"] = count
        print(f"Created {count} PROVIDES relationships")

    def migrate_can_supply_relationship(self):
        """Create CAN_SUPPLY relationships from part_suppliers table."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT supplier_id, part_id, supplier_part_number, unit_cost,
                       lead_time_days, is_approved
                FROM part_suppliers
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                unit_cost = float(row[3]) if row[3] else None

                session.run(
                    """
                    MATCH (s:Supplier {id: $supplier_id})
                    MATCH (p:Part {id: $part_id})
                    CREATE (s)-[:CAN_SUPPLY {
                        supplier_part_number: $supplier_part_number,
                        unit_cost: $unit_cost,
                        lead_time_days: $lead_time_days,
                        is_approved: $is_approved
                    }]->(p)
                    """,
                    supplier_id=row[0],
                    part_id=row[1],
                    supplier_part_number=row[2],
                    unit_cost=unit_cost,
                    lead_time_days=row[4],
                    is_approved=row[5],
                )

        count = len(rows)
        self.metrics.relationships_created["CAN_SUPPLY"] = count
        print(f"Created {count} CAN_SUPPLY relationships")

    def migrate_product_components_relationship(self):
        """Create CONTAINS_COMPONENT relationships."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT product_id, part_id, quantity, is_required
                FROM product_components
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            for row in rows:
                session.run(
                    """
                    MATCH (prod:Product {id: $product_id})
                    MATCH (part:Part {id: $part_id})
                    CREATE (prod)-[:CONTAINS_COMPONENT {
                        quantity: $quantity,
                        is_required: $is_required
                    }]->(part)
                    """,
                    product_id=row[0],
                    part_id=row[1],
                    quantity=row[2],
                    is_required=row[3],
                )

        count = len(rows)
        self.metrics.relationships_created["CONTAINS_COMPONENT"] = count
        print(f"Created {count} CONTAINS_COMPONENT relationships")

    def migrate_certification_relationship(self):
        """Create HAS_CERTIFICATION relationships."""
        with self.neo4j_driver.session() as session:
            result = session.run(
                """
                MATCH (c:Certification)
                WHERE c.supplier_id IS NOT NULL
                MATCH (s:Supplier {id: c.supplier_id})
                CREATE (s)-[:HAS_CERTIFICATION]->(c)
                RETURN count(*) as count
                """
            )
            count = result.single()["count"]

        self.metrics.relationships_created["HAS_CERTIFICATION"] = count
        print(f"Created {count} HAS_CERTIFICATION relationships")

    def migrate_order_relationships(self):
        """Create order-related relationships."""
        with self.neo4j_driver.session() as session:
            # PLACED_BY: Order -> Customer
            result = session.run(
                """
                MATCH (o:Order)
                WHERE o.customer_id IS NOT NULL
                MATCH (c:Customer {id: o.customer_id})
                CREATE (o)-[:PLACED_BY]->(c)
                RETURN count(*) as count
                """
            )
            count = result.single()["count"]
            self.metrics.relationships_created["PLACED_BY"] = count
            print(f"Created {count} PLACED_BY relationships")

            # SHIPS_FROM: Order -> Facility
            result = session.run(
                """
                MATCH (o:Order)
                WHERE o.shipping_facility_id IS NOT NULL
                MATCH (f:Facility {id: o.shipping_facility_id})
                CREATE (o)-[:SHIPS_FROM]->(f)
                RETURN count(*) as count
                """
            )
            count = result.single()["count"]
            self.metrics.relationships_created["SHIPS_FROM"] = count
            print(f"Created {count} SHIPS_FROM relationships")

    def migrate_order_items_relationship(self):
        """Create CONTAINS_ITEM relationships."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT order_id, product_id, quantity, unit_price
                FROM order_items
            """)
            rows = cur.fetchall()

        with self.neo4j_driver.session() as session:
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                for row in batch:
                    unit_price = float(row[3]) if row[3] else None
                    session.run(
                        """
                        MATCH (o:Order {id: $order_id})
                        MATCH (p:Product {id: $product_id})
                        CREATE (o)-[:CONTAINS_ITEM {
                            quantity: $quantity,
                            unit_price: $unit_price
                        }]->(p)
                        """,
                        order_id=row[0],
                        product_id=row[1],
                        quantity=row[2],
                        unit_price=unit_price,
                    )
                print(f"  Processed order items batch {i + len(batch)}/{len(rows)}")

        count = len(rows)
        self.metrics.relationships_created["CONTAINS_ITEM"] = count
        print(f"Created {count} CONTAINS_ITEM relationships")

    def migrate_shipment_relationships(self):
        """Create shipment-related relationships."""
        with self.neo4j_driver.session() as session:
            # FULFILLS: Shipment -> Order
            result = session.run(
                """
                MATCH (s:Shipment)
                WHERE s.order_id IS NOT NULL
                MATCH (o:Order {id: s.order_id})
                CREATE (s)-[:FULFILLS]->(o)
                RETURN count(*) as count
                """
            )
            count = result.single()["count"]
            self.metrics.relationships_created["FULFILLS"] = count
            print(f"Created {count} FULFILLS relationships")

    def migrate_all(self):
        """Run complete migration with metrics tracking."""
        self.metrics.start_time = time.time()

        print("\n" + "=" * 60)
        print("PostgreSQL to Neo4j Migration")
        print("=" * 60)

        self.connect()
        print(f"Connected to PostgreSQL and Neo4j\n")

        # Clear and prepare
        self.clear_neo4j()
        self.create_constraints()

        print("\n--- Migrating Nodes ---")
        self.migrate_suppliers()
        self.migrate_parts()
        self.migrate_products()
        self.migrate_facilities()
        self.migrate_customers()
        self.migrate_orders()
        self.migrate_shipments()
        self.migrate_certifications()

        print("\n--- Migrating Relationships ---")
        self.migrate_supplier_relationships()
        self.migrate_bom()
        self.migrate_transport_routes()
        self.migrate_provides_relationship()
        self.migrate_can_supply_relationship()
        self.migrate_product_components_relationship()
        self.migrate_certification_relationship()
        self.migrate_order_relationships()
        self.migrate_order_items_relationship()
        self.migrate_shipment_relationships()

        self.close()
        self.metrics.end_time = time.time()

        # Count lines of code in this file (rough estimate)
        import inspect

        self.metrics.lines_of_code = len(
            inspect.getsourcelines(PostgreSQLToNeo4jMigrator)[0]
        )

        self.print_report()

    def print_report(self):
        """Print migration metrics report."""
        print("\n" + "=" * 60)
        print("Migration Complete - Metrics Report")
        print("=" * 60)

        print(f"\nDuration: {self.metrics.duration_seconds:.1f} seconds")
        print(f"Lines of migration code: ~{self.metrics.lines_of_code}")

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

        # Write metrics to file for benchmark
        self._save_metrics()

    def _save_metrics(self):
        """Save metrics to JSON file."""
        import json
        import os

        metrics_data = {
            "duration_seconds": self.metrics.duration_seconds,
            "lines_of_code": self.metrics.lines_of_code,
            "nodes_created": self.metrics.nodes_created,
            "relationships_created": self.metrics.relationships_created,
            "total_nodes": self.metrics.total_nodes,
            "total_relationships": self.metrics.total_relationships,
            "decisions": self.metrics.decisions_made,
            "edge_cases": self.metrics.edge_cases,
        }

        metrics_path = os.path.join(os.path.dirname(__file__), "migration_metrics.json")
        with open(metrics_path, "w") as f:
            json.dump(metrics_data, f, indent=2)
        print(f"\nMetrics saved to {metrics_path}")


def main():
    """Run migration."""
    migrator = PostgreSQLToNeo4jMigrator(PG_DSN, NEO4J_URI, NEO4J_AUTH)
    migrator.migrate_all()


if __name__ == "__main__":
    main()
