#!/usr/bin/env python3
"""
Show TBox/RBox definitions from an ontology YAML file.

Extracts and displays entity classes (TBox) and relationship classes (RBox)
in a readable format for quick reference during analysis sessions.

Usage:
    poetry run python scripts/show_ontology.py [ontology_path]
    poetry run python scripts/show_ontology.py --tbox-only
    poetry run python scripts/show_ontology.py --rbox-only
    poetry run python scripts/show_ontology.py --by-domain
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

        # Domain
        domain = ontology.get_class_domain(name)
        if domain:
            entry["domain"] = domain
        subdomain = ontology.get_class_subdomain(name)
        if subdomain:
            entry["subdomain"] = subdomain

        # Kinetic extensions
        sm = ontology.get_class_state_machine(name)
        if sm:
            entry["state_machine"] = f"{sm['state_column']} ({len(sm.get('states', []))} states)"
        axioms = ontology.get_class_axioms(name)
        if axioms:
            entry["axiom_count"] = len(axioms)
        actions = ontology.get_class_actions(name)
        if actions:
            entry["action_count"] = len(actions)
        params = ontology.get_class_scenario_params(name)
        if params:
            entry["scenario_param_count"] = len(params)

        tbox_data.append(entry)

    if as_json:
        return json.dumps({"tbox": tbox_data}, indent=2)

    # Text format
    lines = ["TBox (Entity Classes)", "=" * 60]
    for entry in tbox_data:
        domain_tag = f" [{entry['domain']}]" if entry.get('domain') else ""
        lines.append(f"\n{entry['class']}{domain_tag}")
        lines.append(f"  table: {entry['table']}")
        lines.append(f"  primary_key: {entry['primary_key']}")
        if entry.get('subdomain'):
            lines.append(f"  subdomain: {entry['subdomain']}")
        if entry['identifier']:
            lines.append(f"  identifier: {entry['identifier']}")
        if entry['row_count']:
            lines.append(f"  row_count: {entry['row_count']:,}")
        if entry.get('soft_delete_column'):
            lines.append(f"  soft_delete: {entry['soft_delete_column']}")
        if entry.get('state_machine'):
            lines.append(f"  state_machine: {entry['state_machine']}")
        if entry.get('axiom_count'):
            lines.append(f"  axioms: {entry['axiom_count']}")
        if entry.get('action_count'):
            lines.append(f"  actions: {entry['action_count']}")
        if entry.get('scenario_param_count'):
            lines.append(f"  scenario_params: {entry['scenario_param_count']}")

    return "\n".join(lines)


def format_rbox(ontology: OntologyAccessor, as_json: bool = False) -> str:
    """Format RBox (relationship classes) for display."""
    rbox_data = []

    for name in sorted(ontology.roles.keys()):
        operation_types = ontology.get_operation_types(name)
        domain_key, range_key = ontology.get_role_keys(name)
        props = ontology.get_role_properties(name)

        entry = {
            "relationship": name,
            "operation_types": operation_types,
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

        # Add weight columns for algorithm operations
        if any(op in operation_types for op in ["shortest_path", "centrality", "connected_components", "resilience_analysis"]):
            weights = ontology.get_role_weight_columns(name)
            if weights:
                entry["weight_columns"] = [w["name"] for w in weights]

        # Add temporal bounds if present
        temporal = ontology.get_temporal_bounds(name)
        if temporal:
            entry["temporal_bounds"] = temporal

        # Domain
        role_domain = ontology.get_role_domain_category(name)
        if role_domain:
            entry["domain"] = role_domain
        if ontology.is_role_cross_domain(name):
            entry["cross_domain"] = True

        # Kinetic extensions
        fc = ontology.get_role_flow_config(name)
        if fc:
            entry["flow_config"] = f"{fc['flow_type']} ({fc['quantity_column']} @ {fc['timestamp_column']})"
        axioms = ontology.get_role_axioms(name)
        if axioms:
            entry["axiom_count"] = len(axioms)

        rbox_data.append(entry)

    if as_json:
        return json.dumps({"rbox": rbox_data}, indent=2)

    # Text format - alphabetically sorted
    lines = ["RBox (Relationship Classes)", "=" * 60]

    for entry in rbox_data:
        domain_cls = entry["domain_class"]
        range_ = entry["range_class"]
        ops = ", ".join(entry["operation_types"]) if entry["operation_types"] else "none"
        domain_tag = f" [{entry['domain']}]" if entry.get('domain') else ""
        cross_tag = " ✕" if entry.get('cross_domain') else ""
        lines.append(f"\n{entry['relationship']}{domain_tag}{cross_tag}: {domain_cls} -> {range_}")
        lines.append(f"  table: {entry['edge_table']}")
        lines.append(f"  keys: {entry['domain_key']} -> {entry['range_key']}")
        lines.append(f"  operations: {ops}")
        if entry['row_count']:
            lines.append(f"  edges: {entry['row_count']:,}")
        if entry.get('properties'):
            lines.append(f"  properties: {', '.join(entry['properties'])}")
        if entry.get('inverse_of'):
            lines.append(f"  inverse_of: {entry['inverse_of']}")
        if entry.get('weight_columns'):
            lines.append(f"  weights: {', '.join(entry['weight_columns'])}")
        if entry.get('temporal_bounds'):
            lines.append(f"  temporal: {entry['temporal_bounds']['start_col']} -> {entry['temporal_bounds']['end_col']}")
        if entry.get('flow_config'):
            lines.append(f"  flow: {entry['flow_config']}")
        if entry.get('axiom_count'):
            lines.append(f"  axioms: {entry['axiom_count']}")

    return "\n".join(lines)


def format_by_domain(ontology: OntologyAccessor) -> str:
    """Format ontology grouped by domain."""
    lines = ["Ontology by Domain", "=" * 60]
    domains = ontology.get_all_domains()

    for domain_name in ["procurement", "supply", "demand", "orchestrate"]:
        if domain_name not in domains:
            continue
        info = domains[domain_name]
        lines.append(f"\n{'─' * 60}")
        lines.append(f"  {domain_name.upper()} ({len(info['classes'])} classes, {len(info['roles'])} roles)")
        lines.append(f"{'─' * 60}")

        lines.append("\n  Classes:")
        for cls_name in sorted(info["classes"]):
            subdomain = ontology.get_class_subdomain(cls_name) or ""
            table = ontology.get_class_table(cls_name)
            sd_tag = f" ({subdomain})" if subdomain else ""
            lines.append(f"    {cls_name}{sd_tag} → {table}")

        lines.append("\n  Relationships:")
        for role_name in sorted(info["roles"]):
            cross = " ✕" if ontology.is_role_cross_domain(role_name) else ""
            domain_cls = ontology.get_role_domain(role_name)
            range_cls = ontology.get_role_range(role_name)
            lines.append(f"    {role_name}{cross}: {domain_cls} → {range_cls}")

    cross_roles = ontology.get_cross_domain_roles()
    if cross_roles:
        lines.append(f"\n{'─' * 60}")
        lines.append(f"  CROSS-DOMAIN RELATIONSHIPS ({len(cross_roles)} total, marked ✕ above)")
        lines.append(f"{'─' * 60}")
        for name in sorted(cross_roles):
            d = ontology.get_role_domain_category(name)
            dc = ontology.get_role_domain(name)
            rc = ontology.get_role_range(name)
            lines.append(f"    [{d}] {name}: {dc} → {rc}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Show TBox/RBox definitions from ontology"
    )
    parser.add_argument(
        "ontology_path",
        nargs="?",
        help="Path to ontology YAML (default: pcg_example/ontology/pcg.yaml)"
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
        "--by-domain",
        action="store_true",
        help="Group output by business domain"
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
        ontology_path = Path(__file__).parent.parent / "pcg_example" / "ontology" / "pcg.yaml"

    if not ontology_path.exists():
        print(f"Error: {ontology_path} not found", file=sys.stderr)
        sys.exit(1)

    try:
        ontology = OntologyAccessor(ontology_path, validate=False)
    except Exception as e:
        print(f"Error loading ontology: {e}", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.by_domain:
        print(format_by_domain(ontology))
    elif args.json:
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
        sm_count = len(ontology.get_classes_with_state_machines())
        fc_count = len(ontology.get_roles_with_flow_config())
        cg_count = len(ontology.get_conservation_groups())
        domains = ontology.get_all_domains()
        cross_count = len(ontology.get_cross_domain_roles())
        print(f"\n{'=' * 60}")
        print(f"Summary: {len(ontology.classes)} entities, {len(ontology.roles)} relationships")
        if domains:
            domain_summary = ", ".join(
                f"{d}={len(info['classes'])}c/{len(info['roles'])}r"
                for d, info in sorted(domains.items())
            )
            print(f"Domains: {domain_summary} ({cross_count} cross-domain)")
        if sm_count or fc_count or cg_count:
            print(f"Kinetic: {sm_count} state machines, {fc_count} flow configs, {cg_count} conservation groups")


if __name__ == "__main__":
    main()
