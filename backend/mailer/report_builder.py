from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from generators.suggestion_model import DailySuggestions
from scrapers.base_scraper import TrendItem
from utils.date_utils import format_turkish_date, today_str
from utils.json_store import JsonStore
from utils.logger import get_logger
import config

logger = get_logger("report_builder")

TEMPLATE_DIR = Path(__file__).parent / "templates"


class ReportBuilder:
    """Builds HTML email reports from daily suggestions."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
        )

    def build(self, daily: DailySuggestions,
              trends: list[TrendItem] | None = None) -> str:
        """Build HTML report from daily suggestions."""
        template = self.env.get_template("daily_report.html")

        # Build highlights
        highlights = self._build_highlights(daily, trends)

        # Get search logs for today
        search_logs = self._get_today_logs()

        # Calculate stats
        suggestions = daily.suggestions
        avg_score = (sum(s.viral_score for s in suggestions) / len(suggestions)
                     if suggestions else 0)

        platforms_scraped = len(set(s.platform for s in suggestions))

        html = template.render(
            turkish_date=format_turkish_date(),
            highlights=highlights,
            suggestions=[s.to_dict() for s in suggestions],
            search_logs=search_logs,
            total_suggestions=len(suggestions),
            avg_viral_score=f"{avg_score:.0f}",
            trends_found=len(trends) if trends else 0,
            platforms_scraped=platforms_scraped,
            dashboard_url="http://localhost:3000",
        )

        logger.info(f"Email report built: {len(suggestions)} suggestions")
        return html

    def _build_highlights(self, daily: DailySuggestions,
                          trends: list[TrendItem] | None) -> list[dict]:
        """Build highlight items for the email header."""
        highlights = []

        # Top trends by platform
        if trends:
            platform_trends: dict[str, list[TrendItem]] = {}
            for t in trends:
                platform_trends.setdefault(t.platform, []).append(t)

            icons = {"pinterest": "📌", "instagram": "📸", "tiktok": "🎵"}
            for platform, items in platform_trends.items():
                if items:
                    top = items[0]
                    icon = icons.get(platform, "🔍")
                    highlights.append({
                        "icon": icon,
                        "text": f"{platform.title()}'ta \"{top.title[:50]}\" trendi yükselişte"
                    })

        # Suggestion count
        if daily.suggestions:
            avg_score = sum(s.viral_score for s in daily.suggestions) / len(daily.suggestions)
            highlights.append({
                "icon": "🎯",
                "text": f"Bugün {len(daily.suggestions)} öneri üretildi "
                        f"(ort. viral skor: {avg_score:.0f}/100)"
            })

        return highlights if highlights else [{
            "icon": "📊",
            "text": "Bugünkü içerik önerileri hazır!"
        }]

    def _get_today_logs(self) -> list[dict]:
        """Get today's search logs."""
        logs_data = JsonStore(config.SEARCH_LOGS_PATH).read()
        today = today_str()
        today_logs = []
        for log in logs_data.get("logs", []):
            if log.get("timestamp", "").startswith(today):
                today_logs.append(log)
        return today_logs

    def build_subject(self) -> str:
        """Build email subject line."""
        return f"Wellco Adult | {format_turkish_date()} - Günlük İçerik Stratejisi"
