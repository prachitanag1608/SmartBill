
# modules/expenses.py

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from modules.db import get_connection


def get_columns(conn, table):
    rows = conn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    return {row["name"] for row in rows}


def rupees_to_paise(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid amount.")

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be positive.")

    return int(
        (amount * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def expense_schema():
    conn = get_connection()
    try:
        columns = get_columns(conn, "expenses")

        if not columns:
            raise ValueError("Expenses table not found.")

        return columns
    finally:
        conn.close()


def list_expenses(search=""):
    conn = get_connection()

    try:
        columns = get_columns(conn, "expenses")

        if not columns:
            raise ValueError("Expenses table not found.")

        if "id" not in columns:
            raise ValueError("Expenses table needs an id column.")

        sql = "SELECT * FROM expenses"
        params = []

        searchable = [
            c for c in ("category", "description", "notes", "vendor")
            if c in columns
        ]

        if search.strip() and searchable:
            clauses = [
                f'"{c}" LIKE ?' for c in searchable
            ]
            sql += " WHERE (" + " OR ".join(clauses) + ")"
            params = [
                f"%{search.strip()}%"
                for _ in searchable
            ]

        sql += " ORDER BY id DESC LIMIT 1000"

        return [
            dict(row)
            for row in conn.execute(sql, params).fetchall()
        ]

    finally:
        conn.close()


def create_expense(
    amount_rupees,
    category,
    description="",
    expense_date=None,
    payment_method="cash",
    vendor="",
    notes="",
    created_by=None,
):
    """
    Insert an expense using detected supported columns.

    Common supported schema:
      amount_paise OR amount
      category
      description
      expense_date OR date
      payment_method
      vendor
      notes
      created_by

    Required: id, an amount field and a category field.
    """

    amount_paise = rupees_to_paise(amount_rupees)

    category = (category or "").strip()

    if not category:
        raise ValueError("Expense category is required.")

    if payment_method not in {
        "cash", "upi", "card", "bank_transfer", "other"
    }:
        raise ValueError("Invalid payment method.")

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        columns = get_columns(conn, "expenses")

        if not columns:
            raise ValueError("Expenses table not found.")

        if "category" not in columns:
            raise ValueError("Expenses table needs category.")

        # Match an amount field from the supported schema.
        amount_column = next(
            (
                name for name in ("amount_paise", "amount")
                if name in columns
            ),
            None,
        )

        if not amount_column:
            raise ValueError(
                "No supported expense amount column found."
            )

        values = {
            amount_column: (
                amount_paise
                if amount_column == "amount_paise"
                else float(Decimal(str(amount_rupees)))
            ),
            "category": category,
            "description": description.strip() or None,
            "expense_date": expense_date,
            "date": expense_date,
            "payment_method": payment_method,
            "vendor": vendor.strip() or None,
            "notes": notes.strip() or None,
            "created_by": created_by,
        }

        # Only insert fields that exist.
        insert_values = {
            key: value
            for key, value in values.items()
            if key in columns
        }

        if not insert_values:
            raise ValueError("No compatible expense fields.")

        fields = list(insert_values.keys())

        sql = (
            "INSERT INTO expenses ("
            + ", ".join(f'"{c}"' for c in fields)
            + ") VALUES ("
            + ", ".join("?" for _ in fields)
            + ")"
        )

        cur = conn.execute(
            sql,
            [insert_values[c] for c in fields],
        )

        expense_id = cur.lastrowid

        conn.commit()

        return expense_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def delete_expense(expense_id):
    """
    Deliberately not implemented.

    Financial records should normally be voided/reversed
    with an audit trail instead of being deleted.
    """
    raise NotImplementedError(
        "Use an audited expense reversal workflow."
    )
