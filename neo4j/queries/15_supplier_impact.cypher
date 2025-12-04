// Query 15: Products affected if supplier fails (YELLOW - impact analysis)
// Expected route: YELLOW
// Category: impact-analysis
// Expected handler: traverse

MATCH (s:Supplier {name: $supplier_name})-[:PROVIDES]->(part:Part)
WITH part
MATCH path = (part)<-[:COMPONENT_OF*0..20]-(ancestor:Part)
WITH DISTINCT ancestor
MATCH (prod:Product)-[:CONTAINS_COMPONENT]->(ancestor)
RETURN DISTINCT prod
ORDER BY prod.name
