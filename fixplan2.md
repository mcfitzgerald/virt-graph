Plan: Align VG/SQL and Neo4j Benchmark Results

 Goal: Improve benchmark agreement from ~82% to ~95%+ by fixing two alignment gaps.

 ---
 Part 1: Add Soft-Delete Filtering to VG/SQL Handlers

 Problem

 - Neo4j migration filters WHERE deleted_at IS NULL
 - VG/SQL handlers traverse ALL records including soft-deleted
 - Result: Different node counts, different routes, different depths

 Solution

 Add optional soft_delete_column parameter to base functions.

 Implementation

 Step 1: Enhance fetch_nodes() in base.py

 def fetch_nodes(
     conn: PgConnection,
     nodes_table: str,
     node_ids: list[int],
     columns: list[str] | None = None,
     id_column: str = "id",
     soft_delete_column: str | None = None,  # NEW
 ) -> list[dict[str, Any]]:
     # ...existing code...
     query = f"""
         SELECT {col_spec}
         FROM {nodes_table}
         WHERE {id_column} = ANY(%s)
     """
     if soft_delete_column:
         query += f" AND {soft_delete_column} IS NULL"

 Step 2: Enhance fetch_edges_for_frontier() in base.py

 Add optional node table filtering:

 def fetch_edges_for_frontier(
     conn: PgConnection,
     edges_table: str,
     frontier_ids: list[int],
     edge_from_col: str,
     edge_to_col: str,
     direction: str = "outbound",
     # NEW: Optional soft-delete filtering for endpoint nodes
     from_node_table: str | None = None,
     to_node_table: str | None = None,
     soft_delete_column: str | None = None,
 ) -> list[tuple[int, int]]:

 When soft_delete_column is provided, join to node tables and filter.

 Step 3: Update handler functions

 Add soft_delete_column parameter to:
 - traverse() in traversal.py
 - bom_explode() in traversal.py
 - shortest_path() in pathfinding.py
 - centrality() in network.py
 - _load_full_graph() in network.py

 Step 4: Tests

 Add tests verifying soft-delete filtering matches Neo4j behavior.

 Files to Modify

 | File                                   | Change                                                              |
 |----------------------------------------|---------------------------------------------------------------------|
 | src/virt_graph/handlers/base.py        | Add soft_delete_column to fetch_nodes(), fetch_edges_for_frontier() |
 | src/virt_graph/handlers/traversal.py   | Pass soft_delete_column through traverse(), bom_explode()           |
 | src/virt_graph/handlers/pathfinding.py | Pass soft_delete_column through shortest_path()                     |
 | src/virt_graph/handlers/network.py     | Pass soft_delete_column through centrality(), _load_full_graph()    |
 | tests/test_soft_delete.py              | New test file for soft-delete filtering                             |

 ---
 Part 2: Update Neo4j Centrality Queries to Use GDS

 Problem

 - VG/SQL uses NetworkX real algorithms (betweenness, pagerank, etc.)
 - Neo4j queries just count connections as a proxy
 - Result: Different centrality scores and rankings

 Solution

 Update neo4j_queries.md to use GDS algorithms (already installed, v2.6.9).

 GDS Pattern

 // 1. Create graph projection (once)
 CALL gds.graph.project(
   'facilityGraph',
   'Facility',
   'CONNECTSTO',
   { relationshipProperties: ['distance_km', 'cost_usd'] }
 )

 // 2. Run algorithm
 CALL gds.betweenness.stream('facilityGraph')
 YIELD nodeId, score
 RETURN gds.util.asNode(nodeId).name AS name, score
 ORDER BY score DESC
 LIMIT 10

 // 3. Drop projection when done
 CALL gds.graph.drop('facilityGraph')

 Queries to Update

 | Query               | Current        | Update To                             |
 |---------------------|----------------|---------------------------------------|
 | Q36 (betweenness)   | count(r)       | gds.betweenness.stream()              |
 | Q37 (degree)        | count(r)       | gds.degree.stream()                   |
 | Q38 (PageRank)      | count incoming | gds.pageRank.stream()                 |
 | Q40 (Denver impact) | count routes   | gds.betweenness.stream() before/after |

 Files to Modify

 | File                    | Change                               |
 |-------------------------|--------------------------------------|
 | neo4j_queries.md        | Update Q36-Q40 to use GDS algorithms |
 | benchmark_comparison.md | Update results after re-running      |

 ---
 Part 3: Re-run Benchmark and Update Documentation

 After implementing Parts 1 & 2:

 1. Run VG/SQL queries with soft_delete_column='deleted_at'
 2. Run updated Neo4j GDS queries
 3. Compare results
 4. Update benchmark_comparison.md with new agreement percentage

 Expected Improvement

 | Category        | Current | Expected                    |
 |-----------------|---------|-----------------------------|
 | YELLOW Supplier | 87.5%   | ~100% (soft-delete aligned) |
 | RED Pathfinding | 57%     | ~85% (routes aligned)       |
 | RED Centrality  | 80%     | ~100% (GDS algorithms)      |
 | Overall         | ~82%    | ~95%                        |

 ---
 Implementation Order

 1. Part 1 (Soft-delete) - Most impact, affects multiple categories
 2. Part 2 (GDS) - Quick win, just query updates
 3. Part 3 (Benchmark) - Validation

 ---
 Verification

 After implementation:

 # Test soft-delete filtering
 poetry run python -c "
 from virt_graph.handlers.traversal import traverse
 from virt_graph.handlers.base import get_connection
 conn = get_connection()
 # Without filter
 r1 = traverse(conn, 'suppliers', 'supplier_relationships', 'seller_id', 'buyer_id', 1, max_depth=5)
 # With filter
 r2 = traverse(conn, 'suppliers', 'supplier_relationships', 'seller_id', 'buyer_id', 1, max_depth=5, soft_delete_column='deleted_at')
 print(f'Without filter: {r1[\"nodes_visited\"]} nodes')
 print(f'With filter: {r2[\"nodes_visited\"]} nodes')
 "

 # Test GDS centrality
 docker exec virt-graph-neo4j cypher-shell -u neo4j -p dev_password "
 CALL gds.graph.project('test', 'Facility', 'CONNECTSTO')
 YIELD graphName, nodeCount, relationshipCount;
 "