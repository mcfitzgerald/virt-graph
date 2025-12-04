// Query 19: Find cheapest shipping route between facilities (RED - weighted shortest path)
// Expected route: RED
// Category: pathfinding
// Expected handler: shortest_path
// Weight column: cost_usd

MATCH (start:Facility {name: $from_facility})
MATCH (end:Facility {name: $to_facility})
MATCH path = shortestPath((start)-[:CONNECTS_TO*]->(end))
WITH path, reduce(cost = 0.0, r IN relationships(path) | cost + r.cost_usd) as total_cost
RETURN path, total_cost
ORDER BY total_cost
LIMIT 1
