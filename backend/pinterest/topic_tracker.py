from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from utils.logger import get_logger
from utils.json_store import JsonStore

logger = get_logger("topic_tracker")

PINTEREST_DIR = Path(__file__).parent
TOPICS_PATH = PINTEREST_DIR / "topic_history.json"
NO_REPEAT_DAYS = 45


class TopicTracker:
    """Tracks used topics to prevent repetition within 45 days."""

    def __init__(self):
        self.store = JsonStore(TOPICS_PATH)

    def get_recent_topics(self, days: int = NO_REPEAT_DAYS) -> list:
        """Get topics used in the last N days."""
        data = self.store.read()
        topics = data.get("topics", [])
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [t for t in topics if t.get("date", "") >= cutoff]

    def get_recent_keywords(self, days: int = NO_REPEAT_DAYS) -> set:
        """Get all keywords used in recent topics."""
        recent = self.get_recent_topics(days)
        keywords = set()
        for t in recent:
            for kw in t.get("keywords", []):
                keywords.add(kw.lower())
        return keywords

    def check_overlap(self, new_keywords: list, days: int = NO_REPEAT_DAYS) -> dict:
        """Check if new keywords overlap with recent topics.

        Returns dict with: has_overlap, overlapping_keywords, overlap_topics
        """
        recent_kw = self.get_recent_keywords(days)
        new_kw_lower = [kw.lower() for kw in new_keywords]
        overlapping = [kw for kw in new_kw_lower if kw in recent_kw]

        overlap_topics = []
        if overlapping:
            for t in self.get_recent_topics(days):
                t_kw = [k.lower() for k in t.get("keywords", [])]
                if any(kw in t_kw for kw in overlapping):
                    overlap_topics.append(t)

        return {
            "has_overlap": len(overlapping) > 0,
            "overlapping_keywords": overlapping,
            "overlap_topics": overlap_topics,
        }

    def record(self, date: str, board: str, topic: str, keywords: list, pin_title: str = ""):
        """Record a topic usage."""
        data = self.store.read()
        if "topics" not in data:
            data["topics"] = []

        data["topics"].append({
            "date": date,
            "board": board,
            "topic": topic,
            "keywords": keywords,
            "pin_title": pin_title,
        })

        # Keep last 365 days of history
        cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        data["topics"] = [t for t in data["topics"] if t.get("date", "") >= cutoff]

        self.store.write(data)
        logger.info(f"Recorded topic: '{topic}' with {len(keywords)} keywords")

    def get_board_topics(self, board: str, days: int = NO_REPEAT_DAYS) -> list:
        """Get recent topics for a specific board."""
        recent = self.get_recent_topics(days)
        return [t for t in recent if t.get("board") == board]

    def suggest_avoidance_prompt(self, board: str) -> str:
        """Generate a prompt section telling Claude what topics to avoid."""
        board_topics = self.get_board_topics(board)
        if not board_topics:
            return ""

        lines = ["SON 45 GÜNDE İŞLENEN KONULAR (bunlardan kaçın veya farklı açıdan ele al):"]
        for t in board_topics:
            lines.append(f"- {t['date']}: {t['topic']} (anahtar kelimeler: {', '.join(t.get('keywords', []))})")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Get topic tracking stats for dashboard."""
        all_topics = self.store.read().get("topics", [])
        recent = self.get_recent_topics()
        boards = {}
        for t in recent:
            b = t.get("board", "")
            boards[b] = boards.get(b, 0) + 1

        return {
            "total_topics": len(all_topics),
            "recent_topics_45d": len(recent),
            "board_distribution": boards,
            "recent_keywords": list(self.get_recent_keywords()),
        }
