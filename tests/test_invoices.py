
# tests/test_invoices.py

import unittest

from modules.invoices import (
    list_invoices,
    get_invoice_details,
)


class TestInvoiceManagement(unittest.TestCase):

    def test_list_invoices_returns_list(self):
        result = list_invoices()
        self.assertIsInstance(result, list)

    def test_invoice_details_invalid_id(self):
        result = get_invoice_details(-999999)
        self.assertIsNone(result)

    def test_payment_status_filter(self):
        result = list_invoices(payment_status="paid")

        for invoice in result:
            self.assertEqual(invoice["payment_status"], "paid")

    def test_invoice_status_filter(self):
        result = list_invoices(invoice_status="issued")

        for invoice in result:
            self.assertEqual(invoice["status"], "issued")

    def test_limit(self):
        result = list_invoices(limit=2)
        self.assertLessEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
