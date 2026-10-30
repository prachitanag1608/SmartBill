
# modules/inventory_ui.py

import streamlit as st
import pandas as pd

from modules.inventory import (
    list_inventory,
    inventory_summary,
    get_stock_movements,
    adjust_stock,
)


def quantity(milli):
    return int(milli or 0) / 1000


def money(paise):
    return f"Rs. {int(paise or 0) / 100:,.2f}"


def show_inventory():

    st.title("Inventory Management")
    st.caption(
        "Monitor stock, adjust quantities and track inventory movements."
    )

    # -----------------------------
    # Inventory summary
    # -----------------------------
    try:
        summary = inventory_summary()
    except Exception as e:
        st.error(f"Unable to load inventory summary: {e}")
        return

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Active Products",
        summary["active_products"],
    )

    c2.metric(
        "Low Stock",
        summary["low_stock"],
    )

    c3.metric(
        "Out of Stock",
        summary["out_of_stock"],
    )

    c4.metric(
        "Estimated Stock Value",
        money(summary["stock_value_paise"]),
    )

    st.caption(
        "Stock value is an estimate using current product costs "
        "for tracked products."
    )

    st.divider()

    # -----------------------------
    # Tabs
    # -----------------------------
    tab1, tab2, tab3 = st.tabs([
        "Stock Overview",
        "Stock Adjustment",
        "Movement History",
    ])

    # ===================================
    # TAB 1: Stock Overview
    # ===================================
    with tab1:

        st.subheader("Stock Overview")

        search = st.text_input(
            "Search Product",
            placeholder="Search by name, SKU or barcode",
            key="inventory_search",
        )

        stock_status = st.selectbox(
            "Stock Status",
            [
                "All",
                "In Stock",
                "Low Stock",
                "Out of Stock",
                "Untracked",
            ],
            key="inventory_status",
        )

        try:
            inventory = list_inventory(
                search=search,
                stock_status=stock_status,
            )
        except Exception as e:
            st.error(f"Unable to load products: {e}")
            inventory = []

        if inventory:

            display_rows = []

            for item in inventory:
                display_rows.append({
                    "ID": item["id"],
                    "SKU": item["sku"],
                    "Product": item["name"],
                    "Category": item["category_name"] or "-",
                    "Unit": item["unit"],
                    "Stock": (
                        quantity(item["stock_qty_milli"])
                        if item["track_stock"]
                        else "Not tracked"
                    ),
                    "Reorder Level": (
                        quantity(item["reorder_level_milli"])
                        if item["track_stock"]
                        else "-"
                    ),
                    "Selling Price": money(
                        item["selling_price_paise"]
                    ),
                    "Status": item["stock_status"],
                })

            st.dataframe(
                pd.DataFrame(display_rows),
                use_container_width=True,
                hide_index=True,
            )

            csv = pd.DataFrame(display_rows).to_csv(index=False)

            st.download_button(
                "Export Inventory CSV",
                data=csv,
                file_name="smartbill_inventory.csv",
                mime="text/csv",
            )

        else:
            st.info("No matching inventory products found.")

    # ===================================
    # TAB 2: Stock Adjustment
    # ===================================
    with tab2:

        st.subheader("Physical Stock Adjustment")

        st.warning(
            "Use this section only after physically counting stock. "
            "Sales and purchases must use their own workflows."
        )

        try:
            tracked_products = [
                item
                for item in list_inventory()
                if item["track_stock"]
            ]
        except Exception as e:
            st.error(f"Unable to load products: {e}")
            tracked_products = []

        if not tracked_products:
            st.info("No tracked active products are available.")

        else:

            options = {
                f"{p['name']} | {p['sku']} | "
                f"Stock: {quantity(p['stock_qty_milli'])}": p
                for p in tracked_products
            }

            selected = st.selectbox(
                "Select Product",
                list(options.keys()),
                key="adjust_product",
            )

            product = options[selected]

            current_stock = quantity(
                product["stock_qty_milli"]
            )

            st.metric(
                "Current Stock",
                f"{current_stock:g} {product['unit']}",
            )

            st.caption(
                "Enter the new physical stock quantity. "
                "The system records only the difference."
            )

            with st.form("stock_adjustment_form"):

                new_stock = st.number_input(
                    "New Physical Quantity",
                    min_value=0.0,
                    value=float(current_stock),
                    step=1.0,
                    format="%.3f",
                )

                reason = st.text_area(
                    "Reason for Adjustment",
                    placeholder=(
                        "Example: Physical stock count correction"
                    ),
                    max_chars=500,
                )

                confirmed = st.checkbox(
                    "I confirm that the physical quantity has been checked."
                )

                submit = st.form_submit_button(
                    "Save Stock Adjustment",
                    type="primary",
                )

                if submit:

                    # Convert decimal input to milli-units.
                    # Reject values with more than 3 decimals.
                    scaled = round(new_stock * 1000)

                    if abs(new_stock * 1000 - scaled) > 1e-7:
                        st.error(
                            "Quantity cannot have more than 3 decimal places."
                        )

                    elif not confirmed:
                        st.error(
                            "Please confirm the physical stock count."
                        )

                    elif not reason.strip():
                        st.error(
                            "Adjustment reason is required."
                        )

                    else:
                        try:
                            result = adjust_stock(
                                product_id=product["id"],
                                new_quantity_milli=scaled,
                                reason=reason,
                                # Replace with logged-in user ID
                                # when authentication is connected.
                                created_by=None,
                            )

                            st.success(
                                f"Stock updated for "
                                f"{result['product_name']}. "
                                f"Adjustment: "
                                f"{result['delta_milli'] / 1000:g}"
                            )

                            st.rerun()

                        except ValueError as e:
                            st.error(str(e))

                        except Exception:
                            st.error(
                                "Stock adjustment failed. "
                                "No change should be assumed. "
                                "Check the application logs."
                            )

    # ===================================
    # TAB 3: Movement History
    # ===================================
    with tab3:

        st.subheader("Stock Movement History")

        history_filter = st.selectbox(
            "History Filter",
            ["All Products"] + [
                f"{p['name']} | {p['sku']}"
                for p in tracked_products
            ],
            key="movement_filter",
        )

        product_id = None

        if history_filter != "All Products":
            history_product = next(
                p for p in tracked_products
                if (
                    f"{p['name']} | {p['sku']}"
                    == history_filter
                )
            )
            product_id = history_product["id"]

        try:
            movements = get_stock_movements(
                product_id=product_id,
                limit=500,
            )
        except Exception as e:
            st.error(f"Unable to load stock history: {e}")
            movements = []

        if movements:

            movement_rows = []

            for m in movements:
                movement_rows.append({
                    "Movement ID": m["id"],
                    "Product": m["product_name"],
                    "SKU": m["sku"],
                    "Type": m["movement_type"],
                    "Quantity Change": quantity(
                        m["quantity_delta_milli"]
                    ),
                    "Reference": (
                        f"{m['reference_type'] or '-'} / "
                        f"{m['reference_id'] or '-'}"
                    ),
                    "Reason": m["reason"] or "-",
                    "Date": m["created_at"],
                    "User ID": m["created_by"],
                })

            st.dataframe(
                pd.DataFrame(movement_rows),
                use_container_width=True,
                hide_index=True,
            )

            csv = pd.DataFrame(movement_rows).to_csv(index=False)

            st.download_button(
                "Export Movement History CSV",
                data=csv,
                file_name="smartbill_stock_movements.csv",
                mime="text/csv",
            )

        else:
            st.info("No stock movements found.")
