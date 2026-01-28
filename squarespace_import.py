"""
Squarespace Form Submissions Import
Pulls contacts from Squarespace forms for January 2026
"""

import requests
from datetime import datetime

# Squarespace API Configuration
API_KEY = "5536b32d-44cb-4fa6-b37f-648ef4f6c531"
BASE_URL = "https://api.squarespace.com/1.0"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "User-Agent": "SimpleCRM/1.0"
}


def get_forms():
    """Get all forms from Squarespace."""
    url = f"{BASE_URL}/commerce/forms"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting forms: {response.status_code}")
        print(response.text)
        return None


def get_form_submissions(form_id, start_date=None, end_date=None):
    """Get submissions for a specific form."""
    url = f"{BASE_URL}/commerce/forms/{form_id}/submissions"

    params = {}
    if start_date:
        params['modifiedAfter'] = start_date.isoformat() + 'Z'
    if end_date:
        params['modifiedBefore'] = end_date.isoformat() + 'Z'

    all_submissions = []
    cursor = None

    while True:
        if cursor:
            params['cursor'] = cursor

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            submissions = data.get('result', [])
            all_submissions.extend(submissions)

            # Check for pagination
            pagination = data.get('pagination', {})
            if pagination.get('hasNextPage'):
                cursor = pagination.get('nextPageCursor')
            else:
                break
        else:
            print(f"Error getting submissions: {response.status_code}")
            print(response.text)
            break

    return all_submissions


def extract_contact_info(submission):
    """Extract contact info from a form submission."""
    fields = submission.get('formFields', [])

    contact = {
        'id': submission.get('id'),
        'submitted_at': submission.get('submittedOn'),
        'first_name': '',
        'last_name': '',
        'email': '',
        'phone': '',
        'company': '',
        'message': '',
        'raw_fields': {}
    }

    for field in fields:
        label = field.get('label', '').lower()
        value = field.get('value', '')

        contact['raw_fields'][field.get('label', 'Unknown')] = value

        # Try to match common field names
        if 'first' in label and 'name' in label:
            contact['first_name'] = value
        elif 'last' in label and 'name' in label:
            contact['last_name'] = value
        elif label == 'name' or label == 'full name':
            # Split full name
            parts = value.split(' ', 1)
            contact['first_name'] = parts[0]
            contact['last_name'] = parts[1] if len(parts) > 1 else ''
        elif 'email' in label:
            contact['email'] = value
        elif 'phone' in label or 'tel' in label or 'mobile' in label:
            contact['phone'] = value
        elif 'company' in label or 'business' in label or 'organization' in label:
            contact['company'] = value
        elif 'message' in label or 'comment' in label or 'note' in label:
            contact['message'] = value

    return contact


def pull_january_2026_contacts():
    """Pull all form submissions from January 2026."""

    print("=" * 50)
    print("Squarespace Contact Import - January 2026")
    print("=" * 50)

    # January 2026 date range
    start_date = datetime(2026, 1, 1, 0, 0, 0)
    end_date = datetime(2026, 1, 31, 23, 59, 59)

    print(f"\nDate range: {start_date.date()} to {end_date.date()}")

    # First, get all forms
    print("\nFetching forms...")
    forms_response = get_forms()

    if not forms_response:
        print("Could not retrieve forms. Check your API key.")
        return []

    forms = forms_response.get('result', [])
    print(f"Found {len(forms)} form(s)")

    all_contacts = []

    for form in forms:
        form_id = form.get('id')
        form_name = form.get('name', 'Unnamed Form')

        print(f"\n--- Form: {form_name} ---")

        submissions = get_form_submissions(form_id, start_date, end_date)
        print(f"Found {len(submissions)} submission(s) in January 2026")

        for sub in submissions:
            contact = extract_contact_info(sub)
            contact['form_name'] = form_name
            all_contacts.append(contact)

    return all_contacts


def print_contacts(contacts):
    """Print contacts in a readable format."""
    print("\n" + "=" * 50)
    print(f"TOTAL CONTACTS: {len(contacts)}")
    print("=" * 50)

    for i, contact in enumerate(contacts, 1):
        print(f"\n--- Contact {i} ---")
        print(f"Name: {contact['first_name']} {contact['last_name']}")
        print(f"Email: {contact['email']}")
        print(f"Phone: {contact['phone']}")
        print(f"Company: {contact['company']}")
        print(f"Form: {contact.get('form_name', 'Unknown')}")
        print(f"Submitted: {contact['submitted_at']}")
        if contact['message']:
            print(f"Message: {contact['message'][:100]}...")


def export_to_csv(contacts, filename='squarespace_contacts_jan2026.csv'):
    """Export contacts to CSV file."""
    import csv

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['First Name', 'Last Name', 'Email', 'Phone', 'Company', 'Form', 'Submitted', 'Message'])

        for contact in contacts:
            writer.writerow([
                contact['first_name'],
                contact['last_name'],
                contact['email'],
                contact['phone'],
                contact['company'],
                contact.get('form_name', ''),
                contact['submitted_at'],
                contact['message']
            ])

    print(f"\nExported to {filename}")


if __name__ == "__main__":
    contacts = pull_january_2026_contacts()

    if contacts:
        print_contacts(contacts)
        export_to_csv(contacts)
        print("\nDone! Check squarespace_contacts_jan2026.csv")
    else:
        print("\nNo contacts found for January 2026.")
