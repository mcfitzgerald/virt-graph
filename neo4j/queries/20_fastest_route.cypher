// Query 20: Find fastest shipping route between facilities (RED - weighted shortest path)
// Expected route: RED
// Category: pathfinding
// Expected handler: shortest_path
// Weight column: transit_time_hours

MATCH (start:Facility {name: $from_facility})
MATCH (end:Facility {name: $to_facility})
MATCH path = shortestPath((start)-[:CONNECTS_TO*]->(end))
WITH path, reduce(time = 0.0, r IN relationships(path) | time + r.transit_time_hours) as total_time
RETURN path, total_time
ORDER BY total_time
LIMIT 1
