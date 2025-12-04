# Virtual Graph Benchmark Results

Generated: 2025-12-04T10:01:52.428649

## Summary

| System | Accuracy | First-Attempt | Avg Latency | P95 Latency |
|--------|----------|---------------|-------------|-------------|
| Virtual Graph | 68.0% | 68.0% | 2ms | 4ms |

## Results by Route

### GREEN Queries

| System | Correct | Accuracy | Avg Latency |
|--------|---------|----------|-------------|
| Virtual Graph | 8/9 | 88.9% | 1ms |

### YELLOW Queries

| System | Correct | Accuracy | Avg Latency |
|--------|---------|----------|-------------|
| Virtual Graph | 4/9 | 44.4% | 2ms |

### RED Queries

| System | Correct | Accuracy | Avg Latency |
|--------|---------|----------|-------------|
| Virtual Graph | 5/7 | 71.4% | 2ms |

## Individual Query Results

| ID | Query | Route | VG | VG Time | Neo4j | Neo4j Time |
|----|-------|-------|----|---------|----|---------|
| 1 | find_supplier | GREEN | ✓ | 2ms | - | - |
| 2 | tier1_suppliers | GREEN | ✓ | 1ms | - | - |
| 3 | parts_with_sensor | GREEN | ✓ | 4ms | - | - |
| 4 | parts_from_supplier | GREEN | ✓ | 1ms | - | - |
| 5 | facilities_by_state | GREEN | ✓ | 1ms | - | - |
| 6 | supplier_certifications | GREEN | ✓ | 1ms | - | - |
| 7 | products_with_part | GREEN | ✓ | 1ms | - | - |
| 8 | orders_from_facility | GREEN | ✗ | 1ms | - | - |
| 9 | alternate_suppliers | GREEN | ✓ | 1ms | - | - |
| 10 | tier3_suppliers | YELLOW | ✓ | 5ms | - | - |
| 11 | upstream_suppliers | YELLOW | ✓ | 3ms | - | - |
| 12 | downstream_customers | YELLOW | ✓ | 3ms | - | - |
| 13 | bom_explosion | YELLOW | ✗ | 1ms | - | - |
| 14 | where_used | YELLOW | ✗ | 1ms | - | - |
| 15 | supplier_impact | YELLOW | ✗ | 1ms | - | - |
| 16 | supply_chain_depth | YELLOW | ✓ | 3ms | - | - |
| 17 | bom_leaf_parts | YELLOW | ✗ | 1ms | - | - |
| 18 | common_suppliers | YELLOW | ✗ | 2ms | - | - |
| 19 | cheapest_route | RED | ✓ | 3ms | - | - |
| 20 | fastest_route | RED | ✓ | 2ms | - | - |
| 21 | shortest_distance | RED | ✓ | 2ms | - | - |
| 22 | critical_facility_betweenness | RED | ✓ | 1ms | - | - |
| 23 | most_connected_supplier | RED | ✗ | 1ms | - | - |
| 24 | isolated_facilities | RED | ✓ | 1ms | - | - |
| 25 | all_routes | RED | ✗ | 2ms | - | - |

## Errors

- Query 13 (virtual_graph): SubgraphTooLarge: Query would touch ~65,629 nodes (limit: 10,000). Consider adding filters or reducing depth.
- Query 14 (virtual_graph): SubgraphTooLarge: Query would touch ~42,931 nodes (limit: 10,000). Consider adding filters or reducing depth.
- Query 15 (virtual_graph): SubgraphTooLarge: Query would touch ~24,786 nodes (limit: 10,000). Consider adding filters or reducing depth.
- Query 17 (virtual_graph): SubgraphTooLarge: Query would touch ~65,629 nodes (limit: 10,000). Consider adding filters or reducing depth.
- Query 18 (virtual_graph): SubgraphTooLarge: Query would touch ~65,629 nodes (limit: 10,000). Consider adding filters or reducing depth.
