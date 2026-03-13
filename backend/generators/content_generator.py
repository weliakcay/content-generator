from __future__ import annotations

import json
from datetime import date
from typing import List

import anthropic

import config
import db
from generators.suggestion_model import Suggestion, DailySuggestions
from utils.logger import get_logger

logger = get_logger("content_generator")


class ContentGenerator:
    """Generates content suggestions using Claude API and saves to SQLite."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def generate(self, prompt: str, brand_id: int = 1) -> DailySuggestions:
        """Call Claude API and save results to SQLite."""
        today = date.today().isoformat()
        daily = DailySuggestions(date=today)

        if not config.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY not set - generating mock suggestions")
            daily.suggestions = self._generate_mock_suggestions()
            self._save(daily, brand_id)
            return daily

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            suggestions = self._parse_response(text)
            daily.suggestions = suggestions
            logger.info(f"Generated {len(suggestions)} suggestions via Claude API")
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            logger.info("Falling back to mock suggestions")
            daily.suggestions = self._generate_mock_suggestions()

        self._save(daily, brand_id)
        return daily

    def _parse_response(self, text: str) -> List[Suggestion]:
        """Parse Claude's JSON response into Suggestion objects."""
        suggestions = []
        json_str = text
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            json_str = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            json_str = text[start:end].strip()

        try:
            data = json.loads(json_str)
            if not isinstance(data, list):
                data = [data]
            for item in data:
                suggestions.append(Suggestion(
                    platform=item.get("platform", "instagram"),
                    content_type=item.get("content_type", "post"),
                    title=item.get("title", ""),
                    caption=item.get("caption", ""),
                    hashtags=item.get("hashtags", []),
                    visual_concept=item.get("visual_concept", ""),
                    cta=item.get("cta", ""),
                    publish_time=item.get("publish_time", ""),
                    publish_reason=item.get("publish_reason", ""),
                    viral_score=float(item.get("viral_score", 0)),
                    trend_source=item.get("trend_source", ""),
                ))
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.debug(f"Raw response: {text[:500]}")

        return suggestions

    def _generate_mock_suggestions(self) -> List[Suggestion]:
        """Generate mock suggestions when API is not available."""
        return [
            Suggestion(
                platform="pinterest",
                content_type="pin",
                title="Self-Care Pazar Rutini",
                caption="Pazar günleri sadece dinlenmek değil, kendine yatırım yapmak için. "
                        "Mumlar, rahatlatıcı müzik ve kendine ayırdığın özel bir an... "
                        "Çünkü sen bunu hak ediyorsun.",
                hashtags=["#selfcare", "#wellness", "#kendinebakim"],
                visual_concept="Pastel tonlarda minimalist banyo ortamı.",
                cta="Senin self-care rutinin nasıl?",
                publish_time="Pazar 10:00-11:00",
                publish_reason="Pazar sabahları Pinterest'te self-care aramaları yüksek",
                viral_score=85,
                trend_source="Self-care Sunday trendi",
            ),
        ]

    def _save(self, daily: DailySuggestions, brand_id: int = 1) -> None:
        """Save daily suggestions to SQLite."""
        for s in daily.suggestions:
            with db.get_cursor() as cur:
                cur.execute(
                    """INSERT OR REPLACE INTO suggestions
                        (id, brand_id, date, platform, content_type, title, caption,
                         hashtags, visual_concept, cta, publish_time, publish_reason,
                         similar_examples, viral_score, trend_source,
                         generated_at, email_sent)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        s.id,
                        brand_id,
                        daily.date,
                        s.platform,
                        s.content_type,
                        s.title,
                        s.caption,
                        json.dumps(s.hashtags),
                        s.visual_concept,
                        s.cta,
                        s.publish_time,
                        s.publish_reason,
                        json.dumps(getattr(s, "similar_examples", [])),
                        s.viral_score,
                        s.trend_source,
                        daily.generated_at,
                        1 if daily.email_sent else 0,
                    ),
                )
        logger.info(f"Saved {len(daily.suggestions)} suggestions to DB for brand_id={brand_id}")
