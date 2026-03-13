"""
Content Generator - Daily Pipeline (multi-brand)

Usage:
    python main.py                    # Full pipeline (brand_id=1)
    python main.py --brand-id 2       # Specific brand
    python main.py --no-scrape        # Skip scraping
    python main.py --no-email         # Skip email
    python main.py --pinterest        # Pinterest pipeline only
"""
from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List

sys.path.insert(0, str(Path(__file__).parent))

import config
import db
from scrapers import ScraperFactory
from scrapers.base_scraper import TrendItem
from analyzers.trend_analyzer import TrendAnalyzer
from analyzers.pattern_learner import PatternLearner
from generators.prompt_builder import PromptBuilder
from generators.content_generator import ContentGenerator
from mailer.report_builder import ReportBuilder
from mailer.email_sender import EmailSender
from utils.date_utils import now_str, today_str
from utils.logger import get_logger

logger = get_logger("pipeline")


def _load_brand(brand_id: int = 1) -> dict:
    """Load brand profile and tracking config from SQLite."""
    with db.get_cursor() as cur:
        cur.execute("SELECT name, profile_json, tracking_json FROM brands WHERE id = ?", (brand_id,))
        row = cur.fetchone()
    if not row:
        raise ValueError(f"Brand {brand_id} not found in database")
    return {
        "name": row["name"],
        "profile": json.loads(row["profile_json"] or "{}"),
        "tracking": json.loads(row["tracking_json"] or "{}"),
    }


def log_search(platform: str, query: str, results: List[TrendItem], brand_id: int = 1) -> None:
    """Log a search to SQLite search_logs table."""
    with db.get_cursor() as cur:
        cur.execute(
            """INSERT INTO search_logs
                (brand_id, platform, query, results_count, top_results, status, logged_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                brand_id,
                platform,
                query,
                len(results),
                json.dumps([
                    {
                        "title": r.title[:100],
                        "url": r.url,
                        "viral_score": r.viral_score,
                        "engagement_rate": r.engagement_rate,
                    }
                    for r in sorted(results, key=lambda x: x.viral_score, reverse=True)[:5]
                ]),
                "success" if results else "empty",
                now_str(),
            ),
        )


def run_scraping(tracking_config: dict, brand_id: int = 1) -> List[TrendItem]:
    """Run scrapers for all platforms."""
    all_trends: List[TrendItem] = []

    for platform in ScraperFactory.available_platforms():
        logger.info(f"Scraping {platform}...")
        try:
            scraper = ScraperFactory.create(platform)
            trends = scraper.run(tracking_config)
            all_trends.extend(trends)

            hashtags = [h["tag"] for h in tracking_config.get("hashtags", [])
                        if h.get("platform") == platform]
            keywords = [k["keyword"] for k in tracking_config.get("keywords", [])
                        if platform in k.get("platforms", [])]

            for query in hashtags + keywords:
                matching = [t for t in trends
                            if query.lstrip("#").lower() in (t.title + t.description).lower()]
                log_search(platform, query, matching, brand_id)

            logger.info(f"{platform}: {len(trends)} trends found")
        except Exception as e:
            logger.error(f"{platform} scraping failed: {e}")
            log_search(platform, "ERROR", [], brand_id)

    return all_trends


def run_pipeline(brand_id: int = 1, skip_scrape: bool = False, skip_email: bool = False) -> None:
    """Run the complete daily pipeline for a brand."""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Pipeline started at {start_time.isoformat()} for brand_id={brand_id}")

    # Load brand from DB
    brand_data = _load_brand(brand_id)
    brand_profile = brand_data["profile"]
    tracking_config = brand_data["tracking"]
    logger.info(f"Brand: {brand_data['name']}")

    # Scrape
    all_trends: List[TrendItem] = []
    if not skip_scrape:
        all_trends = run_scraping(tracking_config, brand_id)
        logger.info(f"Total trends scraped: {len(all_trends)}")
    else:
        logger.info("Scraping skipped (--no-scrape)")

    # Analyze trends
    top_trends = TrendAnalyzer.analyze(all_trends, brand_profile)
    logger.info(f"Top {len(top_trends)} trends selected")

    # Load learned patterns
    patterns = PatternLearner.load_patterns(brand_id)
    patterns_text = PatternLearner.format_for_prompt(patterns)

    # Generate content suggestions
    prompt = PromptBuilder.build(brand_profile, top_trends, patterns_text,
                                  suggestions_count=config.SUGGESTIONS_COUNT)
    generator = ContentGenerator()
    daily = generator.generate(prompt, brand_id)
    logger.info(f"Generated {len(daily.suggestions)} suggestions")

    # Send email
    if not skip_email:
        builder = ReportBuilder()
        html = builder.build(daily, top_trends)
        subject = builder.build_subject()
        sender = EmailSender()
        sent = sender.send(html, subject)

        if sent:
            # Update email_sent flag in DB
            with db.get_cursor() as cur:
                cur.execute(
                    "UPDATE suggestions SET email_sent = 1, email_sent_at = ? WHERE brand_id = ? AND date = ?",
                    (now_str(), brand_id, daily.date),
                )
    else:
        logger.info("Email skipped (--no-email)")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Pipeline completed in {elapsed:.1f}s")
    logger.info("=" * 60)


def run_pinterest_pipeline(brand_id: int = 1, skip_email: bool = False) -> None:
    """Run the daily Pinterest pin generation pipeline for a brand."""
    from pinterest.pin_generator import generate_pin_content
    from pinterest.pin_email import send_pin_email

    start_time = datetime.now()
    logger.info(f"Pinterest pipeline started for brand_id={brand_id}")

    pin = generate_pin_content(brand_id=brand_id)

    if pin:
        logger.info(f"Pin generated: '{pin.get('pin_title', '')}'")
        if not skip_email:
            send_pin_email(pin)
    else:
        logger.error("Pin generation failed")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Pinterest pipeline completed in {elapsed:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Content Generator Pipeline")
    parser.add_argument("--brand-id", type=int, default=1, help="Brand ID to run pipeline for")
    parser.add_argument("--no-scrape", action="store_true", help="Skip scraping")
    parser.add_argument("--no-email", action="store_true", help="Skip email")
    parser.add_argument("--pinterest", action="store_true", help="Run Pinterest pipeline")
    args = parser.parse_args()

    db.init_db()

    if args.pinterest:
        run_pinterest_pipeline(brand_id=args.brand_id, skip_email=args.no_email)
    else:
        run_pipeline(brand_id=args.brand_id, skip_scrape=args.no_scrape, skip_email=args.no_email)


if __name__ == "__main__":
    main()
