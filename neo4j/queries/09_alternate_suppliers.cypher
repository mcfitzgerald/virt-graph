// Query 9: Find alternate suppliers for a part (GREEN - 2-hop pattern)
// Expected route: GREEN
// Category: 2-hop

MATCH (s:Supplier)-[cs:CAN_SUPPLY]->(p:Part {part_number: $part_number})
WHERE cs.is_approved = true
RETURN s.name as supplier, cs.unit_cost, cs.lead_time_days
ORDER BY cs.unit_cost
