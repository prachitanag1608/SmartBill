
# modules/invoices.py

from modules.db import get_connection


def list_invoices(
    search="",
    payment_status="All",
    invoice_status="All",
    date_from=None,
    date_to=None,
    limit=500,
):
    """Return invoices matching the selected filters."""

    conn = get_connection()

    try:
        # Discover the actual invoice columns
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(invoices)"
            ).fetchall()
        }

        # Customer name may exist as a snapshot.
        if "customer_name" in columns:
            customer_name_expr = "i.customer_name"
        elif "customer_id" in columns:
            customer_name_expr = """
                COALESCE(c.name, 'Walk-in Customer')
            """
        else:
            customer_name_expr = "'Walk-in Customer'"

        # Phone may be stored in customer table,
        # not in invoice snapshot.
        if "customer_phone" in columns:
            customer_phone_expr = "i.customer_phone"
            phone_join = ""
        elif "customer_id" in columns:
            customer_phone_expr = "c.phone"
            phone_join = """
                LEFT JOIN customers c
                    ON c.id = i.customer_id
            """
        else:
            customer_phone_expr = "NULL"
            phone_join = ""

        sql = f"""
            SELECT
                i.id,
                i.invoice_number,
                i.invoice_date,
                i.status,
                i.payment_status,
                i.subtotal_paise,
                i.discount_paise,
                i.tax_paise,
                i.total_paise,
                {customer_name_expr} AS customer_name,
                {customer_phone_expr} AS customer_phone,

                COALESCE(
                    SUM(
                        CASE
                            WHEN p.status = 'completed'
                            THEN p.amount_paise
                            ELSE 0
                        END
                    ), 0
                ) AS paid_paise

            FROM invoices i

            {phone_join}

            LEFT JOIN payments p
                ON p.invoice_id = i.id

            WHERE 1=1
        """

        params = []

        if search.strip():
            term = f"%{search.strip()}%"

            sql += f"""
                AND (
                    i.invoice_number LIKE ?
                    OR {customer_name_expr} LIKE ?
                    OR COALESCE(
                        CAST({customer_phone_expr} AS TEXT), ''
                    ) LIKE ?
                )
            """

            params.extend([term, term, term])

        if payment_status != "All":
            sql += " AND i.payment_status = ?"
            params.append(payment_status)

        if invoice_status != "All":
            sql += " AND i.status = ?"
            params.append(invoice_status)

        if date_from:
            sql += " AND date(i.invoice_date) >= date(?)"
            params.append(str(date_from))

        if date_to:
            sql += " AND date(i.invoice_date) <= date(?)"
            params.append(str(date_to))

        sql += """
            GROUP BY i.id
            ORDER BY i.id DESC
            LIMIT ?
        """

        params.append(max(1, min(int(limit), 5000)))

        rows = conn.execute(sql, params).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def get_invoice_details(invoice_id):
    """Fetch invoice, item snapshots and payment records."""

    conn = get_connection()

    try:
        invoice = conn.execute(
            "SELECT * FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()

        if not invoice:
            return None

        invoice = dict(invoice)

        items = conn.execute(
            """
            SELECT *
            FROM invoice_items
            WHERE invoice_id = ?
            ORDER BY id
            """,
            (invoice_id,),
        ).fetchall()

        payments = conn.execute(
            """
            SELECT *
            FROM payments
            WHERE invoice_id = ?
            ORDER BY payment_date, id
            """,
            (invoice_id,),
        ).fetchall()

        paid_paise = sum(
            row["amount_paise"]
            for row in payments
            if row["status"] == "completed"
        )

        return {
            "invoice": invoice,
            "items": [dict(row) for row in items],
            "payments": [dict(row) for row in payments],
            "paid_paise": paid_paise,
            "balance_paise": max(
                0,
                invoice["total_paise"] - paid_paise,
            ),
        }

    finally:
        conn.close()
