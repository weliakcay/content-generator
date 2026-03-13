from __future__ import annotations

from .base_scraper import BaseScraper
from .pinterest_scraper import PinterestScraper
from .instagram_scraper import InstagramScraper
from .tiktok_scraper import TikTokScraper


class ScraperFactory:
    """Factory to create platform-specific scrapers."""

    _scrapers: dict[str, type[BaseScraper]] = {
        "pinterest": PinterestScraper,
        "instagram": InstagramScraper,
        "tiktok": TikTokScraper,
    }

    @classmethod
    def create(cls, platform: str) -> BaseScraper:
        scraper_class = cls._scrapers.get(platform.lower())
        if scraper_class is None:
            raise ValueError(f"Unknown platform: {platform}. "
                             f"Available: {list(cls._scrapers.keys())}")
        return scraper_class()

    @classmethod
    def available_platforms(cls) -> list[str]:
        return list(cls._scrapers.keys())
