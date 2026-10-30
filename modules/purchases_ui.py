
# modules/purchase_ui.py

import streamlit as st
import pandas as pd

from modules.purchases import (
    list_suppliers,
    create_supplier,
    list_purchase_orders,
    receive_purchase,
)


def show_purchases():

    st.title("Purchase & Supplier Management")

    tab1, tab2, tab3 = st.tabs([
        "Suppliers",
        "Purchase Orders",
        "Receive Stock",
    ])

    with tab1:
        st.subheader("Supplier Management")

        with st.form("supplier_form"):
            name = st.text_input("Supplier Name")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            address = st.text_area("Address")

            submit = st.form_submit_button("Add Supplier")

            if submit:
                try:
                    create_supplier(
                        name=name,
                        phone=phone or None,
                        email=email or None,
                        address=address or None,
                    )
                    st.success("Supplier created.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Supplier creation failed: {e}")

        search = st.text_input("Search Suppliers")

        try:
            suppliers = list_suppliers(search)
            if suppliers:
                st.dataframe(
                    pd.DataFrame(suppliers),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No suppliers found.")
        except Exception as e:
            st.error(f"Could not load suppliers: {e}")

    with tab2:
        st.subheader("Purchase Orders")

        try:
            orders = list_purchase_orders()

            if orders:
                st.dataframe(
                    pd.DataFrame(orders),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No purchase orders found.")

        except Exception as e:
            st.error(f"Could not load orders: {e}")

        st.info(
            "Purchase order creation requires your purchase_items "
            "and purchase_orders column definitions. Add this after "
            "verifying those fields."
        )

    with tab3:
        st.subheader("Receive Purchase")

        order_id = st.number_input(
            "Purchase Order ID",
            min_value=1,
            step=1,
        )

        confirmation = st.checkbox(
            "I confirm that the full order has physically arrived."
        )

        if st.button("Receive Entire Order", type="primary"):
            if not confirmation:
                st.warning("Please confirm physical receipt.")
            else:
                try:
                    result = receive_purchase(
                        int(order_id),
                        received_by=None,
                    )
                    st.success(
                        f"Received order {result['purchase_order_id']}."
                    )
                    st.rerun()

                except ValueError as e:
                    st.error(str(e))

                except Exception:
                    st.error(
                        "Receiving failed. Check application logs "
                        "and verify the database schema."
                    )
