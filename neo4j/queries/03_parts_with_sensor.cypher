// Query 3: Find all parts with 'sensor' in name (GREEN - text search)
// Expected route: GREEN
// Category: lookup

MATCH (p:Part)
WHERE toLower(p.description) CONTAINS 'sensor'
RETURN p
ORDER BY p.part_number
