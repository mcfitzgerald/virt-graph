# Neo4j Migration Primer

**Goal**: Migrate data from PostgreSQL to Neo4j using the ontology as the source of truth, enabling benchmark comparisons.

**Prerequisites**:
- Completed ontology discovery (`ontology/supply_chain.yaml` exists and is validated)
- Completed pattern discovery (`patterns/raw/` populated)
- PostgreSQL running
- Docker available

---

## Connection Details

**PostgreSQL**:
```
postgresql://virt_graph:dev_password@localhost:5432/supply_chain
```

**Neo4j**:
```
bolt://localhost:7687
user: neo4j
password: dev_password
```

---

## Migration Steps

### Step 1: Start Neo4j
```bash
docker-compose -f neo4j/docker-compose.yml up -d
```

Wait for Neo4j to be ready:
```bash
docker-compose -f neo4j/docker-compose.yml logs -f
# Look for "Started." message
```

### Step 2: Run Ontology-Driven Migration
```bash
poetry run python neo4j/migrate.py
```

The migration script:
1. Reads `ontology/supply_chain.yaml` as source of truth
2. Creates Neo4j constraints and indexes from ontology classes
3. Migrates nodes (respects soft delete patterns)
4. Migrates relationships with properties
5. Validates counts against ontology expectations
6. Outputs metrics to `neo4j/migration_metrics.json`

### Step 3: Verify Migration
```bash
# Check node counts in Neo4j
docker exec -it neo4j cypher-shell -u neo4j -p dev_password \
  "MATCH (n) RETURN labels(n)[0] as label, count(*) ORDER BY label"

# Check relationship counts
docker exec -it neo4j cypher-shell -u neo4j -p dev_password \
  "MATCH ()-[r]->() RETURN type(r) as type, count(*) ORDER BY type"
```

---

## Ontology → Neo4j Mapping

The migration script uses this mapping:

| Ontology | Neo4j |
|----------|-------|
| `tbox.classes.ClassName` | Node label `ClassName` |
| `class.sql.table` | Source PostgreSQL table |
| `class.sql.primary_key` | Node property for matching |
| `class.slots` | Node properties |
| `rbox.roles.role_name` | Relationship type `ROLE_NAME` |
| `role.sql.additional_columns` | Relationship properties |
| `role.sql.weight_columns` | Relationship weight properties |

### Label Mapping (Special Cases)
```python
LABEL_MAPPING = {
    "SupplierCertification": "Certification",  # Shorter label
}
```

---

## Expected Results

After successful migration:

**Nodes** (~27K total):
| Label | Expected Count |
|-------|----------------|
| Supplier | 500 |
| Part | 5,003 |
| Product | 200 |
| Facility | 50 |
| Customer | 1,000 |
| Order | 20,000 |
| Shipment | ~4,000 |
| Certification | ~1,050 |

**Relationships** (~100K total):
| Type | Expected Count |
|------|----------------|
| SUPPLIES_TO | ~300 |
| COMPONENT_OF | ~15,000 |
| CONNECTS_TO | ~150 |
| PROVIDES | 5,003 |
| CAN_SUPPLY | ~2,500 |
| CONTAINS_COMPONENT | ~400 |
| PLACED_BY | 20,000 |
| CONTAINS_ITEM | ~50,000 |
| SHIPS_FROM | ~4,000 |
| HOLDS | ~5,000 |
| HAS_CERTIFICATION | ~1,050 |

---

## Troubleshooting

### Neo4j Won't Start
```bash
# Check logs
docker-compose -f neo4j/docker-compose.yml logs

# Reset and retry
docker-compose -f neo4j/docker-compose.yml down -v
docker-compose -f neo4j/docker-compose.yml up -d
```

### Migration Fails
```bash
# Check PostgreSQL is running
docker-compose -f postgres/docker-compose.yml ps

# Check ontology file exists
cat ontology/supply_chain.yaml | head -20

# Run with verbose output
poetry run python neo4j/migrate.py 2>&1 | tee migration.log
```

### Count Mismatch
If migrated counts don't match ontology expectations:
1. Check soft delete filtering (deleted_at IS NULL)
2. Verify ontology row_count values are current
3. Re-run data generation if needed: `poetry run python scripts/generate_data.py`

---

## Post-Migration Validation

### Run Gate Tests
```bash
poetry run pytest tests/test_gate4_validation.py -v
```

### Verify Sample Queries
```cypher
// Supplier tier traversal
MATCH path = (s:Supplier {name: 'Acme Corp'})-[:SUPPLIES_TO*1..3]->(buyer:Supplier)
RETURN path LIMIT 10;

// BOM explosion
MATCH path = (p:Part {part_number: 'TURBO-001'})-[:COMPONENT_OF*1..5]->(child:Part)
RETURN path LIMIT 20;

// Shortest path
MATCH (start:Facility {name: 'Chicago Warehouse'}),
      (end:Facility {name: 'LA Distribution Center'}),
      path = shortestPath((start)-[:CONNECTS_TO*]-(end))
RETURN path;
```

---

## Backup/Restore

### Backup Neo4j Before Migration
```bash
docker volume create neo4j_data_backup
docker run --rm -v neo4j_data:/from -v neo4j_data_backup:/to alpine cp -a /from/. /to/
```

### Restore Neo4j From Backup
```bash
docker-compose -f neo4j/docker-compose.yml down
docker volume rm neo4j_data
docker run --rm -v neo4j_data_backup:/from -v neo4j_data:/to alpine cp -a /from/. /to/
docker-compose -f neo4j/docker-compose.yml up -d
```

### Fresh Neo4j Start
```bash
docker-compose -f neo4j/docker-compose.yml down -v
docker-compose -f neo4j/docker-compose.yml up -d
poetry run python neo4j/migrate.py
```

---

## Next Steps

After successful migration:

1. **Generate Ground Truth**
   ```bash
   poetry run python benchmark/generate_ground_truth.py
   ```

2. **Run Benchmarks**
   ```bash
   poetry run python benchmark/run.py --system both
   ```

3. **View Results**
   ```bash
   cat benchmark/results/latest/summary.json
   ```

---

## Session Flow

1. **Start Neo4j**: `docker-compose -f neo4j/docker-compose.yml up -d`
2. **Run migration**: `poetry run python neo4j/migrate.py`
3. **Verify counts**: Check output matches ontology expectations
4. **Run gate tests**: `poetry run pytest tests/test_gate4_validation.py -v`
5. **Proceed to benchmarks**: See benchmark documentation
