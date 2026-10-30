
# create_admin.py

import getpass
import sqlite3

from modules.db import init_db, get_connection
from modules.auth import create_user


def main():

    init_db()

    conn = get_connection()

    try:
        count = conn.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE role = 'admin'
        """).fetchone()[0]
    finally:
        conn.close()

    if count:
        print("An admin account already exists.")
        return

    username = input("Admin username: ").strip()
    full_name = input("Admin full name: ").strip()

    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.")
        return

    try:
        create_user(
            username=username,
            password=password,
            full_name=full_name,
            role="admin",
        )
        print("Admin account created.")

    except (ValueError, sqlite3.Error) as e:
        print(f"Could not create admin: {e}")


if __name__ == "__main__":
    main()
