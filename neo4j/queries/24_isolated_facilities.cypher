// Query 24: Find isolated or weakly connected facilities (RED - components)
// Expected route: RED
// Category: network-analysis
// Expected handler: connected_components

MATCH (f:Facility)
WHERE f.is_active = true
OPTIONAL MATCH (f)-[:CONNECTS_TO]-(:Facility)
WITH f, count(*) as outbound
OPTIONAL MATCH (f)<-[:CONNECTS_TO]-(:Facility)
WITH f, outbound, count(*) as inbound
WHERE outbound + inbound < 3
RETURN f.name, f.facility_type, f.city, f.state, outbound, inbound
ORDER BY outbound + inbound
