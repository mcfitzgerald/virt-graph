"""Integration tests for CSV ontology export."""

import csv
import importlib.util
import tempfile
from pathlib import Path

import pytest

# Import from scripts/ (not a package)
_spec = importlib.util.spec_from_file_location(
    "export_ontology_csv",
    Path(__file__).resolve().parents[2] / "scripts" / "export_ontology_csv.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
export_tbox = _mod.export_tbox
export_rbox = _mod.export_rbox
export_abox = _mod.export_abox
export_orchestration = _mod.export_orchestration
write_csv = _mod.write_csv


class TestExportCounts:
    """Verify row counts match ontology."""

    def test_tbox_count(self, ontology):
        rows = export_tbox(ontology)
        assert len(rows) == 41

    def test_rbox_count(self, ontology):
        rows = export_rbox(ontology)
        assert len(rows) == 57

    def test_abox_has_rows(self, ontology):
        rows = export_abox(ontology)
        assert len(rows) > 100  # 166 expected

    def test_orchestration_has_rows(self, ontology):
        rows = export_orchestration(ontology)
        assert len(rows) > 30


class TestExportContent:
    """Verify content quality."""

    def test_tbox_sorted_by_domain(self, ontology):
        rows = export_tbox(ontology)
        domains = [r["Domain"] for r in rows]
        assert domains == sorted(domains)

    def test_rbox_sorted_by_domain(self, ontology):
        rows = export_rbox(ontology)
        domains = [r["Domain"] for r in rows]
        assert domains == sorted(domains)

    def test_tbox_has_state_machines(self, ontology):
        rows = export_tbox(ontology)
        sm_rows = [r for r in rows if r["Has State Machine"] == "Y"]
        assert len(sm_rows) >= 6  # Order, PO, Batch, Shipment, GoodsReceipt, Return

    def test_rbox_has_polymorphic(self, ontology):
        rows = export_rbox(ontology)
        poly = [r for r in rows if r["Is Polymorphic"] == "Y"]
        assert len(poly) >= 5

    def test_rbox_has_cross_domain(self, ontology):
        rows = export_rbox(ontology)
        xd = [r for r in rows if r["Is Cross-Domain"] == "Y"]
        assert len(xd) == 18

    def test_abox_inherited_attrs_tagged(self, ontology):
        rows = export_abox(ontology)
        inherited = [r for r in rows if r["Inherited From"]]
        assert len(inherited) > 0
        sources = {r["Inherited From"] for r in inherited}
        assert "HasActiveFlag" in sources
        assert "HasName" in sources

    def test_orchestration_categories(self, ontology):
        rows = export_orchestration(ontology)
        cats = {r["Category"] for r in rows}
        assert cats == {"State Machine", "Flow", "Cross-Domain", "Axiom"}


class TestCsvRoundtrip:
    """Verify CSV files are well-formed."""

    def test_csv_roundtrip(self, ontology):
        rows = export_tbox(ontology)
        fields = list(rows[0].keys())
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = Path(f.name)
            write_csv(path, fields, rows)

        with open(path) as f:
            reader = csv.DictReader(f)
            read_rows = list(reader)

        assert len(read_rows) == 41
        assert read_rows[0]["Entity"]  # not empty
        path.unlink()
