// Query 10: Find all tier 3 suppliers for a company (YELLOW - n-hop recursive)
// Expected route: YELLOW
// Category: n-hop-recursive
// Expected handler: traverse

MATCH (target:Supplier {name: $company_name})
MATCH path = (s:Supplier)-[:SUPPLIES_TO*1..10]->(target)
WHERE s.tier = 3
RETURN DISTINCT s
ORDER BY s.name
