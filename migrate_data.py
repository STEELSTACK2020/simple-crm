"""Quick migration script using bulk inserts."""
import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

sqlite_conn = sqlite3.connect('crm.db')
sqlite_conn.row_factory = sqlite3.Row
pg_conn = psycopg2.connect(os.getenv('DATABASE_URL'))
pg_cur = pg_conn.cursor()

def migrate(table, cols):
    print(f"Migrating {table}...", end=" ", flush=True)
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute(f'SELECT {cols} FROM {table}')
    rows = [tuple(row) for row in sqlite_cur.fetchall()]
    if not rows:
        print("0 rows")
        return

    col_list = cols.split(', ')
    cols_str = ', '.join(col_list)

    # Use execute_values for bulk insert
    query = f"INSERT INTO {table} ({cols_str}) VALUES %s"
    try:
        execute_values(pg_cur, query, rows, page_size=100)
        pg_conn.commit()
        # Reset sequence
        pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))")
        pg_conn.commit()
        print(f"{len(rows)} rows")
    except Exception as e:
        pg_conn.rollback()
        print(f"ERROR: {e}")

# Migrate all tables
migrate('contacts', 'id, first_name, last_name, email, phone, utm_source, utm_medium, utm_campaign, utm_term, utm_content, deal_value, deal_closed_date, created_at, updated_at, notes, company_id, last_activity_date, original_source_details, landing_page, referrer')
migrate('deals', 'id, name, value, stage, salesperson, utm_source, utm_medium, utm_campaign, expected_close_date, actual_close_date, created_at, updated_at, notes, close_reason, company_id, reported_source')
migrate('deal_contacts', 'id, deal_id, contact_id, role, added_at')
migrate('products', 'id, name, sku, description, price, is_active, created_at, updated_at')
migrate('quotes', 'id, quote_number, title, status, deal_id, contact_id, customer_name, customer_email, customer_phone, customer_company, salesperson_id, salesperson_name, salesperson_email, salesperson_phone, subtotal, discount_percent, discount_amount, tax_percent, tax_amount, total, quote_date, expiry_date, notes, terms, payment_link, payment_date, financing_link, company_id, created_at, updated_at')
migrate('quote_items', 'id, quote_id, product_id, product_name, product_sku, description, quantity, unit_price, discount_percent, line_total, sort_order')
migrate('quick_notes', 'id, user_id, content, updated_at')

sqlite_conn.close()
pg_conn.close()
print("\nMigration complete!")
