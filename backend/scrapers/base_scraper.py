from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TrendItem:
    """A single trend item from any platform."""
    platform: str
    content_type: str  # pin, post, reel, video, etc.
    title: str
    description: str
    url: str
    author: str = ""
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    views: int = 0
    followers: int = 0
    engagement_rate: float = 0.0
    viral_score: float = 0.0
    hashtags: list[str] = field(default_factory=list)
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "content_type": self.content_type,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "author": self.author,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "saves": self.saves,
            "views": self.views,
            "followers": self.followers,
            "engagement_rate": self.engagement_rate,
            "viral_score": self.viral_score,
            "hashtags": self.hashtags,
            "scraped_at": self.scraped_at,
        }


class BaseScraper(ABC):
    """Abstract base class for all platform scrapers."""

    platform: str = ""

    @abstractmethod
    def scrape_hashtags(self, hashtags: list[str]) -> list[TrendItem]:
        """Search by hashtags and return trend items."""
        ...

    @abstractmethod
    def scrape_keywords(self, keywords: list[str]) -> list[TrendItem]:
        """Search by keywords and return trend items."""
        ...

    @abstractmethod
    def scrape_influencers(self, handles: list[str]) -> list[TrendItem]:
        """Scrape recent content from specific accounts."""
        ...

    def calculate_engagement(self, item: TrendItem) -> float:
        """Calculate engagement rate. Override per platform."""
        total_interactions = item.likes + item.comments + item.shares + item.saves
        if item.followers > 0:
            return total_interactions / item.followers
        if item.views > 0:
            return total_interactions / item.views
        return 0.0

    def calculate_viral_score(self, item: TrendItem) -> float:
        """Calculate viral potential score (0-100)."""
        score = 0.0

        # Engagement rate contribution (0-40 points)
        er = item.engagement_rate
        if er >= 0.10:
            score += 40
        elif er >= 0.05:
            score += 30
        elif er >= 0.03:
            score += 20
        elif er >= 0.01:
            score += 10

        # Absolute numbers contribution (0-30 points)
        total = item.likes + item.comments + item.shares + item.saves
        if total >= 10000:
            score += 30
        elif total >= 5000:
            score += 25
        elif total >= 1000:
            score += 20
        elif total >= 500:
            score += 15
        elif total >= 100:
            score += 10

        # Comments ratio (higher = more discussion = more viral) (0-20 points)
        if item.likes > 0:
            comment_ratio = item.comments / item.likes
            if comment_ratio >= 0.10:
                score += 20
            elif comment_ratio >= 0.05:
                score += 15
            elif comment_ratio >= 0.02:
                score += 10

        # Share/save ratio (0-10 points)
        if item.likes > 0:
            share_ratio = (item.shares + item.saves) / item.likes
            if share_ratio >= 0.20:
                score += 10
            elif share_ratio >= 0.10:
                score += 7
            elif share_ratio >= 0.05:
                score += 5

        return min(score, 100.0)

    def run(self, config: dict) -> list[TrendItem]:
        """Run all scraping tasks for this platform."""
        results: list[TrendItem] = []

        hashtags = [h["tag"] for h in config.get("hashtags", [])
                    if h.get("platform") == self.platform]
        if hashtags:
            results.extend(self.scrape_hashtags(hashtags))

        keywords = [k["keyword"] for k in config.get("keywords", [])
                    if self.platform in k.get("platforms", [])]
        if keywords:
            results.extend(self.scrape_keywords(keywords))

        handles = [i["handle"] for i in config.get("influencers", [])
                   if i.get("platform") == self.platform and i.get("active", True)]
        if handles:
            results.extend(self.scrape_influencers(handles))

        # Calculate engagement and viral scores
        for item in results:
            item.engagement_rate = self.calculate_engagement(item)
            item.viral_score = self.calculate_viral_score(item)

        return results
