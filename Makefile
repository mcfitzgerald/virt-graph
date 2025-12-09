# Virtual Graph Makefile
# Common development tasks and validation scripts

.PHONY: help install test validate-ontology validate-linkml validate-vg \
        show-ontology show-tbox show-rbox gen-jsonschema serve-docs \
        db-up db-down db-reset db-logs validate-entities \
        neo4j-up neo4j-down neo4j-logs benchmark benchmark-vg

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
	@echo "Ontology:"
	@echo "  make validate-ontology   Run full two-layer validation"
	@echo "  make validate-linkml     Run LinkML structure validation only"
	@echo "  make validate-vg         Run VG annotation validation only"
	@echo "  make show-ontology       Show TBox/RBox definitions"
	@echo "  make show-tbox           Show entity classes only"
	@echo "  make show-rbox           Show relationships only"
	@echo ""
	@echo "Code Generation:"
	@echo "  make gen-jsonschema   Generate JSON-Schema from ontology"
	@echo ""
	@echo "Database:"
	@echo "  make db-up            Start PostgreSQL"
	@echo "  make db-down          Stop PostgreSQL"
	@echo "  make db-reset         Reset PostgreSQL (regenerate data)"
	@echo "  make validate-entities  Verify named test entities exist"
	@echo ""
	@echo "Neo4j (benchmarking):"
	@echo "  make neo4j-up         Start Neo4j"
	@echo "  make neo4j-down       Stop Neo4j"
	@echo ""
	@echo "Benchmarking:"
	@echo "  make benchmark        Run full benchmark (VG + Neo4j)"
	@echo "  make benchmark-vg     Run Virtual Graph benchmark only"
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

show-ontology:
	@poetry run python scripts/show_ontology.py

show-tbox:
	@poetry run python scripts/show_ontology.py --tbox-only

show-rbox:
	@poetry run python scripts/show_ontology.py --rbox-only

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

validate-entities:
	poetry run python scripts/validate_entities.py

# Neo4j
neo4j-up:
	docker-compose -f neo4j/docker-compose.yml up -d

neo4j-down:
	docker-compose -f neo4j/docker-compose.yml down

neo4j-logs:
	docker-compose -f neo4j/docker-compose.yml logs -f

# Benchmarking
benchmark:
	poetry run python benchmark/run.py --system both
	@echo ""
	@echo "Results saved to benchmark/results/ and docs/evaluation/"

benchmark-vg:
	poetry run python benchmark/run.py --system vg
	@echo ""
	@echo "Results saved to benchmark/results/ and docs/evaluation/"

# Documentation
serve-docs:
	poetry run mkdocs serve
