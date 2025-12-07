# Documentation Overhaul Plan

## Goal
Restructure virt-graph documentation to clearly separate:
- **Generic framework** (concepts, components, how-to)
- **Supply chain example** (runnable worked example inline)

Target both audiences: domain developers AND research evaluators.

## Current State Analysis

**Quality**: 7/10 - content is good but poorly organized
**Files**: 22 docs, ~40% generic, ~60% supply-chain specific
**Issues**:
- Overlap: `architecture.md` vs `architecture/overview.md`
- Missing files referenced in mkdocs.yml
- Build-phase structure (phase1-6) not user-relevant
- Mixed generic/domain content throughout

## Final Documentation Structure

```
docs/
├── index.md                         # Landing page: vision, quick nav, both audiences
│
├── concepts/                        # WHAT IS VIRTUAL GRAPH? (generic)
│   ├── overview.md                  #   Vision, hypothesis, research question
│   ├── architecture.md              #   System layers, traffic light routing, data flow
│   └── when-to-use.md               #   Decision framework: VG vs graph DB vs raw SQL
│
├── workflow/                        # THE 3-PHASE PROCESS (generic)
│   ├── overview.md                  #   Mermaid diagram (recreated from whiteboard)
│   ├── ontology-discovery.md        #   Phase 1: Schema introspection → ontology
│   ├── pattern-discovery.md         #   Phase 2: Explore ontology → query patterns
│   └── analysis-sessions.md         #   Phase 3: Interactive querying loop
│
├── components/                      # TECHNICAL REFERENCE (generic)
│   ├── ontology/
│   │   ├── overview.md              #     What ontology does, LinkML + VG extensions
│   │   ├── format.md                #     TBox/RBox structure, all annotations
│   │   ├── creating.md              #     How to create (TEMPLATE.yaml guide)
│   │   └── validation.md            #     Two-layer validation, OntologyAccessor API
│   ├── handlers/
│   │   ├── overview.md              #     Traffic light routing, when to use which
│   │   ├── traversal.md             #     YELLOW: traverse(), bom_explode()
│   │   ├── pathfinding.md           #     RED: shortest_path(), all_shortest_paths()
│   │   └── network.md               #     RED: centrality(), components(), neighbors()
│   ├── estimator/
│   │   ├── overview.md              #     Why estimation matters, guard system
│   │   ├── sampler.md               #     GraphSampler, auto-detection
│   │   ├── models.md                #     Adaptive damping, extrapolation
│   │   └── guards.md                #     Runtime decision logic
│   └── patterns/
│       ├── overview.md              #     Pattern templates vs raw patterns
│       └── templates.md             #     Template structure, matching, usage
│
├── infrastructure/                  # SETUP & OPERATIONS (generic)
│   ├── installation.md              #   Poetry, dependencies, prerequisites
│   ├── database.md                  #   Docker PostgreSQL setup (generic pattern)
│   └── development.md               #   Testing, Makefile, contributing
│
├── examples/                        # WORKED EXAMPLE (supply chain specific)
│   └── supply-chain/
│       ├── overview.md              #     What you'll learn, prerequisites
│       ├── setup.md                 #     docker-compose up, seed data, verify
│       ├── ontology.md              #     Tour of supply_chain.yaml
│       ├── patterns.md              #     Key discovered patterns
│       ├── queries.md               #     Step-by-step query walkthroughs
│       └── benchmark.md             #     Run benchmarks against Neo4j
│
├── evaluation/                      # RESEARCH & BENCHMARKS (full documentation)
│   ├── methodology.md               #   NEW: How to design analysis questions
│   │                                #     - Using web research for domain knowledge
│   │                                #     - Generating business questions (not SQL)
│   │                                #     - Covering ontology space systematically
│   │                                #     - Demonstrating graph strengths
│   ├── benchmark-setup.md           #   Full Neo4j setup, migration, infrastructure
│   ├── benchmark-results.md         #   Supply chain benchmark results
│   ├── tco-framework.md             #   Enterprise TCO analysis framework
│   └── research-findings.md         #   Synthesis: does the hypothesis hold?
│
└── reference/                       # API & HISTORY
    ├── api/
    │   ├── handlers.md              #     Function signatures, parameters, returns
    │   ├── ontology.md              #     OntologyAccessor API reference
    │   └── estimator.md             #     Estimator module API reference
    └── history.md                   #     Project evolution (distilled from phases)

# Note: CHANGELOG.md stays at project root, linked from docs if needed
```

## Content Migration Plan

### Phase 1: Archive Current Docs
1. Move all current docs to `docs/archive/v0.8/`
2. Backup mkdocs.yml

### Phase 2: Create Directory Structure
```bash
mkdir -p docs/{concepts,workflow,components/{ontology,handlers,estimator,patterns},infrastructure,examples/supply-chain,evaluation,reference/api}
```

### Phase 3: Write Framework Docs

| New File | Source Content |
|----------|---------------|
| `concepts/overview.md` | index.md (hypothesis), traffic_light_routing.md (intro) |
| `concepts/architecture.md` | architecture/overview.md + architecture.md (consolidated) |
| `concepts/when-to-use.md` | tco_analysis.md (decision criteria) |
| `workflow/overview.md` | NEW: Mermaid diagram from whiteboard |
| `workflow/ontology-discovery.md` | prompts/ontology_discovery.md + architecture/ontology.md |
| `workflow/pattern-discovery.md` | prompts/pattern_discovery.md |
| `workflow/analysis-sessions.md` | prompts/analysis_session.md |
| `components/ontology/*` | architecture/ontology.md (split into 4 files) |
| `components/handlers/*` | architecture/handlers.md + api/handlers.md (split) |
| `components/estimator/*` | api/estimator.md (split into 4 files) |
| `components/patterns/*` | NEW based on patterns/templates/ structure |
| `infrastructure/*` | getting-started/* (genericized) |

### Phase 4: Write Supply Chain Example

| File | Content |
|------|---------|
| `overview.md` | What you'll learn, prerequisites, what's included |
| `setup.md` | docker-compose up, seed data, verify connection |
| `ontology.md` | Full tour of supply_chain.yaml with explanations |
| `patterns.md` | Key discovered patterns with example invocations |
| `queries.md` | Step-by-step query walkthroughs (GREEN/YELLOW/RED) |
| `benchmark.md` | How to run benchmarks, interpret results |

### Phase 5: Write Evaluation Docs (EXPANDED)

| File | Content |
|------|---------|
| `methodology.md` | **NEW - Critical addition:** |
|                  | - How Claude should use web research for domain knowledge |
|                  | - Generating business analysis questions (not SQL/Cypher) |
|                  | - Covering ontology space systematically |
|                  | - Demonstrating graph operation strengths |
|                  | - Question inventory design principles |
| `benchmark-setup.md` | Full Neo4j infrastructure setup, migration scripts |
| `benchmark-results.md` | Supply chain results (from existing) |
| `tco-framework.md` | Enterprise TCO analysis (from existing, expanded) |
| `research-findings.md` | Synthesis: hypothesis validation, when VG wins/loses |

### Phase 6: Write Reference Docs
- `api/handlers.md` - reuse existing, cleanup
- `api/ontology.md` - reuse existing, cleanup
- `api/estimator.md` - reuse existing, cleanup
- `history.md` - distill phase1-6 into 1-page evolution

### Phase 7: Update mkdocs.yml
New navigation matching structure above.

## Key Design Decisions

1. **Inline supply chain examples**: Generic docs use supply chain as worked example with clear "For your domain, substitute X" callouts

2. **Runnable example section**: `examples/supply-chain/` is complete tutorial for repo cloners

3. **Component-centric structure**: Main nav follows components; workflow is one component

4. **Two audience tracks**:
   - **Developers**: concepts/ → workflow/ → examples/ → components/
   - **Evaluators**: concepts/ → evaluation/ → reference/

5. **Full benchmark documentation**: Complete Neo4j setup and methodology, not just results

6. **Methodology doc**: New content on how to design analysis questions using LLM + web research

## Files to Archive (move to docs/archive/v0.8/)
- `docs/architecture.md`
- `docs/development/phase*.md` (6 files)
- `docs/tco_analysis.md`
- `docs/getting-started/*` (superseded)
- `docs/architecture/*` (superseded)
- `docs/api/*` (superseded)

## Implementation Order

1. **Archive** - Move current docs, create structure
2. **concepts/** - Foundation, needed by everything else
3. **workflow/** - The 3-phase process with mermaid diagram
4. **components/** - Technical reference (largest section)
5. **infrastructure/** - Setup guides
6. **examples/supply-chain/** - Worked example
7. **evaluation/** - Research docs including new methodology.md
8. **reference/** - API docs and history
9. **index.md + mkdocs.yml** - Landing page and navigation

## Estimated Effort

| Section | Files | Effort |
|---------|-------|--------|
| Archive + structure | - | Trivial |
| concepts/ | 3 | Light (mostly reorganize) |
| workflow/ | 4 | Medium (new mermaid diagram) |
| components/ | 14 | Heavy (split and rewrite) |
| infrastructure/ | 3 | Light (genericize) |
| examples/supply-chain/ | 6 | Medium (new tutorial flow) |
| evaluation/ | 5 | Medium-Heavy (new methodology.md) |
| reference/ | 4 | Light (cleanup existing) |
| index.md + mkdocs.yml | 2 | Light |

**Total: ~41 files, mix of reorganization and new content**
