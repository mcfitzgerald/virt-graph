// Query 4: Parts from a specific supplier (GREEN - 1-hop join)
// Expected route: GREEN
// Category: 1-hop

MATCH (s:Supplier {name: $supplier_name})-[:PROVIDES]->(p:Part)
RETURN p
ORDER BY p.part_number
