"""Accounts, sign-in tokens and saved searches.
Uses Postgres when DATABASE_URL is set (needed on Vercel), otherwise a local SQLite file.
Passwords are stored as salted hashes, never as text."""
import json
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # only needed when DATABASE_URL is set
    psycopg2 = None

BASE = Path(__file__).parent
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
USE_PG = bool(DATABASE_URL)

# Local SQLite path (used only when DATABASE_URL is not set).
if os.environ.get("VERCEL"):
    DB = Path(os.environ.get("DB_PATH") or "/tmp/app.db")
else:
    DB = Path(os.environ.get("DB_PATH") or BASE / "data" / "app.db")

INTEGRITY_ERRORS = (sqlite3.IntegrityError,) + ((psycopg2.IntegrityError,) if psycopg2 else ())
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


class _Conn:
    """Small wrapper so the same code runs on SQLite and Postgres."""

    def __init__(self):
        if USE_PG:
            if psycopg2 is None:
                raise RuntimeError("DATABASE_URL is set but psycopg2 is not installed. "
                                   "Add psycopg2-binary to requirements.txt.")
            self.raw = psycopg2.connect(DATABASE_URL)
        else:
            DB.parent.mkdir(parents=True, exist_ok=True)
            self.raw = sqlite3.connect(DB)
            self.raw.row_factory = sqlite3.Row
            self.raw.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql, params=()):
        if USE_PG:
            cur = self.raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql.replace("?", "%s"), params)
            return cur
        return self.raw.execute(sql, params)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.raw.rollback()
        else:
            self.raw.commit()
        return False

    def close(self):
        self.raw.close()


def conn():
    return _Conn()


def _insert(c, sql, params):
    """Run an INSERT and return the new row id on either database."""
    if USE_PG:
        return c.execute(sql + " RETURNING id", params).fetchone()["id"]
    return c.execute(sql, params).lastrowid


SCHEMA_SQLITE = """
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user','dev')), created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS searches(
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, temp_c REAL, model TEXT,
        log_kstar REAL, kstar REAL, detail TEXT);"""

SCHEMA_PG = [
    """CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user','dev')), created TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS searches(
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, temp_c DOUBLE PRECISION, model TEXT,
        log_kstar DOUBLE PRECISION, kstar DOUBLE PRECISION, detail TEXT)""",
]


def init():
    with closing(conn()) as c, c:
        if USE_PG:
            for stmt in SCHEMA_PG:
                c.execute(stmt)
        else:
            c.raw.executescript(SCHEMA_SQLITE)


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
            new_id = _insert(c, "INSERT INTO users(email, pw_hash, role, created) VALUES (?,?,?,?)",
                             (email, generate_password_hash(password), role, _now()))
            return {"id": new_id, "email": email, "role": role}
    except INTEGRITY_ERRORS:
        raise ValueError("That email is already registered. Try signing in.")


def upsert_developer(email, password):
    email = clean_email(email)
    if len(str(password or "")) < 6:  # developer accounts are made by the owner; users still need 8
        raise ValueError("Use a password of at least 6 characters.")
    with closing(conn()) as c, c:
        c.execute("INSERT INTO users(email, pw_hash, role, created) VALUES (?,?,'dev',?) "
                  "ON CONFLICT(email) DO UPDATE SET pw_hash=excluded.pw_hash, role='dev'",
                  (email, generate_password_hash(password), _now()))


def seed_developer():
    """Make sure exactly one developer account exists, with the configured email and password."""
    upsert_developer(DEV_EMAIL, DEV_PASSWORD)
    with closing(conn()) as c, c:
        c.execute("DELETE FROM users WHERE role='dev' AND email<>?", (clean_email(DEV_EMAIL),))


def check_login(email, password, role):
    try:
        email = clean_email(email)
    except ValueError:
        return None
    with closing(conn()) as c, c:
        row = c.execute("SELECT * FROM users WHERE email=? AND role=?", (email, role)).fetchone()
    if row and check_password_hash(row["pw_hash"], str(password or "")):
        return {"id": row["id"], "email": row["email"], "role": row["role"]}
    return None


def _ser():
    return URLSafeTimedSerializer(_secret(), salt="kstar-auth")


def make_token(user):
    return _ser().dumps({"id": user["id"], "role": user["role"], "email": user["email"]})


def user_from_header(header):
    if not str(header).startswith("Bearer "):
        return None
    try:
        data = _ser().loads(header[7:], max_age=TOKEN_DAYS * 86400)
    except (BadSignature, SignatureExpired):
        return None
    with closing(conn()) as c, c:  # the account must still exist
        row = c.execute("SELECT id, email, role FROM users WHERE id=?", (data["id"],)).fetchone()
    return dict(row) if row else None


def add_search(user_id, kind, label, temp_c, model, log_kstar, kstar, detail=None):
    with closing(conn()) as c, c:
        return _insert(c, "INSERT INTO searches(user_id, created, kind, label, temp_c, model, log_kstar, kstar, detail) "
                          "VALUES (?,?,?,?,?,?,?,?,?)",
                       (user_id, _now(), kind, str(label)[:200], temp_c, model, log_kstar, kstar,
                        json.dumps(detail) if detail is not None else None))


def list_searches(user_id, limit=200):
    with closing(conn()) as c, c:
        rows = c.execute("SELECT id, created, kind, label, temp_c, model, log_kstar, kstar FROM searches "
                         "WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def delete_search(user_id, sid):
    with closing(conn()) as c, c:
        return c.execute("DELETE FROM searches WHERE id=? AND user_id=?", (sid, user_id)).rowcount


def clear_searches(user_id):
    with closing(conn()) as c, c:
        c.execute("DELETE FROM searches WHERE user_id=?", (user_id,))


def count_searches():
    with closing(conn()) as c, c:
        return c.execute("SELECT COUNT(*) AS n FROM searches").fetchone()["n"]
