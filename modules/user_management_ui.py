
# modules/user_management_ui.py

import streamlit as st

from modules.db import get_connection


def show_user_management():
    st.title("User Management")
    st.caption("Review staff registration requests")

    user = st.session_state.get("auth_user")

    # Admin-only page
    if not user or user.get("role") != "admin":
        st.error("Access denied. Admin only.")
        st.stop()

    conn = get_connection()

    try:
        pending_users = conn.execute(
            """
            SELECT id, username, full_name, role
            FROM users
            WHERE is_active = 0
              AND role IN ('manager', 'cashier')
            ORDER BY id DESC
            """
        ).fetchall()

    finally:
        conn.close()

    st.subheader("Pending Registration Requests")

    if not pending_users:
        st.success("No pending registration requests.")
        st.divider()
    else:
        st.write(f"Pending requests: {len(pending_users)}")

        for account in pending_users:
            user_id = account["id"]

            with st.container(border=True):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.write(f"**{account['full_name']}**")
                    st.caption(f"Username: {account['username']}")
                    st.write(
                        f"Requested role: "
                        f"{account['role'].title()}"
                    )

                with col2:
                    st.write(f"Request ID: {user_id}")

                approve_col, reject_col = st.columns(2)

                with approve_col:
                    approve = st.button(
                        "Approve",
                        key=f"approve_{user_id}",
                        type="primary",
                        use_container_width=True,
                    )

                with reject_col:
                    reject = st.button(
                        "Reject",
                        key=f"reject_{user_id}",
                        use_container_width=True,
                    )

                if approve:
                    conn = get_connection()

                    try:
                        # Recheck account before activation.
                        result = conn.execute(
                            """
                            UPDATE users
                            SET is_active = 1
                            WHERE id = ?
                              AND is_active = 0
                              AND role IN ('manager', 'cashier')
                            """,
                            (user_id,),
                        )

                        if result.rowcount == 1:
                            conn.commit()
                            st.success(
                                f"Approved {account['username']}."
                            )
                        else:
                            conn.rollback()
                            st.warning(
                                "Request is no longer pending."
                            )

                    except Exception:
                        conn.rollback()
                        st.error("Unable to approve this request.")

                    finally:
                        conn.close()

                    st.rerun()

                if reject:
                    st.session_state[
                        f"confirm_reject_{user_id}"
                    ] = True

                if st.session_state.get(
                    f"confirm_reject_{user_id}", False
                ):
                    st.warning(
                        f"Reject registration for "
                        f"{account['username']}?"
                    )

                    confirm_col, cancel_col = st.columns(2)

                    with confirm_col:
                        if st.button(
                            "Confirm Rejection",
                            key=f"confirm_rejection_{user_id}",
                        ):
                            conn = get_connection()

                            try:
                                # Delete only the pending account.
                                result = conn.execute(
                                    """
                                    DELETE FROM users
                                    WHERE id = ?
                                      AND is_active = 0
                                      AND role IN ('manager', 'cashier')
                                    """,
                                    (user_id,),
                                )

                                if result.rowcount == 1:
                                    conn.commit()
                                    st.success(
                                        "Registration request rejected."
                                    )
                                else:
                                    conn.rollback()
                                    st.warning(
                                        "Request is no longer pending."
                                    )

                            except Exception:
                                conn.rollback()
                                st.error(
                                    "Unable to reject this request."
                                )

                            finally:
                                conn.close()

                            st.session_state.pop(
                                f"confirm_reject_{user_id}", None
                            )
                            st.rerun()

                    with cancel_col:
                        if st.button(
                            "Cancel",
                            key=f"cancel_rejection_{user_id}",
                        ):
                            st.session_state.pop(
                                f"confirm_reject_{user_id}", None
                            )
                            st.rerun()

    st.divider()

    # Existing staff list
    st.subheader("Active Staff")

    conn = get_connection()

    try:
        active_users = conn.execute(
            """
            SELECT id, username, full_name, role
            FROM users
            WHERE is_active = 1
            ORDER BY role, full_name
            """
        ).fetchall()

    finally:
        conn.close()

    if active_users:
        st.dataframe(
            [
                {
                    "ID": row["id"],
                    "Username": row["username"],
                    "Full Name": row["full_name"],
                    "Role": row["role"].title(),
                }
                for row in active_users
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No active staff accounts found.")
