"""Shared fixtures for PCG ontology tests."""

import pytest
from pathlib import Path

from virt_graph.ontology import OntologyAccessor


@pytest.fixture(scope="session")
def ontology():
    """Load the PCG ontology once for all tests."""
    return OntologyAccessor(
        Path(__file__).parent.parent / "ontology" / "pcg.yaml",
        validate=False,
    )
