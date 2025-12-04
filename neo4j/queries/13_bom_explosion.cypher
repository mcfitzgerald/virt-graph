// Query 13: Full BOM explosion for a product (YELLOW - recursive BOM)
// Expected route: YELLOW
// Category: bom-traversal
// Expected handler: traverse
// Named entity: Turbo Encabulator

MATCH (prod:Product {name: $product_name})-[:CONTAINS_COMPONENT]->(top:Part)
MATCH path = (top)<-[:COMPONENT_OF*0..20]-(component:Part)
RETURN DISTINCT component, length(path) as depth
ORDER BY depth, component.part_number
