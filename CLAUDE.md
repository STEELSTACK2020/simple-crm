# Simple CRM - Claude Context

## Project Overview
- **App:** Steelstack CRM (Flask + PostgreSQL)
- **Owner:** Ray Bishop
- **Company:** Steelstack (steel storage racks), part of Morrison Industries
- **GitHub:** github.com/STEELSTACK2020/simple-crm
- **Live URL:** https://simple-crm-production-36ba.up.railway.app/
- **Local:** http://localhost:5000

## Deployment
- Railway auto-deploys from GitHub on push
- Deploy command: `git add . && git commit -m "message" && git push origin main`
- Railway runs via `Procfile`: `web: gunicorn app:app --bind 0.0.0.0:$PORT`
- Database: PostgreSQL on Railway (connected via `DATABASE_URL` env var)
- Locally: SQLite fallback (`crm.db`) when no `DATABASE_URL` is set

## Key Files
- `app.py` - Main Flask app (routes, API, templates)
- `database.py` - All database functions (supports PostgreSQL + SQLite)
- `pdf_generator.py` - Quote PDF generation (Steelstack branding)
- `email_integration.py` - Outlook/Gmail OAuth email integration
- `shipping_calculator.py` - ZIP code distance + shipping cost
- `analytics_ga.py` - Google Analytics 4 integration
- `templates/` - All HTML templates (Jinja2)
- `static/` - Logo, CSS

## Features
- Contacts, Companies, Deals pipeline (kanban), Quotes with PDF export
- Product catalog (25 Steelstack products)
- Shipping calculator (OSRM routing)
- UTM tracking (source/medium/campaign flows through quotes > deals > contacts)
- Outlook email integration (OAuth, Morrison Industries Azure tenant)
- Google Analytics traffic dashboard (multi-site)
- Embeddable lead capture form for Squarespace
- User login system with @login_required on all routes
- Salespeople management
- Analytics dashboard with charts (Chart.js)

## Tech Stack
- Backend: Python 3, Flask, Gunicorn
- Database: PostgreSQL (Railway) / SQLite (local)
- Frontend: HTML, Tailwind CSS (CDN), Chart.js (CDN)
- PDF: ReportLab
- Dependencies: see `requirements.txt`

## Azure/Outlook Config
- Azure App: Steelstack CRM
- Client ID: b790c0a2-934f-4541-a4d8-cf2c73c16190
- Tenant: Morrison Industries
- API Secret expires: January 20, 2028

## Notes
- See `PROJECT_NOTES.md` for detailed session history and decisions
- See `README.md` for full API docs and database schema
- Backups stored at `C:\Users\RayBishop\backups\`
