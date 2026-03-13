from __future__ import annotations

from scrapers.base_scraper import TrendItem
from analyzers.engagement_calc import normalize_engagement
from utils.logger import get_logger

logger = get_logger("trend_analyzer")


class TrendAnalyzer:
    """Analyzes and ranks trends across platforms."""

    @staticmethod
    def analyze(all_trends: list[TrendItem], brand_profile: dict,
                max_results: int = 15) -> list[TrendItem]:
        """Analyze, deduplicate, and rank trends."""
        if not all_trends:
            logger.warning("No trends to analyze")
            return []

        # 1. Remove duplicates (by URL)
        seen_urls = set()
        unique = []
        for item in all_trends:
            if item.url and item.url not in seen_urls:
                seen_urls.add(item.url)
                unique.append(item)
            elif not item.url:
                unique.append(item)

        logger.info(f"Deduplicated: {len(all_trends)} → {len(unique)} trends")

        # 2. Calculate brand alignment score
        for item in unique:
            item.viral_score = TrendAnalyzer._calculate_composite_score(
                item, brand_profile
            )

        # 3. Sort by composite score
        unique.sort(key=lambda x: x.viral_score, reverse=True)

        # 4. Ensure platform diversity in top results
        result = TrendAnalyzer._ensure_diversity(unique, max_results)

        logger.info(f"Top {len(result)} trends selected "
                    f"(avg viral score: {sum(t.viral_score for t in result) / len(result):.1f})")
        return result

    @staticmethod
    def _calculate_composite_score(item: TrendItem, brand_profile: dict) -> float:
        """Calculate a composite score combining viral potential and brand fit."""
        # Viral score (0-100) from base_scraper already calculated
        viral = item.viral_score

        # Normalized engagement (0-1) → scale to 0-100
        norm_eng = normalize_engagement(item.engagement_rate, item.platform) * 100

        # Brand alignment bonus (0-20)
        brand_bonus = TrendAnalyzer._brand_alignment(item, brand_profile)

        # Platform priority bonus
        platforms = brand_profile.get("platforms", {})
        platform_config = platforms.get(item.platform, {})
        priority = platform_config.get("priority", "medium")
        priority_bonus = {"high": 10, "medium": 5, "low": 0}.get(priority, 5)

        # Composite: 40% viral + 30% engagement + 20% brand + 10% priority
        composite = (viral * 0.4 + norm_eng * 0.3 +
                     brand_bonus * 0.2 + priority_bonus * 0.1)

        return min(composite, 100.0)

    @staticmethod
    def _brand_alignment(item: TrendItem, brand_profile: dict) -> float:
        """Score how well a trend aligns with the brand (0-100)."""
        score = 50.0  # Start neutral

        text = (item.title + " " + item.description).lower()

        # Positive: matches brand values
        core_values = [v.lower() for v in brand_profile.get("core_values", [])]
        for value in core_values:
            if value in text:
                score += 10

        # Positive: matches product categories
        categories = [c.lower() for c in brand_profile.get("product_categories", [])]
        for cat in categories:
            for word in cat.split():
                if word in text:
                    score += 5
                    break

        # Negative: contains forbidden content
        dont_use = [d.lower() for d in brand_profile.get("dont_use", [])]
        for forbidden in dont_use:
            if forbidden in text:
                score -= 20

        return max(0, min(score, 100))

    @staticmethod
    def _ensure_diversity(items: list[TrendItem], max_results: int) -> list[TrendItem]:
        """Ensure platform diversity in results."""
        result = []
        platform_counts: dict[str, int] = {}
        max_per_platform = max(max_results // 3 + 1, 3)

        for item in items:
            count = platform_counts.get(item.platform, 0)
            if count < max_per_platform:
                result.append(item)
                platform_counts[item.platform] = count + 1
            if len(result) >= max_results:
                break

        # If we don't have enough, fill from remaining
        if len(result) < max_results:
            for item in items:
                if item not in result:
                    result.append(item)
                if len(result) >= max_results:
                    break

        return result
