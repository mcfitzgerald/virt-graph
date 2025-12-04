// Query 11: All upstream suppliers from a starting supplier (YELLOW - recursive)
// Expected route: YELLOW
// Category: n-hop-recursive
// Expected handler: traverse

MATCH path = (upstream:Supplier)-[:SUPPLIES_TO*1..10]->(target:Supplier {name: $supplier_name})
RETURN DISTINCT upstream, length(path) as distance
ORDER BY distance, upstream.name
