#!/usr/bin/env python3
"""
Show TBox/RBox definitions from an ontology YAML file.

Extracts and displays entity classes (TBox) and relationship classes (RBox)
in a readable format for quick reference during analysis sessions.

Usage:
    poetry run python scripts/show_ontology.py [ontology_path]
    poetry run python scripts/show_ontology.py --tbox-only
    poetry run python scripts/show_ontology.py --rbox-only
    poetry run python scripts/show_ontology.py --json
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virt_graph.ontology import OntologyAccessor


def format_tbox(ontology: OntologyAccessor, as_json: bool = False) -> str:
    """Format TBox (entity classes) for display."""
    tbox_data = []

    for name in sorted(ontology.classes.keys()):
        entry = {
            "class": name,
            "table": ontology.get_class_table(name),
            "primary_key": ontology.get_class_pk(name),
            "identifier": ontology.get_class_identifier(name),
            "row_count": ontology.get_class_row_count(name),
        }
        soft_delete = ontology.get_class_soft_delete(name)
        if soft_delete[0]:
            entry["soft_delete_column"] = soft_delete[1]
        tbox_data.append(entry)

    if as_json:
        return json.dumps({"tbox": tbox_data}, indent=2)

    # Text format
    lines = ["TBox (Entity Classes)", "=" * 60]
    for entry in tbox_data:
        lines.append(f"\n{entry['class']}")
        lines.append(f"  table: {entry['table']}")
        lines.append(f"  primary_key: {entry['primary_key']}")
        if entry['identifier']:
            lines.append(f"  identifier: {entry['identifier']}")
        if entry['row_count']:
            lines.append(f"  row_count: {entry['row_count']:,}")
        if entry.get('soft_delete_column'):
            lines.append(f"  soft_delete: {entry['soft_delete_column']}")

    return "\n".join(lines)


def format_rbox(ontology: OntologyAccessor, as_json: bool = False) -> str:
    """Format RBox (relationship classes) for display."""
    rbox_data = []

    for name in sorted(ontology.roles.keys()):
        complexity = ontology.get_role_complexity(name)
        domain_key, range_key = ontology.get_role_keys(name)
        props = ontology.get_role_properties(name)

        entry = {
            "relationship": name,
            "complexity": complexity,
            "edge_table": ontology.get_role_table(name),
            "domain_class": ontology.get_role_domain(name),
            "range_class": ontology.get_role_range(name),
            "domain_key": domain_key,
            "range_key": range_key,
            "row_count": ontology.get_role_row_count(name),
        }

        # Add active properties
        active_props = [k for k, v in props.items() if v and k != "inverse_of"]
        if active_props:
            entry["properties"] = active_props
        if props.get("inverse_of"):
            entry["inverse_of"] = props["inverse_of"]

        # Add weight columns for RED complexity
        if complexity == "RED":
            weights = ontology.get_role_weight_columns(name)
            if weights:
                entry["weight_columns"] = [w["name"] for w in weights]

        rbox_data.append(entry)

    if as_json:
        return json.dumps({"rbox": rbox_data}, indent=2)

    # Text format - group by complexity
    lines = ["RBox (Relationship Classes)", "=" * 60]

    for complexity in ["GREEN", "YELLOW", "RED"]:
        entries = [e for e in rbox_data if e["complexity"] == complexity]
        if not entries:
            continue

        lines.append(f"\n[{complexity}]")
        for entry in entries:
            domain = entry["domain_class"]
            range_ = entry["range_class"]
            lines.append(f"\n  {entry['relationship']}: {domain} -> {range_}")
            lines.append(f"    table: {entry['edge_table']}")
            lines.append(f"    keys: {entry['domain_key']} -> {entry['range_key']}")
            if entry['row_count']:
                lines.append(f"    edges: {entry['row_count']:,}")
            if entry.get('properties'):
                lines.append(f"    properties: {', '.join(entry['properties'])}")
            if entry.get('inverse_of'):
                lines.append(f"    inverse_of: {entry['inverse_of']}")
            if entry.get('weight_columns'):
                lines.append(f"    weights: {', '.join(entry['weight_columns'])}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Show TBox/RBox definitions from ontology"
    )
    parser.add_argument(
        "ontology_path",
        nargs="?",
        help="Path to ontology YAML (default: ontology/supply_chain.yaml)"
    )
    parser.add_argument(
        "--tbox-only",
        action="store_true",
        help="Show only TBox (entity classes)"
    )
    parser.add_argument(
        "--rbox-only",
        action="store_true",
        help="Show only RBox (relationships)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()

    # Load ontology
    if args.ontology_path:
        ontology_path = Path(args.ontology_path)
    else:
        ontology_path = Path(__file__).parent.parent / "ontology" / "supply_chain.yaml"

    if not ontology_path.exists():
        print(f"Error: {ontology_path} not found", file=sys.stderr)
        sys.exit(1)

    try:
        ontology = OntologyAccessor(ontology_path, validate=False)
    except Exception as e:
        print(f"Error loading ontology: {e}", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.json:
        if args.tbox_only:
            print(format_tbox(ontology, as_json=True))
        elif args.rbox_only:
            print(format_rbox(ontology, as_json=True))
        else:
            tbox = json.loads(format_tbox(ontology, as_json=True))
            rbox = json.loads(format_rbox(ontology, as_json=True))
            print(json.dumps({**tbox, **rbox}, indent=2))
    else:
        if args.tbox_only:
            print(format_tbox(ontology))
        elif args.rbox_only:
            print(format_rbox(ontology))
        else:
            print(format_tbox(ontology))
            print("\n")
            print(format_rbox(ontology))

    # Summary
    if not args.json:
        print(f"\n{'=' * 60}")
        print(f"Summary: {len(ontology.classes)} entities, {len(ontology.roles)} relationships")


if __name__ == "__main__":
    main()
