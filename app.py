
# ============================================
# SMARTBILL - SHOP MANAGEMENT SYSTEM
# ============================================

import streamlit as st
from pathlib import Path

# ============================================
# DATABASE
# ============================================

from modules.db import init_db, get_connection

# ============================================
# AUTHENTICATION
# ============================================

from modules.auth_ui import login_screen, logout_button
from modules.auth import has_permission

# ============================================
# APPLICATION MODULES
# ============================================

from modules.products import show_products
from modules.customers import show_customers
from modules.billing_ui import show_billing
from modules.invoices_ui import show_invoice_management
from modules.inventory_ui import show_inventory
from modules.purchases_ui import show_purchases
from modules.returns_ui import show_returns
from modules.expenses_ui import show_expenses
from modules.reports_ui import show_reports
from modules.dashboard_ui import show_dashboard
from modules.settings_ui import show_settings
from modules.payments_ui import show_payments
from modules.user_management_ui import show_user_management


# ============================================
# PAGE CONFIGURATION
# MUST BE THE FIRST STREAMLIT COMMAND
# ============================================

st.set_page_config(
    page_title="SmartBill | Shop Management",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================
# GLOBAL THEME
# ============================================

ROOT_DIR = Path(__file__).resolve().parent
CSS_FILE = ROOT_DIR / "style.css"


def load_theme():
    """Load the shared SmartBill theme."""

    if not CSS_FILE.exists():
        st.warning(
            "style.css not found. "
            "Please place it beside app.py."
        )
        return

    css = CSS_FILE.read_text(encoding="utf-8")

    st.markdown(
        f"<style>\n{css}\n</style>",
        unsafe_allow_html=True
    )


load_theme()


# ============================================
# DATABASE INITIALIZATION
# ============================================

init_db()


# ============================================
# AUTHENTICATION
# ============================================

user = st.session_state.get("auth_user")

if not user:
    login_screen()
    st.stop()


# ============================================
# VERIFY CURRENT ACCOUNT
# ============================================

conn = get_connection()

try:
    account = conn.execute(
        """
        SELECT id, username, full_name, role, is_active
        FROM users
        WHERE username = ?
        """,
        (user.get("username"),)
    ).fetchone()

finally:
    conn.close()


# Check account status
if not account or not account["is_active"]:

    st.session_state.pop("auth_user", None)
    st.session_state.pop("main_navigation", None)

    st.error(
        "Your account is inactive or unavailable. "
        "Please log in again."
    )

    st.stop()


# Refresh trusted user details
user = dict(account)

st.session_state["auth_user"] = user


# ============================================
# SIDEBAR
# ============================================

modules = [
    "Dashboard",
    "Products",
    "Customers",
    "New Bill",
    "Invoices",
    "Payments",
    "Inventory",
    "Purchases",
    "Sales Returns",
    "Expenses",
    "Reports",
    "Settings",
    "User Management",
]


# Show only permitted modules
available_modules = [
    module
    for module in modules
    if has_permission(user, module)
]


if not available_modules:
    st.error("No modules are available for your account.")
    st.stop()


with st.sidebar:

    # Shop identity
    st.markdown(
        """
        <div style="
            padding: 12px 8px 16px 8px;
            text-align: center;
        ">
            <div style="font-size: 42px;">🛒</div>
            <div style="
                font-size: 25px;
                font-weight: 900;
                letter-spacing: -1px;
                color: #087F73;
            ">
                SmartBill
            </div>
            <div style="
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.5px;
                color: #718096;
            ">
                YOUR SHOP CONTROL CENTER
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    # Logged-in user
    st.markdown("### 👋 Shop Team")

    st.markdown(
        f"**{user['full_name']}**"
    )

    st.caption(
        f"Role: {str(user['role']).title()}"
    )

    logout_button()

    st.divider()

    # Main navigation
    st.markdown("### 🏪 Store Menu")

    selected_module = st.radio(
        "Choose a section",
        available_modules,
        key="main_navigation",
        label_visibility="collapsed",
        format_func=lambda name: {
            "Dashboard": "🏠 Dashboard",
            "Products": "🛍️ Products",
            "Customers": "👥 Customers",
            "New Bill": "🧾 New Bill",
            "Invoices": "📄 Invoices",
            "Payments": "💳 Payments",
            "Inventory": "📦 Inventory",
            "Purchases": "🛒 Purchases",
            "Sales Returns": "↩️ Sales Returns",
            "Expenses": "💸 Expenses",
            "Reports": "📊 Reports",
            "Settings": "⚙️ Settings",
            "User Management": "👤 User Management",
        }.get(name, name)
    )

    st.divider()

    st.caption("✨ SmartBill • Shop Management")


# ============================================
# PERMISSION CHECK
# ============================================

if not has_permission(user, selected_module):
    st.error("Access denied.")
    st.stop()


# ============================================
# APPLICATION HEADER
# ============================================

st.markdown(
    """
    <div style="
        display:flex;
        align-items:center;
        gap:12px;
        margin-bottom:4px;
    ">
        <div style="font-size:34px;">🛒</div>
        <div>
            <div style="
                font-size:28px;
                font-weight:900;
                color:#263447;
                letter-spacing:-1px;
            ">
                SmartBill
            </div>
            <div style="
                font-size:12px;
                font-weight:700;
                color:#718096;
                letter-spacing:1px;
            ">
                YOUR SHOP. YOUR BUSINESS. YOUR RULES.
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.divider()


# ============================================
# PAGE ROUTING
# ============================================

if selected_module == "Dashboard":

    show_dashboard()

elif selected_module == "Products":

    show_products()

elif selected_module == "Customers":

    show_customers()

elif selected_module == "New Bill":

    show_billing()

elif selected_module == "Invoices":

    show_invoice_management()

elif selected_module == "Payments":

    show_payments()

elif selected_module == "Inventory":

    show_inventory()

elif selected_module == "Purchases":

    show_purchases()

elif selected_module == "Sales Returns":

    show_returns()

elif selected_module == "Expenses":

    show_expenses()

elif selected_module == "Reports":

    show_reports()

elif selected_module == "Settings":

    show_settings()

elif selected_module == "User Management":

    show_user_management()
