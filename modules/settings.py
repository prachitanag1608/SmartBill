
# modules/settings.py

from modules.db import get_connection


EDITABLE_FIELDS = [
    "business_name",
    "address",
    "phone",
    "email",
    "gstin",
    "state_code",
    "currency",
]


def get_business_settings():

    conn = get_connection()

    try:
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(business_settings)"
            ).fetchall()
        }

        fields = [
            field for field in EDITABLE_FIELDS
            if field in columns
        ]

        if not fields:
            raise ValueError(
                "No compatible business settings fields found."
            )

        row = conn.execute(
            "SELECT "
            + ", ".join(f'"{f}"' for f in fields)
            + " FROM business_settings WHERE id = 1"
        ).fetchone()

        if not row:
            raise ValueError(
                "Business settings record id=1 not found."
            )

        return dict(row)

    finally:
        conn.close()


def update_business_settings(values):

    allowed = set(EDITABLE_FIELDS)

    if not isinstance(values, dict):
        raise ValueError("Settings must be a dictionary.")

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(business_settings)"
            ).fetchall()
        }

        updates = {}

        for key, value in values.items():
            if key not in allowed:
                raise ValueError(
                    f"Unsupported setting: {key}"
                )

            if key in columns:
                updates[key] = (
                    value.strip()
                    if isinstance(value, str)
                    else value
                )

        if not updates:
            raise ValueError("No settings to update.")

        if "business_name" in updates:
            if not updates["business_name"]:
                raise ValueError("Business name is required.")

        fields = list(updates.keys())

        sql = (
            "UPDATE business_settings SET "
            + ", ".join(f'"{f}" = ?' for f in fields)
            + " WHERE id = 1"
        )

        cur = conn.execute(
            sql,
            [updates[f] for f in fields],
        )

        if cur.rowcount != 1:
            raise ValueError(
                "Business settings record was not updated."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
