"""
Ontology accessor for LinkML format with Virtual Graph extensions.

Provides a stable API abstracting over the LinkML structure,
presenting logical TBox (classes) and RBox (roles) views.

Validation rules are derived from the VG metamodel (ontology/virt_graph.yaml)
using LinkML's SchemaView, making the metamodel the single source of truth.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from linkml_runtime.utils.schemaview import SchemaView


@dataclass
class ValidationError:
    """A validation error for a schema element."""

    element_type: str  # "class" or "relationship"
    element_name: str
    field: str
    message: str

    def __str__(self):
        return f"{self.element_type} '{self.element_name}': {self.field} - {self.message}"


class OntologyValidationError(Exception):
    """Raised when ontology fails VG annotation validation."""

    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        message = f"Ontology validation failed with {len(errors)} error(s):\n"
        message += "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


class OntologyAccessor:
    """
    Abstraction layer for LinkML ontology with VG extensions.

    Automatically distinguishes:
    - Entity classes (instantiates vg:SQLMappedClass) → TBox
    - Relationship classes (instantiates vg:SQLMappedRelationship) → RBox

    Validates VG-specific annotations on construction.

    Usage:
        ontology = OntologyAccessor()  # Uses default path
        ontology = OntologyAccessor(Path("custom/ontology.yaml"))

        # Access classes (TBox)
        table = ontology.get_class_table("Supplier")
        pk = ontology.get_class_pk("Supplier")

        # Access roles (RBox - relationships)
        domain_key, range_key = ontology.get_role_keys("SuppliesTo")
        complexity = ontology.get_role_complexity("SuppliesTo")
    """

    VG_ENTITY = "vg:SQLMappedClass"
    VG_RELATIONSHIP = "vg:SQLMappedRelationship"

    # Class-level cache for metamodel rules (loaded once per process)
    _metamodel_loaded: bool = False
    _entity_required: set[str] = set()
    _relationship_required: set[str] = set()
    _valid_complexities: set[str] = set()

    def __init__(self, ontology_path: Optional[Path] = None, validate: bool = True):
        """
        Load and optionally validate a LinkML ontology with VG extensions.

        Args:
            ontology_path: Path to ontology YAML file. If None, uses default
                           location at ontology/supply_chain.yaml
            validate: If True, validate VG annotations on load (default: True)

        Raises:
            OntologyValidationError: If validation is enabled and fails
        """
        # Load metamodel rules from virt_graph.yaml (once per process)
        self._load_metamodel_rules()

        if ontology_path is None:
            ontology_path = (
                Path(__file__).parent.parent.parent / "ontology" / "supply_chain.yaml"
            )
        with open(ontology_path) as f:
            self._data = yaml.safe_load(f)

        # Build TBox/RBox indices
        self._tbox: dict[str, dict] = {}
        self._rbox: dict[str, dict] = {}
        self._index_classes()

        # Validate VG annotations
        if validate:
            errors = self.validate()
            if errors:
                raise OntologyValidationError(errors)

    @classmethod
    def _load_metamodel_rules(cls) -> None:
        """
        Load validation rules from virt_graph.yaml via SchemaView.

        This makes virt_graph.yaml the single source of truth for:
        - Required fields for SQLMappedClass (entity classes)
        - Required fields for SQLMappedRelationship (relationship classes)
        - Valid values for TraversalComplexity enum

        Rules are cached at class level and loaded once per process.
        """
        if cls._metamodel_loaded:
            return

        metamodel_path = (
            Path(__file__).parent.parent.parent / "ontology" / "virt_graph.yaml"
        )
        sv = SchemaView(str(metamodel_path))

        # Extract required fields from SQLMappedClass
        cls._entity_required = {
            slot
            for slot in sv.class_slots("SQLMappedClass")
            if sv.induced_slot(slot, "SQLMappedClass").required
        }

        # Extract required fields from SQLMappedRelationship
        cls._relationship_required = {
            slot
            for slot in sv.class_slots("SQLMappedRelationship")
            if sv.induced_slot(slot, "SQLMappedRelationship").required
        }

        # Extract valid enum values for TraversalComplexity
        complexity_enum = sv.get_enum("TraversalComplexity")
        cls._valid_complexities = set(complexity_enum.permissible_values.keys())

        cls._metamodel_loaded = True

    def _index_classes(self):
        """Partition classes into TBox (entities) and RBox (relationships)."""
        for name, cls in self._data.get("classes", {}).items():
            instantiates = cls.get("instantiates", [])
            if self.VG_RELATIONSHIP in instantiates:
                self._rbox[name] = cls
            elif self.VG_ENTITY in instantiates:
                self._tbox[name] = cls
            # Classes without VG instantiates are ignored or could be base classes

        # Build snake_case aliases for backward compatibility
        # e.g., "SuppliesTo" -> "supplies_to"
        self._role_aliases: dict[str, str] = {}
        for name in self._rbox:
            snake = self._pascal_to_snake(name)
            if snake != name:
                self._role_aliases[snake] = name

    def _pascal_to_snake(self, name: str) -> str:
        """Convert PascalCase to snake_case."""
        import re
        # Insert underscore before uppercase letters and lowercase
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    def _resolve_role_name(self, name: str) -> str:
        """Resolve role name, handling snake_case aliases."""
        if name in self._rbox:
            return name
        if name in self._role_aliases:
            return self._role_aliases[name]
        raise KeyError(f"Unknown role: {name}")

    def _get_annotation(self, cls: dict, key: str, default=None):
        """Get a vg: annotation value."""
        annotations = cls.get("annotations", {})
        # Try with vg: prefix first, then without
        return annotations.get(f"vg:{key}", annotations.get(key, default))

    def _get_all_annotations(self, cls: dict) -> set[str]:
        """Get all annotation keys (stripped of vg: prefix)."""
        annotations = cls.get("annotations", {})
        result = set()
        for key in annotations:
            if key.startswith("vg:"):
                result.add(key[3:])  # Strip vg: prefix
            else:
                result.add(key)
        return result

    def _parse_json_or_value(self, value, default=None):
        """Parse JSON string or return value as-is."""
        if value is None:
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate(self) -> list[ValidationError]:
        """
        Validate VG-specific annotations for all classes.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        errors.extend(self._validate_entities())
        errors.extend(self._validate_relationships())
        return errors

    def _validate_entities(self) -> list[ValidationError]:
        """Validate SQLMappedClass annotations."""
        errors = []
        for name, cls in self._tbox.items():
            present = self._get_all_annotations(cls)
            missing = self._entity_required - present
            for field in missing:
                errors.append(
                    ValidationError(
                        element_type="class",
                        element_name=name,
                        field=field,
                        message=f"required annotation 'vg:{field}' is missing",
                    )
                )
        return errors

    def _validate_relationships(self) -> list[ValidationError]:
        """Validate SQLMappedRelationship annotations."""
        errors = []
        for name, cls in self._rbox.items():
            present = self._get_all_annotations(cls)

            # Check required fields
            missing = self._relationship_required - present
            for field in missing:
                errors.append(
                    ValidationError(
                        element_type="relationship",
                        element_name=name,
                        field=field,
                        message=f"required annotation 'vg:{field}' is missing",
                    )
                )

            # Validate traversal_complexity value
            complexity = self._get_annotation(cls, "traversal_complexity")
            if complexity and complexity not in self._valid_complexities:
                errors.append(
                    ValidationError(
                        element_type="relationship",
                        element_name=name,
                        field="traversal_complexity",
                        message=f"invalid value '{complexity}', must be one of {self._valid_complexities}",
                    )
                )

            # Validate domain_class references a known entity
            domain_class = self._get_annotation(cls, "domain_class")
            if domain_class and domain_class not in self._tbox:
                errors.append(
                    ValidationError(
                        element_type="relationship",
                        element_name=name,
                        field="domain_class",
                        message=f"references unknown class '{domain_class}'",
                    )
                )

            # Validate range_class references a known entity
            range_class = self._get_annotation(cls, "range_class")
            if range_class and range_class not in self._tbox:
                errors.append(
                    ValidationError(
                        element_type="relationship",
                        element_name=name,
                        field="range_class",
                        message=f"references unknown class '{range_class}'",
                    )
                )

        return errors

    # =========================================================================
    # TBox: Classes (Entity Tables)
    # =========================================================================

    @property
    def classes(self) -> dict:
        """Get all entity class definitions (TBox)."""
        return self._tbox

    def get_class(self, name: str) -> dict:
        """Get an entity class definition by name."""
        return self._tbox[name]

    def get_class_table(self, name: str) -> str:
        """Get the SQL table name for a class."""
        return self._get_annotation(self._tbox[name], "table")

    def get_class_pk(self, name: str) -> str:
        """Get the primary key column for a class."""
        return self._get_annotation(self._tbox[name], "primary_key")

    def get_class_identifier(self, name: str) -> list[str]:
        """Get natural key columns for a class (may be JSON string or list)."""
        value = self._get_annotation(self._tbox[name], "identifier", [])
        return self._parse_json_or_value(value, [])

    def get_class_soft_delete(self, name: str) -> tuple[bool, Optional[str]]:
        """
        Get soft delete configuration for a class.

        Returns:
            Tuple of (enabled, column_name). Column is None if not enabled.
        """
        column = self._get_annotation(self._tbox[name], "soft_delete_column")
        return (column is not None, column)

    def get_class_slots(self, name: str) -> dict:
        """Get attribute definitions for a class."""
        return self._tbox[name].get("attributes", {})

    def get_class_row_count(self, name: str) -> Optional[int]:
        """Get estimated row count for a class."""
        return self._get_annotation(self._tbox[name], "row_count")

    # =========================================================================
    # RBox: Roles (Relationships)
    # =========================================================================

    @property
    def roles(self) -> dict:
        """Get all relationship definitions (RBox)."""
        return self._rbox

    def get_role(self, name: str) -> dict:
        """Get a relationship definition by name."""
        resolved = self._resolve_role_name(name)
        return self._rbox[resolved]

    def get_role_sql(self, name: str) -> dict:
        """
        Get SQL mapping for a role (reconstructed from annotations).

        Returns dict with: table, domain_key, range_key, weight_columns, additional_columns
        """
        resolved = self._resolve_role_name(name)
        cls = self._rbox[resolved]

        # Get attribute names as additional columns (edge properties)
        attributes = cls.get("attributes", {})
        additional_columns = list(attributes.keys())

        return {
            "table": self._get_annotation(cls, "edge_table"),
            "domain_key": self._get_annotation(cls, "domain_key"),
            "range_key": self._get_annotation(cls, "range_key"),
            "weight_columns": self.get_role_weight_columns(resolved),
            "additional_columns": additional_columns,
        }

    def get_role_table(self, name: str) -> str:
        """Get the edge table name for a role."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "edge_table")

    def get_role_keys(self, name: str) -> tuple[str, str]:
        """
        Get FK columns for a role.

        Returns:
            Tuple of (domain_key, range_key)
        """
        resolved = self._resolve_role_name(name)
        cls = self._rbox[resolved]
        return (
            self._get_annotation(cls, "domain_key"),
            self._get_annotation(cls, "range_key"),
        )

    def get_role_domain(self, name: str) -> str:
        """Get domain class name for a role."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "domain_class")

    def get_role_range(self, name: str) -> str:
        """Get range class name for a role."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "range_class")

    def get_role_complexity(self, name: str) -> str:
        """Get traversal complexity (GREEN/YELLOW/RED) for a role."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "traversal_complexity")

    def get_role_properties(self, name: str) -> dict:
        """
        Get OWL 2 and VG extension properties for a role.

        Returns dict with boolean flags: transitive, symmetric, asymmetric,
        reflexive, irreflexive, functional, inverse_functional, acyclic,
        is_hierarchical, is_weighted.
        """
        resolved = self._resolve_role_name(name)
        cls = self._rbox[resolved]
        return {
            "transitive": self._get_annotation(cls, "transitive", False),
            "symmetric": self._get_annotation(cls, "symmetric", False),
            "asymmetric": self._get_annotation(cls, "asymmetric", False),
            "reflexive": self._get_annotation(cls, "reflexive", False),
            "irreflexive": self._get_annotation(cls, "irreflexive", False),
            "functional": self._get_annotation(cls, "functional", False),
            "inverse_functional": self._get_annotation(cls, "inverse_functional", False),
            "acyclic": self._get_annotation(cls, "acyclic", False),
            "is_hierarchical": self._get_annotation(cls, "is_hierarchical", False),
            "is_weighted": self._get_annotation(cls, "is_weighted", False),
            "inverse_of": self._get_annotation(cls, "inverse_of"),
        }

    def get_role_cardinality(self, name: str) -> dict:
        """
        Get cardinality constraints for a role.

        Returns:
            Dict with 'domain' and 'range' keys using notation like "0..*", "1..1"
        """
        resolved = self._resolve_role_name(name)
        cls = self._rbox[resolved]
        return {
            "domain": self._get_annotation(cls, "cardinality_domain", "0..*"),
            "range": self._get_annotation(cls, "cardinality_range", "0..*"),
        }

    def get_role_weight_columns(self, name: str) -> list[dict]:
        """
        Get weight columns for a role (for weighted edges).

        Returns:
            List of dicts with 'name' and 'type' keys
        """
        resolved = self._resolve_role_name(name)
        value = self._get_annotation(self._rbox[resolved], "weight_columns", [])
        return self._parse_json_or_value(value, [])

    def get_role_row_count(self, name: str) -> Optional[int]:
        """Get estimated edge count for a role."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "row_count")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def is_role_transitive(self, name: str) -> bool:
        """Check if a role has transitive property."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "transitive", False)

    def is_role_symmetric(self, name: str) -> bool:
        """Check if a role has symmetric property."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "symmetric", False)

    def is_role_asymmetric(self, name: str) -> bool:
        """Check if a role has asymmetric property."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "asymmetric", False)

    def is_role_acyclic(self, name: str) -> bool:
        """Check if a role is acyclic (DAG)."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "acyclic", False)

    def is_role_hierarchical(self, name: str) -> bool:
        """Check if a role represents a hierarchy."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "is_hierarchical", False)

    def is_role_weighted(self, name: str) -> bool:
        """Check if a role has weighted edges."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "is_weighted", False)

    def get_role_inverse(self, name: str) -> Optional[str]:
        """Get inverse role name if defined."""
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "inverse_of")

    # =========================================================================
    # Schema-level metadata
    # =========================================================================

    @property
    def name(self) -> str:
        """Get ontology name."""
        return self._data.get("name", "unknown")

    @property
    def version(self) -> str:
        """Get ontology version."""
        return self._data.get("version", "0.0")

    @property
    def database(self) -> dict:
        """Get database connection info from schema annotations."""
        annotations = self._data.get("annotations", {})
        return {
            "type": annotations.get("vg:database_type", "postgresql"),
            "version": annotations.get("vg:database_version"),
            "connection": annotations.get("vg:connection_string"),
        }

    # =========================================================================
    # Raw access (for advanced use)
    # =========================================================================

    @property
    def raw(self) -> dict:
        """Access raw ontology dict for advanced use cases."""
        return self._data


# Convenience function for one-off access
def load_ontology(path: Optional[Path] = None, validate: bool = True) -> OntologyAccessor:
    """Load and return an OntologyAccessor instance."""
    return OntologyAccessor(path, validate=validate)
