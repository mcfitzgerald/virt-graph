# Neo4j Migration Protocol

You are starting an interactive Neo4j migration session. Follow the 4-step protocol below, pausing after each step for human confirmation before proceeding.

**Begin with Step 1: Start Neo4j.**

---

## Session Setup

**PostgreSQL**: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
**Neo4j**: `bolt://localhost:7687` (user: `neo4j`, password: `dev_password`)
**Ontology**: `ontology/supply_chain.yaml` (source of truth)
**Migration script**: `neo4j/migrate.py`
**Docker config**: `neo4j/docker-compose.yml`

---

## Migration Protocol (4 Steps)

### Step 1: Start Neo4j

Start the Neo4j container and wait for it to be ready. Check logs for "Started." message.

**Pause for human confirmation.**

---

### Step 2: Run Migration

Execute the ontology-driven migration script.

The script reads `ontology/supply_chain.yaml` and:
1. Creates constraints and indexes from TBox classes
2. Migrates nodes (respects `soft_delete` patterns)
3. Migrates relationships from RBox roles
4. Preserves edge properties from `additional_columns` and `weight_columns`
5. Outputs metrics to `neo4j/migration_metrics.json`

**Pause for human review of migration output.**

---

### Step 3: Verify Counts

Query Neo4j to verify node and relationship counts match ontology `row_count` values.

**Check**:
- Node count per label matches `tbox.classes.*.row_count`
- Relationship count per type matches `rbox.roles.*.row_count`
- No orphaned nodes (all relationships resolve)

**Pause for human review.**

---

### Step 4: Validate Queries

Run sample traversal queries in Neo4j to verify data integrity:
- Supplier tier traversal (SUPPLIES_TO)
- BOM explosion (COMPONENT_OF)
- Shortest path (CONNECTS_TO with weights)

Compare results to equivalent PostgreSQL queries.

**Pause for human approval.**

---

## Ontology → Neo4j Mapping

| Ontology | Neo4j |
|----------|-------|
| `tbox.classes.ClassName` | Node label `:ClassName` |
| `class.sql.table` | Source PostgreSQL table |
| `class.slots` | Node properties |
| `rbox.roles.role_name` | Relationship type `:ROLE_NAME` |
| `role.sql.additional_columns` | Relationship properties |
| `role.sql.weight_columns` | Relationship weight properties |

---

## Validation Checklist

After migration:

- [ ] All node labels exist with expected counts
- [ ] All relationship types exist with expected counts
- [ ] Traversal queries return non-empty results
- [ ] Weighted edges have valid weight properties
- [ ] Gate tests pass: `poetry run pytest tests/test_gate4_validation.py -v`

---

## Troubleshooting

| Issue | Resolution |
|-------|------------|
| Neo4j won't start | Check logs, reset with `down -v` and restart |
| Migration fails | Verify PostgreSQL is running, ontology exists |
| Count mismatch | Check soft delete filtering, verify ontology row_counts are current |
| Connection refused | Wait for Neo4j startup, check port 7687 |

---

## Post-Migration

After successful migration and validation:

1. **Generate ground truth**: Run benchmark ground truth generator
2. **Run benchmarks**: Execute benchmark suite against both systems
3. **Compare results**: Review benchmark summary output
