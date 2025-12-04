// Query 22: Most critical facility by betweenness centrality (RED - network analysis)
// Expected route: RED
// Category: network-analysis
// Expected handler: centrality
// Centrality type: betweenness

// Note: Neo4j GDS library would be used in production for this
// This is a simplified version using native Cypher patterns
MATCH (f:Facility)
WHERE f.is_active = true
OPTIONAL MATCH (f)<-[:CONNECTS_TO]-(:Facility)
WITH f, count(*) as inbound
OPTIONAL MATCH (f)-[:CONNECTS_TO]->(:Facility)
WITH f, inbound, count(*) as outbound
RETURN f, inbound + outbound as total_connections
ORDER BY total_connections DESC
LIMIT 10
