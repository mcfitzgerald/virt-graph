"""
Ontology accessor for LinkML format with Virtual Graph extensions.

Provides a stable API abstracting over the LinkML structure,
presenting logical TBox (classes) and RBox (roles) views.

Validation rules are derived from the VG metamodel (virt_graph.yaml)
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
        ontology = OntologyAccessor(Path("path/to/ontology.yaml"))

        # Access classes (TBox)
        table = ontology.get_class_table("Supplier")
        pk = ontology.get_class_pk("Supplier")

        # Access roles (RBox - relationships)
        domain_key, range_key = ontology.get_role_keys("SuppliesTo")
        op_types = ontology.get_operation_types("SuppliesTo")
    """

    VG_ENTITY = "vg:SQLMappedClass"
    VG_RELATIONSHIP = "vg:SQLMappedRelationship"

    # Class-level cache for metamodel rules (loaded once per process)
    _metamodel_loaded: bool = False
    _entity_required: set[str] = set()
    _relationship_required: set[str] = set()
    _valid_operation_categories: set[str] = set()
    _valid_operation_types: set[str] = set()

    # Mapping from OperationType to OperationCategory
    _operation_type_to_category: dict[str, str] = {
        "direct_join": "direct",
        "recursive_traversal": "traversal",
        "temporal_traversal": "temporal",
        "path_aggregation": "aggregation",
        "hierarchical_aggregation": "aggregation",
        "shortest_path": "algorithm",
        "centrality": "algorithm",
        "connected_components": "algorithm",
        "resilience_analysis": "algorithm",
    }

    def __init__(self, ontology_path: Path, validate: bool = True):
        """
        Load and optionally validate a LinkML ontology with VG extensions.

        Args:
            ontology_path: Path to ontology YAML file (required)
            validate: If True, validate VG annotations on load (default: True)

        Raises:
            ValueError: If ontology_path is not provided
            OntologyValidationError: If validation is enabled and fails
        """
        if ontology_path is None:
            raise ValueError("ontology_path is required")

        # Load metamodel rules from virt_graph.yaml (once per process)
        self._load_metamodel_rules()
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
        - Valid values for OperationType and OperationCategory enums

        Rules are cached at class level and loaded once per process.
        """
        if cls._metamodel_loaded:
            return

        metamodel_path = Path(__file__).parent.parent.parent / "virt_graph.yaml"
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

        # Extract valid enum values for OperationCategory
        category_enum = sv.get_enum("OperationCategory")
        cls._valid_operation_categories = set(category_enum.permissible_values.keys())

        # Extract valid enum values for OperationType
        type_enum = sv.get_enum("OperationType")
        cls._valid_operation_types = set(type_enum.permissible_values.keys())

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

    def _normalize_to_list(self, value) -> list:
        """
        Normalize a value to a list.

        Handles string (single value), JSON array string, or list.
        Returns empty list for None.

        Args:
            value: String, JSON array string, list, or None

        Returns:
            List of values
        """
        if value is None:
            return []
        parsed = self._parse_json_or_value(value)
        if isinstance(parsed, str):
            return [parsed]
        if isinstance(parsed, list):
            return parsed
        return [parsed]

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

            # Validate operation_types values
            op_types = self._get_annotation(cls, "operation_types")
            if op_types:
                parsed_types = self._parse_json_or_value(op_types, [])
                if isinstance(parsed_types, list):
                    for op_type in parsed_types:
                        if op_type not in self._valid_operation_types:
                            errors.append(
                                ValidationError(
                                    element_type="relationship",
                                    element_name=name,
                                    field="operation_types",
                                    message=f"invalid operation type '{op_type}', must be one of {self._valid_operation_types}",
                                )
                            )

            # Validate temporal_bounds structure if present
            temporal_bounds = self._get_annotation(cls, "temporal_bounds")
            if temporal_bounds:
                parsed_bounds = self._parse_json_or_value(temporal_bounds, {})
                if isinstance(parsed_bounds, dict):
                    if "start_col" not in parsed_bounds:
                        errors.append(
                            ValidationError(
                                element_type="relationship",
                                element_name=name,
                                field="temporal_bounds",
                                message="missing required field 'start_col'",
                            )
                        )
                    if "end_col" not in parsed_bounds:
                        errors.append(
                            ValidationError(
                                element_type="relationship",
                                element_name=name,
                                field="temporal_bounds",
                                message="missing required field 'end_col'",
                            )
                        )

            # Validate domain_class references known entities (supports lists for polymorphism)
            domain_class_value = self._get_annotation(cls, "domain_class")
            domain_classes = self._normalize_to_list(domain_class_value)
            for dc in domain_classes:
                if dc and dc not in self._tbox:
                    errors.append(
                        ValidationError(
                            element_type="relationship",
                            element_name=name,
                            field="domain_class",
                            message=f"references unknown class '{dc}'",
                        )
                    )

            # Validate range_class references known entities (supports lists for polymorphism)
            range_class_value = self._get_annotation(cls, "range_class")
            range_classes = self._normalize_to_list(range_class_value)
            for rc in range_classes:
                if rc and rc not in self._tbox:
                    errors.append(
                        ValidationError(
                            element_type="relationship",
                            element_name=name,
                            field="range_class",
                            message=f"references unknown class '{rc}'",
                        )
                    )

            # Validate type_discriminator if present
            type_disc = self._get_annotation(cls, "type_discriminator")
            if type_disc:
                parsed_disc = self._parse_json_or_value(type_disc, {})
                if isinstance(parsed_disc, dict):
                    # Validate required 'column' field
                    if "column" not in parsed_disc:
                        errors.append(
                            ValidationError(
                                element_type="relationship",
                                element_name=name,
                                field="type_discriminator",
                                message="missing required field 'column'",
                            )
                        )
                    # Validate mapping keys match range_class values
                    mapping = parsed_disc.get("mapping")
                    if mapping and isinstance(mapping, dict):
                        mapping_classes = set(mapping.values())
                        unknown_classes = mapping_classes - set(range_classes)
                        if unknown_classes:
                            errors.append(
                                ValidationError(
                                    element_type="relationship",
                                    element_name=name,
                                    field="type_discriminator",
                                    message=f"mapping references classes not in range_class: {unknown_classes}",
                                )
                            )

            # Basic SQL injection check for sql_filter
            sql_filter = self._get_annotation(cls, "sql_filter")
            if sql_filter:
                # Check for dangerous patterns (basic check, not exhaustive)
                dangerous_patterns = ["--", ";", "/*", "*/", "xp_", "exec ", "execute "]
                filter_lower = sql_filter.lower()
                for pattern in dangerous_patterns:
                    if pattern in filter_lower:
                        errors.append(
                            ValidationError(
                                element_type="relationship",
                                element_name=name,
                                field="sql_filter",
                                message=f"contains potentially dangerous pattern '{pattern}'",
                            )
                        )
                        break

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

    def get_class_pk(self, name: str) -> list[str]:
        """
        Get the primary key column(s) for a class.

        Returns a list for consistency - single-column keys return a
        single-element list.

        Args:
            name: Class name

        Returns:
            List of primary key column names

        Example:
            >>> ontology.get_class_pk("Supplier")
            ['id']
            >>> ontology.get_class_pk("OrderLineItem")
            ['order_id', 'line_number']
        """
        value = self._get_annotation(self._tbox[name], "primary_key")
        return self._normalize_to_list(value)

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

    def get_role_keys(self, name: str) -> tuple[list[str], list[str]]:
        """
        Get FK columns for a role.

        Returns lists for composite key support. Single-column keys
        return single-element lists.

        Args:
            name: Role name

        Returns:
            Tuple of (domain_keys, range_keys) as lists

        Example:
            >>> ontology.get_role_keys("SuppliesTo")
            (['seller_id'], ['buyer_id'])
            >>> ontology.get_role_keys("OrderLineHasProduct")
            (['order_id', 'line_number'], ['product_id'])
        """
        resolved = self._resolve_role_name(name)
        cls = self._rbox[resolved]
        return (
            self._normalize_to_list(self._get_annotation(cls, "domain_key")),
            self._normalize_to_list(self._get_annotation(cls, "range_key")),
        )

    def get_role_domain(self, name: str) -> str:
        """
        Get primary domain class name for a role.

        For polymorphic relationships, returns the first domain class.
        Use get_role_domain_classes() for all classes.

        Args:
            name: Role name

        Returns:
            Primary domain class name
        """
        classes = self.get_role_domain_classes(name)
        return classes[0] if classes else None

    def get_role_range(self, name: str) -> str:
        """
        Get primary range class name for a role.

        For polymorphic relationships, returns the first range class.
        Use get_role_range_classes() for all classes.

        Args:
            name: Role name

        Returns:
            Primary range class name
        """
        classes = self.get_role_range_classes(name)
        return classes[0] if classes else None

    def get_role_domain_classes(self, name: str) -> list[str]:
        """
        Get all domain class names for a role.

        Returns a list for polymorphic relationships that can have
        multiple domain types.

        Args:
            name: Role name

        Returns:
            List of domain class names

        Example:
            >>> ontology.get_role_domain_classes("SuppliesTo")
            ['Supplier']
        """
        resolved = self._resolve_role_name(name)
        value = self._get_annotation(self._rbox[resolved], "domain_class")
        return self._normalize_to_list(value)

    def get_role_range_classes(self, name: str) -> list[str]:
        """
        Get all range class names for a role.

        Returns a list for polymorphic relationships that can target
        multiple entity types.

        Args:
            name: Role name

        Returns:
            List of range class names

        Example:
            >>> ontology.get_role_range_classes("OwnedBy")
            ['User', 'Organization']
        """
        resolved = self._resolve_role_name(name)
        value = self._get_annotation(self._rbox[resolved], "range_class")
        return self._normalize_to_list(value)

    def get_operation_types(self, name: str) -> list[str]:
        """Get operation types supported on this role.

        Returns list of operation type strings like:
        ["recursive_traversal", "temporal_traversal", "path_aggregation"]

        These map directly to handler functions for query execution.
        """
        resolved = self._resolve_role_name(name)
        value = self._get_annotation(self._rbox[resolved], "operation_types", [])
        return self._parse_json_or_value(value, [])

    def get_operation_category(self, op_type: str) -> str:
        """Get category for an operation type.

        Args:
            op_type: Operation type string (e.g., "recursive_traversal")

        Returns:
            Category string (e.g., "traversal", "algorithm", "direct")
        """
        return self._operation_type_to_category.get(op_type, "direct")

    def get_temporal_bounds(self, name: str) -> Optional[dict]:
        """Get temporal validity configuration for a role.

        Returns dict with 'start_col' and 'end_col' keys specifying
        which columns contain the validity period for edges.
        Returns None if the role does not have temporal bounds.
        """
        resolved = self._resolve_role_name(name)
        value = self._get_annotation(self._rbox[resolved], "temporal_bounds", None)
        if value is None:
            return None
        return self._parse_json_or_value(value, None)

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

    def get_role_context(self, name: str) -> Optional[dict]:
        """
        Get structured context for AI-assisted query generation for a role.

        Returns the ContextBlock with business_logic, llm_prompt_hint,
        traversal_semantics, and examples.

        Args:
            name: Role name

        Returns:
            Context dict or None if not set

        Example:
            >>> ctx = ontology.get_role_context("SuppliesTo")
            >>> ctx['business_logic']
            'Suppliers change tiers based on performance'
            >>> ctx['traversal_semantics']['inbound']
            'upstream suppliers'
        """
        resolved = self._resolve_role_name(name)
        value = self._get_annotation(self._rbox[resolved], "context")
        return self._parse_json_or_value(value, None)

    def get_class_context(self, name: str) -> Optional[dict]:
        """
        Get structured context for AI-assisted query generation for a class.

        Returns the ContextBlock with business_logic, llm_prompt_hint, and examples.

        Args:
            name: Class name

        Returns:
            Context dict or None if not set
        """
        value = self._get_annotation(self._tbox[name], "context")
        return self._parse_json_or_value(value, None)

    def get_role_filter(self, name: str) -> Optional[str]:
        """
        Get SQL filter clause for a role.

        Returns the sql_filter annotation which can be used to filter
        edges during traversal (e.g., 'is_active = true').

        Args:
            name: Role name

        Returns:
            SQL WHERE clause fragment or None if not set

        Example:
            >>> ontology.get_role_filter("ConnectsTo")
            "is_active = true AND status != 'suspended'"
        """
        resolved = self._resolve_role_name(name)
        return self._get_annotation(self._rbox[resolved], "sql_filter")

    def get_role_edge_attributes(self, name: str) -> list[dict]:
        """
        Get edge attribute definitions for Property Graph style edge properties.

        Returns list of EdgeAttribute dicts with name, type, and description.
        These are non-weight columns that should be retrieved as edge properties.

        Args:
            name: Role name

        Returns:
            List of edge attribute dicts

        Example:
            >>> ontology.get_role_edge_attributes("TransportRoute")
            [{'name': 'carrier', 'type': 'string'}, {'name': 'scheduled_date', 'type': 'date'}]
        """
        resolved = self._resolve_role_name(name)
        value = self._get_annotation(self._rbox[resolved], "edge_attributes", [])
        return self._parse_json_or_value(value, [])

    def get_role_type_discriminator(self, name: str) -> Optional[dict]:
        """
        Get type discriminator configuration for polymorphic relationships.

        Returns dict with 'column' (discriminator column name) and 'mapping'
        (dict mapping column values to class names).

        Args:
            name: Role name

        Returns:
            Type discriminator config dict or None if not set

        Example:
            >>> disc = ontology.get_role_type_discriminator("OwnedBy")
            >>> disc['column']
            'owner_type'
            >>> disc['mapping']
            {'user': 'User', 'org': 'Organization'}
        """
        resolved = self._resolve_role_name(name)
        value = self._get_annotation(self._rbox[resolved], "type_discriminator")
        return self._parse_json_or_value(value, None)

    def is_role_polymorphic(self, name: str) -> bool:
        """
        Check if a role is polymorphic (has multiple range classes).

        Args:
            name: Role name

        Returns:
            True if role has multiple range classes or a type discriminator
        """
        range_classes = self.get_role_range_classes(name)
        discriminator = self.get_role_type_discriminator(name)
        return len(range_classes) > 1 or discriminator is not None

    def has_composite_key(self, name: str, is_class: bool = True) -> bool:
        """
        Check if an entity or role uses composite keys.

        Args:
            name: Class or role name
            is_class: True for TBox class, False for RBox role

        Returns:
            True if entity uses composite primary key or role uses composite FK
        """
        if is_class:
            pk = self.get_class_pk(name)
            return len(pk) > 1
        else:
            domain_keys, range_keys = self.get_role_keys(name)
            return len(domain_keys) > 1 or len(range_keys) > 1

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
def load_ontology(path: Path, validate: bool = True) -> OntologyAccessor:
    """Load and return an OntologyAccessor instance."""
    return OntologyAccessor(path, validate=validate)
