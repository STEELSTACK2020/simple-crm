"""
Seed script to add sample data for testing the CRM dashboard.
Run this once to populate the database with example contacts.
"""

from database import init_database, add_contact

# Sample contacts with various UTM sources and deal values
sample_contacts = [
    {
        "first_name": "John",
        "last_name": "Smith",
        "email": "john.smith@example.com",
        "phone": "555-0101",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "spring_sale",
        "deal_value": 15000,
        "notes": "Very interested in enterprise plan"
    },
    {
        "first_name": "Sarah",
        "last_name": "Johnson",
        "email": "sarah.j@example.com",
        "phone": "555-0102",
        "utm_source": "facebook",
        "utm_medium": "social",
        "utm_campaign": "brand_awareness",
        "deal_value": 8500,
        "notes": "Referred two other clients"
    },
    {
        "first_name": "Michael",
        "last_name": "Williams",
        "email": "m.williams@example.com",
        "phone": "555-0103",
        "utm_source": "google",
        "utm_medium": "organic",
        "deal_value": 22000,
        "notes": "Large enterprise deal"
    },
    {
        "first_name": "Emily",
        "last_name": "Brown",
        "email": "emily.b@example.com",
        "phone": "555-0104",
        "utm_source": "linkedin",
        "utm_medium": "cpc",
        "utm_campaign": "b2b_outreach",
        "deal_value": 0,
        "notes": "Still in consideration phase"
    },
    {
        "first_name": "David",
        "last_name": "Miller",
        "email": "david.miller@example.com",
        "phone": "555-0105",
        "utm_source": "newsletter",
        "utm_medium": "email",
        "utm_campaign": "monthly_update",
        "deal_value": 5500,
        "notes": "Converted from newsletter subscriber"
    },
    {
        "first_name": "Jessica",
        "last_name": "Davis",
        "email": "jessica.d@example.com",
        "phone": "555-0106",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "competitor_keywords",
        "deal_value": 12000,
        "notes": "Switched from competitor"
    },
    {
        "first_name": "Chris",
        "last_name": "Garcia",
        "email": "c.garcia@example.com",
        "phone": "555-0107",
        "utm_source": "facebook",
        "utm_medium": "social",
        "utm_campaign": "retargeting",
        "deal_value": 0,
        "notes": "Requested demo, waiting for follow-up"
    },
    {
        "first_name": "Amanda",
        "last_name": "Martinez",
        "email": "amanda.m@example.com",
        "phone": "555-0108",
        "utm_source": "google",
        "utm_medium": "organic",
        "deal_value": 18500,
        "notes": "Found us through blog post"
    },
    {
        "first_name": "Robert",
        "last_name": "Taylor",
        "email": "r.taylor@example.com",
        "phone": "555-0109",
        "utm_source": "referral",
        "utm_medium": "partner",
        "utm_campaign": "agency_partner",
        "deal_value": 35000,
        "notes": "Agency partner referral, high value"
    },
    {
        "first_name": "Lisa",
        "last_name": "Anderson",
        "email": "lisa.a@example.com",
        "phone": "555-0110",
        "utm_source": "linkedin",
        "utm_medium": "organic",
        "deal_value": 0,
        "notes": "Connected via LinkedIn, early stage"
    },
    {
        "first_name": "Daniel",
        "last_name": "Thomas",
        "email": "d.thomas@example.com",
        "phone": "555-0111",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "spring_sale",
        "deal_value": 9800,
        "notes": "Quick conversion from ad click"
    },
    {
        "first_name": "Nicole",
        "last_name": "White",
        "email": "nicole.w@example.com",
        "phone": "555-0112",
        "utm_source": "newsletter",
        "utm_medium": "email",
        "utm_campaign": "product_launch",
        "deal_value": 7200,
        "notes": "Responded to product launch email"
    },
]


def seed_data():
    """Initialize database and add sample contacts."""
    print("Initializing database...")
    init_database()

    print("Adding sample contacts...")
    for contact in sample_contacts:
        result = add_contact(**contact)
        if result['success']:
            print(f"  Added: {contact['first_name']} {contact['last_name']}")
        else:
            print(f"  Skipped (exists): {contact['email']}")

    print("\nDone! Sample data has been added.")
    print("Run 'python app.py' to start the dashboard.")


if __name__ == "__main__":
    seed_data()
