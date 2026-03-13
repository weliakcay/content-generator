from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, TrendItem
from utils.rate_limiter import RateLimiter
from utils.logger import get_logger

logger = get_logger("pinterest_scraper")


class PinterestScraper(BaseScraper):
    platform = "pinterest"

    def __init__(self):
        self.rate_limiter = RateLimiter(min_interval=3.0)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def _search(self, query: str, max_results: int = 20) -> list[TrendItem]:
        """Search Pinterest for a query and extract pin data."""
        self.rate_limiter.wait()
        items = []

        try:
            url = f"https://www.pinterest.com/search/pins/?q={requests.utils.quote(query)}"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Pinterest renders most content via JS, so we parse what's available
            # in the initial HTML and any embedded JSON data
            import json
            scripts = soup.find_all("script", {"type": "application/json"})
            for script in scripts:
                try:
                    data = json.loads(script.string or "")
                    pins = self._extract_pins_from_json(data, query)
                    items.extend(pins[:max_results])
                except (json.JSONDecodeError, TypeError):
                    continue

            # Fallback: parse visible pin elements
            if not items:
                items = self._parse_html_pins(soup, query, max_results)

            logger.info(f"Pinterest search '{query}': {len(items)} pins found")

        except requests.RequestException as e:
            logger.error(f"Pinterest search error for '{query}': {e}")

        return items[:max_results]

    def _extract_pins_from_json(self, data: dict, query: str) -> list[TrendItem]:
        """Extract pin data from embedded JSON."""
        items = []

        def walk(obj):
            if isinstance(obj, dict):
                if "id" in obj and "description" in obj and "repin_count" in obj:
                    items.append(TrendItem(
                        platform="pinterest",
                        content_type="pin",
                        title=obj.get("title", query),
                        description=obj.get("description", "")[:500],
                        url=f"https://www.pinterest.com/pin/{obj['id']}/",
                        author=obj.get("pinner", {}).get("username", ""),
                        saves=obj.get("repin_count", 0),
                        comments=obj.get("comment_count", 0),
                        likes=obj.get("reaction_counts", {}).get("1", 0)
                              if isinstance(obj.get("reaction_counts"), dict) else 0,
                    ))
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        return items

    def _parse_html_pins(self, soup: BeautifulSoup, query: str,
                         max_results: int) -> list[TrendItem]:
        """Fallback: parse pins from HTML elements."""
        items = []
        pin_links = soup.find_all("a", href=True)
        for link in pin_links:
            href = link.get("href", "")
            if "/pin/" in href and len(items) < max_results:
                title_el = link.find("img")
                items.append(TrendItem(
                    platform="pinterest",
                    content_type="pin",
                    title=title_el.get("alt", query) if title_el else query,
                    description="",
                    url=f"https://www.pinterest.com{href}" if href.startswith("/") else href,
                ))
        return items

    def scrape_hashtags(self, hashtags: list[str]) -> list[TrendItem]:
        items = []
        for tag in hashtags:
            clean_tag = tag.lstrip("#")
            items.extend(self._search(clean_tag))
        return items

    def scrape_keywords(self, keywords: list[str]) -> list[TrendItem]:
        items = []
        for keyword in keywords:
            items.extend(self._search(keyword))
        return items

    def scrape_influencers(self, handles: list[str]) -> list[TrendItem]:
        items = []
        for handle in handles:
            clean_handle = handle.lstrip("@")
            self.rate_limiter.wait()
            try:
                url = f"https://www.pinterest.com/{clean_handle}/_pins/"
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                pins = self._parse_html_pins(soup, clean_handle, 10)
                for pin in pins:
                    pin.author = clean_handle
                items.extend(pins)
                logger.info(f"Pinterest influencer '{clean_handle}': {len(pins)} pins")
            except requests.RequestException as e:
                logger.error(f"Pinterest influencer error '{clean_handle}': {e}")
        return items

    def calculate_engagement(self, item: TrendItem) -> float:
        """Pinterest: saves are the primary metric."""
        total = item.saves + item.comments + item.likes
        if item.followers > 0:
            return total / item.followers
        # Without follower data, use absolute numbers normalized
        if total > 0:
            return min(total / 1000, 1.0)
        return 0.0
