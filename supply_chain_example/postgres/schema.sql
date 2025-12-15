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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT no_self_supply CHECK (seller_id != buyer_id)
);

CREATE INDEX idx_supplier_rel_seller ON supplier_relationships(seller_id);
CREATE INDEX idx_supplier_rel_buyer ON supplier_relationships(buyer_id);
CREATE UNIQUE INDEX idx_supplier_rel_unique ON supplier_relationships(seller_id, buyer_id);

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT no_self_reference CHECK (parent_part_id != child_part_id)
);

CREATE INDEX idx_bom_parent ON bill_of_materials(parent_part_id);
CREATE INDEX idx_bom_child ON bill_of_materials(child_part_id);
CREATE UNIQUE INDEX idx_bom_unique ON bill_of_materials(parent_part_id, child_part_id);

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
    facility_type VARCHAR(50) NOT NULL, -- warehouse, factory, distribution_center
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT no_same_facility CHECK (origin_facility_id != destination_facility_id)
);

CREATE INDEX idx_transport_origin ON transport_routes(origin_facility_id);
CREATE INDEX idx_transport_dest ON transport_routes(destination_facility_id);
CREATE INDEX idx_transport_mode ON transport_routes(transport_mode);
CREATE UNIQUE INDEX idx_transport_unique ON transport_routes(origin_facility_id, destination_facility_id, transport_mode);

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

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    discount_percent DECIMAL(5, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);

-- ============================================================================
-- SHIPMENTS DOMAIN
-- ============================================================================

CREATE TABLE shipments (
    id SERIAL PRIMARY KEY,
    shipment_number VARCHAR(30) UNIQUE NOT NULL,
    order_id INTEGER REFERENCES orders(id),
    origin_facility_id INTEGER NOT NULL REFERENCES facilities(id),
    destination_facility_id INTEGER REFERENCES facilities(id),
    transport_route_id INTEGER REFERENCES transport_routes(id),
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
CREATE INDEX idx_shipments_origin ON shipments(origin_facility_id);
CREATE INDEX idx_shipments_dest ON shipments(destination_facility_id);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_route ON shipments(transport_route_id);

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
-- SUMMARY: 15 Tables
-- ============================================================================
-- 1. suppliers
-- 2. supplier_relationships (self-referential edges)
-- 3. parts
-- 4. bill_of_materials (recursive BOM edges)
-- 5. part_suppliers (many-to-many)
-- 6. products
-- 7. product_components
-- 8. facilities
-- 9. transport_routes (weighted edges)
-- 10. inventory
-- 11. customers
-- 12. orders
-- 13. order_items
-- 14. shipments
-- 15. supplier_certifications
-- + audit_log (utility table)
