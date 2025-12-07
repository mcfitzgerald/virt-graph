# Benchmark Archive

Historical benchmark results are stored here with version tags.

## Versioning Scheme

Results are versioned by date and codebase version:

```
v{YYYY-MM-DD}_{version}/
├── benchmark_results.md
├── benchmark_results.json
└── metadata.yaml
```

## Archived Versions

| Version | Date | VG Version | Notes |
|---------|------|------------|-------|
| v2024-12-04_0.7.0 | 2024-12-04 | 0.7.0 | Initial prototype benchmark |

## Running Fresh Benchmarks

To run a new benchmark and archive the results:

```bash
# 1. Archive current results (if any)
./scripts/archive_benchmark.sh

# 2. Ensure databases are running
docker-compose -f postgres/docker-compose.yml up -d
docker-compose -f neo4j/docker-compose.yml up -d

# 3. Migrate data to Neo4j
poetry run python neo4j/migrate.py

# 4. Generate ground truth
poetry run python benchmark/generate_ground_truth.py

# 5. Run benchmark
poetry run python benchmark/run.py --system both

# 6. Results appear in benchmark/results/
```

## Metadata Schema

Each archived version includes a `metadata.yaml`:

```yaml
version: "v2024-12-04_0.7.0"
date: "2024-12-04"
virt_graph_version: "0.7.0"
git_commit: "abc123"
database:
  postgres_version: "14"
  neo4j_version: "5.x"
  row_counts:
    suppliers: 500
    parts: 5003
    # ...
notes: |
  Initial prototype benchmark.
  Safety limits triggered on 5 BOM queries.
```
