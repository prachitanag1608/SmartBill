
# modules/dashboard.py

from modules.db import get_connection


def get_dashboard_data():

    conn = get_connection()

    try:
        # Today's issued sales
        sales = conn.execute("""
            SELECT
                COUNT(*) AS invoice_count,
                COALESCE(SUM(total_paise), 0) AS sales_paise
            FROM invoices
            WHERE status = 'issued'
              AND date(invoice_date) = date('now', 'localtime')
        """).fetchone()

        # Today's completed payments
        payments = conn.execute("""
            SELECT
                COALESCE(SUM(amount_paise), 0) AS collected_paise
            FROM payments
            WHERE status = 'completed'
              AND date(payment_date) = date('now', 'localtime')
        """).fetchone()

        # Current active tracked inventory
        inventory = conn.execute("""
            SELECT
                COUNT(*) AS tracked_products,
                COALESCE(SUM(
                    CASE
                        WHEN stock_qty_milli <= 0 THEN 1
                        ELSE 0
                    END
                ), 0) AS out_of_stock,
                COALESCE(SUM(
                    CASE
                        WHEN stock_qty_milli > 0
                         AND stock_qty_milli <= reorder_level_milli
                        THEN 1
                        ELSE 0
                    END
                ), 0) AS low_stock
            FROM products
            WHERE is_active = 1
              AND track_stock = 1
        """).fetchone()

        # Outstanding invoices
        outstanding = conn.execute("""
            SELECT
                COALESCE(SUM(
                    MAX(
                        i.total_paise -
                        COALESCE(p.paid_paise, 0),
                        0
                    )
                ), 0) AS outstanding_paise
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
        """).fetchone()

        # Recent invoices
        recent = conn.execute("""
            SELECT
                id,
                invoice_number,
                invoice_date,
                total_paise,
                payment_status
            FROM invoices
            WHERE status = 'issued'
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

        # Recent product performance
        top_products = conn.execute("""
            SELECT
                ii.product_name,
                ii.sku,
                SUM(ii.quantity_milli) AS quantity_sold_milli,
                SUM(ii.line_total_paise) AS sales_paise
            FROM invoice_items ii
            JOIN invoices i ON i.id = ii.invoice_id
            WHERE i.status = 'issued'
            GROUP BY ii.product_name, ii.sku
            ORDER BY sales_paise DESC
            LIMIT 5
        """).fetchall()

        return {
            "sales": dict(sales),
            "payments": dict(payments),
            "inventory": dict(inventory),
            "outstanding": dict(outstanding),
            "recent_invoices": [
                dict(r) for r in recent
            ],
            "top_products": [
                dict(r) for r in top_products
            ],
        }

    finally:
        conn.close()
