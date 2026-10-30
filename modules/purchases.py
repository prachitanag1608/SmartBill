
# modules/purchases.py

import sqlite3
from modules.db import get_connection


def list_suppliers(search=""):
    conn = get_connection()
    try:
        sql = """
            SELECT *
            FROM suppliers
        """
        params = []

        if search.strip():
            sql += """
                WHERE name LIKE ?
                   OR phone LIKE ?
            """
            term = f"%{search.strip()}%"
            params = [term, term]

        sql += " ORDER BY id DESC"

        return [
            dict(row)
            for row in conn.execute(sql, params).fetchall()
        ]
    finally:
        conn.close()


def create_supplier(
    name,
    phone=None,
    email=None,
    address=None,
):
    name = (name or "").strip()

    if not name:
        raise ValueError("Supplier name is required.")

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Verify that these fields exist in your schema.
        cur = conn.execute("""
            INSERT INTO suppliers (
                name, phone, email, address
            )
            VALUES (?, ?, ?, ?)
        """, (name, phone, email, address))

        supplier_id = cur.lastrowid
        conn.commit()
        return supplier_id

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_purchase_orders(limit=200):
    conn = get_connection()
    try:
        return [
            dict(row)
            for row in conn.execute("""
                SELECT *
                FROM purchase_orders
                ORDER BY id DESC
                LIMIT ?
            """, (max(1, min(int(limit), 5000)),)).fetchall()
        ]
    finally:
        conn.close()


def get_purchase_order(order_id):
    conn = get_connection()
    try:
        order = conn.execute("""
            SELECT *
            FROM purchase_orders
            WHERE id = ?
        """, (order_id,)).fetchone()

        if not order:
            return None

        items = conn.execute("""
            SELECT *
            FROM purchase_items
            WHERE purchase_order_id = ?
        """, (order_id,)).fetchall()

        result = dict(order)
        result["items"] = [dict(x) for x in items]
        return result

    finally:
        conn.close()


def receive_purchase(
    order_id,
    received_by=None,
):
    """
    Receive an entire purchase order.

    CONTRACT:
    - purchase_orders must have status
    - purchase_items must have product_id and quantity
    - order status must be 'ordered'
    - stock movement uses purchase movement_type
    - products uses stock_qty_milli and track_stock

    This version assumes full receipt, not partial receipt.
    Verify the column names and order status values first.
    """

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        order = conn.execute("""
            SELECT *
            FROM purchase_orders
            WHERE id = ?
        """, (order_id,)).fetchone()

        if not order:
            raise ValueError("Purchase order not found.")

        if order["status"] != "ordered":
            raise ValueError(
                "Only ordered purchase orders can be received."
            )

        items = conn.execute("""
            SELECT *
            FROM purchase_items
            WHERE purchase_order_id = ?
        """, (order_id,)).fetchall()

        if not items:
            raise ValueError("Purchase order has no items.")

        for item in items:
            product = conn.execute("""
                SELECT id, stock_qty_milli, track_stock, is_active
                FROM products
                WHERE id = ?
            """, (item["product_id"],)).fetchone()

            if not product:
                raise ValueError("A purchase product no longer exists.")

            if not product["is_active"]:
                raise ValueError("Cannot receive an inactive product.")

            if not product["track_stock"]:
                raise ValueError(
                    "Purchase contains a product with stock tracking disabled."
                )

            # Assumption: purchase item quantity is stored in milli-units.
            qty = int(item["quantity_milli"])

            if qty <= 0:
                raise ValueError("Invalid purchase quantity.")

            conn.execute("""
                UPDATE products
                SET stock_qty_milli = stock_qty_milli + ?
                WHERE id = ?
            """, (qty, product["id"]))

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
                VALUES (?, 'purchase', ?, 'purchase', ?, ?, ?)
            """, (
                product["id"],
                qty,
                order_id,
                f"Purchase order {order_id} received",
                received_by,
            ))

        conn.execute("""
            UPDATE purchase_orders
            SET status = 'received'
            WHERE id = ?
        """, (order_id,))

        conn.commit()

        return {
            "purchase_order_id": order_id,
            "received_items": len(items),
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
