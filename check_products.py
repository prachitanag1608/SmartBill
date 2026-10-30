from modules.db import get_connection

conn = get_connection()

try:
    products = conn.execute("""
        SELECT
            id,
            sku,
            name,
            selling_price_paise,
            stock_qty_milli
        FROM products
        ORDER BY id DESC
    """).fetchall()

    print("\nSMARTBILL PRODUCTS")

    for p in products:
        print(
            p["id"],
            p["sku"],
            p["name"],
            f"₹{p['selling_price_paise'] / 100:.2f}",
            p["stock_qty_milli"] / 1000
        )

finally:
    conn.close()