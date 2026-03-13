"""
Content Generator - Scheduler (multi-brand)

Runs pipeline for ALL active brands daily.

Usage:
    python scheduler.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import schedule
import time
import config
import db
from main import run_pipeline, run_pinterest_pipeline
from utils.logger import get_logger

logger = get_logger("scheduler")


def _get_active_brands():
    """Return list of active brand dicts from DB."""
    with db.get_cursor() as cur:
        cur.execute("SELECT id, name FROM brands WHERE is_active = 1 ORDER BY id")
        return [dict(r) for r in cur.fetchall()]


def daily_job():
    """Run content pipeline for all active brands."""
    brands = _get_active_brands()
    logger.info(f"Daily job triggered for {len(brands)} brand(s)")
    for brand in brands:
        logger.info(f"  → Running pipeline for: {brand['name']} (id={brand['id']})")
        try:
            run_pipeline(brand_id=brand["id"])
        except Exception as e:
            logger.error(f"Pipeline failed for brand {brand['id']}: {e}")


def daily_pinterest_job():
    """Run Pinterest pipeline for all active brands."""
    brands = _get_active_brands()
    logger.info(f"Pinterest job triggered for {len(brands)} brand(s)")
    for brand in brands:
        logger.info(f"  → Pinterest pipeline for: {brand['name']} (id={brand['id']})")
        try:
            run_pinterest_pipeline(brand_id=brand["id"])
        except Exception as e:
            logger.error(f"Pinterest pipeline failed for brand {brand['id']}: {e}")


def main():
    db.init_db()

    run_time = config.DAILY_RUN_TIME
    logger.info(f"Scheduler started. Daily run at {run_time}")
    logger.info("Press Ctrl+C to stop")

    schedule.every().day.at(run_time).do(daily_job)

    hour, minute = map(int, run_time.split(":"))
    pin_minute = minute + 30
    pin_hour = hour
    if pin_minute >= 60:
        pin_minute -= 60
        pin_hour += 1
    pin_time = f"{pin_hour:02d}:{pin_minute:02d}"
    schedule.every().day.at(pin_time).do(daily_pinterest_job)
    logger.info(f"Pinterest pin scheduled at {pin_time}")

    # Run immediately if no data for today
    import datetime as dt
    today = dt.date.today().isoformat()

    with db.get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as c FROM suggestions WHERE date = ?", (today,))
        has_suggestions = cur.fetchone()["c"] > 0
        cur.execute("SELECT COUNT(*) as c FROM pins WHERE date = ?", (today,))
        has_pins = cur.fetchone()["c"] > 0

    if not has_suggestions:
        logger.info("No suggestions for today. Running pipeline now...")
        daily_job()

    if not has_pins:
        logger.info("No Pinterest pins for today. Generating now...")
        daily_pinterest_job()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
