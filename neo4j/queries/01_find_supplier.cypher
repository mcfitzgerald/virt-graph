// Query 1: Find supplier by name (GREEN - simple lookup)
// Expected route: GREEN
// Category: lookup

MATCH (s:Supplier {name: $supplier_name})
RETURN s
