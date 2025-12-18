-- Virtual Graph Supply Chain Schema
-- ~15 tables with realistic "enterprise messiness":
-- - Inconsistent naming conventions
-- - Nullable FKs, soft deletes
-- - Audit columns
-- - Some denormalization

-- ============================================================================
-- SUPPLIER DOMAIN
-- ============================================================================

CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    supplier_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
    country VARCHAR(100),
    city VARCHAR(100),
    contact_email VARCHAR(255),
    credit_rating VARCHAR(10),
    is_active BOOLEAN DEFAULT true,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX idx_suppliers_tier ON suppliers(tier);
CREATE INDEX idx_suppliers_country ON suppliers(country);
CREATE INDEX idx_suppliers_active ON suppliers(is_active) WHERE deleted_at IS NULL;

-- Self-referential supplier relationships (seller → buyer)
-- This represents the tiered supply chain structure
CREATE TABLE supplier_relationships (
    id SERIAL PRIMARY KEY,
    seller_id INTEGER NOT NULL REFERENCES suppliers(id),
    buyer_id INTEGER NOT NULL REFERENCES suppliers(id),
    relationship_type VARCHAR(50) DEFAULT 'supplies',
    contract_start_date DATE,
    contract_end_date DATE,
    is_primary BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    relationship_status VARCHAR(20) DEFAULT 'active'
        CHECK (relationship_status IN ('active', 'suspended', 'terminated')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT no_self_supply CHECK (seller_id != buyer_id)
);

CREATE INDEX idx_supplier_rel_seller ON supplier_relationships(seller_id);
CREATE INDEX idx_supplier_rel_buyer ON supplier_relationships(buyer_id);
CREATE UNIQUE INDEX idx_supplier_rel_unique ON supplier_relationships(seller_id, buyer_id);
CREATE INDEX idx_supplier_rel_active ON supplier_relationships(is_active) WHERE is_active = true;

-- ============================================================================
-- PARTS DOMAIN
-- ============================================================================

CREATE TABLE parts (
    id SERIAL PRIMARY KEY,
    part_number VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(500),
    category VARCHAR(100),
    unit_cost DECIMAL(12, 2),
    weight_kg DECIMAL(10, 3),
    lead_time_days INTEGER,
    primary_supplier_id INTEGER REFERENCES suppliers(id),
    is_critical BOOLEAN DEFAULT false,
    min_stock_level INTEGER DEFAULT 0,
    -- UoM conversion factors for BOM rollups
    base_uom VARCHAR(10) DEFAULT 'each',  -- Base unit of measure for this part
    unit_weight_kg DECIMAL(12, 6),        -- Weight per 'each' in kg
    unit_length_m DECIMAL(12, 6),         -- Length per 'each' in meters
    unit_volume_l DECIMAL(12, 6),         -- Volume per 'each' in liters
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_parts_category ON parts(category);
CREATE INDEX idx_parts_supplier ON parts(primary_supplier_id);
CREATE INDEX idx_parts_critical ON parts(is_critical) WHERE is_critical = true;

-- Bill of Materials - recursive part hierarchy
-- child_part_id is a component OF parent_part_id
CREATE TABLE bill_of_materials (
    id SERIAL PRIMARY KEY,
    parent_part_id INTEGER NOT NULL REFERENCES parts(id),
    child_part_id INTEGER NOT NULL REFERENCES parts(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit VARCHAR(20) DEFAULT 'each',
    is_optional BOOLEAN DEFAULT false,
    assembly_sequence INTEGER,
    notes TEXT,
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,  -- NULL = currently active
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT no_self_reference CHECK (parent_part_id != child_part_id)
);

CREATE INDEX idx_bom_parent ON bill_of_materials(parent_part_id);
CREATE INDEX idx_bom_child ON bill_of_materials(child_part_id);
CREATE UNIQUE INDEX idx_bom_unique ON bill_of_materials(parent_part_id, child_part_id, effective_from);
CREATE INDEX idx_bom_effective ON bill_of_materials(effective_from, effective_to);

-- Alternate suppliers for parts (many-to-many)
CREATE TABLE part_suppliers (
    id SERIAL PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES parts(id),
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    supplier_part_number VARCHAR(50),
    unit_cost DECIMAL(12, 2),
    lead_time_days INTEGER,
    is_approved BOOLEAN DEFAULT true,
    approval_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_part_suppliers_part ON part_suppliers(part_id);
CREATE INDEX idx_part_suppliers_supplier ON part_suppliers(supplier_id);
CREATE UNIQUE INDEX idx_part_suppliers_unique ON part_suppliers(part_id, supplier_id);

-- ============================================================================
-- PRODUCTS DOMAIN
-- ============================================================================

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    list_price DECIMAL(12, 2),
    is_active BOOLEAN DEFAULT true,
    launch_date DATE,
    discontinued_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_active ON products(is_active);

-- Product to top-level parts mapping
CREATE TABLE product_components (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    part_id INTEGER NOT NULL REFERENCES parts(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    is_required BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_components_product ON product_components(product_id);
CREATE INDEX idx_product_components_part ON product_components(part_id);
CREATE UNIQUE INDEX idx_product_components_unique ON product_components(product_id, part_id);

-- ============================================================================
-- FACILITIES DOMAIN
-- ============================================================================

CREATE TABLE facilities (
    id SERIAL PRIMARY KEY,
    facility_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    facility_type VARCHAR(50) NOT NULL
        CHECK (facility_type IN ('warehouse', 'factory', 'distribution_center', 'supplier_hub')),
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    latitude DECIMAL(10, 6),
    longitude DECIMAL(10, 6),
    capacity_units INTEGER,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_facilities_type ON facilities(facility_type);
CREATE INDEX idx_facilities_country ON facilities(country);
CREATE INDEX idx_facilities_state ON facilities(state);

-- Transport routes between facilities (weighted edges)
CREATE TABLE transport_routes (
    id SERIAL PRIMARY KEY,
    origin_facility_id INTEGER NOT NULL REFERENCES facilities(id),
    destination_facility_id INTEGER NOT NULL REFERENCES facilities(id),
    transport_mode VARCHAR(50) NOT NULL, -- truck, rail, air, sea
    distance_km DECIMAL(10, 2),
    transit_time_hours DECIMAL(10, 2),
    cost_usd DECIMAL(12, 2),
    capacity_tons DECIMAL(10, 2),
    is_active BOOLEAN DEFAULT true,
    route_status VARCHAR(20) DEFAULT 'active'
        CHECK (route_status IN ('active', 'seasonal', 'suspended', 'discontinued')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT no_same_facility CHECK (origin_facility_id != destination_facility_id)
);

CREATE INDEX idx_transport_origin ON transport_routes(origin_facility_id);
CREATE INDEX idx_transport_dest ON transport_routes(destination_facility_id);
CREATE INDEX idx_transport_mode ON transport_routes(transport_mode);
CREATE UNIQUE INDEX idx_transport_unique ON transport_routes(origin_facility_id, destination_facility_id, transport_mode);
CREATE INDEX idx_transport_status ON transport_routes(route_status);

-- ============================================================================
-- INVENTORY DOMAIN
-- ============================================================================

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facilities(id),
    part_id INTEGER NOT NULL REFERENCES parts(id),
    quantity_on_hand INTEGER NOT NULL DEFAULT 0,
    quantity_reserved INTEGER NOT NULL DEFAULT 0,
    quantity_on_order INTEGER NOT NULL DEFAULT 0,
    reorder_point INTEGER,
    last_counted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_inventory_facility ON inventory(facility_id);
CREATE INDEX idx_inventory_part ON inventory(part_id);
CREATE UNIQUE INDEX idx_inventory_unique ON inventory(facility_id, part_id);

-- ============================================================================
-- ORDERS DOMAIN
-- ============================================================================

-- Customer information (denormalized for simplicity)
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    customer_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    customer_type VARCHAR(50), -- retail, wholesale, enterprise
    contact_email VARCHAR(255),
    shipping_address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customers_type ON customers(customer_type);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(30) UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    order_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    required_date DATE,
    shipped_date TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, confirmed, shipped, delivered, cancelled
    shipping_facility_id INTEGER REFERENCES facilities(id),
    total_amount DECIMAL(12, 2),
    shipping_cost DECIMAL(12, 2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_facility ON orders(shipping_facility_id);

-- Order items with SAP-style composite key (order_id, line_number)
-- Following SAP VBAP pattern: Document Number + Item Number
CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id),
    line_number INTEGER NOT NULL,  -- Sequential within order (1, 2, 3...)
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    discount_percent DECIMAL(5, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order_id, line_number)  -- Composite key!
);

CREATE INDEX idx_order_items_product ON order_items(product_id);

-- ============================================================================
-- SHIPMENTS DOMAIN
-- ============================================================================

CREATE TABLE shipments (
    id SERIAL PRIMARY KEY,
    shipment_number VARCHAR(30) UNIQUE NOT NULL,
    order_id INTEGER REFERENCES orders(id),
    purchase_order_id INTEGER,  -- FK added via ALTER TABLE after purchase_orders is created
    return_id INTEGER,          -- FK added via ALTER TABLE after returns is created
    origin_facility_id INTEGER NOT NULL REFERENCES facilities(id),
    destination_facility_id INTEGER REFERENCES facilities(id),
    transport_route_id INTEGER REFERENCES transport_routes(id),
    shipment_type VARCHAR(20) DEFAULT 'order_fulfillment'
        CHECK (shipment_type IN ('order_fulfillment', 'transfer', 'replenishment', 'procurement', 'return')),
    carrier VARCHAR(100),
    tracking_number VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, in_transit, delivered, failed
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    weight_kg DECIMAL(10, 2),
    cost_usd DECIMAL(12, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shipments_order ON shipments(order_id);
CREATE INDEX idx_shipments_po ON shipments(purchase_order_id);
CREATE INDEX idx_shipments_return ON shipments(return_id);
CREATE INDEX idx_shipments_origin ON shipments(origin_facility_id);
CREATE INDEX idx_shipments_dest ON shipments(destination_facility_id);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_route ON shipments(transport_route_id);
CREATE INDEX idx_shipments_type ON shipments(shipment_type);

-- ============================================================================
-- MANUFACTURING EXECUTION DOMAIN
-- ============================================================================

-- Work centers - manufacturing capacity within factories
CREATE TABLE work_centers (
    id SERIAL PRIMARY KEY,
    wc_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    facility_id INTEGER NOT NULL REFERENCES facilities(id),
    work_center_type VARCHAR(50) NOT NULL
        CHECK (work_center_type IN ('assembly', 'machining', 'fabrication', 'testing', 'packaging')),
    capacity_per_day INTEGER,
    efficiency_rating DECIMAL(3, 2) DEFAULT 0.85
        CHECK (efficiency_rating >= 0.00 AND efficiency_rating <= 1.00),
    hourly_rate_usd DECIMAL(10, 2),
    setup_time_mins INTEGER DEFAULT 30,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_work_centers_facility ON work_centers(facility_id);
CREATE INDEX idx_work_centers_type ON work_centers(work_center_type);
CREATE INDEX idx_work_centers_active ON work_centers(is_active) WHERE is_active = true;

-- Production routings - process steps to make a product
CREATE TABLE production_routings (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    step_sequence INTEGER NOT NULL,  -- 10, 20, 30... SAP-style gaps
    operation_name VARCHAR(100) NOT NULL,
    work_center_id INTEGER NOT NULL REFERENCES work_centers(id),
    setup_time_mins INTEGER DEFAULT 15,
    run_time_per_unit_mins DECIMAL(8, 2) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,  -- NULL = currently active
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_routings_product ON production_routings(product_id);
CREATE INDEX idx_routings_wc ON production_routings(work_center_id);
CREATE UNIQUE INDEX idx_routings_unique ON production_routings(product_id, step_sequence, effective_from);
CREATE INDEX idx_routings_effective ON production_routings(effective_from, effective_to);

-- Work orders - the "make" signal for production
CREATE TABLE work_orders (
    id SERIAL PRIMARY KEY,
    wo_number VARCHAR(30) UNIQUE NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id),
    facility_id INTEGER NOT NULL REFERENCES facilities(id),
    order_id INTEGER REFERENCES orders(id),  -- NULL for make-to-stock
    order_type VARCHAR(20) NOT NULL DEFAULT 'make_to_order'
        CHECK (order_type IN ('make_to_order', 'make_to_stock')),
    priority INTEGER DEFAULT 3
        CHECK (priority >= 1 AND priority <= 5),  -- 1=highest, 5=lowest
    quantity_planned INTEGER NOT NULL,
    quantity_completed INTEGER DEFAULT 0,
    quantity_scrapped INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'released'
        CHECK (status IN ('released', 'in_progress', 'quality_hold', 'completed', 'cancelled')),
    planned_start_date DATE,
    planned_end_date DATE,
    actual_start_date TIMESTAMP,
    actual_end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_work_orders_product ON work_orders(product_id);
CREATE INDEX idx_work_orders_facility ON work_orders(facility_id);
CREATE INDEX idx_work_orders_order ON work_orders(order_id);
CREATE INDEX idx_work_orders_status ON work_orders(status);
CREATE INDEX idx_work_orders_type ON work_orders(order_type);
CREATE INDEX idx_work_orders_dates ON work_orders(planned_start_date, planned_end_date);

-- Work order steps - execution progress through routing
CREATE TABLE work_order_steps (
    id SERIAL PRIMARY KEY,
    work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
    routing_step_id INTEGER REFERENCES production_routings(id),
    step_sequence INTEGER NOT NULL,
    work_center_id INTEGER NOT NULL REFERENCES work_centers(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped')),
    quantity_in INTEGER,
    quantity_out INTEGER,
    quantity_scrapped INTEGER DEFAULT 0,
    planned_start TIMESTAMP,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    labor_hours DECIMAL(8, 2),
    machine_hours DECIMAL(8, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wo_steps_wo ON work_order_steps(work_order_id);
CREATE INDEX idx_wo_steps_routing ON work_order_steps(routing_step_id);
CREATE INDEX idx_wo_steps_wc ON work_order_steps(work_center_id);
CREATE INDEX idx_wo_steps_status ON work_order_steps(status);

-- Material transactions - WIP, consumption, and scrap tracking
CREATE TABLE material_transactions (
    id SERIAL PRIMARY KEY,
    transaction_number VARCHAR(30) UNIQUE NOT NULL,
    transaction_type VARCHAR(20) NOT NULL
        CHECK (transaction_type IN ('issue_to_wo', 'receipt_from_wo', 'scrap', 'return_to_stock')),
    work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
    part_id INTEGER REFERENCES parts(id),       -- For issue/scrap: component consumed
    product_id INTEGER REFERENCES products(id),  -- For receipt: product completed
    facility_id INTEGER NOT NULL REFERENCES facilities(id),
    quantity INTEGER NOT NULL,
    unit_cost DECIMAL(12, 2),
    reason_code VARCHAR(50),  -- For scrap: quality_defect, machine_error, operator_error, material_defect
    reference_number VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX idx_mtx_wo ON material_transactions(work_order_id);
CREATE INDEX idx_mtx_part ON material_transactions(part_id);
CREATE INDEX idx_mtx_product ON material_transactions(product_id);
CREATE INDEX idx_mtx_facility ON material_transactions(facility_id);
CREATE INDEX idx_mtx_type ON material_transactions(transaction_type);
CREATE INDEX idx_mtx_date ON material_transactions(created_at);

-- ============================================================================
-- PLAN DOMAIN (SCOR Model)
-- ============================================================================

-- Demand forecasts for S&OP planning
CREATE TABLE demand_forecasts (
    id SERIAL PRIMARY KEY,
    forecast_number VARCHAR(30) UNIQUE NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id),
    facility_id INTEGER NOT NULL REFERENCES facilities(id),
    forecast_date DATE NOT NULL,
    forecast_quantity INTEGER NOT NULL,
    forecast_type VARCHAR(30) NOT NULL
        CHECK (forecast_type IN ('statistical', 'manual', 'consensus', 'machine_learning')),
    confidence_level DECIMAL(3, 2)
        CHECK (confidence_level >= 0.00 AND confidence_level <= 1.00),
    seasonality_factor DECIMAL(5, 2) DEFAULT 1.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT demand_forecasts_unique UNIQUE (product_id, facility_id, forecast_date)
);

CREATE INDEX idx_demand_forecasts_product ON demand_forecasts(product_id);
CREATE INDEX idx_demand_forecasts_facility ON demand_forecasts(facility_id);
CREATE INDEX idx_demand_forecasts_date ON demand_forecasts(forecast_date);
CREATE INDEX idx_demand_forecasts_type ON demand_forecasts(forecast_type);

-- ============================================================================
-- SOURCE DOMAIN (SCOR Model)
-- ============================================================================

-- Purchase orders for parts procurement
CREATE TABLE purchase_orders (
    id SERIAL PRIMARY KEY,
    po_number VARCHAR(30) UNIQUE NOT NULL,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    facility_id INTEGER NOT NULL REFERENCES facilities(id),
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_date DATE,
    received_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'confirmed', 'shipped', 'received', 'cancelled')),
    total_amount DECIMAL(12, 2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_purchase_orders_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_purchase_orders_facility ON purchase_orders(facility_id);
CREATE INDEX idx_purchase_orders_status ON purchase_orders(status);
CREATE INDEX idx_purchase_orders_date ON purchase_orders(order_date);

-- Purchase order line items (composite primary key)
CREATE TABLE purchase_order_lines (
    purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    line_number INTEGER NOT NULL,
    part_id INTEGER NOT NULL REFERENCES parts(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    quantity_received INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'partial', 'received', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (purchase_order_id, line_number)
);

CREATE INDEX idx_po_lines_part ON purchase_order_lines(part_id);

-- ============================================================================
-- RETURN DOMAIN (SCOR Model)
-- ============================================================================

-- Customer returns (RMAs)
CREATE TABLE returns (
    id SERIAL PRIMARY KEY,
    rma_number VARCHAR(30) UNIQUE NOT NULL,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    return_date DATE NOT NULL DEFAULT CURRENT_DATE,
    return_reason VARCHAR(50) NOT NULL
        CHECK (return_reason IN ('defective', 'damaged', 'wrong_item', 'not_as_described', 'changed_mind')),
    status VARCHAR(20) NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested', 'approved', 'received', 'processed', 'rejected')),
    refund_amount DECIMAL(12, 2),
    refund_status VARCHAR(20) DEFAULT 'pending'
        CHECK (refund_status IN ('pending', 'processed', 'denied')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_returns_order ON returns(order_id);
CREATE INDEX idx_returns_customer ON returns(customer_id);
CREATE INDEX idx_returns_status ON returns(status);
CREATE INDEX idx_returns_reason ON returns(return_reason);

-- Return line items (composite primary key)
CREATE TABLE return_items (
    return_id INTEGER NOT NULL REFERENCES returns(id),
    line_number INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    order_line_number INTEGER NOT NULL,
    quantity_returned INTEGER NOT NULL,
    disposition VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (disposition IN ('pending', 'restock', 'refurbish', 'scrap')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (return_id, line_number),
    FOREIGN KEY (order_id, order_line_number) REFERENCES order_items(order_id, line_number)
);

CREATE INDEX idx_return_items_order ON return_items(order_id, order_line_number);

-- ============================================================================
-- ORCHESTRATE DOMAIN (SCOR Model)
-- ============================================================================

-- KPI targets for performance measurement against industry benchmarks
-- Supports SCOR Orchestrate process: metrics like OTD, OEE, Perfect Order Rate
CREATE TABLE kpi_targets (
    id SERIAL PRIMARY KEY,
    kpi_name VARCHAR(100) NOT NULL,
    kpi_category VARCHAR(50) NOT NULL
        CHECK (kpi_category IN ('delivery', 'quality', 'cost', 'inventory', 'production')),
    target_value DECIMAL(12, 4) NOT NULL,
    target_unit VARCHAR(20) NOT NULL,
    threshold_warning DECIMAL(12, 4),
    threshold_critical DECIMAL(12, 4),
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,
    product_id INTEGER REFERENCES products(id),
    facility_id INTEGER REFERENCES facilities(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_kpi_targets_category ON kpi_targets(kpi_category);
CREATE INDEX idx_kpi_targets_product ON kpi_targets(product_id);
CREATE INDEX idx_kpi_targets_facility ON kpi_targets(facility_id);
CREATE INDEX idx_kpi_targets_effective ON kpi_targets(effective_from, effective_to);

-- ============================================================================
-- AUDIT / QUALITY DOMAIN
-- ============================================================================

-- Quality certifications for suppliers
CREATE TABLE supplier_certifications (
    id SERIAL PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    certification_type VARCHAR(100) NOT NULL, -- ISO9001, ISO14001, etc.
    certification_number VARCHAR(100),
    issued_date DATE,
    expiry_date DATE,
    is_valid BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_supplier_certs_supplier ON supplier_certifications(supplier_id);
CREATE INDEX idx_supplier_certs_type ON supplier_certifications(certification_type);

-- Audit log for tracking changes (enterprise pattern)
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL, -- INSERT, UPDATE, DELETE
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_table ON audit_log(table_name);
CREATE INDEX idx_audit_record ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_time ON audit_log(changed_at);

-- ============================================================================
-- DEFERRED FOREIGN KEYS
-- ============================================================================
-- These FKs reference tables defined later in the schema

ALTER TABLE shipments ADD CONSTRAINT fk_shipments_purchase_order
    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id);

ALTER TABLE shipments ADD CONSTRAINT fk_shipments_return
    FOREIGN KEY (return_id) REFERENCES returns(id);

-- ============================================================================
-- SUMMARY: 26 Tables
-- ============================================================================
-- SUPPLIER DOMAIN:
--   1. suppliers
--   2. supplier_relationships (self-referential edges)
-- PARTS DOMAIN:
--   3. parts
--   4. bill_of_materials (recursive BOM edges)
--   5. part_suppliers (many-to-many)
-- PRODUCTS DOMAIN:
--   6. products
--   7. product_components
-- FACILITIES DOMAIN:
--   8. facilities (includes supplier_hub type)
--   9. transport_routes (weighted edges)
-- INVENTORY DOMAIN:
--  10. inventory
-- ORDERS DOMAIN:
--  11. customers
--  12. orders
--  13. order_items (composite key)
-- SHIPMENTS DOMAIN:
--  14. shipments (supports procurement/return types)
-- MANUFACTURING EXECUTION DOMAIN:
--  15. work_centers
--  16. production_routings
--  17. work_orders
--  18. work_order_steps
--  19. material_transactions
-- PLAN DOMAIN (SCOR Model):
--  20. demand_forecasts
-- SOURCE DOMAIN (SCOR Model):
--  21. purchase_orders
--  22. purchase_order_lines (composite key)
-- RETURN DOMAIN (SCOR Model):
--  23. returns
--  24. return_items (composite key)
-- ORCHESTRATE DOMAIN (SCOR Model):
--  25. kpi_targets
-- AUDIT / QUALITY DOMAIN:
--  26. supplier_certifications
-- + audit_log (utility table)

-- ============================================================================
-- VIEWS: Normalized data for graph operations
-- ============================================================================

-- BOM with UoM conversion factors for weight rollups
-- Joins parts to get conversion factors, normalizes all quantities to kg
CREATE VIEW bom_with_conversions AS
SELECT
    b.id,
    b.parent_part_id,
    b.child_part_id,
    b.quantity,
    b.unit,
    -- Normalized weight contribution (always in kg)
    CASE b.unit
        WHEN 'each' THEN b.quantity * COALESCE(p.unit_weight_kg, 0)
        WHEN 'kg' THEN b.quantity::decimal
        WHEN 'm' THEN b.quantity * COALESCE(p.unit_weight_kg, 0)
        WHEN 'L' THEN b.quantity * COALESCE(p.unit_weight_kg, 0)
    END as weight_kg,
    -- Normalized cost contribution (always in USD)
    b.quantity * COALESCE(p.unit_cost, 0) as cost_usd,
    b.is_optional,
    b.assembly_sequence,
    b.effective_from,
    b.effective_to,
    b.created_at,
    b.updated_at
FROM bill_of_materials b
JOIN parts p ON b.child_part_id = p.id;
