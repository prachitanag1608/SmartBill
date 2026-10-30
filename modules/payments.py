
# modules/payments.py

import sqlite3
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from modules.db import get_connection


PAYMENT_METHODS = {
    "cash",
    "upi",
    "card",
    "bank_transfer",
    "other",
}


def rupees_to_paise(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid amount.")

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Payment must be positive.")

    return int(
        (amount * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def get_payment_columns(conn):
    return {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(payments)"
        ).fetchall()
    }


def get_invoice_balance(invoice_id, conn=None):
    own_connection = conn is None

    if own_connection:
        conn = get_connection()

    try:
        invoice = conn.execute("""
            SELECT id, invoice_number, total_paise,
                   status, payment_status
            FROM invoices
            WHERE id = ?
        """, (invoice_id,)).fetchone()

        if not invoice:
            raise ValueError("Invoice not found.")

        paid = conn.execute("""
            SELECT COALESCE(SUM(amount_paise), 0)
            FROM payments
            WHERE invoice_id = ?
              AND status = 'completed'
        """, (invoice_id,)).fetchone()[0]

        total = int(invoice["total_paise"])
        paid = int(paid)

        return {
            "invoice_id": invoice["id"],
            "invoice_number": invoice["invoice_number"],
            "invoice_status": invoice["status"],
            "payment_status": invoice["payment_status"],
            "total_paise": total,
            "paid_paise": paid,
            "balance_paise": max(0, total - paid),
        }

    finally:
        if own_connection:
            conn.close()


def list_payments(search=""):
    conn = get_connection()

    try:
        columns = get_payment_columns(conn)

        required = {
            "id",
            "invoice_id",
            "amount_paise",
            "method",
            "status",
            "payment_date",
        }

        if not required.issubset(columns):
            raise ValueError(
                "Payment schema does not match expected fields."
            )

        sql = """
            SELECT
                p.id,
                p.invoice_id,
                i.invoice_number,
                p.amount_paise,
                p.method,
                p.status,
                p.payment_date,
                p.received_by,
                p.notes
            FROM payments p
            LEFT JOIN invoices i ON i.id = p.invoice_id
        """

        params = []

        if search.strip():
            term = f"%{search.strip()}%"
            sql += """
                WHERE i.invoice_number LIKE ?
                   OR CAST(p.id AS TEXT) LIKE ?
            """
            params = [term, term]

        sql += " ORDER BY p.id DESC LIMIT 1000"

        return [
            dict(row)
            for row in conn.execute(sql, params).fetchall()
        ]

    finally:
        conn.close()


def record_payment(
    invoice_id,
    amount_rupees,
    method,
    received_by,
    reference=None,
    notes=None,
):
    amount_paise = rupees_to_paise(amount_rupees)

    if method not in PAYMENT_METHODS:
        raise ValueError("Invalid payment method.")

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        invoice = conn.execute("""
            SELECT id, total_paise, status
            FROM invoices
            WHERE id = ?
        """, (invoice_id,)).fetchone()

        if not invoice:
            raise ValueError("Invoice not found.")

        if invoice["status"] != "issued":
            raise ValueError(
                "Only issued invoices can receive payments."
            )

        columns = get_payment_columns(conn)

        required = {
            "invoice_id",
            "amount_paise",
            "method",
            "status",
            "payment_date",
            "received_by",
            "notes",
        }

        if not required.issubset(columns):
            raise ValueError(
                "Payments schema needs verification."
            )

        balance = get_invoice_balance(
            invoice_id,
            conn,
        )

        if amount_paise > balance["balance_paise"]:
            raise ValueError(
                "Payment exceeds the outstanding balance."
            )

        if balance["balance_paise"] <= 0:
            raise ValueError("Invoice is already paid.")

        if received_by is None:
            raise ValueError(
                "Logged-in staff attribution is required."
            )

        # Check staff exists.
        staff = conn.execute("""
            SELECT username, is_active
            FROM users
            WHERE username = ?
        """, (received_by,)).fetchone()

        if not staff or not staff["is_active"]:
            raise ValueError("Invalid staff account.")

        fields = [
            "invoice_id",
            "amount_paise",
            "method",
            "status",
            "payment_date",
            "received_by",
            "notes",
        ]

        values = [
            invoice_id,
            amount_paise,
            method,
            "completed",
            __import__("datetime").datetime.now().isoformat(
                timespec="seconds"
            ),
            received_by,
            notes,
        ]

        # Optional reference field.
        if "reference" in columns:
            fields.append("reference")
            values.append(reference)

        sql = (
            "INSERT INTO payments ("
            + ", ".join(f'"{f}"' for f in fields)
            + ") VALUES ("
            + ", ".join("?" for _ in fields)
            + ")"
        )

        cur = conn.execute(sql, values)
        payment_id = cur.lastrowid

        updated_balance = (
            balance["balance_paise"] - amount_paise
        )

        new_status = (
            "paid" if updated_balance == 0 else "partial"
        )

        conn.execute("""
            UPDATE invoices
            SET payment_status = ?
            WHERE id = ?
        """, (new_status, invoice_id))

        conn.commit()

        return {
            "payment_id": payment_id,
            "invoice_id": invoice_id,
            "amount_paise": amount_paise,
            "balance_paise": updated_balance,
            "payment_status": new_status,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
