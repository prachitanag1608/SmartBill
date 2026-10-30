
from pathlib import Path
import sqlite3
from contextlib import contextmanager

# -------------------------------------------------
# DATABASE CONFIGURATION
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "database"
DB_PATH = DATABASE_DIR / "smartbill.db"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------
# DATABASE CONNECTION
# -------------------------------------------------

def get_connection():
    """Create a configured SQLite database connection."""

    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=30
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")

    return conn
    


# -------------------------------------------------
# DATABASE SCHEMA
# -------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS business_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    business_name TEXT NOT NULL DEFAULT 'SmartBill Retail',
    address TEXT,
    phone TEXT,
    email TEXT,
    gstin TEXT,
    state_code TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK (role IN ('admin', 'manager', 'cashier')),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    barcode TEXT UNIQUE,
    name TEXT NOT NULL,
    category_id INTEGER,
    description TEXT,
    unit TEXT NOT NULL DEFAULT 'pcs',
    cost_price_paise INTEGER NOT NULL DEFAULT 0
        CHECK (cost_price_paise >= 0),
    selling_price_paise INTEGER NOT NULL
        CHECK (selling_price_paise >= 0),
    tax_rate_bps INTEGER NOT NULL DEFAULT 0
        CHECK (tax_rate_bps BETWEEN 0 AND 10000),
    stock_qty_milli INTEGER NOT NULL DEFAULT 0,
    reorder_level_milli INTEGER NOT NULL DEFAULT 0
        CHECK (reorder_level_milli >= 0),
    track_stock INTEGER NOT NULL DEFAULT 1
        CHECK (track_stock IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (category_id)
        REFERENCES categories(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    gstin TEXT,
    state_code TEXT,
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    gstin TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL UNIQUE,
    customer_id INTEGER,
    created_by INTEGER,
    invoice_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'issued', 'void')),
    payment_status TEXT NOT NULL DEFAULT 'unpaid'
        CHECK (payment_status IN
            ('unpaid', 'partial', 'paid', 'refunded')),
    subtotal_paise INTEGER NOT NULL DEFAULT 0
        CHECK (subtotal_paise >= 0),
    discount_paise INTEGER NOT NULL DEFAULT 0
        CHECK (discount_paise >= 0),
    tax_paise INTEGER NOT NULL DEFAULT 0
        CHECK (tax_paise >= 0),
    total_paise INTEGER NOT NULL DEFAULT 0
        CHECK (total_paise >= 0),
    notes TEXT,

    -- Billing snapshot: preserve details used at issue time
    customer_name TEXT,
    customer_address TEXT,
    customer_gstin TEXT,
    business_name TEXT,
    business_address TEXT,
    business_gstin TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (customer_id)
        REFERENCES customers(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT,

    CHECK (discount_paise <= subtotal_paise),
    CHECK (
        total_paise =
        subtotal_paise - discount_paise + tax_paise
    )
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    product_id INTEGER,
    product_name TEXT NOT NULL,
    sku TEXT,
    quantity_milli INTEGER NOT NULL
        CHECK (quantity_milli > 0),
    unit_price_paise INTEGER NOT NULL
        CHECK (unit_price_paise >= 0),
    discount_paise INTEGER NOT NULL DEFAULT 0
        CHECK (discount_paise >= 0),
    tax_rate_bps INTEGER NOT NULL DEFAULT 0
        CHECK (tax_rate_bps BETWEEN 0 AND 10000),
    tax_paise INTEGER NOT NULL DEFAULT 0
        CHECK (tax_paise >= 0),
    line_total_paise INTEGER NOT NULL
        CHECK (line_total_paise >= 0),

    FOREIGN KEY (invoice_id)
        REFERENCES invoices(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    amount_paise INTEGER NOT NULL
        CHECK (amount_paise > 0),
    method TEXT NOT NULL
        CHECK (method IN
            ('cash', 'upi', 'card', 'bank_transfer', 'other')),
    reference TEXT,
    status TEXT NOT NULL DEFAULT 'completed'
        CHECK (status IN ('completed', 'void')),
    payment_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    received_by INTEGER,
    notes TEXT,

    FOREIGN KEY (invoice_id)
        REFERENCES invoices(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (received_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    description TEXT,
    amount_paise INTEGER NOT NULL
        CHECK (amount_paise > 0),
    expense_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payment_method TEXT,
    created_by INTEGER,
    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_number TEXT NOT NULL UNIQUE,
    supplier_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN
            ('draft', 'received', 'cancelled')),
    purchase_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_paise INTEGER NOT NULL DEFAULT 0
        CHECK (total_paise >= 0),
    notes TEXT,
    created_by INTEGER,
    FOREIGN KEY (supplier_id)
        REFERENCES suppliers(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity_milli INTEGER NOT NULL
        CHECK (quantity_milli > 0),
    unit_cost_paise INTEGER NOT NULL
        CHECK (unit_cost_paise >= 0),
    line_total_paise INTEGER NOT NULL
        CHECK (line_total_paise >= 0),
    FOREIGN KEY (purchase_id)
        REFERENCES purchase_orders(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS sales_returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_number TEXT NOT NULL UNIQUE,
    invoice_id INTEGER NOT NULL,
    return_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'cancelled')),
    refund_amount_paise INTEGER NOT NULL DEFAULT 0
        CHECK (refund_amount_paise >= 0),
    reason TEXT,
    created_by INTEGER,
    FOREIGN KEY (invoice_id)
        REFERENCES invoices(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS sales_return_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL,
    invoice_item_id INTEGER NOT NULL,
    quantity_milli INTEGER NOT NULL
        CHECK (quantity_milli > 0),
    refund_amount_paise INTEGER NOT NULL
        CHECK (refund_amount_paise >= 0),
    restock INTEGER NOT NULL DEFAULT 1
        CHECK (restock IN (0, 1)),
    FOREIGN KEY (return_id)
        REFERENCES sales_returns(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (invoice_item_id)
        REFERENCES invoice_items(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL
        CHECK (movement_type IN (
            'opening',
            'purchase',
            'sale',
            'sale_return',
            'purchase_return',
            'adjustment',
            'damage'
        )),
    quantity_delta_milli INTEGER NOT NULL
        CHECK (quantity_delta_milli != 0),
    reference_type TEXT,
    reference_id INTEGER,
    reason TEXT,
    created_by INTEGER,
    movement_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE RESTRICT
);

-- Indexes for frequently searched data
CREATE INDEX IF NOT EXISTS idx_products_name
    ON products(name);

CREATE INDEX IF NOT EXISTS idx_products_category
    ON products(category_id);

CREATE INDEX IF NOT EXISTS idx_customers_name
    ON customers(name);

CREATE INDEX IF NOT EXISTS idx_customers_phone
    ON customers(phone);

CREATE INDEX IF NOT EXISTS idx_invoices_date
    ON invoices(invoice_date);

CREATE INDEX IF NOT EXISTS idx_invoices_customer
    ON invoices(customer_id);

CREATE INDEX IF NOT EXISTS idx_invoices_status
    ON invoices(status);

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice
    ON invoice_items(invoice_id);

CREATE INDEX IF NOT EXISTS idx_payments_invoice
    ON payments(invoice_id);

CREATE INDEX IF NOT EXISTS idx_stock_product
    ON stock_movements(product_id, movement_date);

CREATE INDEX IF NOT EXISTS idx_purchase_date
    ON purchase_orders(purchase_date);

CREATE INDEX IF NOT EXISTS idx_expenses_date
    ON expenses(expense_date);

CREATE INDEX IF NOT EXISTS idx_returns_invoice
    ON sales_returns(invoice_id);
"""


# -------------------------------------------------
# INITIALIZE DATABASE
# -------------------------------------------------

def init_db():
    """Create database tables and default settings."""

    with db_session() as conn:
        conn.executescript(SCHEMA)

        conn.execute("""
            INSERT OR IGNORE INTO business_settings
                (id, business_name)
            VALUES (1, 'SmartBill Retail')
        """)
        
@contextmanager
def db_session():
    """Open a database session and always close it."""

    conn = get_connection()

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



# -------------------------------------------------
# DATABASE HEALTH CHECK
# -------------------------------------------------

def check_db():
    """Return basic database status."""

    with db_session() as conn:
        result = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        tables = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """).fetchall()

    return {
        "database_path": str(DB_PATH),
        "integrity": result,
        "tables": [row["name"] for row in tables]
    }


if __name__ == "__main__":
    init_db()
    result = check_db()

    print("\nSmartBill Database Initialized")
    print("Database:", result["database_path"])
    print("Integrity:", result["integrity"])
    print("\nTables:")

    for table in result["tables"]:
        print("-", table)
