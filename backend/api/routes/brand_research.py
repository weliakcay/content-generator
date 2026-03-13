"""Brand research - Claude generates 4 design approach options."""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

import anthropic
from fastapi import APIRouter, HTTPException

import config
import db
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("brand_research")

_status: Dict[str, Any] = {"running": False, "result": None, "error": None}


@router.post("/{brand_id}/generate-research")
async def generate_research(brand_id: int) -> Dict[str, Any]:
    """Generate 4 design approach options for a brand via Claude."""
    if _status["running"]:
        return {"status": "already_running"}

    with db.get_cursor() as cur:
        cur.execute("SELECT name, profile_json, website_url FROM brands WHERE id = ?", (brand_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Brand not found")

    brand_name = row["name"]
    profile = json.loads(row["profile_json"] or "{}")

    def _run() -> None:
        _status.update({"running": True, "result": None, "error": None})
        try:
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            prompt = f"""Sen bir marka tasarım danışmanısın. "{brand_name}" markası için 4 farklı görsel kimlik yönelimi öner.

Marka bilgileri:
- Hedef kitle: {profile.get("target_audience", "")}
- Ses tonu: {profile.get("tone_of_voice", "")}
- Temel değerler: {", ".join(profile.get("core_values", []))}
- Ürün kategorileri: {", ".join(profile.get("product_categories", []))}

Her seçenek birbirinden farklı ve tutarlı bir marka yönelimi olsun.

Aşağıdaki JSON array'i döndür (başka açıklama ekleme):
[
  {{
    "name": "Yaklaşım adı (örn: 'Soft & Güçlü')",
    "description": "Bu görsel yönelimi 2 cümleyle anlat",
    "primary_color": "#hex",
    "secondary_colors": ["#hex1", "#hex2"],
    "neutral_colors": ["#açık_hex", "#koyu_hex"],
    "font_heading": "Google Font adı (heading için)",
    "font_body": "Google Font adı (body için)",
    "tone_keywords": ["kelime1", "kelime2", "kelime3", "kelime4", "kelime5"],
    "example_caption": "Bu marka sesinde örnek bir sosyal medya caption'ı (2-3 cümle)",
    "style_keywords": ["görsel1", "görsel2", "görsel3", "görsel4", "görsel5"]
  }}
]"""

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if "```json" in text:
                text = text[text.index("```json") + 7:text.rindex("```")].strip()
            elif "```" in text:
                text = text[text.index("```") + 3:text.rindex("```")].strip()
            options = json.loads(text)
            _status["result"] = options
        except Exception as e:
            _status["error"] = str(e)
            logger.error(f"Research generation failed: {e}")
        finally:
            _status["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


@router.get("/research/status")
async def research_status() -> Dict[str, Any]:
    return {
        "running": _status["running"],
        "result": _status["result"],
        "error": _status["error"],
    }


@router.post("/{brand_id}/apply-research")
async def apply_research(brand_id: int, option: dict) -> Dict[str, Any]:
    """Apply a selected design option to brand identity_json."""
    identity = {
        "selected_approach": option.get("name"),
        "visual_identity": {
            "primary_color": option.get("primary_color"),
            "secondary_colors": option.get("secondary_colors", []),
            "neutral_colors": option.get("neutral_colors", []),
            "font_heading": option.get("font_heading"),
            "font_body": option.get("font_body"),
            "style_keywords": option.get("style_keywords", []),
        },
        "brand_voice": {
            "tone_keywords": option.get("tone_keywords", []),
            "example_caption": option.get("example_caption", ""),
        },
    }
    with db.get_cursor() as cur:
        cur.execute(
            "UPDATE brands SET identity_json = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(identity), brand_id),
        )
    return {"status": "ok", "brand_id": brand_id}
