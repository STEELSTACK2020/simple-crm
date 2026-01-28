"""
Migration script: SQLite to PostgreSQL
Migrates all data from local SQLite database to Railway PostgreSQL.
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connections
SQLITE_PATH = "crm.db"
POSTGRES_URL = os.getenv("DATABASE_URL")

def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_postgres_connection():
    return psycopg2.connect(POSTGRES_URL)

def create_postgres_tables(pg_conn):
    """Create all tables in PostgreSQL."""
    cursor = pg_conn.cursor()

    # Drop existing tables (in correct order due to foreign keys)
    print("Dropping existing tables...")
    cursor.execute("""
        DROP TABLE IF EXISTS quick_notes CASCADE;
        DROP TABLE IF EXISTS user_email_tokens CASCADE;
        DROP TABLE IF EXISTS quote_items CASCADE;
        DROP TABLE IF EXISTS quotes CASCADE;
        DROP TABLE IF EXISTS deal_contacts CASCADE;
        DROP TABLE IF EXISTS deals CASCADE;
        DROP TABLE IF EXISTS contacts CASCADE;
        DROP TABLE IF EXISTS products CASCADE;
        DROP TABLE IF EXISTS companies CASCADE;
        DROP TABLE IF EXISTS salespeople CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
    """)

    print("Creating tables...")

    # Companies table
    cursor.execute("""
        CREATE TABLE companies (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            phone TEXT,
            email TEXT,
            website TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Salespeople table
    cursor.execute("""
        CREATE TABLE salespeople (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Users table
    cursor.execute("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            first_name TEXT,
            last_name TEXT,
            role TEXT DEFAULT 'salesperson',
            is_active INTEGER DEFAULT 1,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Contacts table
    cursor.execute("""
        CREATE TABLE contacts (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            utm_source TEXT,
            utm_medium TEXT,
            utm_campaign TEXT,
            utm_term TEXT,
            utm_content TEXT,
            deal_value REAL DEFAULT 0,
            deal_closed_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            company_id INTEGER REFERENCES companies(id),
            last_activity_date TIMESTAMP,
            original_source_details TEXT,
            landing_page TEXT,
            referrer TEXT
        )
    """)

    # Deals table
    cursor.execute("""
        CREATE TABLE deals (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            value REAL DEFAULT 0,
            stage TEXT DEFAULT 'new_deal',
            salesperson TEXT,
            utm_source TEXT,
            utm_medium TEXT,
            utm_campaign TEXT,
            expected_close_date TEXT,
            actual_close_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            close_reason TEXT,
            company_id INTEGER REFERENCES companies(id),
            reported_source TEXT
        )
    """)

    # Deal contacts junction table
    cursor.execute("""
        CREATE TABLE deal_contacts (
            id SERIAL PRIMARY KEY,
            deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
            contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            role TEXT DEFAULT 'primary',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(deal_id, contact_id)
        )
    """)

    # Products table
    cursor.execute("""
        CREATE TABLE products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            sku TEXT UNIQUE,
            description TEXT,
            price REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Quotes table
    cursor.execute("""
        CREATE TABLE quotes (
            id SERIAL PRIMARY KEY,
            quote_number TEXT UNIQUE,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            deal_id INTEGER REFERENCES deals(id) ON DELETE SET NULL,
            contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
            customer_name TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            customer_company TEXT,
            salesperson_id INTEGER REFERENCES salespeople(id) ON DELETE SET NULL,
            salesperson_name TEXT,
            salesperson_email TEXT,
            salesperson_phone TEXT,
            subtotal REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            tax_percent REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            total REAL DEFAULT 0,
            quote_date TEXT,
            expiry_date TEXT,
            notes TEXT,
            terms TEXT,
            payment_link TEXT,
            payment_date TEXT,
            financing_link TEXT,
            company_id INTEGER REFERENCES companies(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Quote items table
    cursor.execute("""
        CREATE TABLE quote_items (
            id SERIAL PRIMARY KEY,
            quote_id INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name TEXT NOT NULL,
            product_sku TEXT,
            description TEXT,
            quantity REAL DEFAULT 1,
            unit_price REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0
        )
    """)

    # User email tokens table
    cursor.execute("""
        CREATE TABLE user_email_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            token_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, provider)
        )
    """)

    # Quick notes table
    cursor.execute("""
        CREATE TABLE quick_notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER DEFAULT 1,
            content TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    print("Creating indexes...")
    cursor.execute("CREATE INDEX idx_contacts_email ON contacts(email)")
    cursor.execute("CREATE INDEX idx_contacts_utm_source ON contacts(utm_source)")
    cursor.execute("CREATE INDEX idx_contacts_company_id ON contacts(company_id)")
    cursor.execute("CREATE INDEX idx_deals_stage ON deals(stage)")
    cursor.execute("CREATE INDEX idx_deals_utm_source ON deals(utm_source)")
    cursor.execute("CREATE INDEX idx_deals_utm_medium ON deals(utm_medium)")
    cursor.execute("CREATE INDEX idx_deals_company_id ON deals(company_id)")
    cursor.execute("CREATE INDEX idx_deal_contacts_deal_id ON deal_contacts(deal_id)")
    cursor.execute("CREATE INDEX idx_deal_contacts_contact_id ON deal_contacts(contact_id)")
    cursor.execute("CREATE INDEX idx_products_sku ON products(sku)")
    cursor.execute("CREATE INDEX idx_companies_name ON companies(name)")
    cursor.execute("CREATE INDEX idx_quotes_status ON quotes(status)")
    cursor.execute("CREATE INDEX idx_quotes_deal ON quotes(deal_id)")
    cursor.execute("CREATE INDEX idx_quotes_contact ON quotes(contact_id)")
    cursor.execute("CREATE INDEX idx_quotes_company_id ON quotes(company_id)")
    cursor.execute("CREATE INDEX idx_quote_items_quote ON quote_items(quote_id)")
    cursor.execute("CREATE INDEX idx_users_username ON users(username)")
    cursor.execute("CREATE INDEX idx_email_tokens_user ON user_email_tokens(user_id)")

    pg_conn.commit()
    print("Tables created successfully!")

def migrate_table(sqlite_conn, pg_conn, table_name, columns):
    """Migrate a single table from SQLite to PostgreSQL."""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()

    # Get data from SQLite
    sqlite_cursor.execute(f"SELECT {', '.join(columns)} FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        print(f"  {table_name}: 0 rows (empty)")
        return 0

    # Prepare data for PostgreSQL
    data = [tuple(row) for row in rows]

    # Build INSERT query
    placeholders = ', '.join(['%s'] * len(columns))
    columns_str = ', '.join(columns)

    # Insert into PostgreSQL
    insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

    try:
        pg_cursor.executemany(insert_query, data)
        pg_conn.commit()
        print(f"  {table_name}: {len(rows)} rows migrated")
        return len(rows)
    except Exception as e:
        pg_conn.rollback()
        print(f"  {table_name}: ERROR - {e}")
        return 0

def reset_sequence(pg_conn, table_name):
    """Reset the auto-increment sequence for a table."""
    cursor = pg_conn.cursor()
    try:
        cursor.execute(f"""
            SELECT setval(pg_get_serial_sequence('{table_name}', 'id'),
                   COALESCE((SELECT MAX(id) FROM {table_name}), 1))
        """)
        pg_conn.commit()
    except Exception as e:
        print(f"  Warning: Could not reset sequence for {table_name}: {e}")
        pg_conn.rollback()

def run_migration():
    """Run the full migration."""
    print("=" * 50)
    print("SQLite to PostgreSQL Migration")
    print("=" * 50)

    # Connect to databases
    print("\nConnecting to databases...")
    sqlite_conn = get_sqlite_connection()
    pg_conn = get_postgres_connection()
    print("Connected!")

    # Create tables
    print("\n" + "-" * 50)
    create_postgres_tables(pg_conn)

    # Migrate data
    print("\n" + "-" * 50)
    print("Migrating data...")

    # Order matters due to foreign key constraints
    migrations = [
        ('companies', ['id', 'name', 'phone', 'email', 'website', 'address', 'city', 'state', 'zip', 'notes', 'created_at', 'updated_at']),
        ('salespeople', ['id', 'name', 'first_name', 'last_name', 'email', 'phone', 'created_at']),
        ('users', ['id', 'username', 'password_hash', 'email', 'first_name', 'last_name', 'role', 'is_active', 'last_login', 'created_at', 'updated_at']),
        ('contacts', ['id', 'first_name', 'last_name', 'email', 'phone', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'deal_value', 'deal_closed_date', 'created_at', 'updated_at', 'notes', 'company_id', 'last_activity_date', 'original_source_details', 'landing_page', 'referrer']),
        ('deals', ['id', 'name', 'value', 'stage', 'salesperson', 'utm_source', 'utm_medium', 'utm_campaign', 'expected_close_date', 'actual_close_date', 'created_at', 'updated_at', 'notes', 'close_reason', 'company_id', 'reported_source']),
        ('deal_contacts', ['id', 'deal_id', 'contact_id', 'role', 'added_at']),
        ('products', ['id', 'name', 'sku', 'description', 'price', 'is_active', 'created_at', 'updated_at']),
        ('quotes', ['id', 'quote_number', 'title', 'status', 'deal_id', 'contact_id', 'customer_name', 'customer_email', 'customer_phone', 'customer_company', 'salesperson_id', 'salesperson_name', 'salesperson_email', 'salesperson_phone', 'subtotal', 'discount_percent', 'discount_amount', 'tax_percent', 'tax_amount', 'total', 'quote_date', 'expiry_date', 'notes', 'terms', 'payment_link', 'payment_date', 'financing_link', 'company_id', 'created_at', 'updated_at']),
        ('quote_items', ['id', 'quote_id', 'product_id', 'product_name', 'product_sku', 'description', 'quantity', 'unit_price', 'discount_percent', 'line_total', 'sort_order']),
        ('user_email_tokens', ['id', 'user_id', 'provider', 'token_data', 'created_at', 'updated_at']),
        ('quick_notes', ['id', 'user_id', 'content', 'updated_at']),
    ]

    total_rows = 0
    for table_name, columns in migrations:
        count = migrate_table(sqlite_conn, pg_conn, table_name, columns)
        total_rows += count
        # Reset auto-increment sequence
        reset_sequence(pg_conn, table_name)

    # Close connections
    sqlite_conn.close()
    pg_conn.close()

    print("\n" + "=" * 50)
    print(f"Migration complete! Total rows migrated: {total_rows}")
    print("=" * 50)

if __name__ == "__main__":
    run_migration()
