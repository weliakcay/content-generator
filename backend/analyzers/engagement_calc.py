"""Platform-specific engagement rate calculations."""


def calculate_pinterest_engagement(saves: int, comments: int, likes: int,
                                   followers: int = 0) -> float:
    total = saves * 2 + comments * 3 + likes  # Saves weighted more on Pinterest
    if followers > 0:
        return total / followers
    return min(total / 1000, 1.0) if total > 0 else 0.0


def calculate_instagram_engagement(likes: int, comments: int, shares: int,
                                   saves: int, followers: int = 0) -> float:
    total = likes + comments * 2 + shares * 3 + saves * 2
    if followers > 0:
        return total / followers
    return min(total / 1000, 1.0) if total > 0 else 0.0


def calculate_tiktok_engagement(likes: int, comments: int, shares: int,
                                views: int = 0) -> float:
    total = likes + comments * 2 + shares * 3
    if views > 0:
        return total / views
    return min(total / 1000, 1.0) if total > 0 else 0.0


def normalize_engagement(rate: float, platform: str) -> float:
    """Normalize engagement rates across platforms to 0-1 scale.
    Different platforms have different typical engagement rates."""
    benchmarks = {
        "pinterest": 0.02,    # 2% is good on Pinterest
        "instagram": 0.035,   # 3.5% is good on Instagram
        "tiktok": 0.05,       # 5% is good on TikTok
    }
    benchmark = benchmarks.get(platform, 0.03)
    return min(rate / (benchmark * 3), 1.0)
