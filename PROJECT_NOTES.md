# Simple CRM - Project Notes
## For Claude Context Recovery

**Last Updated:** January 22, 2026
**Company:** Steelstack (Steel storage racks)
**Owner:** Ray Bishop

---

## CURRENT STATUS

### What's Working:
- Full CRM running at http://localhost:5000
- Contacts, Companies, Deals, Quotes all functional
- Quote PDF generation with Steelstack branding
- Outlook email integration (OAuth connected, auto-refresh tokens)
- User login system (admin: ray / steelstack)
- Product catalog (25 Steelstack products with correct SKUs/prices)
- Traffic/analytics page
- Payment link field (Stripe) on quotes → shows on PDF
- Financing link field (Approve) on quotes → shows on PDF
- **UTM tracking** - auto-populates from URL → quote → contact → deal
- **"How did you hear about us?"** field on quotes → flows to deals
- **Company linking** - dropdowns on Deal and Contact edit pages
- **All routes secured** with @login_required
- **Database indexed** for performance

### What's Pending:
- Deploying to Railway (need PostgreSQL migration first)
- HubSpot data export (locked out, sent data request email)

---

## JANUARY 22, 2026 SESSION

### What We Built:
1. **UTM Tracking Flow**
   - Quote form auto-fills utm_source, utm_medium, utm_campaign from URL params
   - When quote creates a deal, UTM data flows to the deal
   - When quote creates a contact, UTM data flows to the contact
   - Selecting existing contact auto-fills their UTM data

2. **Lead Source Tracking**
   - Added "How did you hear about us?" field (reported_source)
   - Shows on quote form and deal detail page
   - Pipeline shows: green badge (verified source) or red (no source)

3. **Company Linking**
   - Added Company dropdown to Deal edit page
   - Added Company dropdown to Contact edit page
   - Company detail page shows linked deals/quotes/contacts

### Cleanup Done:
- Deleted 4 orphaned test quotes (test, jess, butter, gfdgdsga)
- Deleted 4 orphaned deal_contacts
- Added @login_required to 63 unprotected routes
- Added 12 database indexes for performance

### PostgreSQL Migration (PLANNED - NOT DONE YET):
- Railway has ephemeral storage (files get wiped on redeploy)
- Need to convert SQLite → PostgreSQL for cloud hosting
- Estimated 2-3 hours of code changes
- Plan: Support BOTH databases (SQLite local, PostgreSQL on Railway)
- See: C:\Users\RayBishop\backups\postgresql-migration-notes.md

---

## KEY DECISIONS MADE

1. **Hosting:** Railway for deployment (free tier, PostgreSQL included)
2. **Database:** SQLite locally, PostgreSQL on Railway (dual support planned)
3. **Payment Links:** Manual workflow - create in Stripe, paste into quote
4. **Financing:** Using Approve - same workflow as Stripe
5. **Email:** Outlook OAuth (connected to steelstackusa.com via Azure app)
6. **Lead Source System:** Two-tier - salespeople record what customer says, admin verifies in Edit Deal
7. **UTM Medium values:** cpc, organic, social, email, referral, direct, display, video, affiliate

---

## BUSINESS CONTEXT

- **Steelstack** sells steel storage rack systems
- Part of **Morrison Industries** tenant (Azure)
- Website on **Squarespace** (considering Webflow)
- Previously used **HubSpot** (now locked out)
- Need to track lead sources (UTM data, where customers come from)
- Customers come from: YouTube, Google, trade shows, referrals

---

## DATABASE INFO

### Tables:
- contacts (3 rows)
- deals (2 rows)
- companies (2 rows - including Arktura)
- quotes (2 rows)
- products (25 rows - Steelstack catalog)
- salespeople (3 rows)

### Indexes Added (Jan 22):
- idx_contacts_email, idx_contacts_company_id
- idx_deals_company_id, idx_deals_stage, idx_deals_utm_medium
- idx_quotes_deal_id, idx_quotes_contact_id, idx_quotes_company_id
- idx_deal_contacts_deal_id, idx_deal_contacts_contact_id

---

## BACKUPS

| Date | Location |
|------|----------|
| Jan 22, 2026 | C:\Users\RayBishop\backups\simple-crm-backup-2026-01-22.zip |
| Jan 22, 2026 | C:\Users\RayBishop\backups\session-notes-2026-01-22.md |
| Jan 22, 2026 | C:\Users\RayBishop\backups\postgresql-migration-notes.md |
| Jan 22, 2026 | C:\Users\RayBishop\backups\conversation-2026-01-22-v2.jsonl |

---

## AZURE/OUTLOOK CONFIG

- **App Name:** Steelstack CRM (in Azure)
- **Client ID:** b790c0a2-934f-4541-a4d8-cf2c73c16190
- **Tenant:** Morrison Industries
- **API Secret Expires:** January 20, 2028
- **Permissions:** Mail.Read (delegated)
- **Token auto-refresh:** Implemented

---

## FILES STRUCTURE

```
C:\Users\RayBishop\simple-crm\
├── app.py              # Main Flask application (~1900 lines)
├── database.py         # Database functions (~2450 lines)
├── pdf_generator.py    # Quote PDF generation
├── email_integration.py # Outlook/Gmail OAuth
├── shipping_calculator.py
├── crm.db              # THE DATABASE (all data)
├── templates/          # HTML templates
├── static/             # Logo, CSS
└── outlook_config.json # Outlook OAuth config

C:\Users\RayBishop\backups\
├── simple-crm-backup-*.zip
├── session-notes-*.md
├── postgresql-migration-notes.md
└── conversation-*.jsonl
```

---

## HOW TO START THE APP

```bash
cd C:\Users\RayBishop\simple-crm
python app.py
```

Then open: http://localhost:5000

Or use: **Desktop shortcut → Start Steelstack CRM.bat**

---

## NEXT SESSION INSTRUCTIONS

At the start of a new conversation, tell Claude:
> "Read C:\Users\RayBishop\simple-crm\PROJECT_NOTES.md and get up to speed"

Or just double-click the batch file on your desktop - it will remind you.

---

## TODO (Next Steps When Ready)

- [ ] PostgreSQL migration for Railway deployment
- [ ] Import HubSpot contacts (waiting on data export)
- [ ] Test quote PDF payment link display

---

*This file helps Claude remember context between sessions.*
