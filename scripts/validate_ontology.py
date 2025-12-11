#!/usr/bin/env python3
"""
Ontology Validation Script

Two-layer validation for Virtual Graph ontologies:
1. LinkML structure validation (via linkml-lint)
2. VG annotation validation (via OntologyAccessor)

Usage:
    poetry run python scripts/validate_ontology.py [ontology_path]
    poetry run python scripts/validate_ontology.py --all
"""

import subprocess
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virt_graph.ontology import OntologyAccessor, OntologyValidationError


def validate_linkml_structure(ontology_path: Path) -> bool:
    """
    Layer 1: Validate LinkML schema structure.

    Validates YAML syntax and LinkML schema structure.
    Does NOT validate VG-specific annotations.
    """
    print(f"\n{'='*60}")
    print(f"Layer 1: LinkML Structure Validation")
    print(f"{'='*60}")
    print(f"File: {ontology_path}")

    result = subprocess.run(
        ["poetry", "run", "linkml-lint", "--validate-only", str(ontology_path)],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✓ LinkML structure validation passed")
        return True
    else:
        print("✗ LinkML structure validation failed:")
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)
        return False


def validate_vg_annotations(ontology_path: Path) -> bool:
    """
    Layer 2: Validate VG-specific annotations.

    Validates:
    - Required VG annotations are present
    - traversal_complexity values are GREEN/YELLOW/RED
    - domain_class/range_class reference valid entity classes
    """
    print(f"\n{'='*60}")
    print(f"Layer 2: VG Annotation Validation")
    print(f"{'='*60}")
    print(f"File: {ontology_path}")

    try:
        # Load with validation enabled
        ontology = OntologyAccessor(ontology_path, validate=True)
        print("✓ VG annotation validation passed")
        print(f"  - {len(ontology.classes)} entity classes (TBox)")
        print(f"  - {len(ontology.roles)} relationship classes (RBox)")
        return True
    except OntologyValidationError as e:
        print("✗ VG annotation validation failed:")
        for error in e.errors:
            print(f"  - {error}")
        return False
    except Exception as e:
        print(f"✗ Error loading ontology: {e}")
        return False


def validate_ontology(ontology_path: Path) -> bool:
    """Run both layers of validation."""
    layer1_passed = validate_linkml_structure(ontology_path)
    layer2_passed = validate_vg_annotations(ontology_path)

    print(f"\n{'='*60}")
    print("Validation Summary")
    print(f"{'='*60}")
    print(f"  Layer 1 (LinkML Structure): {'✓ PASS' if layer1_passed else '✗ FAIL'}")
    print(f"  Layer 2 (VG Annotations):   {'✓ PASS' if layer2_passed else '✗ FAIL'}")
    print(f"{'='*60}")

    return layer1_passed and layer2_passed


def main():
    ontology_dir = Path(__file__).parent.parent / "ontology"

    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            # Validate all ontology files in ontology/ directory
            # Excludes TEMPLATE.yaml (template, not a real ontology)
            ontology_files = [
                f for f in ontology_dir.glob("*.yaml")
                if f.name != "TEMPLATE.yaml"
            ]
            if not ontology_files:
                print(f"No ontology files found in {ontology_dir}")
                sys.exit(1)

            print(f"Found {len(ontology_files)} ontology file(s) to validate:")
            for f in ontology_files:
                print(f"  - {f.name}")

            all_passed = True
            for path in sorted(ontology_files):
                if not validate_ontology(path):
                    all_passed = False
            sys.exit(0 if all_passed else 1)
        else:
            # Validate specific file
            ontology_path = Path(sys.argv[1])
    else:
        # No argument - show usage
        print("Usage:")
        print("  poetry run python scripts/validate_ontology.py <ontology_path>")
        print("  poetry run python scripts/validate_ontology.py --all")
        print()
        print("Examples:")
        print("  poetry run python scripts/validate_ontology.py ontology/supply_chain.yaml")
        print("  poetry run python scripts/validate_ontology.py --all")
        sys.exit(1)

    if not ontology_path.exists():
        print(f"Error: {ontology_path} not found")
        sys.exit(1)

    passed = validate_ontology(ontology_path)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
