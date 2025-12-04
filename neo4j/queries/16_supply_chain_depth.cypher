// Query 16: Find supply chain depth from a T1 supplier (YELLOW - chain analysis)
// Expected route: YELLOW
// Category: n-hop-recursive
// Expected handler: traverse

MATCH (t1:Supplier {name: $supplier_name})
WHERE t1.tier = 1
MATCH path = (upstream:Supplier)-[:SUPPLIES_TO*1..10]->(t1)
WITH upstream, length(path) as chain_depth
RETURN upstream.name, upstream.tier, chain_depth
ORDER BY chain_depth DESC, upstream.name
