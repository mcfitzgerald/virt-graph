"""
Generic Neo4j graph validator against ontology definitions.

Verifies that a Neo4j graph structure matches an ontology definition,
dynamically generating validation queries from any VG ontology file.

Usage:
    poetry run python scripts/validate_neo4j.py
    poetry run python scripts/validate_neo4j.py path/to/ontology.yaml
    poetry run python scripts/validate_neo4j.py --json
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from neo4j import GraphDatabase

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from virt_graph.ontology import OntologyAccessor

# Connection settings
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "dev_password")

# Neo4j label mapping (mirrors migrate.py)
LABEL_MAPPING = {
    "SupplierCertification": "Certification",
}


@dataclass
class ValidationCheck:
    """Result of a single validation check."""

    category: str  # "node_label", "node_count", "relationship_endpoint", etc.
    name: str  # Element being validated
    passed: bool
    message: str
    expected: Optional[any] = None
    actual: Optional[any] = None
    details: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Complete validation report."""

    ontology_name: str
    ontology_version: str
    database_uri: str
    checks: list[ValidationCheck] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def total_count(self) -> int:
        return len(self.checks)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "ontology_name": self.ontology_name,
            "ontology_version": self.ontology_version,
            "database_uri": self.database_uri,
            "summary": {
                "passed": self.passed_count,
                "failed": self.failed_count,
                "total": self.total_count,
                "all_passed": self.all_passed,
            },
            "checks": [
                {
                    "category": c.category,
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "expected": c.expected,
                    "actual": c.actual,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class Neo4jValidator:
    """
    Validates Neo4j graph structure against an ontology definition.

    Performs the following checks:
    - Node label existence
    - Node counts (if row_count annotation exists)
    - Relationship endpoint validation (domain/range)
    - Relationship counts (if row_count annotation exists)
    - Constraint validation (irreflexive, asymmetric)
    """

    def __init__(
        self, ontology_path: Optional[Path] = None, neo4j_uri: str = NEO4J_URI
    ):
        self.ontology = OntologyAccessor(ontology_path)
        self.neo4j_uri = neo4j_uri
        self.driver = None

    def _get_neo4j_label(self, class_name: str) -> str:
        """Get Neo4j label for an ontology class."""
        return LABEL_MAPPING.get(class_name, class_name)

    def _get_neo4j_rel_type(self, role_name: str) -> str:
        """Convert role name to Neo4j relationship type (UPPER_SNAKE_CASE)."""
        return role_name.upper()

    def connect(self):
        """Establish Neo4j connection."""
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=NEO4J_AUTH)
        # Test connection
        with self.driver.session() as session:
            session.run("RETURN 1")

    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()

    def validate_all(self) -> ValidationReport:
        """Run all validations derived from ontology."""
        report = ValidationReport(
            ontology_name=self.ontology.name,
            ontology_version=self.ontology.version,
            database_uri=self.neo4j_uri,
        )

        self.connect()
        try:
            # 1. Node label existence
            report.checks.extend(self._validate_node_labels())

            # 2. Node counts
            report.checks.extend(self._validate_node_counts())

            # 3. Relationship type coverage
            report.checks.extend(self._validate_relationship_types())

            # 4. Relationship endpoint validation
            report.checks.extend(self._validate_relationship_endpoints())

            # 5. Relationship counts
            report.checks.extend(self._validate_relationship_counts())

            # 6. Constraint validation
            report.checks.extend(self._validate_constraints())

        finally:
            self.close()

        return report

    def _validate_node_labels(self) -> list[ValidationCheck]:
        """Verify all expected node labels exist in Neo4j."""
        checks = []
        with self.driver.session() as session:
            # Get all labels in database
            result = session.run("CALL db.labels()")
            db_labels = {record[0] for record in result}

            for class_name in self.ontology.classes:
                label = self._get_neo4j_label(class_name)
                exists = label in db_labels

                checks.append(
                    ValidationCheck(
                        category="node_label",
                        name=class_name,
                        passed=exists,
                        message=f"Label '{label}' exists" if exists else f"Label '{label}' not found",
                        expected=label,
                        actual=label if exists else None,
                    )
                )

        return checks

    def _validate_node_counts(self) -> list[ValidationCheck]:
        """Verify node counts match ontology expectations."""
        checks = []
        with self.driver.session() as session:
            for class_name in self.ontology.classes:
                expected = self.ontology.get_class_row_count(class_name)
                if expected is None:
                    continue  # Skip classes without row_count annotation

                label = self._get_neo4j_label(class_name)
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                actual = result.single()["count"]

                passed = actual == expected
                checks.append(
                    ValidationCheck(
                        category="node_count",
                        name=class_name,
                        passed=passed,
                        message=f"{actual} nodes" if passed else f"{actual} nodes (expected {expected})",
                        expected=expected,
                        actual=actual,
                    )
                )

        return checks

    def _validate_relationship_types(self) -> list[ValidationCheck]:
        """Verify all expected relationship types exist in Neo4j."""
        checks = []
        with self.driver.session() as session:
            # Get all relationship types in database
            result = session.run("CALL db.relationshipTypes()")
            db_rel_types = {record[0] for record in result}

            for role_name in self.ontology.roles:
                rel_type = self._get_neo4j_rel_type(role_name)
                exists = rel_type in db_rel_types

                checks.append(
                    ValidationCheck(
                        category="relationship_type",
                        name=role_name,
                        passed=exists,
                        message=f"Type '{rel_type}' exists" if exists else f"Type '{rel_type}' not found",
                        expected=rel_type,
                        actual=rel_type if exists else None,
                    )
                )

        return checks

    def _validate_relationship_endpoints(self) -> list[ValidationCheck]:
        """Verify relationship endpoints match domain/range declarations."""
        checks = []
        with self.driver.session() as session:
            for role_name in self.ontology.roles:
                rel_type = self._get_neo4j_rel_type(role_name)
                domain_class = self.ontology.get_role_domain(role_name)
                range_class = self.ontology.get_role_range(role_name)
                domain_label = self._get_neo4j_label(domain_class)
                range_label = self._get_neo4j_label(range_class)

                # Find violations where endpoints don't match expected labels
                query = f"""
                    MATCH (a)-[r:{rel_type}]->(b)
                    WHERE NOT a:{domain_label} OR NOT b:{range_label}
                    RETURN count(*) as violations,
                           collect(DISTINCT labels(a))[0..5] as bad_source_labels,
                           collect(DISTINCT labels(b))[0..5] as bad_target_labels
                """
                result = session.run(query)
                record = result.single()
                violations = record["violations"]
                bad_sources = record["bad_source_labels"] or []
                bad_targets = record["bad_target_labels"] or []

                passed = violations == 0
                details = []
                if not passed:
                    if bad_sources:
                        details.append(f"Unexpected source labels: {bad_sources}")
                    if bad_targets:
                        details.append(f"Unexpected target labels: {bad_targets}")

                checks.append(
                    ValidationCheck(
                        category="relationship_endpoint",
                        name=role_name,
                        passed=passed,
                        message=f"Endpoints {domain_label} -> {range_label}"
                        if passed
                        else f"{violations} endpoint violations",
                        expected=f"{domain_label} -> {range_label}",
                        actual=f"{violations} violations",
                        details=details,
                    )
                )

        return checks

    def _validate_relationship_counts(self) -> list[ValidationCheck]:
        """Verify relationship counts match ontology expectations."""
        checks = []
        with self.driver.session() as session:
            for role_name in self.ontology.roles:
                expected = self.ontology.get_role_row_count(role_name)
                if expected is None:
                    continue  # Skip roles without row_count annotation

                rel_type = self._get_neo4j_rel_type(role_name)
                result = session.run(
                    f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
                )
                actual = result.single()["count"]

                passed = actual == expected
                checks.append(
                    ValidationCheck(
                        category="relationship_count",
                        name=role_name,
                        passed=passed,
                        message=f"{actual} edges" if passed else f"{actual} edges (expected {expected})",
                        expected=expected,
                        actual=actual,
                    )
                )

        return checks

    def _validate_constraints(self) -> list[ValidationCheck]:
        """Validate OWL-like constraint properties (irreflexive, asymmetric)."""
        checks = []
        with self.driver.session() as session:
            for role_name in self.ontology.roles:
                props = self.ontology.get_role_properties(role_name)
                rel_type = self._get_neo4j_rel_type(role_name)

                # Irreflexive check (no self-loops)
                if props.get("irreflexive"):
                    query = f"""
                        MATCH (a)-[r:{rel_type}]->(a)
                        RETURN count(*) as self_loops
                    """
                    result = session.run(query)
                    self_loops = result.single()["self_loops"]
                    passed = self_loops == 0

                    checks.append(
                        ValidationCheck(
                            category="constraint_irreflexive",
                            name=role_name,
                            passed=passed,
                            message="No self-loops" if passed else f"{self_loops} self-loops found",
                            expected=0,
                            actual=self_loops,
                        )
                    )

                # Asymmetric check (no bidirectional edges)
                if props.get("asymmetric"):
                    query = f"""
                        MATCH (a)-[r1:{rel_type}]->(b)-[r2:{rel_type}]->(a)
                        RETURN count(*) / 2 as bidirectional
                    """
                    result = session.run(query)
                    bidirectional = result.single()["bidirectional"]
                    passed = bidirectional == 0

                    checks.append(
                        ValidationCheck(
                            category="constraint_asymmetric",
                            name=role_name,
                            passed=passed,
                            message="No bidirectional edges"
                            if passed
                            else f"{bidirectional} bidirectional pairs found",
                            expected=0,
                            actual=bidirectional,
                        )
                    )

        return checks


def print_report(report: ValidationReport):
    """Print human-readable validation report."""
    print()
    print("Neo4j Graph Validation Report")
    print("=" * 50)
    print(f"Ontology: {report.ontology_name} v{report.ontology_version}")
    print(f"Database: {report.database_uri}")
    print()

    # Group checks by category
    categories = {
        "node_label": "Node Labels",
        "node_count": "Node Counts",
        "relationship_type": "Relationship Types",
        "relationship_endpoint": "Relationship Endpoints",
        "relationship_count": "Relationship Counts",
        "constraint_irreflexive": "Constraints (Irreflexive)",
        "constraint_asymmetric": "Constraints (Asymmetric)",
    }

    for cat_key, cat_name in categories.items():
        cat_checks = [c for c in report.checks if c.category == cat_key]
        if not cat_checks:
            continue

        print(f"{cat_name}")
        print("-" * 50)
        for check in cat_checks:
            status = "[pass]" if check.passed else "[FAIL]"
            print(f"  {status} {check.name}: {check.message}")
            for detail in check.details:
                print(f"         {detail}")
        print()

    # Summary
    print("Summary")
    print("-" * 50)
    print(f"Passed: {report.passed_count}/{report.total_count} checks")
    if report.failed_count > 0:
        print(f"Failed: {report.failed_count} checks")
    print()

    if report.all_passed:
        print("[pass] All validations passed")
    else:
        print("[FAIL] Validation failed")


def main():
    parser = argparse.ArgumentParser(
        description="Validate Neo4j graph against ontology definition"
    )
    parser.add_argument(
        "ontology_path",
        nargs="?",
        type=Path,
        default=Path(__file__).parent.parent / "supply_chain_example" / "ontology" / "supply_chain.yaml",
        help="Path to ontology YAML file (default: supply_chain_example/ontology/supply_chain.yaml)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--neo4j-uri",
        default=NEO4J_URI,
        help=f"Neo4j URI (default: {NEO4J_URI})",
    )

    args = parser.parse_args()

    validator = Neo4jValidator(
        ontology_path=args.ontology_path, neo4j_uri=args.neo4j_uri
    )

    try:
        report = validator.validate_all()
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report)

    # Exit with non-zero status if any checks failed
    sys.exit(0 if report.all_passed else 1)


if __name__ == "__main__":
    main()
