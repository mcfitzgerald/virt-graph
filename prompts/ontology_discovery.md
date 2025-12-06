# Ontology Discovery Protocol

You are starting an interactive ontology discovery session. Follow the 4-round protocol below, pausing after each round for human review before proceeding.

**Begin with Round 1: Schema Introspection.**

---

## Session Setup

**Database**: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`
**Output**: `ontology/supply_chain.yaml`
**Format reference**: `ontology/TEMPLATE.yaml`

---

## Discovery Protocol (4 Rounds)

### Round 1: Schema Introspection

Query `information_schema` to discover:
- All tables with columns and data types
- Foreign key relationships
- Self-referential tables (where both FK columns point to same table)
- Check constraints (especially self-reference prevention)
- Unique constraints (natural key candidates)

**Look for patterns**:
- `deleted_at` columns → soft delete
- `_id` suffix columns → foreign keys
- Tables with two FKs to same table → edge/relationship tables
- `is_active`, `status` columns → entity state

Present findings as a table summary. **Pause for human review.**

---

### Round 2: TBox (Class Proposals)

For each entity table, propose a class:

| Field | How to determine |
|-------|------------------|
| `description` | Infer from table name and columns |
| `sql.table` | Table name |
| `sql.primary_key` | Usually `id` |
| `sql.identifier` | Natural key columns (code, name, etc.) |
| `slots` | Map non-FK columns → typed attributes |
| `soft_delete` | If `deleted_at` exists, enable |
| `row_count` | Query `COUNT(*)` |

**Slot ranges**: `string`, `integer`, `decimal`, `boolean`, `date`, `timestamp`

Present class proposals as a structured list. **Pause for human corrections.**

---

### Round 3: RBox (Role Proposals)

For each FK relationship, propose a role:

| Field | How to determine |
|-------|------------------|
| `domain` | Class containing the FK |
| `range` | Class being referenced |
| `sql.table` | Table containing the FK |
| `sql.domain_key` | FK column name |
| `sql.range_key` | Usually `id` of target table |
| `traversal_complexity` | See complexity rules below |
| `properties` | Set OWL 2 axioms (see reference) |
| `cardinality` | Derive from FK constraints |
| `row_count` | Query `COUNT(*)` on edge table |

**Complexity rules**:
| Pattern | Complexity | Reason |
|---------|------------|--------|
| Simple FK join | GREEN | Direct SQL |
| Self-referential (both FKs → same table) | YELLOW | Requires recursive traversal |
| Self-referential + weight columns | RED | Requires network algorithms |

**Property hints**:
- Self-referential edges: likely `asymmetric`, `irreflexive`, `acyclic`
- Hierarchical structures (tiers): set `is_hierarchical: true`
- Edges with distance/cost/time columns: set `is_weighted: true`

Present role proposals. **Pause for human corrections.**

---

### Round 4: Draft & Finalize

1. Write the complete ontology to `ontology/supply_chain.yaml`
2. Follow the structure in `ontology/TEMPLATE.yaml`
3. Include all row counts from queries
4. Human approves or requests changes

---

## Validation Checklist

After writing the ontology, validate:

- [ ] **Row counts**: Query actual counts, compare to `row_count` fields
- [ ] **Referential integrity**: Check for orphaned FKs (LEFT JOIN WHERE NULL)
- [ ] **DAG validation**: For `acyclic: true` roles, verify no cycles exist (recursive CTE with path tracking)
- [ ] **Weight ranges**: For `is_weighted: true`, check weight columns have valid values
- [ ] **Gate tests**: `poetry run pytest tests/test_gate2_validation.py -v`

---

## Quick Reference

### OWL 2 Properties
| Property | Definition |
|----------|------------|
| `transitive` | A→B, B→C implies A→C |
| `symmetric` | A→B implies B→A |
| `asymmetric` | A→B implies NOT B→A |
| `reflexive` | A→A is valid |
| `irreflexive` | A→A is NOT valid |
| `functional` | At most one target per source |
| `inverse_functional` | At most one source per target |

### Virtual Graph Extensions
| Property | Meaning |
|----------|---------|
| `acyclic` | Graph has no cycles (DAG) |
| `is_hierarchical` | Has tier/level structure |
| `is_weighted` | Has numeric edge weights |

### Traversal Complexity
| Color | When | Handler |
|-------|------|---------|
| GREEN | Simple FK join | Direct SQL |
| YELLOW | Recursive self-ref | `traverse()` |
| RED | Network algorithm | NetworkX |

### Cardinality
| Notation | Meaning |
|----------|---------|
| `1..1` | Exactly one (required) |
| `0..1` | Zero or one (optional) |
| `1..*` | One or more |
| `0..*` | Zero or more |
