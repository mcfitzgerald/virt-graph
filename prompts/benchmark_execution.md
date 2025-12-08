 **Your task**: Work through each question using SQL (for GREEN) or handlers (for YELLOW/RED).

 ## Context

 **Ontology**: `ontology/supply_chain.yaml`
 - 9 Entity Classes: Supplier, Part, Product, Facility, Customer, Order, Shipment, Inventory, SupplierCertification
 - 15 Relationships with complexity: GREEN (simple SQL), YELLOW (recursive traversal), RED (network algorithms)

 **Database**: PostgreSQL running via `make db-up`
 - Connection: `postgresql://virt_graph:dev_password@localhost:5432/supply_chain`

 **Available Handlers** (import from `virt_graph.handlers`):
 - YELLOW: `traverse()`, `traverse_collecting()`, `bom_explode()`
 - RED: `shortest_path()`, `all_shortest_paths()`, `centrality()`, `connected_components()`

 **Key Tables**:
 - `suppliers` (500 rows) - tiered network via `supplier_relationships`
 - `parts` (5000 rows) - BOM hierarchy via `bill_of_materials`
 - `facilities` (50 rows) - transport network via `transport_routes`

 **Named Test Entities** (use these in queries):
 - Suppliers: "Acme Corp", "GlobalTech Industries", "Pacific Components", "Eastern Electronics"
 - Products: "Turbo Encabulator", "Flux Capacitor"
 - Facilities: "Chicago Warehouse", "LA Distribution Center", "New York Factory"

 ## Workflow

 For each question:
 1. Classify: GREEN/YELLOW/RED
 2. GREEN → Write SQL directly
 3. YELLOW → Use traverse/bom_explode handler
 4. RED → Use shortest_path/centrality handler
 5. Test against database
 6. Record result

 Start with Q01 and work through systematically.