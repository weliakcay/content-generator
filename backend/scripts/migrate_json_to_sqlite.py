"""Migration script: JSON files → SQLite database.

Run once from the backend/ directory:
    python scripts/migrate_json_to_sqlite.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend/ to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import config


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [WARN] Could not read {path}: {e}")
    return {}


def migrate() -> None:
    print("=== Wellco Content Generator: JSON → SQLite Migration ===\n")

    db.init_db()
    print("✓ Database initialized\n")

    # ── 1. Create Wellco Adult brand (id=1) ──────────────────────────────
    print("[1/5] Migrating brand profile...")
    brand_profile = _read_json(config.BRAND_PROFILE_PATH)
    tracking = _read_json(config.TRACKING_CONFIG_PATH)

    pinterest_dir = Path(__file__).parent.parent / "pinterest"
    pinterest_identity = _read_json(pinterest_dir / "brand_identity.json")

    with db.get_cursor() as cur:
        cur.execute("SELECT id FROM brands WHERE id = 1")
        exists = cur.fetchone()
        if exists:
            print("  Brand id=1 already exists, updating...")
            cur.execute(
                """UPDATE brands SET
                    name = ?, slug = ?, website_url = ?, description = ?,
                    profile_json = ?, tracking_json = ?, pinterest_identity_json = ?,
                    updated_at = datetime('now')
                   WHERE id = 1""",
                (
                    brand_profile.get("brand_name", "Wellco Adult"),
                    "wellco-adult",
                    pinterest_identity.get("website", "https://wellcoadult.com"),
                    "Wellco Adult - Wellness meets intimacy",
                    json.dumps(brand_profile),
                    json.dumps(tracking),
                    json.dumps(pinterest_identity),
                ),
            )
        else:
            cur.execute(
                """INSERT INTO brands
                    (id, name, slug, website_url, description, profile_json,
                     tracking_json, pinterest_identity_json)
                   VALUES (1, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    brand_profile.get("brand_name", "Wellco Adult"),
                    "wellco-adult",
                    pinterest_identity.get("website", "https://wellcoadult.com"),
                    "Wellco Adult - Wellness meets intimacy",
                    json.dumps(brand_profile),
                    json.dumps(tracking),
                    json.dumps(pinterest_identity),
                ),
            )
    print("  ✓ Wellco Adult brand (id=1) migrated\n")

    # ── 2. Migrate suggestions ────────────────────────────────────────────
    print("[2/5] Migrating suggestions...")
    suggestions_dir = config.SUGGESTIONS_DIR
    suggestion_count = 0

    if suggestions_dir.exists():
        for f in sorted(suggestions_dir.glob("*.json")):
            data = _read_json(f)
            date = data.get("date", f.stem)
            generated_at = data.get("generated_at", "")
            email_sent = 1 if data.get("email_sent") else 0
            email_sent_at = data.get("email_sent_at")

            for s in data.get("suggestions", []):
                with db.get_cursor() as cur:
                    cur.execute(
                        """INSERT OR IGNORE INTO suggestions
                            (id, brand_id, date, platform, content_type, title, caption,
                             hashtags, visual_concept, cta, publish_time, publish_reason,
                             similar_examples, viral_score, trend_source, feedback,
                             feedback_reason, feedback_at, generated_at, email_sent, email_sent_at)
                           VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            s.get("id"),
                            date,
                            s.get("platform"),
                            s.get("content_type"),
                            s.get("title"),
                            s.get("caption"),
                            json.dumps(s.get("hashtags", [])),
                            s.get("visual_concept"),
                            s.get("cta"),
                            s.get("publish_time"),
                            s.get("publish_reason"),
                            json.dumps(s.get("similar_examples", [])),
                            s.get("viral_score", 0),
                            s.get("trend_source"),
                            s.get("feedback"),
                            s.get("feedback_reason"),
                            s.get("feedback_at"),
                            generated_at,
                            email_sent,
                            email_sent_at,
                        ),
                    )
                suggestion_count += 1
    print(f"  ✓ {suggestion_count} suggestions migrated\n")

    # ── 3. Migrate pins ───────────────────────────────────────────────────
    print("[3/5] Migrating Pinterest pins...")
    pins_dir = config.DATA_DIR / "pins"
    pin_count = 0

    if pins_dir.exists():
        for f in sorted(pins_dir.glob("*.json")):
            data = _read_json(f)
            date = data.get("date", f.stem)

            for p in data.get("pins", []):
                with db.get_cursor() as cur:
                    cur.execute(
                        """INSERT OR IGNORE INTO pins
                            (id, brand_id, date, board, theme, pin_title, pin_description,
                             hashtags, pinterest_tags, file_name, alt_text, visual_prompt,
                             topic, keywords, style_code, style_name, palette_code,
                             palette_name, palette_colors, posting_time, special_day, created_at)
                           VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            p.get("id"),
                            date,
                            p.get("board"),
                            p.get("theme"),
                            p.get("pin_title"),
                            p.get("pin_description"),
                            json.dumps(p.get("hashtags", [])),
                            json.dumps(p.get("pinterest_tags", [])),
                            p.get("file_name"),
                            p.get("alt_text"),
                            p.get("visual_prompt"),
                            p.get("topic"),
                            json.dumps(p.get("keywords", [])),
                            p.get("style_code"),
                            p.get("style_name"),
                            p.get("palette_code"),
                            p.get("palette_name"),
                            json.dumps(p.get("palette_colors", {})),
                            p.get("posting_time"),
                            p.get("special_day"),
                            p.get("created_at"),
                        ),
                    )
                pin_count += 1
    print(f"  ✓ {pin_count} pins migrated\n")

    # ── 4. Migrate feedback ───────────────────────────────────────────────
    print("[4/5] Migrating feedback...")
    feedback_data = _read_json(config.FEEDBACK_PATH)
    feedback_count = 0

    for item in feedback_data.get("approved_suggestions", []):
        with db.get_cursor() as cur:
            cur.execute(
                """INSERT OR IGNORE INTO feedback
                    (brand_id, suggestion_id, action, platform, content_type, reason, feedback_at)
                   VALUES (1, ?, 'liked', ?, ?, ?, ?)""",
                (
                    item.get("id"),
                    item.get("platform"),
                    item.get("content_type"),
                    item.get("reason"),
                    item.get("feedback_at"),
                ),
            )
        feedback_count += 1

    for item in feedback_data.get("rejected_suggestions", []):
        with db.get_cursor() as cur:
            cur.execute(
                """INSERT OR IGNORE INTO feedback
                    (brand_id, suggestion_id, action, platform, content_type, reason, feedback_at)
                   VALUES (1, ?, 'disliked', ?, ?, ?, ?)""",
                (
                    item.get("id"),
                    item.get("platform"),
                    item.get("content_type"),
                    item.get("reason"),
                    item.get("feedback_at"),
                ),
            )
        feedback_count += 1
    print(f"  ✓ {feedback_count} feedback records migrated\n")

    # ── 5. Migrate search logs ────────────────────────────────────────────
    print("[5/5] Migrating search logs...")
    logs_data = _read_json(config.SEARCH_LOGS_PATH)
    log_count = 0

    for log in logs_data.get("logs", []):
        with db.get_cursor() as cur:
            cur.execute(
                """INSERT INTO search_logs
                    (brand_id, platform, query, results_count, top_results, status, logged_at)
                   VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (
                    log.get("platform"),
                    log.get("query"),
                    log.get("results_count", 0),
                    json.dumps(log.get("top_results", [])),
                    log.get("status", "success"),
                    log.get("timestamp"),
                ),
            )
        log_count += 1
    print(f"  ✓ {log_count} search log entries migrated\n")

    # ── Verify ────────────────────────────────────────────────────────────
    print("=== Verification ===")
    with db.get_cursor() as cur:
        cur.execute("SELECT id, name, slug FROM brands")
        brands = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) as c FROM suggestions")
        s_count = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) as c FROM pins")
        p_count = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) as c FROM feedback")
        f_count = cur.fetchone()["c"]

    print(f"  Brands:      {brands}")
    print(f"  Suggestions: {s_count}")
    print(f"  Pins:        {p_count}")
    print(f"  Feedback:    {f_count}")
    print(f"\n✓ Migration complete! DB: {config.DB_PATH}\n")


if __name__ == "__main__":
    migrate()
