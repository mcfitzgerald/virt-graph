#!/usr/bin/env python3
"""Generate curated cost-to-serve demo DuckDB (~2400 rows, 41 tables).

Story: Same premium toothpaste, 53% margin through Club, 22% through Convenience.
Seven CTS dimensions: freight/drop-size, trade spend (explicit decomposition),
returns, payment terms, yield variance, supplier price creep.
Trade management: 10 programs, ~8 promo events, ~530 deductions decomposing
gross-to-net by type (scan, rebate, promo, slotting, off-invoice).

Usage: poetry run python scripts/generate_demo_db.py [--output PATH] [--schema PATH]
Output: pcg_example/data/demo.duckdb
"""

import argparse
import duckdb
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "pcg_example" / "data" / "demo.duckdb"
DEFAULT_SCHEMA = REPO_ROOT / "erp_schema_duckdb.sql"


# ---------------------------------------------------------------------------
# GL helper
# ---------------------------------------------------------------------------

_gl_id = [0]


def gl_pair(entries, txn_seq, day, dr_acct, cr_acct, amount, ref_type, ref_id,
            desc, product_id=None, node_id=None):
    """Append balanced debit/credit GL entries."""
    _gl_id[0] += 1
    dr_id = _gl_id[0]
    _gl_id[0] += 1
    cr_id = _gl_id[0]
    entries.append((dr_id, txn_seq, day, day, dr_acct, round(amount, 4), 0,
                     ref_type, str(ref_id), node_id, product_id, desc, False))
    entries.append((cr_id, txn_seq, day, day, cr_acct, 0, round(amount, 4),
                     ref_type, str(ref_id), node_id, product_id, desc, False))


# ---------------------------------------------------------------------------
# Master Data
# ---------------------------------------------------------------------------

def insert_suppliers(conn):
    rows = [
        (1, 'SUP-001', 'ChemSource International', 'Shanghai', 'CN', 31.2304, 121.4737, 1, True),
        (2, 'SUP-002', 'AmeriPack Solutions', 'Houston', 'US', 29.7604, -95.3698, 1, True),
        (3, 'SUP-003', 'GreenBase Ingredients', 'Mumbai', 'IN', 19.0760, 72.8777, 2, True),
        (4, 'SUP-004', 'NorthStar Chemicals', 'Toronto', 'CA', 43.6532, -79.3832, 1, True),
        (5, 'SUP-005', 'Pacific Fragrances', 'Los Angeles', 'US', 34.0522, -118.2437, 2, True),
    ]
    conn.executemany("INSERT INTO suppliers VALUES (?,?,?,?,?,?,?,?,?)", rows)


def insert_ingredients(conn):
    rows = [
        (1,  'ACT-FLUOR-001',  'Stannous Fluoride',     'active',    'fluoride',   2, 0.15, 185.00, 'kg', True),
        (2,  'ACT-SURFAC-001', 'Sodium Lauryl Sulfate',  'active',    'surfactant', 2, 1.00, 12.50,  'kg', True),
        (3,  'ACT-CITRIC-001', 'Citric Acid',            'active',    'acid',       2, 1.00, 8.75,   'kg', True),
        (4,  'BASE-SORBIT-001','Sorbitol Solution',       'base',      'humectant',  2, 1.00, 3.20,   'kg', True),
        (5,  'BASE-WATER-001', 'Purified Water',          'base',      'solvent',    2, 1.00, 0.15,   'kg', True),
        (6,  'BASE-GLYCER-001','Glycerin',                'base',      'humectant',  2, 1.00, 4.80,   'kg', True),
        (7,  'BASE-SILICA-001','Hydrated Silica',         'base',      'abrasive',   2, 0.50, 22.00,  'kg', True),
        (8,  'FRAG-CITRUS-001','Citrus Essential Oil',    'fragrance', 'essential',  2, 0.25, 45.00,  'kg', True),
        (9,  'FRAG-MINT-001',  'Peppermint Oil',          'fragrance', 'essential',  2, 0.25, 38.00,  'kg', True),
        (10, 'PKG-TUBE-001',   'Laminate Tube 150ml',     'packaging', 'tube',       2, 0.03, 0.42,   'unit', True),
        (11, 'PKG-BOTTLE-001', 'HDPE Bottle 500ml',       'packaging', 'bottle',     2, 0.04, 0.68,   'unit', True),
        (12, 'PKG-BOTTLE-002', 'PET Bottle 250ml',        'packaging', 'bottle',     2, 0.03, 0.55,   'unit', True),
        (13, 'PKG-CAP-001',    'Flip-Top Cap',            'packaging', 'closure',    2, 0.01, 0.18,   'unit', True),
        (14, 'PKG-LABEL-001',  'Adhesive Label',          'packaging', 'label',      2, 0.005,0.08,   'unit', True),
        (15, 'STAB-XANTH-001', 'Xanthan Gum',            'stabilizer','thickener',  2, 0.10, 32.00,  'kg', True),
    ]
    conn.executemany("INSERT INTO ingredients VALUES (?,?,?,?,?,?,?,?,?,?)", rows)


def insert_supplier_ingredients(conn):
    rows = [
        # id, supplier_id, ingredient_id, unit_cost, lead_time_days, min_order_qty
        (1,  1, 1,  185.00, 45, 50.0),    # Fluoride — single source from China
        (2,  1, 7,   22.00, 45, 200.0),   # Silica from China
        (3,  1, 15,  32.00, 45, 100.0),   # Xanthan from China
        (4,  2, 10,   0.42, 7,  5000.0),  # Tubes from AmeriPack
        (5,  2, 11,   0.68, 7,  5000.0),  # HDPE bottles — PO price $0.68
        (6,  2, 12,   0.55, 7,  5000.0),  # PET bottles
        (7,  2, 13,   0.18, 7,  10000.0), # Caps
        (8,  2, 14,   0.08, 7,  10000.0), # Labels
        (9,  3, 2,   11.80, 30, 500.0),   # SLS from India (cheaper)
        (10, 3, 3,    8.75, 30, 300.0),   # Citric acid from India
        (11, 3, 4,    3.20, 30, 1000.0),  # Sorbitol from India
        (12, 3, 6,    4.80, 30, 500.0),   # Glycerin from India
        (13, 4, 2,   12.80, 10, 200.0),   # SLS from Canada (pricier, faster)
        (14, 4, 5,    0.15, 3,  2000.0),  # Water — trivially cheap, fast
        (15, 4, 4,    3.40, 10, 500.0),   # Sorbitol from Canada
        (16, 4, 6,    5.10, 10, 300.0),   # Glycerin from Canada
        (17, 5, 8,   45.00, 14, 50.0),    # Citrus oil
        (18, 5, 9,   38.00, 14, 50.0),    # Peppermint oil
        (19, 3, 5,    0.12, 30, 5000.0),  # Water from India (bulk)
        (20, 1, 3,    8.50, 45, 500.0),   # Citric acid from China (alt)
        (21, 2, 13,   0.19, 5,  8000.0),  # Caps — alt pricing
        (22, 4, 15,  33.50, 10, 50.0),    # Xanthan from Canada
    ]
    conn.executemany("INSERT INTO supplier_ingredients VALUES (?,?,?,?,?,?)", rows)


def insert_plants(conn):
    rows = [
        (1, 'PLANT-EAST',    'Philadelphia Plant', 'Philadelphia', 'US', 39.9526, -75.1652, 50.0, True),
        (2, 'PLANT-CENTRAL', 'Cincinnati Plant',   'Cincinnati',   'US', 39.1031, -84.5120, 40.0, True),
        (3, 'PLANT-WEST',    'Phoenix Plant',       'Phoenix',      'US', 33.4484, -112.0740, 35.0, True),
    ]
    conn.executemany("INSERT INTO plants VALUES (?,?,?,?,?,?,?,?,?)", rows)


def insert_production_lines(conn):
    rows = [
        (1, 'PL-EAST-1',    'Tube Line East',     1, 'tube_filling',   200, True),
        (2, 'PL-EAST-2',    'Bottle Line East',   1, 'bottle_filling', 150, True),
        (3, 'PL-CENTRAL-1', 'Tube Line Central',  2, 'tube_filling',   180, True),
        (4, 'PL-CENTRAL-2', 'Mixing Line Central',2, 'mixing',         100, True),
        (5, 'PL-WEST-1',    'Bottle Line West',   3, 'bottle_filling', 160, True),
        (6, 'PL-WEST-2',    'Mixing Line West',   3, 'mixing',         120, True),
    ]
    conn.executemany("INSERT INTO production_lines VALUES (?,?,?,?,?,?,?)", rows)


def insert_channels(conn):
    rows = [
        (1, 'CLUB',        'Club',        'warehouse',   True),
        (2, 'GROCERY',     'Grocery',     'supermarket',  True),
        (3, 'CONVENIENCE', 'Convenience', 'convenience', True),
    ]
    conn.executemany("INSERT INTO channels VALUES (?,?,?,?,?)", rows)


def insert_chart_of_accounts(conn):
    rows = [
        (1,  '1000', 'Cash',               'asset',   True),
        (2,  '1100', 'Accounts Receivable', 'asset',   True),
        (3,  '1200', 'RM Inventory',        'asset',   True),
        (4,  '1300', 'WIP',                 'asset',   True),
        (5,  '1400', 'FG Inventory',        'asset',   True),
        (6,  '1500', 'In-Transit',          'asset',   True),
        (7,  '2000', 'Accounts Payable',    'liability', True),
        (8,  '4000', 'Revenue',             'revenue', True),
        (9,  '5000', 'COGS',               'expense', True),
        (10, '5100', 'Freight Expense',     'expense', True),
        (11, '5200', 'Trade Spend',         'expense', True),
        (12, '5300', 'Return Expense',      'expense', True),
    ]
    conn.executemany("INSERT INTO chart_of_accounts VALUES (?,?,?,?,?)", rows)


def insert_bulk_intermediates(conn):
    rows = [
        (51, 'BULK-WPB-001', 'Whitening Paste Base',      'oral_care',      1, 10.0, 8.50,  'kg', True),
        (52, 'BULK-APC-001', 'All-Purpose Cleaner Base',   'home_care',      1, 10.0, 3.20,  'kg', True),
        (53, 'BULK-BWB-001', 'Body Wash Base',             'personal_wash',  1, 10.0, 3.80,  'kg', True),
        (54, 'BULK-FAP-001', 'Fluoride Active Premix',     'oral_care',      2, 5.0,  95.00, 'kg', True),
        (55, 'BULK-CFP-001', 'Citrus Fragrance Premix',    'home_care',      2, 5.0,  28.00, 'kg', True),
        (56, 'BULK-MGB-001', 'Mint Gel Base',              'oral_care',      1, 10.0, 6.20,  'kg', True),
    ]
    conn.executemany("INSERT INTO bulk_intermediates VALUES (?,?,?,?,?,?,?,?,?)", rows)


def insert_formulas(conn):
    rows = [
        # Premix formulas (bom_level=2)
        (1,  'F-PREMIX-FLUOR', 'Fluoride Active Premix',    54, 2, 100.0, 98.0, None, None),
        (2,  'F-PREMIX-CITRUS','Citrus Fragrance Premix',   55, 2, 50.0,  95.0, None, None),
        # Bulk formulas (bom_level=1)
        (3,  'F-BULK-WPB',     'Whitening Paste Base',      51, 1, 500.0, 97.0, None, None),
        (4,  'F-BULK-APC',     'All-Purpose Cleaner Base',  52, 1, 500.0, 97.0, None, None),
        (5,  'F-BULK-BWB',     'Body Wash Base',            53, 1, 500.0, 97.0, None, None),
        (6,  'F-BULK-MGB',     'Mint Gel Base',             56, 1, 500.0, 97.0, None, None),
        # SKU formulas (bom_level=0)
        (7,  'F-SKU-OC001',    'BrightSmile Premium',       1,  0, 200.0, 98.0, 180.0, 0.5),
        (8,  'F-SKU-OC002',    'BrightSmile Mint Fresh',    2,  0, 200.0, 98.0, 200.0, 0.5),
        (9,  'F-SKU-HC001',    'FreshHome All-Purpose',     3,  0, 300.0, 97.0, 150.0, 0.75),
        (10, 'F-SKU-HC002',    'FreshHome Citrus Spray',    4,  0, 250.0, 97.0, 160.0, 0.5),
        (11, 'F-SKU-PW001',    'AquaPure Body Wash',        5,  0, 300.0, 97.0, 140.0, 0.75),
        (12, 'F-SKU-PW002',    'AquaPure Gentle',           6,  0, 300.0, 97.0, 140.0, 0.75),
        (13, 'F-SKU-OC003',    'BrightSmile Kids',          7,  0, 150.0, 98.0, 200.0, 0.5),
        (14, 'F-SKU-HC003',    'FreshHome Lavender',        8,  0, 250.0, 97.0, 160.0, 0.5),
    ]
    conn.executemany("INSERT INTO formulas VALUES (?,?,?,?,?,?,?,?,?)", rows)


def insert_formula_ingredients(conn):
    rows = [
        # F1: Fluoride Active Premix — ingredients only
        (1, 1, 1, 45.0),   # Stannous Fluoride
        (1, 7, 2, 30.0),   # Silica
        (1, 5, 3, 20.0),   # Water
        (1, 15, 4, 5.0),   # Xanthan Gum
        # F2: Citrus Fragrance Premix
        (2, 8, 1, 15.0),   # Citrus Essential Oil
        (2, 3, 2, 10.0),   # Citric Acid
        (2, 6, 3, 15.0),   # Glycerin
        (2, 5, 4, 10.0),   # Water
        # F3: Whitening Paste Base — uses premix 54
        (3, 54, 1, 50.0),  # Fluoride Active Premix (bulk_intermediate)
        (3, 4, 2, 200.0),  # Sorbitol
        (3, 5, 3, 150.0),  # Water
        (3, 6, 4, 80.0),   # Glycerin
        (3, 15, 5, 20.0),  # Xanthan
        # F4: All-Purpose Cleaner Base — uses premix 55
        (4, 55, 1, 30.0),  # Citrus Fragrance Premix (bulk_intermediate)
        (4, 2, 2, 100.0),  # SLS
        (4, 5, 3, 300.0),  # Water
        (4, 3, 4, 50.0),   # Citric Acid
        (4, 15, 5, 20.0),  # Xanthan
        # F5: Body Wash Base
        (5, 2, 1, 120.0),  # SLS
        (5, 6, 2, 100.0),  # Glycerin
        (5, 5, 3, 200.0),  # Water
        (5, 4, 4, 60.0),   # Sorbitol
        (5, 15, 5, 20.0),  # Xanthan
        # F6: Mint Gel Base
        (6, 9, 1, 20.0),   # Peppermint Oil
        (6, 4, 2, 150.0),  # Sorbitol
        (6, 5, 3, 250.0),  # Water
        (6, 6, 4, 60.0),   # Glycerin
        (6, 15, 5, 20.0),  # Xanthan
        # F7: BrightSmile Premium (SKU 1) — bulk 51 + packaging
        (7, 51, 1, 150.0),  # Whitening Paste Base
        (7, 10, 2, 12.0),   # Tubes (12 per case)
        (7, 14, 3, 12.0),   # Labels
        (7, 13, 4, 12.0),   # Caps
        # F8: BrightSmile Mint Fresh (SKU 2) — bulk 56 + packaging
        (8, 56, 1, 120.0),  # Mint Gel Base
        (8, 10, 2, 12.0),   # Tubes
        (8, 14, 3, 12.0),   # Labels
        (8, 13, 4, 12.0),   # Caps
        # F9: FreshHome All-Purpose (SKU 3) — bulk 52 + packaging
        (9, 52, 1, 250.0),  # APC Base
        (9, 11, 2, 12.0),   # HDPE Bottles
        (9, 13, 3, 12.0),   # Caps
        (9, 14, 4, 12.0),   # Labels
        # F10: FreshHome Citrus Spray (SKU 4) — bulk 52 + premix 55 + pkg
        (10, 52, 1, 150.0), # APC Base
        (10, 55, 2, 20.0),  # Citrus Premix
        (10, 12, 3, 12.0),  # PET Bottles
        (10, 13, 4, 12.0),  # Caps
        (10, 14, 5, 12.0),  # Labels
        # F11: AquaPure Body Wash (SKU 5) — bulk 53 + packaging
        (11, 53, 1, 250.0), # Body Wash Base
        (11, 11, 2, 12.0),  # HDPE Bottles
        (11, 13, 3, 12.0),  # Caps
        (11, 14, 4, 12.0),  # Labels
        # F12: AquaPure Gentle (SKU 6) — bulk 53 + packaging
        (12, 53, 1, 250.0), # Body Wash Base
        (12, 12, 2, 12.0),  # PET Bottles
        (12, 13, 3, 12.0),  # Caps
        (12, 14, 4, 12.0),  # Labels
        # F13: BrightSmile Kids (SKU 7) — bulk 51 + packaging
        (13, 51, 1, 100.0), # Whitening Paste Base
        (13, 10, 2, 12.0),  # Tubes
        (13, 14, 3, 12.0),  # Labels
        (13, 13, 4, 12.0),  # Caps
        # F14: FreshHome Lavender (SKU 8) — bulk 52 + packaging
        (14, 52, 1, 200.0), # APC Base
        (14, 12, 2, 12.0),  # PET Bottles
        (14, 13, 3, 12.0),  # Caps
        (14, 14, 4, 12.0),  # Labels
    ]
    conn.executemany("INSERT INTO formula_ingredients VALUES (?,?,?,?)", rows)


def insert_skus(conn):
    rows = [
        # id, code, name, category, brand, units/case, weight_kg, cost/case, price/case, segment, active, supersedes
        (1,  'SKU-OC-001', 'BrightSmile Premium Whitening 150ml', 'ORAL_CARE',      'BrightSmile', 12, 5.40, 18.00, 48.00, 'premium',  True,  None),
        (2,  'SKU-OC-002', 'BrightSmile Mint Fresh Gel 120ml',    'ORAL_CARE',      'BrightSmile', 12, 4.32, 14.20, 36.00, 'mid',      True,  None),
        (3,  'SKU-HC-001', 'FreshHome All-Purpose Cleaner 500ml', 'HOME_CARE',      'FreshHome',   12, 7.20, 8.60,  22.50, 'mid',      True,  None),
        (4,  'SKU-HC-002', 'FreshHome Citrus Spray 350ml',        'HOME_CARE',      'FreshHome',   12, 5.04, 7.80,  18.00, 'value',    True,  None),
        (5,  'SKU-PW-001', 'AquaPure Body Wash 250ml',            'PERSONAL_WASH',  'AquaPure',    12, 7.20, 7.90,  16.50, 'mid',      True,  None),
        (6,  'SKU-PW-002', 'AquaPure Gentle Body Wash 250ml',     'PERSONAL_WASH',  'AquaPure',    12, 7.20, 7.50,  14.00, 'value',    True,  None),
        (7,  'SKU-OC-003', 'BrightSmile Kids Paste 75ml',         'ORAL_CARE',      'BrightSmile', 12, 4.32, 11.00, 28.00, 'mid',      True,  None),
        (8,  'SKU-HC-003', 'FreshHome Lavender Spray 350ml',      'HOME_CARE',      'FreshHome',   12, 5.04, 8.20,  19.50, 'mid',      True,  None),
        (9,  'SKU-OC-001-OLD', 'BrightSmile Whitening 150ml (OLD)', 'ORAL_CARE',    'BrightSmile', 12, 5.40, 16.80, 45.00, 'premium',  False, 1),
        (10, 'SKU-PW-001-OLD', 'AquaPure Body Wash 250ml (OLD)',    'PERSONAL_WASH', 'AquaPure',   12, 7.20, 7.60,  15.00, 'mid',      False, 5),
    ]
    conn.executemany("INSERT INTO skus VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def insert_distribution_centers(conn):
    rows = [
        (1, 'RDC-EAST',         'RDC East Charlotte',   'Charlotte',    'US', 35.2271, -80.8431, 'rdc',         True),
        (2, 'RDC-CENTRAL',      'RDC Central Nashville', 'Nashville',   'US', 36.1627, -86.7816, 'rdc',         True),
        (3, 'CLUB-DC-EAST',     'Club DC Atlanta',       'Atlanta',     'US', 33.7490, -84.3880, 'customer_dc', True),
        (4, 'GROC-DC-SOUTH',    'Grocery DC Tampa',      'Tampa',       'US', 27.9506, -82.4572, 'customer_dc', True),
        (5, 'CONV-DC-NORTHEAST','Conv DC Newark',        'Newark',      'US', 40.7357, -74.1724, 'customer_dc', True),
        (6, 'GROC-DC-CENTRAL',  'Grocery DC Indianapolis','Indianapolis','US', 39.7684, -86.1581, 'customer_dc', True),
    ]
    conn.executemany("INSERT INTO distribution_centers VALUES (?,?,?,?,?,?,?,?,?)", rows)


def insert_retail_locations(conn):
    rows = [
        (1, 'CLUB-ATL-1',  'Club Store Atlanta-1',     'Atlanta',      'US', 33.7490, -84.3880, 'club',        'CLUB',        True),
        (2, 'CLUB-ATL-2',  'Club Store Atlanta-2',      'Marietta',     'US', 33.9526, -84.5499, 'club',        'CLUB',        True),
        (3, 'GROC-TPA-1',  'FreshMart Tampa-1',         'Tampa',        'US', 27.9506, -82.4572, 'supermarket', 'GROCERY',     True),
        (4, 'GROC-TPA-2',  'FreshMart Tampa-2',         'Clearwater',   'US', 27.9659, -82.8001, 'supermarket', 'GROCERY',     True),
        (5, 'CONV-NYC',    'QuickStop NYC',             'New York',     'US', 40.7128, -74.0060, 'convenience', 'CONVENIENCE', True),
        (6, 'CONV-NWK',    'QuickStop Newark',          'Newark',       'US', 40.7357, -74.1724, 'convenience', 'CONVENIENCE', True),
        (7, 'GROC-IND',    'FreshMart Indianapolis',    'Indianapolis', 'US', 39.7684, -86.1581, 'supermarket', 'GROCERY',     True),
        (8, 'CONV-PHL',    'QuickStop Philadelphia',    'Philadelphia', 'US', 39.9526, -75.1652, 'convenience', 'CONVENIENCE', True),
    ]
    conn.executemany("INSERT INTO retail_locations VALUES (?,?,?,?,?,?,?,?,?,?)", rows)


def insert_route_segments(conn):
    rows = [
        # Plant → RDC (inbound primary distribution)
        (1,  'RS-P1-RDC1', 'plant', 1, 'rdc', 1, 'FTL', 850.0, 14.0),   # Philly→Charlotte
        (2,  'RS-P2-RDC2', 'plant', 2, 'rdc', 2, 'FTL', 430.0, 7.0),    # Cincy→Nashville
        (3,  'RS-P3-RDC1', 'plant', 3, 'rdc', 1, 'FTL', 3200.0, 48.0),  # Phoenix→Charlotte
        (4,  'RS-P1-RDC2', 'plant', 1, 'rdc', 2, 'FTL', 1100.0, 18.0),  # Philly→Nashville
        # RDC → Customer DC
        (5,  'RS-RDC1-CLUB', 'rdc', 1, 'customer_dc', 3, 'FTL', 380.0, 6.0),   # Charlotte→Club DC Atlanta
        (6,  'RS-RDC1-GROC', 'rdc', 1, 'customer_dc', 4, 'LTL', 900.0, 15.0),  # Charlotte→Grocery DC Tampa
        (7,  'RS-RDC1-CONV', 'rdc', 1, 'customer_dc', 5, 'LTL', 850.0, 14.0),  # Charlotte→Conv DC Newark
        (8,  'RS-RDC2-GROC', 'rdc', 2, 'customer_dc', 6, 'LTL', 460.0, 8.0),   # Nashville→Grocery DC Indy
        (9,  'RS-RDC2-CLUB', 'rdc', 2, 'customer_dc', 3, 'FTL', 400.0, 7.0),   # Nashville→Club DC Atlanta
        # Customer DC → Store (last mile)
        (10, 'RS-CLUB-ATL1', 'customer_dc', 3, 'store', 1, 'FTL', 5.0,  0.5),   # Club DC→Club ATL-1
        (11, 'RS-CLUB-ATL2', 'customer_dc', 3, 'store', 2, 'FTL', 30.0, 1.0),   # Club DC→Club ATL-2
        (12, 'RS-GROC-TPA1', 'customer_dc', 4, 'store', 3, 'LTL', 10.0, 1.0),   # Groc DC→FreshMart Tampa-1
        (13, 'RS-GROC-TPA2', 'customer_dc', 4, 'store', 4, 'LTL', 40.0, 2.0),   # Groc DC→FreshMart Tampa-2
        (14, 'RS-CONV-NYC',  'customer_dc', 5, 'store', 5, 'LTL', 15.0, 3.0),   # Conv DC→QuickStop NYC
        (15, 'RS-CONV-NWK',  'customer_dc', 5, 'store', 6, 'LTL', 5.0,  1.0),   # Conv DC→QuickStop Newark
        (16, 'RS-GROC-IND',  'customer_dc', 6, 'store', 7, 'LTL', 8.0,  1.0),   # Groc DC Indy→FreshMart Indy
        (17, 'RS-CONV-PHL',  'customer_dc', 5, 'store', 8, 'LTL', 130.0, 3.0),  # Conv DC Newark→QuickStop Philly
        # Supplier → Plant (inbound)
        (18, 'RS-SUP1-P1', 'supplier', 1, 'plant', 1, 'ocean', 19000.0, 720.0), # Shanghai→Philly
        (19, 'RS-SUP2-P1', 'supplier', 2, 'plant', 1, 'FTL', 2500.0, 36.0),     # Houston→Philly
        (20, 'RS-SUP3-P2', 'supplier', 3, 'plant', 2, 'ocean', 15000.0, 600.0), # Mumbai→Cincy
        (21, 'RS-SUP4-P1', 'supplier', 4, 'plant', 1, 'FTL', 900.0, 14.0),      # Toronto→Philly
        (22, 'RS-SUP5-P3', 'supplier', 5, 'plant', 3, 'FTL', 600.0, 10.0),      # LA→Phoenix
        (23, 'RS-SUP2-P2', 'supplier', 2, 'plant', 2, 'FTL', 1600.0, 24.0),     # Houston→Cincy
        (24, 'RS-SUP4-P2', 'supplier', 4, 'plant', 2, 'FTL', 800.0, 12.0),      # Toronto→Cincy
        (25, 'RS-RDC1-RDC2','rdc', 1, 'rdc', 2, 'FTL', 550.0, 9.0),             # Charlotte↔Nashville lateral
    ]
    conn.executemany("INSERT INTO route_segments VALUES (?,?,?,?,?,?,?,?,?)", rows)


# ---------------------------------------------------------------------------
# Procurement
# ---------------------------------------------------------------------------

def insert_purchase_orders(conn):
    rows = [
        # id, po_number, supplier_id, plant_id, order_date, status, txn_seq
        (1,  'PO-001', 1, 1, 5,  'closed', 1001),  # ChemSource→Philly (fluoride, silica, xanthan)
        (2,  'PO-002', 2, 1, 6,  'closed', 1002),  # AmeriPack→Philly (tubes, bottles, caps, labels)
        (3,  'PO-003', 3, 2, 7,  'closed', 1003),  # GreenBase→Cincy (SLS, citric, sorbitol, glycerin)
        (4,  'PO-004', 4, 1, 8,  'closed', 1004),  # NorthStar→Philly (SLS, water, sorbitol)
        (5,  'PO-005', 5, 3, 9,  'closed', 1005),  # Pacific→Phoenix (citrus oil, mint oil)
        (6,  'PO-006', 2, 2, 10, 'closed', 1006),  # AmeriPack→Cincy (bottles, caps, labels)
        (7,  'PO-007', 1, 2, 12, 'closed', 1007),  # ChemSource→Cincy (silica, xanthan)
        (8,  'PO-008', 3, 1, 14, 'closed', 1008),  # GreenBase→Philly (SLS, glycerin)
        (9,  'PO-009', 4, 2, 15, 'closed', 1009),  # NorthStar→Cincy (water, glycerin)
        (10, 'PO-010', 2, 3, 16, 'closed', 1010),  # AmeriPack→Phoenix (bottles, caps)
        (11, 'PO-011', 1, 1, 18, 'closed', 1011),  # ChemSource→Philly (fluoride reorder)
        (12, 'PO-012', 2, 1, 20, 'closed', 1012),  # AmeriPack→Philly (HDPE bottles reorder)
        (13, 'PO-013', 3, 2, 22, 'closed', 1013),  # GreenBase→Cincy (bulk reorder)
        (14, 'PO-014', 5, 1, 24, 'closed', 1014),  # Pacific→Philly (fragrances)
        (15, 'PO-015', 4, 1, 25, 'closed', 1015),  # NorthStar→Philly (water, sorbitol)
        (16, 'PO-016', 2, 2, 26, 'closed', 1016),  # AmeriPack→Cincy (bottles reorder)
        (17, 'PO-017', 3, 3, 27, 'closed', 1017),  # GreenBase→Phoenix
        (18, 'PO-018', 2, 1, 28, 'closed', 1018),  # AmeriPack→Philly (HDPE reorder #3)
        (19, 'PO-019', 1, 2, 29, 'closed', 1019),  # ChemSource→Cincy (xanthan)
        (20, 'PO-020', 4, 3, 30, 'closed', 1020),  # NorthStar→Phoenix
    ]
    conn.executemany("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?)", rows)


def insert_purchase_order_lines(conn):
    rows = [
        # po_id, line, ingredient_id, qty_kg, unit_cost, status
        (1, 1, 1,  100.0,  185.00, 'closed'),  # Fluoride
        (1, 2, 7,  400.0,  22.00,  'closed'),  # Silica
        (1, 3, 15, 200.0,  32.00,  'closed'),  # Xanthan
        (2, 1, 10, 5000.0, 0.42,   'closed'),  # Tubes (units, stored as qty_kg)
        (2, 2, 11, 5000.0, 0.68,   'closed'),  # HDPE Bottles at $0.68
        (2, 3, 13, 10000.0,0.18,   'closed'),  # Caps
        (2, 4, 14, 10000.0,0.08,   'closed'),  # Labels
        (3, 1, 2,  600.0,  11.80,  'closed'),  # SLS
        (3, 2, 3,  400.0,  8.75,   'closed'),  # Citric acid
        (3, 3, 4,  1200.0, 3.20,   'closed'),  # Sorbitol
        (3, 4, 6,  600.0,  4.80,   'closed'),  # Glycerin
        (4, 1, 2,  300.0,  12.80,  'closed'),  # SLS from Canada
        (4, 2, 5,  3000.0, 0.15,   'closed'),  # Water
        (4, 3, 4,  600.0,  3.40,   'closed'),  # Sorbitol
        (5, 1, 8,  100.0,  45.00,  'closed'),  # Citrus oil
        (5, 2, 9,  80.0,   38.00,  'closed'),  # Mint oil
        (6, 1, 11, 5000.0, 0.68,   'closed'),  # HDPE Bottles
        (6, 2, 13, 8000.0, 0.18,   'closed'),  # Caps
        (6, 3, 14, 8000.0, 0.08,   'closed'),  # Labels
        (7, 1, 7,  300.0,  22.00,  'closed'),  # Silica
        (7, 2, 15, 150.0,  32.00,  'closed'),  # Xanthan
        (8, 1, 2,  400.0,  11.80,  'closed'),  # SLS
        (8, 2, 6,  400.0,  4.80,   'closed'),  # Glycerin
        (9, 1, 5,  2000.0, 0.15,   'closed'),  # Water
        (9, 2, 6,  300.0,  5.10,   'closed'),  # Glycerin from Canada
        (10,1, 11, 3000.0, 0.68,   'closed'),  # HDPE Bottles
        (10,2, 13, 6000.0, 0.18,   'closed'),  # Caps
        (11,1, 1,  80.0,   185.00, 'closed'),  # Fluoride reorder
        (12,1, 11, 5000.0, 0.68,   'closed'),  # HDPE Bottles reorder
        (13,1, 2,  500.0,  11.80,  'closed'),  # SLS
        (13,2, 4,  800.0,  3.20,   'closed'),  # Sorbitol
        (14,1, 8,  60.0,   45.00,  'closed'),  # Citrus oil
        (14,2, 9,  50.0,   38.00,  'closed'),  # Mint oil
        (15,1, 5,  2000.0, 0.15,   'closed'),  # Water
        (16,1, 11, 4000.0, 0.68,   'closed'),  # HDPE Bottles
    ]
    conn.executemany("INSERT INTO purchase_order_lines VALUES (?,?,?,?,?,?)", rows)


def insert_goods_receipts(conn):
    rows = [
        # id, gr_number, shipment_id, plant_id, receipt_date, status, txn_seq
        (1,  'GR-001', None, 1, 50,  'received', 2001),  # PO-001 ChemSource (45-day lead)
        (2,  'GR-002', None, 1, 13,  'received', 2002),  # PO-002 AmeriPack (7-day)
        (3,  'GR-003', None, 2, 37,  'received', 2003),  # PO-003 GreenBase (30-day)
        (4,  'GR-004', None, 1, 18,  'received', 2004),  # PO-004 NorthStar (10-day)
        (5,  'GR-005', None, 3, 23,  'received', 2005),  # PO-005 Pacific (14-day)
        (6,  'GR-006', None, 2, 17,  'received', 2006),  # PO-006 AmeriPack
        (7,  'GR-007', None, 2, 57,  'received', 2007),  # PO-007 ChemSource
        (8,  'GR-008', None, 1, 44,  'received', 2008),  # PO-008 GreenBase
        (9,  'GR-009', None, 2, 25,  'received', 2009),  # PO-009 NorthStar
        (10, 'GR-010', None, 3, 23,  'received', 2010),  # PO-010 AmeriPack
        (11, 'GR-011', None, 1, 63,  'received', 2011),  # PO-011 ChemSource reorder
        (12, 'GR-012', None, 1, 27,  'received', 2012),  # PO-012 AmeriPack reorder
        (13, 'GR-013', None, 2, 52,  'received', 2013),  # PO-013 GreenBase
        (14, 'GR-014', None, 1, 38,  'received', 2014),  # PO-014 Pacific
        (15, 'GR-015', None, 1, 35,  'received', 2015),  # PO-015 NorthStar
        (16, 'GR-016', None, 2, 33,  'received', 2016),  # PO-016 AmeriPack
        (17, 'GR-017', None, 3, 57,  'received', 2017),  # PO-017 GreenBase
        (18, 'GR-018', None, 1, 35,  'received', 2018),  # PO-018 AmeriPack
        (19, 'GR-019', None, 2, 74,  'received', 2019),  # PO-019 ChemSource
        (20, 'GR-020', None, 3, 40,  'received', 2020),  # PO-020 NorthStar
    ]
    conn.executemany("INSERT INTO goods_receipts VALUES (?,?,?,?,?,?,?)", rows)


def insert_goods_receipt_lines(conn):
    rows = [
        # gr_id, line, ingredient_id, qty_kg — mirror PO lines
        (1, 1, 1,  100.0),
        (1, 2, 7,  400.0),
        (1, 3, 15, 200.0),
        (2, 1, 10, 5000.0),
        (2, 2, 11, 5000.0),
        (2, 3, 13, 10000.0),
        (2, 4, 14, 10000.0),
        (3, 1, 2,  600.0),
        (3, 2, 3,  400.0),
        (3, 3, 4,  1200.0),
        (3, 4, 6,  600.0),
        (4, 1, 2,  300.0),
        (4, 2, 5,  3000.0),
        (4, 3, 4,  600.0),
        (5, 1, 8,  100.0),
        (5, 2, 9,  80.0),
        (6, 1, 11, 5000.0),
        (6, 2, 13, 8000.0),
        (6, 3, 14, 8000.0),
        (7, 1, 7,  300.0),
        (7, 2, 15, 150.0),
        (8, 1, 2,  400.0),
        (8, 2, 6,  400.0),
        (9, 1, 5,  2000.0),
        (9, 2, 6,  300.0),
        (10,1, 11, 3000.0),
        (10,2, 13, 6000.0),
        (11,1, 1,  80.0),
        (12,1, 11, 5000.0),
        (13,1, 2,  500.0),
        (13,2, 4,  800.0),
        (14,1, 8,  60.0),
        (14,2, 9,  50.0),
        (15,1, 5,  2000.0),
        (16,1, 11, 4000.0),
    ]
    conn.executemany("INSERT INTO goods_receipt_lines VALUES (?,?,?,?)", rows)


def insert_ap_invoices(conn):
    rows = [
        # id, txn_seq, invoice_number, supplier_id, gr_id, invoice_date, due_date, total_amount, currency, status
        (1,  7001, 'API-001', 1, 1,  52, 82,  35300.00,  'USD', 'paid'),
        (2,  7002, 'API-002', 2, 2,  14, 44,  7470.00,   'USD', 'paid'),  # AmeriPack — includes HDPE at $0.72!
        (3,  7003, 'API-003', 3, 3,  38, 68,  16560.00,  'USD', 'paid'),
        (4,  7004, 'API-004', 4, 4,  19, 49,  5490.00,   'USD', 'paid'),
        (5,  7005, 'API-005', 5, 5,  24, 54,  7540.00,   'USD', 'paid'),
        (6,  7006, 'API-006', 2, 6,  18, 48,  5440.00,   'USD', 'paid'),  # AmeriPack — HDPE at $0.72
        (7,  7007, 'API-007', 1, 7,  58, 88,  11400.00,  'USD', 'paid'),
        (8,  7008, 'API-008', 3, 8,  45, 75,  6640.00,   'USD', 'paid'),
        (9,  7009, 'API-009', 4, 9,  26, 56,  1830.00,   'USD', 'paid'),
        (10, 7010, 'API-010', 2, 10, 24, 54,  3240.00,   'USD', 'paid'),  # AmeriPack — HDPE at $0.72
        (11, 7011, 'API-011', 1, 11, 64, 90,  14800.00,  'USD', 'paid'),
        (12, 7012, 'API-012', 2, 12, 28, 58,  3600.00,   'USD', 'paid'),  # AmeriPack — HDPE at $0.72
        (13, 7013, 'API-013', 3, 13, 53, 83,  8460.00,   'USD', 'paid'),
        (14, 7014, 'API-014', 5, 14, 39, 69,  4600.00,   'USD', 'paid'),
        (15, 7015, 'API-015', 4, 15, 36, 66,  300.00,    'USD', 'paid'),
        (16, 7016, 'API-016', 2, 16, 34, 64,  4160.00,   'USD', 'paid'),  # AmeriPack — HDPE at $0.72
        (17, 7017, 'API-017', 3, 17, 58, 88,  4200.00,   'USD', 'paid'),
        (18, 7018, 'API-018', 2, 18, 36, 66,  3600.00,   'USD', 'paid'),  # AmeriPack — HDPE at $0.72
        (19, 7019, 'API-019', 1, 19, 75, 90,  4800.00,   'USD', 'open'),
        (20, 7020, 'API-020', 4, 20, 41, 71,  1500.00,   'USD', 'paid'),
    ]
    conn.executemany("INSERT INTO ap_invoices VALUES (?,?,?,?,?,?,?,?,?,?)", rows)


def insert_ap_invoice_lines(conn):
    rows = [
        # invoice_id, line, ingredient_id, qty_kg, unit_cost, line_amount
        # API-001: ChemSource — normal pricing
        (1, 1, 1,  100.0, 185.00, 18500.00),
        (1, 2, 7,  400.0, 22.00,  8800.00),
        (1, 3, 15, 200.0, 32.00,  6400.00),
        # API-002: AmeriPack — HDPE at $0.72 (overcharge!)
        (2, 1, 10, 5000.0, 0.42, 2100.00),
        (2, 2, 11, 5000.0, 0.72, 3600.00),  # $0.72 vs PO $0.68!
        (2, 3, 13, 10000.0,0.18, 1800.00),
        (2, 4, 14, 10000.0,0.08, 800.00),   # total = 8300; fix total above later
        # API-003: GreenBase
        (3, 1, 2,  600.0, 11.80, 7080.00),
        (3, 2, 3,  400.0, 8.75,  3500.00),
        (3, 3, 4,  1200.0,3.20,  3840.00),
        (3, 4, 6,  600.0, 4.80,  2880.00),
        # API-004: NorthStar
        (4, 1, 2,  300.0, 12.80, 3840.00),
        (4, 2, 5,  3000.0,0.15,  450.00),
        (4, 3, 4,  600.0, 3.40,  2040.00),  # total = 6330
        # API-005: Pacific
        (5, 1, 8,  100.0, 45.00, 4500.00),
        (5, 2, 9,  80.0,  38.00, 3040.00),
        # API-006: AmeriPack→Cincy — HDPE at $0.72
        (6, 1, 11, 5000.0, 0.72, 3600.00),  # overcharge
        (6, 2, 13, 8000.0, 0.18, 1440.00),
        (6, 3, 14, 8000.0, 0.08, 640.00),
        # API-007: ChemSource
        (7, 1, 7,  300.0, 22.00, 6600.00),
        (7, 2, 15, 150.0, 32.00, 4800.00),
        # API-008: GreenBase
        (8, 1, 2,  400.0, 11.80, 4720.00),
        (8, 2, 6,  400.0, 4.80,  1920.00),
        # API-009: NorthStar
        (9, 1, 5,  2000.0,0.15,  300.00),
        (9, 2, 6,  300.0, 5.10,  1530.00),
        # API-010: AmeriPack→Phoenix — HDPE at $0.72
        (10,1, 11, 3000.0, 0.72, 2160.00),  # overcharge
        (10,2, 13, 6000.0, 0.18, 1080.00),
        # API-011: ChemSource reorder
        (11,1, 1,  80.0, 185.00, 14800.00),
        # API-012: AmeriPack HDPE reorder — $0.72
        (12,1, 11, 5000.0, 0.72, 3600.00),  # overcharge
        # API-013: GreenBase
        (13,1, 2,  500.0, 11.80, 5900.00),
        (13,2, 4,  800.0, 3.20,  2560.00),
        # API-014: Pacific
        (14,1, 8,  60.0, 45.00, 2700.00),
        (14,2, 9,  50.0, 38.00, 1900.00),
        # API-015: NorthStar water
        (15,1, 5,  2000.0,0.15,  300.00),
        # API-016: AmeriPack→Cincy HDPE reorder — $0.72
        (16,1, 11, 4000.0, 0.72, 2880.00),  # overcharge
        # API-017: GreenBase→Phoenix
        (17,1, 2,  300.0, 11.80, 3540.00),
        (17,2, 4,  500.0, 3.20,  1600.00),  # total 5140; approx
        # API-018: AmeriPack HDPE reorder #3 — $0.72
        (18,1, 11, 5000.0, 0.72, 3600.00),  # overcharge
        # API-019: ChemSource xanthan
        (19,1, 15, 150.0, 32.00, 4800.00),
        # API-020: NorthStar→Phoenix
        (20,1, 5,  1500.0,0.15,  225.00),
        (20,2, 4,  500.0, 3.40,  1700.00),  # total 1925; approx
    ]
    conn.executemany("INSERT INTO ap_invoice_lines VALUES (?,?,?,?,?,?)", rows)


def insert_ap_payments(conn):
    rows = [
        # id, txn_seq, invoice_id, payment_date, amount, discount, net_amount, method, status
        (1,  9001, 1,  80,  35300.00, 0, 35300.00, 'EFT', 'completed'),
        (2,  9002, 2,  42,  8300.00,  0, 8300.00,  'EFT', 'completed'),
        (3,  9003, 3,  65,  17300.00, 0, 17300.00, 'EFT', 'completed'),
        (4,  9004, 4,  48,  6330.00,  0, 6330.00,  'EFT', 'completed'),
        (5,  9005, 5,  52,  7540.00,  0, 7540.00,  'EFT', 'completed'),
        (6,  9006, 6,  46,  5680.00,  0, 5680.00,  'EFT', 'completed'),
        (7,  9007, 7,  85,  11400.00, 0, 11400.00, 'EFT', 'completed'),
        (8,  9008, 8,  73,  6640.00,  0, 6640.00,  'EFT', 'completed'),
        (9,  9009, 9,  54,  1830.00,  0, 1830.00,  'EFT', 'completed'),
        (10, 9010, 10, 52,  3240.00,  0, 3240.00,  'EFT', 'completed'),
        (11, 9011, 11, 88,  14800.00, 0, 14800.00, 'EFT', 'completed'),
        (12, 9012, 12, 56,  3600.00,  0, 3600.00,  'EFT', 'completed'),
        (13, 9013, 13, 80,  8460.00,  0, 8460.00,  'EFT', 'completed'),
        (14, 9014, 14, 67,  4600.00,  0, 4600.00,  'EFT', 'completed'),
        (15, 9015, 15, 64,  300.00,   0, 300.00,   'EFT', 'completed'),
        (16, 9016, 16, 62,  4160.00,  0, 4160.00,  'EFT', 'completed'),
        (17, 9017, 17, 85,  5140.00,  0, 5140.00,  'EFT', 'completed'),
        (18, 9018, 18, 64,  3600.00,  0, 3600.00,  'EFT', 'completed'),
    ]
    conn.executemany("INSERT INTO ap_payments VALUES (?,?,?,?,?,?,?,?,?)", rows)


def insert_invoice_variances(conn):
    rows = [
        # id, invoice_id, line_number, variance_type, expected, actual, variance_amount, resolution
        (1, 2,  2, 'price', 0.68, 0.72, 200.00,  'open'),  # 5000 × $0.04
        (2, 6,  1, 'price', 0.68, 0.72, 200.00,  'open'),
        (3, 10, 1, 'price', 0.68, 0.72, 120.00,  'open'),  # 3000 × $0.04
        (4, 12, 1, 'price', 0.68, 0.72, 200.00,  'open'),
        (5, 16, 1, 'price', 0.68, 0.72, 160.00,  'open'),  # 4000 × $0.04
        (6, 18, 1, 'price', 0.68, 0.72, 200.00,  'open'),
        (7, 2,  2, 'price', 0.68, 0.72, 200.00,  'open'),  # duplicate intentional—different review
        (8, 6,  1, 'price', 0.68, 0.72, 200.00,  'open'),
    ]
    conn.executemany("INSERT INTO invoice_variances VALUES (?,?,?,?,?,?,?,?)", rows)


# ---------------------------------------------------------------------------
# Manufacturing
# ---------------------------------------------------------------------------

def insert_work_orders(conn):
    rows = [
        # id, wo_number, plant_id, formula_id, planned_qty_kg, planned_start, due_date, status, txn_seq
        (1,  'WO-001', 1, 1,  100.0,  10, 12, 'complete', 3001),  # Fluoride premix
        (2,  'WO-002', 2, 2,  50.0,   11, 13, 'complete', 3002),  # Citrus premix — yield trap
        (3,  'WO-003', 1, 3,  500.0,  14, 18, 'complete', 3003),  # Whitening paste base
        (4,  'WO-004', 2, 4,  500.0,  15, 19, 'complete', 3004),  # APC base
        (5,  'WO-005', 3, 5,  500.0,  16, 20, 'complete', 3005),  # Body wash base
        (6,  'WO-006', 1, 6,  500.0,  17, 21, 'complete', 3006),  # Mint gel base
        (7,  'WO-007', 1, 7,  200.0,  22, 26, 'complete', 3007),  # SKU 1 BrightSmile Premium
        (8,  'WO-008', 1, 8,  200.0,  23, 27, 'complete', 3008),  # SKU 2 Mint Fresh
        (9,  'WO-009', 2, 9,  300.0,  24, 28, 'complete', 3009),  # SKU 3 FreshHome APC
        (10, 'WO-010', 2, 10, 250.0,  25, 29, 'complete', 3010),  # SKU 4 FreshHome Citrus
        (11, 'WO-011', 3, 11, 300.0,  26, 30, 'complete', 3011),  # SKU 5 AquaPure BW
        (12, 'WO-012', 3, 12, 300.0,  27, 31, 'complete', 3012),  # SKU 6 AquaPure Gentle
        (13, 'WO-013', 1, 13, 150.0,  28, 32, 'complete', 3013),  # SKU 7 Kids Paste
        (14, 'WO-014', 2, 14, 250.0,  29, 33, 'complete', 3014),  # SKU 8 Lavender
        (15, 'WO-015', 2, 2,  50.0,   32, 34, 'complete', 3015),  # Citrus premix #2 — yield trap
        (16, 'WO-016', 2, 2,  50.0,   35, 37, 'complete', 3016),  # Citrus premix #3 — yield trap
        (17, 'WO-017', 1, 7,  200.0,  38, 42, 'complete', 3017),  # SKU 1 rerun
        (18, 'WO-018', 2, 9,  300.0,  40, 44, 'complete', 3018),  # SKU 3 rerun
    ]
    conn.executemany("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?)", rows)


def insert_batches(conn):
    rows = [
        # id, batch_number, wo_id, plant_id, formula_id, product_id, qty_kg, yield%, prod_date, status, product_type, bom_level, txn_seq
        # Premix batches
        (1,  'B-001', 1,  1, 1, 54, 98.0,  98.0, 11, 'complete', 'premix', 2, 3101),
        (2,  'B-002', 2,  2, 2, 55, 42.5,  85.0, 12, 'complete', 'premix', 2, 3102),  # BAD YIELD
        (3,  'B-003', 2,  2, 2, 55, 41.0,  82.0, 13, 'complete', 'premix', 2, 3103),  # BAD YIELD
        # Bulk intermediate batches
        (4,  'B-004', 3,  1, 3, 51, 485.0, 97.0, 15, 'complete', 'bulk_intermediate', 1, 3104),
        (5,  'B-005', 4,  2, 4, 52, 485.0, 97.0, 16, 'complete', 'bulk_intermediate', 1, 3105),
        (6,  'B-006', 5,  3, 5, 53, 485.0, 97.0, 17, 'complete', 'bulk_intermediate', 1, 3106),
        (7,  'B-007', 6,  1, 6, 56, 485.0, 97.0, 18, 'complete', 'bulk_intermediate', 1, 3107),
        # Finished good batches — normal yields
        (8,  'B-008', 7,  1, 7, 1,  196.0, 98.0, 23, 'complete', 'finished_good', 0, 3108),  # SKU 1
        (9,  'B-009', 8,  1, 8, 2,  196.0, 98.0, 24, 'complete', 'finished_good', 0, 3109),  # SKU 2
        (10, 'B-010', 9,  2, 9, 3,  291.0, 97.0, 25, 'complete', 'finished_good', 0, 3110),  # SKU 3
        (11, 'B-011', 10, 2, 10,4,  242.5, 97.0, 26, 'complete', 'finished_good', 0, 3111),  # SKU 4
        (12, 'B-012', 11, 3, 11,5,  291.0, 97.0, 27, 'complete', 'finished_good', 0, 3112),  # SKU 5
        (13, 'B-013', 12, 3, 12,6,  291.0, 97.0, 28, 'complete', 'finished_good', 0, 3113),  # SKU 6
        (14, 'B-014', 13, 1, 13,7,  147.0, 98.0, 29, 'complete', 'finished_good', 0, 3114),  # SKU 7
        (15, 'B-015', 14, 2, 14,8,  242.5, 97.0, 30, 'complete', 'finished_good', 0, 3115),  # SKU 8
        # More citrus premix — bad yields
        (16, 'B-016', 15, 2, 2, 55, 41.5,  83.0, 33, 'complete', 'premix', 2, 3116),  # BAD YIELD
        (17, 'B-017', 16, 2, 2, 55, 42.0,  84.0, 36, 'complete', 'premix', 2, 3117),  # BAD YIELD
        # Rerun batches
        (18, 'B-018', 17, 1, 7, 1,  196.0, 98.0, 39, 'complete', 'finished_good', 0, 3118),  # SKU 1 rerun
        (19, 'B-019', 18, 2, 9, 3,  291.0, 97.0, 41, 'complete', 'finished_good', 0, 3119),  # SKU 3 rerun
        # Additional normal batches
        (20, 'B-020', None, 1, 1, 54, 98.0, 98.0, 35, 'complete', 'premix', 2, 3120),
        (21, 'B-021', None, 2, 4, 52, 485.0,97.0, 34, 'complete', 'bulk_intermediate', 1, 3121),
        (22, 'B-022', None, 3, 5, 53, 485.0,97.0, 36, 'complete', 'bulk_intermediate', 1, 3122),
        (23, 'B-023', None, 1, 7, 1,  196.0,98.0, 45, 'complete', 'finished_good', 0, 3123),  # SKU 1
        (24, 'B-024', None, 2, 9, 3,  291.0,97.0, 46, 'complete', 'finished_good', 0, 3124),  # SKU 3
        (25, 'B-025', None, 3, 11,5,  291.0,97.0, 47, 'complete', 'finished_good', 0, 3125),  # SKU 5
        (26, 'B-026', None, 1, 8, 2,  196.0,98.0, 48, 'complete', 'finished_good', 0, 3126),  # SKU 2
        (27, 'B-027', None, 2, 10,4,  242.5,97.0, 49, 'complete', 'finished_good', 0, 3127),  # SKU 4
        (28, 'B-028', None, 2, 14,8,  242.5,97.0, 50, 'complete', 'finished_good', 0, 3128),  # SKU 8
        # One more bad citrus premix
        (29, 'B-029', None, 2, 2, 55, 41.0, 82.0, 52, 'complete', 'premix', 2, 3129),  # BAD YIELD
        (30, 'B-030', None, 1, 13,7,  147.0,98.0, 53, 'complete', 'finished_good', 0, 3130),  # SKU 7
    ]
    conn.executemany("INSERT INTO batches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def insert_batch_ingredients(conn):
    """Generate batch ingredients based on formula and batch quantity."""
    # For simplicity, we compute from formula proportions.
    # Bad-yield batches (2,3,16,17,29) consume MORE material for LESS output.
    import random
    random.seed(42)

    # Load formula ingredient ratios
    formulas_ingredients = {}
    for row in conn.execute("SELECT formula_id, ingredient_id, sequence, quantity_kg FROM formula_ingredients").fetchall():
        fid = row[0]
        if fid not in formulas_ingredients:
            formulas_ingredients[fid] = []
        formulas_ingredients[fid].append((row[1], row[2], row[3]))

    # Load formula batch_size
    formula_sizes = {}
    for row in conn.execute("SELECT id, batch_size_kg FROM formulas").fetchall():
        formula_sizes[row[0]] = row[1]

    # Load batches
    batches = conn.execute(
        "SELECT id, formula_id, quantity_kg, yield_percent FROM batches"
    ).fetchall()

    bad_yield_ids = {2, 3, 16, 17, 29}
    bi_id = 0
    bi_rows = []

    for batch_id, formula_id, batch_qty, yield_pct in batches:
        if formula_id not in formulas_ingredients:
            continue
        formula_size = formula_sizes.get(formula_id, 100.0)
        scale = float(batch_qty) / (float(yield_pct) / 100.0) / float(formula_size)

        for ing_id, seq, formula_qty in formulas_ingredients[formula_id]:
            base_qty = float(formula_qty) * scale
            if batch_id in bad_yield_ids:
                # Bad yield: consumed 15-20% MORE material
                actual_qty = base_qty * random.uniform(1.15, 1.20)
            else:
                # Normal: within 1-2%
                actual_qty = base_qty * random.uniform(0.99, 1.02)
            bi_id += 1
            bi_rows.append((bi_id, batch_id, ing_id, round(actual_qty, 4)))

    conn.executemany("INSERT INTO batch_ingredients VALUES (?,?,?,?)", bi_rows)
    return len(bi_rows)


# ---------------------------------------------------------------------------
# Demand & Fulfillment — THE CRITICAL SECTION
# ---------------------------------------------------------------------------

def _build_orders():
    """Build orders with channel-specific profiles."""
    import random
    random.seed(123)

    orders = []
    order_lines_all = []
    oid = 0
    ol_data = []  # (order_id, channel, retail_loc_id, [(sku_id, cases)])

    # Hero SKU (1) appears in ~40 orders. Other SKUs rotate.
    sku_pool = {
        'CLUB': [1, 2, 3, 7],       # OC + HC
        'GROCERY': [1, 3, 4, 5, 8], # mixed
        'CONVENIENCE': [1, 2, 5, 6], # OC + PW
    }

    # Club: 15 orders, 150-300 cases, stores 1-2
    for i in range(15):
        oid += 1
        day = random.randint(15, 75)
        loc = random.choice([1, 2])
        total = random.randint(150, 300)
        skus = [1] + random.sample([2, 3, 7], k=random.randint(1, 2))
        cases_split = _split_cases(total, len(skus))
        lines = list(zip(skus, cases_split))
        orders.append((oid, f'ORD-{oid:03d}', day, 1, loc, 'delivered', total, 5000 + oid))
        ol_data.append((oid, 'CLUB', loc, lines))

    # Grocery: 25 orders, 40-80 cases, stores 3,4,7
    for i in range(25):
        oid += 1
        day = random.randint(15, 80)
        loc = random.choice([3, 4, 7])
        total = random.randint(40, 80)
        skus = [1] + random.sample([3, 4, 5, 8], k=random.randint(1, 2))
        cases_split = _split_cases(total, len(skus))
        lines = list(zip(skus, cases_split))
        orders.append((oid, f'ORD-{oid:03d}', day, 2, loc, 'delivered', total, 5000 + oid))
        ol_data.append((oid, 'GROCERY', loc, lines))

    # Convenience: 20 orders, 8-20 cases, stores 5,6,8
    for i in range(20):
        oid += 1
        day = random.randint(20, 85)
        loc = random.choice([5, 6, 8])
        total = random.randint(8, 20)
        skus = [1] + random.sample([2, 5, 6], k=random.randint(1, 2))
        cases_split = _split_cases(total, len(skus))
        lines = list(zip(skus, cases_split))
        orders.append((oid, f'ORD-{oid:03d}', day, 3, loc, 'delivered', total, 5000 + oid))
        ol_data.append((oid, 'CONVENIENCE', loc, lines))

    # Build order_lines
    for oid, channel, loc, lines in ol_data:
        for ln_num, (sku_id, cases) in enumerate(lines, 1):
            order_lines_all.append((oid, ln_num, sku_id, cases, 0, 'delivered'))

    return orders, order_lines_all, ol_data


def _split_cases(total, n):
    """Split total cases roughly among n SKUs, hero SKU gets largest share."""
    if n == 1:
        return [total]
    hero_share = int(total * 0.5)
    remainder = total - hero_share
    others = []
    for i in range(n - 1):
        if i == n - 2:
            others.append(remainder)
        else:
            part = max(1, remainder // (n - 1 - i))
            others.append(part)
            remainder -= part
    return [hero_share] + others


def insert_orders(conn):
    orders, _, _ = _build_orders()
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", orders)
    return len(orders)


def insert_order_lines(conn):
    _, order_lines, _ = _build_orders()
    conn.executemany("INSERT INTO order_lines VALUES (?,?,?,?,?,?)", order_lines)
    return len(order_lines)


def _build_shipments(ol_data):
    """Build multi-leg shipments with channel-dedicated freight economics."""
    import random
    random.seed(456)

    # SKU weights
    sku_weights = {1: 5.40, 2: 4.32, 3: 7.20, 4: 5.04, 5: 7.20, 6: 7.20, 7: 4.32, 8: 5.04}

    # Freight $/case targets by channel and leg
    freight_rates = {
        'CLUB':        {'plant_to_rdc': 0.60, 'rdc_to_customer_dc': 0.60, 'customer_dc_to_store': 0.40},
        'GROCERY':     {'plant_to_rdc': 0.70, 'rdc_to_customer_dc': 1.00, 'customer_dc_to_store': 2.50},
        'CONVENIENCE': {'plant_to_rdc': 0.80, 'rdc_to_customer_dc': 2.50, 'customer_dc_to_store': 8.00},
    }

    # Store-level last-mile overrides for convenience
    conv_last_mile = {5: 15.00, 6: 9.50, 8: 7.20}

    # Channel → DC mapping
    channel_dc = {'CLUB': 3, 'GROCERY': 4, 'CONVENIENCE': 5}
    # Grocery store 7 uses DC 6
    store_dc_override = {7: 6}

    # Channel → RDC
    channel_rdc = {'CLUB': 1, 'GROCERY': 1, 'CONVENIENCE': 1}

    # Channel → Plant
    channel_plant = {'CLUB': 1, 'GROCERY': 1, 'CONVENIENCE': 1}

    shipments = []
    shipment_lines_all = []
    sid = 0

    # Group orders by channel and store for efficient shipment building
    from collections import defaultdict
    channel_store_orders = defaultdict(list)
    for oid, channel, loc, lines in ol_data:
        channel_store_orders[(channel, loc)].append((oid, lines))

    # For each channel/store combo, create 3-leg shipment chain
    for (channel, store_id), store_orders in channel_store_orders.items():
        # Aggregate total cases and SKU breakdown
        total_cases = 0
        sku_cases = defaultdict(int)
        order_day_max = 0
        for oid, lines in store_orders:
            # Get order day
            for o in ol_data:
                if o[0] == oid:
                    break
            for sku_id, cases in lines:
                sku_cases[sku_id] += cases
                total_cases += cases

        # Get the max order day for timing
        for o in ol_data:
            if o[0] in [so[0] for so in store_orders]:
                pass  # we'll use a fixed schedule

        rates = freight_rates[channel]
        rdc_id = channel_rdc[channel]
        cust_dc_id = store_dc_override.get(store_id, channel_dc[channel])
        plant_id = channel_plant[channel]

        base_day = 30  # shipments start around day 30

        # Leg 1: plant → RDC
        sid += 1
        leg1_freight = round(rates['plant_to_rdc'] * total_cases, 2)
        total_weight = round(sum(sku_weights.get(s, 6.0) * c for s, c in sku_cases.items()), 2)
        shipments.append((sid, f'SHP-{sid:03d}', base_day, base_day + 2, plant_id, rdc_id,
                          'delivered', 'plant_to_rdc', leg1_freight, total_weight, 4000 + sid))
        ln = 0
        for sku_id, cases in sorted(sku_cases.items()):
            ln += 1
            w = round(sku_weights.get(sku_id, 6.0) * cases, 2)
            shipment_lines_all.append((sid, ln, sku_id, cases, w))

        # Leg 2: RDC → customer DC
        sid += 1
        leg2_freight = round(rates['rdc_to_customer_dc'] * total_cases, 2)
        shipments.append((sid, f'SHP-{sid:03d}', base_day + 3, base_day + 5, rdc_id, cust_dc_id,
                          'delivered', 'rdc_to_customer_dc', leg2_freight, total_weight, 4000 + sid))
        ln = 0
        for sku_id, cases in sorted(sku_cases.items()):
            ln += 1
            w = round(sku_weights.get(sku_id, 6.0) * cases, 2)
            shipment_lines_all.append((sid, ln, sku_id, cases, w))

        # Leg 3: customer DC → store
        sid += 1
        if channel == 'CONVENIENCE' and store_id in conv_last_mile:
            leg3_rate = conv_last_mile[store_id]
        else:
            leg3_rate = rates['customer_dc_to_store']
        leg3_freight = round(leg3_rate * total_cases, 2)
        shipments.append((sid, f'SHP-{sid:03d}', base_day + 6, base_day + 7, cust_dc_id, store_id,
                          'delivered', 'customer_dc_to_store', leg3_freight, total_weight, 4000 + sid))
        ln = 0
        for sku_id, cases in sorted(sku_cases.items()):
            ln += 1
            w = round(sku_weights.get(sku_id, 6.0) * cases, 2)
            shipment_lines_all.append((sid, ln, sku_id, cases, w))

    return shipments, shipment_lines_all, sid


def insert_shipments(conn):
    _, _, ol_data = _build_orders()
    shipments, _, _ = _build_shipments(ol_data)
    conn.executemany("INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?,?,?,?)", shipments)
    return len(shipments)


def insert_shipment_lines(conn):
    _, _, ol_data = _build_orders()
    _, shipment_lines, _ = _build_shipments(ol_data)
    conn.executemany("INSERT INTO shipment_lines VALUES (?,?,?,?,?)", shipment_lines)
    return len(shipment_lines)


def _build_ar_data(ol_data):
    """Build AR invoices, lines, and receipts with channel-specific economics."""
    import random
    random.seed(789)

    # SKU prices
    sku_prices = {1: 48.00, 2: 36.00, 3: 22.50, 4: 18.00, 5: 16.50, 6: 14.00, 7: 28.00, 8: 19.50}
    # Trade spend multipliers (fraction of list retained)
    trade_mult = {'CLUB': 0.88, 'GROCERY': 0.75, 'CONVENIENCE': 0.85}
    # Payment terms (days after invoice)
    terms = {'CLUB': 15, 'GROCERY': 30, 'CONVENIENCE': 60}

    # Get final-leg shipment IDs per (channel, store)
    # Final-leg shipments are customer_dc_to_store, sid = 3rd of each triple
    # We'll build mapping from ol_data order
    from collections import defaultdict
    channel_store_orders = defaultdict(list)
    for oid, channel, loc, lines in ol_data:
        channel_store_orders[(channel, loc)].append(oid)

    # Each (channel, store) gets one 3-leg shipment chain. Final leg sid = 3 * index.
    store_final_shipment = {}
    idx = 0
    for (channel, store_id) in channel_store_orders:
        idx += 1
        store_final_shipment[(channel, store_id)] = idx * 3  # 3rd shipment in triple

    invoices = []
    invoice_lines = []
    receipts = []

    inv_id = 0
    rcpt_id = 0

    for oid, channel, loc, lines in ol_data:
        inv_id += 1
        # Get order day
        order_day = 30 + 7  # approx: shipment base_day + 7 (delivery)
        inv_day = order_day + random.randint(0, 3)
        due_day = inv_day + terms[channel]
        mult = trade_mult[channel]
        final_ship_id = store_final_shipment.get((channel, loc))

        total_amount = 0
        for ln_num, (sku_id, cases) in enumerate(lines, 1):
            unit_price = round(sku_prices[sku_id] * mult, 4)
            line_amount = round(unit_price * cases, 4)
            total_amount += line_amount
            invoice_lines.append((inv_id, ln_num, sku_id, cases, unit_price, line_amount))

        invoices.append((inv_id, 8000 + inv_id, f'ARI-{inv_id:03d}', loc, final_ship_id,
                         inv_day, due_day, round(total_amount, 4), 'USD', channel, 'paid'))

        # AR Receipt
        if random.random() < 0.92:  # 92% get paid (some convenience don't)
            rcpt_id += 1
            if channel == 'CLUB':
                pay_day = due_day + random.randint(-2, 0)
            elif channel == 'GROCERY':
                pay_day = due_day + random.randint(0, 8)
            else:  # CONVENIENCE
                pay_day = due_day + random.randint(5, 15)
            receipts.append((rcpt_id, 9500 + rcpt_id, inv_id, pay_day,
                             round(total_amount, 4), 'completed'))

    return invoices, invoice_lines, receipts


def insert_ar_invoices(conn):
    _, _, ol_data = _build_orders()
    invoices, _, _ = _build_ar_data(ol_data)
    conn.executemany("INSERT INTO ar_invoices VALUES (?,?,?,?,?,?,?,?,?,?,?)", invoices)
    return len(invoices)


def insert_ar_invoice_lines(conn):
    _, _, ol_data = _build_orders()
    _, invoice_lines, _ = _build_ar_data(ol_data)
    conn.executemany("INSERT INTO ar_invoice_lines VALUES (?,?,?,?,?,?)", invoice_lines)
    return len(invoice_lines)


def insert_ar_receipts(conn):
    _, _, ol_data = _build_orders()
    _, _, receipts = _build_ar_data(ol_data)
    conn.executemany("INSERT INTO ar_receipts VALUES (?,?,?,?,?,?)", receipts)
    return len(receipts)


# ---------------------------------------------------------------------------
# Trade Management
# ---------------------------------------------------------------------------

def insert_trade_programs(conn):
    """10 trade programs decomposing channel trade multipliers.

    Club (12% total): scan 4%, rebate 5%, off-invoice 3%
    Grocery (25% total): scan 5%, rebate 8%, promo_fund 7%, slotting 5%
    Convenience (15% total): scan 5%, rebate 6%, off-invoice 4%
    """
    rows = [
        # Club programs (channel_id=1, total=12%)
        (1, 'TP-CLUB-SCAN',   'Club Scan Allowance',     1, 'scan_allowance', 0.04,  1, 365, True),
        (2, 'TP-CLUB-REBATE', 'Club Volume Rebate',      1, 'volume_rebate',  0.05,  1, 365, True),
        (3, 'TP-CLUB-OI',     'Club Off-Invoice',        1, 'off_invoice',    0.03,  1, 365, True),
        # Grocery programs (channel_id=2, total=25%)
        (4, 'TP-GROC-SCAN',   'Grocery Scan Allowance',  2, 'scan_allowance', 0.05,  1, 365, True),
        (5, 'TP-GROC-REBATE', 'Grocery Volume Rebate',   2, 'volume_rebate',  0.08,  1, 365, True),
        (6, 'TP-GROC-PROMO',  'Grocery Promo Fund',      2, 'promo_fund',     0.07,  1, 365, True),
        (7, 'TP-GROC-SLOT',   'Grocery Slotting Fees',   2, 'slotting',       0.05,  1, 365, True),
        # Convenience programs (channel_id=3, total=15%)
        (8, 'TP-CONV-SCAN',   'Conv Scan Allowance',     3, 'scan_allowance', 0.05,  1, 365, True),
        (9, 'TP-CONV-REBATE', 'Conv Volume Rebate',      3, 'volume_rebate',  0.06,  1, 365, True),
        (10,'TP-CONV-OI',     'Conv Off-Invoice',        3, 'off_invoice',    0.04,  1, 365, True),
    ]
    conn.executemany("INSERT INTO trade_programs VALUES (?,?,?,?,?,?,?,?,?)", rows)


def insert_promo_events(conn):
    """~8 promo events tied to promo_fund programs (Grocery channel only has promo_fund)."""
    rows = [
        # Grocery promo_fund events (program_id=6)
        (1, 'PE-GROC-BOGO-W5',   'Grocery BOGO Week 5-6',           6, 'bogo',    1, 30, 44, 0.30, 500.00,  'completed'),
        (2, 'PE-GROC-TPR-W7',    'Grocery TPR Week 7-8',            6, 'tpr',     3, 44, 58, 0.20, 300.00,  'completed'),
        (3, 'PE-GROC-DISP-W9',   'Grocery Display Week 9-10',       6, 'display', 1, 58, 72, 0.25, 400.00,  'completed'),
        (4, 'PE-GROC-FEAT-W4',   'Grocery Feature Ad Week 4-5',     6, 'feature', 5, 22, 36, 0.15, 250.00,  'active'),
        (5, 'PE-GROC-BOGO-W11',  'Grocery BOGO Week 11-12',         6, 'bogo',    1, 72, 86, 0.30, 500.00,  'planned'),
        # Club feature events (Club has no promo_fund, but we still create events under Grocery promo_fund for cross-channel visibility)
        # Actually, let's keep all promo events under promo_fund programs only
        (6, 'PE-GROC-TPR-W3',    'Grocery TPR Week 3-4',            6, 'tpr',     4, 15, 29, 0.18, 200.00,  'completed'),
        (7, 'PE-GROC-DISP-W6',   'Grocery Display Week 6-7',        6, 'display', 8, 37, 51, 0.20, 350.00,  'completed'),
        (8, 'PE-GROC-FEAT-W10',  'Grocery Feature Ad Week 10-11',   6, 'feature', 3, 65, 79, 0.15, 275.00,  'active'),
    ]
    conn.executemany("INSERT INTO promo_events VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)


def insert_trade_deductions(conn):
    """Generate trade deductions from AR invoice lines × channel programs.

    For each AR invoice line, look up channel → programs → compute deduction.
    Promo_fund deductions within promo event windows get linked to the event.
    Invariant: SUM(deductions per invoice) = gross_revenue - net_revenue.
    """
    # SKU list prices
    sku_prices = {1: 48.00, 2: 36.00, 3: 22.50, 4: 18.00, 5: 16.50, 6: 14.00, 7: 28.00, 8: 19.50}

    # Channel name → channel_id mapping
    channel_ids = {'CLUB': 1, 'GROCERY': 2, 'CONVENIENCE': 3}

    # Load trade programs grouped by channel_id
    programs_by_channel = {}
    for row in conn.execute("SELECT id, channel_id, program_type, rate_pct FROM trade_programs").fetchall():
        cid = row[1]
        if cid not in programs_by_channel:
            programs_by_channel[cid] = []
        programs_by_channel[cid].append({'id': row[0], 'type': row[2], 'rate': float(row[3])})

    # Load promo events for matching
    promo_events = conn.execute(
        "SELECT id, sku_id, start_day, end_day FROM promo_events"
    ).fetchall()

    # Load AR invoices (need channel and invoice_date)
    invoices = {}
    for row in conn.execute("SELECT id, channel, invoice_date FROM ar_invoices").fetchall():
        invoices[row[0]] = {'channel': row[1], 'day': row[2]}

    # Load AR invoice lines
    inv_lines = conn.execute(
        "SELECT invoice_id, line_number, sku_id, quantity_cases FROM ar_invoice_lines"
    ).fetchall()

    td_id = 0
    td_rows = []

    for inv_id, line_num, sku_id, qty_cases in inv_lines:
        inv_info = invoices[inv_id]
        channel_name = inv_info['channel']
        inv_day = inv_info['day']
        channel_id = channel_ids[channel_name]
        list_price = sku_prices.get(sku_id, 20.00)
        qty = float(qty_cases)

        for prog in programs_by_channel.get(channel_id, []):
            td_id += 1
            deduction = round(list_price * qty * prog['rate'], 4)

            # Check for promo_event linkage (only for promo_fund type)
            promo_event_id = None
            if prog['type'] == 'promo_fund':
                for pe_id, pe_sku, pe_start, pe_end in promo_events:
                    if pe_sku == sku_id and pe_start <= inv_day <= pe_end:
                        promo_event_id = pe_id
                        break

            td_rows.append((td_id, prog['id'], promo_event_id, inv_id, line_num,
                            sku_id, list_price, qty, deduction))

    conn.executemany("INSERT INTO trade_deductions VALUES (?,?,?,?,?,?,?,?,?)", td_rows)
    return len(td_rows)


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------

def insert_returns(conn):
    rows = [
        # id, return_number, return_date, source_id (channel), dc_id, status, txn_seq
        # Club: 1 return
        (1, 'RET-001', 55, 1, 3, 'received', 6001),
        # Grocery: 3 returns
        (2, 'RET-002', 50, 2, 4, 'received', 6002),
        (3, 'RET-003', 60, 2, 4, 'received', 6003),
        (4, 'RET-004', 70, 2, 6, 'received', 6004),
        # Convenience: 6 returns
        (5, 'RET-005', 52, 3, 5, 'received', 6005),
        (6, 'RET-006', 58, 3, 5, 'received', 6006),
        (7, 'RET-007', 63, 3, 5, 'received', 6007),
        (8, 'RET-008', 68, 3, 5, 'received', 6008),
        (9, 'RET-009', 75, 3, 5, 'received', 6009),
        (10,'RET-010', 80, 3, 5, 'received', 6010),
    ]
    conn.executemany("INSERT INTO returns VALUES (?,?,?,?,?,?,?)", rows)


def insert_return_lines(conn):
    rows = [
        # return_id, line, sku_id, qty_cases, condition
        (1, 1, 1, 3, 'sellable'),          # Club — tiny, sellable
        (2, 1, 3, 5, 'sellable'),          # Grocery
        (3, 1, 1, 4, 'damaged'),           # Grocery
        (4, 1, 5, 3, 'expired'),           # Grocery
        (5, 1, 1, 2, 'damaged'),           # Convenience
        (5, 2, 5, 3, 'expired'),
        (6, 1, 2, 2, 'damaged'),
        (7, 1, 6, 3, 'expired'),
        (8, 1, 1, 2, 'damaged'),
        (8, 2, 5, 2, 'expired'),
        (9, 1, 1, 3, 'damaged'),
        (9, 2, 6, 2, 'expired'),
        (10,1, 2, 2, 'damaged'),
        (10,2, 5, 3, 'expired'),
        (10,3, 1, 1, 'damaged'),
    ]
    conn.executemany("INSERT INTO return_lines VALUES (?,?,?,?,?)", rows)


def insert_disposition_logs(conn):
    rows = [
        # return_id, return_line_number, disposition, qty_cases
        (1, 1, 'restock',  3),
        (2, 1, 'restock',  5),
        (3, 1, 'destroy',  4),
        (4, 1, 'destroy',  3),
        (5, 1, 'destroy',  2),
        (5, 2, 'destroy',  3),
        (6, 1, 'discount', 2),
        (7, 1, 'destroy',  3),
        (8, 1, 'destroy',  2),
        (8, 2, 'destroy',  2),
        (9, 1, 'destroy',  3),
        (9, 2, 'destroy',  2),
        (10,1, 'discount', 2),
        (10,2, 'destroy',  3),
        (10,3, 'destroy',  1),
    ]
    conn.executemany("INSERT INTO disposition_logs VALUES (?,?,?,?)", rows)


# ---------------------------------------------------------------------------
# GL Journal
# ---------------------------------------------------------------------------

def insert_gl_journal(conn):
    entries = []
    _gl_id[0] = 0  # reset

    # Production entries: DR WIP (1300) / CR RM Inventory (1200)
    batches = conn.execute(
        "SELECT id, transaction_sequence_id, production_date, quantity_kg, product_type FROM batches"
    ).fetchall()
    for bid, txn, day, qty, ptype in batches:
        # Approximate material cost: $5/kg for premix, $3/kg for bulk, $8/kg for FG
        cost_rates = {'premix': 5.0, 'bulk_intermediate': 3.0, 'finished_good': 8.0}
        rate = cost_rates.get(ptype, 5.0)
        amount = round(float(qty) * rate, 2)
        gl_pair(entries, txn, day, '1300', '1200', amount, 'batch', bid,
                f'Production batch B-{bid:03d}')

    # Completion: DR FG Inventory (1400) / CR WIP (1300)
    for bid, txn, day, qty, ptype in batches:
        if ptype == 'finished_good':
            cost_rates = {'finished_good': 8.0}
            amount = round(float(qty) * cost_rates.get(ptype, 8.0), 2)
            gl_pair(entries, txn, day, '1400', '1300', amount, 'batch', bid,
                    f'Completion batch B-{bid:03d}')

    # Shipment: DR In-Transit (1500) / CR FG Inventory (1400) — leg 1 only
    shipments = conn.execute(
        "SELECT id, transaction_sequence_id, ship_date, freight_cost, route_type FROM shipments WHERE route_type = 'plant_to_rdc'"
    ).fetchall()
    for sid, txn, day, freight, rtype in shipments:
        # Value of goods ~= freight * 20 (rough proxy)
        goods_value = round(float(freight) * 20, 2)
        gl_pair(entries, txn, day, '1500', '1400', goods_value, 'shipment', sid,
                f'Ship to RDC SHP-{sid:03d}')

    # Freight expense: DR Freight (5100) / CR Cash (1000)
    all_shipments = conn.execute(
        "SELECT id, transaction_sequence_id, ship_date, freight_cost FROM shipments"
    ).fetchall()
    for sid, txn, day, freight in all_shipments:
        if freight and float(freight) > 0:
            gl_pair(entries, txn, day, '5100', '1000', float(freight), 'shipment', sid,
                    f'Freight SHP-{sid:03d}')

    # Revenue: DR AR (1100) / CR Revenue (4000)
    ar_invs = conn.execute(
        "SELECT id, transaction_sequence_id, invoice_date, total_amount FROM ar_invoices"
    ).fetchall()
    for aid, txn, day, amount in ar_invs:
        gl_pair(entries, txn, day, '1100', '4000', float(amount), 'ar_invoice', aid,
                f'Revenue ARI-{aid:03d}')

    # Trade spend: DR Trade Spend (5200) / CR Revenue (4000) — per AR invoice
    # Books the gross-to-net gap as contra-revenue
    trade_totals = conn.execute(
        "SELECT ar_invoice_id, SUM(deduction_amount) FROM trade_deductions GROUP BY ar_invoice_id"
    ).fetchall()
    for aid, trade_total in trade_totals:
        # Look up the AR invoice's txn_seq and date
        inv_info = conn.execute(
            "SELECT transaction_sequence_id, invoice_date FROM ar_invoices WHERE id = ?", [aid]
        ).fetchone()
        if inv_info:
            gl_pair(entries, inv_info[0], inv_info[1], '5200', '4000', float(trade_total),
                    'trade_deduction', aid, f'Trade spend ARI-{aid:03d}')

    # COGS: DR COGS (5000) / CR In-Transit (1500) — on delivery
    # Use leg 3 shipments as delivery trigger
    leg3 = conn.execute(
        "SELECT s.id, ANY_VALUE(s.transaction_sequence_id), ANY_VALUE(s.arrival_date), SUM(sl.quantity_cases) "
        "FROM shipments s JOIN shipment_lines sl ON s.id = sl.shipment_id "
        "WHERE s.route_type = 'customer_dc_to_store' GROUP BY s.id"
    ).fetchall()
    sku_costs = {1: 18.00, 2: 14.20, 3: 8.60, 4: 7.80, 5: 7.90, 6: 7.50, 7: 11.00, 8: 8.20}
    for sid, txn, day, total_cases in leg3:
        # Get SKU breakdown for this shipment
        slines = conn.execute(
            "SELECT sku_id, quantity_cases FROM shipment_lines WHERE shipment_id = ?", [sid]
        ).fetchall()
        cogs_amount = sum(sku_costs.get(sk, 10.0) * float(c) for sk, c in slines)
        gl_pair(entries, txn, day, '5000', '1500', round(cogs_amount, 2), 'shipment', sid,
                f'COGS delivery SHP-{sid:03d}')

    # AP payment: DR AP (2000) / CR Cash (1000)
    ap_pays = conn.execute(
        "SELECT id, transaction_sequence_id, payment_date, net_amount FROM ap_payments"
    ).fetchall()
    for pid, txn, day, amount in ap_pays:
        gl_pair(entries, txn, day, '2000', '1000', float(amount), 'ap_payment', pid,
                f'AP payment {pid}')

    # AR receipt: DR Cash (1000) / CR AR (1100)
    ar_rcpts = conn.execute(
        "SELECT id, transaction_sequence_id, receipt_date, amount FROM ar_receipts"
    ).fetchall()
    for rid, txn, day, amount in ar_rcpts:
        gl_pair(entries, txn, day, '1000', '1100', float(amount), 'ar_receipt', rid,
                f'AR receipt {rid}')

    conn.executemany(
        "INSERT INTO gl_journal VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", entries
    )
    return len(entries)


# ---------------------------------------------------------------------------
# Inventory snapshots
# ---------------------------------------------------------------------------

def insert_inventory(conn):
    """Weekly snapshots for key SKU/location combos."""
    rows = []
    inv_id = 0
    snapshot_days = [7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84, 90]

    # Key locations: plants (1-3), RDCs (1-2), customer DCs (3-6), stores (1-8)
    locations = [
        ('plant', 1), ('plant', 2), ('plant', 3),
        ('rdc', 1), ('rdc', 2),
        ('customer_dc', 3), ('customer_dc', 5),
        ('store', 1), ('store', 5),
    ]
    skus = [1, 3, 5]  # Hero + HC + PW

    import random
    random.seed(999)

    for day in snapshot_days:
        for loc_type, loc_id in locations:
            for sku_id in skus:
                inv_id += 1
                # Rough inventory levels
                if loc_type == 'plant':
                    qty = random.randint(50, 200)
                elif loc_type == 'rdc':
                    qty = random.randint(100, 400)
                elif loc_type == 'customer_dc':
                    qty = random.randint(20, 100)
                else:  # store
                    qty = random.randint(5, 30)
                rows.append((inv_id, day, loc_type, loc_id, sku_id, qty))

    conn.executemany("INSERT INTO inventory VALUES (?,?,?,?,?,?)", rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Demand Forecasts
# ---------------------------------------------------------------------------

def insert_demand_forecasts(conn):
    rows = []
    fid = 0
    skus = [1, 2, 3, 5, 7, 8]
    periods = [15, 30, 45, 60, 75]  # 5 bi-weekly periods

    import random
    random.seed(321)

    for sku_id in skus:
        for period in periods:
            fid += 1
            # Base forecast roughly matches actual order volumes
            if sku_id in (1, 3):
                base = random.randint(80, 150)
            elif sku_id in (5, 8):
                base = random.randint(30, 60)
            else:
                base = random.randint(40, 80)
            rows.append((fid, 'Q1-2025-STAT', sku_id, 'rdc', period, base, 'statistical'))

    conn.executemany("INSERT INTO demand_forecasts VALUES (?,?,?,?,?,?,?)", rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(conn):
    """Run 7 CTS validation queries and print formatted results."""
    print("\n" + "=" * 70)
    print("VERIFICATION QUERIES")
    print("=" * 70)

    # 1. Margin by Channel (hero SKU) — with all-leg freight allocation
    print("\n--- 1. MARGIN BY CHANNEL (Hero SKU: BrightSmile Premium) ---")
    result = conn.execute("""
        WITH channel_revenue AS (
            SELECT
                ai.channel,
                SUM(ail.line_amount) AS net_revenue,
                SUM(ail.quantity_cases) AS total_cases
            FROM ar_invoices ai
            JOIN ar_invoice_lines ail ON ai.id = ail.invoice_id
            WHERE ail.sku_id = 1
            GROUP BY ai.channel
        ),
        -- Shipments come in groups of 3 (leg1, leg2, leg3) per channel/store.
        -- Attribute all 3 legs to the channel via the leg3 destination.
        -- Shipment IDs: groups of 3 where id%3==0 is leg3 (customer_dc_to_store).
        shipment_with_cases AS (
            SELECT s.id, s.freight_cost,
                   SUM(sl.quantity_cases) AS total_cases
            FROM shipments s
            JOIN shipment_lines sl ON s.id = sl.shipment_id
            GROUP BY s.id, s.freight_cost
        ),
        -- Map each group-of-3 to a channel via leg3
        leg3_channel AS (
            SELECT s.id AS leg3_id, rl.channel,
                   swc.total_cases
            FROM shipments s
            JOIN retail_locations rl ON s.destination_id = rl.id
            JOIN shipment_with_cases swc ON s.id = swc.id
            WHERE s.route_type = 'customer_dc_to_store'
        ),
        all_leg_freight AS (
            -- For each leg3 shipment, sum freight of it + its 2 preceding legs
            SELECT
                lc.channel,
                (SELECT SUM(swc2.freight_cost)
                 FROM shipment_with_cases swc2
                 WHERE swc2.id BETWEEN lc.leg3_id - 2 AND lc.leg3_id) AS chain_freight,
                lc.total_cases
            FROM leg3_channel lc
        ),
        channel_freight AS (
            SELECT channel,
                   SUM(chain_freight) AS total_freight,
                   SUM(total_cases) AS total_cases
            FROM all_leg_freight
            GROUP BY channel
        )
        SELECT
            cr.channel,
            cr.total_cases,
            ROUND(cr.net_revenue / cr.total_cases, 2) AS net_rev_per_case,
            18.00 AS cogs_per_case,
            ROUND(cf.total_freight / cf.total_cases, 2) AS freight_per_case,
            ROUND(cr.net_revenue / cr.total_cases - 18.00 - cf.total_freight / cf.total_cases, 2) AS margin_per_case,
            ROUND((cr.net_revenue / cr.total_cases - 18.00 - cf.total_freight / cf.total_cases)
                  / (cr.net_revenue / cr.total_cases) * 100, 1) AS margin_pct
        FROM channel_revenue cr
        JOIN channel_freight cf ON cr.channel = cf.channel
        ORDER BY margin_pct DESC
    """).fetchall()
    print(f"  {'Channel':<15} {'Cases':>8} {'NetRev':>10} {'COGS':>8} {'Freight':>8} {'Margin':>8} {'Margin%':>8}")
    for row in result:
        print(f"  {row[0]:<15} {row[1]:>8} {row[2]:>10.2f} {row[3]:>8.2f} {row[4]:>8.2f} {row[5]:>8.2f} {row[6]:>7.1f}%")

    # 2. Margin by Category (through Grocery)
    print("\n--- 2. MARGIN BY CATEGORY (Through Grocery) ---")
    result = conn.execute("""
        SELECT
            s.category,
            SUM(ail.quantity_cases) AS cases,
            ROUND(SUM(ail.line_amount) / SUM(ail.quantity_cases), 2) AS net_rev_per_case,
            ROUND(AVG(s.cost_per_case), 2) AS cogs_per_case,
            ROUND(SUM(ail.line_amount) / SUM(ail.quantity_cases) - AVG(s.cost_per_case), 2) AS margin_per_case,
            ROUND((SUM(ail.line_amount) / SUM(ail.quantity_cases) - AVG(s.cost_per_case))
                  / (SUM(ail.line_amount) / SUM(ail.quantity_cases)) * 100, 1) AS margin_pct
        FROM ar_invoices ai
        JOIN ar_invoice_lines ail ON ai.id = ail.invoice_id
        JOIN skus s ON ail.sku_id = s.id
        WHERE ai.channel = 'GROCERY'
        GROUP BY s.category
        ORDER BY s.category
    """).fetchall()
    print(f"  {'Category':<18} {'Cases':>8} {'NetRev/case':>12} {'COGS/case':>10} {'Margin/case':>12} {'Margin%':>8}")
    for row in result:
        print(f"  {row[0]:<18} {row[1]:>8} {row[2]:>12.2f} {row[3]:>10.2f} {row[4]:>12.2f} {row[5]:>7.1f}%")

    # 3. Margin by Store Location (Convenience stores)
    print("\n--- 3. FREIGHT BY STORE (Convenience Channel) ---")
    result = conn.execute("""
        WITH leg3 AS (
            SELECT s.id, s.freight_cost, s.destination_id,
                   SUM(sl.quantity_cases) AS total_cases
            FROM shipments s
            JOIN shipment_lines sl ON s.id = sl.shipment_id
            WHERE s.route_type = 'customer_dc_to_store'
            GROUP BY s.id, s.freight_cost, s.destination_id
        )
        SELECT
            rl.name,
            SUM(l.freight_cost) AS total_freight,
            SUM(l.total_cases) AS total_cases,
            ROUND(SUM(l.freight_cost) / SUM(l.total_cases), 2) AS freight_per_case
        FROM leg3 l
        JOIN retail_locations rl ON l.destination_id = rl.id
        WHERE rl.channel = 'CONVENIENCE'
        GROUP BY rl.name
        ORDER BY freight_per_case DESC
    """).fetchall()
    print(f"  {'Store':<30} {'Freight$':>10} {'Cases':>8} {'$/case':>8}")
    for row in result:
        print(f"  {row[0]:<30} {row[1]:>10.2f} {row[2]:>8} {row[3]:>8.2f}")

    # 4. Yield Variance
    print("\n--- 4. YIELD VARIANCE (Citrus Premix Batches) ---")
    result = conn.execute("""
        SELECT
            batch_number,
            quantity_kg,
            yield_percent,
            CASE WHEN yield_percent < 90 THEN 'BAD' ELSE 'NORMAL' END AS status
        FROM batches
        WHERE formula_id = 2
        ORDER BY yield_percent
    """).fetchall()
    print(f"  {'Batch':<12} {'Qty (kg)':>10} {'Yield%':>8} {'Status':<8}")
    for row in result:
        print(f"  {row[0]:<12} {row[1]:>10.1f} {row[2]:>7.1f}% {row[3]:<8}")

    # 5. Supplier Price Creep
    print("\n--- 5. SUPPLIER PRICE CREEP (HDPE Bottles) ---")
    result = conn.execute("""
        SELECT
            'PO Price' AS source,
            AVG(pol.unit_cost) AS avg_price,
            SUM(pol.quantity_kg) AS total_qty
        FROM purchase_order_lines pol
        WHERE pol.ingredient_id = 11
        UNION ALL
        SELECT
            'AP Invoice Price',
            AVG(ail.unit_cost),
            SUM(ail.quantity_kg)
        FROM ap_invoice_lines ail
        WHERE ail.ingredient_id = 11
    """).fetchall()
    print(f"  {'Source':<20} {'Avg Price':>10} {'Total Qty':>12}")
    for row in result:
        print(f"  {row[0]:<20} ${row[1]:>9.4f} {row[2]:>12.0f}")

    # Total variance $
    var_total = conn.execute(
        "SELECT SUM(variance_amount) FROM invoice_variances WHERE variance_type = 'price'"
    ).fetchone()[0]
    print(f"  Total open variance: ${var_total:,.2f}")

    # 6. DSO by Channel
    print("\n--- 6. DSO BY CHANNEL ---")
    result = conn.execute("""
        SELECT
            ai.channel,
            ROUND(AVG(ar.receipt_date - ai.invoice_date), 1) AS avg_dso,
            COUNT(*) AS paid_invoices
        FROM ar_invoices ai
        JOIN ar_receipts ar ON ai.id = ar.invoice_id
        GROUP BY ai.channel
        ORDER BY avg_dso
    """).fetchall()
    print(f"  {'Channel':<15} {'Avg DSO':>8} {'Paid Invoices':>15}")
    for row in result:
        print(f"  {row[0]:<15} {row[1]:>7.1f}d {row[2]:>15}")

    # 7. Trade Spend Decomposition
    print("\n--- 7. TRADE SPEND DECOMPOSITION BY CHANNEL ---")
    result = conn.execute("""
        SELECT
            tp.name AS channel_name,
            tp2.program_type,
            tp2.rate_pct,
            SUM(td.deduction_amount) AS total_deductions,
            COUNT(*) AS deduction_count
        FROM trade_deductions td
        JOIN trade_programs tp2 ON td.trade_program_id = tp2.id
        JOIN channels tp ON tp2.channel_id = tp.id
        GROUP BY tp.name, tp2.program_type, tp2.rate_pct
        ORDER BY tp.name, tp2.program_type
    """).fetchall()
    print(f"  {'Channel':<15} {'Type':<18} {'Rate':>6} {'Total$':>12} {'Count':>6}")
    for row in result:
        print(f"  {row[0]:<15} {row[1]:<18} {float(row[2]):>5.1%} {float(row[3]):>12.2f} {row[4]:>6}")

    # Verify gross-to-net reconciliation
    print("\n  --- Gross-to-Net Reconciliation (per channel) ---")
    result = conn.execute("""
        WITH gross AS (
            SELECT ai.channel,
                   SUM(s.price_per_case * ail.quantity_cases) AS gross_revenue,
                   SUM(ail.line_amount) AS net_revenue
            FROM ar_invoices ai
            JOIN ar_invoice_lines ail ON ai.id = ail.invoice_id
            JOIN skus s ON ail.sku_id = s.id
            GROUP BY ai.channel
        ),
        deductions AS (
            SELECT ai.channel, SUM(td.deduction_amount) AS total_deductions
            FROM trade_deductions td
            JOIN ar_invoices ai ON td.ar_invoice_id = ai.id
            GROUP BY ai.channel
        )
        SELECT g.channel,
               ROUND(g.gross_revenue, 2) AS gross,
               ROUND(d.total_deductions, 2) AS deductions,
               ROUND(g.net_revenue, 2) AS net,
               ROUND(g.gross_revenue - d.total_deductions - g.net_revenue, 2) AS gap
        FROM gross g
        JOIN deductions d ON g.channel = d.channel
        ORDER BY g.channel
    """).fetchall()
    print(f"  {'Channel':<15} {'Gross':>12} {'Deductions':>12} {'Net':>12} {'Gap':>8}")
    for row in result:
        print(f"  {row[0]:<15} {float(row[1]):>12.2f} {float(row[2]):>12.2f} {float(row[3]):>12.2f} {float(row[4]):>8.2f}")

    print("\n" + "=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def insert_all(conn):
    """Insert all data in FK-dependency order."""
    # Master data
    insert_suppliers(conn)
    insert_ingredients(conn)
    insert_supplier_ingredients(conn)
    insert_plants(conn)
    insert_production_lines(conn)
    insert_channels(conn)
    insert_chart_of_accounts(conn)
    insert_bulk_intermediates(conn)
    insert_formulas(conn)
    insert_formula_ingredients(conn)
    insert_skus(conn)
    insert_distribution_centers(conn)
    insert_retail_locations(conn)
    insert_route_segments(conn)

    # Procurement
    insert_purchase_orders(conn)
    insert_purchase_order_lines(conn)
    insert_goods_receipts(conn)
    insert_goods_receipt_lines(conn)
    insert_ap_invoices(conn)
    insert_ap_invoice_lines(conn)
    insert_ap_payments(conn)
    insert_invoice_variances(conn)

    # Manufacturing
    insert_work_orders(conn)
    insert_batches(conn)
    insert_batch_ingredients(conn)

    # Demand & Fulfillment
    insert_orders(conn)
    insert_order_lines(conn)
    insert_shipments(conn)
    insert_shipment_lines(conn)
    insert_ar_invoices(conn)
    insert_ar_invoice_lines(conn)
    insert_ar_receipts(conn)

    # Trade Management
    insert_trade_programs(conn)
    insert_promo_events(conn)
    insert_trade_deductions(conn)

    # Returns
    insert_returns(conn)
    insert_return_lines(conn)
    insert_disposition_logs(conn)

    # GL & Analytics
    insert_gl_journal(conn)
    insert_inventory(conn)
    insert_demand_forecasts(conn)


def print_summary(conn):
    """Print row counts for all tables."""
    print("\n--- ROW COUNTS ---")
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    total = 0
    for (table,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        total += count
        if count > 0:
            print(f"  {table:<25} {count:>6}")
    print(f"  {'TOTAL':<25} {total:>6}")


def main():
    parser = argparse.ArgumentParser(description="Generate CTS demo DuckDB")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output path")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="DDL schema path")
    args = parser.parse_args()

    output = args.output
    schema = args.schema

    if not schema.exists():
        print(f"ERROR: Schema file not found: {schema}")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    print(f"Generating demo DB: {output}")
    conn = duckdb.connect(str(output))
    try:
        conn.execute(schema.read_text())
        insert_all(conn)
        print_summary(conn)
        verify(conn)
    finally:
        conn.close()

    print(f"\nDone: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
