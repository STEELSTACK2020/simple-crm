"""
Admin Password Reset Script
Use this if you get locked out of the CRM.

Usage:
    py reset_admin.py

This will either:
1. Reset the password for an existing admin user
2. Create a new admin user if none exists
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from database import (
    init_database, get_all_users, add_user, update_user,
    get_user_by_username, hash_password, get_connection
)


def reset_admin():
    """Reset or create admin account."""
    print("\n" + "=" * 50)
    print("  Simple CRM - Admin Recovery Tool")
    print("=" * 50 + "\n")

    # Make sure database is initialized
    init_database()

    # Get existing users
    users = get_all_users()
    admin_users = [u for u in users if u['role'] == 'admin']

    if admin_users:
        print(f"Found {len(admin_users)} admin user(s):")
        for i, user in enumerate(admin_users, 1):
            print(f"  {i}. {user['username']} ({user['email'] or 'no email'})")

        print("\nOptions:")
        print("  1. Reset password for existing admin")
        print("  2. Create new admin user")
        print("  3. Exit")

        choice = input("\nEnter choice (1-3): ").strip()

        if choice == '1':
            if len(admin_users) == 1:
                user = admin_users[0]
            else:
                idx = input(f"Enter admin number (1-{len(admin_users)}): ").strip()
                try:
                    user = admin_users[int(idx) - 1]
                except:
                    print("Invalid selection.")
                    return

            new_password = input(f"Enter new password for '{user['username']}': ").strip()
            if len(new_password) < 6:
                print("Password must be at least 6 characters.")
                return

            # Update password directly in database
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET password_hash = ? WHERE id = ?
            """, (hash_password(new_password), user['id']))
            conn.commit()
            conn.close()

            print(f"\n✓ Password reset for '{user['username']}'")
            print(f"  You can now login with the new password.\n")

        elif choice == '2':
            create_new_admin()
        else:
            print("Exiting.")
            return
    else:
        print("No admin users found.")
        create_new_admin()


def create_new_admin():
    """Create a new admin user."""
    print("\nCreate new admin account:")

    username = input("  Username: ").strip()
    if not username:
        print("Username is required.")
        return

    # Check if username exists
    if get_user_by_username(username):
        print(f"Username '{username}' already exists.")
        return

    password = input("  Password (min 6 chars): ").strip()
    if len(password) < 6:
        print("Password must be at least 6 characters.")
        return

    email = input("  Email (optional): ").strip() or None
    first_name = input("  First name (optional): ").strip() or None
    last_name = input("  Last name (optional): ").strip() or None

    result = add_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role='admin'
    )

    if result['success']:
        print(f"\n✓ Admin user '{username}' created successfully!")
        print(f"  You can now login with this account.\n")
    else:
        print(f"\n✗ Failed to create user: {result['error']}\n")


def force_reset():
    """Emergency reset - deletes all users and creates fresh admin."""
    print("\n⚠️  EMERGENCY RESET - This will delete ALL users!")
    confirm = input("Type 'DELETE ALL USERS' to confirm: ").strip()

    if confirm != 'DELETE ALL USERS':
        print("Cancelled.")
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()

    print("\nAll users deleted. Creating new admin...")
    create_new_admin()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        force_reset()
    else:
        reset_admin()
