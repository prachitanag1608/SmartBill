# modules/billing_ui.py

import uuid
import sqlite3
from decimal import Decimal

import streamlit as st
import pandas as pd
import numpy as np
import zxingcpp

from PIL import Image
from io import BytesIO

from modules.db import get_connection
from modules.billing import (
    list_customers,
    search_products,
    checkout,
    get_invoice,
    rupees_to_paise,
    quantity_to_milli,
    calculate_bill,
)


# ==================================================
# SMARTBILL POS HELPERS
# ==================================================

def money(paise):
    return f"₹{int(paise or 0) / 100:,.2f}"


def get_value(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def get_logged_in_user():
    return st.session_state.get("auth_user")


def get_user_id(username):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, username, full_name, role, is_active
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if not row or not row["is_active"]:
            return None

        return dict(row)
    finally:
        conn.close()


def initialize_billing_session():
    defaults = {
        "sb_cart": [],
        "sb_checkout_key": str(uuid.uuid4()),
        "sb_bill_notes": "",
        "sb_checkout_success": False,
        "sb_last_invoice_id": None,
        "sb_product_search": "",
        "sb_bill_discount_value": 0.0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_cart():
    st.session_state.sb_cart = []
    st.session_state.sb_checkout_key = str(uuid.uuid4())
    st.session_state.sb_bill_discount_value = 0.0
    st.session_state.sb_bill_notes = ""
    st.session_state.sb_product_search = ""


def find_cart_item(product_id):
    for index, item in enumerate(st.session_state.sb_cart):
        if int(item["product_id"]) == int(product_id):
            return index
    return None


def cart_quantity_milli(product_id):
    index = find_cart_item(product_id)
    if index is None:
        return 0
    return st.session_state.sb_cart[index]["quantity_milli"]


# ==================================================
# CART OPERATIONS
# ==================================================

def add_to_cart(product, quantity):
    product_id = int(get_value(product, "id"))
    quantity_milli = quantity_to_milli(quantity)

    if quantity_milli <= 0:
        st.error("Quantity must be greater than zero.")
        return False

    stock_tracked = bool(get_value(product, "track_stock", 1))
    available_stock = int(
        get_value(product, "stock_qty_milli", 0)
    )

    existing_index = find_cart_item(product_id)
    current_quantity = cart_quantity_milli(product_id)

    if stock_tracked:
        if current_quantity + quantity_milli > available_stock:
            st.error("Requested quantity exceeds available stock.")
            return False

    if existing_index is not None:
        st.session_state.sb_cart[existing_index][
            "quantity_milli"
        ] += quantity_milli
    else:
        st.session_state.sb_cart.append({
            "product_id": product_id,
            "product_name": get_value(product, "name", ""),
            "sku": get_value(product, "sku", ""),
            "quantity_milli": quantity_milli,
            "unit_price_paise": int(
                get_value(product, "selling_price_paise", 0)
            ),
            "tax_rate_bps": int(
                get_value(product, "tax_rate_bps", 0)
            ),
            "track_stock": stock_tracked,
            "available_stock_milli": available_stock,
        })

    st.session_state.sb_checkout_key = str(uuid.uuid4())
    return True


def remove_from_cart(product_id):
    st.session_state.sb_cart = [
        item for item in st.session_state.sb_cart
        if int(item["product_id"]) != int(product_id)
    ]
    st.session_state.sb_checkout_key = str(uuid.uuid4())


def update_cart_quantity(product_id, new_quantity):
    index = find_cart_item(product_id)

    if index is None:
        return False

    item = st.session_state.sb_cart[index]
    new_quantity_milli = quantity_to_milli(new_quantity)

    if item["track_stock"]:
        if new_quantity_milli > item["available_stock_milli"]:
            st.error("Quantity exceeds available stock.")
            return False

    item["quantity_milli"] = new_quantity_milli
    st.session_state.sb_checkout_key = str(uuid.uuid4())
    return True


# ==================================================
# BILL CALCULATIONS
# ==================================================

def get_cart_bill(discount_paise=0):
    items = []

    for item in st.session_state.sb_cart:
        items.append({
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "sku": item["sku"],
            "quantity_milli": item["quantity_milli"],
            "unit_price_paise": item["unit_price_paise"],
            "tax_rate_bps": item["tax_rate_bps"],
            "discount_bps": 0,
            "track_stock": item["track_stock"],
        })

    if not items:
        return None

    return calculate_bill(
        items,
        bill_discount_paise=discount_paise,
    )


# ==================================================
# PRODUCT SEARCH
# ==================================================

def show_product_search():
    st.markdown("### 🔎 Find Products")

    search_query = st.text_input(
        "Search product",
        placeholder="Search by product name, SKU or barcode...",
        key="sb_product_search",
    )

    if not search_query.strip():
        st.caption("Search for products to add them to your cart.")
        return

    try:
        products = search_products(search_query.strip())
    except Exception as exc:
        st.error(f"Unable to search products: {exc}")
        return

    if not products:
        st.warning("No matching products found.")
        return

    st.caption(f"{len(products)} matching product(s)")

    # Product selection
    product_options = {
        int(get_value(p, "id")): p
        for p in products
    }

    product_ids = list(product_options.keys())

    selected_id = st.selectbox(
        "Select product",
        options=product_ids,
        format_func=lambda pid: (
            f"{get_value(product_options[pid], 'name', 'Product')} "
            f"• {money(get_value(product_options[pid], 'selling_price_paise', 0))}"
        ),
        key="sb_selected_product",
    )

    product = product_options[selected_id]

    stock = int(get_value(product, "stock_qty_milli", 0))
    track_stock = bool(get_value(product, "track_stock", 1))

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div class="pos-panel">
                <div class="pos-label">PRODUCT</div>
                <div style="font-size:19px;font-weight:800;margin-top:8px;">
                    {get_value(product, 'name', 'Product')}
                </div>
                <div style="color:#718087;font-size:13px;margin-top:4px;">
                    SKU: {get_value(product, 'sku', '-')}
                </div>
                <div class="pos-total" style="margin-top:12px;">
                    {money(get_value(product, 'selling_price_paise', 0))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="pos-panel">
                <div class="pos-label">INVENTORY</div>
                <div style="font-size:22px;font-weight:800;margin-top:8px;">
                    {"Tracked" if track_stock else "Not tracked"}
                </div>
                <div style="color:#718087;font-size:13px;margin-top:8px;">
                    {"Available: " + str(stock / 1000) if track_stock else "Stock tracking disabled"}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if track_stock and stock <= 0:
        st.error("This product is out of stock.")
        return

    quantity = st.number_input(
        "Quantity to add",
        min_value=0.001,
        value=1.0,
        step=1.0,
        format="%.3f",
        key="sb_product_quantity",
    )

    if st.button(
        "＋ Add to Cart",
        type="primary",
        use_container_width=True,
        key="sb_add_to_cart",
    ):
        if add_to_cart(product, quantity):
            st.success("Product added to cart.")
            st.rerun()


# ==================================================
# BARCODE SCANNER
# ==================================================

def find_product_by_barcode(barcode):
    conn = get_connection()

    try:
        return conn.execute(
            """
            SELECT *
            FROM products
            WHERE barcode = ?
              AND is_active = 1
            LIMIT 1
            """,
            (barcode,),
        ).fetchone()
    finally:
        conn.close()


def show_barcode_scanner():
    st.markdown("### 📷 Barcode Scanner")

    st.caption(
        "Capture a barcode image with your camera. "
        "Camera permission is required."
    )

    camera_image = st.camera_input(
        "Capture barcode",
        key="smartbill_barcode_camera",
    )

    if camera_image is None:
        return

    try:
        image = Image.open(
            BytesIO(camera_image.getvalue())
        ).convert("RGB")

        image_array = np.array(image)
        results = zxingcpp.read_barcodes(image_array)

        if not results:
            st.warning(
                "Barcode not detected. Improve lighting and focus."
            )
            return

        barcode = results[0].text.strip()

        if not barcode:
            st.warning("Barcode could not be decoded.")
            return

        st.success(f"Detected barcode: {barcode}")

        product = find_product_by_barcode(barcode)

        if not product:
            st.error(
                "Product not found. Check the barcode saved "
                "in the Products section."
            )
            return

        product = dict(product)

        st.markdown("#### Matched Product")

        st.write(f"**Product:** {product['name']}")
        st.write(f"**SKU:** {product['sku']}")
        st.write(
            f"**Price:** {money(product['selling_price_paise'])}"
        )

        if product["track_stock"]:
            st.caption(
                f"Available stock: "
                f"{product['stock_qty_milli'] / 1000:g}"
            )

            if product["stock_qty_milli"] <= 0:
                st.error("This product is out of stock.")
                return

        quantity = st.number_input(
            "Scan quantity",
            min_value=0.001,
            value=1.0,
            step=1.0,
            format="%.3f",
            key="sb_scanned_product_quantity",
        )

        if st.button(
            "＋ Add Scanned Product",
            type="primary",
            use_container_width=True,
            key="sb_add_scanned_product",
        ):
            if add_to_cart(product, quantity):
                st.success("Scanned product added.")
                st.rerun()

    except Exception as exc:
        st.error(f"Unable to process barcode: {exc}")


# ==================================================
# CUSTOMER SELECTION
# ==================================================

def show_customer_selection():
    st.markdown("### 👤 Customer")

    try:
        customers = list_customers()
    except Exception as exc:
        st.error(f"Unable to load customers: {exc}")
        return None

    customer_options = [
        ("Walk-in Customer", None)
    ]

    for customer in customers:
        customer_id = int(get_value(customer, "id"))
        name = get_value(customer, "name", "Customer")
        phone = get_value(customer, "phone", "")

        label = name

        if phone:
            label += f" • {phone}"

        customer_options.append((label, customer_id))

    labels = [x[0] for x in customer_options]

    selected_label = st.selectbox(
        "Select customer",
        labels,
        key="sb_customer_selection",
    )

    selected_customer_id = dict(customer_options)[selected_label]

    if selected_customer_id is None:
        st.caption("Billing as Walk-in Customer.")
    else:
        st.caption("Customer selected.")

    return selected_customer_id


# ==================================================
# CART DISPLAY
# ==================================================

def show_cart():
    cart = st.session_state.sb_cart

    st.markdown(
        f"### 🛒 Current Order  ·  {len(cart)} item(s)"
    )

    if not cart:
        st.info(
            "Your cart is empty. Add products using the search "
            "or barcode scanner."
        )
        return

    for item in list(cart):
        product_id = item["product_id"]

        with st.container(border=True):
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"**{item['product_name']}**")
                st.caption(
                    f"SKU: {item['sku']}  |  "
                    f"Unit price: {money(item['unit_price_paise'])}"
                )

            with col2:
                st.markdown(
                    f"**{money((item['quantity_milli'] * item['unit_price_paise']) // 1000)}**"
                )

            qty_col, remove_col = st.columns([3, 1])

            with qty_col:
                new_qty = st.number_input(
                    "Quantity",
                    min_value=0.001,
                    value=item["quantity_milli"] / 1000,
                    step=1.0,
                    format="%.3f",
                    key=f"sb_cart_qty_{product_id}",
                )

                if Decimal(str(new_qty)) != Decimal(
                    str(item["quantity_milli"] / 1000)
                ):
                    if st.button(
                        "Update",
                        key=f"sb_cart_update_{product_id}",
                    ):
                        if update_cart_quantity(product_id, new_qty):
                            st.success("Quantity updated.")
                            st.rerun()

            with remove_col:
                st.write("")
                st.write("")

                if st.button(
                    "🗑️",
                    key=f"sb_remove_{product_id}",
                    help="Remove product",
                ):
                    remove_from_cart(product_id)
                    st.rerun()

    if st.button(
        "Clear Entire Cart",
        use_container_width=True,
        key="sb_clear_cart",
    ):
        reset_cart()
        st.rerun()


# ==================================================
# CHECKOUT SUMMARY
# ==================================================

def show_checkout_summary():
    st.markdown("### 🧾 Bill Summary")

    discount_rupees = st.number_input(
        "Bill discount (₹)",
        min_value=0.0,
        value=float(st.session_state.sb_bill_discount_value),
        step=1.0,
        key="sb_discount_widget",
    )

    st.session_state.sb_bill_discount_value = discount_rupees

    discount_paise = rupees_to_paise(discount_rupees)

    try:
        bill = get_cart_bill(discount_paise)
    except (ValueError, TypeError) as exc:
        st.error(str(exc))
        return None

    if bill is None:
        return None

    st.markdown('<div class="pos-panel">', unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Subtotal",
            money(bill["subtotal_paise"]),
        )

    with c2:
        st.metric(
            "Tax",
            money(bill["tax_paise"]),
        )

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        st.caption("Discount")
        st.markdown(
            f"**-{money(discount_paise)}**"
        )

    with c2:
        st.caption("TOTAL TO PAY")
        st.markdown(
            f'<div class="pos-total">{money(bill["total_paise"])}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    return bill


# ==================================================
# PAYMENT
# ==================================================

def show_payment_section(total_paise):
    st.markdown("### 💳 Payment")

    payment_option = st.radio(
        "Payment type",
        ["Full Payment", "Partial Payment", "Pay Later"],
        horizontal=True,
        key="sb_payment_type",
    )

    payment_amount_paise = 0

    if payment_option == "Full Payment":
        payment_amount_paise = total_paise

    elif payment_option == "Partial Payment":
        if total_paise <= 0:
            st.info("Payment is not required for a zero-value bill.")
            payment_amount_paise = 0
        else:
            amount_rupees = st.number_input(
                "Amount received (₹)",
                min_value=0.01,
                max_value=total_paise / 100,
                value=min(100.0, total_paise / 100),
                step=1.0,
                key="sb_partial_payment_amount",
            )

            payment_amount_paise = rupees_to_paise(amount_rupees)

            if payment_amount_paise > total_paise:
                st.error("Payment exceeds the bill total.")
                return None

    else:
        st.caption("Invoice will remain unpaid.")

    method = st.selectbox(
        "Payment method",
        ["cash", "upi", "card", "bank_transfer", "other"],
        format_func=lambda x: x.replace("_", " ").title(),
        key="sb_payment_method",
    )

    notes = st.text_area(
        "Bill notes (optional)",
        key="sb_bill_notes_input",
        placeholder="Add a note for this invoice...",
    )

    return {
        "payment_amount_paise": payment_amount_paise,
        "payment_method": method,
        "notes": notes,
    }


# ==================================================
# INVOICE SUCCESS
# ==================================================

def show_successful_invoice(invoice_id):
    st.success("🎉 Bill created successfully!")

    try:
        result = get_invoice(invoice_id)
    except Exception as exc:
        st.warning(
            f"Bill was created, but invoice details could not "
            f"be loaded: {exc}"
        )
        return

    if not result:
        st.info(f"Invoice ID: {invoice_id}")
        return

    # get_invoice() returns a wrapper containing invoice,
    # items, payments, paid_paise and balance_paise.
    invoice = result.get("invoice", result)

    invoice_number = invoice.get(
        "invoice_number", str(invoice_id)
    )

    total_paise = invoice.get("total_paise", 0)

    st.markdown("## Invoice Generated")

    st.markdown(
        f"""
        <div class="pos-panel">
            <div class="pos-label">INVOICE NUMBER</div>
            <div style="font-size:22px;font-weight:800;margin-top:8px;">
                {invoice_number}
            </div>
            <div style="margin-top:16px;color:#718087;">
                BILL TOTAL
            </div>
            <div class="pos-total">
                {money(total_paise)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Paid",
            money(result.get("paid_paise", 0)),
        )

    with col2:
        st.metric(
            "Balance",
            money(result.get("balance_paise", total_paise)),
        )

    st.write(
        f"**Payment Status:** "
        f"{invoice.get('payment_status', 'N/A').title()}"
    )

    items = result.get("items", [])

    if items:
        st.markdown("#### Purchased Items")

        rows = []

        for item in items:
            rows.append({
                "Product": item.get("product_name", ""),
                "SKU": item.get("sku", ""),
                "Quantity": item.get("quantity_milli", 0) / 1000,
                "Amount": money(item.get("line_total_paise", 0)),
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )


# ==================================================
# MAIN BILLING SCREEN
# ==================================================

def show_billing():
    initialize_billing_session()

    auth_user = get_logged_in_user()

    if not auth_user:
        st.error("Please log in to access billing.")
        st.stop()

    username = auth_user.get("username")

    if not username:
        st.error("Authenticated username is missing.")
        st.stop()

    try:
        db_user = get_user_id(username)
    except sqlite3.Error as exc:
        st.error(f"Unable to verify user: {exc}")
        st.stop()

    if not db_user:
        st.error("Account inactive or unavailable. Please log in again.")
        st.stop()

    # ----------------------------------------------
    # HEADER
    # ----------------------------------------------

    st.markdown(
        """
        <div style="margin-bottom:8px;">
            <div style="font-size:12px;letter-spacing:1.5px;
                        font-weight:700;color:#08A99F;">
                SMARTBILL  /  POINT OF SALE
            </div>
            <div style="font-size:32px;font-weight:850;
                        line-height:1.3;">
                New Bill
            </div>
            <div style="color:#718087;font-size:14px;">
                Create an invoice, add products and complete checkout.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        f"👤 {db_user['full_name']}  ·  "
        f"{db_user['role'].title()}"
    )

    if st.session_state.get("sb_checkout_success"):
        invoice_id = st.session_state.get("sb_last_invoice_id")

        if invoice_id is not None:
            show_successful_invoice(invoice_id)

        if st.button(
            "＋ Create Another Bill",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.sb_checkout_success = False
            st.session_state.sb_last_invoice_id = None
            reset_cart()
            st.rerun()

        return

    st.divider()

    # ----------------------------------------------
    # MAIN POS LAYOUT
    # ----------------------------------------------

    left, right = st.columns([1.5, 1], gap="large")

    # LEFT: PRODUCT STATION
    with left:
        st.markdown("## 🛍️ Product Station")

        with st.expander(
            "📷 Scan Barcode",
            expanded=False,
        ):
            show_barcode_scanner()

        show_product_search()

    # RIGHT: CUSTOMER
    with right:
        with st.container(border=True):
            selected_customer_id = show_customer_selection()

    st.divider()

    # ----------------------------------------------
    # CART
    # ----------------------------------------------

    show_cart()

    if not st.session_state.sb_cart:
        return

    st.divider()

    # ----------------------------------------------
    # CHECKOUT AND SUMMARY
    # ----------------------------------------------

    col1, col2 = st.columns([1.2, 1], gap="large")

    with col1:
        with st.container(border=True):
            bill = show_checkout_summary()

    if bill is None:
        return

    with col2:
        with st.container(border=True):
            payment = show_payment_section(
                bill["total_paise"]
            )

    if payment is None:
        return

    st.divider()

    # ----------------------------------------------
    # FINAL CONFIRMATION
    # ----------------------------------------------

    st.markdown("## ✅ Checkout")

    subtotal = bill["subtotal_paise"]
    discount = bill["discount_paise"]
    tax = bill["tax_paise"]
    total = bill["total_paise"]
    paid = payment["payment_amount_paise"]
    balance = total - paid

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Bill Total", money(total))

    with col2:
        st.metric("Payment", money(paid))

    with col3:
        st.metric("Outstanding", money(balance))

    with st.expander("Review bill details"):
        st.write(f"Subtotal: {money(subtotal)}")
        st.write(f"Discount: {money(discount)}")
        st.write(f"Tax: {money(tax)}")
        st.write(f"Final Total: {money(total)}")
        st.write(f"Payment Method: {payment['payment_method'].title()}")

    st.warning(
        "Please verify the bill. Confirming will issue the invoice "
        "and update inventory."
    )

    if st.button(
        "✓  Confirm & Generate Bill",
        type="primary",
        use_container_width=True,
        key="sb_confirm_checkout",
    ):
        if not st.session_state.sb_cart:
            st.error("Your cart is empty.")
            st.stop()

        try:
            created_by = int(db_user["id"])

            items = [
                {
                    "product_id": int(item["product_id"]),
                    "quantity_milli": int(item["quantity_milli"]),
                }
                for item in st.session_state.sb_cart
            ]

            checkout_result = checkout(
                items=items,
                customer_id=selected_customer_id,
                bill_discount_paise=discount,
                payment_amount_paise=paid,
                payment_method=payment["payment_method"],
                payment_reference=None,
                notes=payment["notes"],
                created_by=created_by,
                idempotency_key=st.session_state.sb_checkout_key,
            )

            # checkout() returns a dictionary, not a plain ID.
            invoice_id = (
                checkout_result.get("id")
                if isinstance(checkout_result, dict)
                else checkout_result
            )

            if invoice_id is None:
                raise ValueError(
                    "Checkout returned no invoice ID."
                )

            st.session_state.sb_last_invoice_id = invoice_id
            st.session_state.sb_checkout_success = True

            # Clear the cart only after successful checkout.
            reset_cart()

            st.rerun()

        except Exception as exc:
            st.error(f"Checkout failed: {exc}")

            st.info(
                "If the operation was interrupted, check your invoice "
                "records before retrying."
            )


# ==================================================
# COMPATIBILITY ENTRY POINT
# ==================================================

def show_new_bill():
    show_billing()
