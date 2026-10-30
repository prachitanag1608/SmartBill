
# modules/settings_ui.py

import streamlit as st

from modules.settings import (
    get_business_settings,
    update_business_settings,
)


def show_settings():

    st.title("Business Settings")
    st.caption("Manage your SmartBill business profile.")

    try:
        settings = get_business_settings()
    except Exception as e:
        st.error(f"Could not load settings: {e}")
        return

    with st.form("business_settings_form"):

        business_name = st.text_input(
            "Business Name",
            value=settings.get("business_name") or "",
        )

        address = st.text_area(
            "Business Address",
            value=settings.get("address") or "",
        )

        phone = st.text_input(
            "Phone",
            value=settings.get("phone") or "",
        )

        email = st.text_input(
            "Email",
            value=settings.get("email") or "",
        )

        gstin = st.text_input(
            "GSTIN",
            value=settings.get("gstin") or "",
        )

        state_code = st.text_input(
            "State Code",
            value=str(settings.get("state_code") or ""),
        )

        currency = st.text_input(
            "Currency",
            value=settings.get("currency") or "INR",
        )

        submitted = st.form_submit_button(
            "Save Settings",
            type="primary",
        )

        if submitted:
            try:
                values = {
                    "business_name": business_name,
                    "address": address,
                    "phone": phone,
                    "email": email,
                    "gstin": gstin,
                    "state_code": state_code,
                    "currency": currency,
                }

                update_business_settings(values)

                st.success("Business settings updated.")
                st.rerun()

            except Exception as e:
                st.error(f"Could not save settings: {e}")

    st.divider()

    st.subheader("System Information")

    st.write("Application: SmartBill")
    st.write("Module: Business Settings")
    st.caption(
        "Staff access controls and invoice numbering "
        "configuration can be added separately."
    )
