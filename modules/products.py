
import sqlite3
from contextlib import contextmanager

import streamlit as st
import pandas as pd

from modules.db import get_connection


# ==============================================
# DATABASE SESSION
# ==============================================

@contextmanager
def session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==============================================
# HELPERS
# ==============================================

def to_paise(amount):
    """Convert rupees to paise."""
    return int(round(float(amount) * 100))


def to_milli(quantity):
    """Convert units to thousandths."""
    return int(round(float(quantity) * 1000))


def money(paise):
    return f"₹{paise / 100:,.2f}"


# ==============================================
# CATEGORY MANAGEMENT
# ==============================================

def get_categories():
    with session() as conn:
        return conn.execute("""
            SELECT id, name
            FROM categories
            WHERE is_active = 1
            ORDER BY name
        """).fetchall()


def add_category(name, description=None):
    name = name.strip()

    if not name:
        raise ValueError("Category name is required.")

    with session() as conn:
        conn.execute("""
            INSERT INTO categories(name, description)
            VALUES (?, ?)
        """, (name, description or None))


# ==============================================
# PRODUCT OPERATIONS
# ==============================================

def get_products(search="", show_archived=False):
    query = """
        SELECT
            p.id,
            p.sku,
            p.barcode,
            p.name,
            p.category_id,
            c.name AS category,
            p.unit,
            p.cost_price_paise,
            p.selling_price_paise,
            p.tax_rate_bps,
            p.stock_qty_milli,
            p.reorder_level_milli,
            p.track_stock,
            p.is_active
        FROM products p
        LEFT JOIN categories c
            ON p.category_id = c.id
        WHERE 1=1
    """

    params = []

    if not show_archived:
        query += " AND p.is_active = 1"

    if search.strip():
        query += """
            AND (
                p.name LIKE ?
                OR p.sku LIKE ?
                OR p.barcode LIKE ?
            )
        """
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    query += " ORDER BY p.name"

    with session() as conn:
        return conn.execute(query, params).fetchall()


def add_product(
    sku,
    barcode,
    name,
    category_id,
    unit,
    cost_price_paise,
    selling_price_paise,
    tax_rate_bps,
    opening_stock_milli,
    reorder_level_milli,
    track_stock
):
    sku = sku.strip()
    name = name.strip()
    barcode = barcode.strip() or None

    if not sku or not name:
        raise ValueError("SKU and product name are required.")

    if cost_price_paise < 0 or selling_price_paise < 0:
        raise ValueError("Prices cannot be negative.")

    if not 0 <= tax_rate_bps <= 10000:
        raise ValueError("Invalid tax rate.")

    if opening_stock_milli < 0:
        raise ValueError("Opening stock cannot be negative.")

    if reorder_level_milli < 0:
        raise ValueError("Reorder level cannot be negative.")

    if not track_stock and opening_stock_milli != 0:
        raise ValueError(
            "Non-stock-tracked products cannot have opening stock."
        )

    with session() as conn:
        cur = conn.execute("""
            INSERT INTO products (
                sku,
                barcode,
                name,
                category_id,
                unit,
                cost_price_paise,
                selling_price_paise,
                tax_rate_bps,
                stock_qty_milli,
                reorder_level_milli,
                track_stock
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sku,
            barcode,
            name,
            category_id,
            unit,
            cost_price_paise,
            selling_price_paise,
            tax_rate_bps,
            opening_stock_milli,
            reorder_level_milli,
            int(track_stock)
        ))

        product_id = cur.lastrowid

        # Record opening stock.
        if opening_stock_milli > 0:
            conn.execute("""
                INSERT INTO stock_movements (
                    product_id,
                    movement_type,
                    quantity_delta_milli,
                    reference_type,
                    reason
                )
                VALUES (?, 'opening', ?, 'product', ?)
            """, (
                product_id,
                opening_stock_milli,
                "Opening stock"
            ))

        return product_id


def update_product(
    product_id,
    sku,
    barcode,
    name,
    category_id,
    unit,
    cost_price_paise,
    selling_price_paise,
    tax_rate_bps,
    reorder_level_milli,
    track_stock
):
    if not sku.strip() or not name.strip():
        raise ValueError("SKU and name are required.")

    if cost_price_paise < 0 or selling_price_paise < 0:
        raise ValueError("Prices cannot be negative.")

    if not 0 <= tax_rate_bps <= 10000:
        raise ValueError("Invalid tax rate.")

    if reorder_level_milli < 0:
        raise ValueError("Reorder level cannot be negative.")

    with session() as conn:
        row = conn.execute("""
            SELECT stock_qty_milli
            FROM products
            WHERE id = ? AND is_active = 1
        """, (product_id,)).fetchone()

        if row is None:
            raise ValueError("Product not found or archived.")

        # Existing stock cannot silently become untracked.
        if not track_stock and row["stock_qty_milli"] != 0:
            raise ValueError(
                "Stock must be zero before disabling stock tracking."
            )

        conn.execute("""
            UPDATE products
            SET
                sku = ?,
                barcode = ?,
                name = ?,
                category_id = ?,
                unit = ?,
                cost_price_paise = ?,
                selling_price_paise = ?,
                tax_rate_bps = ?,
                reorder_level_milli = ?,
                track_stock = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 1
        """, (
            sku.strip(),
            barcode.strip() or None,
            name.strip(),
            category_id,
            unit,
            cost_price_paise,
            selling_price_paise,
            tax_rate_bps,
            reorder_level_milli,
            int(track_stock),
            product_id
        ))


def archive_product(product_id):
    with session() as conn:
        conn.execute("""
            UPDATE products
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 1
        """, (product_id,))

        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            raise ValueError("Product not found or already archived.")


def restore_product(product_id):
    with session() as conn:
        conn.execute("""
            UPDATE products
            SET is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 0
        """, (product_id,))

        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            raise ValueError("Archived product not found.")


# ==============================================
# STOCK ADJUSTMENT
# ==============================================

def adjust_stock(product_id, delta_milli, reason):
    if delta_milli == 0:
        raise ValueError("Stock adjustment cannot be zero.")

    if not reason.strip():
        raise ValueError("Adjustment reason is required.")

    with session() as conn:
        product = conn.execute("""
            SELECT stock_qty_milli, track_stock, is_active
            FROM products
            WHERE id = ?
        """, (product_id,)).fetchone()

        if product is None or not product["is_active"]:
            raise ValueError("Active product not found.")

        if not product["track_stock"]:
            raise ValueError(
                "Stock tracking is disabled for this product."
            )

        new_stock = product["stock_qty_milli"] + delta_milli

        if new_stock < 0:
            raise ValueError("Insufficient stock for this adjustment.")

        conn.execute("""
            UPDATE products
            SET stock_qty_milli = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_stock, product_id))

        conn.execute("""
            INSERT INTO stock_movements (
                product_id,
                movement_type,
                quantity_delta_milli,
                reference_type,
                reason
            )
            VALUES (?, 'adjustment', ?, 'manual', ?)
        """, (
            product_id,
            delta_milli,
            reason.strip()
        ))


def get_stock_history(product_id):
    with session() as conn:
        return conn.execute("""
            SELECT
                movement_type,
                quantity_delta_milli,
                reference_type,
                reference_id,
                reason,
                movement_date
            FROM stock_movements
            WHERE product_id = ?
            ORDER BY id DESC
        """, (product_id,)).fetchall()


# ==============================================
# PRODUCT MANAGEMENT INTERFACE
# ==============================================

def show_products():
    st.title("📦 Product Management")
    st.caption("Manage your retail products and inventory.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Product List",
        "Add Product",
        "Edit / Archive",
        "Stock Adjustment"
    ])

    # ------------------------------------------
    # PRODUCT LIST
    # ------------------------------------------

    with tab1:
        search = st.text_input(
            "Search by name, SKU or barcode",
            key="product_search"
        )

        include_archived = st.checkbox(
            "Include archived products"
        )

        products = get_products(
            search,
            show_archived=include_archived
        )

        if products:
            df = pd.DataFrame([dict(p) for p in products])

            df["Selling Price"] = df[
                "selling_price_paise"
            ].apply(money)

            df["Cost Price"] = df[
                "cost_price_paise"
            ].apply(money)

            df["Stock"] = df[
                "stock_qty_milli"
            ].apply(lambda x: x / 1000)

            df["Tax (%)"] = df[
                "tax_rate_bps"
            ].apply(lambda x: x / 100)

            df["Stock Status"] = df.apply(
                lambda r: (
                    "Not tracked"
                    if not r["track_stock"]
                    else (
                        "Low stock"
                        if r["stock_qty_milli"]
                        <= r["reorder_level_milli"]
                        else "In stock"
                    )
                ),
                axis=1
            )

            st.dataframe(
                df[[
                    "sku",
                    "barcode",
                    "name",
                    "category",
                    "Selling Price",
                    "Cost Price",
                    "Stock",
                    "Tax (%)",
                    "Stock Status",
                    "is_active"
                ]],
                use_container_width=True,
                hide_index=True
            )

            st.caption(f"{len(products)} product(s) found.")
        else:
            st.info("No products found.")

    # ------------------------------------------
    # ADD PRODUCT
    # ------------------------------------------

    with tab2:
        categories = get_categories()

        with st.expander("Create a category", expanded=False):
            with st.form("add_category_form"):
                category_name = st.text_input("Category name")
                category_description = st.text_input(
                    "Description (optional)"
                )

                category_submit = st.form_submit_button(
                    "Create Category"
                )

                if category_submit:
                    try:
                        add_category(
                            category_name,
                            category_description
                        )
                        st.success("Category created.")
                        st.rerun()
                    except (ValueError, sqlite3.Error) as e:
                        st.error(str(e))

        categories = get_categories()

        category_options = {
            c["name"]: c["id"] for c in categories
        }

        with st.form("add_product_form"):
            sku = st.text_input("SKU *")
            barcode = st.text_input("Barcode (optional)")
            name = st.text_input("Product name *")

            category_name = st.selectbox(
                "Category",
                ["Uncategorized"] + list(category_options.keys())
            )

            unit = st.selectbox(
                "Unit",
                ["pcs", "kg", "g", "L", "mL", "box", "pack"]
            )

            c1, c2 = st.columns(2)

            with c1:
                cost = st.number_input(
                    "Cost price (₹)",
                    min_value=0.0,
                    value=0.0,
                    step=1.0
                )

                selling = st.number_input(
                    "Selling price (₹)",
                    min_value=0.0,
                    value=0.0,
                    step=1.0
                )

            with c2:
                tax_percent = st.number_input(
                    "Tax rate (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.5
                )

                opening_stock = st.number_input(
                    "Opening stock",
                    min_value=0.0,
                    value=0.0,
                    step=1.0
                )

            reorder = st.number_input(
                "Low-stock threshold",
                min_value=0.0,
                value=5.0,
                step=1.0
            )

            track_stock = st.checkbox(
                "Track inventory",
                value=True
            )

            submit = st.form_submit_button("Save Product")

            if submit:
                try:
                    category_id = category_options.get(
                        category_name
                    )

                    product_id = add_product(
                        sku=sku,
                        barcode=barcode,
                        name=name,
                        category_id=category_id,
                        unit=unit,
                        cost_price_paise=to_paise(cost),
                        selling_price_paise=to_paise(selling),
                        tax_rate_bps=int(
                            round(tax_percent * 100)
                        ),
                        opening_stock_milli=to_milli(
                            opening_stock
                        ),
                        reorder_level_milli=to_milli(reorder),
                        track_stock=track_stock
                    )

                    st.success(
                        f"Product saved successfully. ID: {product_id}"
                    )
                    st.rerun()

                except (ValueError, sqlite3.Error) as e:
                    st.error(f"Could not save product: {e}")

    # ------------------------------------------
    # EDIT / ARCHIVE
    # ------------------------------------------

    with tab3:
        active_products = get_products()

        if not active_products:
            st.info("No active products to edit.")
        else:
            product_map = {
                f"{p['sku']} — {p['name']}": p
                for p in active_products
            }

            selected_label = st.selectbox(
                "Select product",
                list(product_map.keys()),
                key="edit_product_select"
            )

            p = product_map[selected_label]

            categories = get_categories()
            category_options = {
                c["name"]: c["id"] for c in categories
            }

            category_names = list(category_options.keys())

            current_category = p["category"]
            if current_category not in category_options:
                category_names.insert(0, "Uncategorized")
                category_options["Uncategorized"] = None

            if not category_names:
                category_names = ["Uncategorized"]
                category_options["Uncategorized"] = None

            selected_category = st.selectbox(
                "Edit category",
                category_names,
                index=(
                    category_names.index(current_category)
                    if current_category in category_names
                    else 0
                ),
                key=f"edit_category_{p['id']}"
            )

            with st.form(f"edit_product_{p['id']}"):
                new_sku = st.text_input("SKU", value=p["sku"])
                new_barcode = st.text_input(
                    "Barcode",
                    value=p["barcode"] or ""
                )
                new_name = st.text_input(
                    "Product name",
                    value=p["name"]
                )
                new_unit = st.selectbox(
                    "Unit",
                    ["pcs", "kg", "g", "L", "mL", "box", "pack"],
                    index=(
                        ["pcs", "kg", "g", "L", "mL", "box", "pack"]
                        .index(p["unit"])
                        if p["unit"] in
                        ["pcs", "kg", "g", "L", "mL", "box", "pack"]
                        else 0
                    )
                )

                new_cost = st.number_input(
                    "Cost price (₹)",
                    min_value=0.0,
                    value=p["cost_price_paise"] / 100
                )

                new_selling = st.number_input(
                    "Selling price (₹)",
                    min_value=0.0,
                    value=p["selling_price_paise"] / 100
                )

                new_tax = st.number_input(
                    "Tax rate (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=p["tax_rate_bps"] / 100
                )

                new_reorder = st.number_input(
                    "Low-stock threshold",
                    min_value=0.0,
                    value=p["reorder_level_milli"] / 1000
                )

                new_tracking = st.checkbox(
                    "Track inventory",
                    value=bool(p["track_stock"])
                )

                save_edit = st.form_submit_button(
                    "Update Product"
                )

                if save_edit:
                    try:
                        update_product(
                            product_id=p["id"],
                            sku=new_sku,
                            barcode=new_barcode,
                            name=new_name,
                            category_id=category_options.get(
                                selected_category
                            ),
                            unit=new_unit,
                            cost_price_paise=to_paise(new_cost),
                            selling_price_paise=to_paise(new_selling),
                            tax_rate_bps=int(
                                round(new_tax * 100)
                            ),
                            reorder_level_milli=to_milli(
                                new_reorder
                            ),
                            track_stock=new_tracking
                        )

                        st.success("Product updated.")
                        st.rerun()

                    except (ValueError, sqlite3.Error) as e:
                        st.error(str(e))

            st.divider()
            st.warning("Archiving hides this product from active listings.")

            confirm_archive = st.checkbox(
                "Confirm archive",
                key=f"archive_confirm_{p['id']}"
            )

            if st.button(
                "Archive Product",
                disabled=not confirm_archive,
                key=f"archive_{p['id']}"
            ):
                try:
                    archive_product(p["id"])
                    st.success("Product archived.")
                    st.rerun()
                except (ValueError, sqlite3.Error) as e:
                    st.error(str(e))

    # ------------------------------------------
    # STOCK ADJUSTMENT
    # ------------------------------------------

    with tab4:
        tracked_products = [
            p for p in get_products()
            if p["track_stock"]
        ]

        if not tracked_products:
            st.info("No stock-tracked products found.")
        else:
            stock_map = {
                f"{p['sku']} — {p['name']}": p
                for p in tracked_products
            }

            label = st.selectbox(
                "Choose product",
                list(stock_map.keys()),
                key="stock_product"
            )

            p = stock_map[label]

            st.metric(
                "Current stock",
                f"{p['stock_qty_milli'] / 1000:.3f} {p['unit']}"
            )

            with st.form("stock_adjustment_form"):
                direction = st.radio(
                    "Adjustment",
                    ["Increase", "Decrease"],
                    horizontal=True
                )

                qty = st.number_input(
                    "Quantity",
                    min_value=0.001,
                    value=1.0,
                    step=1.0
                )

                reason = st.text_input(
                    "Reason (required)",
                    placeholder="Physical stock count correction"
                )

                adjust_submit = st.form_submit_button(
                    "Record Adjustment"
                )

                if adjust_submit:
                    try:
                        delta = to_milli(qty)

                        if direction == "Decrease":
                            delta = -delta

                        if delta == 0:
                            raise ValueError(
                                "Quantity is too small."
                            )

                        adjust_stock(
                            product_id=p["id"],
                            delta_milli=delta,
                            reason=reason
                        )

                        st.success("Stock adjustment recorded.")
                        st.rerun()

                    except (ValueError, sqlite3.Error) as e:
                        st.error(str(e))

            st.subheader("Stock movement history")

            history = get_stock_history(p["id"])

            if history:
                history_df = pd.DataFrame(
                    [dict(row) for row in history]
                )

                history_df["Quantity Change"] = (
                    history_df["quantity_delta_milli"]
                    .apply(lambda x: f"{x / 1000:+.3f}")
                )

                st.dataframe(
                    history_df[[
                        "movement_date",
                        "movement_type",
                        "Quantity Change",
                        "reason",
                        "reference_type",
                        "reference_id"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No stock movements recorded.")
