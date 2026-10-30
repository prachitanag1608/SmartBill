
# modules/inventory.py

from modules.db import get_connection


def list_inventory(search="", stock_status="All", limit=500):
    """Return inventory items with calculated stock status."""

    conn = get_connection()

    try:
        sql = """
            SELECT
                p.id,
                p.sku,
                p.barcode,
                p.name,
                p.category_id,
                p.unit,
                p.cost_price_paise,
                p.selling_price_paise,
                p.stock_qty_milli,
                p.reorder_level_milli,
                p.track_stock,
                p.is_active,
                c.name AS category_name
            FROM products p
            LEFT JOIN categories c
                ON c.id = p.category_id
            WHERE p.is_active = 1
        """

        params = []

        if search.strip():
            term = f"%{search.strip()}%"
            sql += """
                AND (
                    p.name LIKE ?
                    OR p.sku LIKE ?
                    OR COALESCE(p.barcode, '') LIKE ?
                )
            """
            params.extend([term, term, term])

        sql += " ORDER BY p.name COLLATE NOCASE"

        rows = conn.execute(sql, params).fetchall()

        result = []

        for row in rows:
            item = dict(row)

            stock = int(item["stock_qty_milli"] or 0)
            reorder = int(item["reorder_level_milli"] or 0)
            tracked = bool(item["track_stock"])

            if not tracked:
                status = "Untracked"
            elif stock <= 0:
                status = "Out of Stock"
            elif stock <= reorder:
                status = "Low Stock"
            else:
                status = "In Stock"

            item["stock_status"] = status

            result.append(item)

        if stock_status != "All":
            result = [
                item for item in result
                if item["stock_status"] == stock_status
            ]

        limit = max(1, min(int(limit), 5000))
        return result[:limit]

    finally:
        conn.close()


def inventory_summary():
    """Return summary statistics for active products."""

    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT
                stock_qty_milli,
                reorder_level_milli,
                cost_price_paise,
                track_stock
            FROM products
            WHERE is_active = 1
        """).fetchall()

        tracked = [
            row for row in rows
            if row["track_stock"]
        ]

        low_stock = 0
        out_of_stock = 0
        stock_value_paise = 0

        for row in tracked:
            stock = int(row["stock_qty_milli"] or 0)
            reorder = int(row["reorder_level_milli"] or 0)
            cost = int(row["cost_price_paise"] or 0)

            if stock <= 0:
                out_of_stock += 1
            elif stock <= reorder:
                low_stock += 1

            stock_value_paise += round(
                stock * cost / 1000
            )

        return {
            "active_products": len(rows),
            "tracked_products": len(tracked),
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "stock_value_paise": stock_value_paise,
        }

    finally:
        conn.close()



def get_stock_movements(product_id=None, limit=200):
    """Retrieve stock movement history."""

    conn = get_connection()

    try:
        # Inspect the actual table schema
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(stock_movements)"
            ).fetchall()
        }

        # Use the available timestamp column, if present.
        possible_timestamp_columns = [
            "created_at",
            "movement_date",
            "created_on",
            "timestamp",
        ]

        timestamp_column = next(
            (
                name
                for name in possible_timestamp_columns
                if name in columns
            ),
            None,
        )

        if timestamp_column:
            # Column name comes from our fixed allowlist.
            timestamp_expr = f"sm.{timestamp_column}"
        else:
            # Avoid failing if no timestamp column exists.
            timestamp_expr = "NULL"

        sql = f"""
            SELECT
                sm.id,
                sm.product_id,
                p.name AS product_name,
                p.sku,
                sm.movement_type,
                sm.quantity_delta_milli,
                sm.reference_type,
                sm.reference_id,
                sm.reason,
                sm.created_by,
                {timestamp_expr} AS created_at
            FROM stock_movements sm
            JOIN products p
                ON p.id = sm.product_id
            WHERE 1=1
        """

        params = []

        if product_id is not None:
            sql += " AND sm.product_id = ?"
            params.append(product_id)

        sql += " ORDER BY sm.id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 5000)))

        rows = conn.execute(sql, params).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()

def adjust_stock(
    product_id,
    new_quantity_milli,
    reason,
    created_by=None,
):
    """
    Set physical stock quantity.

    Records the difference as an adjustment.
    Product update and movement insert are atomic.
    """

    product_id = int(product_id)
    new_quantity_milli = int(new_quantity_milli)
    reason = str(reason or "").strip()

    if new_quantity_milli < 0:
        raise ValueError("Stock quantity cannot be negative.")

    if new_quantity_milli > 2_000_000_000:
        raise ValueError("Stock quantity is too large.")

    if not reason:
        raise ValueError("Adjustment reason is required.")

    if len(reason) > 500:
        raise ValueError("Reason must not exceed 500 characters.")

    conn = get_connection()

    try:
        # Acquire write lock before reading stock.
        conn.execute("BEGIN IMMEDIATE")

        product = conn.execute("""
            SELECT
                id,
                name,
                stock_qty_milli,
                track_stock,
                is_active
            FROM products
            WHERE id = ?
        """, (product_id,)).fetchone()

        if not product:
            raise ValueError("Product not found.")

        if not product["is_active"]:
            raise ValueError("Inactive products cannot be adjusted.")

        if not product["track_stock"]:
            raise ValueError("Stock tracking is disabled for this product.")

        old_quantity = int(product["stock_qty_milli"] or 0)

        delta = new_quantity_milli - old_quantity

        if delta == 0:
            raise ValueError("New quantity matches current stock.")

        # Update inventory.
        conn.execute("""
            UPDATE products
            SET stock_qty_milli = ?
            WHERE id = ?
        """, (new_quantity_milli, product_id))

        # Record the stock movement.
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
            VALUES (?, 'adjustment', ?, 'adjustment', NULL, ?, ?)
        """, (
            product_id,
            delta,
            reason,
            created_by,
        ))

        conn.commit()

        return {
            "product_id": product_id,
            "product_name": product["name"],
            "old_quantity_milli": old_quantity,
            "new_quantity_milli": new_quantity_milli,
            "delta_milli": delta,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
