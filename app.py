"""
Simple CRM Flask Application
Web dashboard and API for contact management.
"""

import os
# Allow OAuth over HTTP for local development (remove in production)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session
from functools import wraps
from datetime import datetime, timedelta
from database import (
    init_database, add_contact, update_contact, get_contact, get_contact_by_email,
    get_all_contacts, search_contacts, delete_contact, get_contacts_count,
    get_analytics, set_deal_value, get_year_comparison,
    get_leads_by_month_medium, get_deals_for_contact,
    update_contact_activity, get_untouched_leads,
    # Deal functions
    DEAL_STAGES, add_deal, update_deal, update_deal_stage, get_deal,
    get_all_deals, get_deals_by_stage, delete_deal,
    add_contact_to_deal, remove_contact_from_deal, get_deal_analytics, search_deals,
    get_salespeople, get_salesperson, add_salesperson, update_salesperson, delete_salesperson, get_utm_mediums,
    get_dashboard_analytics, get_deals_year_comparison, get_deals_by_month_medium,
    # Product functions
    add_product, update_product, get_product, get_all_products, search_products, delete_product,
    # Company functions
    add_company, update_company, get_company, get_all_companies, search_companies, delete_company,
    get_company_deals, get_company_contacts, get_company_quotes,
    # Quote functions
    QUOTE_STATUSES, add_quote, update_quote, get_quote, get_all_quotes, delete_quote,
    add_quote_item, update_quote_item, delete_quote_item, get_quotes_for_deal, recalculate_quote_totals,
    # User functions
    add_user, get_user, get_user_by_username, authenticate_user, update_user,
    delete_user, get_all_users, get_user_count,
    # Quick notes
    get_quick_notes, save_quick_notes,
    # Fix requests
    add_fix_request, get_all_fix_requests, init_fix_requests_table, update_fix_request_status,
    # Migrations
    add_sales_notes_column, add_contact_salesperson_column
)
from pdf_generator import generate_quote_pdf
from shipping_calculator import calculate_shipping_cost, DEFAULT_ORIGIN_ZIP, RATE_PER_MILE
from analytics_ga import (
    is_oauth_configured, is_ga_connected, get_ga_config, save_ga_config,
    fetch_traffic_by_channel, fetch_traffic_by_channel_and_month,
    fetch_phone_clicks,
    get_demo_traffic_data, get_demo_traffic_by_month,
    get_oauth_flow, save_oauth_token, save_oauth_secrets, get_oauth_secrets,
    disconnect_ga, OAUTH_SECRETS_PATH,
    get_websites, get_website, add_website, remove_website, get_default_website
)
from email_integration import (
    get_email_status, is_gmail_configured, is_gmail_connected,
    get_gmail_auth_url, gmail_oauth_callback, disconnect_gmail,
    is_outlook_configured, is_outlook_connected, save_outlook_config,
    get_outlook_auth_url, outlook_oauth_callback, disconnect_outlook,
    fetch_emails_for_contact, get_gmail_email_body, get_outlook_email_body
)

app = Flask(__name__)
app.secret_key = 'simple-crm-secret-key-change-in-production'


# Custom Jinja filter to handle dates (works with both strings and datetime objects)
@app.template_filter('format_date')
def format_date_filter(value, format='%Y-%m-%d'):
    """Format a date value, handling both strings and datetime objects."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value[:10] if len(value) >= 10 else value
    if hasattr(value, 'strftime'):
        return value.strftime(format)
    return str(value)

# Initialize database on startup
init_database()
init_fix_requests_table()  # Create fix_requests table if not exists
add_sales_notes_column()  # Add sales_notes column to contacts if not exists
add_contact_salesperson_column()  # Add salesperson_id column to contacts if not exists


# ============== Authentication ==============

def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        if session.get('user_role') != 'admin':
            return "Access denied. Admin only.", 403
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get the currently logged in user."""
    if 'user_id' in session:
        return get_user(session['user_id'])
    return None


@app.context_processor
def inject_user():
    """Make current user available in all templates."""
    return dict(current_user=get_current_user())


@app.context_processor
def inject_pending_fixes():
    """Make pending fixes available in all templates for the navbar."""
    try:
        fixes = get_all_fix_requests()
        pending = [f for f in fixes if f.get('status') == 'pending']
        return dict(pending_fixes=pending, pending_fixes_count=len(pending))
    except:
        return dict(pending_fixes=[], pending_fixes_count=0)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    # If no users exist, redirect to setup
    if get_user_count() == 0:
        return redirect(url_for('setup'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        result = authenticate_user(username, password)
        if result['success']:
            user = result['user']
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['username'] = user['username']

            # Redirect to 'next' parameter or dashboard
            next_url = request.args.get('next') or url_for('dashboard')
            return redirect(next_url)
        else:
            return render_template('login.html', error=result['error'])

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Initial setup - create first admin account."""
    # Only allow if no users exist
    if get_user_count() > 0:
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()

        # Validation
        if not username or not password:
            return render_template('setup.html', error="Username and password are required")
        if password != confirm_password:
            return render_template('setup.html', error="Passwords do not match")
        if len(password) < 6:
            return render_template('setup.html', error="Password must be at least 6 characters")

        # Create admin user
        result = add_user(username, password, email=email, first_name=first_name,
                         last_name=last_name, role='admin')

        if result['success']:
            # Auto-login
            session['user_id'] = result['id']
            session['user_role'] = 'admin'
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('setup.html', error=result['error'])

    return render_template('setup.html')


# CORS support for form submissions from external sites
@app.after_request
def add_cors_headers(response):
    """Add CORS headers for form submission endpoints."""
    # Only add CORS headers for the form submission endpoint
    if request.path == '/api/form/submit':
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ============== Web Dashboard Routes ==============

@app.route('/')
@login_required
def dashboard():
    """Main dashboard with analytics from DEALS, optionally filtered by date range."""
    # Get date filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    period = request.args.get('period')  # e.g., '2025', '2025-01', 'all'

    # Handle period shortcuts
    if period and period != 'all':
        if len(period) == 4:  # Year only, e.g., '2025'
            start_date = f"{period}-01-01"
            end_date = f"{period}-12-31"
        elif len(period) == 7:  # Year-month, e.g., '2025-01'
            start_date = f"{period}-01"
            # Calculate last day of month
            year, month = int(period[:4]), int(period[5:7])
            if month == 12:
                end_date = f"{period}-31"
            else:
                from datetime import date
                next_month = date(year, month + 1, 1)
                last_day = (next_month - __import__('datetime').timedelta(days=1)).day
                end_date = f"{period}-{last_day:02d}"

    # Use deal-centric analytics instead of contact-centric
    analytics = get_dashboard_analytics(start_date=start_date, end_date=end_date)
    comparison = get_deals_year_comparison()
    deals_by_month = get_deals_by_month_medium()
    untouched_leads = get_untouched_leads(limit=10)
    quick_notes = get_quick_notes(session.get('user_id', 1))
    return render_template('dashboard.html', analytics=analytics, comparison=comparison,
                          deals_by_month=deals_by_month, untouched_leads=untouched_leads,
                          quick_notes=quick_notes)


@app.route('/api/quick-notes', methods=['POST'])
@login_required
def api_save_quick_notes():
    """Save quick notes."""
    content = request.json.get('content', '')
    user_id = session.get('user_id', 1)
    save_quick_notes(content, user_id)
    return jsonify({'success': True})


@app.route('/contacts')
@login_required
def contacts_list():
    """View all contacts with pagination and sorting."""
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    sort_by = request.args.get('sort', 'created_at')
    sort_dir = request.args.get('dir', 'desc')

    # Validate per_page
    if per_page not in [25, 50, 100]:
        per_page = 25

    # Validate sort column
    valid_sorts = ['first_name', 'last_name', 'email', 'phone', 'utm_source', 'utm_medium',
                   'last_activity_date', 'created_at', 'deal_value']
    if sort_by not in valid_sorts:
        sort_by = 'created_at'

    # Validate sort direction
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'desc'

    if search_query:
        contacts = search_contacts(search_query)
        total_contacts = len(contacts)
        total_pages = 1
    else:
        total_contacts = get_contacts_count()
        total_pages = (total_contacts + per_page - 1) // per_page  # Ceiling division
        offset = (page - 1) * per_page
        contacts = get_all_contacts(limit=per_page, offset=offset, sort_by=sort_by, sort_dir=sort_dir)

    return render_template('contacts.html',
                           contacts=contacts,
                           search_query=search_query,
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_contacts=total_contacts,
                           sort_by=sort_by,
                           sort_dir=sort_dir)


@app.route('/contacts/<int:contact_id>')
@login_required
def contact_detail(contact_id):
    """View a single contact's details."""
    contact = get_contact(contact_id)
    if not contact:
        return "Contact not found", 404
    deals = get_deals_for_contact(contact_id)
    user_id = session.get('user_id')
    email_connected = is_gmail_connected(user_id) or is_outlook_connected(user_id)
    return render_template('contact_detail.html', contact=contact, deals=deals, email_connected=email_connected)


@app.route('/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def contact_edit(contact_id):
    """Edit a contact."""
    contact = get_contact(contact_id)
    if not contact:
        return "Contact not found", 404

    if request.method == 'POST':
        # Get company_id
        company_id = request.form.get('company_id')
        company_id = int(company_id) if company_id else None

        # Get salesperson_id
        salesperson_id = request.form.get('salesperson_id')
        salesperson_id = int(salesperson_id) if salesperson_id else None

        # Update contact with form data
        update_data = {
            'first_name': request.form.get('first_name'),
            'last_name': request.form.get('last_name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'company_id': company_id,
            'salesperson_id': salesperson_id,
            'utm_source': request.form.get('utm_source'),
            'utm_medium': request.form.get('utm_medium'),
            'utm_campaign': request.form.get('utm_campaign'),
            'utm_term': request.form.get('utm_term'),
            'utm_content': request.form.get('utm_content'),
            'original_source_details': request.form.get('original_source_details'),
            'deal_value': float(request.form.get('deal_value') or 0),
            'deal_closed_date': request.form.get('deal_closed_date') or None,
            'notes': request.form.get('notes'),
            'sales_notes': request.form.get('sales_notes'),
        }
        update_contact(contact_id, **update_data)
        return redirect(url_for('contact_detail', contact_id=contact_id))

    return render_template('contact_edit.html', contact=contact, companies=get_all_companies(), mediums=get_utm_mediums(), salespeople=get_salespeople())


@app.route('/contacts/<int:contact_id>/delete', methods=['POST'])
@login_required
def contact_delete(contact_id):
    """Delete a contact."""
    delete_contact(contact_id)
    return redirect(url_for('contacts_list'))


@app.route('/contacts/<int:contact_id>/reset-activity', methods=['POST'])
@login_required
def contact_reset_activity(contact_id):
    """Reset a contact's last_activity_date to None."""
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE contacts SET last_activity_date = NULL WHERE id = %s" if os.environ.get('DATABASE_URL') else "UPDATE contacts SET last_activity_date = NULL WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/contacts/add', methods=['GET', 'POST'])
@login_required
def contact_add():
    """Add a new contact (manual entry)."""
    if request.method == 'POST':
        result = add_contact(
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            utm_source=request.form.get('utm_source'),
            utm_medium=request.form.get('utm_medium'),
            utm_campaign=request.form.get('utm_campaign'),
            utm_term=request.form.get('utm_term'),
            utm_content=request.form.get('utm_content'),
            deal_value=float(request.form.get('deal_value') or 0),
            deal_closed_date=request.form.get('deal_closed_date') or None,
            notes=request.form.get('notes'),
        )
        if result['success']:
            return redirect(url_for('contact_detail', contact_id=result['id']))
        return render_template('contact_add.html', error=result['error'], mediums=get_utm_mediums())

    return render_template('contact_add.html', mediums=get_utm_mediums())


@app.route('/contacts/import', methods=['POST'])
@login_required
def import_contacts():
    """Import contacts from a CSV file."""
    import csv
    import io

    if 'csv_file' not in request.files:
        return redirect(url_for('contacts_list') + '?error=No+file+uploaded')

    file = request.files['csv_file']
    if file.filename == '':
        return redirect(url_for('contacts_list') + '?error=No+file+selected')

    if not file.filename.endswith('.csv'):
        return redirect(url_for('contacts_list') + '?error=Please+upload+a+CSV+file')

    try:
        # Read CSV file - try UTF-8 first, fall back to Windows encoding
        raw_data = file.stream.read()
        try:
            decoded = raw_data.decode("utf-8")
        except UnicodeDecodeError:
            decoded = raw_data.decode("cp1252")  # Windows/Excel encoding

        stream = io.StringIO(decoded, newline=None)
        reader = csv.DictReader(stream)

        imported = 0
        skipped = 0
        updated = 0

        # Build salesperson lookup dict (name -> id)
        salespeople_list = get_salespeople()
        salesperson_lookup = {}
        for sp in salespeople_list:
            salesperson_lookup[sp['name'].lower().strip()] = sp['id']
            # Also add first name only for matching
            if sp.get('first_name'):
                salesperson_lookup[sp['first_name'].lower().strip()] = sp['id']

        for row in reader:
            # Get values with flexible column names
            # First Name
            first_name = row.get('first_name', row.get('First Name', row.get('firstname', ''))).strip()
            # Last Name
            last_name = row.get('last_name', row.get('Last Name', row.get('lastname', ''))).strip()
            # Email - check multiple variations including "Email Address"
            email = row.get('email', row.get('Email', row.get('EMAIL',
                row.get('Email Address', row.get('email address',
                row.get('Address', row.get('address', ''))))))).strip()
            # Phone
            phone = row.get('phone', row.get('Phone', row.get('PHONE', ''))).strip()
            # notes = Customer Message
            customer_message = row.get('notes', row.get('Message', row.get('message', ''))).strip()
            # sales_notes = Sales Notes
            sales_notes = row.get('sales_notes', row.get('Notes', '')).strip()
            # Source
            utm_source = row.get('utm_source', row.get('source', row.get('Source', ''))).strip()
            # Medium
            utm_medium = row.get('utm_medium', row.get('medium', row.get('Medium', ''))).strip()
            # Owner -> Salesperson
            owner = row.get('Owner', row.get('owner', row.get('Salesperson', row.get('salesperson', '')))).strip()
            # created_at
            created_time = row.get('created_at', row.get('Time', row.get('time', ''))).strip()

            # Look up salesperson_id by name
            salesperson_id = None
            if owner:
                salesperson_id = salesperson_lookup.get(owner.lower().strip())

            # Skip if no email (required field)
            if not email:
                skipped += 1
                continue

            # Check if contact already exists
            existing = get_contact_by_email(email)
            if existing:
                # Update existing contact with new data (if fields are provided)
                update_data = {}
                if sales_notes:
                    update_data['sales_notes'] = sales_notes
                if salesperson_id:
                    update_data['salesperson_id'] = salesperson_id
                if customer_message and not existing.get('notes'):
                    update_data['notes'] = customer_message
                if update_data:
                    update_contact(existing['id'], **update_data)
                    updated += 1
                else:
                    skipped += 1
                continue

            # Add new contact
            result = add_contact(
                first_name=first_name or 'Unknown',
                last_name=last_name or '',
                email=email,
                phone=phone or None,
                notes=customer_message or None,  # notes -> Customer Message
                sales_notes=sales_notes or None,  # Notes -> Sales Notes
                utm_source=utm_source or None,
                utm_medium=utm_medium or None
            )

            if result.get('success'):
                # Update salesperson and created_at if we have them
                update_data = {}
                if salesperson_id:
                    update_data['salesperson_id'] = salesperson_id
                if created_time:
                    update_data['created_at'] = created_time
                if update_data:
                    update_contact(result['id'], **update_data)
                imported += 1
            else:
                skipped += 1

        message = f"Imported+{imported}+contacts"
        if updated > 0:
            message += f",+updated+{updated}"
        if skipped > 0:
            message += f"+({skipped}+skipped)"

        return redirect(url_for('contacts_list') + f'?success={message}')

    except Exception as e:
        return redirect(url_for('contacts_list') + f'?error=Import+failed:+{str(e)[:50]}')


# ============== Traffic Dashboard Routes ==============

@app.route('/traffic')
@login_required
def traffic_dashboard():
    """Traffic dashboard with website analytics from GA4."""
    from flask import session

    # Get date filter parameters
    period = request.args.get('period', '30d')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    website_id = request.args.get('website')

    # Calculate date range based on period
    if not start_date or not end_date:
        today = datetime.now()
        if period == '7d':
            start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        elif period == '30d':
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        elif period == '90d':
            start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
        elif period == 'ytd':
            start_date = f"{today.year}-01-01"
        else:
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    ga_connected = is_ga_connected()
    oauth_configured = is_oauth_configured()

    # Get list of websites and current selection
    websites = get_websites() if ga_connected else []
    current_website = None
    if website_id:
        current_website = get_website(website_id)
    if not current_website and websites:
        current_website = get_default_website()

    # Get traffic data (real or demo)
    phone_clicks = 0
    if ga_connected and current_website:
        website_id = current_website['id']
        traffic = fetch_traffic_by_channel(start_date, end_date, website_id)
        traffic_by_month = fetch_traffic_by_channel_and_month(website_id=website_id)
        phone_data = fetch_phone_clicks(start_date, end_date, website_id)
        if phone_data:
            phone_clicks = phone_data.get('phone_clicks', 0)
        if traffic is None or 'error' in traffic:
            traffic = get_demo_traffic_data()
            traffic['is_demo'] = True
            traffic['error_message'] = traffic.get('error', 'Could not fetch data')
        if traffic_by_month is None or 'error' in traffic_by_month:
            traffic_by_month = get_demo_traffic_by_month()
    else:
        traffic = get_demo_traffic_data()
        traffic_by_month = get_demo_traffic_by_month()

    # Get leads by month and medium from CRM data
    leads_by_month = get_leads_by_month_medium()

    return render_template('traffic.html',
                           traffic=traffic,
                           traffic_by_month=traffic_by_month,
                           leads_by_month=leads_by_month,
                           phone_clicks=phone_clicks,
                           ga_connected=ga_connected,
                           oauth_configured=oauth_configured,
                           websites=websites,
                           current_website=current_website,
                           period=period,
                           start_date=start_date,
                           end_date=end_date)


@app.route('/traffic/settings', methods=['GET', 'POST'])
@login_required
def traffic_settings():
    """Configure Google Analytics OAuth connection."""
    error = None
    success = None

    if request.method == 'POST':
        # Save OAuth client credentials
        client_id = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()

        if not client_id or not client_secret:
            error = "Both Client ID and Client Secret are required"
        else:
            save_oauth_secrets(client_id, client_secret)
            success = "OAuth credentials saved! Now click 'Connect with Google' to authorize."

    oauth_configured = is_oauth_configured()
    ga_connected = is_ga_connected()
    config = get_ga_config() if ga_connected else None
    oauth_secrets = get_oauth_secrets() if oauth_configured else None
    websites = get_websites() if ga_connected else []

    return render_template('traffic_settings.html',
                           oauth_configured=oauth_configured,
                           ga_connected=ga_connected,
                           config=config,
                           oauth_secrets=oauth_secrets,
                           websites=websites,
                           error=error,
                           success=success)


@app.route('/traffic/oauth/authorize')
@login_required
def traffic_oauth_authorize():
    """Start OAuth flow - redirect to Google login."""
    if not is_oauth_configured():
        return redirect(url_for('traffic_settings'))

    # Build redirect URI dynamically for local vs Railway
    railway_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if railway_url:
        redirect_uri = f"https://{railway_url}/traffic/oauth/callback"
    else:
        redirect_uri = 'http://localhost:5000/traffic/oauth/callback'

    flow = get_oauth_flow(redirect_uri=redirect_uri)
    if not flow:
        return "OAuth not configured", 400

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='select_account consent'
    )

    # Store state in session for verification
    from flask import session
    session['oauth_state'] = state

    return redirect(authorization_url)


@app.route('/traffic/oauth/callback')
@login_required
def traffic_oauth_callback():
    """Handle OAuth callback from Google."""
    from flask import session

    if not is_oauth_configured():
        return redirect(url_for('traffic_settings'))

    # Build redirect URI dynamically for local vs Railway
    railway_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if railway_url:
        redirect_uri = f"https://{railway_url}/traffic/oauth/callback"
    else:
        redirect_uri = 'http://localhost:5000/traffic/oauth/callback'

    flow = get_oauth_flow(redirect_uri=redirect_uri)
    if not flow:
        return "OAuth not configured", 400

    # Get the authorization response - fix HTTP to HTTPS for Railway
    auth_response = request.url
    if railway_url and auth_response.startswith('http://'):
        auth_response = auth_response.replace('http://', 'https://', 1)

    flow.fetch_token(authorization_response=auth_response)

    # Save the credentials
    credentials = flow.credentials
    save_oauth_token(credentials)

    # Redirect to property selection
    return redirect(url_for('traffic_select_property'))


@app.route('/traffic/select-property', methods=['GET', 'POST'])
@login_required
def traffic_select_property():
    """Select which GA4 property to use."""
    if not is_oauth_configured():
        return redirect(url_for('traffic_settings'))

    error = None

    if request.method == 'POST':
        property_id = request.form.get('property_id', '').strip()
        if property_id:
            save_ga_config(property_id)
            return redirect(url_for('traffic_dashboard'))
        else:
            error = "Please enter a Property ID"

    # For now, just show a form to enter property ID manually
    # (fetching properties list requires additional API setup)
    return render_template('traffic_select_property.html', error=error)


@app.route('/traffic/disconnect', methods=['POST'])
@login_required
def traffic_disconnect():
    """Disconnect Google Analytics."""
    disconnect_ga()
    return redirect(url_for('traffic_settings'))


@app.route('/traffic/websites/add', methods=['POST'])
@login_required
def traffic_add_website():
    """Add a new website to track."""
    name = request.form.get('name', '').strip()
    property_id = request.form.get('property_id', '').strip()

    if name and property_id:
        add_website(name, property_id)

    return redirect(url_for('traffic_settings'))


@app.route('/traffic/websites/<website_id>/remove', methods=['POST'])
@login_required
def traffic_remove_website(website_id):
    """Remove a website from tracking."""
    remove_website(website_id)
    return redirect(url_for('traffic_settings'))


@app.route('/traffic/test')
@login_required
def traffic_test():
    """Test GA4 connection."""
    if not is_ga_connected():
        return jsonify({'error': 'Google Analytics not connected'}), 400

    traffic = fetch_traffic_by_channel()
    if traffic and 'error' not in traffic:
        return jsonify({'success': True, 'data': traffic})
    else:
        return jsonify({'success': False, 'error': traffic.get('error', 'Unknown error')}), 500


# ============== Email Settings Routes ==============

@app.route('/settings/email')
@login_required
def email_settings():
    """Email integration settings page."""
    user_id = session.get('user_id')
    email_status = get_email_status(user_id)
    gmail_auth_url = get_gmail_auth_url() if is_gmail_configured() else None
    outlook_auth_url = get_outlook_auth_url() if is_outlook_configured() else None

    return render_template('email_settings.html',
                          email_status=email_status,
                          gmail_auth_url=gmail_auth_url,
                          outlook_auth_url=outlook_auth_url,
                          message=request.args.get('message'),
                          message_type=request.args.get('message_type', 'info'))


@app.route('/settings/email/gmail/callback')
@login_required
def gmail_oauth_callback_route():
    """Handle Gmail OAuth callback."""
    user_id = session.get('user_id')
    result = gmail_oauth_callback(user_id, request.url)
    if result['success']:
        return redirect(url_for('email_settings', message='Gmail connected successfully!', message_type='success'))
    else:
        return redirect(url_for('email_settings', message=f"Gmail connection failed: {result.get('error')}", message_type='error'))


@app.route('/settings/email/gmail/disconnect', methods=['POST'])
@login_required
def gmail_disconnect_route():
    """Disconnect Gmail."""
    user_id = session.get('user_id')
    disconnect_gmail(user_id)
    return redirect(url_for('email_settings', message='Gmail disconnected', message_type='success'))


@app.route('/settings/email/outlook/configure', methods=['POST'])
@login_required
def outlook_configure_route():
    """Save Outlook OAuth configuration and redirect to auth."""
    client_id = request.form.get('client_id')
    client_secret = request.form.get('client_secret')
    tenant_id = request.form.get('tenant_id') or 'common'

    if not client_id or not client_secret:
        return redirect(url_for('email_settings', message='Client ID and Secret are required', message_type='error'))

    save_outlook_config(client_id, client_secret, tenant_id)
    auth_url = get_outlook_auth_url()

    if auth_url:
        return redirect(auth_url)
    else:
        return redirect(url_for('email_settings', message='Failed to generate auth URL', message_type='error'))


@app.route('/settings/email/outlook/callback')
@login_required
def outlook_oauth_callback_route():
    """Handle Outlook OAuth callback."""
    code = request.args.get('code')
    if not code:
        return redirect(url_for('email_settings', message='No authorization code received', message_type='error'))

    user_id = session.get('user_id')
    result = outlook_oauth_callback(user_id, code)
    if result['success']:
        return redirect(url_for('email_settings', message='Outlook connected successfully!', message_type='success'))
    else:
        return redirect(url_for('email_settings', message=f"Outlook connection failed: {result.get('error')}", message_type='error'))


@app.route('/settings/email/outlook/disconnect', methods=['POST'])
@login_required
def outlook_disconnect_route():
    """Disconnect Outlook."""
    user_id = session.get('user_id')
    disconnect_outlook(user_id)
    return redirect(url_for('email_settings', message='Outlook disconnected', message_type='success'))


@app.route('/api/emails/<email_address>')
@login_required
def api_get_emails(email_address):
    """Fetch emails for a contact's email address using logged-in user's email connection."""
    user_id = session.get('user_id')
    max_results = request.args.get('max_results', 20, type=int)
    result = fetch_emails_for_contact(user_id, email_address, max_results=max_results)
    return jsonify(result)


@app.route('/api/emails/<source>/<email_id>')
@login_required
def api_get_email_body(source, email_id):
    """Fetch the full body of a single email by source (gmail/outlook) and ID."""
    user_id = session.get('user_id')

    if source == 'gmail':
        result = get_gmail_email_body(user_id, email_id)
    elif source == 'outlook':
        result = get_outlook_email_body(user_id, email_id)
    else:
        return jsonify({"success": False, "error": "Invalid email source"}), 400

    return jsonify(result)


# ============== User Management Routes ==============

@app.route('/settings/users')
@login_required
@admin_required
def user_management():
    """User management page (admin only)."""
    users = get_all_users()
    return render_template('users.html', users=users)


@app.route('/settings/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def user_add():
    """Add a new user."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role = request.form.get('role', 'salesperson')

        if not username or not password:
            return render_template('user_form.html', error="Username and password are required", user=None)

        if len(password) < 6:
            return render_template('user_form.html', error="Password must be at least 6 characters", user=None)

        result = add_user(username, password, email=email, first_name=first_name,
                         last_name=last_name, role=role)

        if result['success']:
            return redirect(url_for('user_management'))
        else:
            return render_template('user_form.html', error=result['error'], user=None)

    return render_template('user_form.html', user=None)


@app.route('/settings/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def user_edit(user_id):
    """Edit a user."""
    user = get_user(user_id)
    if not user:
        return "User not found", 404

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role = request.form.get('role', 'salesperson')
        is_active = request.form.get('is_active') == 'on'
        new_password = request.form.get('password', '').strip()

        update_data = {
            'email': email or None,
            'first_name': first_name or None,
            'last_name': last_name or None,
            'role': role,
            'is_active': 1 if is_active else 0
        }

        if new_password:
            if len(new_password) < 6:
                return render_template('user_form.html', error="Password must be at least 6 characters", user=user)
            update_data['password'] = new_password

        update_user(user_id, **update_data)
        return redirect(url_for('user_management'))

    return render_template('user_form.html', user=user)


@app.route('/settings/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def user_delete(user_id):
    """Delete a user."""
    # Prevent deleting yourself
    if session.get('user_id') == user_id:
        return redirect(url_for('user_management'))

    delete_user(user_id)
    return redirect(url_for('user_management'))


# ============== Deals Routes ==============

@app.route('/deals')
@login_required
def deals_pipeline():
    """Deals pipeline view with kanban board."""
    # Get filters from query params
    salesperson_filter = request.args.get('salesperson', '')
    stage_filter = request.args.get('stage', '')
    search_query = request.args.get('search', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    # Get pipeline data, optionally filtered
    pipeline = get_deals_by_stage(
        salesperson=salesperson_filter if salesperson_filter else None,
        stage_filter=stage_filter if stage_filter else None,
        search=search_query if search_query else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None
    )

    # Get analytics with same filters applied
    analytics = get_deal_analytics(
        salesperson=salesperson_filter if salesperson_filter else None,
        stage_filter=stage_filter if stage_filter else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None
    )
    salespeople = get_salespeople()

    return render_template('deals.html',
                           pipeline=pipeline,
                           stages=DEAL_STAGES,
                           analytics=analytics,
                           salespeople=salespeople,
                           current_salesperson=salesperson_filter,
                           current_stage=stage_filter,
                           search_query=search_query,
                           date_from=date_from,
                           date_to=date_to)


@app.route('/deals/add', methods=['GET', 'POST'])
@login_required
def deal_add():
    """Add a new deal."""
    if request.method == 'POST':
        # Get contact_id - either from existing contact or create new one
        contact_id = request.form.get('contact_id') or None

        # Check if new contact fields are filled in (and no existing contact selected)
        if not contact_id:
            new_first_name = request.form.get('new_contact_first_name', '').strip()
            new_last_name = request.form.get('new_contact_last_name', '').strip()
            new_email = request.form.get('new_contact_email', '').strip()
            new_phone = request.form.get('new_contact_phone', '').strip()

            # If at least first name and email are provided, create new contact
            if new_first_name and new_email:
                # Check if contact already exists with this email
                existing = get_contact_by_email(new_email)
                if existing:
                    contact_id = existing['id']
                else:
                    contact_result = add_contact(
                        first_name=new_first_name,
                        last_name=new_last_name,
                        email=new_email,
                        phone=new_phone
                    )
                    if contact_result['success']:
                        contact_id = contact_result['id']

        # Get company_id
        company_id = request.form.get('company_id')
        company_id = int(company_id) if company_id else None

        result = add_deal(
            name=request.form.get('name'),
            value=float(request.form.get('value') or 0),
            stage=request.form.get('stage', 'new_deal'),
            salesperson=request.form.get('salesperson') or None,
            utm_source=request.form.get('utm_source') or None,
            utm_medium=request.form.get('utm_medium') or None,
            utm_campaign=request.form.get('utm_campaign') or None,
            expected_close_date=request.form.get('expected_close_date') or None,
            notes=request.form.get('notes') or None,
            contact_id=contact_id,
            company_id=company_id
        )
        if result['success']:
            return redirect(url_for('deal_detail', deal_id=result['id']))
        return render_template('deal_add.html', error=result['error'], contacts=get_all_contacts(), salespeople=get_salespeople(), companies=get_all_companies())

    contacts = get_all_contacts()
    salespeople = get_salespeople()
    companies = get_all_companies()
    return render_template('deal_add.html', contacts=contacts, salespeople=salespeople, companies=companies)


@app.route('/deals/<int:deal_id>')
@login_required
def deal_detail(deal_id):
    """View a single deal's details."""
    deal = get_deal(deal_id)
    if not deal:
        return "Deal not found", 404
    all_contacts = get_all_contacts(limit=1000)  # Get more contacts for search
    return render_template('deal_detail.html', deal=deal, all_contacts=all_contacts)


@app.route('/deals/<int:deal_id>/edit', methods=['GET', 'POST'])
@login_required
def deal_edit(deal_id):
    """Edit a deal."""
    deal = get_deal(deal_id)
    if not deal:
        return "Deal not found", 404

    if request.method == 'POST':
        # Get company_id
        company_id = request.form.get('company_id')
        company_id = int(company_id) if company_id else None

        update_deal(
            deal_id,
            name=request.form.get('name'),
            value=float(request.form.get('value') or 0),
            stage=request.form.get('stage'),
            salesperson=request.form.get('salesperson') or None,
            utm_source=request.form.get('utm_source') or None,
            utm_medium=request.form.get('utm_medium') or None,
            utm_campaign=request.form.get('utm_campaign') or None,
            expected_close_date=request.form.get('expected_close_date') or None,
            actual_close_date=request.form.get('actual_close_date') or None,
            notes=request.form.get('notes') or None,
            company_id=company_id
        )
        return redirect(url_for('deal_detail', deal_id=deal_id))

    return render_template('deal_add.html', deal=deal, contacts=get_all_contacts(), salespeople=get_salespeople(), companies=get_all_companies())


@app.route('/deals/<int:deal_id>/stage', methods=['POST'])
@login_required
def deal_update_stage(deal_id):
    """Update deal stage (from detail page buttons)."""
    new_stage = request.form.get('stage')
    update_deal_stage(deal_id, new_stage)
    return redirect(url_for('deal_detail', deal_id=deal_id))


@app.route('/deals/<int:deal_id>/delete', methods=['POST'])
@login_required
def deal_delete(deal_id):
    """Delete a deal."""
    delete_deal(deal_id)
    return redirect(url_for('deals_pipeline'))


@app.route('/deals/<int:deal_id>/reason', methods=['POST'])
@login_required
def deal_update_reason(deal_id):
    """Update the win/loss reason for a deal."""
    close_reason = request.form.get('close_reason', '').strip()
    update_deal(deal_id, close_reason=close_reason if close_reason else None)
    return redirect(url_for('deal_detail', deal_id=deal_id))


@app.route('/deals/<int:deal_id>/reported-source', methods=['POST'])
@login_required
def deal_update_reported_source(deal_id):
    """Update the reported source (what salesperson records from customer)."""
    reported_source = request.form.get('reported_source', '').strip()
    update_deal(deal_id, reported_source=reported_source if reported_source else None)
    return redirect(url_for('deal_detail', deal_id=deal_id))


@app.route('/deals/<int:deal_id>/source', methods=['POST'])
@login_required
def deal_update_source(deal_id):
    """Update the verified lead source (utm_medium) for a deal."""
    utm_medium = request.form.get('utm_medium', '').strip()
    update_deal(deal_id, utm_medium=utm_medium if utm_medium else None)
    return redirect(url_for('deal_detail', deal_id=deal_id))


@app.route('/deals/<int:deal_id>/contacts/add', methods=['POST'])
@login_required
def deal_add_contact(deal_id):
    """Add a contact to a deal."""
    contact_id = request.form.get('contact_id')
    if contact_id:
        add_contact_to_deal(deal_id, int(contact_id))
    return redirect(url_for('deal_detail', deal_id=deal_id))


@app.route('/deals/<int:deal_id>/contacts/<int:contact_id>/remove', methods=['POST'])
@login_required
def deal_remove_contact(deal_id, contact_id):
    """Remove a contact from a deal."""
    remove_contact_from_deal(deal_id, contact_id)
    return redirect(url_for('deal_detail', deal_id=deal_id))


# ============== Salespeople Routes ==============

@app.route('/salespeople')
@login_required
def salespeople_list():
    """View all salespeople."""
    salespeople = get_salespeople()
    return render_template('salespeople.html', salespeople=salespeople)


@app.route('/salespeople/add', methods=['GET', 'POST'])
@login_required
def salesperson_add():
    """Add a new salesperson."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            # Auto-generate name from first/last
            first = request.form.get('first_name', '').strip()
            last = request.form.get('last_name', '').strip()
            name = f"{first} {last}".strip()

        result = add_salesperson(
            name=name,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone')
        )
        if result['success']:
            return redirect(url_for('salespeople_list'))
        return render_template('salesperson_form.html', error=result['error'])

    return render_template('salesperson_form.html')


@app.route('/salespeople/<int:salesperson_id>/edit', methods=['GET', 'POST'])
@login_required
def salesperson_edit(salesperson_id):
    """Edit a salesperson."""
    sp = get_salesperson(salesperson_id)
    if not sp:
        return "Salesperson not found", 404

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            first = request.form.get('first_name', '').strip()
            last = request.form.get('last_name', '').strip()
            name = f"{first} {last}".strip()

        result = update_salesperson(
            salesperson_id,
            name=name,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone')
        )
        if result['success']:
            return redirect(url_for('salespeople_list'))
        return render_template('salesperson_form.html', salesperson=sp, error=result['error'])

    return render_template('salesperson_form.html', salesperson=sp)


@app.route('/salespeople/<int:salesperson_id>/delete', methods=['POST'])
@login_required
def salesperson_delete(salesperson_id):
    """Delete a salesperson."""
    delete_salesperson(salesperson_id)
    return redirect(url_for('salespeople_list'))


# ============== Products Routes ==============

@app.route('/products')
@login_required
def products_list():
    """View all products."""
    search_query = request.args.get('search', '')
    if search_query:
        products = search_products(search_query)
    else:
        products = get_all_products()
    return render_template('products.html', products=products, search_query=search_query)


@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def product_add():
    """Add a new product."""
    if request.method == 'POST':
        result = add_product(
            name=request.form.get('name'),
            sku=request.form.get('sku') or None,
            description=request.form.get('description') or None,
            price=float(request.form.get('price') or 0)
        )
        if result['success']:
            return redirect(url_for('products_list'))
        return render_template('product_form.html', error=result['error'])

    return render_template('product_form.html')


@app.route('/products/<int:product_id>')
@login_required
def product_detail(product_id):
    """View a single product's details."""
    product = get_product(product_id)
    if not product:
        return "Product not found", 404
    return render_template('product_detail.html', product=product)


@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def product_edit(product_id):
    """Edit a product."""
    product = get_product(product_id)
    if not product:
        return "Product not found", 404

    if request.method == 'POST':
        result = update_product(
            product_id,
            name=request.form.get('name'),
            sku=request.form.get('sku') or None,
            description=request.form.get('description') or None,
            price=float(request.form.get('price') or 0)
        )
        if result['success']:
            return redirect(url_for('products_list'))
        return render_template('product_form.html', product=product, error=result['error'])

    return render_template('product_form.html', product=product)


@app.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
def product_delete(product_id):
    """Delete a product."""
    delete_product(product_id)
    return redirect(url_for('products_list'))


# ============== Companies Routes ==============

@app.route('/companies')
@login_required
def companies_list():
    """View all companies."""
    search_query = request.args.get('search', '')
    if search_query:
        companies = search_companies(search_query)
    else:
        companies = get_all_companies()
    return render_template('companies.html', companies=companies, search_query=search_query)


@app.route('/companies/add', methods=['GET', 'POST'])
@login_required
def company_add():
    """Add a new company."""
    if request.method == 'POST':
        result = add_company(
            name=request.form.get('name'),
            phone=request.form.get('phone') or None,
            email=request.form.get('email') or None,
            website=request.form.get('website') or None,
            address=request.form.get('address') or None,
            city=request.form.get('city') or None,
            state=request.form.get('state') or None,
            zip_code=request.form.get('zip') or None,
            notes=request.form.get('notes') or None
        )
        if result['success']:
            return redirect(url_for('company_detail', company_id=result['id']))
        return render_template('company_form.html', error=result['error'])

    return render_template('company_form.html')


@app.route('/companies/<int:company_id>')
@login_required
def company_detail(company_id):
    """View a company's details with related deals, quotes, and contacts."""
    company = get_company(company_id)
    if not company:
        return "Company not found", 404
    deals = get_company_deals(company_id)
    quotes = get_company_quotes(company_id)
    contacts = get_company_contacts(company_id)
    return render_template('company_detail.html', company=company, deals=deals, quotes=quotes, contacts=contacts)


@app.route('/companies/<int:company_id>/edit', methods=['GET', 'POST'])
@login_required
def company_edit(company_id):
    """Edit a company."""
    company = get_company(company_id)
    if not company:
        return "Company not found", 404

    if request.method == 'POST':
        result = update_company(
            company_id,
            name=request.form.get('name'),
            phone=request.form.get('phone') or None,
            email=request.form.get('email') or None,
            website=request.form.get('website') or None,
            address=request.form.get('address') or None,
            city=request.form.get('city') or None,
            state=request.form.get('state') or None,
            zip_code=request.form.get('zip') or None,
            notes=request.form.get('notes') or None
        )
        if result['success']:
            return redirect(url_for('company_detail', company_id=company_id))
        return render_template('company_form.html', company=company, error=result['error'])

    return render_template('company_form.html', company=company)


@app.route('/companies/<int:company_id>/delete', methods=['POST'])
@login_required
def company_delete(company_id):
    """Delete a company."""
    delete_company(company_id)
    return redirect(url_for('companies_list'))


@app.route('/api/companies', methods=['GET'])
@login_required
def api_get_companies():
    """API: Get all companies."""
    search_query = request.args.get('search', '')
    if search_query:
        companies = search_companies(search_query)
    else:
        companies = get_all_companies()
    return jsonify(companies)


@app.route('/api/companies', methods=['POST'])
@login_required
def api_add_company():
    """API: Add a new company."""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'error': 'Name is required'}), 400

    result = add_company(
        name=data['name'],
        phone=data.get('phone'),
        email=data.get('email'),
        website=data.get('website'),
        address=data.get('address'),
        city=data.get('city'),
        state=data.get('state'),
        zip_code=data.get('zip'),
        notes=data.get('notes')
    )
    if result['success']:
        return jsonify(result), 201
    return jsonify(result), 400


# ============== Quotes Routes ==============

@app.route('/quotes')
@login_required
def quotes_list():
    """View all quotes with optional status and salesperson filters."""
    status_filter = request.args.get('status', '')
    salesperson_filter = request.args.get('salesperson', '')

    quotes = get_all_quotes(status=status_filter if status_filter else None,
                           salesperson_id=int(salesperson_filter) if salesperson_filter else None)
    # Ensure customer_name is never None for groupby sorting
    for quote in quotes:
        if quote.get('customer_name') is None:
            quote['customer_name'] = ''
    salespeople = get_salespeople()

    return render_template('quotes.html', quotes=quotes, statuses=QUOTE_STATUSES,
                          current_status=status_filter, salespeople=salespeople,
                          current_salesperson=salesperson_filter)


@app.route('/quotes/add', methods=['GET', 'POST'])
@login_required
def quote_add():
    """Create a new quote. Automatically creates a deal unless one is already linked."""
    if request.method == 'POST':
        # Get salesperson_id and look up their info
        salesperson_id = request.form.get('salesperson_id')
        if salesperson_id:
            salesperson_id = int(salesperson_id)

        # Check if deal_id is provided (coming from existing deal)
        deal_id = request.form.get('deal_id')
        auto_create_deal = not deal_id  # Only auto-create if no deal provided

        # Handle company - either existing or new
        company_id = request.form.get('company_id')
        new_company_name = request.form.get('new_company_name', '').strip()

        # If new company name provided, create the company first
        if new_company_name and not company_id:
            company_result = add_company(name=new_company_name)
            if company_result['success']:
                company_id = company_result['id']

        # Get customer info from form - now with separate first/last name
        contact_id = request.form.get('contact_id') or None
        customer_first_name = request.form.get('customer_first_name', '').strip()
        customer_last_name = request.form.get('customer_last_name', '').strip()
        customer_email = request.form.get('customer_email') or None
        customer_phone = request.form.get('customer_phone') or None

        # Combine first/last into full name for quote display
        customer_name = f"{customer_first_name} {customer_last_name}".strip() or None

        # Get UTM source info (needed for both contact and deal)
        utm_source = request.form.get('utm_source', '').strip() or None
        utm_medium = request.form.get('utm_medium', '').strip() or None
        utm_campaign = request.form.get('utm_campaign', '').strip() or None

        # Auto-create contact if customer info provided but no existing contact selected
        if customer_email and not contact_id:
            # Check if contact already exists with this email
            existing_contact = get_contact_by_email(customer_email)
            if existing_contact:
                contact_id = existing_contact['id']
                # Update existing contact with UTM data if they don't have it
                if utm_source or utm_medium or utm_campaign:
                    update_contact(contact_id,
                        utm_source=utm_source if utm_source else existing_contact.get('utm_source'),
                        utm_medium=utm_medium if utm_medium else existing_contact.get('utm_medium'),
                        utm_campaign=utm_campaign if utm_campaign else existing_contact.get('utm_campaign')
                    )
            else:
                # Create new contact with separate first/last name AND UTM data
                contact_result = add_contact(
                    first_name=customer_first_name,
                    last_name=customer_last_name,
                    email=customer_email,
                    phone=customer_phone,
                    utm_source=utm_source,
                    utm_medium=utm_medium,
                    utm_campaign=utm_campaign
                )
                if contact_result['success']:
                    contact_id = contact_result['id']
                    # Link contact to company if we have one
                    if company_id:
                        update_contact(contact_id, company_id=int(company_id))

        # Get reported source (what customer said when asked "how did you hear about us?")
        reported_source = request.form.get('reported_source', '').strip() or None

        result = add_quote(
            title=request.form.get('title'),
            salesperson_id=salesperson_id,
            deal_id=int(deal_id) if deal_id else None,
            company_id=int(company_id) if company_id else None,
            contact_id=contact_id,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_company=new_company_name if new_company_name else None,
            quote_date=request.form.get('quote_date') or None,
            expiry_date=request.form.get('expiry_date') or None,
            notes=request.form.get('notes') or None,
            terms=request.form.get('terms') or None,
            discount_percent=float(request.form.get('discount_percent') or 0),
            tax_percent=float(request.form.get('tax_percent') or 0),
            auto_create_deal=not deal_id,  # Auto-create deal if none provided
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            reported_source=reported_source
        )
        if result['success']:
            return redirect(url_for('quote_edit', quote_id=result['id']))
        return render_template('quote_form.html', error=result['error'],
                             salespeople=get_salespeople(), contacts=get_all_contacts(limit=5000),
                             companies=get_all_companies(), products=get_all_products())

    # GET - show empty form
    salespeople = get_salespeople()
    contacts = get_all_contacts(limit=5000)  # Load more contacts for search
    companies = get_all_companies()
    products = get_all_products()

    # Pre-fill from deal if deal_id provided (coming from deal detail page)
    deal_id = request.args.get('deal_id')
    prefill = {}
    if deal_id:
        deal = get_deal(int(deal_id))
        if deal:
            prefill['deal_id'] = deal_id
            prefill['title'] = f"Quote for {deal['name']}"
            prefill['from_existing_deal'] = True  # Flag to show different message
            if deal.get('contacts') and len(deal['contacts']) > 0:
                contact = deal['contacts'][0]
                prefill['contact_id'] = contact['id']
                prefill['customer_name'] = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
                prefill['customer_email'] = contact.get('email')
                prefill['customer_phone'] = contact.get('phone')

    return render_template('quote_form.html', salespeople=salespeople, contacts=contacts,
                          companies=companies, products=products, prefill=prefill)


@app.route('/quotes/<int:quote_id>')
@login_required
def quote_detail(quote_id):
    """View a quote's details."""
    quote = get_quote(quote_id)
    if not quote:
        return "Quote not found", 404
    return render_template('quote_detail.html', quote=quote, statuses=QUOTE_STATUSES)


@app.route('/quotes/<int:quote_id>/edit', methods=['GET', 'POST'])
@login_required
def quote_edit(quote_id):
    """Edit a quote and its line items."""
    quote = get_quote(quote_id)
    if not quote:
        return "Quote not found", 404

    if request.method == 'POST':
        # Update quote info
        salesperson_id = request.form.get('salesperson_id')
        salesperson_name = None
        salesperson_email = None
        salesperson_phone = None
        if salesperson_id:
            sp = get_salesperson(int(salesperson_id))
            if sp:
                salesperson_name = sp.get('name')
                salesperson_email = sp.get('email')
                salesperson_phone = sp.get('phone')

        update_quote(
            quote_id,
            title=request.form.get('title'),
            status='sent',  # Auto-update status to "sent" when saving
            salesperson_id=int(salesperson_id) if salesperson_id else None,
            salesperson_name=salesperson_name,
            salesperson_email=salesperson_email,
            salesperson_phone=salesperson_phone,
            customer_name=request.form.get('customer_name') or None,
            customer_email=request.form.get('customer_email') or None,
            customer_phone=request.form.get('customer_phone') or None,
            customer_company=request.form.get('customer_company') or None,
            quote_date=request.form.get('quote_date') or None,
            expiry_date=request.form.get('expiry_date') or None,
            notes=request.form.get('notes') or None,
            terms=request.form.get('terms') or None,
            discount_percent=float(request.form.get('discount_percent') or 0),
            tax_percent=float(request.form.get('tax_percent') or 0)
        )

        # Recalculate totals in case discount/tax changed
        recalculate_quote_totals(quote_id)

        # Create deal if quote doesn't have one yet (deal created on first save)
        quote = get_quote(quote_id)
        if not quote.get('deal_id'):
            # Create the deal now
            customer_company = request.form.get('customer_company') or quote.get('customer_company')
            deal_name = customer_company if customer_company else quote.get('title')
            deal_result = add_deal(
                name=deal_name,
                value=quote.get('total', 0),
                stage='new_deal',
                salesperson=salesperson_name,
                contact_id=quote.get('contact_id'),
                company_id=quote.get('company_id')
            )
            if deal_result.get('success'):
                # Link the deal to the quote
                update_quote(quote_id, deal_id=deal_result['id'])

        # Check if user wants to download PDF after saving
        if request.form.get('action') == 'save_and_pdf':
            return redirect(url_for('quote_pdf', quote_id=quote_id))

        # Reload quote
        quote = get_quote(quote_id)

    salespeople = get_salespeople()
    contacts = get_all_contacts()
    deals = get_all_deals()
    products = get_all_products()
    return render_template('quote_edit.html', quote=quote, salespeople=salespeople,
                          contacts=contacts, deals=deals, products=products, statuses=QUOTE_STATUSES)


@app.route('/quotes/<int:quote_id>/status', methods=['POST'])
@login_required
def quote_update_status(quote_id):
    """Update quote status."""
    new_status = request.form.get('status')
    if new_status in QUOTE_STATUSES:
        # If marking as paid, set payment date
        if new_status == 'paid':
            update_quote(quote_id, status=new_status, payment_date=datetime.now().strftime('%Y-%m-%d'))
        else:
            update_quote(quote_id, status=new_status)
    return redirect(url_for('quote_detail', quote_id=quote_id))


@app.route('/quotes/<int:quote_id>/payment-link', methods=['POST'])
@login_required
def quote_add_payment_link(quote_id):
    """Add payment link to quote."""
    payment_link = request.form.get('payment_link', '').strip()
    if payment_link:
        update_quote(quote_id, payment_link=payment_link)
    return redirect(url_for('quote_edit', quote_id=quote_id))


@app.route('/quotes/<int:quote_id>/financing-link', methods=['POST'])
@login_required
def quote_add_financing_link(quote_id):
    """Add financing link to quote."""
    financing_link = request.form.get('financing_link', '').strip()
    if financing_link:
        update_quote(quote_id, financing_link=financing_link)
    return redirect(url_for('quote_edit', quote_id=quote_id))


@app.route('/quotes/<int:quote_id>/delete', methods=['POST'])
@login_required
def quote_delete(quote_id):
    """Delete a quote."""
    delete_quote(quote_id)
    return redirect(url_for('quotes_list'))


@app.route('/quotes/<int:quote_id>/items/add', methods=['POST'])
@login_required
def quote_add_item(quote_id):
    """Add a line item to a quote."""
    product_id = request.form.get('product_id')
    add_quote_item(
        quote_id=quote_id,
        product_id=int(product_id) if product_id else None,
        product_name=request.form.get('product_name') or None,
        product_sku=request.form.get('product_sku') or None,
        description=request.form.get('description') or None,
        quantity=float(request.form.get('quantity') or 1),
        unit_price=float(request.form.get('unit_price') or 0),
        discount_percent=float(request.form.get('item_discount') or 0)
    )
    return redirect(url_for('quote_edit', quote_id=quote_id, _anchor='products'))


@app.route('/quotes/<int:quote_id>/items/<int:item_id>/update', methods=['POST'])
@login_required
def quote_update_item(quote_id, item_id):
    """Update a quote line item."""
    update_quote_item(
        item_id,
        quantity=float(request.form.get('quantity') or 1),
        unit_price=float(request.form.get('unit_price') or 0),
        discount_percent=float(request.form.get('item_discount') or 0)
    )
    return redirect(url_for('quote_edit', quote_id=quote_id, _anchor='products'))


@app.route('/quotes/<int:quote_id>/items/<int:item_id>/delete', methods=['POST'])
@login_required
def quote_delete_item(quote_id, item_id):
    """Delete a quote line item."""
    delete_quote_item(item_id)
    return redirect(url_for('quote_edit', quote_id=quote_id, _anchor='products'))


@app.route('/quotes/<int:quote_id>/pdf')
def quote_pdf(quote_id):
    """Generate and download a PDF of the quote."""
    quote = get_quote(quote_id)
    if not quote:
        return "Quote not found", 404

    # Debug: Print payment_link to console
    print(f"DEBUG PDF - Quote ID: {quote_id}")
    print(f"DEBUG PDF - Payment Link: {quote.get('payment_link', 'NOT FOUND')}")

    # Generate PDF
    pdf_buffer = generate_quote_pdf(quote, quote.get('line_items', []))

    # Create filename from quote number and customer
    customer_name = quote.get('customer_name') or quote.get('customer_company') or 'Customer'
    safe_name = "".join(c for c in customer_name if c.isalnum() or c in (' ', '-', '_')).strip()
    filename = f"STEELSTACK_{safe_name}_{quote.get('quote_number', 'Quote')}.pdf"

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


# ============== Shipping Calculator API ==============

@app.route('/api/shipping/calculate', methods=['GET', 'POST'])
@login_required
def api_calculate_shipping():
    """Calculate shipping cost between two ZIP codes."""
    if request.method == 'POST':
        data = request.get_json() or {}
        origin_zip = data.get('origin_zip', DEFAULT_ORIGIN_ZIP)
        destination_zip = data.get('destination_zip', '')
        rate = float(data.get('rate_per_mile', RATE_PER_MILE))
    else:
        origin_zip = request.args.get('origin_zip', DEFAULT_ORIGIN_ZIP)
        destination_zip = request.args.get('destination_zip', '')
        rate = float(request.args.get('rate_per_mile', RATE_PER_MILE))

    if not destination_zip:
        return jsonify({'success': False, 'error': 'Destination ZIP code is required'})

    result = calculate_shipping_cost(origin_zip, destination_zip, rate)
    return jsonify(result)


# ============== API Routes (for integration) ==============

@app.route('/api/contacts', methods=['GET'])
@login_required
def api_get_contacts():
    """API: Get all contacts."""
    search_query = request.args.get('search', '')
    if search_query:
        contacts = search_contacts(search_query)
    else:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        contacts = get_all_contacts(limit=limit, offset=offset)
    return jsonify(contacts)


@app.route('/api/contacts', methods=['POST'])
@login_required
def api_add_contact():
    """API: Add a new contact (for form integration)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    result = add_contact(
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        email=data.get('email', ''),
        phone=data.get('phone'),
        utm_source=data.get('utm_source'),
        utm_medium=data.get('utm_medium'),
        utm_campaign=data.get('utm_campaign'),
        utm_term=data.get('utm_term'),
        utm_content=data.get('utm_content'),
        deal_value=data.get('deal_value', 0),
        notes=data.get('notes'),
    )

    if result['success']:
        return jsonify(result), 201
    return jsonify(result), 400


@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
@login_required
def api_get_contact(contact_id):
    """API: Get a single contact."""
    contact = get_contact(contact_id)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
    return jsonify(contact)


@app.route('/api/contacts/<int:contact_id>', methods=['PUT', 'PATCH'])
@login_required
def api_update_contact(contact_id):
    """API: Update a contact."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    result = update_contact(contact_id, **data)
    return jsonify(result)


@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
@login_required
def api_delete_contact(contact_id):
    """API: Delete a contact."""
    result = delete_contact(contact_id)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 404


@app.route('/api/contacts/<int:contact_id>/deal', methods=['POST'])
@login_required
def api_set_deal(contact_id):
    """API: Set deal value for a contact."""
    data = request.get_json()
    if not data or 'deal_value' not in data:
        return jsonify({"error": "deal_value required"}), 400

    result = set_deal_value(contact_id, data['deal_value'])
    return jsonify(result)


@app.route('/api/analytics', methods=['GET'])
@login_required
def api_get_analytics():
    """API: Get dashboard analytics."""
    return jsonify(get_analytics())


@app.route('/api/deals/by-medium/<medium>', methods=['GET'])
@login_required
def api_deals_by_medium(medium):
    """API: Get deals filtered by UTM medium, with optional date range."""
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    # Get optional date filters
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    # Build date filter
    date_filter = ""
    params = []
    if start_date and end_date:
        date_filter = "AND d.actual_close_date >= ? AND d.actual_close_date <= ?"
        params = [start_date, end_date]
    elif start_date:
        date_filter = "AND d.actual_close_date >= ?"
        params = [start_date]
    elif end_date:
        date_filter = "AND d.actual_close_date <= ?"
        params = [end_date]

    # Handle "Unknown" which means NULL in database
    if medium.lower() == 'unknown':
        cursor.execute(f"""
            SELECT d.id, d.name, d.value, d.stage, d.salesperson,
                   d.utm_source, d.utm_medium, d.actual_close_date,
                   c.first_name, c.last_name, c.email
            FROM deals d
            LEFT JOIN deal_contacts dc ON d.id = dc.deal_id
            LEFT JOIN contacts c ON dc.contact_id = c.id
            WHERE d.stage = 'closed_won' AND d.utm_medium IS NULL {date_filter}
            ORDER BY d.actual_close_date DESC
        """, params)
    else:
        cursor.execute(f"""
            SELECT d.id, d.name, d.value, d.stage, d.salesperson,
                   d.utm_source, d.utm_medium, d.actual_close_date,
                   c.first_name, c.last_name, c.email
            FROM deals d
            LEFT JOIN deal_contacts dc ON d.id = dc.deal_id
            LEFT JOIN contacts c ON dc.contact_id = c.id
            WHERE d.stage = 'closed_won' AND d.utm_medium = ? {date_filter}
            ORDER BY d.actual_close_date DESC
        """, [medium] + params)

    deals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(deals)


@app.route('/api/deals/by-source/<source>', methods=['GET'])
@login_required
def api_deals_by_source(source):
    """API: Get deals filtered by UTM source, with optional date range."""
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    # Get optional date filters
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    # Build date filter
    date_filter = ""
    params = []
    if start_date and end_date:
        date_filter = "AND d.actual_close_date >= ? AND d.actual_close_date <= ?"
        params = [start_date, end_date]
    elif start_date:
        date_filter = "AND d.actual_close_date >= ?"
        params = [start_date]
    elif end_date:
        date_filter = "AND d.actual_close_date <= ?"
        params = [end_date]

    # Handle "Direct/Unknown" which means NULL in database
    if source.lower() in ['direct/unknown', 'direct', 'unknown']:
        cursor.execute(f"""
            SELECT d.id, d.name, d.value, d.stage, d.salesperson,
                   d.utm_source, d.utm_medium, d.actual_close_date,
                   c.first_name, c.last_name, c.email
            FROM deals d
            LEFT JOIN deal_contacts dc ON d.id = dc.deal_id
            LEFT JOIN contacts c ON dc.contact_id = c.id
            WHERE d.stage = 'closed_won' AND d.utm_source IS NULL {date_filter}
            ORDER BY d.actual_close_date DESC
        """, params)
    else:
        cursor.execute(f"""
            SELECT d.id, d.name, d.value, d.stage, d.salesperson,
                   d.utm_source, d.utm_medium, d.actual_close_date,
                   c.first_name, c.last_name, c.email
            FROM deals d
            LEFT JOIN deal_contacts dc ON d.id = dc.deal_id
            LEFT JOIN contacts c ON dc.contact_id = c.id
            WHERE d.stage = 'closed_won' AND d.utm_source = ? {date_filter}
            ORDER BY d.actual_close_date DESC
        """, [source] + params)

    deals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(deals)


@app.route('/api/leads/by-year/<year>', methods=['GET'])
@login_required
def api_leads_by_year(year):
    """API: Get leads by month and medium for a specific year."""
    data = get_leads_by_month_medium(year)
    return jsonify(data)


@app.route('/api/traffic/by-year/<year>', methods=['GET'])
@login_required
def api_traffic_by_year(year):
    """API: Get traffic by month and channel for a specific year."""
    website_id = request.args.get('website')
    if is_ga_connected():
        data = fetch_traffic_by_channel_and_month(int(year), website_id=website_id)
        if data and 'error' not in data:
            return jsonify(data)
    # Return demo data if GA not configured or error
    return jsonify(get_demo_traffic_by_month(int(year)))


@app.route('/api/leads/by-month-medium/<month>/<medium>', methods=['GET'])
@login_required
def api_leads_by_month_medium(month, medium):
    """API: Get leads for a specific month and medium."""
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    # Handle "Unknown" which means NULL in database
    if medium.lower() == 'unknown':
        cursor.execute("""
            SELECT id, first_name, last_name, email, phone,
                   utm_source, utm_medium, utm_campaign, created_at
            FROM contacts
            WHERE substr(created_at, 1, 7) = ? AND utm_medium IS NULL
            ORDER BY created_at DESC
        """, (month,))
    else:
        cursor.execute("""
            SELECT id, first_name, last_name, email, phone,
                   utm_source, utm_medium, utm_campaign, created_at
            FROM contacts
            WHERE substr(created_at, 1, 7) = ? AND utm_medium = ?
            ORDER BY created_at DESC
        """, (month, medium))

    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(leads)


@app.route('/api/deals/by-year/<year>', methods=['GET'])
@login_required
def api_deals_by_year(year):
    """API: Get deals by month and medium for a specific year."""
    data = get_deals_by_month_medium(year)
    return jsonify(data)


@app.route('/api/deals/by-month-medium/<month>/<medium>', methods=['GET'])
@login_required
def api_deals_by_month_medium(month, medium):
    """API: Get won deals for a specific month and medium."""
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    # Handle "Unknown" which means NULL in database
    if medium.lower() == 'unknown':
        cursor.execute("""
            SELECT id, name, value, salesperson, utm_source, utm_medium, actual_close_date
            FROM deals
            WHERE stage = 'closed_won' AND substr(actual_close_date, 1, 7) = ? AND utm_medium IS NULL
            ORDER BY actual_close_date DESC
        """, (month,))
    else:
        cursor.execute("""
            SELECT id, name, value, salesperson, utm_source, utm_medium, actual_close_date
            FROM deals
            WHERE stage = 'closed_won' AND substr(actual_close_date, 1, 7) = ? AND utm_medium = ?
            ORDER BY actual_close_date DESC
        """, (month, medium))

    deals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(deals)


@app.route('/api/deals/<int:deal_id>/stage', methods=['PUT'])
@login_required
def api_update_deal_stage(deal_id):
    """API: Update deal stage (for drag-and-drop). Accepts optional close_reason for closed stages."""
    data = request.get_json()
    if not data or 'stage' not in data:
        return jsonify({'success': False, 'error': 'Stage required'}), 400

    new_stage = data['stage']
    close_reason = data.get('close_reason')

    # Update stage
    result = update_deal_stage(deal_id, new_stage)

    # If there's a close reason and the update was successful, save it
    if result.get('success') and close_reason and new_stage in ['closed_won', 'closed_lost']:
        update_deal(deal_id, close_reason=close_reason)

    return jsonify(result)


@app.route('/api/deals', methods=['GET'])
@login_required
def api_get_deals():
    """API: Get all deals."""
    deals = get_all_deals()
    return jsonify(deals)


@app.route('/api/deals/analytics', methods=['GET'])
@login_required
def api_deal_analytics():
    """API: Get deal analytics."""
    return jsonify(get_deal_analytics())


@app.route('/api/salespeople', methods=['GET'])
@login_required
def api_get_salespeople():
    """API: Get all salespeople."""
    return jsonify(get_salespeople())


@app.route('/api/salespeople/<int:salesperson_id>', methods=['GET'])
@login_required
def api_get_salesperson(salesperson_id):
    """API: Get a single salesperson."""
    sp = get_salesperson(salesperson_id)
    if sp:
        return jsonify(sp)
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/salespeople', methods=['POST'])
@login_required
def api_add_salesperson():
    """API: Add a new salesperson."""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'error': 'Name is required'}), 400

    result = add_salesperson(
        name=data['name'],
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        email=data.get('email'),
        phone=data.get('phone')
    )
    if result['success']:
        return jsonify(result), 201
    return jsonify(result), 400


@app.route('/api/salespeople/<int:salesperson_id>', methods=['PUT'])
@login_required
def api_update_salesperson(salesperson_id):
    """API: Update a salesperson."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    result = update_salesperson(
        salesperson_id,
        name=data.get('name'),
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        email=data.get('email'),
        phone=data.get('phone')
    )
    return jsonify(result)


@app.route('/api/salespeople/<int:salesperson_id>', methods=['DELETE'])
@login_required
def api_delete_salesperson(salesperson_id):
    """API: Delete a salesperson."""
    result = delete_salesperson(salesperson_id)
    return jsonify(result)


# ============== Embeddable Form Routes ==============

@app.route('/api/form/submit', methods=['POST', 'OPTIONS'])
def api_form_submit():
    """API: Handle form submissions from external websites (with CORS support)."""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    # Validate required fields
    if not data.get('email'):
        return jsonify({"success": False, "error": "Email is required"}), 400

    # Add the contact
    result = add_contact(
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        email=data.get('email', ''),
        phone=data.get('phone'),
        utm_source=data.get('utm_source'),
        utm_medium=data.get('utm_medium'),
        utm_campaign=data.get('utm_campaign'),
        utm_term=data.get('utm_term'),
        utm_content=data.get('utm_content'),
        notes=data.get('message'),  # Store message in notes field
        landing_page=data.get('landing_page'),
        referrer=data.get('referrer'),
    )

    if result['success']:
        return jsonify({"success": True, "message": "Thank you! We'll be in touch soon."}), 201
    return jsonify({"success": False, "error": result.get('error', 'Submission failed')}), 400


@app.route('/forms')
@login_required
def forms_page():
    """Page showing the embeddable form code."""
    # Get the server URL for the form endpoint
    server_url = request.url_root.rstrip('/')
    # Force HTTPS on Railway/production
    if 'railway.app' in server_url or os.environ.get('RAILWAY_PUBLIC_DOMAIN'):
        server_url = server_url.replace('http://', 'https://')
    return render_template('forms.html', server_url=server_url)


# ============== Fix Requests ==============

@app.route('/fixes/submit', methods=['POST'])
@login_required
def submit_fix_request():
    """Handle fix request/bug report submission."""
    import os
    from werkzeug.utils import secure_filename

    name = request.form.get('name', '').strip()
    message = request.form.get('message', '').strip()

    if not name or not message:
        return redirect(url_for('quotes_list') + '?error=Name+and+message+are+required')

    # Handle file upload
    attachment_filename = None
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename:
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'fixes')
            os.makedirs(upload_dir, exist_ok=True)

            # Secure the filename and save
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            attachment_filename = f"{timestamp}_{filename}"
            file.save(os.path.join(upload_dir, attachment_filename))

    # Save to database
    result = add_fix_request(name, message, attachment_filename)

    if result['success']:
        return redirect(url_for('quotes_list') + '?success=Issue+reported+successfully!+Thank+you+for+your+feedback.')
    else:
        return redirect(url_for('quotes_list') + '?error=Failed+to+submit+issue')


@app.route('/fixes')
@login_required
def view_fix_requests():
    """View all fix requests."""
    fixes = get_all_fix_requests()
    return render_template('fix_requests.html', fixes=fixes)


@app.route('/fixes/<int:fix_id>/done', methods=['POST'])
@login_required
def mark_fix_done(fix_id):
    """Mark a fix request as done."""
    update_fix_request_status(fix_id, 'done')
    # Redirect back to the page they came from
    return redirect(request.referrer or url_for('dashboard'))


if __name__ == '__main__':
    print("\n" + "="*50)
    print("Simple CRM Starting...")
    print("="*50)
    print("\nDashboard: http://localhost:5000")
    print("Deals:     http://localhost:5000/deals")
    print("Contacts:  http://localhost:5000/contacts")
    print("Products:  http://localhost:5000/products")
    print("Quotes:    http://localhost:5000/quotes")
    print("Traffic:   http://localhost:5000/traffic")
    print("\nAPI Endpoints:")
    print("  GET/POST   /api/contacts")
    print("  GET/PUT/DELETE /api/contacts/<id>")
    print("  GET        /api/deals")
    print("  PUT        /api/deals/<id>/stage")
    print("  GET        /api/deals/analytics")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
