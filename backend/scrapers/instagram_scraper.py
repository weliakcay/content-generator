from __future__ import annotations

import json
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, TrendItem
from utils.rate_limiter import RateLimiter
from utils.logger import get_logger

logger = get_logger("instagram_scraper")


class InstagramScraper(BaseScraper):
    platform = "instagram"

    def __init__(self):
        self.rate_limiter = RateLimiter(min_interval=5.0)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "XMLHttpRequest",
        })

    def _search_hashtag(self, tag: str, max_results: int = 15) -> list[TrendItem]:
        """Search Instagram by hashtag using the web interface."""
        self.rate_limiter.wait()
        items = []
        clean_tag = tag.lstrip("#")

        try:
            # Try the hashtag explore page
            url = f"https://www.instagram.com/explore/tags/{clean_tag}/"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                items = self._extract_from_html(response.text, clean_tag)
                logger.info(f"Instagram hashtag #{clean_tag}: {len(items)} posts found")
            else:
                logger.warning(f"Instagram hashtag #{clean_tag}: HTTP {response.status_code}")

        except requests.RequestException as e:
            logger.error(f"Instagram hashtag error #{clean_tag}: {e}")

        return items[:max_results]

    def _search_keyword(self, keyword: str, max_results: int = 15) -> list[TrendItem]:
        """Search Instagram by keyword."""
        self.rate_limiter.wait()
        items = []

        try:
            # Instagram doesn't have a direct keyword search on web
            # Convert keyword to hashtag format as a workaround
            tag = keyword.replace(" ", "").lower()
            url = f"https://www.instagram.com/explore/tags/{tag}/"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                items = self._extract_from_html(response.text, keyword)
                logger.info(f"Instagram keyword '{keyword}': {len(items)} posts found")
            else:
                logger.warning(f"Instagram keyword '{keyword}': HTTP {response.status_code}")

        except requests.RequestException as e:
            logger.error(f"Instagram keyword error '{keyword}': {e}")

        return items[:max_results]

    def _extract_from_html(self, html: str, query: str) -> list[TrendItem]:
        """Extract post data from Instagram HTML/embedded JSON."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Look for embedded JSON data in script tags
        scripts = soup.find_all("script", {"type": "application/ld+json"})
        for script in scripts:
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    items.extend(self._parse_json_posts(data, query))
                elif isinstance(data, list):
                    for d in data:
                        items.extend(self._parse_json_posts(d, query))
            except (json.JSONDecodeError, TypeError):
                continue

        # Also look for shared data in window._sharedData or similar
        for script in soup.find_all("script"):
            text = script.string or ""
            if "window._sharedData" in text or "window.__additionalDataLoaded" in text:
                try:
                    # Extract JSON from the script
                    json_str = text.split("=", 1)[1].rstrip(";").strip()
                    data = json.loads(json_str)
                    items.extend(self._walk_for_posts(data, query))
                except (json.JSONDecodeError, IndexError, TypeError):
                    continue

        # Fallback: Create items from meta tags if nothing found
        if not items:
            meta_desc = soup.find("meta", {"name": "description"})
            if meta_desc and meta_desc.get("content"):
                items.append(TrendItem(
                    platform="instagram",
                    content_type="post",
                    title=query,
                    description=meta_desc["content"][:500],
                    url=f"https://www.instagram.com/explore/tags/{query.replace(' ', '')}/",
                ))

        return items

    def _parse_json_posts(self, data: dict, query: str) -> list[TrendItem]:
        """Parse Instagram posts from JSON-LD data."""
        items = []
        if data.get("@type") in ("ImageObject", "VideoObject"):
            items.append(TrendItem(
                platform="instagram",
                content_type="reel" if data.get("@type") == "VideoObject" else "post",
                title=query,
                description=(data.get("caption", "") or "")[:500],
                url=data.get("url", ""),
                author=data.get("author", {}).get("name", ""),
                likes=data.get("interactionStatistic", {}).get("userInteractionCount", 0)
                      if isinstance(data.get("interactionStatistic"), dict) else 0,
            ))
        return items

    def _walk_for_posts(self, data, query: str) -> list[TrendItem]:
        """Recursively walk JSON to find post data."""
        items = []

        def walk(obj):
            if isinstance(obj, dict):
                # Look for edge_media_to_caption pattern
                if "shortcode" in obj and "edge_media_preview_like" in obj:
                    caption = ""
                    edges = obj.get("edge_media_to_caption", {}).get("edges", [])
                    if edges:
                        caption = edges[0].get("node", {}).get("text", "")

                    items.append(TrendItem(
                        platform="instagram",
                        content_type="video" if obj.get("is_video") else "post",
                        title=query,
                        description=caption[:500],
                        url=f"https://www.instagram.com/p/{obj['shortcode']}/",
                        author=obj.get("owner", {}).get("username", ""),
                        likes=obj.get("edge_media_preview_like", {}).get("count", 0),
                        comments=obj.get("edge_media_to_comment", {}).get("count", 0),
                        views=obj.get("video_view_count", 0),
                        hashtags=[w for w in caption.split() if w.startswith("#")],
                    ))
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        return items

    def scrape_hashtags(self, hashtags: list[str]) -> list[TrendItem]:
        items = []
        for tag in hashtags:
            items.extend(self._search_hashtag(tag))
        return items

    def scrape_keywords(self, keywords: list[str]) -> list[TrendItem]:
        items = []
        for keyword in keywords:
            items.extend(self._search_keyword(keyword))
        return items

    def scrape_influencers(self, handles: list[str]) -> list[TrendItem]:
        items = []
        for handle in handles:
            clean_handle = handle.lstrip("@")
            self.rate_limiter.wait()
            try:
                url = f"https://www.instagram.com/{clean_handle}/"
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    posts = self._extract_from_html(response.text, clean_handle)
                    for post in posts:
                        post.author = clean_handle
                    items.extend(posts)
                    logger.info(f"Instagram influencer @{clean_handle}: {len(posts)} posts")
                else:
                    logger.warning(f"Instagram influencer @{clean_handle}: HTTP {response.status_code}")
            except requests.RequestException as e:
                logger.error(f"Instagram influencer error @{clean_handle}: {e}")
        return items

    def calculate_engagement(self, item: TrendItem) -> float:
        """Instagram: likes + comments / followers."""
        total = item.likes + item.comments
        if item.followers > 0:
            return total / item.followers
        if item.views > 0:
            return total / item.views
        if total > 0:
            return min(total / 1000, 1.0)
        return 0.0
