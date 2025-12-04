// Query 2: List all tier 1 suppliers (GREEN - simple filter)
// Expected route: GREEN
// Category: lookup

MATCH (s:Supplier)
WHERE s.tier = 1 AND s.is_active = true
RETURN s
ORDER BY s.name
