# CRM Login System Guide

## What This Does

- **Login wall** - Users must log in to access the CRM
- **Two roles:** Admin and Salesperson
- **Admins can:** Manage users, see everything
- **Salespeople can:** Use the CRM, connect their own email

---

## First Time Setup

When you first run the CRM with no users:

1. Go to `http://localhost:5000`
2. You'll be redirected to the **Setup** page
3. Create your first admin account:
   - Username
   - Password (min 6 characters)
   - Email (optional)
   - First/Last name (optional)
4. Click Create - you're now logged in as admin

---

## Managing Users

**As an admin:**

1. Click **Settings** in the top nav
2. Click **User Management**
3. From here you can:
   - **Add users** - Click "+ Add User"
   - **Edit users** - Click on a user
   - **Delete users** - Click delete (can't delete yourself)
   - **Deactivate users** - Uncheck "Active" when editing

**When adding a user:**
- Username (required, must be unique)
- Password (required, min 6 characters)
- Email (optional)
- First/Last name (optional)
- Role: Admin or Salesperson

---

## Locked Out? Password Reset

If you forget your password or get locked out:

1. Open a command prompt in the simple-crm folder
2. Run: `py reset_admin.py`
3. Follow the prompts to:
   - Reset an existing admin's password, OR
   - Create a new admin account

**Emergency nuclear option:**
```
py reset_admin.py --force
```
This deletes ALL users and lets you start fresh (use with caution!)

---

## How It Works (Technical)

**Database:**
- Users stored in `users` table
- Passwords are hashed with SHA-256 + salt (never stored in plain text)
- Sessions tracked via Flask session cookie

**Protected Routes:**
- Most pages require `@login_required` decorator
- Admin-only pages use `@admin_required` decorator
- If not logged in, redirects to `/login`

**Session Data:**
- `user_id` - current user's ID
- `user_role` - 'admin' or 'salesperson'
- `username` - for display

---

## Moving to Another Server

The login system is self-contained:

**What moves with CRM data:**
- Nothing related to auth - it stays behind

**What stays on the server:**
- `users` table (usernames, hashed passwords)
- `user_email_tokens` table (Outlook connections)

This means when you migrate CRM data to another system, you don't carry over user accounts - you set them up fresh on the new system.

---

## Security Notes

- Passwords are **never** stored in plain text
- Each password has a unique salt
- Sessions expire when browser closes
- Failed logins show generic error (doesn't reveal if username exists)
- Admin role required for user management

---

## Files Involved

| File | Purpose |
|------|---------|
| `database.py` | User table, auth functions (hash_password, authenticate_user, etc.) |
| `app.py` | Login/logout routes, @login_required decorator |
| `templates/login.html` | Login page |
| `templates/setup.html` | First-time admin setup |
| `templates/users.html` | User management list |
| `templates/user_form.html` | Add/edit user form |
| `reset_admin.py` | Password recovery script |

---

## Quick Reference

**Login URL:** `http://localhost:5000/login`
**User Management:** `http://localhost:5000/settings/users` (admin only)
**Password Reset:** `py reset_admin.py`

**Default after setup:** You're the admin. Create salesperson accounts for your team.
