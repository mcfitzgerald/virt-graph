# Virtual Graph Makefile
# Ontology construction, validation, and handler framework

.PHONY: help install test-ontology \
        validate-ontology validate-linkml validate-vg \
        show-ontology show-tbox show-rbox serve-docs \
        neo4j-up neo4j-down neo4j-cycle validate-neo4j

# Default target
help:
	@echo "Virtual Graph Development Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install            Install dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test-ontology      Run ontology validation tests"
	@echo ""
	@echo "Ontology:"
	@echo "  make validate-ontology  Run full two-layer validation"
	@echo "  make validate-linkml    Run LinkML structure validation only"
	@echo "  make validate-vg        Run VG annotation validation only"
	@echo "  make show-ontology      Show TBox/RBox definitions"
	@echo "  make show-tbox          Show entity classes only"
	@echo "  make show-rbox          Show relationships only"
	@echo ""
	@echo "Neo4j (benchmarking):"
	@echo "  make neo4j-up           Start Neo4j"
	@echo "  make neo4j-down         Stop Neo4j"
	@echo "  make neo4j-cycle        Full cycle: stop, wipe, restart"
	@echo "  make validate-neo4j     Validate Neo4j graph against ontology"
	@echo ""
	@echo "Documentation:"
	@echo "  make serve-docs         Serve documentation locally"

# Setup
install:
	poetry install

# Testing
test-ontology:
	poetry run pytest fmcg_example/tests/test_ontology.py -v

# Ontology Validation
validate-ontology:
	poetry run python scripts/validate_ontology.py --all

validate-linkml:
	poetry run linkml-lint --validate-only fmcg_example/ontology/prism_fmcg.yaml

validate-vg:
	@poetry run python -c "from virt_graph.ontology import OntologyAccessor; from pathlib import Path; o = OntologyAccessor(Path('fmcg_example/ontology/prism_fmcg.yaml')); print(f'✓ VG validation passed: {len(o.classes)} classes, {len(o.roles)} roles')"

show-ontology:
	@poetry run python scripts/show_ontology.py

show-tbox:
	@poetry run python scripts/show_ontology.py --tbox-only

show-rbox:
	@poetry run python scripts/show_ontology.py --rbox-only

# Neo4j
neo4j-up:
	docker-compose -f fmcg_example/neo4j/docker-compose.yml up -d

neo4j-down:
	docker-compose -f fmcg_example/neo4j/docker-compose.yml down

neo4j-cycle:  ## Full cycle: stop, remove volumes, restart (fixes stale PID issues)
	docker-compose -f fmcg_example/neo4j/docker-compose.yml stop
	docker-compose -f fmcg_example/neo4j/docker-compose.yml down -v
	@echo "Waiting for clean shutdown..."
	sleep 2
	docker-compose -f fmcg_example/neo4j/docker-compose.yml up -d
	@echo "Neo4j restarting. Wait ~20s for full startup."

validate-neo4j:  ## Validate Neo4j graph against ontology
	poetry run python scripts/validate_neo4j.py

# Documentation
serve-docs:
	poetry run mkdocs serve
