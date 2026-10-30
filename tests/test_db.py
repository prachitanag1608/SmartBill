
import sqlite3
import unittest

from modules.db import init_db, get_connection


class TestSmartBillDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_database_connection(self):
        with get_connection() as conn:
            result = conn.execute(
                "SELECT 1"
            ).fetchone()[0]

        self.assertEqual(result, 1)

    def test_default_business_settings(self):
        with get_connection() as conn:
            row = conn.execute("""
                SELECT business_name
                FROM business_settings
                WHERE id = 1
            """).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["business_name"], "SmartBill Retail")

    def test_add_category_and_product(self):
        with get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO categories(name)
                VALUES ('Test Category')
            """)

            category = conn.execute("""
                SELECT id FROM categories
                WHERE name = 'Test Category'
            """).fetchone()

            conn.execute("""
                INSERT INTO products (
                    sku,
                    name,
                    category_id,
                    cost_price_paise,
                    selling_price_paise,
                    stock_qty_milli
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "TEST-SKU-001",
                "Test Notebook",
                category["id"],
                3000,
                5000,
                10000
            ))

            product = conn.execute("""
                SELECT * FROM products
                WHERE sku = 'TEST-SKU-001'
            """).fetchone()

        self.assertEqual(product["name"], "Test Notebook")
        self.assertEqual(product["selling_price_paise"], 5000)
        self.assertEqual(product["stock_qty_milli"], 10000)

    def test_duplicate_sku_rejected(self):
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("""
                    INSERT INTO products (
                        sku, name, selling_price_paise
                    )
                    VALUES (?, ?, ?)
                """, ("TEST-SKU-001", "Duplicate", 1000))

    def test_negative_price_rejected(self):
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("""
                    INSERT INTO products (
                        sku, name, selling_price_paise
                    )
                    VALUES (?, ?, ?)
                """, ("TEST-NEG-001", "Invalid Product", -100))

    def test_foreign_key_enforced(self):
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("""
                    INSERT INTO invoice_items (
                        invoice_id,
                        product_name,
                        quantity_milli,
                        unit_price_paise,
                        line_total_paise
                    )
                    VALUES (999999, 'Invalid', 1000, 100, 100)
                """)


if __name__ == "__main__":
    unittest.main(verbosity=2)
