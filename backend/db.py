"""SQLite database module - thread-safe, WAL mode, multi-brand support."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import config

_local = threading.local()

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS brands (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL,
    slug                    TEXT UNIQUE NOT NULL,
    website_url             TEXT,
    description             TEXT,
    profile_json            TEXT NOT NULL DEFAULT '{}',
    identity_json           TEXT NOT NULL DEFAULT '{}',
    tracking_json           TEXT NOT NULL DEFAULT '{}',
    pinterest_identity_json TEXT NOT NULL DEFAULT '{}',
    is_active               INTEGER NOT NULL DEFAULT 1,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suggestions (
    id              TEXT PRIMARY KEY,
    brand_id        INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    date            TEXT NOT NULL,
    platform        TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    title           TEXT NOT NULL,
    caption         TEXT,
    hashtags        TEXT NOT NULL DEFAULT '[]',
    visual_concept  TEXT,
    cta             TEXT,
    publish_time    TEXT,
    publish_reason  TEXT,
    similar_examples TEXT NOT NULL DEFAULT '[]',
    viral_score     REAL DEFAULT 0,
    trend_source    TEXT,
    feedback        TEXT,
    feedback_reason TEXT,
    feedback_at     TEXT,
    generated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    email_sent      INTEGER NOT NULL DEFAULT 0,
    email_sent_at   TEXT
);

CREATE TABLE IF NOT EXISTS pins (
    id              TEXT PRIMARY KEY,
    brand_id        INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    date            TEXT NOT NULL,
    board           TEXT,
    theme           TEXT,
    pin_title       TEXT,
    pin_description TEXT,
    hashtags        TEXT NOT NULL DEFAULT '[]',
    pinterest_tags  TEXT NOT NULL DEFAULT '[]',
    file_name       TEXT,
    alt_text        TEXT,
    visual_prompt   TEXT,
    topic           TEXT,
    keywords        TEXT NOT NULL DEFAULT '[]',
    style_code      TEXT,
    style_name      TEXT,
    palette_code    TEXT,
    palette_name    TEXT,
    palette_colors  TEXT NOT NULL DEFAULT '{}',
    posting_time    TEXT,
    special_day     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id        INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    suggestion_id   TEXT REFERENCES suggestions(id),
    action          TEXT NOT NULL,
    platform        TEXT,
    content_type    TEXT,
    reason          TEXT,
    feedback_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id        INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    query           TEXT NOT NULL,
    results_count   INTEGER DEFAULT 0,
    top_results     TEXT NOT NULL DEFAULT '[]',
    status          TEXT DEFAULT 'success',
    logged_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trends (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id        INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    date            TEXT NOT NULL,
    platform        TEXT NOT NULL,
    title           TEXT,
    description     TEXT,
    url             TEXT,
    viral_score     REAL DEFAULT 0,
    engagement_rate REAL DEFAULT 0,
    raw_json        TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_suggestions_brand_date ON suggestions(brand_id, date);
CREATE INDEX IF NOT EXISTS idx_suggestions_feedback ON suggestions(brand_id, feedback);
CREATE INDEX IF NOT EXISTS idx_pins_brand_date ON pins(brand_id, date);
CREATE INDEX IF NOT EXISTS idx_feedback_brand ON feedback(brand_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_brand ON search_logs(brand_id);
CREATE INDEX IF NOT EXISTS idx_trends_brand_date ON trends(brand_id, date);
"""


def _get_db_path() -> str:
    return str(config.DB_PATH)


def get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(
            _get_db_path(),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


@contextmanager
def get_cursor() -> Iterator[sqlite3.Cursor]:
    """Context manager: yields cursor, auto-commits or rolls back."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def init_db() -> None:
    """Create all tables if they don't exist."""
    # Ensure data dir exists
    Path(_get_db_path()).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
