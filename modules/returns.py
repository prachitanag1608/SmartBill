
# modules/returns.py

from modules.db import get_connection


def find_returnable_invoices(search=""):
    conn = get_connection()
    try:
        sql = """
            SELECT
                id,
                invoice_number,
                invoice_date,
                status,
                payment_status,
                total_paise
            FROM invoices
            WHERE status = 'issued'
        """
        params = []

        if search.strip():
            term = f"%{search.strip()}%"
            sql += """
                AND (
                    invoice_number LIKE ?
                )
            """
            params.append(term)

        sql += " ORDER BY id DESC LIMIT 100"

        return [
            dict(row)
            for row in conn.execute(sql, params).fetchall()
        ]
    finally:
        conn.close()


def get_original_invoice_items(invoice_id):
    conn = get_connection()
    try:
        invoice = conn.execute("""
            SELECT *
            FROM invoices
            WHERE id = ?
              AND status = 'issued'
        """, (invoice_id,)).fetchone()

        if not invoice:
            raise ValueError("Issued invoice not found.")

        items = conn.execute("""
            SELECT *
            FROM invoice_items
            WHERE invoice_id = ?
        """, (invoice_id,)).fetchall()

        return {
            "invoice": dict(invoice),
            "items": [dict(x) for x in items],
        }
    finally:
        conn.close()


def calculate_return_preview(
    original_quantity_milli,
    previously_returned_milli,
    requested_quantity_milli,
    original_line_total_paise,
):
    """
    Basic proportional preview.

    Production refunds should allocate original discounts,
    taxes, rounding and previous returns consistently.
    """

    original_quantity_milli = int(original_quantity_milli)
    previously_returned_milli = int(previously_returned_milli)
    requested_quantity_milli = int(requested_quantity_milli)
    original_line_total_paise = int(original_line_total_paise)

    if original_quantity_milli <= 0:
        raise ValueError("Invalid original quantity.")

    remaining = (
        original_quantity_milli - previously_returned_milli
    )

    if remaining < 0:
        raise ValueError("Existing return quantities are invalid.")

    if requested_quantity_milli <= 0:
        raise ValueError("Return quantity must be positive.")

    if requested_quantity_milli > remaining:
        raise ValueError(
            "Requested return exceeds the remaining returnable quantity."
        )

    refund_preview = (
        original_line_total_paise
        * requested_quantity_milli
        // original_quantity_milli
    )

    return {
        "remaining_quantity_milli": remaining,
        "requested_quantity_milli": requested_quantity_milli,
        "refund_preview_paise": refund_preview,
    }
