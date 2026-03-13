from __future__ import annotations

import json
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, TrendItem
from utils.rate_limiter import RateLimiter
from utils.logger import get_logger

logger = get_logger("tiktok_scraper")


class TikTokScraper(BaseScraper):
    platform = "tiktok"

    def __init__(self):
        self.rate_limiter = RateLimiter(min_interval=5.0)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def _search(self, query: str, search_type: str = "keyword",
                max_results: int = 15) -> list[TrendItem]:
        """Search TikTok for content."""
        self.rate_limiter.wait()
        items = []

        try:
            if search_type == "hashtag":
                clean_tag = query.lstrip("#")
                url = f"https://www.tiktok.com/tag/{clean_tag}"
            else:
                url = f"https://www.tiktok.com/search?q={requests.utils.quote(query)}"

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                items = self._extract_from_html(response.text, query)
                logger.info(f"TikTok {search_type} '{query}': {len(items)} videos found")
            else:
                logger.warning(f"TikTok {search_type} '{query}': HTTP {response.status_code}")

        except requests.RequestException as e:
            logger.error(f"TikTok {search_type} error '{query}': {e}")

        return items[:max_results]

    def _extract_from_html(self, html: str, query: str) -> list[TrendItem]:
        """Extract video data from TikTok HTML/embedded JSON."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # TikTok embeds data in SIGI_STATE or __UNIVERSAL_DATA_FOR_REHYDRATION__
        for script in soup.find_all("script"):
            text = script.string or ""

            # Try SIGI_STATE
            if "SIGI_STATE" in text or "__UNIVERSAL_DATA" in text:
                try:
                    # Find JSON object in script
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        data = json.loads(text[start:end])
                        items.extend(self._walk_for_videos(data, query))
                except (json.JSONDecodeError, TypeError):
                    continue

        # Also try JSON-LD
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for d in data:
                        items.extend(self._parse_jsonld(d, query))
                elif isinstance(data, dict):
                    items.extend(self._parse_jsonld(data, query))
            except (json.JSONDecodeError, TypeError):
                continue

        return items

    def _parse_jsonld(self, data: dict, query: str) -> list[TrendItem]:
        """Parse TikTok videos from JSON-LD."""
        items = []
        if data.get("@type") == "VideoObject":
            interaction = data.get("interactionStatistic", [])
            likes = views = comments = shares = 0
            if isinstance(interaction, list):
                for stat in interaction:
                    itype = stat.get("interactionType", "")
                    count = int(stat.get("userInteractionCount", 0))
                    if "Like" in itype:
                        likes = count
                    elif "Watch" in itype:
                        views = count
                    elif "Comment" in itype:
                        comments = count
                    elif "Share" in itype:
                        shares = count

            items.append(TrendItem(
                platform="tiktok",
                content_type="video",
                title=data.get("name", query)[:200],
                description=data.get("description", "")[:500],
                url=data.get("url", ""),
                author=data.get("creator", {}).get("name", "")
                       if isinstance(data.get("creator"), dict) else "",
                likes=likes,
                views=views,
                comments=comments,
                shares=shares,
            ))
        return items

    def _walk_for_videos(self, data, query: str) -> list[TrendItem]:
        """Walk TikTok's SIGI_STATE data to find video items."""
        items = []

        def walk(obj):
            if isinstance(obj, dict):
                # Look for ItemModule or video data pattern
                if "desc" in obj and "stats" in obj and isinstance(obj["stats"], dict):
                    stats = obj["stats"]
                    author_info = obj.get("author", "")
                    if isinstance(author_info, dict):
                        author_name = author_info.get("uniqueId", "")
                    else:
                        author_name = str(author_info)

                    desc = obj.get("desc", "")
                    hashtags = [w for w in desc.split() if w.startswith("#")]

                    items.append(TrendItem(
                        platform="tiktok",
                        content_type="video",
                        title=desc[:200] if desc else query,
                        description=desc[:500],
                        url=f"https://www.tiktok.com/@{author_name}/video/{obj.get('id', '')}",
                        author=author_name,
                        likes=int(stats.get("diggCount", 0)),
                        comments=int(stats.get("commentCount", 0)),
                        shares=int(stats.get("shareCount", 0)),
                        views=int(stats.get("playCount", 0)),
                        saves=int(stats.get("collectCount", 0)),
                        hashtags=hashtags,
                    ))
                    return  # Don't recurse into found items

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
            items.extend(self._search(tag, search_type="hashtag"))
        return items

    def scrape_keywords(self, keywords: list[str]) -> list[TrendItem]:
        items = []
        for keyword in keywords:
            items.extend(self._search(keyword, search_type="keyword"))
        return items

    def scrape_influencers(self, handles: list[str]) -> list[TrendItem]:
        items = []
        for handle in handles:
            clean_handle = handle.lstrip("@")
            self.rate_limiter.wait()
            try:
                url = f"https://www.tiktok.com/@{clean_handle}"
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    videos = self._extract_from_html(response.text, clean_handle)
                    for video in videos:
                        video.author = clean_handle
                    items.extend(videos)
                    logger.info(f"TikTok influencer @{clean_handle}: {len(videos)} videos")
                else:
                    logger.warning(f"TikTok influencer @{clean_handle}: HTTP {response.status_code}")
            except requests.RequestException as e:
                logger.error(f"TikTok influencer error @{clean_handle}: {e}")
        return items

    def calculate_engagement(self, item: TrendItem) -> float:
        """TikTok: likes + comments + shares / views."""
        total = item.likes + item.comments + item.shares
        if item.views > 0:
            return total / item.views
        if total > 0:
            return min(total / 1000, 1.0)
        return 0.0
