#!/usr/bin/env python3
"""Export PCG ontology as 4 CSV sheets for Google Sheets / organizational education.

Usage:
    poetry run python scripts/export_ontology_csv.py [--output-dir DIR]

Outputs:
    DIR/tbox_entities.csv          — Entity catalog (38 rows)
    DIR/rbox_relationships.csv     — Relationship catalog (50 rows)
    DIR/abox_attributes.csv        — Attribute catalog (~170 rows)
    DIR/orchestration_flows.csv    — State machines, flows, cross-domain, axioms
"""

import argparse
import csv
from pathlib import Path

from virt_graph.ontology import OntologyAccessor


def yn(val: bool) -> str:
    return "Y" if val else "N"


def join_list(items: list) -> str:
    return ", ".join(str(i) for i in items) if items else ""


def safe_get(d: dict | None, key: str, default: str = "") -> str:
    if d is None:
        return default
    return str(d.get(key, default))


def find_slot_source(o: OntologyAccessor, class_name: str, slot_name: str, local_slots: set[str]) -> str:
    """Walk the is_a / mixin chain to find which class defines a slot."""
    if slot_name in local_slots:
        return class_name
    cls = o._schema_view.get_class(class_name)
    if cls is None:
        return class_name
    # Check mixins
    for mixin_name in cls.mixins or []:
        mixin_slots = {s.name for s in o._schema_view.class_induced_slots(mixin_name)}
        if slot_name in mixin_slots:
            return mixin_name
    # Walk up is_a
    if cls.is_a:
        parent_raw = o._tbox.get(cls.is_a, {}).get("attributes", {})
        return find_slot_source(o, cls.is_a, slot_name, set(parent_raw.keys()))
    return class_name


def export_tbox(o: OntologyAccessor) -> list[dict]:
    """Sheet 1: TBox — Entity Catalog."""
    rows = []
    for name in sorted(o._tbox, key=lambda n: (o.get_class_domain(n) or "", n)):
        sm = o.get_class_state_machine(name)
        states = sm.get("states", []) if sm else []
        ctx = o.get_class_context(name)
        identifier = o.get_class_identifier(name)
        rows.append({
            "Entity": name,
            "Domain": o.get_class_domain(name) or "",
            "Subdomain": o.get_class_subdomain(name) or "",
            "Table": o.get_class_table(name),
            "Primary Key": join_list(o.get_class_pk(name)),
            "Natural Key": join_list(identifier) if isinstance(identifier, list) else str(identifier or ""),
            "Description": o._tbox[name].get("description", ""),
            "Column Count": len(o.get_class_inherited_attributes(name)),
            "Has State Machine": yn(sm is not None),
            "States": join_list(states),
            "Axiom Count": len(o.get_class_axioms(name)),
            "Action Count": len(o.get_class_actions(name)),
            "Business Logic": safe_get(ctx, "business_logic"),
        })
    return rows


def export_rbox(o: OntologyAccessor) -> list[dict]:
    """Sheet 2: RBox — Relationship Catalog."""
    rows = []
    for name in sorted(o._rbox, key=lambda n: (o.get_role_domain_category(n) or "", n)):
        props = o.get_role_properties(name)
        active_props = [k for k, v in props.items() if v and k != "inverse_of"]
        if props.get("inverse_of"):
            active_props.append(f"inverse_of={props['inverse_of']}")
        domain_keys, range_keys = o.get_role_keys(name)
        weight_cols = o.get_role_weight_columns(name)
        edge_attrs = o.get_role_edge_attributes(name)
        fc = o.get_role_flow_config(name)
        ctx = o.get_role_context(name)
        rows.append({
            "Relationship": name,
            "Domain": o.get_role_domain_category(name) or "",
            "From Entity": join_list(o.get_role_domain_classes(name)),
            "To Entity": join_list(o.get_role_range_classes(name)),
            "Edge Table": o.get_role_table(name),
            "From Key": join_list(domain_keys),
            "To Key": join_list(range_keys),
            "Operation Types": join_list(o.get_operation_types(name)),
            "Is Polymorphic": yn(o.is_role_polymorphic(name)),
            "Is Cross-Domain": yn(o.is_role_cross_domain(name)),
            "OWL Properties": join_list(active_props),
            "Weight Columns": join_list([w["name"] for w in weight_cols]) if weight_cols else "",
            "Edge Attributes": join_list([a["name"] for a in edge_attrs]) if edge_attrs else "",
            "SQL Filter": o.get_role_filter(name) or "",
            "Has Flow Config": yn(fc is not None),
            "Flow Type": safe_get(fc, "flow_type") if fc else "",
            "Description": o._rbox[o._resolve_role_name(name)].get("description", ""),
            "Business Logic": safe_get(ctx, "business_logic"),
        })
    return rows


def export_abox(o: OntologyAccessor) -> list[dict]:
    """Sheet 3: ABox — Attribute Catalog."""
    rows = []
    for name in sorted(o._tbox, key=lambda n: (o.get_class_domain(n) or "", n)):
        local_slots = set(o.get_class_slots(name).keys())
        table = o.get_class_table(name)
        domain = o.get_class_domain(name) or ""
        for attr_name, attr_def in sorted(o.get_class_inherited_attributes(name).items()):
            source = find_slot_source(o, name, attr_name, local_slots)
            rows.append({
                "Entity": name,
                "Domain": domain,
                "Table": table,
                "Attribute": attr_name,
                "Data Type": attr_def.get("range", "string"),
                "Inherited From": source if source != name else "",
                "Description": attr_def.get("description", ""),
            })
    return rows


def export_orchestration(o: OntologyAccessor) -> list[dict]:
    """Sheet 4: Orchestration — State Machines, Flows, Cross-Domain, Axioms."""
    rows = []

    # --- State Machines ---
    for class_name in sorted(o.get_classes_with_state_machines()):
        sm = o.get_class_state_machine(class_name)
        if not sm:
            continue
        domain = o.get_class_domain(class_name) or ""
        state_col = sm.get("state_column", "")
        initial = sm.get("initial_state")
        terminals = set(sm.get("terminal_states", []))
        transitions = sm.get("transitions", [])

        # Build transition map: from_state -> list of to_states
        trans_from: dict[str, list[str]] = {}
        for t in transitions:
            fs = t.get("from_state", "")
            ts = t.get("to_state", "")
            trans_from.setdefault(fs, []).append(ts)

        for state in sm.get("states", []):
            rows.append({
                "Category": "State Machine",
                "Entity/Relationship": class_name,
                "Domain": domain,
                "Detail 1": state_col,
                "Detail 2": state,
                "Detail 3": yn(state == initial),
                "Detail 4": yn(state in terminals),
                "Detail 5": join_list(trans_from.get(state, [])),
                "Detail 6": "",
                "Detail 7": "",
            })

    # --- Flow Configurations ---
    for role_name in sorted(o.get_roles_with_flow_config()):
        fc = o.get_role_flow_config(role_name)
        if not fc:
            continue
        rows.append({
            "Category": "Flow",
            "Entity/Relationship": role_name,
            "Domain": o.get_role_domain_category(role_name) or "",
            "Detail 1": safe_get(fc, "flow_type"),
            "Detail 2": safe_get(fc, "quantity_column"),
            "Detail 3": safe_get(fc, "timestamp_column"),
            "Detail 4": safe_get(fc, "conservation_group"),
            "Detail 5": safe_get(fc, "unit"),
            "Detail 6": "",
            "Detail 7": "",
        })

    # --- Cross-Domain Bridges ---
    for role_name in sorted(o.get_cross_domain_roles()):
        rows.append({
            "Category": "Cross-Domain",
            "Entity/Relationship": role_name,
            "Domain": o.get_role_domain_category(role_name) or "",
            "Detail 1": join_list(o.get_role_domain_classes(role_name)),
            "Detail 2": join_list(o.get_role_range_classes(role_name)),
            "Detail 3": join_list(o.get_operation_types(role_name)),
            "Detail 4": "",
            "Detail 5": "",
            "Detail 6": "",
            "Detail 7": "",
        })

    # --- Axioms (class + relationship) ---
    for class_name in sorted(o._tbox):
        for axiom in o.get_class_axioms(class_name):
            rows.append({
                "Category": "Axiom",
                "Entity/Relationship": class_name,
                "Domain": o.get_class_domain(class_name) or "",
                "Detail 1": axiom.get("name", ""),
                "Detail 2": axiom.get("axiom_type", ""),
                "Detail 3": axiom.get("severity", ""),
                "Detail 4": axiom.get("description", ""),
                "Detail 5": axiom.get("sql_expression", ""),
                "Detail 6": "",
                "Detail 7": "",
            })
    for role_name in sorted(o._rbox):
        for axiom in o.get_role_axioms(role_name):
            rows.append({
                "Category": "Axiom",
                "Entity/Relationship": role_name,
                "Domain": o.get_role_domain_category(role_name) or "",
                "Detail 1": axiom.get("name", ""),
                "Detail 2": axiom.get("axiom_type", ""),
                "Detail 3": axiom.get("severity", ""),
                "Detail 4": axiom.get("description", ""),
                "Detail 5": axiom.get("sql_expression", ""),
                "Detail 6": "",
                "Detail 7": "",
            })

    return rows


# Column headers for orchestration sheet (semantic names in a comment row)
ORCH_HEADER_MAP = {
    "State Machine": "Category | Entity/Relationship | Domain | State Column | State | Is Initial | Is Terminal | Transitions From Here | | ",
    "Flow": "Category | Entity/Relationship | Domain | Flow Type | Quantity Column | Timestamp Column | Conservation Group | Unit | | ",
    "Cross-Domain": "Category | Entity/Relationship | Domain | From Entity | To Entity | Operation Types | | | | ",
    "Axiom": "Category | Entity/Relationship | Domain | Axiom Name | Type | Severity | Description | SQL Expression | | ",
}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Export ontology as CSV sheets")
    parser.add_argument("--output-dir", default="pcg_example/exports", help="Output directory")
    parser.add_argument("--ontology", default="pcg_example/ontology/pcg.yaml", help="Ontology YAML path")
    args = parser.parse_args()

    out = Path(args.output_dir)
    o = OntologyAccessor(Path(args.ontology), validate=False)

    # Sheet 1: TBox
    tbox_rows = export_tbox(o)
    tbox_fields = [
        "Entity", "Domain", "Subdomain", "Table", "Primary Key", "Natural Key",
        "Description", "Column Count", "Has State Machine", "States",
        "Axiom Count", "Action Count", "Business Logic",
    ]
    n1 = write_csv(out / "tbox_entities.csv", tbox_fields, tbox_rows)

    # Sheet 2: RBox
    rbox_rows = export_rbox(o)
    rbox_fields = [
        "Relationship", "Domain", "From Entity", "To Entity", "Edge Table",
        "From Key", "To Key", "Operation Types", "Is Polymorphic",
        "Is Cross-Domain", "OWL Properties", "Weight Columns", "Edge Attributes",
        "SQL Filter", "Has Flow Config", "Flow Type", "Description", "Business Logic",
    ]
    n2 = write_csv(out / "rbox_relationships.csv", rbox_fields, rbox_rows)

    # Sheet 3: ABox
    abox_rows = export_abox(o)
    abox_fields = ["Entity", "Domain", "Table", "Attribute", "Data Type", "Inherited From", "Description"]
    n3 = write_csv(out / "abox_attributes.csv", abox_fields, abox_rows)

    # Sheet 4: Orchestration
    orch_rows = export_orchestration(o)
    orch_fields = [
        "Category", "Entity/Relationship", "Domain",
        "Detail 1", "Detail 2", "Detail 3", "Detail 4",
        "Detail 5", "Detail 6", "Detail 7",
    ]
    n4 = write_csv(out / "orchestration_flows.csv", orch_fields, orch_rows)

    # Summary
    print(f"Exported to {out}/:")
    print(f"  tbox_entities.csv         — {n1} entities")
    print(f"  rbox_relationships.csv    — {n2} relationships")
    print(f"  abox_attributes.csv       — {n3} attributes")
    print(f"  orchestration_flows.csv   — {n4} rows (state machines + flows + cross-domain + axioms)")


if __name__ == "__main__":
    main()
