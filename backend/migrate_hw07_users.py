"""HW7 Part 1: add `username` + `role` to the existing MySQL `users` table and seed one user per role.

Run from the repository root (MySQL container s6758-mysql must be up):
    python backend/migrate_hw07_users.py
Idempotent: columns are only added when missing, seed users are only inserted when missing.
Passwords are stored as salted PBKDF2 hashes (crud.hash_password), never as plain text.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text  # noqa: E402

from app.crud import hash_password  # noqa: E402
from app.database import engine  # noqa: E402

# Test accounts for this course project only (documented in README_HW7_RUN.md).
SEED_USERS = [
    ("reader1", "Reader One", "reader1@example.com", "Reader#6758", "reader"),
    ("writer1", "Writer One", "writer1@example.com", "Writer#6758", "writer"),
    ("moderator1", "Moderator One", "moderator1@example.com", "Moderator#6758", "moderator"),
]


def column_exists(conn, name: str) -> bool:
    return bool(conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = :c"
    ), {"c": name}).scalar())


def main() -> None:
    with engine.begin() as conn:
        if not column_exists(conn, "username"):
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100) NULL AFTER id"))
            print("added column users.username")
        if not column_exists(conn, "role"):
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN role ENUM('reader','writer','moderator') "
                "NOT NULL DEFAULT 'reader' AFTER password_hash"
            ))
            print("added column users.role")

        # Existing HW4 users get a username derived from their email (they keep role 'reader').
        for uid, email in conn.execute(text("SELECT id, email FROM users WHERE username IS NULL")).all():
            base = re.sub(r"[^a-z0-9_]", "_", email.split("@")[0].lower())[:90] or f"user{uid}"
            conn.execute(text("UPDATE users SET username = :u WHERE id = :i"), {"u": f"{base}_{uid}", "i": uid})
            print(f"backfilled username for user id {uid}")

        conn.execute(text("ALTER TABLE users MODIFY username VARCHAR(100) NOT NULL"))
        has_index = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() "
            "AND table_name = 'users' AND index_name = 'uq_users_username'"
        )).scalar()
        if not has_index:
            conn.execute(text("ALTER TABLE users ADD CONSTRAINT uq_users_username UNIQUE (username)"))
            print("added unique index on users.username")

        for username, name, email, password, role in SEED_USERS:
            exists = conn.execute(text("SELECT COUNT(*) FROM users WHERE username = :u"), {"u": username}).scalar()
            if exists:
                print(f"seed user {username} already present")
                continue
            conn.execute(text(
                "INSERT INTO users (username, name, email, password_hash, role) VALUES (:u, :n, :e, :p, :r)"
            ), {"u": username, "n": name, "e": email, "p": hash_password(password), "r": role})
            print(f"inserted {username} ({role})")

        rows = conn.execute(text("SELECT id, username, role, LEFT(password_hash, 20) FROM users ORDER BY id")).all()
    print("\nusers table now:")
    for r in rows:
        print(f"  id={r[0]:<3} username={r[1]:<22} role={r[2]:<10} password_hash={r[3]}...")


if __name__ == "__main__":
    main()
