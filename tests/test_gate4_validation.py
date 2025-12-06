"""
Gate 4 Validation Tests: Skill Integration

These tests validate that:
1. Pattern templates are correctly structured and can be loaded
2. Pattern matching selects correct templates for sample queries
3. Ontology mappings resolve to valid handler parameters
4. End-to-end: Query → Pattern → Ontology → Handler → Result

Run with: poetry run pytest tests/test_gate4_validation.py -v
"""

import os
import sys
from pathlib import Path

import pytest
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from virt_graph.ontology import OntologyAccessor


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def patterns_dir(project_root):
    """Get patterns templates directory."""
    return project_root / "patterns" / "templates"


@pytest.fixture
def ontology_path(project_root):
    """Get ontology file path."""
    return project_root / "ontology" / "supply_chain.yaml"


@pytest.fixture
def ontology(ontology_path):
    """Load ontology using OntologyAccessor."""
    return OntologyAccessor(ontology_path)


@pytest.fixture
def all_pattern_templates(patterns_dir):
    """Load all pattern templates."""
    templates = {}
    for yaml_file in patterns_dir.rglob("*.yaml"):
        with open(yaml_file) as f:
            template = yaml.safe_load(f)
            templates[yaml_file.stem] = {
                "path": yaml_file,
                "content": template,
            }
    return templates


# =============================================================================
# Test 1: Pattern Template Structure
# =============================================================================


class TestPatternTemplateStructure:
    """Validate pattern template structure and required fields."""

    REQUIRED_FIELDS = [
        "name",
        "description",
        "handler",
        "applicability",
        "ontology_bindings",
    ]

    def test_all_templates_exist(self, patterns_dir):
        """Verify all expected pattern template files exist."""
        expected_templates = [
            "traversal/tier_traversal.yaml",
            "traversal/bom_explosion.yaml",
            "traversal/where_used.yaml",
            "pathfinding/shortest_path.yaml",
            "pathfinding/all_paths.yaml",
            "aggregation/impact_analysis.yaml",
            "network-analysis/centrality.yaml",
            "network-analysis/components.yaml",
        ]

        for template_path in expected_templates:
            full_path = patterns_dir / template_path
            assert full_path.exists(), f"Missing pattern template: {template_path}"

    def test_templates_have_required_fields(self, all_pattern_templates):
        """Verify all templates have required fields."""
        for name, data in all_pattern_templates.items():
            template = data["content"]
            for field in self.REQUIRED_FIELDS:
                assert field in template, (
                    f"Template '{name}' missing required field: {field}"
                )

    def test_templates_have_valid_handlers(self, all_pattern_templates):
        """Verify templates reference valid handlers."""
        valid_handlers = [
            "traverse",
            "traverse_collecting",
            "bom_explode",
            "shortest_path",
            "all_shortest_paths",
            "centrality",
            "connected_components",
            "graph_density",
            "neighbors",
        ]

        for name, data in all_pattern_templates.items():
            template = data["content"]
            handler = template.get("handler")

            # Check main handler
            assert handler in valid_handlers, (
                f"Template '{name}' has invalid handler: {handler}"
            )

            # Check alternative handler if present
            alt_handler = template.get("alternative_handler")
            if alt_handler:
                assert alt_handler in valid_handlers, (
                    f"Template '{name}' has invalid alternative_handler: {alt_handler}"
                )

    def test_templates_have_query_signals(self, all_pattern_templates):
        """Verify all templates have query signals for matching."""
        for name, data in all_pattern_templates.items():
            template = data["content"]
            applicability = template.get("applicability", {})

            has_signals = "query_signals" in applicability
            assert has_signals, (
                f"Template '{name}' missing applicability.query_signals"
            )

    def test_templates_have_examples(self, all_pattern_templates):
        """Verify templates have example instantiations."""
        for name, data in all_pattern_templates.items():
            template = data["content"]
            has_example = "example" in template or "variants" in template
            assert has_example, (
                f"Template '{name}' missing example or variants"
            )


# =============================================================================
# Test 2: Pattern Matching
# =============================================================================


class TestPatternMatching:
    """Validate pattern matching selects correct templates."""

    @pytest.mark.parametrize("query,expected_pattern", [
        # Tier traversal
        ("Find all tier 3 suppliers for Acme Corp", "tier_traversal"),
        ("Who supplies to GlobalTech Industries?", "tier_traversal"),
        ("Trace upstream supply chain", "tier_traversal"),

        # BOM explosion
        ("Full parts list for the Turbo Encabulator", "bom_explosion"),
        ("What components go into product X?", "bom_explosion"),
        ("BOM explosion for assembly Y", "bom_explosion"),

        # Where-used
        ("Where is part X used?", "where_used"),
        ("What assemblies contain component Y?", "where_used"),

        # Shortest path
        ("Cheapest route from Chicago to LA", "shortest_path"),
        ("Fastest shipping path from NYC to Munich", "shortest_path"),
        ("What's the shortest route?", "shortest_path"),

        # All paths
        ("Show me all alternative routes from A to B", "all_paths"),
        ("Alternative routes available?", "all_paths"),

        # Impact analysis
        ("What products are affected if Acme Corp fails?", "impact_analysis"),
        ("Impact of supplier disruption", "impact_analysis"),

        # Centrality
        ("Which facility is most critical?", "centrality"),
        ("Most connected supplier", "centrality"),
        ("Find bottleneck facilities", "centrality"),

        # Components
        ("Are there isolated clusters?", "components"),
        ("Is the network connected?", "components"),
    ])
    def test_query_matches_expected_pattern(
        self, query, expected_pattern, all_pattern_templates
    ):
        """Test that queries match expected patterns based on signals."""
        # Find the matching pattern by checking query signals
        matched_pattern = None
        best_match_count = 0

        for name, data in all_pattern_templates.items():
            template = data["content"]
            signals = template.get("applicability", {}).get("query_signals", [])

            match_count = 0
            query_lower = query.lower()

            for signal in signals:
                # Simple substring matching (in real system, use regex)
                signal_words = signal.lower().replace("|", " ").split()
                for word in signal_words:
                    if word in query_lower:
                        match_count += 1

            if match_count > best_match_count:
                best_match_count = match_count
                matched_pattern = name

        assert matched_pattern == expected_pattern, (
            f"Query '{query}' matched '{matched_pattern}' "
            f"but expected '{expected_pattern}'"
        )


# =============================================================================
# Test 3: Ontology Resolution
# =============================================================================


class TestOntologyResolution:
    """Validate ontology mappings can be resolved to handler parameters."""

    def test_ontology_has_required_classes(self, ontology):
        """Verify ontology has all required classes."""
        required_classes = ["Supplier", "Part", "Product", "Facility"]

        for cls in required_classes:
            assert cls in ontology.classes, f"Ontology missing class: {cls}"
            # Verify sql mapping exists via accessor
            table = ontology.get_class_table(cls)
            assert table is not None, f"Class '{cls}' missing sql.table"

    def test_ontology_has_required_relationships(self, ontology):
        """Verify ontology has all required relationships."""
        required_relationships = [
            "supplies_to",
            "component_of",
            "connects_to",
            "provides",
            "can_supply",
            "contains_component",
        ]

        for rel in required_relationships:
            assert rel in ontology.roles, (
                f"Ontology missing relationship: {rel}"
            )
            # Verify sql mapping exists via accessor
            table = ontology.get_role_table(rel)
            assert table is not None, (
                f"Relationship '{rel}' missing sql.table"
            )

    def test_ontology_sql_mappings_complete(self, ontology):
        """Verify all sql mappings have required fields."""
        for name in ontology.roles:
            # All relationships need table and keys - accessor methods will raise if missing
            table = ontology.get_role_table(name)
            assert table is not None, (
                f"Relationship '{name}' missing sql.table"
            )
            domain_key, range_key = ontology.get_role_keys(name)
            assert domain_key is not None, (
                f"Relationship '{name}' missing sql.domain_key"
            )
            assert range_key is not None, (
                f"Relationship '{name}' missing sql.range_key"
            )

    def test_traversal_complexity_annotations(self, ontology):
        """Verify relationships have traversal_complexity."""
        for name in ontology.roles:
            complexity = ontology.get_role_complexity(name)
            assert complexity is not None, (
                f"Relationship '{name}' missing traversal_complexity"
            )
            assert complexity in ["GREEN", "YELLOW", "RED"], (
                f"Relationship '{name}' has invalid complexity: {complexity}"
            )

    @pytest.mark.parametrize("pattern_name,expected_bindings", [
        ("tier_traversal", {
            "nodes_table": "suppliers",
            "edges_table": "supplier_relationships",
            "edge_from_col": "seller_id",
            "edge_to_col": "buyer_id",
        }),
        ("bom_explosion", {
            "nodes_table": "parts",
            "edges_table": "bill_of_materials",
            "edge_from_col": "parent_part_id",  # Swapped for explosion
            "edge_to_col": "child_part_id",      # Swapped for explosion
        }),
        ("shortest_path", {
            "nodes_table": "facilities",
            "edges_table": "transport_routes",
            "edge_from_col": "origin_facility_id",
            "edge_to_col": "destination_facility_id",
        }),
    ])
    def test_pattern_to_ontology_resolution(
        self, pattern_name, expected_bindings, all_pattern_templates, ontology
    ):
        """Test that pattern bindings resolve correctly from ontology."""
        template = all_pattern_templates[pattern_name]["content"]
        bindings = template.get("ontology_bindings", {})

        # Get node class from bindings
        node_class = bindings.get("node_class")
        if node_class and node_class in ontology.classes:
            resolved_nodes_table = ontology.get_class_table(node_class)
            assert resolved_nodes_table == expected_bindings["nodes_table"], (
                f"Pattern '{pattern_name}' nodes_table resolution failed"
            )

        # Get relationship from bindings
        relationship = bindings.get("edge_relationship")
        if relationship and relationship in ontology.roles:
            resolved_edges_table = ontology.get_role_table(relationship)
            assert resolved_edges_table == expected_bindings["edges_table"], (
                f"Pattern '{pattern_name}' edges_table resolution failed"
            )


# =============================================================================
# Test 4: End-to-End Integration
# =============================================================================


class TestEndToEndIntegration:
    """Test complete flow from query to handler invocation."""

    @pytest.fixture
    def db_connection(self):
        """Get database connection if available."""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                dbname="supply_chain",
                user="virt_graph",
                password="dev_password",
            )
            yield conn
            conn.close()
        except Exception:
            pytest.skip("Database not available for integration test")

    def test_tier_traversal_end_to_end(self, db_connection, ontology):
        """Test complete tier traversal from query to result."""
        from virt_graph.handlers.traversal import traverse_collecting

        # Query: "Find all tier 3 suppliers for supplier ID 1"
        # Using first tier 1 supplier as starting point

        # Resolve from ontology
        edges_table = ontology.get_role_table("supplies_to")
        domain_key, range_key = ontology.get_role_keys("supplies_to")

        # Execute handler
        result = traverse_collecting(
            conn=db_connection,
            nodes_table="suppliers",
            edges_table=edges_table,
            edge_from_col=domain_key,
            edge_to_col=range_key,
            start_id=1,  # First supplier
            target_condition="tier = 3",
            direction="inbound",
            max_depth=10,
        )

        # Validate result structure
        assert "matching_nodes" in result
        assert "total_traversed" in result
        assert isinstance(result["matching_nodes"], list)

        # If we found tier 3 suppliers, verify they're actually tier 3
        for node in result["matching_nodes"]:
            assert node.get("tier") == 3, "Found non-tier-3 supplier"

    def test_bom_explosion_end_to_end(self, db_connection, ontology):
        """Test complete BOM explosion from query to result."""
        from virt_graph.handlers.traversal import traverse

        # Query: "BOM for a part"
        # Find a parent part first
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT parent_part_id
                FROM bill_of_materials
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                pytest.skip("No BOM data available")
            start_part_id = row[0]

        # Execute BOM explosion using traverse
        # Note: For explosion, we swap from/to to go parent->children
        result = traverse(
            conn=db_connection,
            nodes_table="parts",
            edges_table="bill_of_materials",
            edge_from_col="parent_part_id",  # Swapped
            edge_to_col="child_part_id",      # Swapped
            start_id=start_part_id,
            direction="outbound",
            max_depth=10,
            include_start=True,
        )

        # Validate result
        assert "nodes" in result
        assert "depth_reached" in result
        assert len(result["nodes"]) > 0, "BOM should have at least start node"

    def test_shortest_path_end_to_end(self, db_connection, ontology):
        """Test complete shortest path from query to result."""
        from virt_graph.handlers.pathfinding import shortest_path

        # Find two connected facilities
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT origin_facility_id, destination_facility_id
                FROM transport_routes
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                pytest.skip("No transport routes available")
            start_id, end_id = row[0], row[1]

        # Resolve from ontology
        edges_table = ontology.get_role_table("connects_to")
        domain_key, range_key = ontology.get_role_keys("connects_to")

        # Execute handler
        result = shortest_path(
            conn=db_connection,
            nodes_table="facilities",
            edges_table=edges_table,
            edge_from_col=domain_key,
            edge_to_col=range_key,
            start_id=start_id,
            end_id=end_id,
            weight_col="cost_usd",
            max_depth=10,
        )

        # Validate result structure
        assert "path" in result
        assert "distance" in result
        assert result["path"] is not None, "Should find a path"
        assert result["path"][0] == start_id
        assert result["path"][-1] == end_id

    def test_centrality_end_to_end(self, db_connection, ontology):
        """Test complete centrality calculation."""
        from virt_graph.handlers.network import centrality

        # Resolve from ontology
        edges_table = ontology.get_role_table("connects_to")
        domain_key, range_key = ontology.get_role_keys("connects_to")

        # Execute handler
        result = centrality(
            conn=db_connection,
            nodes_table="facilities",
            edges_table=edges_table,
            edge_from_col=domain_key,
            edge_to_col=range_key,
            centrality_type="degree",
            top_n=5,
        )

        # Validate result structure
        assert "results" in result
        assert "graph_stats" in result
        assert len(result["results"]) <= 5

        # Results should be sorted by score descending
        scores = [r["score"] for r in result["results"]]
        assert scores == sorted(scores, reverse=True), "Results not sorted by score"


# =============================================================================
# Test 5: Skill File Structure
# =============================================================================


class TestSkillFileStructure:
    """Validate skill definition files exist and are properly structured."""

    def test_pattern_skill_exists(self, project_root):
        """Verify pattern skill definition exists."""
        skill_path = project_root / ".claude" / "skills" / "patterns" / "SKILL.md"
        assert skill_path.exists(), "Pattern skill definition missing"

    def test_handler_skill_exists(self, project_root):
        """Verify handler skill definition exists."""
        skill_path = project_root / ".claude" / "skills" / "handlers" / "SKILL.md"
        assert skill_path.exists(), "Handler skill definition missing"

    def test_schema_skill_exists(self, project_root):
        """Verify schema skill definition exists."""
        skill_path = project_root / ".claude" / "skills" / "schema" / "SKILL.md"
        assert skill_path.exists(), "Schema skill definition missing"

    def test_pattern_reference_exists(self, project_root):
        """Verify pattern reference documentation exists."""
        ref_path = project_root / ".claude" / "skills" / "patterns" / "reference.md"
        assert ref_path.exists(), "Pattern reference documentation missing"

    def test_handler_reference_exists(self, project_root):
        """Verify handler reference documentation exists."""
        ref_path = project_root / ".claude" / "skills" / "handlers" / "reference.md"
        assert ref_path.exists(), "Handler reference documentation missing"

    def test_skill_has_frontmatter(self, project_root):
        """Verify skill files have proper YAML frontmatter."""
        skill_files = [
            ".claude/skills/patterns/SKILL.md",
            ".claude/skills/handlers/SKILL.md",
            ".claude/skills/schema/SKILL.md",
        ]

        for skill_file in skill_files:
            skill_path = project_root / skill_file
            if skill_path.exists():
                content = skill_path.read_text()
                assert content.startswith("---"), (
                    f"Skill file '{skill_file}' missing YAML frontmatter"
                )
                # Check for closing frontmatter
                second_delimiter = content.find("---", 3)
                assert second_delimiter > 0, (
                    f"Skill file '{skill_file}' missing closing frontmatter delimiter"
                )


# =============================================================================
# Gate 4 Summary
# =============================================================================


class TestGate4Summary:
    """Summary test to verify Gate 4 completion criteria."""

    def test_gate4_checklist(self, project_root, all_pattern_templates, ontology):
        """Verify all Gate 4 deliverables are present."""
        checklist = {
            # Pattern templates
            "traversal/tier_traversal.yaml": False,
            "traversal/bom_explosion.yaml": False,
            "traversal/where_used.yaml": False,
            "pathfinding/shortest_path.yaml": False,
            "pathfinding/all_paths.yaml": False,
            "aggregation/impact_analysis.yaml": False,
            "network-analysis/centrality.yaml": False,
            "network-analysis/components.yaml": False,
            # Skills
            ".claude/skills/patterns/SKILL.md": False,
            ".claude/skills/patterns/reference.md": False,
            ".claude/skills/handlers/SKILL.md": False,
            ".claude/skills/handlers/reference.md": False,
        }

        # Check pattern templates
        patterns_dir = project_root / "patterns" / "templates"
        for pattern_path in list(checklist.keys())[:8]:
            full_path = patterns_dir / pattern_path
            if full_path.exists():
                checklist[pattern_path] = True

        # Check skill files
        for skill_path in list(checklist.keys())[8:]:
            full_path = project_root / skill_path
            if full_path.exists():
                checklist[skill_path] = True

        # Report results
        missing = [k for k, v in checklist.items() if not v]
        assert len(missing) == 0, f"Gate 4 incomplete. Missing: {missing}"

        # Verify pattern count
        assert len(all_pattern_templates) >= 8, (
            f"Expected at least 8 pattern templates, found {len(all_pattern_templates)}"
        )

        print("\n" + "=" * 60)
        print("GATE 4 VALIDATION: PASSED")
        print("=" * 60)
        print(f"Pattern templates: {len(all_pattern_templates)}")
        print(f"Ontology classes: {len(ontology.classes)}")
        print(f"Ontology roles: {len(ontology.roles)}")
        print("All deliverables present and validated")
        print("=" * 60)
