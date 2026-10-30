import streamlit as st
from modules.dashboard import get_dashboard_data


def rupees(paise):
    return f"₹{int(paise or 0) / 100:,.2f}"


def show_dashboard():
    st.title("Dashboard")
    st.caption("SmartBill business overview")

    try:
        data = get_dashboard_data()
    except Exception as e:
        st.error(f"Unable to load dashboard: {e}")
        return

    sales = data["sales"]
    payments = data["payments"]
    inventory = data["inventory"]
    outstanding = data["outstanding"]

    c1, c2, c3 = st.columns(3)

    c1.metric("Today's Sales", rupees(sales["sales_paise"]))
    c2.metric("Invoices Today", sales["invoice_count"])
    c3.metric(
        "Payments Collected Today",
        rupees(payments["collected_paise"])
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Outstanding Balance",
        rupees(outstanding["outstanding_paise"])
    )
    c2.metric("Low Stock", inventory["low_stock"])
    c3.metric("Out of Stock", inventory["out_of_stock"])

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Recent Invoices")

        recent = data["recent_invoices"]

        if recent:
            st.dataframe(
                recent,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No issued invoices yet.")

    with right:
        st.subheader("Top Products")

        top = data["top_products"]

        if top:
            import pandas as pd

            df = pd.DataFrame(top)
            df["Sales ₹"] = df["sales_paise"] / 100
            df["Quantity Sold"] = (
                df["quantity_sold_milli"] / 1000
            )

            st.dataframe(
                df[
                    [
                        "product_name",
                        "sku",
                        "Quantity Sold",
                        "Sales ₹"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No sales records yet.")