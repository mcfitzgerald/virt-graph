// Query 8: Orders shipping from a specific facility (GREEN - 1-hop)
// Expected route: GREEN
// Category: 1-hop

MATCH (o:Order)-[:SHIPS_FROM]->(f:Facility {name: $facility_name})
WHERE o.status <> 'cancelled'
RETURN o
ORDER BY o.order_date DESC
LIMIT 100
