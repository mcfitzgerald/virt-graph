// Query 5: Facilities in a specific state (GREEN - simple filter)
// Expected route: GREEN
// Category: lookup

MATCH (f:Facility)
WHERE f.state = $state AND f.is_active = true
RETURN f
ORDER BY f.name
