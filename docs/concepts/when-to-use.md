# When to Use Virtual Graph

This guide helps you decide whether Virtual Graph is the right approach for your use case.

## Decision Framework

```
┌─────────────────────────────────────────────────────────────────┐
│                    DECISION FLOWCHART                            │
└─────────────────────────────────────────────────────────────────┘

    Do you have existing relational data?
                    │
         ┌─────────┴─────────┐
         │ YES               │ NO
         ▼                   ▼
    Graph queries needed?    Consider native graph DB
                    │        from the start
         ┌─────────┴─────────┐
         │ YES               │ NO
         ▼                   ▼
    What % are graph ops?    Stay with SQL
                    │
    ┌───────┬───────┴───────┬───────┐
    │<20%   │ 20-80%        │ >80%  │
    ▼       ▼               ▼
 Virtual   Virtual        Consider
 Graph     Graph          Neo4j
 (clear    (sweet         migration
  win)      spot)
```

## Choose Virtual Graph When

### 1. Existing SQL Investment

You have a significant relational database with established schema, data, and operations.

**Indicators**:
- Production PostgreSQL/MySQL/SQL Server database
- Years of accumulated business data
- Existing ETL pipelines and data quality processes
- Team expertise in SQL

**Why VG wins**: No migration risk, no data duplication, zero sync lag.

### 2. Moderate Graph Query Volume

Graph-like queries represent 20-80% of your analytical needs.

**Indicators**:
- Some hierarchy traversals (org charts, BOMs, supplier chains)
- Occasional pathfinding or network analysis
- Most queries are still lookups and joins

**Why VG wins**: Full graph DB infrastructure is overkill.

### 3. Real-Time Data Requirements

You cannot tolerate sync lag between source and graph database.

**Indicators**:
- Operational dashboards requiring current data
- Audit/compliance requiring single source of truth
- Frequent data updates (hourly or more)

**Why VG wins**: Queries run directly on PostgreSQL - always current.

### 4. Budget Constraints

Cannot justify new infrastructure costs.

**Virtual Graph Year 1 TCO**:
| Component | Cost |
|-----------|------|
| Setup (4 hours labor) | ~$400 |
| LLM API calls | ~$600/year |
| Infrastructure | $0 (uses existing) |
| **Total** | **~$1,000-1,500** |

**Neo4j Year 1 TCO**:
| Component | Cost |
|-----------|------|
| Setup (44 hours labor) | ~$4,400 |
| Neo4j Aura | ~$2,400-6,000/year |
| ETL infrastructure | ~$600-1,200/year |
| **Total** | **~$7,400-11,600** |

### 5. Rapid Prototyping

Need to explore graph queries quickly before committing to architecture.

**Why VG wins**:
- 4 hours to first query vs 44+ hours for Neo4j
- No infrastructure commitment
- Easy to abandon if graph queries aren't valuable

### 6. Acceptable Accuracy Trade-off

Can accept 90%+ accuracy with safety limits.

**Current benchmark results**:
| Route | Virtual Graph | Target |
|-------|---------------|--------|
| GREEN | 88.9% | 100% |
| YELLOW | 100%* | 90% |
| RED | 85.7% | 80% |
| **Overall** | **92%** | 85% |

*Includes queries that correctly triggered safety limits.

## Choose Neo4j (or Other Graph DB) When

### 1. Complex Graph Patterns

Need native graph pattern matching (Cypher's MATCH).

**Examples**:
- "Find all triangles in the network"
- "Match any path where A-[*]-B-[*]-C and all nodes share property X"
- "Find motifs/patterns across arbitrary relationships"

**Why Neo4j wins**: Native pattern matching is orders of magnitude faster than SQL emulation.

### 2. Heavy Graph Workloads

>80% of queries are graph traversals, pathfinding, or network analysis.

**Indicators**:
- Building a recommendation engine
- Social network analysis
- Fraud detection graphs
- Knowledge graphs

**Why Neo4j wins**: Optimized storage and algorithms for graph operations.

### 3. 100% Accuracy Required

Cannot accept any query failures or approximations.

**Indicators**:
- Regulatory compliance queries
- Financial audit trails
- Safety-critical path analysis

**Why Neo4j wins**: Native graph storage means deterministic results.

### 4. Graph-First Design

Building a new system where graph is the primary model.

**Indicators**:
- No existing relational data to preserve
- Domain is inherently graph-shaped
- Team has graph database expertise

**Why Neo4j wins**: No SQL→graph impedance mismatch.

### 5. Advanced Algorithms

Need PageRank, community detection, graph neural networks at scale.

**Why Neo4j wins**: Built-in graph data science library, GPU acceleration options.

## Hybrid Approach

Consider using both:

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  OLTP + Simple Analytics          Heavy Graph Analytics         │
│  ┌─────────────────────┐          ┌─────────────────────┐       │
│  │    PostgreSQL       │          │      Neo4j          │       │
│  │    + Virtual Graph  │  ────▶   │  (batch sync)       │       │
│  │                     │          │                     │       │
│  │  - Lookups          │          │  - Pattern matching │       │
│  │  - Simple traversal │          │  - Community detect │       │
│  │  - Real-time data   │          │  - Graph ML         │       │
│  └─────────────────────┘          └─────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**When hybrid makes sense**:
- 90% of queries work great with Virtual Graph
- 10% need heavy graph algorithms
- Can tolerate batch sync for complex analytics
- Budget allows both systems

## Capability Comparison

| Capability | Virtual Graph | Neo4j |
|------------|--------------|-------|
| Simple Lookups | GREEN | Native |
| N-hop Joins | GREEN | Native |
| Recursive Traversal | YELLOW | Native |
| Shortest Path | RED | Native |
| Centrality | RED | Native |
| Pattern Matching | Limited | Native |
| ACID Transactions | Via PostgreSQL | Native |
| Real-time Data | Yes | Requires sync |
| Scale (nodes) | 10K per query* | Millions |

*Safety limit, configurable for known-bounded graphs.

## Performance Comparison

| Metric | Virtual Graph | Neo4j |
|--------|--------------|-------|
| Simple Query Latency | 1-5ms | 5-20ms |
| Traversal Latency | 2-5ms | 10-50ms |
| Path Query Latency | 2-3ms | 20-100ms |
| Bulk Graph Ops | Slower | Faster |
| Network Hop | None | Required |

**Note**: Virtual Graph can be faster for moderate queries because it avoids network hops to a separate database. Neo4j is faster for bulk graph operations.

## Risk Analysis

### Virtual Graph Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM generates incorrect SQL | Medium | Low | Pattern library, validation |
| Safety limits too restrictive | Low | Medium | Configurable per-query |
| Complex patterns not supported | Medium | Medium | Fallback to direct SQL |

### Neo4j Migration Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data sync failures | Medium | High | Monitoring, alerts |
| Schema drift | Medium | High | Version control, testing |
| Migration data loss | Low | High | Validation scripts |
| Performance degradation | Low | Medium | Query optimization |

## Quick Decision Checklist

Answer these questions:

1. **Do you have >1 year of data in PostgreSQL?**
   - Yes → +1 for Virtual Graph
   - No → Neutral

2. **What % of queries need graph operations?**
   - <20% → +2 for Virtual Graph
   - 20-80% → +1 for Virtual Graph
   - >80% → +1 for Neo4j

3. **Do you need real-time data?**
   - Yes → +2 for Virtual Graph
   - No → Neutral

4. **Is your annual budget for this project < $5,000?**
   - Yes → +2 for Virtual Graph
   - No → Neutral

5. **Do you need complex pattern matching?**
   - Yes → +2 for Neo4j
   - No → +1 for Virtual Graph

6. **Is 90% accuracy acceptable?**
   - Yes → +1 for Virtual Graph
   - No → +1 for Neo4j

**Score interpretation**:
- Virtual Graph score > Neo4j score → Start with Virtual Graph
- Scores are close → Consider hybrid approach or prototype with VG first
- Neo4j score > Virtual Graph score → Evaluate Neo4j migration

## Next Steps

If Virtual Graph fits your needs:

1. **Setup**: Follow [Installation](../infrastructure/installation.md)
2. **Learn the workflow**: Read [Workflow Overview](../workflow/overview.md)
3. **Try the example**: Work through [Supply Chain Example](../examples/supply-chain/overview.md)
