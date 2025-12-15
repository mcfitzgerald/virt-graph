# Test Plan: virt_graph.yaml as Single Source of Truth

This plan validates that the refactored ontology system works correctly with `virt_graph.yaml` as the authoritative metamodel.

## Prerequisites

```bash
make db-up  # Ensure PostgreSQL is running
```

## Test 1: Validate Metamodel Itself

Confirm `virt_graph.yaml` is valid LinkML:

```bash
poetry run linkml-lint --validate-only ontology/virt_graph.yaml
```

Expected: No errors, exits 0.

## Test 2: Validate Existing Ontology

Confirm `supply_chain.yaml` passes both validation layers:

```bash
# Layer 1: LinkML structure
poetry run linkml-lint --validate-only ontology/supply_chain.yaml

# Layer 2: VG annotations (derived from virt_graph.yaml)
poetry run python -c "
from virt_graph.ontology import OntologyAccessor
o = OntologyAccessor(validate=True)
print(f'Loaded {len(o.classes)} classes, {len(o.roles)} roles')
"
```

Expected: Both pass, shows 9 classes and 16 roles.

## Test 3: Verify Dynamic Rule Loading

Confirm OntologyAccessor extracts rules from metamodel:

```bash
poetry run python -c "
from virt_graph.ontology import OntologyAccessor

# Trigger metamodel loading
OntologyAccessor(validate=False)

print('Entity required fields:', OntologyAccessor._entity_required)
print('Relationship required fields:', OntologyAccessor._relationship_required)
print('Valid complexities:', OntologyAccessor._valid_complexities)
"
```

Expected:
```
Entity required fields: {'table', 'primary_key'}
Relationship required fields: {'edge_table', 'domain_key', 'range_key', 'domain_class', 'range_class', 'traversal_complexity'}
Valid complexities: {'GREEN', 'YELLOW', 'RED'}
```

## Test 4: Create New Ontology Using Discovery Protocol (Blind Test)

**IMPORTANT**: This test must be executed by an isolated agent that cannot see the existing `supply_chain.yaml`. This ensures a true "blind" comparison where the discovery protocol generates an ontology purely from schema introspection.

### Why Isolation Matters
If the agent can read the existing ontology, it may copy naming conventions, relationship choices, or structural decisions rather than deriving them independently from the database schema. This defeats the purpose of validating the discovery protocol.

### Execution Method

Dispatch to a background agent with restricted context:

```
You are generating a fresh ontology from scratch using ONLY:
1. The metamodel at `ontology/virt_graph.yaml`
2. The discovery protocol at `prompts/ontology_discovery.md`
3. Database introspection via psycopg2

**CRITICAL: Do NOT read ontology/supply_chain.yaml or any other existing ontology files. This is a blind test.**

**Database Connection:**
- Host: localhost, Port: 5432, Database: supply_chain
- User: virt_graph, Password: dev_password
- Use psycopg2 (NOT psql CLI - may not be installed)

**Your Task:**
1. Read `ontology/virt_graph.yaml` to understand the metamodel (SQLMappedClass, SQLMappedRelationship requirements)
2. Read `prompts/ontology_discovery.md` to understand the protocol
3. Execute all 4 rounds of the discovery protocol:
   - Round 1: Schema introspection (tables, FKs, constraints, row counts)
   - Round 2: Entity class discovery (TBox)
   - Round 3: Relationship class discovery (RBox) - classify GREEN/YELLOW/RED
   - Round 4: Write complete ontology to `ontology/supply_chain_test.yaml`
4. Validate the ontology passes both layers:
   - `poetry run linkml-lint --validate-only ontology/supply_chain_test.yaml`
   - `OntologyAccessor(Path('ontology/supply_chain_test.yaml'), validate=True)`

**Output:** Write a valid LinkML ontology to `ontology/supply_chain_test.yaml`
```

### Expected Agent Behavior
- Agent reads only metamodel and discovery protocol
- Agent queries database schema via psycopg2
- Agent generates ontology based purely on schema analysis
- Agent validates output before completion

## Test 5: Validate New Ontology

```bash
# Layer 1
poetry run linkml-lint --validate-only ontology/supply_chain_test.yaml

# Layer 2
poetry run python -c "
from pathlib import Path
from virt_graph.ontology import OntologyAccessor
o = OntologyAccessor(Path('ontology/supply_chain_test.yaml'), validate=True)
print(f'Loaded {len(o.classes)} classes, {len(o.roles)} roles')
"
```

Expected: Both layers pass.

## Test 6: Compare Ontologies

Compare the newly generated ontology with the existing one:

```bash
poetry run python -c "
from pathlib import Path
from virt_graph.ontology import OntologyAccessor

existing = OntologyAccessor(Path('ontology/supply_chain.yaml'), validate=False)
new = OntologyAccessor(Path('ontology/supply_chain_test.yaml'), validate=False)

print('=== Entity Classes (TBox) ===')
print(f'Existing: {sorted(existing.classes.keys())}')
print(f'New:      {sorted(new.classes.keys())}')

print('\n=== Relationship Classes (RBox) ===')
print(f'Existing: {sorted(existing.roles.keys())}')
print(f'New:      {sorted(new.roles.keys())}')

print('\n=== Complexity Distribution ===')
for complexity in ['GREEN', 'YELLOW', 'RED']:
    existing_count = sum(1 for r in existing.roles if existing.get_role_complexity(r) == complexity)
    new_count = sum(1 for r in new.roles if new.get_role_complexity(r) == complexity)
    print(f'{complexity}: existing={existing_count}, new={new_count}')
"
```

Expected: Same or similar classes/roles with matching complexity classifications.

## Test 7: Full Validation Script

Run the full validation script on all ontologies:

```bash
poetry run python scripts/validate_ontology.py --all
```

Expected: All ontology files pass both layers.

## Test 8: Ontology Validation Tests

Run ontology validation tests:

```bash
poetry run pytest tests/test_ontology_validation.py -v
```

Expected: All tests pass (28 tests covering structure, annotations, coverage, mappings, integrity, queries).

## Test 9: Metamodel Extension Test

Verify that adding a new required field to `virt_graph.yaml` automatically updates validation:

1. Add a test field to SQLMappedClass in `virt_graph.yaml`:
   ```yaml
   test_field:
     range: string
     required: true
   ```

2. Run validation - should FAIL:
   ```bash
   poetry run python -c "
   from virt_graph.ontology import OntologyAccessor
   o = OntologyAccessor(validate=True)
   "
   ```

3. Remove the test field and verify validation passes again.

This confirms the single-source-of-truth architecture works correctly.

## Cleanup

```bash
# Remove test ontology if created
rm -f ontology/supply_chain_test.yaml

# Stop database
make db-down
```

## Success Criteria

- [ ] All 9 tests pass
- [ ] Validation rules derived dynamically from virt_graph.yaml
- [ ] New ontology created via discovery protocol is valid
- [ ] No hardcoded validation rules in Python code
