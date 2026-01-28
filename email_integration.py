"""
Email Integration Module
Handles Gmail and Outlook OAuth connections for reading emails.
Emails are fetched on-demand, not stored in the database.
Tokens are stored per-user in the database.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta

from database import (
    save_user_email_token, get_user_email_token,
    delete_user_email_token, get_user_email_status,
    get_contact_by_email, update_contact_activity
)

# Config paths (app-level credentials, shared across all users)
CONFIG_DIR = Path(__file__).parent
GMAIL_CREDENTIALS_PATH = CONFIG_DIR / "gmail_credentials.json"
OUTLOOK_CONFIG_PATH = CONFIG_DIR / "outlook_config.json"

# Gmail OAuth scopes (read-only)
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Microsoft Graph API scopes (read-only)
OUTLOOK_SCOPES = ['https://graph.microsoft.com/Mail.Read']


def get_base_url():
    """Get the base URL for OAuth redirects (handles localhost vs production)."""
    # Check for Railway or other production environment
    railway_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if railway_url:
        return f"https://{railway_url}"

    # Check for explicit BASE_URL environment variable
    base_url = os.environ.get('BASE_URL')
    if base_url:
        return base_url.rstrip('/')

    # Default to localhost for development
    return 'http://localhost:5000'


def get_gmail_redirect_uri():
    """Get Gmail OAuth redirect URI."""
    return f"{get_base_url()}/settings/email/gmail/callback"


def get_outlook_redirect_uri():
    """Get Outlook OAuth redirect URI."""
    return f"{get_base_url()}/settings/email/outlook/callback"


# ============== Gmail Integration ==============

def is_gmail_configured():
    """Check if Gmail OAuth credentials file exists (app-level)."""
    return GMAIL_CREDENTIALS_PATH.exists()


def is_gmail_connected(user_id):
    """Check if Gmail is connected for a specific user."""
    token_data = get_user_email_token(user_id, 'gmail')
    if not token_data:
        return False
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(token_data, GMAIL_SCOPES)
        return creds and creds.valid
    except:
        return False


def get_gmail_auth_url():
    """Get Gmail OAuth authorization URL."""
    if not is_gmail_configured():
        return None

    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_secrets_file(
            str(GMAIL_CREDENTIALS_PATH),
            scopes=GMAIL_SCOPES,
            redirect_uri=get_gmail_redirect_uri()
        )

        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return auth_url
    except Exception as e:
        print(f"Error getting Gmail auth URL: {e}")
        return None


def gmail_oauth_callback(user_id, authorization_response):
    """Handle Gmail OAuth callback and save credentials for user."""
    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_secrets_file(
            str(GMAIL_CREDENTIALS_PATH),
            scopes=GMAIL_SCOPES,
            redirect_uri=get_gmail_redirect_uri()
        )

        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials

        # Convert credentials to dict and save to database
        token_data = json.loads(creds.to_json())
        save_user_email_token(user_id, 'gmail', token_data)

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def disconnect_gmail(user_id):
    """Disconnect Gmail for a specific user."""
    delete_user_email_token(user_id, 'gmail')
    return {"success": True}


def get_gmail_service(user_id):
    """Get authenticated Gmail API service for a specific user."""
    token_data = get_user_email_token(user_id, 'gmail')
    if not token_data:
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_info(token_data, GMAIL_SCOPES)

        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token back to database
            new_token_data = json.loads(creds.to_json())
            save_user_email_token(user_id, 'gmail', new_token_data)

        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        print(f"Error getting Gmail service: {e}")
        return None


def fetch_gmail_emails(user_id, email_address, max_results=20):
    """
    Fetch emails to/from a specific email address from Gmail.
    Returns list of email summaries (not stored in DB).
    """
    service = get_gmail_service(user_id)
    if not service:
        return {"success": False, "error": "Gmail not connected"}

    try:
        # Search for emails to OR from this address
        query = f"from:{email_address} OR to:{email_address}"

        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])
        emails = []

        for msg in messages:
            # Get message details
            message = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'To', 'Subject', 'Date']
            ).execute()

            headers = {h['name']: h['value'] for h in message.get('payload', {}).get('headers', [])}

            emails.append({
                'id': msg['id'],
                'from': headers.get('From', ''),
                'to': headers.get('To', ''),
                'subject': headers.get('Subject', '(No Subject)'),
                'date': headers.get('Date', ''),
                'snippet': message.get('snippet', ''),
                'source': 'gmail'
            })

        return {"success": True, "emails": emails}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_gmail_email_body(user_id, email_id):
    """
    Fetch the full body of a single Gmail email.
    Returns the email with full content.
    """
    import base64

    service = get_gmail_service(user_id)
    if not service:
        return {"success": False, "error": "Gmail not connected"}

    try:
        # Get full message
        message = service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()

        headers = {h['name']: h['value'] for h in message.get('payload', {}).get('headers', [])}

        # Extract body
        body = ""
        payload = message.get('payload', {})

        if 'body' in payload and payload['body'].get('data'):
            # Simple message
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        elif 'parts' in payload:
            # Multipart message - find text/plain or text/html
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain' and part.get('body', {}).get('data'):
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    break
                elif mime_type == 'text/html' and part.get('body', {}).get('data'):
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                # Handle nested multipart
                if 'parts' in part:
                    for subpart in part['parts']:
                        sub_mime = subpart.get('mimeType', '')
                        if sub_mime == 'text/plain' and subpart.get('body', {}).get('data'):
                            body = base64.urlsafe_b64decode(subpart['body']['data']).decode('utf-8', errors='ignore')
                            break
                        elif sub_mime == 'text/html' and subpart.get('body', {}).get('data'):
                            body = base64.urlsafe_b64decode(subpart['body']['data']).decode('utf-8', errors='ignore')

        return {
            "success": True,
            "email": {
                'id': email_id,
                'from': headers.get('From', ''),
                'to': headers.get('To', ''),
                'subject': headers.get('Subject', '(No Subject)'),
                'date': headers.get('Date', ''),
                'body': body,
                'source': 'gmail'
            }
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============== Outlook/Microsoft Integration ==============

def save_outlook_config(client_id, client_secret, tenant_id='common'):
    """Save Outlook OAuth configuration (app-level, shared across users)."""
    config = {
        'client_id': client_id,
        'client_secret': client_secret,
        'tenant_id': tenant_id
    }
    with open(OUTLOOK_CONFIG_PATH, 'w') as f:
        json.dump(config, f)
    return {"success": True}


def get_outlook_config():
    """Get Outlook OAuth configuration."""
    if not OUTLOOK_CONFIG_PATH.exists():
        return None
    with open(OUTLOOK_CONFIG_PATH, 'r') as f:
        return json.load(f)


def is_outlook_configured():
    """Check if Outlook OAuth is configured (app-level)."""
    return OUTLOOK_CONFIG_PATH.exists()


def refresh_outlook_token(user_id):
    """Refresh an expired Outlook token using the refresh token."""
    import requests

    token_data = get_user_email_token(user_id, 'outlook')
    if not token_data or 'refresh_token' not in token_data:
        return None

    config = get_outlook_config()
    if not config:
        return None

    client_id = config['client_id']
    client_secret = config['client_secret']
    tenant_id = config.get('tenant_id', 'common')

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    try:
        response = requests.post(token_url, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': token_data['refresh_token'],
            'grant_type': 'refresh_token',
            'scope': 'offline_access Mail.Read'
        })

        if response.status_code == 200:
            new_token_data = response.json()
            # Add expiration timestamp
            new_token_data['expires_at'] = datetime.now().timestamp() + new_token_data.get('expires_in', 3600)
            # Save updated token
            save_user_email_token(user_id, 'outlook', new_token_data)
            return new_token_data
        else:
            print(f"Token refresh failed: {response.text}")
            return None
    except Exception as e:
        print(f"Token refresh error: {e}")
        return None


def is_outlook_connected(user_id):
    """Check if Outlook is connected for a specific user. Auto-refreshes if expired."""
    token_data = get_user_email_token(user_id, 'outlook')
    if not token_data:
        return False
    try:
        # Check if token is expired
        expires_at = token_data.get('expires_at', 0)
        if datetime.now().timestamp() >= expires_at:
            # Try to refresh the token
            new_token = refresh_outlook_token(user_id)
            return new_token is not None
        return True
    except:
        return False


def get_outlook_auth_url():
    """Get Outlook OAuth authorization URL."""
    config = get_outlook_config()
    if not config:
        return None

    client_id = config['client_id']
    tenant_id = config.get('tenant_id', 'common')
    redirect_uri = get_outlook_redirect_uri()
    scope = 'offline_access Mail.Read'

    auth_url = (
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
        f"&response_mode=query"
    )
    return auth_url


def outlook_oauth_callback(user_id, authorization_code):
    """Handle Outlook OAuth callback and save credentials for user."""
    import requests

    config = get_outlook_config()
    if not config:
        return {"success": False, "error": "Outlook not configured"}

    client_id = config['client_id']
    client_secret = config['client_secret']
    tenant_id = config.get('tenant_id', 'common')
    redirect_uri = get_outlook_redirect_uri()

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    try:
        response = requests.post(token_url, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'code': authorization_code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
            'scope': 'offline_access Mail.Read'
        })

        if response.status_code == 200:
            token_data = response.json()
            # Add expiration timestamp
            token_data['expires_at'] = datetime.now().timestamp() + token_data.get('expires_in', 3600)

            # Save to database for this user
            save_user_email_token(user_id, 'outlook', token_data)

            return {"success": True}
        else:
            return {"success": False, "error": response.text}

    except Exception as e:
        return {"success": False, "error": str(e)}


def refresh_outlook_token(user_id):
    """Refresh Outlook access token using refresh token for a specific user."""
    import requests

    token_data = get_user_email_token(user_id, 'outlook')
    if not token_data:
        return None

    config = get_outlook_config()
    if not config:
        return None

    refresh_token = token_data.get('refresh_token')
    if not refresh_token:
        return None

    client_id = config['client_id']
    client_secret = config['client_secret']
    tenant_id = config.get('tenant_id', 'common')

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    try:
        response = requests.post(token_url, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'scope': 'offline_access Mail.Read'
        })

        if response.status_code == 200:
            new_token_data = response.json()
            new_token_data['expires_at'] = datetime.now().timestamp() + new_token_data.get('expires_in', 3600)

            # Save refreshed token back to database
            save_user_email_token(user_id, 'outlook', new_token_data)

            return new_token_data.get('access_token')
    except:
        pass

    return None


def get_outlook_access_token(user_id):
    """Get valid Outlook access token for a specific user, refreshing if needed."""
    token_data = get_user_email_token(user_id, 'outlook')
    if not token_data:
        return None

    expires_at = token_data.get('expires_at', 0)

    # If token is expired or about to expire (within 5 minutes), refresh it
    if datetime.now().timestamp() >= expires_at - 300:
        return refresh_outlook_token(user_id)

    return token_data.get('access_token')


def disconnect_outlook(user_id):
    """Disconnect Outlook for a specific user."""
    delete_user_email_token(user_id, 'outlook')
    return {"success": True}


def fetch_outlook_emails(user_id, email_address, max_results=20):
    """
    Fetch emails to/from a specific email address from Outlook.
    Returns list of email summaries (not stored in DB).
    """
    import requests

    access_token = get_outlook_access_token(user_id)
    if not access_token:
        return {"success": False, "error": "Outlook not connected"}

    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Use $search without $orderby (they can't be combined in Graph API)
        # The search will look in from, to, subject, and body
        search_url = f"https://graph.microsoft.com/v1.0/me/messages?$search=\"{email_address}\"&$top={max_results}"

        response = requests.get(search_url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            messages = data.get('value', [])

            emails = []
            for msg in messages:
                from_email = msg.get('from', {}).get('emailAddress', {})
                to_emails = msg.get('toRecipients', [])
                to_str = ', '.join([r.get('emailAddress', {}).get('address', '') for r in to_emails])

                emails.append({
                    'id': msg.get('id'),
                    'from': f"{from_email.get('name', '')} <{from_email.get('address', '')}>",
                    'to': to_str,
                    'subject': msg.get('subject', '(No Subject)'),
                    'date': msg.get('receivedDateTime', ''),
                    'snippet': msg.get('bodyPreview', '')[:200],
                    'source': 'outlook'
                })

            # Sort by date (newest first) since we can't use $orderby with $search
            emails.sort(key=lambda x: x.get('date', ''), reverse=True)

            return {"success": True, "emails": emails}
        else:
            return {"success": False, "error": f"API error: {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_outlook_email_body(user_id, email_id):
    """
    Fetch the full body of a single Outlook email.
    Returns the email with full content.
    """
    import requests

    access_token = get_outlook_access_token(user_id)
    if not access_token:
        return {"success": False, "error": "Outlook not connected"}

    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Get single message with body
        url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            msg = response.json()
            from_email = msg.get('from', {}).get('emailAddress', {})
            to_emails = msg.get('toRecipients', [])
            to_str = ', '.join([r.get('emailAddress', {}).get('address', '') for r in to_emails])

            # Get body content (prefer HTML, fallback to text)
            body_content = msg.get('body', {})
            body = body_content.get('content', '')

            return {
                "success": True,
                "email": {
                    'id': email_id,
                    'from': f"{from_email.get('name', '')} <{from_email.get('address', '')}>",
                    'to': to_str,
                    'subject': msg.get('subject', '(No Subject)'),
                    'date': msg.get('receivedDateTime', ''),
                    'body': body,
                    'body_type': body_content.get('contentType', 'text'),
                    'source': 'outlook'
                }
            }
        else:
            return {"success": False, "error": f"API error: {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============== Combined Functions ==============

def get_email_status(user_id):
    """Get status of both email integrations for a specific user."""
    return {
        'gmail': {
            'configured': is_gmail_configured(),
            'connected': is_gmail_connected(user_id)
        },
        'outlook': {
            'configured': is_outlook_configured(),
            'connected': is_outlook_connected(user_id)
        }
    }


def fetch_emails_for_contact(user_id, email_address, max_results=20):
    """
    Fetch emails from all connected email sources for a contact.
    Combines results from Gmail and Outlook if both are connected.
    Uses the specified user's email connections.
    Also updates the contact's last_activity_date if emails were sent TO the contact.
    """
    all_emails = []
    errors = []

    # Try Gmail
    if is_gmail_connected(user_id):
        gmail_result = fetch_gmail_emails(user_id, email_address, max_results)
        if gmail_result['success']:
            all_emails.extend(gmail_result['emails'])
        else:
            errors.append(f"Gmail: {gmail_result.get('error')}")

    # Try Outlook
    if is_outlook_connected(user_id):
        outlook_result = fetch_outlook_emails(user_id, email_address, max_results)
        if outlook_result['success']:
            all_emails.extend(outlook_result['emails'])
        else:
            errors.append(f"Outlook: {outlook_result.get('error')}")

    # Sort all emails by date (newest first)
    try:
        all_emails.sort(key=lambda x: x.get('date', ''), reverse=True)
    except:
        pass

    # Update last_activity_date if emails were sent TO the contact
    if all_emails:
        sent_to_contact = [e for e in all_emails if email_address.lower() in e.get('to', '').lower()]
        if sent_to_contact:
            contact = get_contact_by_email(email_address)
            if contact:
                update_contact_activity(contact['id'])

    return {
        'success': len(errors) == 0 or len(all_emails) > 0,
        'emails': all_emails[:max_results],
        'errors': errors if errors else None,
        'sources': {
            'gmail': is_gmail_connected(user_id),
            'outlook': is_outlook_connected(user_id)
        }
    }
