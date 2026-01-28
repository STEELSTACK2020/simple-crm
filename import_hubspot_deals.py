"""
HubSpot Deals Import Script
Imports deals from Deals 2.xlsx into the CRM database and links them to contacts.
"""

import pandas as pd
import re
from database import (
    init_database, get_connection, add_deal, add_contact_to_deal,
    sync_contact_deal_values_for_deal
)

# Initialize database
init_database()

# Stage mapping: HubSpot -> CRM
STAGE_MAP = {
    'Closed Won': 'closed_won',
    'Closed Lost': 'closed_lost',
    'Proposal Sent': 'proposal',
    'Negotiation / Decision Making': 'negotiation',
    'Qualified To Buy': 'new_deal',
    '2026 Q1 Buy': 'negotiation',
    '2026 Q2 Buy': 'negotiation',
    'On Hold': 'new_deal',
}


def extract_email(associated_contact):
    """Extract email from 'Name (email@example.com)' format."""
    if pd.isna(associated_contact):
        return None
    match = re.search(r'\(([^)]+@[^)]+)\)', str(associated_contact))
    return match.group(1).lower().strip() if match else None


def find_contact_by_email(email):
    """Find a contact ID by email."""
    if not email:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name, last_name FROM contacts WHERE LOWER(email) = ?", (email.lower(),))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None


def import_deals(file_path, dry_run=True):
    """
    Import deals from HubSpot Excel export.

    Args:
        file_path: Path to the xlsx file
        dry_run: If True, just preview without importing
    """
    # Read Excel file
    df = pd.read_excel(file_path)

    print(f"Found {len(df)} deals to import")
    print(f"Columns: {list(df.columns)}")
    print("-" * 60)

    imported = 0
    skipped = 0
    contacts_not_found = []
    contacts_linked = 0
    errors = []

    conn = get_connection()
    cursor = conn.cursor()

    for idx, row in df.iterrows():
        # Get deal name
        deal_name = str(row.get('Deal Name', '')).strip() if pd.notna(row.get('Deal Name')) else ''

        if not deal_name:
            skipped += 1
            errors.append(f"Row {idx + 2}: No deal name")
            continue

        # Get other fields
        amount = float(row.get('Amount', 0)) if pd.notna(row.get('Amount')) else 0
        salesperson = str(row.get('Deal owner', '')).strip() if pd.notna(row.get('Deal owner')) else None
        utm_medium = str(row.get('Original Traffic Source', '')).strip() if pd.notna(row.get('Original Traffic Source')) else None

        # Map stage
        hubspot_stage = str(row.get('Deal Stage', '')).strip() if pd.notna(row.get('Deal Stage')) else 'new_deal'
        crm_stage = STAGE_MAP.get(hubspot_stage, 'new_deal')

        # Handle close date
        close_date = None
        if pd.notna(row.get('Close Date')):
            try:
                close_date = pd.to_datetime(row['Close Date']).strftime('%Y-%m-%d')
            except:
                close_date = None

        # Determine if it's actual or expected close date based on stage
        actual_close_date = close_date if crm_stage in ['closed_won', 'closed_lost'] else None
        expected_close_date = close_date if crm_stage not in ['closed_won', 'closed_lost'] else None

        # Extract contact email
        associated_contact = row.get('Associated Contact', '')
        contact_email = extract_email(associated_contact)
        contact = find_contact_by_email(contact_email) if contact_email else None

        if dry_run:
            print(f"[PREVIEW] {deal_name}")
            print(f"          Value: ${amount:,.2f} | Stage: {hubspot_stage} -> {crm_stage}")
            print(f"          Owner: {salesperson} | Medium: {utm_medium}")
            if contact:
                print(f"          Contact: {contact['first_name']} {contact['last_name']} ({contact_email}) [FOUND]")
            elif contact_email:
                print(f"          Contact: {contact_email} [NOT FOUND]")
                contacts_not_found.append((deal_name, contact_email))
            else:
                print(f"          Contact: None specified")
            print()
            imported += 1
        else:
            try:
                # Check if deal already exists by name
                cursor.execute("SELECT id FROM deals WHERE name = ?", (deal_name,))
                existing = cursor.fetchone()

                if existing:
                    skipped += 1
                    errors.append(f"Row {idx + 2}: Deal already exists - {deal_name}")
                    continue

                # Add the deal
                result = add_deal(
                    name=deal_name,
                    value=amount,
                    stage=crm_stage,
                    salesperson=salesperson,
                    utm_medium=utm_medium,
                    expected_close_date=expected_close_date,
                )

                if result['success']:
                    deal_id = result['id']

                    # Set actual_close_date if closed
                    if actual_close_date:
                        cursor.execute(
                            "UPDATE deals SET actual_close_date = ? WHERE id = ?",
                            (actual_close_date, deal_id)
                        )
                        conn.commit()

                    # Link to contact if found
                    if contact:
                        link_result = add_contact_to_deal(deal_id, contact['id'])
                        if link_result['success']:
                            contacts_linked += 1
                            # If closed_won, sync the contact's deal_value
                            if crm_stage == 'closed_won':
                                sync_contact_deal_values_for_deal(deal_id)
                    elif contact_email:
                        contacts_not_found.append((deal_name, contact_email))

                    imported += 1
                    print(f"[IMPORTED] {deal_name} - ${amount:,.2f} ({crm_stage})")
                else:
                    skipped += 1
                    errors.append(f"Row {idx + 2}: {result.get('error', 'Unknown error')}")

            except Exception as e:
                skipped += 1
                errors.append(f"Row {idx + 2}: Error - {str(e)}")

    conn.close()

    print("-" * 60)
    print(f"SUMMARY:")
    print(f"  {'Would import' if dry_run else 'Imported'}: {imported}")
    print(f"  Skipped: {skipped}")
    if not dry_run:
        print(f"  Contacts linked: {contacts_linked}")

    if contacts_not_found:
        print(f"\nCONTACTS NOT FOUND ({len(contacts_not_found)}):")
        for deal_name, email in contacts_not_found[:15]:
            print(f"  - {email} (for deal: {deal_name[:40]}...)")
        if len(contacts_not_found) > 15:
            print(f"  ... and {len(contacts_not_found) - 15} more")

    if errors:
        print(f"\nISSUES ({len(errors)}):")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    return imported, skipped, contacts_not_found


if __name__ == "__main__":
    import sys

    file_path = r"C:\Users\RayBishop\Downloads\Deals 2.xlsx"

    print("=" * 60)
    print("HUBSPOT DEALS IMPORT")
    print("=" * 60)

    if len(sys.argv) > 1 and sys.argv[1] == "--import":
        print("MODE: LIVE IMPORT")
        print()
        import_deals(file_path, dry_run=False)
    else:
        print("MODE: DRY RUN (preview only)")
        print("Run with --import flag to actually import")
        print()
        import_deals(file_path, dry_run=True)
