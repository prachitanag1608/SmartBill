
# modules/reports.py

from modules.db import get_connection


def sales_summary(start_date, end_date):
    """
    Sales summary for issued invoices.

    Dates: YYYY-MM-DD
    Invoice date is assumed to be stored in this format.
    """

    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) AS invoice_count,
                COALESCE(SUM(subtotal_paise), 0)
                    AS subtotal_paise,
                COALESCE(SUM(discount_paise), 0)
                    AS discount_paise,
                COALESCE(SUM(tax_paise), 0)
                    AS tax_paise,
                COALESCE(SUM(total_paise), 0)
                    AS total_paise
            FROM invoices
            WHERE status = 'issued'
              AND date(invoice_date) >= date(?)
              AND date(invoice_date) <= date(?)
        """, (start_date, end_date)).fetchone()

        return dict(row)
    finally:
        conn.close()


def payment_summary(start_date, end_date):
    """
    Completed payment collection report.

    Payment date column assumed: payment_date.
    """

    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) AS payment_count,
                COALESCE(SUM(amount_paise), 0)
                    AS collected_paise
            FROM payments
            WHERE status = 'completed'
              AND date(payment_date) >= date(?)
              AND date(payment_date) <= date(?)
        """, (start_date, end_date)).fetchone()

        return dict(row)
    finally:
        conn.close()


def outstanding_summary():
    """
    Outstanding balances for issued invoices.

    Uses completed payments.
    """

    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                i.id,
                i.invoice_number,
                i.invoice_date,
                i.total_paise,
                COALESCE(p.paid_paise, 0) AS paid_paise
            FROM invoices i
            LEFT JOIN (
                SELECT
                    invoice_id,
                    SUM(amount_paise) AS paid_paise
                FROM payments
                WHERE status = 'completed'
                GROUP BY invoice_id
            ) p ON p.invoice_id = i.id
            WHERE i.status = 'issued'
            ORDER BY i.id DESC
        """).fetchall()

        result = []

        for row in rows:
            item = dict(row)

            total = int(item["total_paise"] or 0)
            paid = int(item["paid_paise"] or 0)

            item["balance_paise"] = max(0, total - paid)

            if item["balance_paise"] > 0:
                result.append(item)

        return result
    finally:
        conn.close()


def top_selling_products(
    start_date,
    end_date,
    limit=10,
):
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                ii.product_id,
                ii.product_name,
                ii.sku,
                SUM(ii.quantity_milli) AS quantity_sold_milli,
                SUM(ii.line_total_paise) AS sales_paise
            FROM invoice_items ii
            JOIN invoices i ON i.id = ii.invoice_id
            WHERE i.status = 'issued'
              AND date(i.invoice_date) >= date(?)
              AND date(i.invoice_date) <= date(?)
            GROUP BY ii.product_id, ii.product_name, ii.sku
            ORDER BY sales_paise DESC
            LIMIT ?
        """, (
            start_date,
            end_date,
            max(1, min(int(limit), 100)),
        )).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def daily_sales(start_date, end_date):
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                date(invoice_date) AS sale_date,
                COUNT(*) AS invoice_count,
                SUM(total_paise) AS sales_paise
            FROM invoices
            WHERE status = 'issued'
              AND date(invoice_date) >= date(?)
              AND date(invoice_date) <= date(?)
            GROUP BY date(invoice_date)
            ORDER BY date(invoice_date)
        """, (start_date, end_date)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()
