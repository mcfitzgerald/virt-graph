# Data Generation Architecture

The generator follows a strictly ordered, 15-level dependency graph to ensure referential integrity.

## Dependency Levels

| Level | Domain | Description | Key Tables |
|-------|--------|-------------|------------|
| **0** | Reference | Foundational master data | `divisions`, `products`, `ingredients` |
| **1** | Master | Physical infrastructure | `plants`, `suppliers`, `route_segments` |
| **2** | Relationships | Sourcing & recipes | `formulas`, `supplier_ingredients` |
| **3** | Network | Logistics network | `retail_accounts`, `distribution_centers` |
| **4** | Product | SKU explosion | `skus`, `promotions`, `sku_costs` |
| **5** | Procurement | Inbound orders | `purchase_orders`, `work_orders` |
| **6** | Manufacturing | Production execution | `batches`, `po_lines`, `gr_lines` |
| **7** | Inventory | Stock & consumption | `inventory`, `batch_ingredients` |
| **8** | Demand | **(Largest)** Customer demand | `pos_sales`, `orders`, `forecasts` |
| **9** | Planning | Order management | `order_lines`, `allocations`, `pick_waves` |
| **10** | Fulfillment | Outbound shipping | `shipments`, `shipment_legs` |
| **11** | Lines | Detailed shipping | `shipment_lines` |
| **12** | Returns | Reverse logistics start | `rma_authorizations`, `returns` |
| **13** | Disposition | Reverse logistics end | `disposition_logs` |
| **14** | Monitoring | Analytics & Logs | `kpi_actuals`, `audit_logs`, `risk_events` |

## Core Components

### 1. GeneratorContext
The `GeneratorContext` class acts as the shared "world state". It holds:
*   **Data Storage:** A dictionary of lists for every table.
*   **ID Mapping:** Dictionaries mapping codes (e.g., "SKU-001") to integer IDs, allowing upper levels to reference lower levels O(1).
*   **Random State:** Seeded NumPy generators for reproducibility.

### 2. Vectorized Generation
For high-volume tables (Levels 8-11), Python loops are too slow. We use `vectorized.py` to generate columns as NumPy arrays.
*   **Zipf Distribution:** Used for SKU selection to match the Pareto (80/20) principle.
*   **Promo Calendar:** A pre-computed index used to apply lift/hangover multipliers to millions of POS rows instantly.

### 3. LookupCache
To avoid O(N) scans when linking tables (e.g., finding all lines for an order), `LookupCache` builds O(1) indices (hash maps) after each level is generated.

### 4. StreamingWriter
Data is written to disk using PostgreSQL `COPY` format. To prevent OOM errors, the `DependencyTracker` allows the writer to purge in-memory data for a table once all its dependent children have been generated.
