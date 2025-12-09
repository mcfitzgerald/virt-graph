#!/usr/bin/env python3
"""
Validate that named test entities exist in the database.

Run before benchmarking to ensure the database has all expected named entities.

Usage:
    poetry run python scripts/validate_entities.py
    make validate-entities
"""

import sys

import psycopg2

# Named test entities that should exist for benchmark queries
REQUIRED_ENTITIES = {
    "suppliers": [
        "Acme Corp",
        "GlobalTech Industries",
        "Precision Parts Ltd",
        "Pacific Components",
        "Northern Materials",
        "Apex Manufacturing",
        "Eastern Electronics",
        "Delta Supplies",
    ],
    "products": [
        "Turbo Encabulator",
        "Flux Capacitor",
        "Standard Widget",
    ],
    "facilities": [
        "Chicago Warehouse",
        "LA Distribution Center",
        "New York Factory",
        "Shanghai Hub",
        "Munich Factory",
        "Denver Hub",
        "Miami Hub",
        "Seattle Warehouse",
    ],
    "customers": [
        "Acme Industries",
        "Globex Corporation",
        "Initech Inc",
    ],
    "parts": [
        ("part_number", "CHIP-001"),
        ("part_number", "RESISTOR-100"),
        ("part_number", "CAP-001"),
        ("part_number", "MOTOR-001"),
        ("part_number", "SENSOR-001"),
        ("part_number", "TURBO-ENC-001"),
        ("part_number", "FLUX-CAP-001"),
    ],
    "orders": [
        ("order_number", "ORD-2024-001"),
        ("order_number", "ORD-2024-002"),
        ("order_number", "ORD-2024-003"),
    ],
}

# Required relationships between named entities
REQUIRED_RELATIONSHIPS = {
    "supplier_relationships": [
        # (seller_name, buyer_name) - should find path through supplier chain
        ("Eastern Electronics", "Pacific Components"),  # T3 → T2
        ("Pacific Components", "Acme Corp"),  # T2 → T1
    ],
    "transport_routes": [
        # (origin_name, destination_name)
        ("Denver Hub", "Chicago Warehouse"),
        ("Denver Hub", "LA Distribution Center"),
        ("Chicago Warehouse", "LA Distribution Center"),
    ],
    "bill_of_materials": [
        # (parent_part_number, child_part_number)
        ("TURBO-ENC-001", "CHIP-001"),
        ("TURBO-ENC-001", "RESISTOR-100"),
    ],
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="supply_chain",
        user="virt_graph",
        password="dev_password",
    )


def validate_entities(conn) -> list[str]:
    """Check that all required entities exist. Returns list of missing entities."""
    missing = []

    with conn.cursor() as cur:
        for table, entities in REQUIRED_ENTITIES.items():
            for entity in entities:
                if isinstance(entity, tuple):
                    # Custom column check
                    column, value = entity
                    cur.execute(
                        f"SELECT 1 FROM {table} WHERE {column} = %s LIMIT 1",
                        (value,),
                    )
                else:
                    # Default: check name column
                    cur.execute(
                        f"SELECT 1 FROM {table} WHERE name = %s LIMIT 1",
                        (entity,),
                    )

                if not cur.fetchone():
                    if isinstance(entity, tuple):
                        missing.append(f"{table}.{entity[0]}={entity[1]}")
                    else:
                        missing.append(f"{table}.name={entity}")

    return missing


def validate_relationships(conn) -> list[str]:
    """Check that required relationships exist. Returns list of missing relationships."""
    missing = []

    with conn.cursor() as cur:
        # Check supplier relationships
        for seller_name, buyer_name in REQUIRED_RELATIONSHIPS.get("supplier_relationships", []):
            cur.execute(
                """
                SELECT 1 FROM supplier_relationships sr
                JOIN suppliers s1 ON sr.seller_id = s1.id
                JOIN suppliers s2 ON sr.buyer_id = s2.id
                WHERE s1.name = %s AND s2.name = %s
                LIMIT 1
                """,
                (seller_name, buyer_name),
            )
            if not cur.fetchone():
                missing.append(f"supplier_relationships: {seller_name} → {buyer_name}")

        # Check transport routes
        for origin_name, dest_name in REQUIRED_RELATIONSHIPS.get("transport_routes", []):
            cur.execute(
                """
                SELECT 1 FROM transport_routes tr
                JOIN facilities f1 ON tr.origin_facility_id = f1.id
                JOIN facilities f2 ON tr.destination_facility_id = f2.id
                WHERE f1.name = %s AND f2.name = %s
                LIMIT 1
                """,
                (origin_name, dest_name),
            )
            if not cur.fetchone():
                missing.append(f"transport_routes: {origin_name} → {dest_name}")

        # Check BOM relationships
        for parent_num, child_num in REQUIRED_RELATIONSHIPS.get("bill_of_materials", []):
            cur.execute(
                """
                SELECT 1 FROM bill_of_materials bom
                JOIN parts p1 ON bom.parent_part_id = p1.id
                JOIN parts p2 ON bom.child_part_id = p2.id
                WHERE p1.part_number = %s AND p2.part_number = %s
                LIMIT 1
                """,
                (parent_num, child_num),
            )
            if not cur.fetchone():
                missing.append(f"bill_of_materials: {parent_num} contains {child_num}")

    return missing


def main():
    """Validate all named test entities and relationships."""
    print("=" * 60)
    print("Virtual Graph - Entity Validation")
    print("=" * 60)

    try:
        conn = get_connection()
    except psycopg2.OperationalError as e:
        print(f"\n❌ Cannot connect to database: {e}")
        print("   Make sure PostgreSQL is running: make db-up")
        sys.exit(1)

    print("\nChecking required entities...")
    missing_entities = validate_entities(conn)

    print("Checking required relationships...")
    missing_relationships = validate_relationships(conn)

    conn.close()

    # Report results
    all_missing = missing_entities + missing_relationships

    if all_missing:
        print(f"\n❌ Missing {len(all_missing)} item(s):")
        for item in all_missing:
            print(f"   - {item}")
        print("\nTo fix: regenerate data with 'make db-reset'")
        sys.exit(1)
    else:
        print(f"\n✓ All {sum(len(v) for v in REQUIRED_ENTITIES.values())} named entities exist")
        print(f"✓ All {sum(len(v) for v in REQUIRED_RELATIONSHIPS.values())} named relationships exist")
        print("\nDatabase is ready for benchmarking!")
        sys.exit(0)


if __name__ == "__main__":
    main()
