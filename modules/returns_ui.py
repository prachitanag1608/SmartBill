
# modules/returns_ui.py

import streamlit as st
import pandas as pd

from modules.returns import (
    find_returnable_invoices,
    get_original_invoice_items,
)


def show_returns():

    st.title("Sales Returns & Refunds")

    search = st.text_input(
        "Search Original Invoice",
        placeholder="Enter invoice number",
    )

    try:
        invoices = find_returnable_invoices(search)

        if invoices:
            st.dataframe(
                pd.DataFrame(invoices),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No matching issued invoices.")

    except Exception as e:
        st.error(f"Unable to load invoices: {e}")
        return

    st.divider()
    st.subheader("Inspect Original Invoice")

    invoice_id = st.number_input(
        "Invoice Database ID",
        min_value=1,
        step=1,
        key="return_invoice_id",
    )

    if st.button("Load Invoice Items"):
        try:
            details = get_original_invoice_items(
                int(invoice_id)
            )

            st.session_state["return_invoice_details"] = details

        except Exception as e:
            st.error(str(e))

    details = st.session_state.get("return_invoice_details")

    if details:
        st.subheader("Original Items")
        st.dataframe(
            pd.DataFrame(details["items"]),
            use_container_width=True,
            hide_index=True,
        )

        st.info(
            "Invoice inspection is enabled. Return submission "
            "will be enabled after the refund and return schema "
            "is verified."
        )
