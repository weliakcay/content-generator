from __future__ import annotations

import json
from typing import Any, Dict, List

import db
from utils.logger import get_logger

logger = get_logger("pattern_learner")


class PatternLearner:
    """Learns patterns from user feedback stored in SQLite."""

    @staticmethod
    def load_patterns(brand_id: int = 1) -> Dict[str, Any]:
        """Load learned patterns from feedback data for a brand."""
        with db.get_cursor() as cur:
            cur.execute(
                """SELECT f.action, f.platform, f.content_type, f.reason,
                          s.caption, s.hashtags
                   FROM feedback f
                   LEFT JOIN suggestions s ON f.suggestion_id = s.id
                   WHERE f.brand_id = ?""",
                (brand_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]

        approved = [r for r in rows if r["action"] == "liked"]
        rejected = [r for r in rows if r["action"] == "disliked"]

        if not approved and not rejected:
            return {"has_data": False}

        # Parse hashtags from JSON strings
        for item in approved + rejected:
            raw = item.get("hashtags")
            item["hashtags"] = json.loads(raw) if raw else []

        patterns: Dict[str, Any] = {
            "has_data": True,
            "total_approved": len(approved),
            "total_rejected": len(rejected),
            "approval_rate": len(approved) / max(len(approved) + len(rejected), 1),
            "preferred_platforms": PatternLearner._count_field(approved, "platform"),
            "avoided_platforms": PatternLearner._count_field(rejected, "platform"),
            "preferred_content_types": PatternLearner._count_field(approved, "content_type"),
            "avoided_content_types": PatternLearner._count_field(rejected, "content_type"),
            "successful_hashtags": PatternLearner._extract_hashtags(approved),
            "avoided_hashtags": PatternLearner._extract_hashtags(rejected),
            "caption_insights": PatternLearner._analyze_captions(approved, rejected),
        }

        logger.info(f"Patterns loaded for brand {brand_id}: {len(approved)} approved, {len(rejected)} rejected")
        return patterns

    @staticmethod
    def _count_field(items: List[Dict], field: str) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        for item in items:
            value = item.get(field) or "unknown"
            counts[value] = counts.get(value, 0) + 1
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"value": k, "count": v} for k, v in sorted_counts]

    @staticmethod
    def _extract_hashtags(items: List[Dict]) -> List[str]:
        hashtag_counts: Dict[str, int] = {}
        for item in items:
            for tag in item.get("hashtags", []):
                hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
        sorted_tags = sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)
        return [tag for tag, _ in sorted_tags[:20]]

    @staticmethod
    def _analyze_captions(approved: List[Dict], rejected: List[Dict]) -> Dict[str, Any]:
        def extract_keywords(items: List[Dict]) -> List[str]:
            word_counts: Dict[str, int] = {}
            for item in items:
                caption = item.get("caption") or ""
                for word in caption.lower().split():
                    if len(word) > 3 and not word.startswith("#"):
                        word_counts[word] = word_counts.get(word, 0) + 1
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            return [w for w, _ in sorted_words[:15]]

        return {
            "liked_keywords": extract_keywords(approved),
            "disliked_keywords": extract_keywords(rejected),
            "questions_in_liked": sum(1 for i in approved if "?" in (i.get("caption") or "")),
            "questions_in_disliked": sum(1 for i in rejected if "?" in (i.get("caption") or "")),
            "emoji_in_liked": sum(1 for i in approved if any(ord(c) > 127 for c in (i.get("caption") or ""))),
            "emoji_in_disliked": sum(1 for i in rejected if any(ord(c) > 127 for c in (i.get("caption") or ""))),
        }

    @staticmethod
    def format_for_prompt(patterns: Dict[str, Any]) -> str:
        """Format patterns as text for inclusion in AI prompt."""
        if not patterns.get("has_data"):
            return "Henüz kullanıcı geri bildirimi yok. Genel marka profiline göre üret."

        lines = ["KULLANICI TERCİHLERİ (geçmiş geri bildirimlerden öğrenildi):"]
        rate = patterns.get("approval_rate", 0)
        lines.append(f"- Genel beğeni oranı: %{rate * 100:.0f}")

        preferred = patterns.get("preferred_platforms", [])
        if preferred:
            lines.append(f"- En beğenilen platform: {preferred[0]['value']}")

        pref_types = patterns.get("preferred_content_types", [])
        if pref_types:
            lines.append(f"- Tercih edilen içerik türleri: {', '.join(t['value'] for t in pref_types[:3])}")

        avoided_types = patterns.get("avoided_content_types", [])
        if avoided_types:
            lines.append(f"- Beğenilmeyen içerik türleri: {', '.join(t['value'] for t in avoided_types[:3])}")

        caption_insights = patterns.get("caption_insights", {})
        if caption_insights.get("questions_in_liked", 0) > caption_insights.get("questions_in_disliked", 0):
            lines.append("- Caption'da soru sormak beğeniliyor")
        if caption_insights.get("emoji_in_liked", 0) > caption_insights.get("emoji_in_disliked", 0):
            lines.append("- Emoji kullanımı beğeniliyor")

        successful_tags = patterns.get("successful_hashtags", [])
        if successful_tags:
            lines.append(f"- Başarılı hashtagler: {', '.join(successful_tags[:5])}")

        return "\n".join(lines)
