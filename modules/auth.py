
# modules/auth.py

import hashlib
import hmac
import secrets
import sqlite3

from modules.db import get_connection


ITERATIONS = 600_000

ROLES = {"admin", "manager", "cashier"}

# Permissions by role
PERMISSIONS = {
    "admin": {
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
    },
    "manager": {
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
    },
    "cashier": {
        "Dashboard",
        "Products",
        "Customers",
        "New Bill",
        "Invoices",
        "Payments",
    },
}


def hash_password(password):
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError(
            "Password must contain at least 12 characters."
        )

    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS,
    )

    return (
        f"pbkdf2_sha256${ITERATIONS}$"
        f"{salt.hex()}${digest.hex()}"
    )


def verify_password(password, stored_hash):
    try:
        algorithm, rounds, salt_hex, digest_hex = (
            stored_hash.split("$")
        )

        if algorithm != "pbkdf2_sha256":
            return False

        rounds = int(rounds)

        # Prevent unreasonable work factors from untrusted DB values.
        if not 100_000 <= rounds <= 2_000_000:
            return False

        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)

        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            rounds,
        )

        return hmac.compare_digest(actual, expected)

    except (ValueError, TypeError, AttributeError):
        return False


def authenticate_user(username, password):
    username = (username or "").strip()

    if not username or not isinstance(password, str):
        return None

    conn = get_connection()

    try:
        row = conn.execute("""
            SELECT username, password_hash,
                   full_name, role, is_active
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        if not row:
            return None

        if not row["is_active"]:
            return None

        if row["role"] not in ROLES:
            return None

        if not verify_password(
            password,
            row["password_hash"],
        ):
            return None

        # Never return password hash.
        return {
            "username": row["username"],
            "full_name": row["full_name"],
            "role": row["role"],
        }

    finally:
        conn.close()


def has_permission(user, module):
    if not user:
        return False

    return module in PERMISSIONS.get(
        user.get("role"), set()
    )


def require_permission(user, module):
    if not has_permission(user, module):
        raise PermissionError(
            f"Access denied for module: {module}"
        )


def create_user(username, password, full_name, role):
    """
    User creation.

    Call this only from a trusted administrator workflow
    or secure one-time bootstrap process.
    """

    username = (username or "").strip()
    full_name = (full_name or "").strip()

    if not username or not full_name:
        raise ValueError(
            "Username and full name are required."
        )

    if role not in ROLES:
        raise ValueError("Invalid user role.")

    password_hash = hash_password(password)

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            INSERT INTO users (
                username,
                password_hash,
                full_name,
                role,
                is_active
            )
            VALUES (?, ?, ?, ?, 1)
        """, (
            username,
            password_hash,
            full_name,
            role,
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError(
            "Username already exists or user data is invalid."
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
