# Virtual Graph Makefile
# Common development tasks and validation scripts

.PHONY: help install test test-handlers test-ontology \
        validate-ontology validate-linkml validate-vg \
        show-ontology show-tbox show-rbox gen-jsonschema serve-docs \
        db-up db-down db-reset db-logs \
        neo4j-up neo4j-down neo4j-stop neo4j-reset neo4j-cycle neo4j-logs validate-neo4j \
        fmcg-generate fmcg-validate fmcg-db-up fmcg-db-down fmcg-db-reset fmcg-db-logs fmcg-test

# Default target
help:
	@echo "Virtual Graph Development Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install dependencies"
	@echo ""
	@echo "FMCG Example (Prism Consumer Goods) - Primary:"
	@echo "  make fmcg-db-up       Start FMCG PostgreSQL (port 5433)"
	@echo "  make fmcg-db-down     Stop FMCG PostgreSQL"
	@echo "  make fmcg-db-reset    Reset FMCG PostgreSQL (wipe and reload)"
	@echo "  make fmcg-db-logs     View FMCG PostgreSQL logs"
	@echo "  make fmcg-generate    Generate ~11.4M rows of FMCG data"
	@echo "  make fmcg-validate    Validate data without writing SQL"
	@echo "  make fmcg-test        Run FMCG tests"
	@echo ""
	@echo "Documentation:"
	@echo "  make serve-docs       Serve documentation locally"
	@echo ""
	@echo "Legacy (supply_chain_example - archived):"
	@echo "  make test             Run supply chain tests"
	@echo "  make db-up/down/reset Start/stop/reset supply chain PostgreSQL"
	@echo "  make neo4j-up/down    Start/stop Neo4j for benchmarking"
	@echo "  make validate-ontology   Run full two-layer validation"

# Setup
install:
	poetry install

# Testing
test:
	poetry run pytest supply_chain_example/tests/

test-handlers:
	poetry run pytest supply_chain_example/tests/test_handler_safety.py -v

test-ontology:
	poetry run pytest supply_chain_example/tests/test_ontology_validation.py -v

# Ontology Validation
validate-ontology:
	poetry run python scripts/validate_ontology.py --all

validate-linkml:
	poetry run linkml-lint --validate-only supply_chain_example/ontology/supply_chain.yaml

validate-vg:
	@poetry run python -c "from virt_graph.ontology import OntologyAccessor; from pathlib import Path; o = OntologyAccessor(Path('supply_chain_example/ontology/supply_chain.yaml')); print(f'✓ VG validation passed: {len(o.classes)} classes, {len(o.roles)} roles')"

show-ontology:
	@poetry run python scripts/show_ontology.py

show-tbox:
	@poetry run python scripts/show_ontology.py --tbox-only

show-rbox:
	@poetry run python scripts/show_ontology.py --rbox-only

# Code Generation (reference only - not required for operation)
gen-jsonschema:
	@mkdir -p supply_chain_example/ontology/schemas
	poetry run gen-json-schema supply_chain_example/ontology/supply_chain.yaml > supply_chain_example/ontology/schemas/supply_chain.schema.json
	@echo "Generated supply_chain_example/ontology/schemas/supply_chain.schema.json"

# Database
db-up:
	docker-compose -f supply_chain_example/postgres/docker-compose.yml up -d

db-down:
	docker-compose -f supply_chain_example/postgres/docker-compose.yml down

db-reset:
	docker-compose -f supply_chain_example/postgres/docker-compose.yml down -v
	docker-compose -f supply_chain_example/postgres/docker-compose.yml up -d

db-logs:
	docker-compose -f supply_chain_example/postgres/docker-compose.yml logs -f

# Neo4j
neo4j-up:
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml up -d

neo4j-down:
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml down

neo4j-stop:  ## Stop Neo4j with clean shutdown (waits for container to fully stop)
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml stop
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml down

neo4j-reset:
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml down -v
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml up -d

neo4j-cycle:  ## Full cycle: stop, remove volumes, restart (fixes stale PID issues)
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml stop
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml down -v
	@echo "Waiting for clean shutdown..."
	sleep 2
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml up -d
	@echo "Neo4j restarting. Wait ~20s for full startup."

neo4j-logs:
	docker-compose -f supply_chain_example/neo4j/docker-compose.yml logs -f

validate-neo4j:  ## Validate Neo4j graph against ontology
	poetry run python scripts/validate_neo4j.py

# Documentation
serve-docs:
	poetry run mkdocs serve

# FMCG Example (Prism Consumer Goods) - Primary example
fmcg-generate:  ## Generate FMCG seed data (~11.4M rows)
	poetry run python fmcg_example/scripts/generate_data.py --output fmcg_example/postgres/seed.sql

fmcg-validate:  ## Validate FMCG data generation without writing SQL
	poetry run python fmcg_example/scripts/generate_data.py --validate-only

fmcg-test:  ## Run FMCG tests
	poetry run pytest fmcg_example/tests/ -v

fmcg-db-up:  ## Start FMCG PostgreSQL (port 5433)
	docker-compose -f fmcg_example/postgres/docker-compose.yml up -d

fmcg-db-down:  ## Stop FMCG PostgreSQL
	docker-compose -f fmcg_example/postgres/docker-compose.yml down

fmcg-db-reset:  ## Reset FMCG PostgreSQL (wipe and reload)
	docker-compose -f fmcg_example/postgres/docker-compose.yml down -v
	docker-compose -f fmcg_example/postgres/docker-compose.yml up -d

fmcg-db-logs:  ## View FMCG PostgreSQL logs
	docker-compose -f fmcg_example/postgres/docker-compose.yml logs -f
