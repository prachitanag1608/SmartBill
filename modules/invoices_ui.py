
# modules/invoice_ui.py

import streamlit as st
import pandas as pd

from modules.invoices import (
    list_invoices,
    get_invoice_details,
)
from modules.invoice_pdf import generate_invoice_pdf


def rupees(paise):
    return f"Rs. {int(paise or 0) / 100:,.2f}"


def show_invoice_management():

    st.title("Invoice Management")
    st.caption("Search, view and download your invoices.")

    # Search
    search = st.text_input(
        "Search Invoice / Customer",
        placeholder="Enter invoice number, name or phone",
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        payment_status = st.selectbox(
            "Payment Status",
            ["All", "unpaid", "partial", "paid", "refunded"],
        )

    with col2:
        invoice_status = st.selectbox(
            "Invoice Status",
            ["All", "draft", "issued", "void"],
        )

    with col3:
        limit = st.selectbox(
            "Maximum Records",
            [100, 250, 500, 1000],
            index=2,
        )

    with st.expander("Date Filters"):
        use_dates = st.checkbox("Apply date filter")

        date_from = None
        date_to = None

        if use_dates:
            d1, d2 = st.columns(2)

            with d1:
                date_from = st.date_input("From Date")

            with d2:
                date_to = st.date_input("To Date")

            if date_from > date_to:
                st.error("Start date cannot be after end date.")
                return

    try:
        invoices = list_invoices(
            search=search,
            payment_status=payment_status,
            invoice_status=invoice_status,
            date_from=date_from if use_dates else None,
            date_to=date_to if use_dates else None,
            limit=limit,
        )
    except Exception as e:
        st.error(f"Unable to load invoices: {e}")
        return

    if not invoices:
        st.info("No invoices found.")
        return

    df = pd.DataFrame(invoices)

    total_sales = sum(
        row["total_paise"]
        for row in invoices
        if row["status"] == "issued"
    )

    total_paid = sum(
        row["paid_paise"]
        for row in invoices
        if row["status"] == "issued"
    )

    balance = sum(
        max(0, row["total_paise"] - row["paid_paise"])
        for row in invoices
        if row["status"] == "issued"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("Invoices Found", len(invoices))
    c2.metric("Issued Invoice Total", rupees(total_sales))
    c3.metric("Outstanding Balance", rupees(balance))

    st.caption(
        "Summary is based on the currently filtered invoices. "
        "Issued invoices only are included in sales and balance."
    )

    # Display invoice list
    display = df[[
        "id",
        "invoice_number",
        "invoice_date",
        "customer_name",
        "total_paise",
        "paid_paise",
        "payment_status",
        "status",
    ]].copy()

    display = display.rename(columns={
        "id": "ID",
        "invoice_number": "Invoice No",
        "invoice_date": "Date",
        "customer_name": "Customer",
        "total_paise": "Total (Paise)",
        "paid_paise": "Paid (Paise)",
        "payment_status": "Payment",
        "status": "Status",
    })

    display["Total"] = display.pop("Total (Paise)").apply(rupees)
    display["Paid"] = display.pop("Paid (Paise)").apply(rupees)

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    # Select invoice
    st.divider()
    st.subheader("View Invoice")

    invoice_options = {
        f"{row['invoice_number']} | "
        f"{row['customer_name'] or 'Walk-in Customer'} | "
        f"{rupees(row['total_paise'])}": row["id"]
        for row in invoices
    }

    selected_label = st.selectbox(
        "Select Invoice",
        list(invoice_options.keys()),
    )

    invoice_id = invoice_options[selected_label]

    try:
        details = get_invoice_details(invoice_id)
    except Exception as e:
        st.error(f"Unable to retrieve invoice: {e}")
        return

    if not details:
        st.warning("Invoice not found.")
        return

    inv = details["invoice"]

    st.subheader(f"Invoice: {inv['invoice_number']}")

    c1, c2, c3 = st.columns(3)

    c1.metric("Grand Total", rupees(inv["total_paise"]))
    c2.metric("Paid", rupees(details["paid_paise"]))
    c3.metric("Balance", rupees(details["balance_paise"]))

    st.write("**Invoice Date:**", inv["invoice_date"])
    st.write("**Customer:**", inv.get("customer_name") or "Walk-in Customer")
    st.write("**Invoice Status:**", inv["status"])
    st.write("**Payment Status:**", inv["payment_status"])

    st.markdown("#### Items")

    item_rows = []

    for item in details["items"]:
        item_rows.append({
            "Product": item["product_name"],
            "SKU": item["sku"],
            "Quantity": int(item["quantity_milli"]) / 1000,
            "Unit Price": rupees(item["unit_price_paise"]),
            "Discount": rupees(item["discount_paise"]),
            "Tax": rupees(item["tax_paise"]),
            "Line Total": rupees(item["line_total_paise"]),
        })

    st.dataframe(
        pd.DataFrame(item_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Payments")

    if details["payments"]:
        payment_rows = [{
            "Payment Date": p["payment_date"],
            "Method": p["method"],
            "Amount": rupees(p["amount_paise"]),
            "Status": p["status"],
        } for p in details["payments"]]

        st.dataframe(
            pd.DataFrame(payment_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No payment records.")

    # PDF download
    st.divider()

    if st.button("Generate Invoice PDF", type="primary"):
        try:
            pdf_bytes = generate_invoice_pdf(details)

            st.download_button(
                "Download Invoice PDF",
                data=pdf_bytes,
                file_name=f"{inv['invoice_number']}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error(f"PDF generation failed: {e}")
