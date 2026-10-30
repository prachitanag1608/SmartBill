
# modules/auth_ui.py

import sqlite3
import streamlit as st

from modules.db import get_connection
from modules.auth import authenticate_user, hash_password


# --------------------------------------------------
# LOGIN + REGISTRATION SCREEN
# --------------------------------------------------

def login_screen():

    st.markdown(
        """
        <div style="text-align:center; padding:20px 0 10px 0;">
            <h1>🧾 SmartBill</h1>
            <p>Billing Management System</p>
            <p style="color:gray;">
                Secure billing and business management
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["Login", "Register"])

    # --------------------------------------------------
    # LOGIN
    # --------------------------------------------------

    with login_tab:

        st.subheader("Welcome Back")

        with st.form("smartbill_login_form"):

            username = st.text_input(
                "Username",
                max_chars=50,
            ).strip()

            password = st.text_input(
                "Password",
                type="password",
            )

            login_clicked = st.form_submit_button(
                "Login",
                type="primary",
                use_container_width=True,
            )

        if login_clicked:

            if not username or not password:
                st.error("Please enter your username and password.")

            else:
                try:
                    user = authenticate_user(username, password)

                    if user:
                        # Store authenticated user.
                        st.session_state["auth_user"] = user

                        # Remove old navigation selection.
                        st.session_state.pop("main_navigation", None)

                        st.rerun()

                    else:
                        st.error(
                            "Invalid username/password, "
                            "or your account is inactive."
                        )

                except Exception:
                    st.error(
                        "Login failed. Please check your account "
                        "or contact the administrator."
                    )

    # --------------------------------------------------
    # REGISTRATION
    # --------------------------------------------------

    with register_tab:

        st.subheader("Create Your Account")

        st.info(
            "Register as a Cashier or Manager. "
            "Your account requires Admin approval."
        )

        with st.form("smartbill_register_form"):

            full_name = st.text_input(
                "Full Name",
                max_chars=100,
            ).strip()

            new_username = st.text_input(
                "Choose Username",
                max_chars=50,
            ).strip()

            new_password = st.text_input(
                "Create Password",
                type="password",
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
            )

            job_role = st.selectbox(
                "Job Role",
                ["Cashier", "Manager"],
            )

            register_clicked = st.form_submit_button(
                "Register",
                type="primary",
                use_container_width=True,
            )

        if register_clicked:

            if not full_name or not new_username:
                st.error("Please fill in all required fields.")

            elif any(ch.isspace() for ch in new_username):
                st.error("Username cannot contain spaces.")

            elif new_password != confirm_password:
                st.error("Passwords do not match.")

            elif len(new_password) < 12:
                st.error(
                    "Password must contain at least 12 characters."
                )

            else:
                conn = None

                try:
                    # Hash password before storing.
                    password_hash = hash_password(new_password)

                    conn = get_connection()

                    # New accounts are inactive until approved.
                    conn.execute(
                        """
                        INSERT INTO users (
                            username,
                            password_hash,
                            full_name,
                            role,
                            is_active
                        )
                        VALUES (?, ?, ?, ?, 0)
                        """,
                        (
                            new_username,
                            password_hash,
                            full_name,
                            job_role.lower(),
                        ),
                    )

                    conn.commit()

                    st.success(
                        "Registration successful! "
                        "Your account is pending Admin approval."
                    )

                except sqlite3.IntegrityError:
                    if conn:
                        conn.rollback()

                    st.error(
                        "Username already exists. "
                        "Please choose another username."
                    )

                except sqlite3.Error:
                    if conn:
                        conn.rollback()

                    st.error(
                        "Registration failed due to a database error."
                    )

                except Exception:
                    if conn:
                        conn.rollback()

                    st.error(
                        "Unable to complete registration. "
                        "Please check the application configuration."
                    )

                finally:
                    if conn:
                        conn.close()


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

def logout_button():

    if st.button(
        "Logout",
        key="smartbill_logout",
        use_container_width=True,
    ):
        st.session_state.pop("auth_user", None)
        st.session_state.pop("main_navigation", None)

        st.rerun()
