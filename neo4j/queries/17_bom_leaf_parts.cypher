// Query 17: Find all leaf parts (raw materials) in a product's BOM (YELLOW)
// Expected route: YELLOW
// Category: bom-traversal
// Expected handler: traverse

MATCH (prod:Product {name: $product_name})-[:CONTAINS_COMPONENT]->(top:Part)
MATCH path = (top)<-[:COMPONENT_OF*0..20]-(leaf:Part)
WHERE NOT EXISTS { (leaf)<-[:COMPONENT_OF]-(:Part) }
RETURN DISTINCT leaf
ORDER BY leaf.part_number
