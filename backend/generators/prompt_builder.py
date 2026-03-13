from __future__ import annotations

from scrapers.base_scraper import TrendItem
from utils.logger import get_logger

logger = get_logger("prompt_builder")


class PromptBuilder:
    """Builds Claude API prompts from brand profile, trends, and patterns."""

    @staticmethod
    def build(brand_profile: dict, top_trends: list[TrendItem],
              patterns_text: str, suggestions_count: int = 5) -> str:
        """Build the full prompt for content generation."""

        # Determine platform distribution
        platforms = brand_profile.get("platforms", {})
        distribution = {}
        for platform, pconfig in platforms.items():
            count = pconfig.get("daily_suggestions", 1)
            distribution[platform] = count

        # Ensure total matches suggestions_count
        total = sum(distribution.values())
        if total != suggestions_count:
            # Adjust proportionally
            for p in distribution:
                distribution[p] = max(1, round(distribution[p] * suggestions_count / total))

        # Format trends
        trends_text = PromptBuilder._format_trends(top_trends)

        # Format platform guidelines
        platform_guidelines = PromptBuilder._format_platform_guidelines(brand_profile)

        brand_name = brand_profile.get("brand_name", "marka")

        prompt = f"""Sen {brand_name} markası için sosyal medya içerik stratejisti olarak çalışıyorsun.

## MARKA PROFİLİ
- Marka: {brand_profile.get('brand_name', 'Wellco Adult')}
- Ses Tonu: {brand_profile.get('tone_of_voice', 'Samimi, bilgilendirici, empowering')}
- Temel Değerler: {', '.join(brand_profile.get('core_values', []))}
- Hedef Kitle: {brand_profile.get('target_audience', '25-45 yaş')}
- Ürün Kategorileri: {', '.join(brand_profile.get('product_categories', []))}
- Dil: {brand_profile.get('language', 'Turkish')}

## YASAKLAR (KESİNLİKLE KULLANMA)
{chr(10).join('- ' + d for d in brand_profile.get('dont_use', []))}

## İÇERİK KURALLARI
- Tüm içerikler SFW (Safe For Work) olmalı
- Hashtag sayısı: 10-15 arası
- Her içerikte CTA (Call to Action) olmalı
- Emoji kullanılabilir

## BUGÜNKÜ TRENDLER
{trends_text}

## {patterns_text}

## PLATFORM KILAVUZLARI
{platform_guidelines}

## GÖREV
Tam olarak {suggestions_count} adet içerik önerisi üret. Dağılım:
{chr(10).join(f'- {platform.title()}: {count} adet' for platform, count in distribution.items())}

Her öneri için şu formatı MUTLAKA kullan (JSON formatında):

```json
[
  {{
    "platform": "instagram|pinterest|tiktok",
    "content_type": "post|carousel|reel|pin|video",
    "title": "İçerik başlığı",
    "caption": "Tam caption metni (hashtag'ler dahil, 3-5 cümle)",
    "hashtags": ["#hashtag1", "#hashtag2", "..."],
    "visual_concept": "Görselin detaylı açıklaması (düzen, renkler, içerik, estetik)",
    "cta": "Call to action cümlesi",
    "publish_time": "Önerilen yayın zamanı (ör: Pazar 10:00-11:00)",
    "publish_reason": "Bu zamanın neden iyi olduğu",
    "viral_score": 0-100 arası tahmini viral skor,
    "trend_source": "Bu öneri hangi trende dayanıyor"
  }}
]
```

ÖNEMLİ:
- Caption'lar Türkçe olmalı
- Her caption marka ses tonuna uygun olmalı
- Hashtag'ler hem Türkçe hem İngilizce karışık olabilir
- Görsel konsept detaylı olsun (renk paleti, kompozisyon, objeler)
- Yayın zamanları Türkiye saatine göre olsun
- Sadece JSON array döndür, başka açıklama ekleme"""

        logger.info(f"Prompt built: {len(prompt)} chars, {suggestions_count} suggestions requested")
        return prompt

    @staticmethod
    def _format_trends(trends: list[TrendItem]) -> str:
        if not trends:
            return "Bugün için trend verisi bulunamadı. Genel wellness trendlerini kullan."

        lines = []
        for i, trend in enumerate(trends[:10], 1):
            lines.append(
                f"{i}. [{trend.platform.upper()}] {trend.title[:100]}\n"
                f"   Engagement: {trend.engagement_rate:.4f} | "
                f"Viral Skor: {trend.viral_score:.0f}/100\n"
                f"   Likes: {trend.likes} | Comments: {trend.comments} | "
                f"Shares: {trend.shares}\n"
                f"   Açıklama: {trend.description[:150]}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _format_platform_guidelines(brand_profile: dict) -> str:
        lines = []
        platforms = brand_profile.get("platforms", {})

        for platform, config in platforms.items():
            style = config.get("style", "")
            formats = config.get("preferred_formats", [])
            content_types = config.get("content_types", [])

            lines.append(f"### {platform.upper()}")
            lines.append(f"- Stil: {style}")
            if content_types:
                lines.append(f"- İçerik türleri: {', '.join(content_types)}")
            if formats:
                lines.append(f"- Tercih edilen formatlar: {', '.join(formats)}")
            lines.append("")

        return "\n".join(lines)
