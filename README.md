# Simple CRM

A lightweight contact management system with UTM tracking, deal value attribution, and analytics dashboard. Built with Python, Flask, and SQLite.

## Features

### Contact Management
- Store first name, last name, email, phone, and notes
- Search contacts by name or email
- Edit and delete contacts

### UTM Tracking
- Track source, medium, campaign, term, and content for each contact
- See which marketing channels bring in the most leads and revenue

### Deal Tracking
- Assign dollar amounts to contacts when they close deals
- Set manual deal close dates
- Track deals pending close dates vs closed deals

### Deals Pipeline
- Kanban-style drag-and-drop pipeline board
- Stages: New Deal, Proposal, Negotiation, Closed Won, Closed Lost
- **Date Filter**: Filter deals by created date range
- **Search**: Search deals by name
- **Salesperson Filter**: Filter by assigned salesperson
- **Stage Filter**: Filter by deal stage
- **Mandatory Close Reason**: When moving a deal to Closed Won/Lost, a popup requires entering a win/loss reason
- Quick-select buttons for common reasons (Best pricing, Went with competitor, etc.)

### Products
- Product catalog for quotes and pricing
- Fields: Name, SKU (unique), Description, Price
- Search products by name, SKU, or description
- Active/Inactive status for products

### Companies
- Central database for all business accounts
- Fields: Name, Phone, Email, Website, Address, City, State, ZIP, Notes
- Search companies by name
- Company detail page shows linked deals, quotes, and contacts
- Reusable across quotes and deals

### Quotes System
- Professional quote generation with PDF export
- **Deal Creation on Save**: Deal is created automatically when quote is first saved (not on initial creation)
- **Company Selector**: Select existing company or create new one inline
- **Searchable Contact Lookup**: Type to search contacts by name or email
- **Auto-Populated Dates**: Quote date = today, Expiry = 30 days out
- **Terms & Conditions Presets**:
  - 50/50 Payment Terms (50% upfront, 50% with 15-day terms)
  - 100% Upfront Payment
  - Custom Terms (free text)
- **Line Items**: Add products from catalog or custom items with quantity, price, discounts
- **Scroll Position Preserved**: Page stays in same spot after adding/updating items
- **Auto-Status Update**: Status automatically changes to "Sent" when quote is saved
- **Linked to Deals**: Quotes appear on the deal detail page showing all associated quotes
- **Salesperson Filter**: Filter quotes by salesperson on quotes list
- **Visual Indicators**: Accepted quotes show green in the list
- **Save & Download PDF**: Button saves quote first, then downloads PDF (prevents stale data)

### PDF Quote Export
- Matches existing Steelstack quote format (HubSpot-style)
- **Page 1**: Logo header, title banner, customer info, quote details, products table, totals
- **Page 2**: Purchase terms, salesperson contact, company address
- **Signature Section**: Signature line, Date line, and Printed Name line for customer sign-off
- Download as: `STEELSTACK_CustomerName_Q-2025-0001.pdf`
- Available from quote detail and edit pages

### Shipping Calculator
- Built into the quote edit page
- **ZIP Code Distance**: Enter origin and destination ZIP codes
- **Real Driving Distance**: Uses OSRM (Open Source Routing Machine) for actual road miles, not straight-line
- **Rate Per Mile**: Default $3.85/mile, adjustable
- **Minimum Cost**: $1,200 minimum shipping charge (shows note when applied)
- **Editable Price**: Manually adjust price per truck after calculation
- **Multiple Trucks**: Select number of trucks (1, 2, 3, etc.) with auto-calculated total
- **Add to Quote**: One-click adds shipping as a line item
- Shipping description includes route, distance, and rate breakdown

### Salespeople
- Full salesperson profiles with contact info
- Fields: Name, Email, Phone
- Salesperson info auto-populates on quotes
- Filter deals and quotes by salesperson

### Email Integration
- **Gmail OAuth**: Connect your Gmail/Google Workspace account
- **Outlook OAuth**: Connect your Outlook/Office 365 account
- **On-Demand Fetching**: Emails are fetched when viewing a contact (not stored in database)
- **Contact Detail Integration**: See email history with each contact directly on their profile
- **Read-Only**: We only request read permission - cannot send emails from CRM
- **Secure**: Uses OAuth tokens, your password is never stored
- Can connect both Gmail AND Outlook simultaneously

### Lead Activity Tracking
- **Last Activity Date**: Track when each contact was last engaged
- **Contacts List Column**: "Last Activity" column shows activity date or "Never" badge
- **Dashboard Widget**: "Leads Needing Attention" shows contacts with no emails/notes
- **Accountability View**: Quickly see which leads need follow-up

### Embeddable Lead Capture Form
- Self-contained form code to embed on external websites (Squarespace, etc.)
- **Automatic UTM Tracking**: Captures utm_source, utm_medium, utm_campaign, utm_term, utm_content from URL
- Captures: First Name, Last Name, Email, Phone, Message
- Submissions go directly to CRM Contacts
- CORS-enabled API endpoint for cross-origin submissions
- Copy-paste embed code available at `/forms`

### Analytics Dashboard
- **Stats Cards**: Total contacts, total sales, closed deals, average deal value
- **Leads Needing Attention**: Widget showing untouched leads that need follow-up (no emails, no notes)
- **Date Filtering**: Filter dashboard by year, month, or custom date range
- **Year-over-Year Comparison**: Compare revenue and deals across years
- **Sales by Medium Pie Chart**: Clickable - shows deals when clicked
- **Deals by Medium Pie Chart**: Clickable - shows deals when clicked
- **Leads by Month Bar Chart**: Stacked by medium, with year dropdown (2024-2030), clickable segments
- **Performance Tables**: Revenue and contacts by source/medium
- **Recent Closed Deals**: Sorted by close date
- **Pipeline Deals**: Active deals in progress
- **Recent Contacts**: Latest contacts added

### Traffic Dashboard (Google Analytics)
- **Multiple Websites**: Track multiple GA4 properties with dropdown selector
- **Sessions by Channel**: Organic Search, Paid Search, Direct, Paid Social, Organic Social, Referral, Email, etc.
- **Users & New Users**: Track total and new visitors
- **Phone Clicks**: Track how many people click your phone number on your website
- **Sessions by Month**: Stacked bar chart with year dropdown (2024-2030)
- **Channel Performance Table**: Sessions, users, bounce rate, avg duration
- **Date Filtering**: Last 7/30/90 days, year to date, or custom range
- **GA4 Integration**: Connect your Google Analytics 4 property for real data

### REST API
- Full API for integration with external systems (forms, other software)
- Endpoints for contacts, deals, analytics, traffic, and chart data

## Quick Start

```bash
cd C:\Users\RayBishop\simple-crm
py -m pip install flask reportlab pgeocode requests
py seed_sample_data.py   # Optional: adds demo data
py app.py
```

Open **http://localhost:5000** in your browser.

## Project Structure

```
simple-crm/
├── app.py              # Flask web application (routes & API)
├── database.py         # SQLite database module (all DB functions)
├── pdf_generator.py    # Quote PDF generation (reportlab)
├── shipping_calculator.py # ZIP code mileage & shipping cost calculator
├── analytics_ga.py     # Google Analytics 4 integration module
├── crm.db              # SQLite database file (created on first run)
├── ga_config.json      # GA4 property ID (created when connected)
├── ga_token.json       # OAuth tokens (created after Google login)
├── oauth_secrets.json  # OAuth client credentials (you enter these)
├── requirements.txt    # Python dependencies
├── seed_sample_data.py # Script to add sample contacts
├── README.md           # This documentation file
├── static/
│   └── logo.png        # Steelstack logo for PDF quotes
└── templates/
    ├── base.html                  # Base template with navigation & Chart.js
    ├── dashboard.html             # Sales dashboard with analytics & charts
    ├── traffic.html               # Traffic dashboard with GA4 data
    ├── traffic_settings.html      # GA4 OAuth settings
    ├── traffic_select_property.html # GA4 property selection after OAuth
    ├── contacts.html              # Contact list view with search
    ├── contact_detail.html        # Single contact view with timeline
    ├── contact_edit.html          # Edit contact form
    ├── contact_add.html           # Add new contact form
    ├── companies.html             # Companies list view with search
    ├── company_detail.html        # Single company view with deals/quotes/contacts
    ├── company_form.html          # Add/edit company form
    ├── deals.html                 # Deals pipeline kanban board
    ├── deal_detail.html           # Single deal view
    ├── deal_add.html              # Add/edit deal form
    ├── products.html              # Product catalog list
    ├── product_detail.html        # Single product view
    ├── product_form.html          # Add/edit product form
    ├── quotes.html                # Quotes list with filters
    ├── quote_form.html            # Create new quote form
    ├── quote_edit.html            # Edit quote & line items
    ├── quote_detail.html          # View quote details
    ├── salespeople.html           # Salespeople list
    ├── salesperson_form.html      # Add/edit salesperson
    └── forms.html                 # Embeddable form code generator
```

## Web Interface

| URL | Description |
|-----|-------------|
| `/` | Sales dashboard with analytics, charts, and date filtering |
| `/?period=2025` | Sales dashboard filtered to year 2025 |
| `/?period=2025-06` | Sales dashboard filtered to June 2025 |
| `/?start_date=2025-01-01&end_date=2025-12-31` | Sales dashboard with custom date range |
| `/traffic` | Traffic dashboard with GA4 website analytics |
| `/traffic?period=7d` | Traffic for last 7 days |
| `/traffic?period=30d` | Traffic for last 30 days |
| `/traffic?period=90d` | Traffic for last 90 days |
| `/traffic?period=ytd` | Traffic year to date |
| `/traffic/settings` | Configure Google Analytics connection |
| `/contacts` | List all contacts with search |
| `/contacts?search=john` | Search contacts |
| `/contacts/add` | Add a new contact manually |
| `/contacts/<id>` | View contact details |
| `/contacts/<id>/edit` | Edit a contact |
| `/deals` | Deals pipeline kanban board |
| `/deals?salesperson=John` | Filter deals by salesperson |
| `/deals?stage=closed_won` | Filter deals by stage |
| `/deals?date_from=2025-01-01&date_to=2025-12-31` | Filter deals by date range |
| `/deals?search=acme` | Search deals by name |
| `/deals/add` | Add a new deal |
| `/deals/<id>` | View deal details |
| `/deals/<id>/edit` | Edit a deal |
| `/products` | Product catalog list |
| `/products?search=widget` | Search products |
| `/products/add` | Add a new product |
| `/products/<id>` | View product details |
| `/products/<id>/edit` | Edit a product |
| `/companies` | Companies list with search |
| `/companies/add` | Add a new company |
| `/companies/<id>` | View company details (linked deals, quotes, contacts) |
| `/companies/<id>/edit` | Edit a company |
| `/quotes` | Quotes list with filters |
| `/quotes?salesperson=1` | Filter quotes by salesperson |
| `/quotes?status=accepted` | Filter quotes by status |
| `/quotes/add` | Create a new quote |
| `/quotes/<id>` | View quote details |
| `/quotes/<id>/edit` | Edit quote and line items |
| `/quotes/<id>/pdf` | Download quote as PDF |
| `/salespeople` | Salespeople list |
| `/salespeople/add` | Add a new salesperson |
| `/salespeople/<id>/edit` | Edit a salesperson |
| `/forms` | Get embeddable lead capture form code |

## API Endpoints

All API endpoints return JSON.

### Contacts CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/contacts` | List all contacts (supports `?search=`, `?limit=`, `?offset=`) |
| `POST` | `/api/contacts` | Create a new contact |
| `GET` | `/api/contacts/<id>` | Get a single contact |
| `PUT/PATCH` | `/api/contacts/<id>` | Update a contact |
| `DELETE` | `/api/contacts/<id>` | Delete a contact |
| `POST` | `/api/contacts/<id>/deal` | Set deal value for a contact |

### Analytics & Charts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/analytics` | Get dashboard analytics data |
| `GET` | `/api/deals/by-medium/<medium>` | Get deals filtered by UTM medium |
| `GET` | `/api/deals/by-source/<source>` | Get deals filtered by UTM source |
| `GET` | `/api/leads/by-year/<year>` | Get leads by month/medium for bar chart |
| `GET` | `/api/leads/by-month-medium/<month>/<medium>` | Get leads for specific month & medium |
| `GET` | `/api/traffic/by-year/<year>` | Get traffic sessions by month/channel |

### Deals

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/deals` | List all deals |
| `PUT` | `/api/deals/<id>/stage` | Update deal stage (for drag-and-drop) |
| `GET` | `/api/deals/analytics` | Get deal analytics data |

### Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/products` | List all products (future) |

### Form Submission (External Websites)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/form/submit` | Submit lead from external form (CORS enabled) |

### Example: Add a Contact via API

```bash
curl -X POST http://localhost:5000/api/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "555-1234",
    "utm_source": "google",
    "utm_medium": "cpc",
    "utm_campaign": "spring_sale"
  }'
```

### Example: Set Deal Value with Close Date

```bash
curl -X PUT http://localhost:5000/api/contacts/1 \
  -H "Content-Type: application/json" \
  -d '{
    "deal_value": 15000,
    "deal_closed_date": "2025-06-15"
  }'
```

### Example: Get Deals by Medium

```bash
curl http://localhost:5000/api/deals/by-medium/cpc
curl http://localhost:5000/api/deals/by-medium/Unknown  # For NULL medium
```

### Example: Get Leads for Chart

```bash
curl http://localhost:5000/api/leads/by-year/2025
curl http://localhost:5000/api/leads/by-month-medium/2025-06/cpc
```

## Form Integration

### Easy Way: Use the Built-in Embeddable Form

1. Go to `/forms` in your CRM
2. Click **Copy Code**
3. Paste the code into a **Code Block** on Squarespace (or any website)
4. Done! Form submissions go directly to your CRM with UTM tracking

The embeddable form automatically captures UTM parameters from URLs like:
```
https://yoursite.com/contact?utm_source=google&utm_medium=cpc&utm_campaign=spring_sale
```

### Advanced: Custom Form Integration

To capture leads from custom forms, POST to `/api/form/submit` (CORS enabled):

```javascript
// Get UTM params from URL
const urlParams = new URLSearchParams(window.location.search);

// Submit to CRM
fetch('http://YOUR-CRM-URL/api/form/submit', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    first_name: document.getElementById('firstName').value,
    last_name: document.getElementById('lastName').value,
    email: document.getElementById('email').value,
    phone: document.getElementById('phone').value,
    message: document.getElementById('message').value,
    utm_source: urlParams.get('utm_source'),
    utm_medium: urlParams.get('utm_medium'),
    utm_campaign: urlParams.get('utm_campaign'),
    utm_term: urlParams.get('utm_term'),
    utm_content: urlParams.get('utm_content')
  })
});
```

## Database Schema

The `contacts` table contains:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `first_name` | TEXT | Contact's first name (required) |
| `last_name` | TEXT | Contact's last name (required) |
| `email` | TEXT | Email address (unique, required) |
| `phone` | TEXT | Phone number |
| `utm_source` | TEXT | Traffic source (google, facebook, etc.) |
| `utm_medium` | TEXT | Marketing medium (cpc, organic, email, social, etc.) |
| `utm_campaign` | TEXT | Campaign name |
| `utm_term` | TEXT | Search keyword |
| `utm_content` | TEXT | Ad/content identifier |
| `deal_value` | REAL | Dollar amount if deal closed (default 0) |
| `deal_closed_date` | TEXT | When the deal was closed (ISO format) |
| `created_at` | TEXT | When contact was created (auto-set) |
| `updated_at` | TEXT | When contact was last updated (auto-set) |
| `notes` | TEXT | Additional notes |

### Indexes

- `idx_contacts_email` - Fast email lookups
- `idx_contacts_utm_source` - Fast source analytics

### Deals Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `name` | TEXT | Deal name (required) |
| `value` | REAL | Deal value in dollars |
| `stage` | TEXT | Pipeline stage (new_deal, proposal, negotiation, closed_won, closed_lost) |
| `salesperson` | TEXT | Assigned salesperson |
| `utm_source` | TEXT | Traffic source |
| `utm_medium` | TEXT | Marketing medium |
| `utm_campaign` | TEXT | Campaign name |
| `expected_close_date` | TEXT | Expected close date |
| `actual_close_date` | TEXT | Actual close date (auto-set when closed) |
| `close_reason` | TEXT | Win/loss reason (required when closing) |
| `created_at` | TEXT | When deal was created |
| `updated_at` | TEXT | When deal was last updated |
| `notes` | TEXT | Additional notes |

### Products Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `name` | TEXT | Product name (required) |
| `sku` | TEXT | SKU - unique identifier |
| `description` | TEXT | Product description |
| `price` | REAL | Product price |
| `is_active` | INTEGER | 1 = active, 0 = inactive |
| `created_at` | TEXT | When product was created |
| `updated_at` | TEXT | When product was last updated |

### Salespeople Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `name` | TEXT | Salesperson name (unique) |
| `email` | TEXT | Salesperson email |
| `phone` | TEXT | Salesperson phone |
| `created_at` | TEXT | When added |

### Companies Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `name` | TEXT | Company name (unique, required) |
| `phone` | TEXT | Company phone |
| `email` | TEXT | Company email |
| `website` | TEXT | Company website URL |
| `address` | TEXT | Street address |
| `city` | TEXT | City |
| `state` | TEXT | State |
| `zip` | TEXT | ZIP code |
| `notes` | TEXT | Additional notes |
| `created_at` | TEXT | When created |
| `updated_at` | TEXT | When last updated |

### Quotes Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `quote_number` | TEXT | Unique quote number (Q-YYYY-NNNN) |
| `title` | TEXT | Quote title |
| `deal_id` | INTEGER | Linked deal (FK to deals) |
| `company_id` | INTEGER | Linked company (FK to companies) |
| `contact_id` | INTEGER | Linked contact (FK to contacts) |
| `salesperson_id` | INTEGER | Assigned salesperson (FK to salespeople) |
| `salesperson_name` | TEXT | Salesperson name (snapshot) |
| `salesperson_email` | TEXT | Salesperson email (snapshot) |
| `salesperson_phone` | TEXT | Salesperson phone (snapshot) |
| `customer_name` | TEXT | Customer name |
| `customer_email` | TEXT | Customer email |
| `customer_phone` | TEXT | Customer phone |
| `customer_company` | TEXT | Customer company name |
| `quote_date` | TEXT | Date quote was created |
| `expiry_date` | TEXT | Quote expiration date |
| `status` | TEXT | draft, sent, accepted, declined, expired |
| `subtotal` | REAL | Sum of line items |
| `discount_percent` | REAL | Overall discount percentage |
| `discount_amount` | REAL | Calculated discount amount |
| `tax_percent` | REAL | Tax percentage |
| `tax_amount` | REAL | Calculated tax amount |
| `total` | REAL | Final total |
| `notes` | TEXT | Quote notes |
| `terms` | TEXT | Terms & conditions |
| `created_at` | TEXT | When created |
| `updated_at` | TEXT | When last updated |

### Quote Items Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `quote_id` | INTEGER | Parent quote (FK to quotes) |
| `product_id` | INTEGER | Linked product (FK to products, optional) |
| `product_name` | TEXT | Product name |
| `product_sku` | TEXT | Product SKU |
| `description` | TEXT | Line item description |
| `quantity` | REAL | Quantity |
| `unit_price` | REAL | Price per unit |
| `discount_percent` | REAL | Line item discount |
| `line_total` | REAL | Calculated line total |
| `sort_order` | INTEGER | Display order |
| `created_at` | TEXT | When added |

## Database Functions (database.py)

| Function | Description |
|----------|-------------|
| `init_database()` | Create tables and indexes |
| `add_contact(...)` | Add new contact with all fields |
| `update_contact(id, **kwargs)` | Update contact fields |
| `set_deal_value(id, value)` | Set deal value and auto-set close date |
| `get_contact(id)` | Get single contact by ID |
| `get_contact_by_email(email)` | Get contact by email |
| `get_all_contacts(limit, offset)` | Paginated contact list |
| `search_contacts(query)` | Search by name or email |
| `delete_contact(id)` | Delete a contact |
| `get_analytics(start_date, end_date)` | Dashboard data with optional date filter |
| `get_year_comparison()` | Year-over-year comparison data |
| `get_leads_by_month_medium(year)` | Leads breakdown for bar chart |

## Dashboard Features Detail

### Date Filtering
- **All Time**: Show all data
- **Year buttons**: 2024, 2025, 2026 quick filters
- **Month dropdown**: Select specific month (Jan 2025 - Dec 2026)
- **Custom range**: Pick start and end dates

### Charts (Chart.js)
- **Sales by Medium Pie Chart**: Shows revenue distribution, click slices to see deals
- **Deals by Medium Pie Chart**: Shows deal count distribution, click slices to see deals
- **Leads by Month Bar Chart**:
  - Stacked bars by UTM medium
  - Year dropdown (2024-2030)
  - Totals displayed on top of each bar
  - Click any segment to see those leads

### Modal Popups
When you click chart elements, a modal shows:
- List of deals/leads
- Total count and value
- Click any row to go to contact detail

## Running on Windows

```bash
# Navigate to project
cd C:\Users\RayBishop\simple-crm

# Install Flask (if not installed)
py -m pip install flask

# Run the app
py app.py
```

The app runs on `http://localhost:5000` by default.

## Tech Stack

- **Backend**: Python 3, Flask
- **Database**: SQLite
- **Frontend**: HTML, Tailwind CSS (via CDN), Chart.js (via CDN)
- **Templating**: Jinja2

## Setting Up Google Analytics

To connect your GA4 property and see real website traffic data (~10 minutes):

### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (top dropdown > New Project) or select existing

### Step 2: Enable the Analytics API
1. Go to [Analytics Data API](https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com)
2. Click **Enable**

### Step 3: Set Up OAuth Consent Screen
1. Go to APIs & Services > OAuth consent screen (or "Google Auth Platform" > "Branding")
2. Choose "External"
3. Fill in App name and your email
4. Click through to save

### Step 4: Add Yourself as Test User
1. Go to "Google Auth Platform" > "Audience" (or OAuth consent screen > Test users)
2. Click "+ Add Users"
3. Enter your Gmail address and save

### Step 5: Create OAuth Credentials
1. Go to APIs & Services > Credentials
2. Click "Create Credentials" > "OAuth client ID"
3. Application type: **Web application**
4. Under "Authorized redirect URIs" add: `http://localhost:5000/traffic/oauth/callback`
5. Click Create
6. Copy the **Client ID** and **Client Secret** (secret starts with `GOCSPX-`)

### Step 6: Configure in CRM
1. Go to `/traffic/settings` in the CRM
2. Enter the Client ID and Client Secret
3. Click "Save Credentials"
4. Click "Connect with Google" button
5. Login with your Google account
6. Enter your GA4 Property ID (found in GA4 Admin > Property Settings)

The traffic dashboard will now show real data from your website.

## Multiple Websites

Track multiple websites from the same Traffic dashboard using a dropdown selector.

### How It Works
- The Google OAuth setup is **one-time only** - you already did this
- Each website just needs its GA4 Property ID
- All websites under your Google account are accessible
- Switch between websites using the dropdown on the Traffic page

### Adding Another Website

1. Go to **Traffic** dashboard
2. Click the website dropdown → **"+ Add Website"**
3. Enter:
   - **Website Name**: Friendly name (e.g., "Company Blog")
   - **GA4 Property ID**: Numbers only (found in GA4 Admin > Property Settings)
4. Click **Add Website**

That's it - no new OAuth setup, no Google Cloud Console. Just the Property ID.

### Requirements for Each Website
- Must have Google Analytics (GA4) installed on the website
- Must be accessible by the same Google account you logged in with
- Each website has its own unique Property ID

### Managing Websites
- **Switch websites**: Use the dropdown on the Traffic page
- **Add website**: Dropdown → "+ Add Website" or GA Settings page
- **Remove website**: GA Settings page → click "Remove" next to the website
- **Rename website**: Edit the `ga_config.json` file directly

## Running the App

Every time you want to use the CRM:

```bash
cd C:\Users\RayBishop\simple-crm
py app.py
```

Then open http://localhost:5000 in your browser.

**Keep the terminal window open** - closing it stops the CRM.

## Phone Click Tracking

Track when visitors click phone numbers on your website. Data shows in the Traffic dashboard.

### Setup for Squarespace

1. Log into Squarespace
2. Go to **Settings** → **Advanced** → **Code Injection**
3. Paste this in the **Footer** section:

```javascript
<script>
document.addEventListener('click', function(e) {
  var link = e.target.closest('a[href^="tel:"]');
  if (link) {
    gtag('event', 'phone_click', {
      event_category: 'contact',
      event_label: link.href
    });
  }
});
</script>
```

4. Click **Save**

### Requirements
- Google Analytics (GA4) must be installed on your website
- The code works with ANY phone number link on your site
- Data appears in CRM Traffic dashboard within 24-48 hours

### Testing Phone Click Tracking
1. Open GA4: [analytics.google.com](https://analytics.google.com)
2. Go to **Reports** → **Realtime**
3. Click a phone number on your website
4. Watch for "phone_click" event (appears within 5-30 seconds)

## Backup & Restore

### Create a Backup

**Option 1: Manual Zip**
Right-click the `simple-crm` folder → Send to → Compressed (zipped) folder

**Option 2: PowerShell Command**
```powershell
Compress-Archive -Path 'C:\Users\RayBishop\simple-crm' -DestinationPath 'C:\Users\RayBishop\simple-crm-backup.zip' -Force
```

### What Gets Backed Up
| File | Contains |
|------|----------|
| `crm.db` | All contacts, deals, and data (MOST IMPORTANT) |
| `ga_token.json` | Google login credentials |
| `ga_config.json` | GA4 property ID |
| `oauth_secrets.json` | OAuth client credentials |
| Everything else | Application code |

### Restore from Backup
1. Delete the broken `simple-crm` folder
2. Right-click the backup zip → **Extract All**
3. Run `py app.py`

### Backup Tips
- Store a copy on OneDrive, Dropbox, or USB drive
- Back up regularly, especially before making changes
- The `crm.db` file is your data - protect it!

## Moving to a New Computer

### Step 1: Copy Your Folder
Copy the entire `simple-crm` folder to the new computer:
- USB drive
- OneDrive / Dropbox / Google Drive
- Email (zip it first)

### Step 2: Install Python
1. Download from [python.org](https://www.python.org/downloads/)
2. During install, check **"Add Python to PATH"**

### Step 3: Install Dependencies
Open Command Prompt in the `simple-crm` folder:
```bash
py -m pip install flask reportlab pgeocode requests google-analytics-data google-auth google-auth-oauthlib
```

### Step 4: Run It
```bash
py app.py
```
Open http://localhost:5000 - done!

### Notes
- Your data travels with the folder (it's in `crm.db`)
- Google Analytics may require re-login (go to `/traffic/settings`)
- Takes about 5 minutes total

## Deployment Options

When ready to put online for access from anywhere:

| Service | Monthly Cost | Difficulty | Notes |
|---------|--------------|------------|-------|
| **PythonAnywhere** | $5/mo | Easiest | Made for Python/Flask apps |
| **Render** | Free / $7/mo | Easy | Free tier sleeps after inactivity |
| **Railway** | ~$5/mo | Easy | Simple interface |
| **DigitalOcean** | $4-6/mo | Medium | More control |
| **Heroku** | $5-7/mo | Easy | Popular but pricier |

**Recommended: PythonAnywhere** - easiest for Flask apps, $5/month.

### Domain Options

| Option | Cost |
|--------|------|
| Free subdomain (e.g., `yourname.pythonanywhere.com`) | $0 |
| Subdomain of your domain (e.g., `crm.yoursite.com`) | Free (just DNS) |
| New domain (e.g., `yourcrm.com`) | ~$12/year |

### What Changes When Hosted
- Update GA4 OAuth redirect URI to your new domain
- Access from anywhere (phone, other computers, team members)
- No need to keep your computer running

## Future Enhancements

- Email quotes directly to customers
- User authentication for team access
- Email integration
- CSV import/export
- Advanced filtering and reporting
- Contact tags/categories
- Activity log/history
- Duplicate quote functionality
