# Outlook Email Integration Setup Guide

## What This Does

Once connected, the CRM can:
- **View email history** for any contact - see all emails to/from that person directly on their contact page
- **Per-user connections** - each salesperson connects their own Outlook, sees only their own emails
- **Read-only access** - CRM can only READ emails, never send/delete/modify
- **On-demand fetching** - emails are NOT stored in the CRM database, just displayed live from Outlook
- **Track accountability** - see which leads have been contacted and which haven't

---

## One-Time Admin Setup (Azure App Registration)

This only needs to be done ONCE for the whole company.

### Step 1: Create the App in Azure

1. Go to https://portal.azure.com
2. Sign in with your **admin Microsoft account** (the one that manages your company's Microsoft 365)
3. Search for **App registrations** in the top search bar
4. Click **+ New registration**
5. Fill in:
   - **Name:** `Steelstack CRM` (or whatever you want to call it)
   - **Supported account types:** Leave as "Accounts in this organizational directory only"
   - **Redirect URI:** Select "Web" and enter: `http://localhost:5000/settings/email/outlook/callback`
6. Click **Register**

### Step 2: Get Your Client ID

1. After creating, you'll be on the app's **Overview** page
2. Copy the **Application (client) ID** - save this somewhere
   - Looks like: `b790c0a2-934f-4541-a4d8-cf2c73c16190`

### Step 3: Create a Client Secret

1. In the left sidebar, click **Certificates & secrets**
2. Click **+ New client secret**
3. Description: `CRM Access`
4. Expires: `24 months` (set a calendar reminder to renew!)
5. Click **Add**
6. **IMMEDIATELY** copy the **Value** column (NOT the Secret ID!)
   - Value looks like: `Ev-8Q~5lT8fZWGtzXD8...`
   - Secret ID looks like: `a9c6ac5c-73e3-4a27-...` (DON'T use this)
   - The Value disappears once you leave this page!

### Step 4: Add Email Permission

1. In the left sidebar, click **API permissions**
2. Click **+ Add a permission**
3. Select **Microsoft Graph**
4. Select **Delegated permissions**
5. Search for **Mail.Read** and check the box
6. Click **Add permissions**
7. Click **Grant admin consent for [Your Company]** button at the top
8. Click **Yes** to confirm

---

## Per-User Setup (Each Salesperson)

Each person who wants to see their emails in the CRM does this:

1. Log into the CRM with their account
2. Go to **Settings > Email Integration**
3. Enter the Client ID and Client Secret (get from admin)
4. Click **Connect with Outlook**
5. Sign in with their work Microsoft account
6. Click **Accept** on the permissions screen

That's it! Now when they view a contact, they'll see their email history with that person.

---

## Troubleshooting

### "Invalid client secret"
- You copied the **Secret ID** instead of the **Value**
- Create a new secret and copy the Value immediately

### "Application not found in directory"
- You're signing in with a different Microsoft account than where the app was created
- Make sure you sign in with your work account

### "Admin approval required"
- Your company requires admin consent
- An admin needs to go to Azure > Enterprise Applications > [App Name] > Permissions > Grant admin consent

### "No reply address registered"
- The Redirect URI wasn't set
- Go to Azure > App registrations > [App] > Authentication > Add platform > Web
- Enter: `http://localhost:5000/settings/email/outlook/callback`

---

## Moving to Production (Cloud Server)

When you move the CRM to a real domain:

1. Go to Azure > App registrations > [App] > Authentication
2. Add a new Redirect URI: `https://yourdomain.com/settings/email/outlook/callback`
3. Keep the localhost one too (for development)

---

## Security Notes

- **Tokens expire** - access tokens last 1 hour, refresh tokens are used automatically
- **Revoke anytime** - users can disconnect from CRM settings, or from their Microsoft account security settings
- **Read-only** - the app can ONLY read emails, nothing else
- **Per-user** - each user's token is stored separately, they only see their own emails
- **No email storage** - emails are fetched on-demand, never saved in the CRM database

---

## Your Credentials (for reference)

**Client ID:** `b790c0a2-934f-4541-a4d8-cf2c73c16190`
**Client Secret:** [stored securely - create new one if lost]
**Tenant:** Morrison Industries (steelstackusa.com)
**Redirect URI:** `http://localhost:5000/settings/email/outlook/callback`

---

## Renewal Reminder

Your client secret expires: **January 20, 2028**

Set a calendar reminder to create a new secret before then!
