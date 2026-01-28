# Simple CRM - Configuration Guide

## Quick Reference: What to Customize

This guide shows all the places you need to update with your own business information.

---

## 1. COMPANY BRANDING (PDF Quotes)

**File:** `pdf_generator.py`

### Company Name & Address (Line 365-369)
```python
company_address = """<b>YOUR COMPANY NAME</b><br/>
123 Your Street<br/>
Suite 100<br/>
Your City, ST 12345<br/>
United States"""
```

### PDF Title Banner (Line 147)
```python
title_text = f"YOUR COMPANY | {customer_name.upper()}"
```

### Brand Colors (Lines 17-19)
```python
BRAND_RED = colors.HexColor('#d80010')    # Your primary color
BRAND_DARK = colors.HexColor('#0a1622')   # Header background
BRAND_GRAY = colors.HexColor('#6b7280')   # Secondary text
```

---

## 2. PDF FILENAME

**File:** `app.py` (Line ~1360)

```python
filename = f"YOURCOMPANY_{safe_name}_{quote.get('quote_number', 'Quote')}.pdf"
```

---

## 3. LOGO

**File:** `static/logo.png`

Replace this file with your company logo. Recommended size: 400x100 pixels (PNG with transparent background)

---

## 4. WEBSITE THEME COLORS

**File:** `templates/base.html` (Lines 10-18)

```css
.gradient-bg {
    background: #0a1622;  /* Navigation bar color */
}
.btn-primary, .bg-slate-800 {
    background: #d80010 !important;  /* Button color */
}
.btn-primary:hover, .hover\:bg-slate-900:hover {
    background: #b8000d !important;  /* Button hover color */
}
```

---

## 5. TERMS & CONDITIONS

**File:** `templates/quote_edit.html` (Lines ~530-535)

Update the payment terms templates:
- 50/50 Payment Terms text
- 100% Upfront Payment text
- Your terms & conditions URL

---

## 6. SHIPPING ORIGIN

**File:** `shipping_calculator.py`

```python
DEFAULT_ORIGIN_ZIP = "37087"  # Change to your warehouse ZIP code
```

---

## 7. CONTACT FORM (Lead Capture)

**File:** `templates/forms.html` (Line 106)

```javascript
var SCRM_THANK_YOU_PAGE = 'https://www.yourwebsite.com/thank-you';
```

---

## 8. EMAIL INTEGRATION (Outlook)

**Location:** Settings > Email Integration in the app

You'll need:
- Microsoft Azure App Registration
- Client ID
- Client Secret
- Tenant ID

See `OUTLOOK_SETUP_GUIDE.md` for detailed instructions.

---

## 9. PAYMENT LINKS (Stripe)

No code changes needed. Just:
1. Create a Stripe account
2. Create payment links in Stripe Dashboard
3. Paste links into quotes

---

## 10. FINANCING LINKS (Approve)

No code changes needed. Just:
1. Set up your Approve account
2. Create financing applications
3. Paste links into quotes

---

## 11. DATABASE

**File:** `crm.db`

This SQLite file contains all your data:
- Contacts
- Companies
- Deals
- Quotes
- Products
- Users

**IMPORTANT:** Back this up regularly!

---

## Files to Backup Before Deploying

1. `crm.db` - Your database (all your data)
2. `static/logo.png` - Your logo
3. `outlook_config.json` - Outlook OAuth settings
4. `ga_config.json` - Google Analytics settings (if used)

---

## Deployment Checklist

- [ ] Update company name in `pdf_generator.py`
- [ ] Update company address in `pdf_generator.py`
- [ ] Update brand colors (optional)
- [ ] Replace `static/logo.png`
- [ ] Update PDF filename prefix in `app.py`
- [ ] Update shipping origin ZIP in `shipping_calculator.py`
- [ ] Update terms & conditions URLs
- [ ] Set up Outlook OAuth (or skip if not using email)
- [ ] Back up `crm.db`
- [ ] Deploy to Railway (or other host)

---

## Quick Color Reference

| Element | Current Color | Hex Code |
|---------|--------------|----------|
| Primary Red | ![#d80010](https://via.placeholder.com/15/d80010/d80010.png) | `#d80010` |
| Dark Background | ![#0a1622](https://via.placeholder.com/15/0a1622/0a1622.png) | `#0a1622` |
| Gray Text | ![#6b7280](https://via.placeholder.com/15/6b7280/6b7280.png) | `#6b7280` |

---

*Generated for Simple CRM - January 2026*
