// Query 21: Find shortest distance route between facilities (RED - weighted path)
// Expected route: RED
// Category: pathfinding
// Expected handler: shortest_path
// Weight column: distance_km

MATCH (start:Facility {name: $from_facility})
MATCH (end:Facility {name: $to_facility})
MATCH path = shortestPath((start)-[:CONNECTS_TO*]->(end))
WITH path, reduce(dist = 0.0, r IN relationships(path) | dist + r.distance_km) as total_distance
RETURN path, total_distance
ORDER BY total_distance
LIMIT 1
