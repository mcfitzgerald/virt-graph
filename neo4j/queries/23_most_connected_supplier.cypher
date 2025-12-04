// Query 23: Most connected supplier by degree (RED - network analysis)
// Expected route: RED
// Category: network-analysis
// Expected handler: centrality
// Centrality type: degree

MATCH (s:Supplier)
WHERE s.is_active = true
OPTIONAL MATCH (s)-[:SUPPLIES_TO]->(:Supplier)
WITH s, count(*) as supplies_to_count
OPTIONAL MATCH (s)<-[:SUPPLIES_TO]-(:Supplier)
WITH s, supplies_to_count, count(*) as supplied_by_count
OPTIONAL MATCH (s)-[:PROVIDES]->(:Part)
WITH s, supplies_to_count, supplied_by_count, count(*) as parts_provided
RETURN s.name, s.tier, supplies_to_count, supplied_by_count, parts_provided,
       supplies_to_count + supplied_by_count + parts_provided as total_degree
ORDER BY total_degree DESC
LIMIT 10
