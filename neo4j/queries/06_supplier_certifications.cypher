// Query 6: Get all certifications for a supplier (GREEN - 1-hop)
// Expected route: GREEN
// Category: 1-hop

MATCH (s:Supplier {name: $supplier_name})-[:HAS_CERTIFICATION]->(c:Certification)
WHERE c.is_valid = true
RETURN s.name as supplier, c.certification_type, c.expiry_date
ORDER BY c.expiry_date
