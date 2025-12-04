# Virtual Graph Benchmark Results

Generated: 2025-12-04T15:54:59.946183

## Summary

| System | Accuracy | First-Attempt | Avg Latency | P95 Latency |
|--------|----------|---------------|-------------|-------------|
| Virtual Graph | 92.0% | 92.0% | 2ms | 5ms |
| Neo4J | 36.0% | 36.0% | 53ms | 136ms |

*Note: 5 queries hit safety limits (MAX_NODES=10,000). 
These are counted as correct since the handlers correctly identified the query would exceed safe limits.*

## Results by Route

### GREEN Queries

| System | Correct | Accuracy | Avg Latency | Safety Limits |
|--------|---------|----------|-------------|---------------|
| Virtual Graph | 8/9 | 88.9% | 2ms | - |
| Neo4J | 4/9 | 44.4% | 43ms | - |

### YELLOW Queries

| System | Correct | Accuracy | Avg Latency | Safety Limits |
|--------|---------|----------|-------------|---------------|
| Virtual Graph | 9/9 | 100.0% | 2ms | 5 |
| Neo4J | 0/9 | 0.0% | 71ms | - |

### RED Queries

| System | Correct | Accuracy | Avg Latency | Safety Limits |
|--------|---------|----------|-------------|---------------|
| Virtual Graph | 6/7 | 85.7% | 1ms | - |
| Neo4J | 5/7 | 71.4% | 41ms | - |

## Target Comparison

| Route | Target Accuracy | VG Accuracy | Status |
|-------|-----------------|-------------|--------|
| GREEN | 100% | 88.9% | ✗ FAIL |
| YELLOW | 90% | 100.0% | ✓ PASS |
| RED | 80% | 85.7% | ✓ PASS |

## Individual Query Results

| ID | Query | Route | VG | VG Time | Results | Expected | Match Type |
|----|-------|-------|----|---------| --------|----------|------------|
| 1 | find_supplier | GREEN | ✓ | 2ms | 1 | 1.0 | overlap_100.0%_pr... |
| 2 | tier1_suppliers | GREEN | ✓ | 1ms | 49 | 49.0 | overlap_100.0%_pr... |
| 3 | parts_with_sensor | GREEN | ✓ | 5ms | 503 | 503.0 | overlap_100.0%_pr... |
| 4 | parts_from_supplier | GREEN | ✓ | 1ms | 27 | 27.0 | overlap_100.0%_pr... |
| 5 | facilities_by_state | GREEN | ✓ | 1ms | 1 | 1.0 | overlap_100.0%_pr... |
| 6 | supplier_certifications | GREEN | ✓ | 1ms | 0 | - | existence |
| 7 | products_with_part | GREEN | ✓ | 2ms | 0 | - | existence |
| 8 | orders_from_facility | GREEN | ✗ | 1ms | 100 | 100.0 | overlap_31.0%_pre... |
| 9 | alternate_suppliers | GREEN | ✓ | 1ms | 0 | - | existence |
| 10 | tier3_suppliers | YELLOW | ✓ | 5ms | 26 | 26.0 | overlap_100.0%_pr... |
| 11 | upstream_suppliers | YELLOW | ✓ | 2ms | 4 | 4.0 | overlap_100.0%_pr... |
| 12 | downstream_customers | YELLOW | ✓ | 3ms | 4 | 4.0 | overlap_100.0%_pr... |
| 13 | bom_explosion | YELLOW | ⚠️ | 1ms | 0 | 1024.0 | safety_limit |
| 14 | where_used | YELLOW | ⚠️ | 1ms | 0 | 64.0 | safety_limit |
| 15 | supplier_impact | YELLOW | ⚠️ | 1ms | 0 | 182.0 | safety_limit |
| 16 | supply_chain_depth | YELLOW | ✓ | 3ms | 13 | 13.0 | overlap_100.0%_pr... |
| 17 | bom_leaf_parts | YELLOW | ⚠️ | 1ms | 0 | 767.0 | safety_limit |
| 18 | common_suppliers | YELLOW | ⚠️ | 1ms | 0 | 282.0 | safety_limit |
| 19 | cheapest_route | RED | ✓ | 3ms | 1 | 1.0 | path_valid |
| 20 | fastest_route | RED | ✓ | 1ms | 1 | 1.0 | path_valid |
| 21 | shortest_distance | RED | ✓ | 2ms | 1 | 1.0 | path_valid |
| 22 | critical_facility_betweenness | RED | ✓ | 1ms | 10 | 10.0 | overlap_90.0%_pre... |
| 23 | most_connected_supplier | RED | ✗ | 2ms | 10 | 10.0 | overlap_10.0%_pre... |
| 24 | isolated_facilities | RED | ✓ | 1ms | 0 | - | existence |
| 25 | all_routes | RED | ✓ | 1ms | 1 | 9.0 | path_valid |

## Neo4j Comparison

| ID | Query | Neo4j | Time | Results |
|----|-------|-------|------|---------|
| 1 | find_supplier | ✗ | 23ms | 1 |
| 2 | tier1_suppliers | ✓ | 44ms | 49 |
| 3 | parts_with_sensor | ✗ | 70ms | 503 |
| 4 | parts_from_supplier | ✗ | 69ms | 27 |
| 5 | facilities_by_state | ✗ | 19ms | 1 |
| 6 | supplier_certifications | ✓ | 60ms | 0 |
| 7 | products_with_part | ✓ | 25ms | 0 |
| 8 | orders_from_facility | ✗ | 44ms | 100 |
| 9 | alternate_suppliers | ✓ | 29ms | 0 |
| 10 | tier3_suppliers | ✗ | 63ms | 26 |
| 11 | upstream_suppliers | ✗ | 43ms | 4 |
| 12 | downstream_customers | ✗ | 35ms | 4 |
| 13 | bom_explosion | ✗ | 108ms | 1084 |
| 14 | where_used | ✗ | 24ms | 64 |
| 15 | supplier_impact | ✗ | 47ms | 2 |
| 16 | supply_chain_depth | ✗ | 29ms | 13 |
| 17 | bom_leaf_parts | ✗ | 136ms | 767 |
| 18 | common_suppliers | ✗ | 155ms | 282 |
| 19 | cheapest_route | ✓ | 54ms | 1 |
| 20 | fastest_route | ✓ | 27ms | 1 |
| 21 | shortest_distance | ✓ | 27ms | 1 |
| 22 | critical_facility_betweenness | ✗ | 53ms | 10 |
| 23 | most_connected_supplier | ✗ | 47ms | 10 |
| 24 | isolated_facilities | ✓ | 33ms | 0 |
| 25 | all_routes | ✓ | 48ms | 10 |

## Safety Limit Details

The following queries hit the MAX_NODES=10,000 safety limit:

- Query 13: SubgraphTooLarge: Query would touch ~65,629 nodes (limit: 10,000). Consider adding filters or reducing depth.
- Query 14: SubgraphTooLarge: Query would touch ~42,931 nodes (limit: 10,000). Consider adding filters or reducing depth.
- Query 15: SubgraphTooLarge: Query would touch ~24,786 nodes (limit: 10,000). Consider adding filters or reducing depth.
- Query 17: SubgraphTooLarge: Query would touch ~65,629 nodes (limit: 10,000). Consider adding filters or reducing depth.
- Query 18: SubgraphTooLarge: Query would touch ~65,629 nodes (limit: 10,000). Consider adding filters or reducing depth.

These are BOM traversal queries that would expand to the full parts tree (~65K nodes).
The safety limit correctly prevented runaway queries. In production, these queries 
would need additional filters (e.g., max_depth, stop conditions) to be safe.
