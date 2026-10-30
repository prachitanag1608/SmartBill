
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from uuid import uuid4
import sqlite3

from modules.db import get_connection


PAYMENT_METHODS = {
    "cash",
    "upi",
    "card",
    "bank_transfer",
    "other",
}


# =================================================
# MONEY / QUANTITY HELPERS
# =================================================

def rupees_to_paise(value):
    """Convert a rupee amount to integer paise."""
    amount = Decimal(str(value))

    if not amount.is_finite() or amount < 0:
        raise ValueError("Invalid monetary amount.")

    return int(
        (amount * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP
        )
    )


def quantity_to_milli(value):
    """Convert quantity to thousandths."""
    qty = Decimal(str(value))

    if not qty.is_finite() or qty <= 0:
        raise ValueError("Quantity must be positive.")

    milli = qty * 1000

    if milli != milli.to_integral_value():
        raise ValueError(
            "Quantity must have at most 3 decimal places."
        )

    return int(milli)


def money(paise):
    return f"₹{paise / 100:,.2f}"


def rounded_division(numerator, denominator):
    """Round non-negative integer division half-up."""
    if numerator < 0 or denominator <= 0:
        raise ValueError("Invalid calculation.")

    return (numerator + denominator // 2) // denominator


# =================================================
# TAX / BILL CALCULATIONS
# =================================================

def calculate_bill(items, bill_discount_paise=0):
    """
    items:
        [
            {
                'product_id': 1,
                'quantity_milli': 1000,
                'unit_price_paise': 5000,
                'tax_rate_bps': 0,
                'discount_bps': 0
            }
        ]

    discount_bps: 100 = 1%, 10000 = 100%

    Tax is calculated after each line discount.
    Line tax is rounded to the nearest paise.
    """

    if not items:
        raise ValueError("Cart is empty.")

    if (
        not isinstance(bill_discount_paise, int)
        or isinstance(bill_discount_paise, bool)
        or bill_discount_paise < 0
    ):
        raise ValueError("Invalid bill discount.")

    lines = []
    subtotal = 0
    item_discount_total = 0
    tax_total = 0

    for item in items:
        qty = item["quantity_milli"]
        price = item["unit_price_paise"]
        tax_rate = item["tax_rate_bps"]
        discount_rate = item.get("discount_bps", 0)

        if (
            not isinstance(qty, int)
            or isinstance(qty, bool)
            or qty <= 0
        ):
            raise ValueError("Invalid quantity.")

        if (
            not isinstance(price, int)
            or isinstance(price, bool)
            or price < 0
        ):
            raise ValueError("Invalid unit price.")

        if (
            not isinstance(tax_rate, int)
            or isinstance(tax_rate, bool)
            or not 0 <= tax_rate <= 10000
        ):
            raise ValueError("Invalid tax rate.")

        if (
            not isinstance(discount_rate, int)
            or isinstance(discount_rate, bool)
            or not 0 <= discount_rate <= 10000
        ):
            raise ValueError("Invalid discount rate.")

        # Gross line amount.
        gross = rounded_division(
            qty * price, 1000
        )

        line_discount = rounded_division(
            gross * discount_rate, 10000
        )

        taxable = gross - line_discount

        line_tax = rounded_division(
            taxable * tax_rate, 10000
        )

        line_total = taxable + line_tax

        subtotal += gross
        item_discount_total += line_discount
        tax_total += line_tax

        lines.append({
            **item,
            "gross_paise": gross,
            "discount_paise": line_discount,
            "taxable_paise": taxable,
            "tax_paise": line_tax,
            "line_total_paise": line_total,
        })

    after_item_discounts = (
        subtotal - item_discount_total
    )

    if bill_discount_paise > after_item_discounts:
        raise ValueError(
            "Bill discount exceeds the eligible amount."
        )

    # Allocate bill-level discount proportionally.
    # Any remainder is assigned deterministically.
    allocations = [0] * len(lines)

    if bill_discount_paise:
        bases = [
            line["taxable_paise"]
            for line in lines
        ]

        base_total = sum(bases)

        if base_total <= 0:
            raise ValueError(
                "Cannot apply bill discount to zero-value bill."
            )

        running = 0

        for i in range(len(lines)):
            if i == len(lines) - 1:
                allocation = (
                    bill_discount_paise - running
                )
            else:
                allocation = (
                    bill_discount_paise * bases[i]
                    // base_total
                )

            allocations[i] = allocation
            running += allocation

    final_lines = []
    final_tax_total = 0

    for i, line in enumerate(lines):
        allocated = allocations[i]

        final_taxable = (
            line["taxable_paise"] - allocated
        )

        final_tax = rounded_division(
            final_taxable * line["tax_rate_bps"],
            10000
        )

        final_total = final_taxable + final_tax

        final_tax_total += final_tax

        final_lines.append({
            **line,
            "bill_discount_paise": allocated,
            "final_taxable_paise": final_taxable,
            "final_tax_paise": final_tax,
            "line_total_paise": final_total,
        })

    total_discount = (
        item_discount_total + bill_discount_paise
    )

    final_total = (
        subtotal - total_discount + final_tax_total
    )

    return {
        "lines": final_lines,
        "subtotal_paise": subtotal,
        "discount_paise": total_discount,
        "tax_paise": final_tax_total,
        "total_paise": final_total,
    }


# =================================================
# DATABASE HELPERS
# =================================================

def list_customers(search=""):
    conn = get_connection()

    try:
        query = """
            SELECT id, name, phone, email
            FROM customers
            WHERE is_active = 1
        """
        params = []

        if search.strip():
            term = f"%{search.strip()}%"
            query += """
                AND (
                    name LIKE ?
                    OR phone LIKE ?
                    OR email LIKE ?
                )
            """
            params.extend([term, term, term])

        query += " ORDER BY name COLLATE NOCASE"

        return conn.execute(query, params).fetchall()

    finally:
        conn.close()


def search_products(search):
    if not search.strip():
        return []

    conn = get_connection()

    try:
        term = f"%{search.strip()}%"

        return conn.execute("""
            SELECT
                id, sku, barcode, name, unit,
                selling_price_paise, tax_rate_bps,
                stock_qty_milli, track_stock
            FROM products
            WHERE is_active = 1
              AND (
                  name LIKE ?
                  OR sku LIKE ?
                  OR barcode LIKE ?
              )
            ORDER BY name
            LIMIT 50
        """, (term, term, term)).fetchall()

    finally:
        conn.close()


# =================================================
# CHECKOUT
# =================================================

def checkout(
    items,
    customer_id=None,
    bill_discount_paise=0,
    payment_amount_paise=0,
    payment_method="cash",
    payment_reference=None,
    notes=None,
    created_by=None,
    idempotency_key=None,
):
    """
    Issue an invoice atomically.

    items:
        [
            {
                'product_id': 1,
                'quantity_milli': 1000,
                'discount_bps': 0
            }
        ]

    Prices and taxes are always fetched from the database.
    Client-provided prices are never trusted.

    idempotency_key:
        Unique checkout request key. Reusing the same key
        returns the existing invoice, without charging again.

    The same key must not be reused for a different request.
    """

    if not items:
        raise ValueError("Cart is empty.")

    if not isinstance(bill_discount_paise, int) or isinstance(
        bill_discount_paise, bool
    ) or bill_discount_paise < 0:
        raise ValueError("Invalid bill discount.")

    if not isinstance(payment_amount_paise, int) or isinstance(
        payment_amount_paise, bool
    ) or payment_amount_paise < 0:
        raise ValueError("Invalid payment amount.")

    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Invalid payment method.")

    if idempotency_key is None:
        idempotency_key = str(uuid4())

    if not isinstance(idempotency_key, str) or not (
        1 <= len(idempotency_key) <= 100
    ):
        raise ValueError("Invalid checkout request key.")

    # Consolidate duplicate cart rows.
    combined = {}

    for item in items:
        pid = item.get("product_id")
        qty = item.get("quantity_milli")
        discount = item.get("discount_bps", 0)

        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid <= 0
        ):
            raise ValueError("Invalid product ID.")

        if (
            not isinstance(qty, int)
            or isinstance(qty, bool)
            or qty <= 0
        ):
            raise ValueError("Invalid quantity.")

        if (
            not isinstance(discount, int)
            or isinstance(discount, bool)
            or not 0 <= discount <= 10000
        ):
            raise ValueError("Invalid discount.")

        if pid in combined:
            if combined[pid]["discount_bps"] != discount:
                raise ValueError(
                    "Same product has conflicting discounts."
                )

            combined[pid]["quantity_milli"] += qty

        else:
            combined[pid] = {
                "product_id": pid,
                "quantity_milli": qty,
                "discount_bps": discount,
            }

    conn = get_connection()

    try:
        # Acquire write lock before validating stock.
        conn.execute("BEGIN IMMEDIATE")

        # Idempotency check.
        existing = conn.execute("""
            SELECT id, invoice_number, total_paise
            FROM invoices
            WHERE notes LIKE ?
        """, (
            f"[SBKEY:{idempotency_key}]%"
        ,)).fetchone()

        if existing:
            conn.rollback()
            return dict(existing)

        if created_by is not None:
            user = conn.execute("""
                SELECT id, is_active
                FROM users
                WHERE id = ?
            """, (created_by,)).fetchone()

            if user is None or not user["is_active"]:
                raise ValueError("Invalid billing user.")

        customer = None

        if customer_id is not None:
            customer = conn.execute("""
                SELECT *
                FROM customers
                WHERE id = ? AND is_active = 1
            """, (customer_id,)).fetchone()

            if customer is None:
                raise ValueError(
                    "Customer not found or inactive."
                )

        business = conn.execute("""
            SELECT *
            FROM business_settings
            WHERE id = 1
        """).fetchone()

        if business is None:
            raise ValueError(
                "Business settings not initialized."
            )

        billing_items = []

        for pid, item in combined.items():
            product = conn.execute("""
                SELECT *
                FROM products
                WHERE id = ? AND is_active = 1
            """, (pid,)).fetchone()

            if product is None:
                raise ValueError(
                    f"Product {pid} is unavailable."
                )

            qty = item["quantity_milli"]

            if product["track_stock"]:
                if product["stock_qty_milli"] < qty:
                    raise ValueError(
                        f"Insufficient stock for {product['name']}. "
                        f"Available: "
                        f"{product['stock_qty_milli'] / 1000:g} "
                        f"{product['unit']}."
                    )

            billing_items.append({
                "product_id": pid,
                "product_name": product["name"],
                "sku": product["sku"],
                "unit": product["unit"],
                "quantity_milli": qty,
                "unit_price_paise": (
                    product["selling_price_paise"]
                ),
                "tax_rate_bps": product["tax_rate_bps"],
                "discount_bps": item["discount_bps"],
                "track_stock": product["track_stock"],
            })

        bill = calculate_bill(
            billing_items,
            bill_discount_paise
        )

        total = bill["total_paise"]

        if payment_amount_paise > total:
            raise ValueError(
                "Payment cannot exceed invoice total. "
                "Record change separately for cash transactions."
            )

        if total == 0 and payment_amount_paise > 0:
            raise ValueError(
                "Payment is not applicable to a zero-value invoice."
            )

        payment_status = (
            "paid"
            if payment_amount_paise == total
            else (
                "partial"
                if payment_amount_paise > 0
                else "unpaid"
            )
        )

        invoice_number = (
            "SB-"
            + datetime.now().strftime("%Y%m%d")
            + "-"
            + uuid4().hex[:10].upper()
        )

        final_notes = (
            f"[SBKEY:{idempotency_key}]"
            + (f" {notes.strip()}" if notes else "")
        )

        cur = conn.execute("""
            INSERT INTO invoices (
                invoice_number,
                customer_id,
                created_by,
                status,
                payment_status,
                subtotal_paise,
                discount_paise,
                tax_paise,
                total_paise,
                notes,
                customer_name,
                customer_address,
                customer_gstin,
                business_name,
                business_address,
                business_gstin
            )
            VALUES (?, ?, ?, 'issued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_number,
            customer_id,
            created_by,
            payment_status,
            bill["subtotal_paise"],
            bill["discount_paise"],
            bill["tax_paise"],
            total,
            final_notes,
            customer["name"] if customer else "Walk-in Customer",
            customer["address"] if customer else None,
            customer["gstin"] if customer else None,
            business["business_name"],
            business["address"],
            business["gstin"],
        ))

        invoice_id = cur.lastrowid

        # Save item snapshots and inventory movements.
        for line in bill["lines"]:
            conn.execute("""
                INSERT INTO invoice_items (
                    invoice_id,
                    product_id,
                    product_name,
                    sku,
                    quantity_milli,
                    unit_price_paise,
                    discount_paise,
                    tax_rate_bps,
                    tax_paise,
                    line_total_paise
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice_id,
                line["product_id"],
                line["product_name"],
                line["sku"],
                line["quantity_milli"],
                line["unit_price_paise"],
                (
                    line["discount_paise"]
                    + line["bill_discount_paise"]
                ),
                line["tax_rate_bps"],
                line["final_tax_paise"],
                line["line_total_paise"],
            ))

            if line["track_stock"]:
                # Conditional update provides another
                # safety check for stock.
                updated = conn.execute("""
                    UPDATE products
                    SET stock_qty_milli =
                        stock_qty_milli - ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                      AND is_active = 1
                      AND track_stock = 1
                      AND stock_qty_milli >= ?
                """, (
                    line["quantity_milli"],
                    line["product_id"],
                    line["quantity_milli"],
                ))

                if updated.rowcount != 1:
                    raise ValueError(
                        "Stock changed during checkout. Retry."
                    )

                conn.execute("""
                    INSERT INTO stock_movements (
                        product_id,
                        movement_type,
                        quantity_delta_milli,
                        reference_type,
                        reference_id,
                        reason,
                        created_by
                    )
                    VALUES (?, 'sale', ?, 'invoice', ?, ?, ?)
                """, (
                    line["product_id"],
                    -line["quantity_milli"],
                    invoice_id,
                    invoice_number,
                    created_by,
                ))

        # Record payment if any.
        if payment_amount_paise > 0:
            conn.execute("""
                INSERT INTO payments (
                    invoice_id,
                    amount_paise,
                    method,
                    reference,
                    status,
                    received_by,
                    notes
                )
                VALUES (?, ?, ?, ?, 'completed', ?, ?)
            """, (
                invoice_id,
                payment_amount_paise,
                payment_method,
                payment_reference,
                created_by,
                "Initial checkout payment",
            ))

        # Audit log.
        conn.execute("""
            INSERT INTO audit_logs (
                user_id,
                action,
                entity_type,
                entity_id,
                details
            )
            VALUES (?, 'invoice_issued', 'invoice', ?, ?)
        """, (
            created_by,
            invoice_id,
            invoice_number,
        ))

        conn.commit()

        return {
            "id": invoice_id,
            "invoice_number": invoice_number,
            "total_paise": total,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =================================================
# INVOICE RETRIEVAL
# =================================================

def get_invoice(invoice_id):
    conn = get_connection()

    try:
        invoice = conn.execute("""
            SELECT *
            FROM invoices
            WHERE id = ?
        """, (invoice_id,)).fetchone()

        if invoice is None:
            return None

        items = conn.execute("""
            SELECT *
            FROM invoice_items
            WHERE invoice_id = ?
            ORDER BY id
        """, (invoice_id,)).fetchall()

        payments = conn.execute("""
            SELECT *
            FROM payments
            WHERE invoice_id = ?
              AND status = 'completed'
            ORDER BY id
        """, (invoice_id,)).fetchall()

        paid = sum(p["amount_paise"] for p in payments)

        return {
            "invoice": dict(invoice),
            "items": [dict(i) for i in items],
            "payments": [dict(p) for p in payments],
            "paid_paise": paid,
            "balance_paise": (
                invoice["total_paise"] - paid
            ),
        }

    finally:
        conn.close()
