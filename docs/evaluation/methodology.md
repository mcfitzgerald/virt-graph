# Evaluation Methodology

This guide describes how to design comprehensive analysis question inventories for Virtual Graph evaluation. The methodology ensures questions cover the ontology systematically and demonstrate graph operation strengths.

## Overview

Effective evaluation requires questions that:

1. **Cover the ontology systematically** - All entity types and relationships tested
2. **Demonstrate graph strengths** - Recursive traversal, pathfinding, centrality
3. **Reflect real business needs** - Questions an analyst would actually ask
4. **Test all complexity routes** - GREEN, YELLOW, and RED handlers

## Question Design Process

### Phase 1: Domain Research

Before writing questions, understand the domain through web research:

```
For a supply chain domain, research:
- Common supply chain analysis questions
- KPIs and metrics used in industry
- Risk assessment methodologies
- Network optimization problems
- Compliance and audit requirements
```

**Example Research Prompts:**

```
"What questions do supply chain analysts typically ask about their supplier networks?"

"What graph-based analyses are used in supply chain risk management?"

"How do companies analyze bill of materials for cost optimization?"
```

**Key Insight:** Generate business questions, not SQL/Cypher queries. The system should translate natural language to the appropriate implementation.

### Phase 2: Ontology Coverage Matrix

Map questions to ensure complete coverage:

```
┌──────────────────────────────────────────────────────────────────┐
│                    ONTOLOGY COVERAGE MATRIX                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Entity Classes    Question Coverage                             │
│  ──────────────    ─────────────────                             │
│  Supplier          ✓ Lookup  ✓ Filter  ✓ Aggregate              │
│  Part              ✓ Lookup  ✓ Filter  ✓ Aggregate              │
│  Product           ✓ Lookup  ✓ Filter  ○ Aggregate              │
│  Facility          ✓ Lookup  ✓ Filter  ✓ Aggregate              │
│  Customer          ○ Lookup  ○ Filter  ○ Aggregate              │
│  ...                                                             │
│                                                                  │
│  Relationships     Question Coverage                             │
│  ─────────────     ─────────────────                             │
│  SuppliesTo        ✓ Traverse  ✓ Depth  ✓ Collect               │
│  ComponentOf       ✓ Traverse  ✓ Depth  ✓ Collect               │
│  ConnectsTo        ✓ Path     ✓ Weight  ✓ Centrality            │
│  CanSupply         ✓ Join     ○ Filter                          │
│  ...                                                             │
│                                                                  │
│  ✓ = covered   ○ = partial   ✗ = missing                        │
└──────────────────────────────────────────────────────────────────┘
```

### Phase 3: Route Distribution

Balance questions across complexity routes:

| Route | Target % | Handler Coverage |
|-------|----------|------------------|
| GREEN | 30-40% | Direct SQL, simple joins |
| YELLOW | 30-40% | Recursive traversal, BOM |
| RED | 20-30% | Pathfinding, centrality |

**Rationale:**
- GREEN establishes baseline SQL capability
- YELLOW tests the core traversal hypothesis
- RED validates network algorithm integration

### Phase 4: Question Templates

Use templates to generate comprehensive questions:

#### GREEN Templates (Simple Lookups)

```
"Find [Entity] where [attribute] = [value]"
"List all [Entity] with [attribute] > [threshold]"
"Which [Entity] have [relationship] to [other entity]?"
"Count [Entity] grouped by [attribute]"
```

**Examples:**
- "Find the supplier named Acme Corp"
- "List all tier 1 suppliers"
- "Which parts have a lead time greater than 30 days?"
- "Count orders by status"

#### YELLOW Templates (Recursive Traversal)

```
"Find all [upstream/downstream] [Entity] for [starting entity]"
"What is the depth of [hierarchy] from [start]?"
"Which [Entity] at tier N are reachable from [start]?"
"Explode [BOM/hierarchy] for [product/assembly]"
"Where is [component] used in the [hierarchy]?"
```

**Examples:**
- "Find all upstream suppliers for Acme Corp"
- "What is the depth of the BOM for Turbo Encabulator?"
- "Which tier 3 suppliers feed into GlobalTech?"
- "Full parts list for product SKU-001"
- "Where is sensor XYZ used?"

#### RED Templates (Network Analysis)

```
"What is the [shortest/cheapest/fastest] path from [A] to [B]?"
"Which [Entity] has highest [centrality type] in the network?"
"Are there isolated [Entity] not connected to the main network?"
"Find all routes between [A] and [B]"
"What is the density of the [network type] network?"
```

**Examples:**
- "Cheapest shipping route from Chicago to LA"
- "Which facility is most critical to the transport network?"
- "Are there isolated warehouses?"
- "All possible routes from factory to customer"

## Question Quality Criteria

### Good Questions

✓ **Business-focused:** "Which suppliers would be affected if Pacific Components stopped operating?"

✓ **Specific:** "Find tier 3 suppliers that exclusively supply to Acme Corp"

✓ **Testable:** Has a deterministic answer that can be validated

✓ **Graph-relevant:** Benefits from graph traversal (not just a filter)

### Poor Questions

✗ **Implementation-focused:** "Write a Cypher query to find suppliers" (specifies implementation)

✗ **Ambiguous:** "Find related suppliers" (related how?)

✗ **Non-deterministic:** "Find some parts" (no clear criteria)

✗ **SQL-trivial:** "Count all orders" (doesn't demonstrate graph capability)

## Ground Truth Generation

For each question, establish ground truth through:

### 1. Direct SQL Verification

```sql
-- Question: "Find all tier 3 suppliers for Acme Corp"
-- Ground truth query:
WITH RECURSIVE upstream AS (
  SELECT sr.seller_id, 1 as depth
  FROM supplier_relationships sr
  JOIN suppliers s ON sr.buyer_id = s.id
  WHERE s.name = 'Acme Corp'

  UNION ALL

  SELECT sr.seller_id, u.depth + 1
  FROM supplier_relationships sr
  JOIN upstream u ON sr.buyer_id = u.seller_id
  WHERE u.depth < 10
)
SELECT DISTINCT s.*
FROM upstream u
JOIN suppliers s ON u.seller_id = s.id
WHERE s.tier = 3;
```

### 2. Neo4j Verification (for RED queries)

```cypher
// Question: "Cheapest route from Chicago to LA"
MATCH path = shortestPath(
  (a:Facility {name: 'Chicago Warehouse'})-[:CONNECTS_TO*]-(b:Facility {name: 'LA Distribution Center'})
)
RETURN path, reduce(cost = 0, r in relationships(path) | cost + r.cost_usd) as total_cost
```

### 3. Manual Verification

For complex questions, manually trace through sample data to establish expected results.

## Safety Limit Testing

Include questions that intentionally test safety limits:

| Question Type | Expected Behavior |
|---------------|-------------------|
| Full BOM explosion (no filter) | Should hit MAX_NODES limit |
| Deep traversal (depth > 50) | Should hit MAX_DEPTH limit |
| Large result set | Should hit MAX_RESULTS limit |

**Purpose:** Verify the system correctly identifies and handles dangerous queries rather than executing them blindly.

## Benchmark Question Inventory

The supply chain benchmark uses 25 questions:

| # | Route | Question Category |
|---|-------|-------------------|
| 1-9 | GREEN | Lookups, filters, simple joins |
| 10-18 | YELLOW | Tier traversal, BOM, impact analysis |
| 19-25 | RED | Pathfinding, centrality, components |

### Distribution Analysis

```
GREEN:  9 questions (36%)
YELLOW: 9 questions (36%)
RED:    7 questions (28%)
```

### Coverage Validation

All entity classes have at least one question:
- Supplier: Q1, Q2, Q10, Q11, Q23
- Part: Q3, Q4, Q13, Q14
- Facility: Q5, Q19-22, Q24
- Product: Q7, Q13
- Order: Q8
- etc.

All key relationships tested:
- SuppliesTo: Q10, Q11, Q12, Q16
- ComponentOf: Q13, Q14, Q17
- ConnectsTo: Q19, Q20, Q21, Q22, Q24, Q25
- CanSupply: Q4, Q9

## Extending the Inventory

When adding new questions:

1. **Check coverage matrix** - Fill gaps before adding redundant coverage
2. **Vary difficulty** - Mix simple and complex questions per route
3. **Add edge cases** - Empty results, single results, large results
4. **Test boundaries** - Max depth, max nodes, timeout scenarios

### Template for New Questions

```yaml
question:
  id: 26
  text: "Natural language question here"
  route: GREEN|YELLOW|RED
  entities_covered: [Supplier, Part]
  relationships_covered: [CanSupply]
  expected_result_type: list|count|path|ranking
  expected_count: 42  # or range [10, 50]
  ground_truth_sql: |
    SELECT ... FROM ...
  notes: "Any special considerations"
```

## Evaluation Metrics

### Accuracy Metrics

| Metric | Definition |
|--------|------------|
| Overall Accuracy | Correct / Total questions |
| Route Accuracy | Correct per route / Questions per route |
| First-Attempt Rate | Correct without retry / Total |

### Result Comparison

For **list results:**
- Exact match (order matters)
- Set overlap (order doesn't matter)
- Jaccard similarity

For **count results:**
- Exact match
- Within tolerance (±5%)

For **path results:**
- Valid path (exists in graph)
- Optimal (matches expected cost/distance)

For **ranking results:**
- Top-N overlap
- Rank correlation (Spearman's ρ)

## Iterating on the Inventory

After initial evaluation:

1. **Analyze failures** - Why did specific questions fail?
2. **Identify gaps** - What question types are missing?
3. **Adjust difficulty** - Too easy? Too hard?
4. **Add regression tests** - Questions for fixed bugs

Document changes in the benchmark changelog to track inventory evolution.
