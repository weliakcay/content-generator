"""Brand onboarding API - scrape URL + generate profile via Claude."""
from __future__ import annotations

import json
import re
import threading
from typing import Any, Dict, Optional

import anthropic
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter
from pydantic import BaseModel

import config
import db
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("onboarding")

_status: Dict[str, Any] = {"running": False, "brand_id": None, "step": "", "error": None}


class OnboardRequest(BaseModel):
    brand_name: str
    website_url: str
    description: str


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-") or "brand"


def _scrape_site(url: str) -> str:
    try:
        resp = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""
        meta = soup.find("meta", {"name": "description"})
        meta_text = meta.get("content", "") if meta else ""
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])[:12]]
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")[:6] if len(p.get_text(strip=True)) > 40]
        return (
            f"Site başlığı: {title_text}\n"
            f"Meta açıklama: {meta_text}\n"
            f"Başlıklar: {' | '.join(headings)}\n"
            f"İçerik: {' '.join(paragraphs[:3])[:500]}"
        )
    except Exception as e:
        return f"Site taranamadı: {e}"


def _generate_profile(brand_name: str, url: str, description: str, scraped: str) -> Dict[str, Any]:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = f"""Aşağıdaki bilgilere dayanarak bu marka için eksiksiz bir JSON marka profili oluştur.

Marka Adı: {brand_name}
Web Sitesi: {url}
Açıklama: {description}
Site İçeriği: {scraped}

Aşağıdaki anahtarları içeren JSON objesi döndür (başka açıklama ekleme):
{{
  "brand_name": "{brand_name}",
  "tone_of_voice": "Markanın ses tonunu 1-2 cümleyle tanımla",
  "core_values": ["değer1", "değer2", "değer3", "değer4"],
  "target_audience": "Hedef kitleyi yaş, cinsiyet, ilgi alanları ile tanımla",
  "product_categories": ["kategori1", "kategori2"],
  "dont_use": ["yasak içerik türü 1", "yasak içerik türü 2"],
  "language": "Turkish",
  "platforms": {{
    "pinterest": {{"priority": "high", "style": "Görsel stil açıklaması", "daily_suggestions": 2, "content_types": ["pin"], "preferred_formats": ["infographic", "tip-list"]}},
    "instagram": {{"priority": "high", "style": "Görsel stil açıklaması", "daily_suggestions": 2, "content_types": ["post", "reel"], "preferred_formats": ["carousel", "reel"]}},
    "tiktok": {{"priority": "medium", "style": "Video stil açıklaması", "daily_suggestions": 1, "content_types": ["video"], "preferred_formats": ["educational-short"]}}
  }},
  "content_guidelines": {{"max_hashtags": 15, "use_emojis": true, "include_cta": true, "sfw_only": true}}
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if "```json" in text:
        text = text[text.index("```json") + 7:text.rindex("```")].strip()
    elif "```" in text:
        text = text[text.index("```") + 3:text.rindex("```")].strip()
    return json.loads(text)


@router.post("/start")
async def start_onboarding(req: OnboardRequest) -> Dict[str, Any]:
    """Start brand onboarding in background thread."""
    if _status["running"]:
        return {"status": "already_running"}

    def _run() -> None:
        _status.update({"running": True, "brand_id": None, "error": None})
        try:
            _status["step"] = "scraping"
            scraped = _scrape_site(req.website_url)

            _status["step"] = "generating"
            profile = _generate_profile(req.brand_name, req.website_url, req.description, scraped)

            brand_md = f"""# {req.brand_name}

**Website:** {req.website_url}

## Marka Sesi
{profile.get("tone_of_voice", "")}

## Hedef Kitle
{profile.get("target_audience", "")}

## Temel Değerler
{chr(10).join("- " + v for v in profile.get("core_values", []))}

## Yasak İçerik
{chr(10).join("- " + d for d in profile.get("dont_use", []))}
"""
            _status["step"] = "saving"
            slug = _slugify(req.brand_name)
            # Ensure slug uniqueness
            with db.get_cursor() as cur:
                cur.execute("SELECT COUNT(*) as c FROM brands WHERE slug LIKE ?", (f"{slug}%",))
                count = cur.fetchone()["c"]
            if count > 0:
                slug = f"{slug}-{count + 1}"

            with db.get_cursor() as cur:
                cur.execute(
                    "INSERT INTO brands (name, slug, website_url, description, profile_json) VALUES (?, ?, ?, ?, ?)",
                    (req.brand_name, slug, req.website_url, brand_md, json.dumps(profile)),
                )
                brand_id = cur.lastrowid

            _status["brand_id"] = brand_id
            _status["step"] = "done"
            logger.info(f"Brand onboarded: {req.brand_name} → id={brand_id}")
        except Exception as e:
            _status["error"] = str(e)
            logger.error(f"Onboarding failed: {e}")
        finally:
            _status["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


@router.get("/status")
async def onboarding_status() -> Dict[str, Any]:
    return {
        "running": _status["running"],
        "brand_id": _status["brand_id"],
        "step": _status["step"],
        "error": _status["error"],
    }
