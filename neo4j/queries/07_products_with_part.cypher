// Query 7: Products containing a specific part (GREEN - 1-hop reverse)
// Expected route: GREEN
// Category: 1-hop

MATCH (prod:Product)-[:CONTAINS_COMPONENT]->(part:Part {part_number: $part_number})
RETURN prod
ORDER BY prod.name
