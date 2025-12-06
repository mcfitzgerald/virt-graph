"""
Ontology accessor for TBox/RBox format.

Provides a stable API for accessing ontology data regardless of
underlying YAML format changes.
"""

from pathlib import Path
from typing import Optional

import yaml


class OntologyAccessor:
    """
    Abstraction layer for accessing TBox/RBox ontology structure.

    Provides a stable API regardless of underlying YAML format changes.
    The TBox (Terminological Box) contains class definitions.
    The RBox (Role Box) contains relationship/role definitions.

    Usage:
        ontology = OntologyAccessor()  # Uses default path
        ontology = OntologyAccessor(Path("custom/ontology.yaml"))

        # Access classes
        table = ontology.get_class_table("Supplier")
        pk = ontology.get_class_pk("Supplier")

        # Access roles (relationships)
        domain_key, range_key = ontology.get_role_keys("supplies_to")
        complexity = ontology.get_role_complexity("supplies_to")
    """

    def __init__(self, ontology_path: Optional[Path] = None):
        """
        Initialize the ontology accessor.

        Args:
            ontology_path: Path to ontology YAML file. If None, uses default
                           location at ontology/supply_chain.yaml
        """
        if ontology_path is None:
            ontology_path = (
                Path(__file__).parent.parent.parent / "ontology" / "supply_chain.yaml"
            )
        with open(ontology_path) as f:
            self._data = yaml.safe_load(f)

    # === Meta ===
    @property
    def name(self) -> str:
        """Get ontology name."""
        return self._data["meta"]["name"]

    @property
    def version(self) -> str:
        """Get ontology version."""
        return self._data["meta"]["version"]

    @property
    def database(self) -> dict:
        """Get database connection info."""
        return self._data["meta"]["database"]

    # === TBox: Classes ===
    @property
    def classes(self) -> dict:
        """Get all class definitions."""
        return self._data["tbox"]["classes"]

    def get_class(self, name: str) -> dict:
        """Get a class definition by name."""
        return self._data["tbox"]["classes"][name]

    def get_class_table(self, name: str) -> str:
        """Get the SQL table name for a class."""
        return self._data["tbox"]["classes"][name]["sql"]["table"]

    def get_class_pk(self, name: str) -> str:
        """Get the primary key column for a class."""
        return self._data["tbox"]["classes"][name]["sql"]["primary_key"]

    def get_class_identifier(self, name: str) -> list[str]:
        """Get natural key columns for a class."""
        return self._data["tbox"]["classes"][name]["sql"].get("identifier", [])

    def get_class_soft_delete(self, name: str) -> tuple[bool, Optional[str]]:
        """
        Get soft delete configuration for a class.

        Returns:
            Tuple of (enabled, column_name). Column is None if not enabled.
        """
        cls = self._data["tbox"]["classes"][name]
        soft_delete = cls.get("soft_delete", {})
        return soft_delete.get("enabled", False), soft_delete.get("column")

    def get_class_slots(self, name: str) -> dict:
        """Get attribute slots for a class."""
        return self._data["tbox"]["classes"][name].get("slots", {})

    def get_class_row_count(self, name: str) -> Optional[int]:
        """Get estimated row count for a class."""
        return self._data["tbox"]["classes"][name].get("row_count")

    # === RBox: Roles (Relationships) ===
    @property
    def roles(self) -> dict:
        """Get all role definitions."""
        return self._data["rbox"]["roles"]

    def get_role(self, name: str) -> dict:
        """Get a role definition by name."""
        return self._data["rbox"]["roles"][name]

    def get_role_sql(self, name: str) -> dict:
        """Get full SQL mapping for a role."""
        return self._data["rbox"]["roles"][name]["sql"]

    def get_role_table(self, name: str) -> str:
        """Get the edge table name for a role."""
        return self._data["rbox"]["roles"][name]["sql"]["table"]

    def get_role_keys(self, name: str) -> tuple[str, str]:
        """
        Get FK columns for a role.

        Returns:
            Tuple of (domain_key, range_key)
        """
        sql = self._data["rbox"]["roles"][name]["sql"]
        return sql["domain_key"], sql["range_key"]

    def get_role_domain(self, name: str) -> str:
        """Get domain class for a role."""
        return self._data["rbox"]["roles"][name]["domain"]

    def get_role_range(self, name: str) -> str:
        """Get range class for a role."""
        return self._data["rbox"]["roles"][name]["range"]

    def get_role_complexity(self, name: str) -> str:
        """Get traversal complexity (GREEN/YELLOW/RED) for a role."""
        return self._data["rbox"]["roles"][name]["traversal_complexity"]

    def get_role_properties(self, name: str) -> dict:
        """
        Get OWL 2 properties for a role.

        Properties include: transitive, symmetric, asymmetric, reflexive,
        irreflexive, functional, inverse_functional, acyclic, is_hierarchical,
        is_weighted.
        """
        return self._data["rbox"]["roles"][name].get("properties", {})

    def get_role_cardinality(self, name: str) -> dict:
        """
        Get cardinality constraints for a role.

        Returns:
            Dict with 'domain' and 'range' keys using notation like "0..*", "1..1"
        """
        return self._data["rbox"]["roles"][name].get("cardinality", {})

    def get_role_weight_columns(self, name: str) -> list[dict]:
        """
        Get weight columns for a role (for weighted edges).

        Returns:
            List of dicts with 'name' and 'type' keys
        """
        return self._data["rbox"]["roles"][name]["sql"].get("weight_columns", [])

    def get_role_row_count(self, name: str) -> Optional[int]:
        """Get estimated edge count for a role."""
        return self._data["rbox"]["roles"][name].get("row_count")

    # === Utility Methods ===
    def is_role_transitive(self, name: str) -> bool:
        """Check if a role has transitive property."""
        return self.get_role_properties(name).get("transitive", False)

    def is_role_symmetric(self, name: str) -> bool:
        """Check if a role has symmetric property."""
        return self.get_role_properties(name).get("symmetric", False)

    def is_role_acyclic(self, name: str) -> bool:
        """Check if a role is acyclic (DAG)."""
        return self.get_role_properties(name).get("acyclic", False)

    def is_role_hierarchical(self, name: str) -> bool:
        """Check if a role represents a hierarchy."""
        return self.get_role_properties(name).get("is_hierarchical", False)

    def is_role_weighted(self, name: str) -> bool:
        """Check if a role has weighted edges."""
        return self.get_role_properties(name).get("is_weighted", False)

    def get_role_inverse(self, name: str) -> Optional[str]:
        """Get inverse role name if defined."""
        return self.get_role_properties(name).get("inverse_of")

    # === Raw access (for advanced use) ===
    @property
    def raw(self) -> dict:
        """Access raw ontology dict for advanced use cases."""
        return self._data


# Convenience function for one-off access
def load_ontology(path: Optional[Path] = None) -> OntologyAccessor:
    """Load and return an OntologyAccessor instance."""
    return OntologyAccessor(path)
