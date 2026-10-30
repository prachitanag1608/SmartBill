
# modules/reports_ui.py

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from modules.reports import (
    sales_summary,
    payment_summary,
    outstanding_summary,
    top_selling_products,
    daily_sales,
)


def money(paise):
    return f"₹{int(paise or 0) / 100:,.2f}"


def show_reports():

    st.title("SmartBill Reports & Analytics")

    today = date.today()

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=today - timedelta(days=29),
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=today,
        )

    if start_date > end_date:
        st.error("Start date cannot exceed end date.")
        return

    start = start_date.isoformat()
    end = end_date.isoformat()

    try:
        sales = sales_summary(start, end)
        payments = payment_summary(start, end)
        outstanding = outstanding_summary()
        top_products = top_selling_products(start, end)
        trend = daily_sales(start, end)

    except Exception as e:
        st.error(f"Could not load reports: {e}")
        return

    st.subheader("Sales Summary")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Invoices",
        sales["invoice_count"],
    )

    c2.metric(
        "Issued Sales",
        money(sales["total_paise"]),
    )

    c3.metric(
        "Discounts",
        money(sales["discount_paise"]),
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Tax",
        money(sales["tax_paise"]),
    )

    c2.metric(
        "Payments Collected",
        money(payments["collected_paise"]),
    )

    c3.metric(
        "Outstanding Invoices",
        len(outstanding),
    )

    st.divider()

    st.subheader("Daily Sales Trend")

    if trend:
        df = pd.DataFrame(trend)

        df["Sales ₹"] = df["sales_paise"] / 100

        st.line_chart(
            df.set_index("sale_date")["Sales ₹"]
        )

        st.download_button(
            "Export Daily Sales CSV",
            data=df.to_csv(index=False),
            file_name="smartbill_daily_sales.csv",
            mime="text/csv",
        )
    else:
        st.info("No sales found for the selected period.")

    st.divider()

    st.subheader("Top-Selling Products")

    if top_products:
        df = pd.DataFrame(top_products)

        df["Quantity Sold"] = (
            df["quantity_sold_milli"] / 1000
        )

        df["Sales ₹"] = df["sales_paise"] / 100

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Export Product Sales CSV",
            data=df.to_csv(index=False),
            file_name="smartbill_product_sales.csv",
            mime="text/csv",
        )
    else:
        st.info("No product sales found.")

    st.divider()

    st.subheader("Outstanding Invoices")

    if outstanding:
        df = pd.DataFrame(outstanding)

        df["Invoice Total ₹"] = df["total_paise"] / 100
        df["Paid ₹"] = df["paid_paise"] / 100
        df["Outstanding ₹"] = df["balance_paise"] / 100

        st.dataframe(
            df[
                [
                    "invoice_number",
                    "invoice_date",
                    "Invoice Total ₹",
                    "Paid ₹",
                    "Outstanding ₹",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Export Outstanding CSV",
            data=df.to_csv(index=False),
            file_name="smartbill_outstanding.csv",
            mime="text/csv",
        )
    else:
        st.success("No outstanding invoices.")
