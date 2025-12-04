// Query 18: Find suppliers common to multiple products (YELLOW - multi-traversal)
// Expected route: YELLOW
// Category: n-hop-recursive
// Expected handler: traverse

MATCH (prod1:Product {name: $product1_name})-[:CONTAINS_COMPONENT]->(p1:Part)
MATCH (prod2:Product {name: $product2_name})-[:CONTAINS_COMPONENT]->(p2:Part)
MATCH path1 = (p1)<-[:COMPONENT_OF*0..10]-(child1:Part)
MATCH path2 = (p2)<-[:COMPONENT_OF*0..10]-(child2:Part)
MATCH (s:Supplier)-[:PROVIDES]->(child1)
MATCH (s)-[:PROVIDES]->(child2)
RETURN DISTINCT s
ORDER BY s.name
