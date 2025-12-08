# Documentation Fixes Required

## Summary

The generated documentation has three main issues:
1. **Low-quality ASCII diagrams** that should be converted to Mermaid
2. **Redundant information** duplicated across multiple files
3. **Stale benchmark results** that need auto-updating when benchmarks re-run

---

## 1. ASCII Diagrams to Convert to Mermaid

### High Priority (Complex diagrams)

| File | Line Range | Description |
|------|------------|-------------|
| `docs/concepts/architecture.md` | 7-46 | System overview - complex nested boxes |
| `docs/concepts/architecture.md` | 151-169 | Query routing - traffic light diagram |
| `docs/concepts/architecture.md` | 218-251 | Route selection flow - decision tree |
| `docs/concepts/architecture.md` | 264-305 | Query flow example - 5-step process |
| `docs/concepts/architecture.md` | 367-383 | Data flow - component diagram |
| `docs/examples/supply-chain/overview.md` | 19-42 | Supply chain domain - multi-tier network |

### Medium Priority

| File | Line Range | Description |
|------|------------|-------------|
| `docs/concepts/overview.md` | 17-31 | Hypothesis model - box diagram |
| `docs/concepts/when-to-use.md` | 7-30 | Decision flowchart |
| `docs/concepts/when-to-use.md` | 169-185 | Hybrid architecture |
| `docs/workflow/ontology-discovery.md` | 7-22 | Discovery rounds flow |
| `docs/workflow/pattern-discovery.md` | 7-28 | Pattern phases flow |
| `docs/workflow/analysis-sessions.md` | 7-42 | Session loop |
| `docs/evaluation/methodology.md` | 45-69 | Coverage matrix |

### Low Priority (Simple)

| File | Line Range | Description |
|------|------------|-------------|
| `docs/workflow/overview.md` | 122-141 | Analysis per query flow |

---

## 2. Redundant Content to Consolidate

### Benchmark Metrics (most duplicated)

**Files repeating the same benchmark numbers:**
- `docs/index.md` (lines 96-115)
- `docs/concepts/overview.md` (lines 108-119)
- `docs/concepts/when-to-use.md` (lines 98-111)
- `docs/evaluation/benchmark-results.md` (main source)
- `docs/examples/supply-chain/benchmark.md` (near-duplicate of benchmark-results.md)
- `docs/evaluation/research-findings.md` (lines 23-72)

**Recommendation:**
- Keep `docs/evaluation/benchmark-results.md` as the single source of truth
- Other files should reference it with a link instead of duplicating metrics
- Consider using MkDocs snippets/includes if available

### Three-Phase Workflow

**Files with overlapping content:**
- `docs/index.md` - summary
- `docs/concepts/overview.md` - moderate detail
- `docs/workflow/overview.md` - full detail (canonical)

**Recommendation:**
- `docs/workflow/overview.md` is the canonical source
- Other files should have brief summaries with links to workflow overview

### Architecture Diagrams

**Duplicate/similar diagrams:**
- `docs/concepts/architecture.md` - current version
- `docs/archive/v0.8/architecture.md` - nearly identical

**Recommendation:**
- Archive is fine as-is (historical)
- Ensure current version is clearly the authoritative one

### Safety Limits

**Files listing MAX_DEPTH=50, MAX_NODES=10,000, etc:**
- `docs/concepts/architecture.md`
- `docs/reference/api/handlers.md`
- `docs/evaluation/benchmark-results.md`

**Recommendation:**
- Define once in `docs/reference/api/handlers.md` (API reference)
- Other files link to it

---

## 3. Benchmark Results Auto-Update

### Current Problem

The benchmark script (`benchmark/run.py`) outputs to:
- `benchmark/results/benchmark_results.md`
- `benchmark/results/benchmark_results.json`

But the documentation references hardcoded metrics in multiple files that don't update when benchmarks re-run.

### Solution (IMPLEMENTED)

The benchmark script has been updated to:

1. **Output to docs location:** ✅
   - Added `DOCS_RESULTS_DIR` pointing to `docs/evaluation/`
   - Generates `benchmark-results-latest.md` in docs directory

2. **Generate doc-friendly version:** ✅
   - Added `generate_docs_report()` function that creates cleaner markdown
   - Focuses on key metrics without internal implementation details

3. **Makefile targets added:** ✅
   - `make benchmark` - Run full benchmark (VG + Neo4j)
   - `make benchmark-vg` - Run Virtual Graph only

### Remaining TODO

| File | Change |
|------|--------|
| `docs/evaluation/benchmark-results.md` | Update to reference `benchmark-results-latest.md` or include it |

---

## 4. Archive Cleanup

The `docs/archive/v0.8/` directory contains 15 files that significantly overlap with current docs. This is fine for historical reference but should be clearly marked.

**Recommendation:**
- Add a note at the top of archived files: "This is archived documentation from v0.8. See current docs at [link]."
- Or move archive outside main docs tree

---

## Priority Order

1. **Benchmark auto-update** - Prevents stale data from accumulating
2. **Consolidate benchmark references** - Most duplicated content
3. **Convert ASCII to Mermaid** - Visual improvement
4. **Remove other redundant content** - Nice to have

---

## Execution Checklist

- [x] Modify `benchmark/run.py` to output to docs
- [ ] Update `docs/evaluation/benchmark-results.md` structure
- [x] Add Makefile target for benchmark + docs update
- [ ] Replace ASCII diagrams in `docs/concepts/architecture.md` (6 diagrams)
- [ ] Replace ASCII diagrams in other files (8 diagrams)
- [ ] Consolidate benchmark metrics references (5 files)
- [ ] Consolidate three-phase workflow content (2 files)
- [ ] Add archive notice to v0.8 docs
