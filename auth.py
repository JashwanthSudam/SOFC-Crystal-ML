"""Accounts, sign-in tokens and saved searches (SQLite). Passwords are stored as salted hashes, never as text."""
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).parent

# Vercel's deployed application directory is read-only. Always use /tmp
# on Vercel, even if an old relative DB_PATH environment variable is set.
# IMPORTANT: /tmp is ephemeral; use a hosted database for durable production data.
if os.environ.get("VERCEL") == "1":
    DB = Path("/tmp/kstar-app-data/app.db")
elif os.environ.get("DB_PATH"):
    DB = Path(os.environ["DB_PATH"])
else:
    DB = BASE / "data" / "app.db"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOKEN_DAYS = 7
# The one and only developer account. Change it on a public host with DEV_EMAIL and DEV_PASSWORD.
DEV_EMAIL = os.environ.get("DEV_EMAIL", "dev@gmail.com")
DEV_PASSWORD = os.environ.get("DEV_PASSWORD", "dev@1234")


def _secret():
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    f = DB.parent / "secret.key"
    DB.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


def conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init():
    with closing(conn()) as c, c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','dev')), created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS searches(
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, temp_c REAL, model TEXT,
                log_kstar REAL, kstar REAL, detail TEXT);""")


IST = timezone(timedelta(hours=5, minutes=30), "IST")


def _now():
    """Current time in Indian Standard Time, stored as ISO text with the +05:30 offset."""
    return datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S+05:30")


def clean_email(email):
    email = str(email or "").strip().lower()
    if email.endswith("@gmail"):  # allow the short form name@gmail
        email += ".com"
    if not EMAIL_RE.match(email) or len(email) > 120:
        raise ValueError("Enter a valid email address, for example name@gmail.com.")
    return email


def create_user(email, password, role="user"):
    email = clean_email(email)
    password = str(password or "")
    if not 8 <= len(password) <= 128:
        raise ValueError("Use a password of at least 8 characters.")
    try:
        with closing(conn()) as c, c:
            cur = c.execute("INSERT INTO users(email, pw_hash, role, created) VALUES (?,?,?,?)",
                            (email, generate_password_hash(password), role, _now()))
            return {"id": cur.lastrowid, "email": email, "role": role}
    except sqlite3.IntegrityError:
        raise ValueError("That email is already registered. Try signing in.")


def upsert_developer(email, password):
    email = clean_email(email)
    if len(str(password or "")) < 6:  # developer accounts are made by the owner; users still need 8
