"""
Simple CRM Database Module
PostgreSQL database for contact management with UTM tracking and deal values.
"""

import os
import psycopg2
import psycopg2.errors
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import sqlite3  # For fallback and exception handling

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback to SQLite for local dev if no DATABASE_URL
USE_POSTGRES = DATABASE_URL is not None

# Connection pool for PostgreSQL (reuses connections for better performance)
_connection_pool = None

def get_pool():
    """Get or create the connection pool."""
    global _connection_pool
    if _connection_pool is None and USE_POSTGRES:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor
        )
    return _connection_pool


class PostgresCursorWrapper:
    """Wrapper for PostgreSQL cursor that converts ? to %s in queries."""
    def __init__(self, cursor):
        self._cursor = cursor
        self._lastrowid = None

    def execute(self, query, params=None):
        import re
        # Convert SQLite ? placeholders to PostgreSQL %s
        query = query.replace('?', '%s')
        # Convert SQLite GROUP_CONCAT to PostgreSQL STRING_AGG
        query = query.replace('GROUP_CONCAT(', 'STRING_AGG(')

        # Convert INSERT OR IGNORE for deal_contacts table
        if 'INSERT OR IGNORE INTO deal_contacts' in query:
            query = query.replace('INSERT OR IGNORE INTO', 'INSERT INTO')
            query = query.rstrip() + ' ON CONFLICT (deal_id, contact_id) DO NOTHING'

        # Convert INSERT OR REPLACE for deal_contacts table
        elif 'INSERT OR REPLACE INTO deal_contacts' in query:
            query = query.replace('INSERT OR REPLACE INTO', 'INSERT INTO')
            query = query.rstrip() + ' ON CONFLICT (deal_id, contact_id) DO UPDATE SET role = EXCLUDED.role'

        # Convert INSERT OR REPLACE for user_email_tokens table
        elif 'INSERT OR REPLACE INTO user_email_tokens' in query:
            query = query.replace('INSERT OR REPLACE INTO', 'INSERT INTO')
            query = query.rstrip() + ' ON CONFLICT (user_id, provider) DO UPDATE SET token_data = EXCLUDED.token_data, updated_at = EXCLUDED.updated_at'

        # Convert INSERT OR REPLACE for app_settings table
        elif 'INSERT OR REPLACE INTO app_settings' in query:
            query = query.replace('INSERT OR REPLACE INTO', 'INSERT INTO')
            query = query.rstrip() + ' ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = EXCLUDED.updated_at'

        # Add RETURNING id for INSERT statements to support lastrowid
        # But NOT for ON CONFLICT DO NOTHING (junction tables may not have id column)
        # And NOT for tables without an id column (app_settings uses setting_key as PK)
        is_insert = query.strip().upper().startswith('INSERT') and 'RETURNING' not in query.upper()
        needs_returning = is_insert and 'DO NOTHING' not in query.upper() and 'app_settings' not in query
        if needs_returning:
            query = query.rstrip().rstrip(';') + ' RETURNING id'

        if params:
            result = self._cursor.execute(query, params)
        else:
            result = self._cursor.execute(query)

        # Fetch the returned id for INSERT statements (only if RETURNING was added)
        if needs_returning:
            row = self._cursor.fetchone()
            if row:
                self._lastrowid = row['id'] if isinstance(row, dict) else row[0]

        return result

    def executemany(self, query, params_list):
        query = query.replace('?', '%s')
        return self._cursor.executemany(query, params_list)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size)

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._lastrowid

    @property
    def description(self):
        return self._cursor.description


class PostgresConnectionWrapper:
    """Wrapper for PostgreSQL connection that returns wrapped cursors and returns to pool on close."""
    def __init__(self, conn, pool_ref=None):
        self._conn = conn
        self._pool = pool_ref

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        """Return connection to pool instead of closing it."""
        if self._pool:
            self._pool.putconn(self._conn)
        else:
            self._conn.close()


def get_connection():
    """Get a database connection with row factory for dict-like access."""
    if USE_POSTGRES:
        p = get_pool()
        if p:
            conn = p.getconn()
            return PostgresConnectionWrapper(conn, pool_ref=p)
        else:
            # Fallback if pool fails
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return PostgresConnectionWrapper(conn)
    else:
        # Fallback to SQLite for local development
        import sqlite3
        DATABASE_PATH = Path(__file__).parent / "crm.db"
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def execute_query(cursor, query, params=None):
    """Execute a query, converting ? to %s for PostgreSQL compatibility."""
    if USE_POSTGRES:
        # Convert SQLite ? placeholders to PostgreSQL %s
        query = query.replace('?', '%s')
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor


def init_database():
    """Initialize the database with the contacts and deals tables."""
    if USE_POSTGRES:
        # Tables already created in PostgreSQL via migration
        print("Using PostgreSQL - tables already exist")
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,

            -- UTM Parameters for tracking source
            utm_source TEXT,      -- e.g., google, facebook, newsletter
            utm_medium TEXT,      -- e.g., cpc, organic, email
            utm_campaign TEXT,    -- e.g., spring_sale, brand_awareness
            utm_term TEXT,        -- e.g., keyword searched
            utm_content TEXT,     -- e.g., ad variation identifier

            -- Deal tracking (legacy - keeping for backwards compatibility)
            deal_value REAL DEFAULT 0,  -- Dollar amount if they closed a deal
            deal_closed_date TEXT,      -- When the deal was closed

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)

    # Deals table - the main entity for tracking opportunities
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value REAL DEFAULT 0,
            stage TEXT DEFAULT 'new_deal',

            -- Salesperson assignment
            salesperson TEXT,

            -- UTM Parameters for tracking source
            utm_source TEXT,
            utm_medium TEXT,
            utm_campaign TEXT,

            -- Dates
            expected_close_date TEXT,
            actual_close_date TEXT,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)

    # Add salesperson column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE deals ADD COLUMN salesperson TEXT")
    except:
        pass  # Column already exists

    # Add close_reason column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE deals ADD COLUMN close_reason TEXT")
    except:
        pass  # Column already exists

    # Junction table to link deals to contacts (many-to-many)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deal_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            role TEXT DEFAULT 'primary',  -- primary, secondary, etc.
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
            UNIQUE(deal_id, contact_id)
        )
    """)

    # Create index on email for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)")

    # Create index on UTM source for analytics
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_utm_source ON contacts(utm_source)")

    # Create indexes for deals
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_utm_source ON deals(utm_source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deal_contacts_deal ON deal_contacts(deal_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deal_contacts_contact ON deal_contacts(contact_id)")

    # Salespeople table - static list of sales team members
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salespeople (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration: Add new columns to salespeople table
    try:
        cursor.execute("ALTER TABLE salespeople ADD COLUMN first_name TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE salespeople ADD COLUMN last_name TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE salespeople ADD COLUMN email TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE salespeople ADD COLUMN phone TEXT")
    except:
        pass

    # Products table - for quotes and pricing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT UNIQUE,
            description TEXT,
            price REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create index on SKU for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")

    # Companies table - central entity for businesses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            phone TEXT,
            email TEXT,
            website TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create index on company name
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)")

    # Add company_id to deals if not exists
    try:
        cursor.execute("ALTER TABLE deals ADD COLUMN company_id INTEGER REFERENCES companies(id)")
    except:
        pass

    # Add reported_source to deals - what salesperson records from customer
    try:
        cursor.execute("ALTER TABLE deals ADD COLUMN reported_source TEXT")
    except:
        pass

    # Add company_id to contacts if not exists
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN company_id INTEGER REFERENCES companies(id)")
    except:
        pass

    # Add last_activity_date to contacts for tracking engagement
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN last_activity_date TEXT")
    except:
        pass

    # Add original_source_details for manual entry by sales team
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN original_source_details TEXT")
    except:
        pass

    # Add landing_page for tracking which page the visitor first landed on
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN landing_page TEXT")
    except:
        pass

    # Add referrer for tracking where the visitor came from
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN referrer TEXT")
    except:
        pass

    # Email sync tracking columns for "Awaiting Response" feature
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN last_outbound_email_date TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN last_inbound_email_date TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN last_email_subject TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN email_synced_at TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN followup_dismissed_at TEXT")
    except:
        pass

    # Quotes table - for creating and tracking quotes/proposals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_number TEXT UNIQUE,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'draft',

            -- Customer info
            deal_id INTEGER,
            contact_id INTEGER,
            customer_name TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            customer_company TEXT,

            -- Salesperson info
            salesperson_id INTEGER,
            salesperson_name TEXT,
            salesperson_email TEXT,
            salesperson_phone TEXT,

            -- Pricing
            subtotal REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            tax_percent REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            total REAL DEFAULT 0,

            -- Dates
            quote_date TEXT,
            expiry_date TEXT,

            -- Content
            notes TEXT,
            terms TEXT,

            -- Payment & Financing
            payment_link TEXT,
            payment_date TEXT,
            financing_link TEXT,
            company_id INTEGER REFERENCES companies(id),

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE SET NULL,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL,
            FOREIGN KEY (salesperson_id) REFERENCES salespeople(id) ON DELETE SET NULL
        )
    """)

    # Add columns to quotes for existing databases (migrations)
    try:
        cursor.execute("ALTER TABLE quotes ADD COLUMN company_id INTEGER REFERENCES companies(id)")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE quotes ADD COLUMN payment_link TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE quotes ADD COLUMN payment_date TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE quotes ADD COLUMN financing_link TEXT")
    except:
        pass

    # Quote line items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quote_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER NOT NULL,
            product_id INTEGER,

            -- Item details (stored at time of quote creation)
            product_name TEXT NOT NULL,
            product_sku TEXT,
            description TEXT,

            -- Pricing
            quantity REAL DEFAULT 1,
            unit_price REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            line_total REAL DEFAULT 0,

            -- Order in quote
            sort_order INTEGER DEFAULT 0,

            FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        )
    """)

    # Create indexes for quotes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_deal ON quotes(deal_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_contact ON quotes(contact_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quote_items_quote ON quote_items(quote_id)")

    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_company_id ON contacts(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_company_id ON deals(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_utm_medium ON deals(utm_medium)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_company_id ON quotes(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deal_contacts_deal_id ON deal_contacts(deal_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deal_contacts_contact_id ON deal_contacts(contact_id)")

    # Users table for authentication
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            first_name TEXT,
            last_name TEXT,
            role TEXT DEFAULT 'salesperson',  -- 'admin' or 'salesperson'
            is_active INTEGER DEFAULT 1,
            last_login TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

    # User email tokens - stores OAuth tokens per user per provider
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_email_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,  -- 'gmail' or 'outlook'
            token_data TEXT NOT NULL,  -- JSON blob with tokens
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, provider)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_tokens_user ON user_email_tokens(user_id)")

    # Quick notes - scratchpad for user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quick_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            content TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


def add_contact(first_name, last_name, email, phone=None,
                utm_source=None, utm_medium=None, utm_campaign=None,
                utm_term=None, utm_content=None, deal_value=0,
                deal_closed_date=None, notes=None, landing_page=None, referrer=None,
                sales_notes=None):
    """Add a new contact to the database."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO contacts (
                first_name, last_name, email, phone,
                utm_source, utm_medium, utm_campaign, utm_term, utm_content,
                deal_value, deal_closed_date, notes, landing_page, referrer, sales_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (first_name, last_name, email, phone,
              utm_source, utm_medium, utm_campaign, utm_term, utm_content,
              deal_value, deal_closed_date, notes, landing_page, referrer, sales_notes))
        conn.commit()
        contact_id = cursor.lastrowid
        return {"success": True, "id": contact_id}
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation) as e:
        return {"success": False, "error": f"Email already exists: {email}"}
    finally:
        conn.close()


def update_contact(contact_id, **kwargs):
    """Update a contact's information. Automatically updates last_activity_date."""
    conn = get_connection()
    cursor = conn.cursor()

    # Build dynamic update query
    allowed_fields = [
        'first_name', 'last_name', 'email', 'phone',
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'deal_value', 'deal_closed_date', 'notes', 'last_activity_date', 'company_id',
        'original_source_details', 'sales_notes', 'salesperson_id', 'created_at'
    ]

    updates = []
    values = []
    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return {"success": False, "error": "No valid fields to update"}

    # Always update last_activity_date when contact is modified
    if 'last_activity_date' not in kwargs:
        updates.append("last_activity_date = ?")
        values.append(datetime.now().isoformat())

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(contact_id)

    query = f"UPDATE contacts SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()

    return {"success": True, "updated": cursor.rowcount}


def sync_utm_from_contact_to_deals(contact_id):
    """Sync UTM fields from a contact to all associated deals."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get the contact's UTM fields
    cursor.execute("""
        SELECT utm_source, utm_medium, utm_campaign
        FROM contacts WHERE id = ?
    """, (contact_id,))
    contact = cursor.fetchone()

    if not contact:
        conn.close()
        return {"success": False, "error": "Contact not found"}

    utm_source = contact['utm_source']
    utm_medium = contact['utm_medium']
    utm_campaign = contact['utm_campaign']

    # Update all deals linked to this contact
    cursor.execute("""
        UPDATE deals
        SET utm_source = ?,
            utm_medium = ?,
            utm_campaign = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id IN (
            SELECT deal_id FROM deal_contacts WHERE contact_id = ?
        )
    """, (utm_source, utm_medium, utm_campaign, contact_id))

    updated_count = cursor.rowcount
    conn.commit()
    conn.close()

    return {"success": True, "deals_updated": updated_count}


def set_deal_value(contact_id, deal_value):
    """Set a deal value for a contact (when they close a deal)."""
    return update_contact(
        contact_id,
        deal_value=deal_value,
        deal_closed_date=datetime.now().isoformat()
    )


def update_contact_activity(contact_id):
    """Update the last_activity_date for a contact to now."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE contacts SET last_activity_date = ? WHERE id = ?
    """, (datetime.now().isoformat(), contact_id))
    conn.commit()
    conn.close()
    return {"success": True}


def get_untouched_leads(days_threshold=7, limit=20):
    """
    Get contacts that have no activity (no notes, no last_activity_date).
    Returns contacts that need attention.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get contacts with no activity
    # A contact is "untouched" if:
    # 1. last_activity_date is NULL
    # 2. notes is NULL or empty
    cursor.execute("""
        SELECT id, first_name, last_name, email, phone, created_at, last_activity_date, notes
        FROM contacts
        WHERE last_activity_date IS NULL
          AND (notes IS NULL OR notes = '')
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_contact_email_status(contact_id, last_outbound_date, last_inbound_date, last_outbound_subject):
    """Update the email tracking fields for a contact."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE contacts
        SET last_outbound_email_date = ?,
            last_inbound_email_date = ?,
            last_email_subject = ?,
            email_synced_at = ?
        WHERE id = ?
    """, (last_outbound_date, last_inbound_date, last_outbound_subject,
          datetime.now().isoformat(), contact_id))
    conn.commit()
    conn.close()
    return {"success": True}


def dismiss_contact_followup(contact_id):
    """Dismiss a contact from the awaiting response queue (e.g., talked on phone)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE contacts SET followup_dismissed_at = ? WHERE id = ?
    """, (datetime.now().isoformat(), contact_id))
    conn.commit()
    conn.close()
    return {"success": True}


def get_awaiting_response_contacts(days_threshold=3, limit=20):
    """
    Get contacts awaiting a response - emailed but no reply within threshold days.
    Only includes contacts created from 2026-01-01 onwards.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Use different date functions based on database type
    if os.environ.get('DATABASE_URL'):
        # PostgreSQL
        date_diff = f"EXTRACT(EPOCH FROM (NOW() - last_outbound_email_date::timestamp)) / 86400"
    else:
        # SQLite
        date_diff = "julianday('now') - julianday(last_outbound_email_date)"

    cursor.execute(f"""
        SELECT id, first_name, last_name, email, phone, created_at,
               last_outbound_email_date, last_inbound_email_date,
               last_email_subject, email_synced_at, followup_dismissed_at
        FROM contacts
        WHERE last_outbound_email_date IS NOT NULL
          AND (
            last_inbound_email_date IS NULL
            OR last_outbound_email_date > last_inbound_email_date
          )
          AND {date_diff} >= ?
          AND (followup_dismissed_at IS NULL
               OR last_outbound_email_date > followup_dismissed_at)
          AND created_at >= '2026-01-01'
        ORDER BY last_outbound_email_date ASC
        LIMIT ?
    """, (days_threshold, limit))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_contacts_for_email_sync(limit=500):
    """Get contacts with email addresses for syncing email status."""
    conn = get_connection()
    cursor = conn.cursor()
    # Use CASE to handle NULL sorting (works in both SQLite and PostgreSQL)
    cursor.execute("""
        SELECT id, email FROM contacts
        WHERE email IS NOT NULL AND email != ''
        ORDER BY
            CASE WHEN email_synced_at IS NULL THEN 0 ELSE 1 END,
            email_synced_at ASC,
            created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_contacts_by_activity(limit=100, offset=0):
    """Get all contacts ordered by last activity (most recent first), with never-contacted at the end."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM contacts
        ORDER BY
            CASE WHEN last_activity_date IS NULL THEN 1 ELSE 0 END,
            last_activity_date DESC,
            created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_contact(contact_id):
    """Get a single contact by ID, including salesperson info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, s.name as salesperson_name
        FROM contacts c
        LEFT JOIN salespeople s ON c.salesperson_id = s.id
        WHERE c.id = ?
    """, (contact_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_deals_for_contact(contact_id):
    """Get all deals associated with a contact."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.*, dc.role
        FROM deals d
        JOIN deal_contacts dc ON d.id = dc.deal_id
        WHERE dc.contact_id = ?
        ORDER BY d.updated_at DESC
    """, (contact_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_contact_by_email(email):
    """Get a contact by email address."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_contacts(limit=100, offset=0, sort_by='created_at', sort_dir='desc'):
    """Get all contacts with pagination and sorting."""
    conn = get_connection()
    cursor = conn.cursor()

    # Whitelist of allowed sort columns to prevent SQL injection
    valid_columns = ['first_name', 'last_name', 'email', 'phone', 'utm_source', 'utm_medium',
                     'last_activity_date', 'created_at', 'deal_value']
    if sort_by not in valid_columns:
        sort_by = 'created_at'

    sort_direction = 'DESC' if sort_dir.lower() == 'desc' else 'ASC'

    # Use correct placeholder for PostgreSQL vs SQLite
    if USE_POSTGRES:
        query = f"SELECT * FROM contacts ORDER BY {sort_by} {sort_direction} LIMIT %s OFFSET %s"
    else:
        query = f"SELECT * FROM contacts ORDER BY {sort_by} {sort_direction} LIMIT ? OFFSET ?"

    cursor.execute(query, (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_contacts_count():
    """Get total number of contacts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM contacts")
    result = cursor.fetchone()
    conn.close()
    return result['count'] if result else 0


def get_contacts_by_date_range(from_date, to_date):
    """Get contacts created within a date range. Returns first_name, last_name, email."""
    conn = get_connection()
    cursor = conn.cursor()
    # Add a day to to_date so it includes contacts created on that day
    if USE_POSTGRES:
        cursor.execute("""
            SELECT first_name, last_name, email FROM contacts
            WHERE created_at >= %s AND created_at < %s
            ORDER BY created_at DESC
        """, (from_date, to_date))
    else:
        cursor.execute("""
            SELECT first_name, last_name, email FROM contacts
            WHERE created_at >= ? AND created_at < ?
            ORDER BY created_at DESC
        """, (from_date, to_date))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def search_contacts(query):
    """Search contacts by name or email. Supports full name search (e.g. 'Chris Vistage')."""
    conn = get_connection()
    cursor = conn.cursor()
    search_term = f"%{query}%"

    # Use ILIKE for PostgreSQL (case-insensitive), LIKE for SQLite
    if USE_POSTGRES:
        cursor.execute("""
            SELECT * FROM contacts
            WHERE first_name ILIKE %s OR last_name ILIKE %s OR email ILIKE %s
                OR (first_name || ' ' || last_name) ILIKE %s
            ORDER BY created_at DESC
        """, (search_term, search_term, search_term, search_term))
    else:
        cursor.execute("""
            SELECT * FROM contacts
            WHERE first_name LIKE ? OR last_name LIKE ? OR email LIKE ?
                OR (first_name || ' ' || last_name) LIKE ?
            ORDER BY created_at DESC
        """, (search_term, search_term, search_term, search_term))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_contact(contact_id):
    """Delete a contact by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0, "deleted": deleted}


def get_analytics(start_date=None, end_date=None):
    """Get dashboard analytics data, optionally filtered by deal close date range."""
    conn = get_connection()
    cursor = conn.cursor()

    analytics = {}

    # Store filter info
    analytics['filter_start'] = start_date
    analytics['filter_end'] = end_date
    analytics['is_filtered'] = start_date is not None or end_date is not None

    # Build date filter clause for deal-related queries
    date_filter = ""
    date_params = []
    if start_date and end_date:
        date_filter = "AND deal_closed_date >= ? AND deal_closed_date <= ?"
        date_params = [start_date, end_date]
    elif start_date:
        date_filter = "AND deal_closed_date >= ?"
        date_params = [start_date]
    elif end_date:
        date_filter = "AND deal_closed_date <= ?"
        date_params = [end_date]

    # Total contacts (not filtered by date)
    cursor.execute("SELECT COUNT(*) as count FROM contacts")
    analytics['total_contacts'] = cursor.fetchone()['count']

    # Total deal value (filtered by close date if specified)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(SUM(deal_value), 0) as total
            FROM contacts
            WHERE deal_value > 0 AND deal_closed_date IS NOT NULL {date_filter}
        """, date_params)
    else:
        cursor.execute("SELECT COALESCE(SUM(deal_value), 0) as total FROM contacts WHERE deal_value > 0")
    analytics['total_deal_value'] = cursor.fetchone()['total']

    # Contacts with deals closed (filtered)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM contacts
            WHERE deal_value > 0 AND deal_closed_date IS NOT NULL {date_filter}
        """, date_params)
    else:
        cursor.execute("SELECT COUNT(*) as count FROM contacts WHERE deal_value > 0")
    analytics['closed_deals'] = cursor.fetchone()['count']

    # Average deal value (filtered)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(AVG(deal_value), 0) as avg
            FROM contacts
            WHERE deal_value > 0 AND deal_closed_date IS NOT NULL {date_filter}
        """, date_params)
    else:
        cursor.execute("SELECT COALESCE(AVG(deal_value), 0) as avg FROM contacts WHERE deal_value > 0")
    analytics['average_deal_value'] = cursor.fetchone()['avg']

    # Contacts by UTM source (revenue filtered by close date)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(utm_source, 'Direct/Unknown') as source,
                   COUNT(*) as count,
                   COALESCE(SUM(CASE WHEN deal_closed_date IS NOT NULL {date_filter.replace('AND', 'AND deal_closed_date IS NOT NULL AND') if date_filter else ''} THEN deal_value ELSE 0 END), 0) as revenue
            FROM contacts
            WHERE deal_value > 0 AND deal_closed_date IS NOT NULL {date_filter}
            GROUP BY utm_source
            ORDER BY revenue DESC
        """, date_params + date_params if date_filter else date_params)
    else:
        cursor.execute("""
            SELECT COALESCE(utm_source, 'Direct/Unknown') as source,
                   COUNT(*) as count,
                   COALESCE(SUM(deal_value), 0) as revenue
            FROM contacts
            GROUP BY utm_source
            ORDER BY count DESC
        """)
    analytics['by_source'] = [dict(row) for row in cursor.fetchall()]

    # Contacts by UTM medium (revenue filtered by close date)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(utm_medium, 'Unknown') as medium,
                   COUNT(*) as count,
                   COALESCE(SUM(deal_value), 0) as revenue
            FROM contacts
            WHERE deal_value > 0 AND deal_closed_date IS NOT NULL {date_filter}
            GROUP BY utm_medium
            ORDER BY revenue DESC
        """, date_params)
    else:
        cursor.execute("""
            SELECT COALESCE(utm_medium, 'Unknown') as medium,
                   COUNT(*) as count,
                   COALESCE(SUM(deal_value), 0) as revenue
            FROM contacts
            GROUP BY utm_medium
            ORDER BY count DESC
        """)
    analytics['by_medium'] = [dict(row) for row in cursor.fetchall()]

    # Recent contacts (last 10)
    cursor.execute("""
        SELECT id, first_name, last_name, email, deal_value, created_at
        FROM contacts
        ORDER BY created_at DESC
        LIMIT 10
    """)
    analytics['recent_contacts'] = [dict(row) for row in cursor.fetchall()]

    # Recent closed deals (sorted by close date, filtered if dates specified)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT id, first_name, last_name, email, deal_value,
                   deal_closed_date, created_at, utm_source
            FROM contacts
            WHERE deal_value > 0 AND deal_closed_date IS NOT NULL {date_filter}
            ORDER BY deal_closed_date DESC
            LIMIT 10
        """, date_params)
    else:
        cursor.execute("""
            SELECT id, first_name, last_name, email, deal_value,
                   deal_closed_date, created_at, utm_source
            FROM contacts
            WHERE deal_value > 0 AND deal_closed_date IS NOT NULL
            ORDER BY deal_closed_date DESC
            LIMIT 10
        """)
    analytics['recent_closed_deals'] = [dict(row) for row in cursor.fetchall()]

    # Deals pending close date (have value but no close date)
    cursor.execute("""
        SELECT id, first_name, last_name, email, deal_value, created_at, utm_source
        FROM contacts
        WHERE deal_value > 0 AND deal_closed_date IS NULL
        ORDER BY created_at DESC
    """)
    analytics['pending_close_date'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return analytics


def get_year_comparison():
    """Get year-over-year comparison data for the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    comparison = {}

    # Get revenue and deal count by year
    cursor.execute("""
        SELECT
            substr(deal_closed_date, 1, 4) as year,
            COUNT(*) as deal_count,
            COALESCE(SUM(deal_value), 0) as total_revenue,
            COALESCE(AVG(deal_value), 0) as avg_deal
        FROM contacts
        WHERE deal_value > 0 AND deal_closed_date IS NOT NULL
        GROUP BY substr(deal_closed_date, 1, 4)
        ORDER BY year DESC
    """)
    comparison['by_year'] = [dict(row) for row in cursor.fetchall()]

    # Get revenue by source for each year
    cursor.execute("""
        SELECT
            substr(deal_closed_date, 1, 4) as year,
            COALESCE(utm_source, 'Direct/Unknown') as source,
            COUNT(*) as deal_count,
            COALESCE(SUM(deal_value), 0) as revenue
        FROM contacts
        WHERE deal_value > 0 AND deal_closed_date IS NOT NULL
        GROUP BY substr(deal_closed_date, 1, 4), utm_source
        ORDER BY year DESC, revenue DESC
    """)
    comparison['by_year_source'] = [dict(row) for row in cursor.fetchall()]

    # Get monthly breakdown for current and previous year
    cursor.execute("""
        SELECT
            substr(deal_closed_date, 1, 7) as month,
            COUNT(*) as deal_count,
            COALESCE(SUM(deal_value), 0) as revenue
        FROM contacts
        WHERE deal_value > 0 AND deal_closed_date IS NOT NULL
        GROUP BY substr(deal_closed_date, 1, 7)
        ORDER BY month DESC
        LIMIT 24
    """)
    comparison['by_month'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return comparison


def get_leads_by_month_medium(year=None):
    """Get leads (contacts) broken down by month and medium for bar chart."""
    # Default return structure in case of error
    default_return = {
        'year': str(datetime.now().year),
        'months': [f"{datetime.now().year}-{str(m).zfill(2)}" for m in range(1, 13)],
        'month_names': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        'mediums': ['Unknown'],
        'data': {'Unknown': [0] * 12},
        'totals': [0] * 12,
        'available_years': [str(datetime.now().year)],
        'raw': []
    }

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # If no year specified, use current year
        if not year:
            year = str(datetime.now().year)
        else:
            year = str(year)

        # All 12 months for the year
        all_months = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        # Get all leads grouped by month and medium for the specified year
        if USE_POSTGRES:
            cursor.execute("""
                SELECT
                    TO_CHAR(created_at::timestamp, 'YYYY-MM') as month,
                    COALESCE(utm_medium, 'Unknown') as medium,
                    COUNT(*) as lead_count
                FROM contacts
                WHERE EXTRACT(YEAR FROM created_at::timestamp) = %s
                GROUP BY TO_CHAR(created_at::timestamp, 'YYYY-MM'), COALESCE(utm_medium, 'Unknown')
                ORDER BY month, lead_count DESC
            """, (int(year),))
        else:
            cursor.execute("""
                SELECT
                    substr(created_at, 1, 7) as month,
                    COALESCE(utm_medium, 'Unknown') as medium,
                    COUNT(*) as lead_count
                FROM contacts
                WHERE substr(created_at, 1, 4) = ?
                GROUP BY substr(created_at, 1, 7), utm_medium
                ORDER BY month, lead_count DESC
            """, (year,))
        raw_data = [dict(row) for row in cursor.fetchall()]

        # Get all unique mediums across all data
        cursor.execute("""
            SELECT DISTINCT COALESCE(utm_medium, 'Unknown') as medium
            FROM contacts
        """)
        mediums = [row['medium'] for row in cursor.fetchall()]
        if not mediums:
            mediums = ['Unknown']

        # Get available years for the dropdown
        if USE_POSTGRES:
            cursor.execute("""
                SELECT DISTINCT EXTRACT(YEAR FROM created_at::timestamp) as year
                FROM contacts
                WHERE created_at IS NOT NULL
                ORDER BY year DESC
            """)
            available_years = [str(int(row['year'])) for row in cursor.fetchall() if row['year']]
        else:
            cursor.execute("""
                SELECT DISTINCT substr(created_at, 1, 4) as year
                FROM contacts
                WHERE created_at IS NOT NULL
                ORDER BY year DESC
            """)
            available_years = [row[0] for row in cursor.fetchall() if row[0]]

        # Ensure current year is in list
        if year not in available_years:
            available_years.insert(0, year)

        # Build structured data for chart
        # Format: { medium: [count_jan, count_feb, ...] }
        chart_data = {}
        for medium in mediums:
            chart_data[medium] = []
            for month in all_months:
                count = 0
                for row in raw_data:
                    if row['month'] == month and row['medium'] == medium:
                        count = row['lead_count']
                        break
                chart_data[medium].append(count)

        # Sort mediums by total leads (largest to smallest)
        medium_totals = {medium: sum(chart_data[medium]) for medium in mediums}
        mediums = sorted(mediums, key=lambda m: medium_totals[m], reverse=True)

        # Calculate totals per month
        monthly_totals = []
        for i, month in enumerate(all_months):
            total = sum(chart_data[medium][i] for medium in mediums)
            monthly_totals.append(total)

        conn.close()
        return {
            'year': year,
            'months': all_months,
            'month_names': month_names,
            'mediums': mediums,
            'data': chart_data,
            'totals': monthly_totals,
            'available_years': available_years,
            'raw': raw_data
        }
    except Exception as e:
        print(f"Error in get_leads_by_month_medium: {e}")
        return default_return


# ============== Deal Functions ==============

DEAL_STAGES = ['new_deal', 'proposal', 'negotiation', 'closed_won', 'closed_lost']

def add_deal(name, value=0, stage='new_deal', salesperson=None, utm_source=None, utm_medium=None,
             utm_campaign=None, expected_close_date=None, notes=None, contact_id=None, company_id=None,
             reported_source=None):
    """Add a new deal to the database."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO deals (
                name, value, stage, salesperson, utm_source, utm_medium, utm_campaign,
                expected_close_date, notes, company_id, reported_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, value, stage, salesperson, utm_source, utm_medium, utm_campaign,
              expected_close_date, notes, company_id, reported_source))
        conn.commit()
        deal_id = cursor.lastrowid

        # If contact_id provided, link the contact to this deal
        if contact_id:
            cursor.execute("""
                INSERT OR IGNORE INTO deal_contacts (deal_id, contact_id, role)
                VALUES (?, ?, 'primary')
            """, (deal_id, contact_id))
            conn.commit()

        return {"success": True, "id": deal_id}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def update_deal(deal_id, **kwargs):
    """Update a deal's information."""
    conn = get_connection()
    cursor = conn.cursor()

    allowed_fields = [
        'name', 'value', 'stage', 'salesperson', 'utm_source', 'utm_medium', 'utm_campaign',
        'expected_close_date', 'actual_close_date', 'notes', 'close_reason', 'company_id',
        'reported_source'
    ]

    updates = []
    values = []
    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return {"success": False, "error": "No valid fields to update"}

    # If stage is being set to 'closed_won' or 'closed_lost', set actual_close_date
    if 'stage' in kwargs and kwargs['stage'] in ['closed_won', 'closed_lost']:
        if 'actual_close_date' not in kwargs:
            updates.append("actual_close_date = ?")
            values.append(datetime.now().strftime('%Y-%m-%d'))

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(deal_id)

    query = f"UPDATE deals SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()

    # If deal is now closed_won, update linked contacts' deal_value
    if 'stage' in kwargs and kwargs['stage'] == 'closed_won':
        sync_contact_deal_values_for_deal(deal_id)

    return {"success": True, "updated": cursor.rowcount}


def sync_contact_deal_values_for_deal(deal_id):
    """Update deal_value for all contacts linked to a specific deal."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get the deal value and stage
    cursor.execute("SELECT value, stage FROM deals WHERE id = ?", (deal_id,))
    deal = cursor.fetchone()

    if not deal:
        conn.close()
        return

    deal_value = deal['value'] or 0
    deal_stage = deal['stage']

    # Get all contacts linked to this deal
    cursor.execute("SELECT contact_id FROM deal_contacts WHERE deal_id = ?", (deal_id,))
    contacts = cursor.fetchall()

    for contact in contacts:
        contact_id = contact['contact_id']
        # Recalculate total deal value from all closed_won deals
        cursor.execute("""
            SELECT COALESCE(SUM(d.value), 0) as total
            FROM deals d
            JOIN deal_contacts dc ON d.id = dc.deal_id
            WHERE dc.contact_id = ? AND d.stage = 'closed_won'
        """, (contact_id,))
        total = cursor.fetchone()['total']

        # Update the contact's deal_value
        cursor.execute("UPDATE contacts SET deal_value = ? WHERE id = ?", (total, contact_id))

    conn.commit()
    conn.close()


def sync_all_contact_deal_values():
    """Recalculate deal_value for ALL contacts based on their linked closed_won deals."""
    conn = get_connection()
    cursor = conn.cursor()

    # Update all contacts with their sum of closed_won deals
    cursor.execute("""
        UPDATE contacts SET deal_value = (
            SELECT COALESCE(SUM(d.value), 0)
            FROM deals d
            JOIN deal_contacts dc ON d.id = dc.deal_id
            WHERE dc.contact_id = contacts.id AND d.stage = 'closed_won'
        )
    """)

    conn.commit()
    updated = cursor.rowcount
    conn.close()
    return updated


def update_deal_stage(deal_id, new_stage):
    """Update just the stage of a deal (for drag-and-drop)."""
    if new_stage not in DEAL_STAGES:
        return {"success": False, "error": f"Invalid stage: {new_stage}"}
    return update_deal(deal_id, stage=new_stage)


def get_deal(deal_id):
    """Get a single deal by ID with its contacts."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT d.*, co.name as company_name
        FROM deals d
        LEFT JOIN companies co ON d.company_id = co.id
        WHERE d.id = ?
    """, (deal_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    deal = dict(row)

    # Get associated contacts
    cursor.execute("""
        SELECT c.*, dc.role
        FROM contacts c
        JOIN deal_contacts dc ON c.id = dc.contact_id
        WHERE dc.deal_id = ?
        ORDER BY dc.role, c.first_name
    """, (deal_id,))
    deal['contacts'] = [dict(r) for r in cursor.fetchall()]

    # Get associated quotes
    cursor.execute("""
        SELECT id, quote_number, title, status, total, created_at
        FROM quotes
        WHERE deal_id = ?
        ORDER BY created_at DESC
    """, (deal_id,))
    deal['quotes'] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return deal


def get_all_deals(limit=100, offset=0):
    """Get all deals with pagination."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM deals ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_deals_by_stage(salesperson=None, stage_filter=None, search=None, date_from=None, date_to=None):
    """Get all deals organized by stage (for pipeline view), optionally filtered by salesperson, stage, search, and/or date range.

    Date filters apply differently based on stage:
    - For closed_won/closed_lost: filters by actual_close_date (when deal closed)
    - For all other stages: filters by created_at (when deal was created)
    """
    conn = get_connection()
    cursor = conn.cursor()

    # If filtering by specific stage, only query that stage
    stages_to_query = [stage_filter] if stage_filter and stage_filter in DEAL_STAGES else DEAL_STAGES

    # Use appropriate syntax for PostgreSQL vs SQLite
    placeholder = "%s" if USE_POSTGRES else "?"
    concat_func = "STRING_AGG(c.first_name || ' ' || c.last_name, ', ')" if USE_POSTGRES else "GROUP_CONCAT(c.first_name || ' ' || c.last_name, ', ')"
    like_op = "ILIKE" if USE_POSTGRES else "LIKE"

    pipeline = {}
    for stage in DEAL_STAGES:
        if stage in stages_to_query:
            # Build query with optional filters
            query = f"""
                SELECT d.*,
                       (SELECT {concat_func}
                        FROM contacts c
                        JOIN deal_contacts dc ON c.id = dc.contact_id
                        WHERE dc.deal_id = d.id) as contact_names
                FROM deals d
                WHERE d.stage = {placeholder}
            """
            params = [stage]

            if salesperson:
                query += f" AND d.salesperson = {placeholder}"
                params.append(salesperson)

            if search:
                query += f" AND d.name {like_op} {placeholder}"
                params.append(f"%{search}%")

            # Use actual_close_date for closed deals, created_at for open deals
            is_closed_stage = stage in ('closed_won', 'closed_lost')
            date_field = "d.actual_close_date" if is_closed_stage else "d.created_at"

            if date_from:
                query += f" AND {date_field} >= {placeholder}"
                params.append(date_from)

            if date_to:
                if is_closed_stage:
                    # actual_close_date is just a date, no time component
                    query += f" AND {date_field} <= {placeholder}"
                    params.append(date_to)
                else:
                    # created_at includes time, so include full day
                    query += f" AND {date_field} <= {placeholder}"
                    params.append(date_to + " 23:59:59")

            query += " ORDER BY d.updated_at DESC"
            cursor.execute(query, params)
            pipeline[stage] = [dict(row) for row in cursor.fetchall()]
        else:
            pipeline[stage] = []  # Empty for stages not being queried

    conn.close()
    return pipeline


def delete_deal(deal_id):
    """Delete a deal by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0, "deleted": deleted}


def add_contact_to_deal(deal_id, contact_id, role='primary'):
    """Link a contact to a deal. Updates the contact's last_activity_date."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR REPLACE INTO deal_contacts (deal_id, contact_id, role)
            VALUES (?, ?, ?)
        """, (deal_id, contact_id, role))
        conn.commit()
        conn.close()
        # Update contact's last activity
        update_contact_activity(contact_id)
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def remove_contact_from_deal(deal_id, contact_id):
    """Remove a contact from a deal."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM deal_contacts WHERE deal_id = ? AND contact_id = ?
    """, (deal_id, contact_id))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0}


def get_deal_analytics(salesperson=None, stage_filter=None, date_from=None, date_to=None):
    """Get analytics focused on deals, with optional filters.

    Date filters apply differently:
    - For won/lost deals: filters by actual_close_date (when deal closed)
    - For pipeline/open deals: filters by created_at (when deal started)
    """
    conn = get_connection()
    cursor = conn.cursor()

    analytics = {}

    # Helper function to build WHERE clause and params for WON deals
    def build_won_query():
        conditions = ["stage = 'closed_won'"]
        params = []
        if salesperson:
            conditions.append("salesperson = ?")
            params.append(salesperson)
        if date_from:
            conditions.append("actual_close_date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("actual_close_date <= ?")
            params.append(date_to)
        return " AND ".join(conditions), params

    # Helper function to build WHERE clause and params for LOST deals
    def build_lost_query():
        conditions = ["stage = 'closed_lost'"]
        params = []
        if salesperson:
            conditions.append("salesperson = ?")
            params.append(salesperson)
        if date_from:
            conditions.append("actual_close_date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("actual_close_date <= ?")
            params.append(date_to)
        return " AND ".join(conditions), params

    # Helper function to build WHERE clause for ALL closed deals (won + lost)
    def build_closed_query():
        conditions = ["stage IN ('closed_won', 'closed_lost')"]
        params = []
        if salesperson:
            conditions.append("salesperson = ?")
            params.append(salesperson)
        if date_from:
            conditions.append("actual_close_date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("actual_close_date <= ?")
            params.append(date_to)
        return " AND ".join(conditions), params

    # Helper function to build WHERE clause for OPEN/PIPELINE deals (uses created_at)
    def build_open_query(exclude_closed=True):
        conditions = []
        params = []
        if exclude_closed:
            conditions.append("stage NOT IN ('closed_won', 'closed_lost')")
        if salesperson:
            conditions.append("salesperson = ?")
            params.append(salesperson)
        if stage_filter:
            conditions.append("stage = ?")
            params.append(stage_filter)
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to + " 23:59:59")
        return " AND ".join(conditions) if conditions else "1=1", params

    # Won deals value (filtered by actual_close_date)
    won_where, won_params = build_won_query()
    cursor.execute(f"""
        SELECT COALESCE(SUM(value), 0) as total, COUNT(*) as count
        FROM deals WHERE {won_where}
    """, won_params)
    row = cursor.fetchone()
    analytics['won_value'] = row['total']
    analytics['won_count'] = row['count']

    # Lost deals count (filtered by actual_close_date)
    lost_where, lost_params = build_lost_query()
    cursor.execute(f"SELECT COUNT(*) as count FROM deals WHERE {lost_where}", lost_params)
    analytics['lost_count'] = cursor.fetchone()['count']

    # Win rate (use actual_close_date for closed deals)
    closed_where, closed_params = build_closed_query()
    cursor.execute(f"""
        SELECT
            COUNT(CASE WHEN stage = 'closed_won' THEN 1 END) as won,
            COUNT(*) as closed
        FROM deals
        WHERE {closed_where}
    """, closed_params)
    row = cursor.fetchone()
    if row['closed'] > 0:
        analytics['win_rate'] = round((row['won'] / row['closed']) * 100, 1)
    else:
        analytics['win_rate'] = 0

    # Average deal value (won deals, filtered by actual_close_date)
    cursor.execute(f"""
        SELECT COALESCE(AVG(value), 0) as avg FROM deals WHERE {won_where}
    """, won_params)
    analytics['avg_deal_value'] = cursor.fetchone()['avg']

    # Total pipeline value (open deals only, filtered by created_at)
    pipeline_where, pipeline_params = build_open_query(exclude_closed=True)
    cursor.execute(f"""
        SELECT COALESCE(SUM(value), 0) as total, COUNT(*) as count
        FROM deals WHERE {pipeline_where}
    """, pipeline_params)
    row = cursor.fetchone()
    analytics['pipeline_value'] = row['total']

    # Total deals count - combine open deals (by created_at) + closed deals (by actual_close_date)
    analytics['total_deals'] = analytics['won_count'] + analytics['lost_count'] + row['count']

    # Deals by stage - for open deals use created_at, for closed use actual_close_date
    by_stage = []

    # Query open stages (uses created_at)
    open_stages_conditions = []
    open_stages_params = []
    open_stages_conditions.append("stage NOT IN ('closed_won', 'closed_lost')")
    if salesperson:
        open_stages_conditions.append("salesperson = ?")
        open_stages_params.append(salesperson)
    if date_from:
        open_stages_conditions.append("created_at >= ?")
        open_stages_params.append(date_from)
    if date_to:
        open_stages_conditions.append("created_at <= ?")
        open_stages_params.append(date_to + " 23:59:59")
    open_stages_where = " AND ".join(open_stages_conditions)

    cursor.execute(f"""
        SELECT stage, COUNT(*) as count, COALESCE(SUM(value), 0) as value
        FROM deals
        WHERE {open_stages_where}
        GROUP BY stage
    """, open_stages_params)
    by_stage.extend([dict(row) for row in cursor.fetchall()])

    # Query closed stages (uses actual_close_date)
    closed_stages_conditions = []
    closed_stages_params = []
    closed_stages_conditions.append("stage IN ('closed_won', 'closed_lost')")
    if salesperson:
        closed_stages_conditions.append("salesperson = ?")
        closed_stages_params.append(salesperson)
    if date_from:
        closed_stages_conditions.append("actual_close_date >= ?")
        closed_stages_params.append(date_from)
    if date_to:
        closed_stages_conditions.append("actual_close_date <= ?")
        closed_stages_params.append(date_to)
    closed_stages_where = " AND ".join(closed_stages_conditions)

    cursor.execute(f"""
        SELECT stage, COUNT(*) as count, COALESCE(SUM(value), 0) as value
        FROM deals
        WHERE {closed_stages_where}
        GROUP BY stage
    """, closed_stages_params)
    by_stage.extend([dict(row) for row in cursor.fetchall()])

    analytics['by_stage'] = by_stage

    # Deals by source (use created_at for all)
    all_deals_where, all_deals_params = build_open_query(exclude_closed=False)
    cursor.execute(f"""
        SELECT COALESCE(utm_source, 'Direct/Unknown') as source,
               COUNT(*) as count,
               COALESCE(SUM(value), 0) as value
        FROM deals
        WHERE {all_deals_where}
        GROUP BY utm_source
        ORDER BY value DESC
    """, all_deals_params)
    analytics['by_source'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return analytics


def search_deals(query):
    """Search deals by name."""
    conn = get_connection()
    cursor = conn.cursor()
    search_term = f"%{query}%"

    # Use ILIKE for PostgreSQL (case-insensitive), LIKE for SQLite
    if USE_POSTGRES:
        cursor.execute("""
            SELECT * FROM deals
            WHERE name ILIKE %s
            ORDER BY created_at DESC
        """, (search_term,))
    else:
        cursor.execute("""
            SELECT * FROM deals
            WHERE name LIKE ?
            ORDER BY created_at DESC
        """, (search_term,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# Predefined UTM mediums
UTM_MEDIUMS = [
    'Paid Search',
    'Organic Search',
    'Paid Social',
    'Organic Social',
    'Direct Traffic',
    'Referrals',
    'Offline Sources',
    'Email',
    'Display',
    'AI Referrals',
    'other'
]


def get_utm_mediums():
    """Get list of UTM mediums (predefined list plus any custom ones from database)."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get existing mediums from contacts and deals
    cursor.execute("""
        SELECT DISTINCT utm_medium FROM contacts WHERE utm_medium IS NOT NULL AND utm_medium != ''
        UNION
        SELECT DISTINCT utm_medium FROM deals WHERE utm_medium IS NOT NULL AND utm_medium != ''
    """)
    db_mediums = [row['utm_medium'] for row in cursor.fetchall()]
    conn.close()

    # Combine predefined with database mediums, removing duplicates
    all_mediums = list(UTM_MEDIUMS)
    for m in db_mediums:
        if m and m.lower() not in [x.lower() for x in all_mediums]:
            all_mediums.append(m)

    return sorted(all_mediums, key=str.lower)


def get_salespeople():
    """Get list of salespeople from the salespeople table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, first_name, last_name, email, phone, created_at
        FROM salespeople
        ORDER BY name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_salesperson(salesperson_id):
    """Get a single salesperson by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salespeople WHERE id = ?", (salesperson_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_salesperson(name, first_name=None, last_name=None, email=None, phone=None):
    """Add a new salesperson to the system."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO salespeople (name, first_name, last_name, email, phone)
            VALUES (?, ?, ?, ?, ?)
        """, (name.strip(), first_name, last_name, email, phone))
        conn.commit()
        salesperson_id = cursor.lastrowid
        return {"success": True, "id": salesperson_id, "name": name.strip()}
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation):
        return {"success": False, "error": "Salesperson already exists"}
    finally:
        conn.close()


def update_salesperson(salesperson_id, **kwargs):
    """Update a salesperson's information."""
    conn = get_connection()
    cursor = conn.cursor()

    allowed_fields = ['name', 'first_name', 'last_name', 'email', 'phone']

    updates = []
    values = []
    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return {"success": False, "error": "No valid fields to update"}

    values.append(salesperson_id)
    query = f"UPDATE salespeople SET {', '.join(updates)} WHERE id = ?"

    try:
        cursor.execute(query, values)
        conn.commit()
        return {"success": True, "updated": cursor.rowcount}
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation):
        return {"success": False, "error": "Name already exists"}
    finally:
        conn.close()


def delete_salesperson(salesperson_id):
    """Delete a salesperson from the system."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM salespeople WHERE id = ?", (salesperson_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0, "deleted": deleted}


def get_dashboard_analytics(start_date=None, end_date=None):
    """Get dashboard analytics data from DEALS table, optionally filtered by close date range."""
    conn = get_connection()
    cursor = conn.cursor()

    analytics = {}

    # Store filter info
    analytics['filter_start'] = start_date
    analytics['filter_end'] = end_date
    analytics['is_filtered'] = start_date is not None or end_date is not None

    # Build date filter clause for closed deals
    date_filter = ""
    date_params = []
    if start_date and end_date:
        date_filter = "AND actual_close_date >= ? AND actual_close_date <= ?"
        date_params = [start_date, end_date]
    elif start_date:
        date_filter = "AND actual_close_date >= ?"
        date_params = [start_date]
    elif end_date:
        date_filter = "AND actual_close_date <= ?"
        date_params = [end_date]

    # Total deals (filtered if date range specified, counting closed_won deals)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COUNT(*) as count FROM deals
            WHERE stage = 'closed_won' {date_filter}
        """, date_params)
    else:
        cursor.execute("SELECT COUNT(*) as count FROM deals WHERE stage = 'closed_won'")
    analytics['total_deals'] = cursor.fetchone()['count']

    # Total contacts (for reference)
    cursor.execute("SELECT COUNT(*) as count FROM contacts")
    analytics['total_contacts'] = cursor.fetchone()['count']

    # Total won deal value (filtered by close date if specified)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(SUM(value), 0) as total
            FROM deals
            WHERE stage = 'closed_won' {date_filter}
        """, date_params)
    else:
        cursor.execute("SELECT COALESCE(SUM(value), 0) as total FROM deals WHERE stage = 'closed_won'")
    analytics['total_deal_value'] = cursor.fetchone()['total']

    # Deals won count (filtered)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM deals
            WHERE stage = 'closed_won' {date_filter}
        """, date_params)
    else:
        cursor.execute("SELECT COUNT(*) as count FROM deals WHERE stage = 'closed_won'")
    analytics['closed_deals'] = cursor.fetchone()['count']

    # Average deal value (won deals, filtered)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(AVG(value), 0) as avg
            FROM deals
            WHERE stage = 'closed_won' {date_filter}
        """, date_params)
    else:
        cursor.execute("SELECT COALESCE(AVG(value), 0) as avg FROM deals WHERE stage = 'closed_won'")
    analytics['average_deal_value'] = cursor.fetchone()['avg']

    # Deals by UTM source (won deals, filtered)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(utm_source, 'Direct/Unknown') as source,
                   COUNT(*) as count,
                   COALESCE(SUM(value), 0) as revenue
            FROM deals
            WHERE stage = 'closed_won' {date_filter}
            GROUP BY utm_source
            ORDER BY revenue DESC
        """, date_params)
    else:
        cursor.execute("""
            SELECT COALESCE(utm_source, 'Direct/Unknown') as source,
                   COUNT(*) as count,
                   COALESCE(SUM(value), 0) as revenue
            FROM deals
            WHERE stage = 'closed_won'
            GROUP BY utm_source
            ORDER BY revenue DESC
        """)
    analytics['by_source'] = [dict(row) for row in cursor.fetchall()]

    # Deals by UTM medium (won deals, filtered)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(utm_medium, 'Unknown') as medium,
                   COUNT(*) as count,
                   COALESCE(SUM(value), 0) as revenue
            FROM deals
            WHERE stage = 'closed_won' {date_filter}
            GROUP BY utm_medium
            ORDER BY revenue DESC
        """, date_params)
    else:
        cursor.execute("""
            SELECT COALESCE(utm_medium, 'Unknown') as medium,
                   COUNT(*) as count,
                   COALESCE(SUM(value), 0) as revenue
            FROM deals
            WHERE stage = 'closed_won'
            GROUP BY utm_medium
            ORDER BY revenue DESC
        """)
    analytics['by_medium'] = [dict(row) for row in cursor.fetchall()]

    # Recent won deals (filtered by close date if specified)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT id, name, value, salesperson, utm_source, actual_close_date
            FROM deals
            WHERE stage = 'closed_won' {date_filter}
            ORDER BY actual_close_date DESC
            LIMIT 10
        """, date_params)
    else:
        cursor.execute("""
            SELECT id, name, value, salesperson, utm_source, actual_close_date
            FROM deals
            WHERE stage = 'closed_won'
            ORDER BY actual_close_date DESC
            LIMIT 10
        """)
    analytics['recent_closed_deals'] = [dict(row) for row in cursor.fetchall()]

    # Deals in pipeline (not closed)
    cursor.execute("""
        SELECT id, name, value, stage, salesperson, expected_close_date, utm_source
        FROM deals
        WHERE stage NOT IN ('closed_won', 'closed_lost')
        ORDER BY expected_close_date ASC NULLS LAST, created_at DESC
        LIMIT 10
    """)
    analytics['pipeline_deals'] = [dict(row) for row in cursor.fetchall()]

    # Pipeline value
    cursor.execute("""
        SELECT COALESCE(SUM(value), 0) as total FROM deals
        WHERE stage NOT IN ('closed_won', 'closed_lost')
    """)
    analytics['pipeline_value'] = cursor.fetchone()['total']

    # Revenue by salesperson (won deals, filtered)
    if analytics['is_filtered']:
        cursor.execute(f"""
            SELECT COALESCE(salesperson, 'Unassigned') as salesperson,
                   COUNT(*) as count,
                   COALESCE(SUM(value), 0) as revenue
            FROM deals
            WHERE stage = 'closed_won' {date_filter}
            GROUP BY salesperson
            ORDER BY revenue DESC
        """, date_params)
    else:
        cursor.execute("""
            SELECT COALESCE(salesperson, 'Unassigned') as salesperson,
                   COUNT(*) as count,
                   COALESCE(SUM(value), 0) as revenue
            FROM deals
            WHERE stage = 'closed_won'
            GROUP BY salesperson
            ORDER BY revenue DESC
        """)
    analytics['by_salesperson'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return analytics


def get_deals_year_comparison():
    """Get year-over-year comparison data for deals."""
    conn = get_connection()
    cursor = conn.cursor()

    comparison = {}

    # Get revenue and deal count by year (closed won deals)
    cursor.execute("""
        SELECT
            substr(actual_close_date, 1, 4) as year,
            COUNT(*) as deal_count,
            COALESCE(SUM(value), 0) as total_revenue,
            COALESCE(AVG(value), 0) as avg_deal
        FROM deals
        WHERE stage = 'closed_won' AND actual_close_date IS NOT NULL
        GROUP BY substr(actual_close_date, 1, 4)
        ORDER BY year DESC
    """)
    comparison['by_year'] = [dict(row) for row in cursor.fetchall()]

    # Get revenue by source for each year
    cursor.execute("""
        SELECT
            substr(actual_close_date, 1, 4) as year,
            COALESCE(utm_source, 'Direct/Unknown') as source,
            COUNT(*) as deal_count,
            COALESCE(SUM(value), 0) as revenue
        FROM deals
        WHERE stage = 'closed_won' AND actual_close_date IS NOT NULL
        GROUP BY substr(actual_close_date, 1, 4), utm_source
        ORDER BY year DESC, revenue DESC
    """)
    comparison['by_year_source'] = [dict(row) for row in cursor.fetchall()]

    # Get monthly breakdown for closed won deals
    cursor.execute("""
        SELECT
            substr(actual_close_date, 1, 7) as month,
            COUNT(*) as deal_count,
            COALESCE(SUM(value), 0) as revenue
        FROM deals
        WHERE stage = 'closed_won' AND actual_close_date IS NOT NULL
        GROUP BY substr(actual_close_date, 1, 7)
        ORDER BY month DESC
        LIMIT 24
    """)
    comparison['by_month'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return comparison


def get_deals_by_month_medium(year=None):
    """Get deals broken down by month and medium for bar chart."""
    conn = get_connection()
    cursor = conn.cursor()

    # If no year specified, use current year
    if not year:
        year = str(datetime.now().year)

    # All 12 months for the year
    all_months = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Get all won deals grouped by month and medium for the specified year
    cursor.execute("""
        SELECT
            substr(actual_close_date, 1, 7) as month,
            COALESCE(utm_medium, 'Unknown') as medium,
            COUNT(*) as deal_count,
            COALESCE(SUM(value), 0) as revenue
        FROM deals
        WHERE substr(actual_close_date, 1, 4) = ? AND stage = 'closed_won'
        GROUP BY substr(actual_close_date, 1, 7), utm_medium
        ORDER BY month, deal_count DESC
    """, (year,))
    raw_data = [dict(row) for row in cursor.fetchall()]

    # Get all unique mediums from won deals
    cursor.execute("""
        SELECT DISTINCT COALESCE(utm_medium, 'Unknown') as medium
        FROM deals WHERE stage = 'closed_won'
    """)
    mediums = [row['medium'] for row in cursor.fetchall()]
    if not mediums:
        mediums = ['Unknown']

    # Get available years (2024 through 2030)
    available_years = [str(y) for y in range(2030, 2023, -1)]

    # Build structured data for chart (deal counts and revenue)
    chart_data = {}
    revenue_data = {}
    for medium in mediums:
        chart_data[medium] = []
        revenue_data[medium] = []
        for month in all_months:
            count = 0
            revenue = 0
            for row in raw_data:
                if row['month'] == month and row['medium'] == medium:
                    count = row['deal_count']
                    revenue = row['revenue']
                    break
            chart_data[medium].append(count)
            revenue_data[medium].append(revenue)

    # Calculate totals per month (deals and revenue)
    monthly_totals = []
    monthly_revenue_totals = []
    for i, month in enumerate(all_months):
        total = sum(chart_data[medium][i] for medium in mediums)
        revenue_total = sum(revenue_data[medium][i] for medium in mediums)
        monthly_totals.append(total)
        monthly_revenue_totals.append(revenue_total)

    conn.close()
    return {
        'year': year,
        'months': all_months,
        'month_names': month_names,
        'mediums': mediums,
        'data': chart_data,
        'revenue_data': revenue_data,
        'totals': monthly_totals,
        'revenue_totals': monthly_revenue_totals,
        'available_years': available_years,
        'raw': raw_data
    }


# ============== Product Functions ==============

def add_product(name, sku=None, description=None, price=0):
    """Add a new product to the database."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO products (name, sku, description, price)
            VALUES (?, ?, ?, ?)
        """, (name, sku, description, price))
        conn.commit()
        product_id = cursor.lastrowid
        return {"success": True, "id": product_id}
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation) as e:
        if "sku" in str(e).lower():
            return {"success": False, "error": f"SKU already exists: {sku}"}
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def update_product(product_id, **kwargs):
    """Update a product's information."""
    conn = get_connection()
    cursor = conn.cursor()

    allowed_fields = ['name', 'sku', 'description', 'price', 'is_active']

    updates = []
    values = []
    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return {"success": False, "error": "No valid fields to update"}

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(product_id)

    query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
    try:
        cursor.execute(query, values)
        conn.commit()
        return {"success": True, "updated": cursor.rowcount}
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation) as e:
        if "sku" in str(e).lower():
            return {"success": False, "error": "SKU already exists"}
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_product(product_id):
    """Get a single product by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_product_by_sku(sku):
    """Get a product by SKU."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_products(include_inactive=False):
    """Get all products, optionally including inactive ones."""
    conn = get_connection()
    cursor = conn.cursor()
    if include_inactive:
        cursor.execute("SELECT * FROM products ORDER BY name")
    else:
        cursor.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def search_products(query):
    """Search products by name, SKU, or description."""
    conn = get_connection()
    cursor = conn.cursor()
    search_term = f"%{query}%"

    # Use ILIKE for PostgreSQL (case-insensitive), LIKE for SQLite
    if USE_POSTGRES:
        cursor.execute("""
            SELECT * FROM products
            WHERE (name ILIKE %s OR sku ILIKE %s OR description ILIKE %s) AND is_active = 1
            ORDER BY name
        """, (search_term, search_term, search_term))
    else:
        cursor.execute("""
            SELECT * FROM products
            WHERE (name LIKE ? OR sku LIKE ? OR description LIKE ?) AND is_active = 1
            ORDER BY name
        """, (search_term, search_term, search_term))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_product(product_id):
    """Delete a product by ID (hard delete)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0, "deleted": deleted}


def deactivate_product(product_id):
    """Soft delete - mark product as inactive."""
    return update_product(product_id, is_active=0)


def activate_product(product_id):
    """Reactivate an inactive product."""
    return update_product(product_id, is_active=1)


# ============== Company Functions ==============

def add_company(name, phone=None, email=None, website=None, address=None,
                city=None, state=None, zip_code=None, notes=None):
    """Add a new company to the database."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO companies (name, phone, email, website, address, city, state, zip, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name.strip(), phone, email, website, address, city, state, zip_code, notes))
        conn.commit()
        company_id = cursor.lastrowid
        return {"success": True, "id": company_id, "name": name.strip()}
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation):
        return {"success": False, "error": "Company already exists"}
    finally:
        conn.close()


def update_company(company_id, **kwargs):
    """Update a company's information."""
    conn = get_connection()
    cursor = conn.cursor()

    allowed_fields = ['name', 'phone', 'email', 'website', 'address', 'city', 'state', 'zip', 'notes']

    updates = []
    values = []
    for field, value in kwargs.items():
        if field == 'zip_code':
            field = 'zip'
        if field in allowed_fields:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return {"success": False, "error": "No valid fields to update"}

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(company_id)

    query = f"UPDATE companies SET {', '.join(updates)} WHERE id = ?"
    try:
        cursor.execute(query, values)
        conn.commit()
        return {"success": True, "updated": cursor.rowcount}
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation):
        return {"success": False, "error": "Company name already exists"}
    finally:
        conn.close()


def get_company(company_id):
    """Get a single company by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_company_by_name(name):
    """Get a company by name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM companies WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_companies():
    """Get all companies."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM companies ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def search_companies(query):
    """Search companies by name."""
    conn = get_connection()
    cursor = conn.cursor()
    search_term = f"%{query}%"

    # Use ILIKE for PostgreSQL (case-insensitive), LIKE for SQLite
    if USE_POSTGRES:
        cursor.execute("""
            SELECT * FROM companies
            WHERE name ILIKE %s
            ORDER BY name
        """, (search_term,))
    else:
        cursor.execute("""
            SELECT * FROM companies
            WHERE name LIKE ?
            ORDER BY name
        """, (search_term,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_company(company_id):
    """Delete a company. Unlinks related contacts, deals, and quotes first."""
    conn = get_connection()
    cursor = conn.cursor()
    # Unlink related records to avoid foreign key violations
    cursor.execute("UPDATE contacts SET company_id = NULL WHERE company_id = ?", (company_id,))
    cursor.execute("UPDATE deals SET company_id = NULL WHERE company_id = ?", (company_id,))
    cursor.execute("UPDATE quotes SET company_id = NULL WHERE company_id = ?", (company_id,))
    cursor.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0, "deleted": deleted}


def get_company_deals(company_id):
    """Get all deals for a company."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM deals WHERE company_id = ?
        ORDER BY created_at DESC
    """, (company_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_company_contacts(company_id):
    """Get all contacts for a company."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM contacts WHERE company_id = ?
        ORDER BY first_name, last_name
    """, (company_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_company_quotes(company_id):
    """Get all quotes for a company."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM quotes WHERE company_id = ?
        ORDER BY created_at DESC
    """, (company_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============== Quote Functions ==============

QUOTE_STATUSES = ['draft', 'sent', 'accepted', 'invoiced', 'paid', 'declined', 'expired']


def generate_quote_number():
    """Generate a unique quote number like Q-2026-0001."""
    conn = get_connection()
    cursor = conn.cursor()
    year = datetime.now().year
    pattern = f"Q-{year}-%"

    # Get the highest quote number for this year
    if USE_POSTGRES:
        cursor.execute("""
            SELECT quote_number FROM quotes
            WHERE quote_number LIKE %s
            ORDER BY quote_number DESC LIMIT 1
        """, (pattern,))
    else:
        cursor.execute("""
            SELECT quote_number FROM quotes
            WHERE quote_number LIKE ?
            ORDER BY quote_number DESC LIMIT 1
        """, (pattern,))

    row = cursor.fetchone()
    conn.close()

    if row:
        # Extract the sequence number and increment
        try:
            seq = int(row['quote_number'].split('-')[-1]) + 1
        except:
            seq = 1
    else:
        seq = 1

    return f"Q-{year}-{seq:04d}"


def add_quote(title, salesperson_id=None, deal_id=None, contact_id=None, company_id=None,
              customer_name=None, customer_email=None, customer_phone=None, customer_company=None,
              quote_date=None, expiry_date=None, notes=None, terms=None,
              discount_percent=0, tax_percent=0, auto_create_deal=True,
              utm_source=None, utm_medium=None, utm_campaign=None, reported_source=None):
    """Create a new quote. If auto_create_deal is True and no deal_id provided, creates a deal automatically."""
    conn = get_connection()
    cursor = conn.cursor()

    quote_number = generate_quote_number()

    # Auto-fill salesperson info if salesperson_id provided
    salesperson_name = None
    salesperson_email = None
    salesperson_phone = None
    if salesperson_id:
        sp = get_salesperson(salesperson_id)
        if sp:
            salesperson_name = sp.get('name')
            salesperson_email = sp.get('email')
            salesperson_phone = sp.get('phone')

    # Auto-fill company name from company_id if provided
    if company_id and not customer_company:
        company = get_company(company_id)
        if company:
            customer_company = company.get('name')

    # Auto-fill customer info from contact if contact_id provided
    if contact_id and not customer_name:
        contact = get_contact(contact_id)
        if contact:
            customer_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            customer_email = customer_email or contact.get('email')
            customer_phone = customer_phone or contact.get('phone')

    # Default quote_date to today
    if not quote_date:
        quote_date = datetime.now().strftime('%Y-%m-%d')

    # Auto-create a deal if none provided
    if auto_create_deal and not deal_id:
        # Use company name as deal name if provided, otherwise use title
        deal_name = customer_company if customer_company else title
        deal_result = add_deal(
            name=deal_name,
            value=0,  # Will be updated when quote total is calculated
            stage='new_deal',
            salesperson=salesperson_name,
            contact_id=contact_id,
            company_id=company_id,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            reported_source=reported_source
        )
        if deal_result.get('success'):
            deal_id = deal_result['id']

    try:
        cursor.execute("""
            INSERT INTO quotes (
                quote_number, title, status,
                deal_id, contact_id, company_id, customer_name, customer_email, customer_phone, customer_company,
                salesperson_id, salesperson_name, salesperson_email, salesperson_phone,
                discount_percent, tax_percent,
                quote_date, expiry_date, notes, terms
            ) VALUES (?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (quote_number, title,
              deal_id, contact_id, company_id, customer_name, customer_email, customer_phone, customer_company,
              salesperson_id, salesperson_name, salesperson_email, salesperson_phone,
              discount_percent, tax_percent,
              quote_date, expiry_date, notes, terms))
        conn.commit()
        quote_id = cursor.lastrowid
        conn.close()
        # Update contact's last activity if contact_id provided
        if contact_id:
            update_contact_activity(contact_id)
        return {"success": True, "id": quote_id, "quote_number": quote_number, "deal_id": deal_id}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def update_quote(quote_id, **kwargs):
    """Update a quote's information."""
    conn = get_connection()
    cursor = conn.cursor()

    allowed_fields = [
        'title', 'status',
        'deal_id', 'contact_id', 'customer_name', 'customer_email', 'customer_phone', 'customer_company',
        'salesperson_id', 'salesperson_name', 'salesperson_email', 'salesperson_phone',
        'subtotal', 'discount_percent', 'discount_amount', 'tax_percent', 'tax_amount', 'total',
        'quote_date', 'expiry_date', 'notes', 'terms',
        'payment_link', 'payment_date', 'financing_link'
    ]

    updates = []
    values = []
    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return {"success": False, "error": "No valid fields to update"}

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(quote_id)

    query = f"UPDATE quotes SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()

    return {"success": True, "updated": cursor.rowcount}


def recalculate_quote_totals(quote_id):
    """Recalculate subtotal, discount, tax, and total for a quote. Also updates linked deal value."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get quote settings and deal_id
    cursor.execute("SELECT discount_percent, tax_percent, deal_id FROM quotes WHERE id = ?", (quote_id,))
    quote = cursor.fetchone()
    if not quote:
        conn.close()
        return {"success": False, "error": "Quote not found"}

    discount_percent = quote['discount_percent'] or 0
    tax_percent = quote['tax_percent'] or 0
    deal_id = quote['deal_id']

    # Calculate subtotal from line items
    cursor.execute("SELECT COALESCE(SUM(line_total), 0) as subtotal FROM quote_items WHERE quote_id = ?", (quote_id,))
    subtotal = cursor.fetchone()['subtotal']

    # Calculate discount and tax
    discount_amount = subtotal * (discount_percent / 100)
    taxable_amount = subtotal - discount_amount
    tax_amount = taxable_amount * (tax_percent / 100)
    total = taxable_amount + tax_amount

    # Update quote
    cursor.execute("""
        UPDATE quotes SET
            subtotal = ?, discount_amount = ?, tax_amount = ?, total = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (subtotal, discount_amount, tax_amount, total, quote_id))

    # Also update the linked deal value if there is one
    if deal_id:
        cursor.execute("""
            UPDATE deals SET value = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (total, deal_id))

    conn.commit()
    conn.close()

    return {"success": True, "subtotal": subtotal, "discount_amount": discount_amount,
            "tax_amount": tax_amount, "total": total}


def get_quote(quote_id):
    """Get a single quote by ID with its line items."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    quote = dict(row)

    # Get line items
    cursor.execute("""
        SELECT * FROM quote_items
        WHERE quote_id = ?
        ORDER BY sort_order, id
    """, (quote_id,))
    quote['line_items'] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return quote


def get_all_quotes(status=None, salesperson_id=None, limit=100, offset=0):
    """Get all quotes with optional status and salesperson filters."""
    conn = get_connection()
    cursor = conn.cursor()

    # Build dynamic query based on filters
    query = "SELECT * FROM quotes WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if salesperson_id:
        query += " AND salesperson_id = ?"
        params.append(salesperson_id)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_quote(quote_id):
    """Delete a quote and its line items."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quotes WHERE id = ?", (quote_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0, "deleted": deleted}


def add_quote_item(quote_id, product_id=None, product_name=None, product_sku=None,
                   description=None, quantity=1, unit_price=0, discount_percent=0, sort_order=0):
    """Add a line item to a quote."""
    conn = get_connection()
    cursor = conn.cursor()

    # If product_id provided, fetch product details
    if product_id and not product_name:
        product = get_product(product_id)
        if product:
            product_name = product['name']
            product_sku = product_sku or product.get('sku')
            description = description or product.get('description')
            unit_price = unit_price or product.get('price', 0)

    if not product_name:
        conn.close()
        return {"success": False, "error": "Product name is required"}

    # Calculate line total
    line_total = quantity * unit_price * (1 - discount_percent / 100)

    try:
        cursor.execute("""
            INSERT INTO quote_items (
                quote_id, product_id, product_name, product_sku, description,
                quantity, unit_price, discount_percent, line_total, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (quote_id, product_id, product_name, product_sku, description,
              quantity, unit_price, discount_percent, line_total, sort_order))
        conn.commit()
        item_id = cursor.lastrowid
        conn.close()

        # Recalculate quote totals
        recalculate_quote_totals(quote_id)

        return {"success": True, "id": item_id}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def update_quote_item(item_id, **kwargs):
    """Update a quote line item."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get the quote_id first for recalculation
    cursor.execute("SELECT quote_id FROM quote_items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Item not found"}
    quote_id = row['quote_id']

    allowed_fields = [
        'product_id', 'product_name', 'product_sku', 'description',
        'quantity', 'unit_price', 'discount_percent', 'sort_order'
    ]

    updates = []
    values = []
    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        conn.close()
        return {"success": False, "error": "No valid fields to update"}

    values.append(item_id)
    query = f"UPDATE quote_items SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)

    # Recalculate line total
    cursor.execute("SELECT quantity, unit_price, discount_percent FROM quote_items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if item:
        line_total = item['quantity'] * item['unit_price'] * (1 - (item['discount_percent'] or 0) / 100)
        cursor.execute("UPDATE quote_items SET line_total = ? WHERE id = ?", (line_total, item_id))

    conn.commit()
    conn.close()

    # Recalculate quote totals
    recalculate_quote_totals(quote_id)

    return {"success": True}


def delete_quote_item(item_id):
    """Delete a line item from a quote."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get the quote_id first for recalculation
    cursor.execute("SELECT quote_id FROM quote_items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Item not found"}
    quote_id = row['quote_id']

    cursor.execute("DELETE FROM quote_items WHERE id = ?", (item_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    # Recalculate quote totals
    if deleted > 0:
        recalculate_quote_totals(quote_id)

    return {"success": deleted > 0}


def get_quotes_for_deal(deal_id):
    """Get all quotes associated with a deal."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM quotes WHERE deal_id = ?
        ORDER BY created_at DESC
    """, (deal_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============== User Authentication Functions ==============

import hashlib
import secrets


def hash_password(password):
    """Hash a password using SHA-256 with a salt."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password, stored_hash):
    """Verify a password against a stored hash."""
    try:
        salt, password_hash = stored_hash.split(':')
        return hashlib.sha256((salt + password).encode()).hexdigest() == password_hash
    except:
        return False


def add_user(username, password, email=None, first_name=None, last_name=None, role='salesperson'):
    """Create a new user account."""
    conn = get_connection()
    cursor = conn.cursor()

    password_hash = hash_password(password)

    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, first_name, last_name, role)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username.lower(), password_hash, email, first_name, last_name, role))
        conn.commit()
        user_id = cursor.lastrowid
        return {"success": True, "id": user_id}
    except (sqlite3.IntegrityError, psycopg2.errors.UniqueViolation):
        return {"success": False, "error": "Username already exists"}
    finally:
        conn.close()


def get_user(user_id):
    """Get a user by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username):
    """Get a user by username."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username.lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def authenticate_user(username, password):
    """Authenticate a user with username and password."""
    user = get_user_by_username(username)
    if not user:
        return {"success": False, "error": "Invalid username or password"}

    if not user.get('is_active'):
        return {"success": False, "error": "Account is deactivated"}

    if not verify_password(password, user['password_hash']):
        return {"success": False, "error": "Invalid username or password"}

    # Update last login
    update_last_login(user['id'])

    return {"success": True, "user": user}


def update_last_login(user_id):
    """Update the last_login timestamp for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET last_login = ? WHERE id = ?
    """, (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()


def update_user(user_id, **kwargs):
    """Update a user's information."""
    conn = get_connection()
    cursor = conn.cursor()

    allowed_fields = ['email', 'first_name', 'last_name', 'role', 'is_active', 'salesperson_id']
    updates = []
    values = []

    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f"{field} = ?")
            values.append(value)

    # Handle password change separately
    if 'password' in kwargs and kwargs['password']:
        updates.append("password_hash = ?")
        values.append(hash_password(kwargs['password']))

    if not updates:
        conn.close()
        return {"success": False, "error": "No valid fields to update"}

    updates.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(user_id)

    cursor.execute(f"""
        UPDATE users SET {', '.join(updates)} WHERE id = ?
    """, values)
    conn.commit()
    conn.close()
    return {"success": True}


def delete_user(user_id):
    """Delete a user account."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0}


def get_all_users():
    """Get all users."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, first_name, last_name, role, is_active, last_login, created_at, salesperson_id
        FROM users
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_user_count():
    """Get total number of users."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users")
    row = cursor.fetchone()
    conn.close()
    return row['count'] if row else 0


# ============== User Email Token Functions ==============

def save_user_email_token(user_id, provider, token_data):
    """Save or update email token for a user."""
    import json
    conn = get_connection()
    cursor = conn.cursor()

    # Convert dict to JSON string for storage
    token_json = json.dumps(token_data) if isinstance(token_data, dict) else token_data

    # Use INSERT OR REPLACE to handle both insert and update
    cursor.execute("""
        INSERT OR REPLACE INTO user_email_tokens (user_id, provider, token_data, updated_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, provider, token_json, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return {"success": True}


def get_user_email_token(user_id, provider):
    """Get email token for a user and provider."""
    import json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT token_data FROM user_email_tokens
        WHERE user_id = ? AND provider = ?
    """, (user_id, provider))
    row = cursor.fetchone()
    conn.close()
    if row and row['token_data']:
        return json.loads(row['token_data'])
    return None


def delete_user_email_token(user_id, provider):
    """Delete email token for a user and provider."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM user_email_tokens
        WHERE user_id = ? AND provider = ?
    """, (user_id, provider))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return {"success": deleted > 0}


def get_users_with_email_connected():
    """Get all user IDs that have email tokens stored."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT t.user_id, u.first_name, u.last_name, u.username
        FROM user_email_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE u.is_active = 1
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_user_email_status(user_id):
    """Get email connection status for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT provider FROM user_email_tokens
        WHERE user_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    providers = [row['provider'] for row in rows]
    return {
        'gmail': 'gmail' in providers,
        'outlook': 'outlook' in providers
    }


# ============== Quick Notes Functions ==============

def get_quick_notes(user_id=1):
    """Get quick notes for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM quick_notes WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['content'] if row else ''


def save_quick_notes(content, user_id=1):
    """Save quick notes for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM quick_notes WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()

    if exists:
        cursor.execute("""
            UPDATE quick_notes SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (content, user_id))
    else:
        cursor.execute("""
            INSERT INTO quick_notes (user_id, content) VALUES (?, ?)
        """, (user_id, content))

    conn.commit()
    conn.close()
    return {"success": True}


# ============== Fix Requests ==============

def add_fix_request(name, message, attachment_filename=None, attachment_data=None, attachment_content_type=None):
    """Add a new fix request/bug report."""
    conn = get_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute("""
            INSERT INTO fix_requests (name, message, attachment_filename, attachment_data, attachment_content_type, status, created_at)
            VALUES (%s, %s, %s, %s, %s, 'pending', CURRENT_TIMESTAMP)
            RETURNING id
        """, (name, message, attachment_filename, attachment_data, attachment_content_type))
        result = cursor.fetchone()
        fix_id = result['id'] if result else None
    else:
        cursor.execute("""
            INSERT INTO fix_requests (name, message, attachment_filename, attachment_data, attachment_content_type, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
        """, (name, message, attachment_filename, attachment_data, attachment_content_type))
        fix_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return {"success": True, "id": fix_id}


def get_fix_request(fix_id):
    """Get a single fix request by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    if USE_POSTGRES:
        cursor.execute("SELECT * FROM fix_requests WHERE id = %s", (fix_id,))
    else:
        cursor.execute("SELECT * FROM fix_requests WHERE id = ?", (fix_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_fix_requests():
    """Get all fix requests."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM fix_requests
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_fix_request_status(fix_id, status):
    """Update the status of a fix request."""
    conn = get_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute("""
            UPDATE fix_requests SET status = %s WHERE id = %s
        """, (status, fix_id))
    else:
        cursor.execute("""
            UPDATE fix_requests SET status = ? WHERE id = ?
        """, (status, fix_id))

    conn.commit()
    conn.close()
    return {"success": True}


def init_fix_requests_table():
    """Create the fix_requests table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fix_requests (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                attachment_filename TEXT,
                attachment_data BYTEA,
                attachment_content_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add columns if table already exists
        try:
            cursor.execute("ALTER TABLE fix_requests ADD COLUMN IF NOT EXISTS attachment_data BYTEA")
            cursor.execute("ALTER TABLE fix_requests ADD COLUMN IF NOT EXISTS attachment_content_type TEXT")
        except:
            pass
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fix_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                attachment_filename TEXT,
                attachment_data BLOB,
                attachment_content_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add columns if table already exists
        try:
            cursor.execute("ALTER TABLE fix_requests ADD COLUMN attachment_data BLOB")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE fix_requests ADD COLUMN attachment_content_type TEXT")
        except:
            pass

    conn.commit()
    conn.close()


def add_sales_notes_column():
    """Add sales_notes column to contacts table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if USE_POSTGRES:
            # Check if column exists
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'sales_notes'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE contacts ADD COLUMN sales_notes TEXT")
                conn.commit()
                print("Added sales_notes column to contacts table")
        else:
            # SQLite - try to add, ignore if exists
            try:
                cursor.execute("ALTER TABLE contacts ADD COLUMN sales_notes TEXT")
                conn.commit()
                print("Added sales_notes column to contacts table")
            except:
                pass  # Column already exists
    except Exception as e:
        print(f"Note: sales_notes column may already exist: {e}")
    finally:
        conn.close()


def add_user_salesperson_column():
    """Add salesperson_id column to users table to link users to salespeople."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if USE_POSTGRES:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'salesperson_id'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN salesperson_id INTEGER REFERENCES salespeople(id) ON DELETE SET NULL")
                conn.commit()
                print("Added salesperson_id column to users table")
        else:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN salesperson_id INTEGER REFERENCES salespeople(id)")
                conn.commit()
                print("Added salesperson_id column to users table")
            except:
                pass  # Column already exists
    except Exception as e:
        print(f"Note: users.salesperson_id column may already exist: {e}")
    finally:
        conn.close()


def get_salesperson_for_user(user_id):
    """Get the salesperson record linked to a user, or None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.* FROM salespeople s
        JOIN users u ON u.salesperson_id = s.id
        WHERE u.id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_contact_salesperson_column():
    """Add salesperson_id column to contacts table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if USE_POSTGRES:
            # Check if column exists
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'salesperson_id'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE contacts ADD COLUMN salesperson_id INTEGER REFERENCES salespeople(id) ON DELETE SET NULL")
                conn.commit()
                print("Added salesperson_id column to contacts table")
        else:
            # SQLite - try to add, ignore if exists
            try:
                cursor.execute("ALTER TABLE contacts ADD COLUMN salesperson_id INTEGER REFERENCES salespeople(id)")
                conn.commit()
                print("Added salesperson_id column to contacts table")
            except:
                pass  # Column already exists
    except Exception as e:
        print(f"Note: salesperson_id column may already exist: {e}")
    finally:
        conn.close()


# ============== App Settings (key-value store for OAuth, config, etc.) ==============

def init_app_settings_table():
    """Create app_settings table if it doesn't exist (works for both SQLite and PostgreSQL)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
    except Exception as e:
        print(f"Note: app_settings table may already exist: {e}")
    finally:
        conn.close()


def save_app_setting(key, value):
    """Save an app setting (stores dict/list as JSON)."""
    import json
    conn = get_connection()
    cursor = conn.cursor()
    value_json = json.dumps(value) if isinstance(value, (dict, list)) else value
    cursor.execute("""
        INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at)
        VALUES (?, ?, ?)
    """, (key, value_json, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_app_setting(key):
    """Get an app setting by key (returns parsed JSON or None)."""
    import json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row and row['setting_value']:
        try:
            return json.loads(row['setting_value'])
        except (json.JSONDecodeError, TypeError):
            return row['setting_value']
    return None


def delete_app_setting(key):
    """Delete an app setting by key."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM app_settings WHERE setting_key = ?", (key,))
    conn.commit()
    conn.close()


# ============== Marketing Shortcuts ==============

def get_marketing_shortcuts():
    """Get all marketing shortcuts."""
    shortcuts = get_app_setting('marketing_shortcuts')
    if not shortcuts:
        return []
    return shortcuts


def save_marketing_shortcuts(shortcuts):
    """Save all marketing shortcuts."""
    save_app_setting('marketing_shortcuts', shortcuts)


def get_marketing_categories():
    """Get all marketing categories."""
    categories = get_app_setting('marketing_categories')
    if not categories:
        return []
    return categories


def save_marketing_categories(categories):
    """Save all marketing categories."""
    save_app_setting('marketing_categories', categories)


def add_marketing_category(name):
    """Add a new marketing category."""
    import uuid
    categories = get_marketing_categories()
    # Check if category already exists
    for cat in categories:
        if cat['name'].lower() == name.lower():
            return cat
    category = {
        'id': str(uuid.uuid4())[:8],
        'name': name,
        'order': len(categories)
    }
    categories.append(category)
    save_marketing_categories(categories)
    return category


def update_marketing_category(category_id, name=None, order=None):
    """Update a marketing category."""
    categories = get_marketing_categories()
    for category in categories:
        if category['id'] == category_id:
            if name is not None:
                category['name'] = name
            if order is not None:
                category['order'] = order
            save_marketing_categories(categories)
            return category
    return None


def delete_marketing_category(category_id):
    """Delete a marketing category and move its shortcuts to Uncategorized."""
    categories = get_marketing_categories()
    categories = [c for c in categories if c['id'] != category_id]
    save_marketing_categories(categories)
    # Move shortcuts in this category to no category
    shortcuts = get_marketing_shortcuts()
    for shortcut in shortcuts:
        if shortcut.get('category') == category_id:
            shortcut['category'] = ''
    save_marketing_shortcuts(shortcuts)
    return True


def add_marketing_shortcut(name, url='', icon='link', color='slate', category=''):
    """Add a new marketing shortcut."""
    import uuid
    shortcuts = get_marketing_shortcuts()
    # Get max order for this category
    max_order = max([s.get('order', 0) for s in shortcuts if s.get('category') == category] or [0])
    shortcut = {
        'id': str(uuid.uuid4())[:8],
        'name': name,
        'url': url,
        'icon': icon,
        'color': color,
        'category': category,
        'order': max_order + 1,
        'created_at': datetime.now().isoformat()
    }
    shortcuts.append(shortcut)
    save_marketing_shortcuts(shortcuts)
    return shortcut


def update_marketing_shortcut(shortcut_id, name=None, url=None, icon=None, color=None, category=None):
    """Update a marketing shortcut."""
    shortcuts = get_marketing_shortcuts()
    for shortcut in shortcuts:
        if shortcut['id'] == shortcut_id:
            if name is not None:
                shortcut['name'] = name
            if url is not None:
                shortcut['url'] = url
            if icon is not None:
                shortcut['icon'] = icon
            if color is not None:
                shortcut['color'] = color
            if category is not None:
                shortcut['category'] = category
            save_marketing_shortcuts(shortcuts)
            return shortcut
    return None


def delete_marketing_shortcut(shortcut_id):
    """Delete a marketing shortcut."""
    shortcuts = get_marketing_shortcuts()
    shortcuts = [s for s in shortcuts if s['id'] != shortcut_id]
    save_marketing_shortcuts(shortcuts)
    return True


def reorder_shortcuts(shortcut_ids):
    """Reorder shortcuts based on list of IDs. Also handles moving between categories."""
    shortcuts = get_marketing_shortcuts()
    shortcut_map = {s['id']: s for s in shortcuts}

    # Update order based on position in the list
    for order, shortcut_id in enumerate(shortcut_ids):
        if shortcut_id in shortcut_map:
            shortcut_map[shortcut_id]['order'] = order

    save_marketing_shortcuts(list(shortcut_map.values()))
    return True


def move_shortcut_to_category(shortcut_id, new_category_id, new_order=None):
    """Move a shortcut to a different category with optional order."""
    shortcuts = get_marketing_shortcuts()
    for shortcut in shortcuts:
        if shortcut['id'] == shortcut_id:
            shortcut['category'] = new_category_id
            if new_order is not None:
                shortcut['order'] = new_order
            else:
                # Put at end of new category
                max_order = max([s.get('order', 0) for s in shortcuts if s.get('category') == new_category_id] or [0])
                shortcut['order'] = max_order + 1
            save_marketing_shortcuts(shortcuts)
            return shortcut
    return None


def get_shortcuts_by_category():
    """Get shortcuts organized by category."""
    shortcuts = get_marketing_shortcuts()
    categories = get_marketing_categories()

    # Create a dict of category_id -> category_name
    cat_map = {c['id']: c['name'] for c in categories}
    cat_order = {c['id']: c.get('order', 0) for c in categories}

    # Group shortcuts by category
    grouped = {}
    for shortcut in shortcuts:
        cat_id = shortcut.get('category', '')
        cat_name = cat_map.get(cat_id, 'Uncategorized') if cat_id else 'Uncategorized'
        if cat_name not in grouped:
            grouped[cat_name] = {'id': cat_id, 'shortcuts': [], 'order': cat_order.get(cat_id, 999)}
        grouped[cat_name]['shortcuts'].append(shortcut)

    # Sort shortcuts within each category by order
    for cat_name in grouped:
        grouped[cat_name]['shortcuts'].sort(key=lambda s: (s.get('order', 0), s.get('name', '')))

    # Sort categories by order
    sorted_groups = sorted(grouped.items(), key=lambda x: (x[1]['order'], x[0]))
    return sorted_groups


def init_default_marketing_shortcuts():
    """Initialize default marketing shortcuts if none exist."""
    shortcuts = get_marketing_shortcuts()
    if shortcuts:
        return  # Already have shortcuts

    # Create default categories
    ads_cat = add_marketing_category('Ads Management')
    seo_cat = add_marketing_category('SEO & Analytics')
    social_cat = add_marketing_category('Social Media')
    tools_cat = add_marketing_category('Tools & Resources')

    defaults = [
        {'name': 'Google Ads', 'icon': 'google', 'color': 'blue', 'category': ads_cat['id']},
        {'name': 'Bing Ads', 'icon': 'microsoft', 'color': 'blue', 'category': ads_cat['id']},
        {'name': 'ClickCease', 'icon': 'shield', 'color': 'red', 'category': ads_cat['id']},
        {'name': 'Google Analytics', 'icon': 'chart', 'color': 'yellow', 'category': seo_cat['id']},
        {'name': 'Bing Webmaster', 'icon': 'search', 'color': 'green', 'category': seo_cat['id']},
        {'name': 'Ubersuggest', 'icon': 'chart', 'color': 'orange', 'category': seo_cat['id']},
        {'name': 'CallRail', 'icon': 'link', 'color': 'green', 'category': seo_cat['id']},
        {'name': 'Meta Business Suite', 'icon': 'meta', 'color': 'blue', 'category': social_cat['id']},
        {'name': 'Buffer', 'icon': 'link', 'color': 'blue', 'category': social_cat['id']},
        {'name': 'SharePoint Marketing', 'icon': 'folder', 'color': 'teal', 'category': tools_cat['id']},
        {'name': 'WordPress', 'icon': 'link', 'color': 'blue', 'category': tools_cat['id']},
        {'name': 'Squarespace', 'icon': 'link', 'color': 'slate', 'category': tools_cat['id']},
        {'name': 'Shopify', 'icon': 'link', 'color': 'green', 'category': tools_cat['id']},
        {'name': 'Canva', 'icon': 'link', 'color': 'purple', 'category': tools_cat['id']},
    ]

    for d in defaults:
        add_marketing_shortcut(d['name'], '', d['icon'], d['color'], d['category'])


def add_missing_shortcuts():
    """Add new shortcuts to existing installations."""
    shortcuts = get_marketing_shortcuts()
    existing_names = {s['name'] for s in shortcuts}
    categories = get_marketing_categories()

    # Find or create categories
    cat_map = {c['name']: c['id'] for c in categories}

    if 'Tools & Resources' not in cat_map:
        cat = add_marketing_category('Tools & Resources')
        cat_map['Tools & Resources'] = cat['id']
    if 'Social Media' not in cat_map:
        cat = add_marketing_category('Social Media')
        cat_map['Social Media'] = cat['id']
    if 'SEO & Analytics' not in cat_map:
        cat = add_marketing_category('SEO & Analytics')
        cat_map['SEO & Analytics'] = cat['id']

    new_shortcuts = [
        {'name': 'WordPress', 'icon': 'link', 'color': 'blue', 'category': cat_map.get('Tools & Resources', '')},
        {'name': 'Squarespace', 'icon': 'link', 'color': 'slate', 'category': cat_map.get('Tools & Resources', '')},
        {'name': 'Shopify', 'icon': 'link', 'color': 'green', 'category': cat_map.get('Tools & Resources', '')},
        {'name': 'Canva', 'icon': 'link', 'color': 'purple', 'category': cat_map.get('Tools & Resources', '')},
        {'name': 'Buffer', 'icon': 'link', 'color': 'blue', 'category': cat_map.get('Social Media', '')},
        {'name': 'CallRail', 'icon': 'link', 'color': 'green', 'category': cat_map.get('SEO & Analytics', '')},
        # STEELSTACK Social
        {'name': 'STEELSTACK Instagram', 'icon': 'link', 'color': 'purple', 'category': cat_map.get('Social Media', '')},
        {'name': 'STEELSTACK Facebook', 'icon': 'meta', 'color': 'blue', 'category': cat_map.get('Social Media', '')},
        {'name': 'STEELSTACK YouTube', 'icon': 'link', 'color': 'red', 'category': cat_map.get('Social Media', '')},
        # Morrison Industries Social
        {'name': 'Morrison Industries Instagram', 'icon': 'link', 'color': 'purple', 'category': cat_map.get('Social Media', '')},
        {'name': 'Morrison Industries Facebook', 'icon': 'meta', 'color': 'blue', 'category': cat_map.get('Social Media', '')},
        {'name': 'Morrison Industries YouTube', 'icon': 'link', 'color': 'red', 'category': cat_map.get('Social Media', '')},
    ]

    added = []
    for s in new_shortcuts:
        if s['name'] not in existing_names:
            add_marketing_shortcut(s['name'], '', s['icon'], s['color'], s['category'])
            added.append(s['name'])

    return added


if __name__ == "__main__":
    init_database()
