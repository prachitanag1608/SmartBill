
import sqlite3
import streamlit as st
import pandas as pd

from modules.db import get_connection


# ==============================================
# DATABASE HELPERS
# ==============================================

def fetch_all(query, params=()):
    conn = get_connection()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def execute_write(query, params=()):
    conn = get_connection()
    try:
        conn.execute(query, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==============================================
# CUSTOMER CRUD
# ==============================================

def get_customers(search="", include_archived=False):
    query = """
        SELECT
            id, name, phone, email, address,
            gstin, state_code, notes, is_active,
            created_at
        FROM customers
        WHERE 1=1
    """
    params = []

    if not include_archived:
        query += " AND is_active = 1"

    if search.strip():
        term = f"%{search.strip()}%"
        query += """
            AND (
                name LIKE ?
                OR phone LIKE ?
                OR email LIKE ?
            )
        """
        params.extend([term, term, term])

    query += " ORDER BY name COLLATE NOCASE"

    return fetch_all(query, params)


def add_customer(
    name,
    phone,
    email,
    address,
    gstin,
    state_code,
    notes
):
    name = name.strip()

    if not name:
        raise ValueError("Customer name is required.")

    execute_write("""
        INSERT INTO customers (
            name, phone, email, address,
            gstin, state_code, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        phone.strip() or None,
        email.strip() or None,
        address.strip() or None,
        gstin.strip().upper() or None,
        state_code.strip() or None,
        notes.strip() or None
    ))


def update_customer(
    customer_id,
    name,
    phone,
    email,
    address,
    gstin,
    state_code,
    notes
):
    name = name.strip()

    if not name:
        raise ValueError("Customer name is required.")

    conn = get_connection()

    try:
        cur = conn.execute("""
            UPDATE customers
            SET
                name = ?,
                phone = ?,
                email = ?,
                address = ?,
                gstin = ?,
                state_code = ?,
                notes = ?
            WHERE id = ? AND is_active = 1
        """, (
            name,
            phone.strip() or None,
            email.strip() or None,
            address.strip() or None,
            gstin.strip().upper() or None,
            state_code.strip() or None,
            notes.strip() or None,
            customer_id
        ))

        if cur.rowcount == 0:
            raise ValueError(
                "Customer not found or archived."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def archive_customer(customer_id):
    conn = get_connection()

    try:
        cur = conn.execute("""
            UPDATE customers
            SET is_active = 0
            WHERE id = ? AND is_active = 1
        """, (customer_id,))

        if cur.rowcount == 0:
            raise ValueError(
                "Customer not found or already archived."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def restore_customer(customer_id):
    conn = get_connection()

    try:
        cur = conn.execute("""
            UPDATE customers
            SET is_active = 1
            WHERE id = ? AND is_active = 0
        """, (customer_id,))

        if cur.rowcount == 0:
            raise ValueError("Archived customer not found.")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==============================================
# CUSTOMER PURCHASE HISTORY
# ==============================================

def get_purchase_history(customer_id):
    return fetch_all("""
        SELECT
            id,
            invoice_number,
            invoice_date,
            status,
            payment_status,
            total_paise
        FROM invoices
        WHERE customer_id = ?
          AND status = 'issued'
        ORDER BY invoice_date DESC, id DESC
    """, (customer_id,))


# ==============================================
# CUSTOMER INTERFACE
# ==============================================

def show_customers():
    st.title("👥 Customer Management")
    st.caption("Manage customer profiles and billing information.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Customer List",
        "Add Customer",
        "Edit / Archive",
        "Purchase History"
    ])

    # ------------------------------------------
    # CUSTOMER LIST
    # ------------------------------------------

    with tab1:
        search = st.text_input(
            "Search name, phone or email",
            key="customer_search"
        )

        include_archived = st.checkbox(
            "Include archived customers",
            key="customer_archived"
        )

        customers = get_customers(
            search,
            include_archived
        )

        if customers:
            df = pd.DataFrame([
                dict(c) for c in customers
            ])

            df = df.rename(columns={
                "id": "Customer ID",
                "name": "Name",
                "phone": "Phone",
                "email": "Email",
                "address": "Address",
                "gstin": "GSTIN",
                "state_code": "State Code",
                "is_active": "Active"
            })

            st.dataframe(
                df[[
                    "Customer ID",
                    "Name",
                    "Phone",
                    "Email",
                    "Address",
                    "GSTIN",
                    "State Code",
                    "Active"
                ]],
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                f"{len(customers)} customer(s) found."
            )
        else:
            st.info("No customers found.")

    # ------------------------------------------
    # ADD CUSTOMER
    # ------------------------------------------

    with tab2:
        with st.form("add_customer_form"):
            name = st.text_input("Customer name *")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            address = st.text_area("Address")

            gstin = st.text_input(
                "GSTIN (optional)"
            )

            state_code = st.text_input(
                "State code (optional)"
            )

            notes = st.text_area("Notes (optional)")

            submitted = st.form_submit_button(
                "Save Customer"
            )

            if submitted:
                try:
                    add_customer(
                        name,
                        phone,
                        email,
                        address,
                        gstin,
                        state_code,
                        notes
                    )

                    st.success(
                        "Customer registered successfully."
                    )
                    st.rerun()

                except (ValueError, sqlite3.Error) as e:
                    st.error(f"Could not save customer: {e}")

    # ------------------------------------------
    # EDIT / ARCHIVE
    # ------------------------------------------

    with tab3:
        customers = get_customers()

        if not customers:
            st.info("No active customers available.")
        else:
            customer_map = {
                f"{c['id']} — {c['name']}": c
                for c in customers
            }

            selected = st.selectbox(
                "Select customer",
                list(customer_map.keys()),
                key="edit_customer_select"
            )

            c = customer_map[selected]

            with st.form(f"edit_customer_{c['id']}"):
                new_name = st.text_input(
                    "Name",
                    value=c["name"]
                )
                new_phone = st.text_input(
                    "Phone",
                    value=c["phone"] or ""
                )
                new_email = st.text_input(
                    "Email",
                    value=c["email"] or ""
                )
                new_address = st.text_area(
                    "Address",
                    value=c["address"] or ""
                )
                new_gstin = st.text_input(
                    "GSTIN",
                    value=c["gstin"] or ""
                )
                new_state = st.text_input(
                    "State code",
                    value=c["state_code"] or ""
                )
                new_notes = st.text_area(
                    "Notes",
                    value=c["notes"] or ""
                )

                save = st.form_submit_button(
                    "Update Customer"
                )

                if save:
                    try:
                        update_customer(
                            c["id"],
                            new_name,
                            new_phone,
                            new_email,
                            new_address,
                            new_gstin,
                            new_state,
                            new_notes
                        )

                        st.success("Customer updated.")
                        st.rerun()

                    except (ValueError, sqlite3.Error) as e:
                        st.error(str(e))

            st.divider()

            confirm = st.checkbox(
                "I confirm that I want to archive this customer.",
                key=f"archive_customer_confirm_{c['id']}"
            )

            if st.button(
                "Archive Customer",
                disabled=not confirm,
                key=f"archive_customer_{c['id']}"
            ):
                try:
                    archive_customer(c["id"])
                    st.success("Customer archived.")
                    st.rerun()

                except (ValueError, sqlite3.Error) as e:
                    st.error(str(e))

    # ------------------------------------------
    # PURCHASE HISTORY
    # ------------------------------------------

    with tab4:
        customers = get_customers(
            include_archived=True
        )

        if not customers:
            st.info("Register a customer first.")
        else:
            customer_map = {
                f"{c['id']} — {c['name']}": c
                for c in customers
            }

            selected = st.selectbox(
                "Choose customer",
                list(customer_map.keys()),
                key="history_customer_select"
            )

            customer = customer_map[selected]

            invoices = get_purchase_history(
                customer["id"]
            )

            if invoices:
                df = pd.DataFrame([
                    dict(row) for row in invoices
                ])

                df["Total"] = df[
                    "total_paise"
                ].apply(
                    lambda x: f"₹{x / 100:,.2f}"
                )

                st.dataframe(
                    df[[
                        "invoice_number",
                        "invoice_date",
                        "payment_status",
                        "Total"
                    ]].rename(columns={
                        "invoice_number": "Invoice",
                        "invoice_date": "Date",
                        "payment_status": "Payment Status"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                st.caption(
                    f"{len(invoices)} issued invoice(s)."
                )
            else:
                st.info(
                    "No issued invoices found for this customer."
                )
