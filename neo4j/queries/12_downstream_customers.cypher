// Query 12: All downstream customers from a supplier (YELLOW - recursive outbound)
// Expected route: YELLOW
// Category: n-hop-recursive
// Expected handler: traverse

MATCH path = (source:Supplier {name: $supplier_name})-[:SUPPLIES_TO*1..10]->(downstream:Supplier)
RETURN DISTINCT downstream, length(path) as distance
ORDER BY distance, downstream.name
