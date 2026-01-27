"""
Google Analytics 4 Integration Module
Fetches website traffic data from GA4 for the Traffic Dashboard.
Supports OAuth 2.0 "Login with Google" flow.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# Configuration file paths
CONFIG_PATH = Path(__file__).parent / "ga_config.json"
TOKEN_PATH = Path(__file__).parent / "ga_token.json"
OAUTH_SECRETS_PATH = Path(__file__).parent / "oauth_secrets.json"

# OAuth scopes needed for GA4
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

# GA4 API imports
try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        RunReportRequest,
        DateRange,
        Dimension,
        Metric,
    )
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    GA_AVAILABLE = True
except ImportError:
    GA_AVAILABLE = False


def is_oauth_configured():
    """Check if OAuth client secrets are configured."""
    return OAUTH_SECRETS_PATH.exists()


def is_ga_connected():
    """Check if GA4 is connected (has valid token and property ID)."""
    return TOKEN_PATH.exists() and CONFIG_PATH.exists()


def get_ga_config():
    """Load GA configuration."""
    if not CONFIG_PATH.exists():
        return None
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)

    # Migrate old single-property format to new multi-website format
    if 'websites' not in config and 'property_id' in config:
        config = {
            'websites': [{
                'id': '1',
                'name': 'Main Website',
                'property_id': config['property_id'],
                'added_at': config.get('configured_at', datetime.now().isoformat())
            }],
            'default_website': '1'
        }
        save_ga_config_raw(config)

    return config


def save_ga_config_raw(config):
    """Save raw GA configuration."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
    return config


def save_ga_config(property_id, name=None):
    """Save GA configuration (adds first website or updates for backwards compatibility)."""
    config = get_ga_config()

    if config and 'websites' in config:
        # Add to existing config
        return add_website(name or 'Website', property_id)

    # Create new config with first website
    config = {
        'websites': [{
            'id': '1',
            'name': name or 'Main Website',
            'property_id': property_id,
            'added_at': datetime.now().isoformat()
        }],
        'default_website': '1'
    }
    return save_ga_config_raw(config)


def get_websites():
    """Get list of all configured websites."""
    config = get_ga_config()
    if not config or 'websites' not in config:
        return []
    return config['websites']


def get_website(website_id):
    """Get a specific website by ID."""
    websites = get_websites()
    for site in websites:
        if site['id'] == website_id:
            return site
    return None


def add_website(name, property_id):
    """Add a new website to track."""
    config = get_ga_config() or {'websites': [], 'default_website': None}

    # Generate new ID
    existing_ids = [int(w['id']) for w in config.get('websites', []) if w['id'].isdigit()]
    new_id = str(max(existing_ids, default=0) + 1)

    new_website = {
        'id': new_id,
        'name': name,
        'property_id': property_id,
        'added_at': datetime.now().isoformat()
    }

    config['websites'].append(new_website)

    # Set as default if first website
    if not config.get('default_website'):
        config['default_website'] = new_id

    save_ga_config_raw(config)
    return new_website


def remove_website(website_id):
    """Remove a website from tracking."""
    config = get_ga_config()
    if not config or 'websites' not in config:
        return False

    config['websites'] = [w for w in config['websites'] if w['id'] != website_id]

    # Update default if we removed it
    if config.get('default_website') == website_id:
        config['default_website'] = config['websites'][0]['id'] if config['websites'] else None

    save_ga_config_raw(config)
    return True


def set_default_website(website_id):
    """Set the default website."""
    config = get_ga_config()
    if config:
        config['default_website'] = website_id
        save_ga_config_raw(config)


def get_default_website():
    """Get the default website."""
    config = get_ga_config()
    if not config:
        return None

    default_id = config.get('default_website')
    if default_id:
        return get_website(default_id)

    # Fall back to first website
    websites = config.get('websites', [])
    return websites[0] if websites else None


def get_oauth_secrets():
    """Load OAuth client secrets."""
    if not OAUTH_SECRETS_PATH.exists():
        return None
    with open(OAUTH_SECRETS_PATH, 'r') as f:
        return json.load(f)


def save_oauth_secrets(client_id, client_secret):
    """Save OAuth client secrets."""
    secrets = {
        'web': {
            'client_id': client_id,
            'client_secret': client_secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': ['http://localhost:5000/traffic/oauth/callback']
        }
    }
    with open(OAUTH_SECRETS_PATH, 'w') as f:
        json.dump(secrets, f, indent=2)
    return secrets


def get_oauth_flow(redirect_uri='http://localhost:5000/traffic/oauth/callback'):
    """Create OAuth flow for authorization."""
    if not GA_AVAILABLE or not is_oauth_configured():
        return None

    flow = Flow.from_client_secrets_file(
        str(OAUTH_SECRETS_PATH),
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow


def save_oauth_token(credentials):
    """Save OAuth token from credentials."""
    token_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': list(credentials.scopes),
        'saved_at': datetime.now().isoformat()
    }
    with open(TOKEN_PATH, 'w') as f:
        json.dump(token_data, f, indent=2)


def get_credentials():
    """Get OAuth credentials from saved token."""
    if not TOKEN_PATH.exists():
        return None

    with open(TOKEN_PATH, 'r') as f:
        token_data = json.load(f)

    credentials = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes')
    )
    return credentials


def get_ga_client():
    """Get authenticated GA4 client using OAuth credentials."""
    if not GA_AVAILABLE:
        return None

    credentials = get_credentials()
    if not credentials:
        return None

    # Always try to refresh if we have a refresh token (access tokens expire after 1 hour)
    if credentials.refresh_token:
        try:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            save_oauth_token(credentials)
        except Exception as e:
            print(f"Token refresh error: {e}")
            # Continue with existing token, it might still work

    return BetaAnalyticsDataClient(credentials=credentials)


def disconnect_ga():
    """Disconnect GA4 (remove tokens and config)."""
    if TOKEN_PATH.exists():
        os.remove(TOKEN_PATH)
    if CONFIG_PATH.exists():
        os.remove(CONFIG_PATH)


def fetch_traffic_by_channel(start_date=None, end_date=None, website_id=None):
    """
    Fetch traffic sessions grouped by channel from GA4.
    """
    if not GA_AVAILABLE or not is_ga_connected():
        return None

    # Get website (specific or default)
    if website_id:
        website = get_website(website_id)
    else:
        website = get_default_website()

    if not website:
        return None

    client = get_ga_client()
    if not client:
        return None

    # Default to last 30 days
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    property_id = website['property_id']

    try:
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="sessionDefaultChannelGroup"),
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="newUsers"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"),
            ],
        )

        response = client.run_report(request)

        by_channel = []
        total_sessions = 0
        total_users = 0
        total_new_users = 0

        for row in response.rows:
            channel = row.dimension_values[0].value
            sessions = int(row.metric_values[0].value)
            users = int(row.metric_values[1].value)
            new_users = int(row.metric_values[2].value)
            bounce_rate = float(row.metric_values[3].value) * 100
            avg_duration = float(row.metric_values[4].value)

            by_channel.append({
                'channel': channel,
                'sessions': sessions,
                'users': users,
                'new_users': new_users,
                'bounce_rate': round(bounce_rate, 1),
                'avg_duration': round(avg_duration, 1),
            })

            total_sessions += sessions
            total_users += users
            total_new_users += new_users

        by_channel.sort(key=lambda x: x['sessions'], reverse=True)

        return {
            'by_channel': by_channel,
            'totals': {
                'sessions': total_sessions,
                'users': total_users,
                'new_users': total_new_users,
            },
            'date_range': {
                'start': start_date,
                'end': end_date,
            },
            'is_demo': False
        }

    except Exception as e:
        print(f"GA4 API Error: {e}")
        return {'error': str(e)}


def fetch_phone_clicks(start_date=None, end_date=None, website_id=None):
    """
    Fetch phone_click event count from GA4.
    """
    if not GA_AVAILABLE or not is_ga_connected():
        return None

    # Get website (specific or default)
    if website_id:
        website = get_website(website_id)
    else:
        website = get_default_website()

    if not website:
        return None

    client = get_ga_client()
    if not client:
        return None

    # Default to last 30 days
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    property_id = website['property_id']

    try:
        from google.analytics.data_v1beta.types import FilterExpression, Filter

        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="eventName"),
            ],
            metrics=[
                Metric(name="eventCount"),
            ],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name="eventName",
                    string_filter=Filter.StringFilter(value="phone_click"),
                )
            ),
        )

        response = client.run_report(request)

        phone_clicks = 0
        for row in response.rows:
            phone_clicks = int(row.metric_values[0].value)

        return {
            'phone_clicks': phone_clicks,
            'date_range': {
                'start': start_date,
                'end': end_date,
            }
        }

    except Exception as e:
        print(f"GA4 Phone Click Error: {e}")
        return {'phone_clicks': 0, 'error': str(e)}


def fetch_traffic_by_channel_and_month(year=None, website_id=None):
    """
    Fetch monthly traffic by channel for stacked bar chart.
    """
    if not GA_AVAILABLE or not is_ga_connected():
        return None

    # Get website (specific or default)
    if website_id:
        website = get_website(website_id)
    else:
        website = get_default_website()

    if not website:
        return None

    client = get_ga_client()
    if not client:
        return None

    if not year:
        year = datetime.now().year

    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    property_id = website['property_id']

    try:
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="yearMonth"),
                Dimension(name="sessionDefaultChannelGroup"),
            ],
            metrics=[
                Metric(name="sessions"),
            ],
        )

        response = client.run_report(request)

        all_months = [f"{year}{str(m).zfill(2)}" for m in range(1, 13)]
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        channels = set()
        raw_data = {}

        for row in response.rows:
            year_month = row.dimension_values[0].value
            channel = row.dimension_values[1].value
            sessions = int(row.metric_values[0].value)

            channels.add(channel)
            if year_month not in raw_data:
                raw_data[year_month] = {}
            raw_data[year_month][channel] = sessions

        channels = sorted(list(channels))

        chart_data = {}
        for channel in channels:
            chart_data[channel] = []
            for month in all_months:
                count = raw_data.get(month, {}).get(channel, 0)
                chart_data[channel].append(count)

        monthly_totals = []
        for i, month in enumerate(all_months):
            total = sum(chart_data[channel][i] for channel in channels)
            monthly_totals.append(total)

        available_years = [str(y) for y in range(2030, 2023, -1)]

        return {
            'year': str(year),
            'months': all_months,
            'month_names': month_names,
            'channels': channels,
            'data': chart_data,
            'totals': monthly_totals,
            'available_years': available_years,
            'is_demo': False
        }

    except Exception as e:
        print(f"GA4 API Error: {e}")
        return {'error': str(e)}


def fetch_ga_properties():
    """Fetch list of GA4 properties the user has access to."""
    if not GA_AVAILABLE or not is_oauth_configured():
        return None

    credentials = get_credentials()
    if not credentials:
        return None

    try:
        from googleapiclient.discovery import build

        # Use Admin API to list accounts and properties
        service = build('analyticsadmin', 'v1beta', credentials=credentials)

        accounts = service.accounts().list().execute()

        properties = []
        for account in accounts.get('accounts', []):
            account_name = account['name']
            props = service.properties().list(filter=f"parent:{account_name}").execute()
            for prop in props.get('properties', []):
                properties.append({
                    'property_id': prop['name'].replace('properties/', ''),
                    'display_name': prop['displayName'],
                    'account': account.get('displayName', 'Unknown')
                })

        return properties
    except Exception as e:
        print(f"Error fetching properties: {e}")
        return None


# Demo/placeholder data for when GA is not connected
def get_demo_traffic_data():
    """Return demo data for preview when GA is not connected."""
    return {
        'by_channel': [
            {'channel': 'Organic Search', 'sessions': 2847, 'users': 2103, 'new_users': 1876, 'bounce_rate': 42.3, 'avg_duration': 185.4},
            {'channel': 'Paid Search', 'sessions': 1523, 'users': 1401, 'new_users': 1298, 'bounce_rate': 38.7, 'avg_duration': 203.2},
            {'channel': 'Direct', 'sessions': 1245, 'users': 987, 'new_users': 432, 'bounce_rate': 35.2, 'avg_duration': 245.8},
            {'channel': 'Paid Social', 'sessions': 892, 'users': 834, 'new_users': 789, 'bounce_rate': 52.1, 'avg_duration': 124.6},
            {'channel': 'Organic Social', 'sessions': 634, 'users': 598, 'new_users': 521, 'bounce_rate': 48.9, 'avg_duration': 156.3},
            {'channel': 'Referral', 'sessions': 423, 'users': 387, 'new_users': 298, 'bounce_rate': 41.2, 'avg_duration': 178.9},
            {'channel': 'Email', 'sessions': 312, 'users': 287, 'new_users': 98, 'bounce_rate': 28.4, 'avg_duration': 312.5},
            {'channel': 'Affiliates', 'sessions': 156, 'users': 143, 'new_users': 132, 'bounce_rate': 44.7, 'avg_duration': 167.2},
        ],
        'totals': {
            'sessions': 8032,
            'users': 6740,
            'new_users': 5444,
        },
        'date_range': {
            'start': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'end': datetime.now().strftime('%Y-%m-%d'),
        },
        'is_demo': True,
    }


def get_demo_traffic_by_month(year=None):
    """Return demo monthly data for preview."""
    if not year:
        year = datetime.now().year

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    all_months = [f"{year}{str(m).zfill(2)}" for m in range(1, 13)]

    channels = ['Organic Search', 'Paid Search', 'Direct', 'Paid Social', 'Organic Social', 'Referral', 'Email']

    import random
    random.seed(42)

    chart_data = {}
    for channel in channels:
        base = {'Organic Search': 250, 'Paid Search': 150, 'Direct': 100,
                'Paid Social': 80, 'Organic Social': 50, 'Referral': 40, 'Email': 30}[channel]
        chart_data[channel] = [int(base * (0.8 + random.random() * 0.4)) for _ in range(12)]

    monthly_totals = []
    for i in range(12):
        total = sum(chart_data[channel][i] for channel in channels)
        monthly_totals.append(total)

    available_years = [str(y) for y in range(2030, 2023, -1)]

    return {
        'year': str(year),
        'months': all_months,
        'month_names': month_names,
        'channels': channels,
        'data': chart_data,
        'totals': monthly_totals,
        'available_years': available_years,
        'is_demo': True,
    }
