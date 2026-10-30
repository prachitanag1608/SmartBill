
# modules/payments_ui.py

import streamlit as st
import pandas as pd

from modules.payments import (
    get_invoice_balance,
    list_payments,
    record_payment,
)


def money(paise):
    return f"₹{int(paise or 0) / 100:,.2f}"


def show_payments():

    st.title("Payments Management")

    user = st.session_state.get("auth_user")

    if not user:
        st.error("Please log in.")
        return

    st.subheader("Record Payment")

    with st.form("record_payment_form"):

        invoice_id = st.number_input(
            "Invoice Database ID",
            min_value=1,
            step=1,
        )

        amount = st.number_input(
            "Payment Amount (₹)",
            min_value=0.01,
            value=100.0,
            step=10.0,
        )

        method = st.selectbox(
            "Payment Method",
            [
                "cash",
                "upi",
                "card",
                "bank_transfer",
                "other",
            ],
        )

        reference = st.text_input(
            "Transaction Reference (optional)"
        )

        notes = st.text_area("Notes")

        submitted = st.form_submit_button(
            "Record Payment",
            type="primary",
        )

        if submitted:
            try:
                result = record_payment(
                    invoice_id=int(invoice_id),
                    amount_rupees=amount,
                    method=method,
                    received_by=user["username"],
                    reference=reference or None,
                    notes=notes or None,
                )

                st.success(
                    "Payment recorded successfully. "
                    f"Payment ID: {result['payment_id']}"
                )

                st.info(
                    "Remaining balance: "
                    + money(result["balance_paise"])
                )

                st.rerun()

            except ValueError as e:
                st.error(str(e))

            except Exception:
                st.error(
                    "Payment failed. Verify the database "
                    "schema and application logs."
                )

    st.divider()

    st.subheader("Invoice Balance Lookup")

    lookup_id = st.number_input(
        "Invoice ID for balance lookup",
        min_value=1,
        step=1,
        key="balance_invoice_id",
    )

    if st.button("Check Balance"):
        try:
            balance = get_invoice_balance(
                int(lookup_id)
            )

            st.write(
                "Invoice:",
                balance["invoice_number"],
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Invoice Total",
                money(balance["total_paise"]),
            )

            c2.metric(
                "Paid",
                money(balance["paid_paise"]),
            )

            c3.metric(
                "Outstanding",
                money(balance["balance_paise"]),
            )

        except Exception as e:
            st.error(f"Could not load balance: {e}")

    st.divider()

    st.subheader("Payment History")

    search = st.text_input(
        "Search by invoice number or payment ID"
    )

    try:
        payments = list_payments(search)

        if payments:
            st.dataframe(
                pd.DataFrame(payments),
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "Export Payments CSV",
                data=pd.DataFrame(payments).to_csv(
                    index=False
                ),
                file_name="smartbill_payments.csv",
                mime="text/csv",
            )
        else:
            st.info("No payment records found.")

    except Exception as e:
        st.error(f"Unable to load payments: {e}")
