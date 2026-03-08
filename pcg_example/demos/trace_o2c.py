#!/usr/bin/env python3
"""
Order-to-Cash (O2C) Trace Demo
===============================

Traces a single customer order through the full O2C cycle, following the
ontology relationships declared in pcg.yaml:

  Order -> OrderLines -> Shipment -> ShipmentLines -> ARInvoice ->
  ARInvoiceLines -> ARReceipt -> GLJournal

Demonstrates:
  - Document chain traversal via direct_join relationships
  - Polymorphic source_id resolution (Channel vs RetailLocation)
  - State machine progression (Order: delivered, Shipment: delivered, ARInvoice: open)
  - Revenue source of truth (ar_invoice_lines, NOT order_lines)
  - GL double-entry bookkeeping trail with full account resolution
  - Conservation: order cases = shipment cases = invoice cases

Usage:
  poetry run python pcg_example/demos/trace_o2c.py [--order-id ID]
"""

import argparse
import sys

import psycopg


CONN_STR = "postgresql://postgres:postgres@localhost:5432/erp_db"


def trace_order(conn, order_id=None):
    """Trace a single order through the full O2C chain."""
    with conn.cursor() as cur:
        # Step 1: Find or load the order
        if order_id:
            cur.execute(
                "SELECT id, order_number, status, day, total_cases, "
                "source_id, retail_location_id, transaction_sequence_id "
                "FROM orders WHERE id = %s",
                (order_id,),
            )
        else:
            cur.execute(
                "SELECT id, order_number, status, day, total_cases, "
                "source_id, retail_location_id, transaction_sequence_id "
                "FROM orders "
                "WHERE status = 'delivered' AND source_id <= 7 AND total_cases < 500 "
                "LIMIT 1"
            )
        order = cur.fetchone()
        if not order:
            print("No matching order found.")
            return
        order_id = order[0]

        print("=" * 72)
        print("ORDER-TO-CASH TRACE")
        print("Following ontology relationships: Order -> Shipment -> Invoice -> Cash")
        print("=" * 72)

        # --- ORDER ---
        print(f"\n{'─' * 72}")
        print("STEP 1: ORDER  (orders table)")
        print(f"  Ontology class: Order  |  Relationship: OrderFromChannel, OrderForRetailLocation")
        print(f"{'─' * 72}")
        print(f"  order_number:   {order[1]}")
        print(f"  status:         {order[2]}")
        print(f"  day:            {order[3]}")
        print(f"  total_cases:    {order[4]}")

        # Resolve polymorphic source_id (OrderFromChannel)
        source_id = order[5]
        if source_id and source_id <= 7:
            cur.execute("SELECT channel_code FROM channels WHERE id = %s", (source_id,))
            ch = cur.fetchone()
            print(f"  source:         channel {ch[0]} (source_id={source_id} <= 7 -> channels table)")
        else:
            print(f"  source:         retail_location (source_id={source_id} >= 67 -> retail_locations table)")

        # Resolve delivery location (OrderForRetailLocation)
        cur.execute(
            "SELECT location_code, store_format, channel FROM retail_locations WHERE id = %s",
            (order[6],),
        )
        rl = cur.fetchone()
        print(f"  deliver_to:     {rl[0]} ({rl[1]}, channel={rl[2]})")

        # --- ORDER LINES ---
        cur.execute(
            "SELECT ol.line_number, s.sku_code, s.name, ol.quantity_cases, ol.unit_price "
            "FROM order_lines ol JOIN skus s ON s.id = ol.sku_id "
            "WHERE ol.order_id = %s ORDER BY ol.line_number",
            (order_id,),
        )
        olines = cur.fetchall()
        order_cases = sum(l[3] for l in olines)

        print(f"\n{'─' * 72}")
        print(f"STEP 2: ORDER LINES  ({len(olines)} lines in order_lines table)")
        print(f"  Ontology: OrderHasLines (order_lines.order_id -> orders.id)")
        print(f"  Flow config: material flow, conservation_group=order_to_cash")
        print(f"{'─' * 72}")
        for l in olines[:5]:
            print(f"  line {l[0]:2d}: {l[1]:20s} {l[2][:30]:30s} qty={l[3]:5.0f} @ ${l[4]:.2f}")
        if len(olines) > 5:
            print(f"  ... and {len(olines) - 5} more lines")
        print(f"  TOTAL: {order_cases:,.0f} cases")

        # --- Find AR Invoice (linked via shipment, not directly from order) ---
        cur.execute(
            "SELECT ai.id, ai.invoice_number, ai.status, ai.invoice_date, ai.due_date, "
            "ai.total_amount, ai.channel, ai.shipment_id, ai.transaction_sequence_id "
            "FROM ar_invoices ai "
            "WHERE ai.customer_location_id = %s AND ai.invoice_date >= %s "
            "ORDER BY ai.invoice_date LIMIT 1",
            (order[6], order[3]),
        )
        inv = cur.fetchone()
        if not inv:
            print("\n  (No matching AR invoice found for this order)")
            return
        inv_id, ship_id = inv[0], inv[7]

        # --- SHIPMENT ---
        cur.execute(
            "SELECT shipment_number, status, ship_date, arrival_date, "
            "route_type, freight_cost, origin_id, destination_id "
            "FROM shipments WHERE id = %s",
            (ship_id,),
        )
        sh = cur.fetchone()

        print(f"\n{'─' * 72}")
        print(f"STEP 3: SHIPMENT  (shipments table)")
        print(f"  Ontology: ARInvoiceForShipment (ar_invoices.shipment_id -> shipments.id)")
        print(f"  NOTE: No direct Order->Shipment FK — linked via invoice, like real ERPs")
        print(f"{'─' * 72}")
        print(f"  shipment_number: {sh[0]}")
        print(f"  status:          {sh[1]}")
        print(f"  ship_date:       day {sh[2]} -> arrival: day {sh[3]}")
        print(f"  route_type:      {sh[4]}")
        print(f"  freight_cost:    ${sh[5]:,.2f}")

        # Shipment lines
        cur.execute(
            "SELECT sl.line_number, s.sku_code, sl.quantity_cases, sl.weight_kg "
            "FROM shipment_lines sl JOIN skus s ON s.id = sl.sku_id "
            "WHERE sl.shipment_id = %s ORDER BY sl.line_number",
            (ship_id,),
        )
        slines = cur.fetchall()
        ship_cases = sum(l[2] for l in slines)
        ship_weight = sum(l[3] for l in slines)

        print(f"\n  SHIPMENT LINES ({len(slines)} lines):")
        for l in slines[:5]:
            print(f"    line {l[0]:2d}: {l[1]:20s} qty={l[2]:5.0f} cases, {l[3]:8.1f} kg")
        if len(slines) > 5:
            print(f"    ... and {len(slines) - 5} more lines")
        print(f"    TOTAL: {ship_cases:,.0f} cases, {ship_weight:,.1f} kg")

        # --- AR INVOICE ---
        print(f"\n{'─' * 72}")
        print(f"STEP 4: AR INVOICE  (ar_invoices table)")
        print(f"  Ontology: ARInvoiceForCustomer, ARInvoiceHasLines")
        print(f"  State machine: open -> partial -> paid | open -> disputed -> bad_debt")
        print(f"{'─' * 72}")
        print(f"  invoice_number:  {inv[1]}")
        print(f"  status:          {inv[2]}")
        print(f"  invoice_date:    day {inv[3]}")
        print(f"  due_date:        day {inv[4]}")
        print(f"  total_amount:    ${inv[5]:,.2f}")
        print(f"  channel:         {inv[6]}")

        # AR invoice lines (revenue source of truth)
        cur.execute(
            "SELECT ail.line_number, s.sku_code, ail.quantity_cases, ail.line_amount "
            "FROM ar_invoice_lines ail JOIN skus s ON s.id = ail.sku_id "
            "WHERE ail.invoice_id = %s ORDER BY ail.line_number",
            (inv_id,),
        )
        ailines = cur.fetchall()
        inv_cases = sum(l[2] for l in ailines)
        total_rev = sum(l[3] for l in ailines)

        print(f"\n  AR INVOICE LINES ({len(ailines)} lines — REVENUE SOURCE OF TRUTH):")
        for l in ailines[:5]:
            unit = l[3] / l[2] if l[2] else 0
            print(f"    line {l[0]:2d}: {l[1]:20s} qty={l[2]:5.0f} cases, ${l[3]:10,.2f} (${unit:.2f}/case)")
        if len(ailines) > 5:
            print(f"    ... and {len(ailines) - 5} more lines")
        print(f"    TOTAL: {inv_cases:,.0f} cases, ${total_rev:,.2f} revenue")

        # --- AR RECEIPT ---
        cur.execute(
            "SELECT id, receipt_date, amount FROM ar_receipts WHERE invoice_id = %s",
            (inv_id,),
        )
        rcpts = cur.fetchall()
        collected = sum(r[2] for r in rcpts)

        print(f"\n{'─' * 72}")
        print(f"STEP 5: AR RECEIPT  (ar_receipts table — cash collection)")
        print(f"  Ontology: ARReceiptForInvoice (ar_receipts.invoice_id -> ar_invoices.id)")
        print(f"  Flow config: financial flow, conservation_group=order_to_cash")
        print(f"{'─' * 72}")
        if rcpts:
            for r in rcpts:
                print(f"  receipt_date: day {r[1]}, amount: ${r[2]:,.2f}")
            print(f"  Collection rate: {collected / inv[5] * 100:.1f}%")
        else:
            print(f"  (no receipt yet — invoice still outstanding)")

        # --- GL JOURNAL ---
        print(f"\n{'─' * 72}")
        print(f"STEP 6: GL JOURNAL  (double-entry bookkeeping trail)")
        print(f"  Ontology: GLJournalToAccount (gl_journal.account_code -> chart_of_accounts)")
        print(f"  Traced via reference_id = shipment_number and invoice_number")
        print(f"{'─' * 72}")

        # Shipment GL entries
        cur.execute(
            "SELECT reference_type, entry_date, debit_amount, credit_amount, "
            "account_code, description "
            "FROM gl_journal WHERE reference_id = %s ORDER BY entry_date, id",
            (sh[0],),
        )
        gl_ship = cur.fetchall()

        # Receipt GL entries
        cur.execute(
            "SELECT reference_type, entry_date, debit_amount, credit_amount, "
            "account_code, description "
            "FROM gl_journal WHERE reference_id = %s ORDER BY entry_date, id",
            (inv[1],),
        )
        gl_rcpt = cur.fetchall()

        all_gl = gl_ship + gl_rcpt
        if all_gl:
            print(f"  {'Day':>5s}  {'Type':12s}  {'Account':8s}  {'Debit':>12s}  {'Credit':>12s}  Description")
            print(f"  {'---':>5s}  {'----':12s}  {'-------':8s}  {'-----':>12s}  {'------':>12s}  -----------")
            for g in all_gl:
                dr = f"${g[2]:,.2f}" if g[2] > 0 else ""
                cr = f"${g[3]:,.2f}" if g[3] > 0 else ""
                print(f"  {g[1]:5d}  {g[0]:12s}  {g[4]:8s}  {dr:>12s}  {cr:>12s}  {g[5] or ''}")

        # --- CONSERVATION CHECK ---
        print(f"\n{'=' * 72}")
        print(f"CONSERVATION CHECK (order_to_cash flow group)")
        print(f"{'=' * 72}")
        print(f"  Order cases:    {order_cases:>10,.0f}")
        print(f"  Shipped cases:  {ship_cases:>10,.0f}  {'MATCH' if order_cases == ship_cases else 'MISMATCH'}")
        print(f"  Invoiced cases: {inv_cases:>10,.0f}  {'MATCH' if ship_cases == inv_cases else 'MISMATCH'}")
        print(f"  Invoiced amount:   ${inv[5]:>10,.2f}")
        print(f"  Collected amount:  ${collected:>10,.2f}  {'MATCH' if abs(collected - inv[5]) < 0.01 else 'PARTIAL' if collected > 0 else 'PENDING'}")

        margin = total_rev - sum(g[2] for g in gl_ship if g[0] == 'sale' and g[4] == '5100')
        cogs = sum(g[2] for g in gl_ship if g[0] == 'sale' and g[4] == '5100')
        if cogs > 0:
            print(f"\n  Revenue:   ${total_rev:>10,.2f}")
            print(f"  COGS:      ${cogs:>10,.2f}")
            print(f"  Freight:   ${sh[5]:>10,.2f}")
            print(f"  Margin:    ${total_rev - cogs - sh[5]:>10,.2f} ({(total_rev - cogs - sh[5]) / total_rev * 100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Trace an order through the O2C cycle")
    parser.add_argument("--order-id", type=int, help="Specific order ID to trace (default: picks a small delivered order)")
    args = parser.parse_args()

    try:
        with psycopg.connect(CONN_STR) as conn:
            trace_order(conn, args.order_id)
    except psycopg.OperationalError as e:
        print(f"Database connection failed: {e}", file=sys.stderr)
        print("Make sure the PCG database is running (see .env.example)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
