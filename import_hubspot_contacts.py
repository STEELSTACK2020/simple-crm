"""
HubSpot Contacts Import Script
Imports contacts from hubspot leads.xlsx into the CRM database.
"""

import pandas as pd
from datetime import datetime
from database import init_database, get_connection

# Initialize database
init_database()

def import_contacts(file_path, dry_run=True):
    """
    Import contacts from HubSpot Excel export.

    Args:
        file_path: Path to the xlsx file
        dry_run: If True, just preview without importing
    """
    # Read Excel file
    df = pd.read_excel(file_path)

    print(f"Found {len(df)} contacts to import")
    print(f"Columns: {list(df.columns)}")
    print("-" * 50)

    # Column mapping: HubSpot -> CRM
    column_map = {
        'First Name': 'first_name',
        'Last Name': 'last_name',
        'Email': 'email',
        'Phone Number': 'phone',
        'Create Date': 'created_at',
        'Last Activity Date': 'last_activity_date',
        'Last Keywords': 'utm_term',
        'First Referring Site': 'utm_source',
        'Original Traffic Source': 'utm_medium',
        'Original Source Details': 'original_source_details'
    }

    imported = 0
    skipped = 0
    errors = []

    conn = get_connection()
    cursor = conn.cursor()

    for idx, row in df.iterrows():
        # Get values with defaults for missing data
        first_name = str(row.get('First Name', '')).strip() if pd.notna(row.get('First Name')) else ''
        last_name = str(row.get('Last Name', '')).strip() if pd.notna(row.get('Last Name')) else ''
        email = str(row.get('Email', '')).strip() if pd.notna(row.get('Email')) else ''

        # Skip if no email (required field)
        if not email:
            skipped += 1
            errors.append(f"Row {idx + 2}: No email - {first_name} {last_name}")
            continue

        # Parse dates
        created_at = None
        if pd.notna(row.get('Create Date')):
            try:
                created_at = pd.to_datetime(row['Create Date']).strftime('%Y-%m-%d %H:%M:%S')
            except:
                created_at = None

        last_activity_date = None
        if pd.notna(row.get('Last Activity Date')):
            try:
                last_activity_date = pd.to_datetime(row['Last Activity Date']).strftime('%Y-%m-%d %H:%M:%S')
            except:
                last_activity_date = None

        # Get other fields
        phone = str(row.get('Phone Number', '')).strip() if pd.notna(row.get('Phone Number')) else None
        utm_term = str(row.get('Last Keywords', '')).strip() if pd.notna(row.get('Last Keywords')) else None
        utm_source = str(row.get('First Referring Site', '')).strip() if pd.notna(row.get('First Referring Site')) else None
        utm_medium = str(row.get('Original Traffic Source', '')).strip() if pd.notna(row.get('Original Traffic Source')) else None
        original_source_details = str(row.get('Original Source Details', '')).strip() if pd.notna(row.get('Original Source Details')) else None

        if dry_run:
            print(f"[PREVIEW] {first_name} {last_name} <{email}> {phone or ''}")
            print(f"          Created: {created_at}, Last Activity: {last_activity_date}")
            print(f"          Source: {utm_source}, Medium: {utm_medium}, Keywords: {utm_term}")
            print()
            imported += 1
        else:
            try:
                # Check if contact already exists by email
                cursor.execute("SELECT id FROM contacts WHERE email = ?", (email,))
                existing = cursor.fetchone()

                if existing:
                    skipped += 1
                    errors.append(f"Row {idx + 2}: Email already exists - {email}")
                    continue

                # Insert contact
                cursor.execute("""
                    INSERT INTO contacts (
                        first_name, last_name, email, phone,
                        utm_source, utm_medium, utm_term,
                        original_source_details,
                        last_activity_date, created_at, updated_at, deal_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
                """, (
                    first_name, last_name, email, phone,
                    utm_source, utm_medium, utm_term,
                    original_source_details,
                    last_activity_date, created_at
                ))
                imported += 1
                print(f"[IMPORTED] {first_name} {last_name} <{email}>")

            except Exception as e:
                skipped += 1
                errors.append(f"Row {idx + 2}: Error - {str(e)}")

    if not dry_run:
        conn.commit()
    conn.close()

    print("-" * 50)
    print(f"SUMMARY:")
    print(f"  Imported: {imported}")
    print(f"  Skipped: {skipped}")

    if errors:
        print(f"\nISSUES ({len(errors)}):")
        for err in errors[:10]:  # Show first 10 errors
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    return imported, skipped


if __name__ == "__main__":
    import sys

    file_path = r"C:\Users\RayBishop\Downloads\leads2.xls"

    print("=" * 50)
    print("HUBSPOT CONTACTS IMPORT")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == "--import":
        print("MODE: LIVE IMPORT")
        print()
        import_contacts(file_path, dry_run=False)
    else:
        print("MODE: DRY RUN (preview only)")
        print("Run with --import flag to actually import")
        print()
        import_contacts(file_path, dry_run=True)
