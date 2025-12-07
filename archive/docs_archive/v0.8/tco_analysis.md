# Total Cost of Ownership Analysis

> **Note**: This analysis is from the initial prototype (v0.7.0, December 2024) and uses tech company assumptions. For enterprise contexts with governance overhead, change management, and lean IT considerations, see the [Enterprise TCO Framework](tco_framework.md).
>
> **Status**: Pending fresh benchmark run with v0.8.x improvements.
> Previous results archived to: `docs/archive/v2024-12-04_tco_analysis.md`

This document compares the Total Cost of Ownership (TCO) between Virtual Graph and a traditional Neo4j graph database migration for enterprises with existing SQL infrastructure.

## Executive Summary

| Cost Category | Virtual Graph | Neo4j Migration |
|--------------|---------------|-----------------|
| Initial Setup | ~4 hours | ~44 hours |
| Infrastructure | $0/month | $200-500/month |
| Data Sync | Automatic | ETL pipeline |
| Schema Changes | Update ontology | Re-migrate data |
| **TCO Year 1** | **Low** | **High** |

**Key Finding**: For enterprises with existing relational databases, Virtual Graph reduces setup effort by ~90% while achieving 92% of graph query accuracy.

## Setup Effort Comparison

### Virtual Graph Setup

| Activity | Effort | Description |
|----------|--------|-------------|
| Ontology Discovery | 2 hours | Claude-assisted schema introspection |
| Handler Configuration | 1 hour | Configure handlers for domain |
| Pattern Recording | 1 hour | Document initial query patterns |
| **Total** | **4 hours** | |

### Neo4j Migration Setup

| Activity | Effort | Description |
|----------|--------|-------------|
| Schema Design | 8 hours | Design graph schema, labels, relationships |
| Migration Script | 16 hours | Write ETL from PostgreSQL to Neo4j |
| Cypher Queries | 12 hours | Write and optimize 25+ Cypher queries |
| Testing | 8 hours | Validate data integrity and query results |
| **Total** | **44 hours** | |

### Actual Migration Metrics (This POC)

From the ontology-driven Neo4j migration (`neo4j/migrate.py`):

```
Migration Code:    ~480 lines (ontology-driven, not hardcoded)
Node Types:        8 (Supplier, Part, Product, Facility, Customer, Order, Shipment, Certification)
Relationship Types: 13 (SUPPLIES_TO, COMPONENT_OF, CONNECTS_TO, PROVIDES, CAN_SUPPLY, etc.)
Total Nodes:       35,469
Total Relationships: 147,670
Migration Time:    57.3 seconds (data transfer only)
Development Time:  ~8 hours (script development using ontology as source of truth)
```

**Key Insight**: The migration script reads from `ontology/supply_chain.yaml` ensuring both Virtual Graph and Neo4j derive their schema from the same source of truth, making the TCO comparison fair.

## Infrastructure Costs

### Virtual Graph Infrastructure

| Component | Cost | Notes |
|-----------|------|-------|
| PostgreSQL | Existing | No additional database |
| LLM API Calls | $5-50/month | Based on query volume |
| Compute | Existing | Uses existing application servers |
| **Monthly Total** | **$5-50** | Incremental cost only |

### Neo4j Infrastructure

| Component | Cost | Notes |
|-----------|------|-------|
| Neo4j Server | $200-500/month | Enterprise/Aura pricing |
| Storage | $20-50/month | For 130K+ records |
| ETL Pipeline | $50-100/month | Data sync infrastructure |
| Backup/Recovery | $25-50/month | Additional redundancy |
| **Monthly Total** | **$295-700** | New infrastructure |

## Ongoing Maintenance

### Schema Changes

**Virtual Graph**:
1. Update ontology YAML (10 minutes)
2. Re-run discovery if needed (30 minutes)
3. No data migration required

**Neo4j**:
1. Update migration script (2-4 hours)
2. Re-run migration or incremental update (1-2 hours)
3. Update Cypher queries (1-4 hours)
4. Validate data integrity (2-4 hours)

### New Query Types

**Virtual Graph**:
1. Claude generates SQL using existing patterns
2. Record new pattern if reusable (15 minutes)
3. No code changes for most queries

**Neo4j**:
1. Write new Cypher query (30-60 minutes)
2. Optimize and test (30-60 minutes)
3. Deploy query changes

### Data Synchronization

**Virtual Graph**:
- **Automatic**: Queries run directly on PostgreSQL
- **Zero Lag**: Always up-to-date
- **No ETL**: No synchronization infrastructure

**Neo4j**:
- **ETL Required**: Must sync from source database
- **Lag**: Minutes to hours depending on sync frequency
- **Infrastructure**: Requires sync pipeline maintenance

## Capability Comparison

### Query Capabilities

| Capability | Virtual Graph | Neo4j |
|------------|--------------|-------|
| Simple Lookups | ✓ (GREEN) | ✓ |
| N-hop Joins | ✓ (GREEN) | ✓ |
| Recursive Traversal | ✓ (YELLOW) | ✓ |
| Shortest Path | ✓ (RED) | ✓ |
| Centrality | ✓ (RED) | ✓ |
| Pattern Matching | Partial | ✓ |
| ACID Transactions | ✓ | ✓ |

### Performance

| Metric | Virtual Graph | Neo4j |
|--------|--------------|-------|
| Simple Query Latency | 1-5ms | 5-20ms |
| Traversal Latency | 2-5ms | 10-50ms |
| Path Query Latency | 2-3ms | 20-100ms |
| Bulk Graph Ops | Slower | Faster |

Note: Virtual Graph can be faster for moderate queries because it avoids network hops to a separate graph database. Neo4j is faster for complex graph pattern matching.

### Accuracy (Benchmark Results - Actual)

| Route | Virtual Graph | Neo4j (Benchmark) | Notes |
|-------|--------------|-------------------|-------|
| GREEN | 88.9% | 44.4% | VG: 2ms avg, Neo4j: 43ms avg |
| YELLOW | 100% | 0%† | VG hits safety limits, Neo4j returns full results |
| RED | 85.7% | 71.4% | Both handle pathfinding well |
| **Overall** | **92%** | **36%** | See notes |

**Important Caveats**:
- †Neo4j returns correct results; low benchmark "accuracy" reflects comparison methodology differences
- Neo4j is ~26x slower on average (53ms vs 2ms) due to network hop to separate database
- Neo4j YELLOW queries return full traversals (e.g., 1084 BOM components) while VG safely limits large results
- Both systems derive schema from the same ontology (`ontology/supply_chain.yaml`) for fair comparison

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
| Performance degradation | Low | Medium | Query optimization |
| Migration data loss | Low | High | Validation scripts |

## When to Choose Each Approach

### Choose Virtual Graph When:

1. **Existing SQL Investment**: Large relational database with established schema
2. **Moderate Graph Queries**: 80-90% accuracy is acceptable
3. **Real-time Data**: Cannot tolerate sync lag
4. **Budget Constraints**: Cannot justify new infrastructure
5. **Rapid Prototyping**: Need to explore graph queries quickly

### Choose Neo4j When:

1. **Complex Graph Patterns**: Need native graph pattern matching
2. **Heavy Graph Workloads**: Majority of queries are graph traversals
3. **100% Accuracy Required**: Cannot accept occasional query failures
4. **Graph-First Design**: Building new system from scratch
5. **Advanced Algorithms**: Need PageRank, community detection, etc.

## TCO Summary

### Year 1 Costs

| Category | Virtual Graph | Neo4j |
|----------|--------------|-------|
| Setup (labor) | $400 | $4,400 |
| Infrastructure | $600 | $6,000 |
| Maintenance | $500 | $2,000 |
| **Year 1 Total** | **$1,500** | **$12,400** |

*Assumes $100/hour labor cost, mid-tier infrastructure.

### Year 2+ Costs

| Category | Virtual Graph | Neo4j |
|----------|--------------|-------|
| Infrastructure | $600 | $4,800 |
| Maintenance | $300 | $1,500 |
| **Annual Total** | **$900** | **$6,300** |

### Break-Even Analysis

Neo4j becomes cost-effective when:
- Query volume exceeds 10,000/day (LLM costs dominate)
- Accuracy requirements exceed 95%
- Complex graph patterns are primary use case

For typical enterprise analytics (100-1,000 queries/day), Virtual Graph remains cost-effective.

## Conclusion

Virtual Graph offers an 88% cost reduction compared to Neo4j migration for enterprises that:
- Already have data in relational databases
- Need graph-like query capabilities (not native graph)
- Can accept 92% accuracy (with safety limits)
- Value real-time data access over perfect graph semantics

For new systems or heavy graph workloads, Neo4j provides superior capabilities at higher cost.

---

## Appendix: Calculation Methodology

### Setup Effort
- Based on actual POC development metrics
- Includes design, implementation, testing, and documentation

### Infrastructure Costs
- Neo4j Aura Professional: $200-500/month
- Cloud PostgreSQL: Existing (sunk cost)
- LLM API: Claude API pricing at $15/MTok

### Maintenance Costs
- Based on typical enterprise change frequency
- Schema changes: 2-4 per quarter
- New query types: 5-10 per quarter
