// Query 25: Find all possible routes between facilities (RED - path enumeration)
// Expected route: RED
// Category: pathfinding
// Expected handler: all_shortest_paths

MATCH (start:Facility {name: $from_facility})
MATCH (end:Facility {name: $to_facility})
MATCH path = (start)-[:CONNECTS_TO*1..5]->(end)
WITH path,
     reduce(cost = 0.0, r IN relationships(path) | cost + r.cost_usd) as total_cost,
     reduce(time = 0.0, r IN relationships(path) | time + r.transit_time_hours) as total_time,
     length(path) as hops
RETURN [n IN nodes(path) | n.name] as route,
       hops,
       total_cost,
       total_time
ORDER BY hops, total_cost
LIMIT 10
