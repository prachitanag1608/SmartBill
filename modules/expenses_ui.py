
# modules/expenses_ui.py

import streamlit as st
import pandas as pd
from datetime import date

from modules.expenses import (
    list_expenses,
    create_expense,
)


def show_expenses():

    st.title("Expense Management")
    st.caption("Manage your business expenses.")

    with st.expander("Add New Expense", expanded=True):

        with st.form("expense_form", clear_on_submit=True):

            c1, c2 = st.columns(2)

            with c1:
                amount = st.number_input(
                    "Amount (₹)",
                    min_value=0.01,
                    value=100.0,
                    step=10.0,
                )

                category = st.selectbox(
                    "Category",
                    [
                        "Rent",
                        "Electricity",
                        "Internet",
                        "Transport",
                        "Packaging",
                        "Maintenance",
                        "Salary",
                        "Marketing",
                        "Other",
                    ],
                )

                expense_date = st.date_input(
                    "Expense Date",
                    value=date.today(),
                )

            with c2:
                payment_method = st.selectbox(
                    "Payment Method",
                    [
                        "cash",
                        "upi",
                        "card",
                        "bank_transfer",
                        "other",
                    ],
                )

                vendor = st.text_input("Vendor / Payee")
                description = st.text_input("Description")

            notes = st.text_area("Notes")

            submitted = st.form_submit_button(
                "Save Expense",
                type="primary",
            )

            if submitted:
                try:
                    expense_id = create_expense(
                        amount_rupees=amount,
                        category=category,
                        description=description,
                        expense_date=expense_date.isoformat(),
                        payment_method=payment_method,
                        vendor=vendor,
                        notes=notes,
                    )

                    st.success(
                        f"Expense recorded. ID: {expense_id}"
                    )
                    st.rerun()

                except Exception as e:
                    st.error(f"Could not save expense: {e}")

    st.divider()
    st.subheader("Expense History")

    search = st.text_input(
        "Search expenses",
        placeholder="Search category or description",
    )

    try:
        records = list_expenses(search)

        if not records:
            st.info("No expenses found.")
            return

        df = pd.DataFrame(records)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Export Expenses CSV",
            data=df.to_csv(index=False),
            file_name="smartbill_expenses.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"Could not load expenses: {e}")
