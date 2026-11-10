"""
Script to reset or set user password in PostgreSQL database directly.
Usage:
    python scripts/reset_user_password.py <username> <new_password>
Example:
    python scripts/reset_user_password.py admin change_me_admin_password
    python scripts/reset_user_password.py cashier cashier123
"""
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.core.database import sync_engine
from app.core.security import hash_password


def reset_password(username: str, plain_password: str) -> bool:
    hashed = hash_password(plain_password)
    print(f"[*] Hashing password for '{username}'...")

    with sync_engine.begin() as conn:
        # 1. Check data.users
        schema = "data"
        res = None
        try:
            res = conn.execute(
                text("SELECT id, username, email, status FROM data.users WHERE username = :u"),
                {"u": username},
            ).fetchone()
        except Exception:
            pass

        if not res:
            # 2. Check public.users
            try:
                res = conn.execute(
                    text("SELECT id, username, email, status FROM public.users WHERE username = :u"),
                    {"u": username},
                ).fetchone()
                if res:
                    schema = "public"
            except Exception:
                pass

        if not res:
            print(f"[ERROR] User '{username}' was not found in either data.users or public.users.")
            # List available users
            for s in ("data", "public"):
                try:
                    all_users = conn.execute(
                        text(f"SELECT username, email, status FROM {s}.users LIMIT 20")
                    ).fetchall()
                    if all_users:
                        print(f"[*] Available users in {s}.users:")
                        for row in all_users:
                            print(f"    - {row[0]} ({row[1]}, status={row[2]})")
                except Exception:
                    pass
            return False

        # Update password and ensure status is ACTIVE
        conn.execute(
            text(f"UPDATE {schema}.users SET hashed_password = :h, status = 'ACTIVE' WHERE username = :u"),
            {"h": hashed, "u": username},
        )
        print(f"[SUCCESS] User '{username}' in {schema}.users password updated to '{plain_password}' and status set to 'ACTIVE'.")
        return True


if __name__ == "__main__":
    target_user = sys.argv[1] if len(sys.argv) > 1 else "admin"
    target_pass = sys.argv[2] if len(sys.argv) > 2 else "change_me_admin_password"
    reset_password(target_user, target_pass)
