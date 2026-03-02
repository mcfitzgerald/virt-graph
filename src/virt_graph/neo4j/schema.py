"""
Neo4j schema generator — ontology-driven.

Reads any VG ontology and generates Neo4j schema (constraints, indexes, labels).
Works with any ontology, not hardcoded to a specific domain.

Usage:
    from virt_graph.neo4j.schema import generate_schema

    # Generate Cypher DDL statements
    statements = generate_schema(ontology)

    # Or execute directly against Neo4j
    generate_schema(ontology, driver=neo4j_driver)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from virt_graph.ontology import OntologyAccessor


def _pascal_to_upper_snake(name: str) -> str:
    """Convert PascalCase to UPPER_SNAKE_CASE for Neo4j relationship types."""
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).upper()


def generate_schema(
    ontology: OntologyAccessor,
    driver=None,
    clear: bool = False,
) -> list[str]:
    """
    Generate Neo4j schema from a VG ontology.

    Creates:
    - Uniqueness constraints from vg:primary_key (including composite)
    - Node labels from entity classes
    - Relationship types from relationship classes

    Args:
        ontology: An OntologyAccessor instance
        driver: Optional neo4j.Driver instance. If provided, statements are executed.
        clear: If True, drop all existing data first (DETACH DELETE).

    Returns:
        List of Cypher DDL statements
    """
    statements: list[str] = []

    if clear:
        statements.append("MATCH (n) DETACH DELETE n")

    # Create uniqueness constraints for each entity class
    for cls_name, cls_info in ontology.classes.items():
        pk_cols = cls_info["primary_key"]

        if len(pk_cols) == 1:
            # Simple PK — uniqueness constraint
            pk = pk_cols[0]
            constraint_name = f"{cls_name.lower()}_{pk}_unique"
            stmt = (
                f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                f"FOR (n:{cls_name}) REQUIRE n.{pk} IS UNIQUE"
            )
            statements.append(stmt)
        else:
            # Composite PK — node key constraint (requires Enterprise or 5.7+)
            pk_list = ", ".join(f"n.{col}" for col in pk_cols)
            constraint_name = f"{cls_name.lower()}_pk_unique"
            stmt = (
                f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                f"FOR (n:{cls_name}) REQUIRE ({pk_list}) IS UNIQUE"
            )
            statements.append(stmt)

    # Execute if driver provided
    if driver is not None:
        _execute_statements(driver, statements)

    return statements


def get_label_for_class(cls_name: str) -> str:
    """Get Neo4j node label for an ontology class. By default, uses the class name."""
    return cls_name


def get_rel_type_for_role(role_name: str) -> str:
    """Get Neo4j relationship type for an ontology role. Converts to UPPER_SNAKE_CASE."""
    return _pascal_to_upper_snake(role_name)


def _execute_statements(driver, statements: list[str]) -> None:
    """Execute a list of Cypher statements against a Neo4j driver."""
    with driver.session() as session:
        for stmt in statements:
            try:
                session.run(stmt)
            except Exception as e:
                # Constraints may already exist, constraints may not be supported
                print(f"  Warning: {e}")
