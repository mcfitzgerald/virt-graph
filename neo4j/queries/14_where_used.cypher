// Query 14: Where is this part used? (YELLOW - reverse BOM traversal)
// Expected route: YELLOW
// Category: bom-traversal
// Expected handler: traverse

MATCH path = (part:Part {part_number: $part_number})-[:COMPONENT_OF*1..20]->(parent:Part)
RETURN DISTINCT parent, length(path) as depth
ORDER BY depth, parent.part_number
