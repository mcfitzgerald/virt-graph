# Virtual Graph Makefile
# Common development tasks and validation scripts

.PHONY: help install test validate-ontology validate-linkml validate-vg \
        gen-jsonschema serve-docs db-up db-down db-reset neo4j-up neo4j-down

# Default target
help:
	@echo "Virtual Graph Development Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-gate1       Run Gate 1 tests"
	@echo "  make test-gate2       Run Gate 2 tests (ontology)"
	@echo ""
	@echo "Ontology Validation:"
	@echo "  make validate-ontology   Run full two-layer validation"
	@echo "  make validate-linkml     Run LinkML structure validation only"
	@echo "  make validate-vg         Run VG annotation validation only"
	@echo ""
	@echo "Code Generation:"
	@echo "  make gen-jsonschema   Generate JSON-Schema from ontology"
	@echo ""
	@echo "Database:"
	@echo "  make db-up            Start PostgreSQL"
	@echo "  make db-down          Stop PostgreSQL"
	@echo "  make db-reset         Reset PostgreSQL (regenerate data)"
	@echo ""
	@echo "Neo4j (benchmarking):"
	@echo "  make neo4j-up         Start Neo4j"
	@echo "  make neo4j-down       Stop Neo4j"
	@echo ""
	@echo "Documentation:"
	@echo "  make serve-docs       Serve documentation locally"

# Setup
install:
	poetry install

# Testing
test:
	poetry run pytest

test-gate1:
	poetry run pytest tests/test_gate1_validation.py -v

test-gate2:
	poetry run pytest tests/test_gate2_validation.py -v

# Ontology Validation
validate-ontology:
	poetry run python scripts/validate_ontology.py --all

validate-linkml:
	poetry run linkml-lint --validate-only ontology/supply_chain.yaml

validate-vg:
	@poetry run python -c "from virt_graph.ontology import OntologyAccessor; o = OntologyAccessor(); print(f'✓ VG validation passed: {len(o.classes)} classes, {len(o.roles)} roles')"

# Code Generation (reference only - not required for operation)
gen-jsonschema:
	@mkdir -p ontology/schemas
	poetry run gen-json-schema ontology/supply_chain.yaml > ontology/schemas/supply_chain.schema.json
	@echo "Generated ontology/schemas/supply_chain.schema.json"

# Database
db-up:
	docker-compose -f postgres/docker-compose.yml up -d

db-down:
	docker-compose -f postgres/docker-compose.yml down

db-reset:
	docker-compose -f postgres/docker-compose.yml down -v
	docker-compose -f postgres/docker-compose.yml up -d

db-logs:
	docker-compose -f postgres/docker-compose.yml logs -f

# Neo4j
neo4j-up:
	docker-compose -f neo4j/docker-compose.yml up -d

neo4j-down:
	docker-compose -f neo4j/docker-compose.yml down

neo4j-logs:
	docker-compose -f neo4j/docker-compose.yml logs -f

# Documentation
serve-docs:
	poetry run mkdocs serve
