"""Dashboard chat - Claude with full brand context."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
import db
from utils.date_utils import today_str
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("chat")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    brand_id: int = 1
    messages: List[ChatMessage]


def _build_context(brand_id: int) -> str:
    with db.get_cursor() as cur:
        cur.execute("SELECT * FROM brands WHERE id = ?", (brand_id,))
        brand_row = cur.fetchone()
    if not brand_row:
        return "Marka verisi bulunamadı."

    brand = dict(brand_row)
    profile = json.loads(brand.get("profile_json") or "{}")

    with db.get_cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) as total, AVG(viral_score) as avg_score,
                      SUM(CASE WHEN feedback='liked' THEN 1 ELSE 0 END) as liked,
                      SUM(CASE WHEN feedback='disliked' THEN 1 ELSE 0 END) as disliked
               FROM suggestions WHERE brand_id = ? AND date >= date('now', '-30 days')""",
            (brand_id,),
        )
        stats = dict(cur.fetchone())

        cur.execute(
            "SELECT platform, content_type, title, viral_score, feedback FROM suggestions WHERE brand_id = ? AND date = ? ORDER BY viral_score DESC",
            (brand_id, today_str()),
        )
        today_suggestions = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT COUNT(*) as c FROM pins WHERE brand_id = ?",
            (brand_id,),
        )
        total_pins = cur.fetchone()["c"]

    liked = stats.get("liked") or 0
    disliked = stats.get("disliked") or 0
    total_fb = liked + disliked

    return f"""AKTIF MARKA: {brand.get("name")}
Website: {brand.get("website_url", "Belirtilmemiş")}

MARKA PROFİLİ:
- Ses tonu: {profile.get("tone_of_voice", "")}
- Hedef kitle: {profile.get("target_audience", "")}
- Temel değerler: {", ".join(profile.get("core_values", []))}
- Dil: {profile.get("language", "Turkish")}

SON 30 GÜN PERFORMANSI:
- Üretilen öneri sayısı: {stats.get("total") or 0}
- Ortalama viral skor: {round(stats.get("avg_score") or 0, 1)}/100
- Beğenilen: {liked} | Beğenilmeyen: {disliked}
- Onay oranı: %{round(liked / max(total_fb, 1) * 100, 1)}
- Toplam Pinterest pin: {total_pins}

BUGÜNÜN ÖNERİLERİ ({today_str()}):
{json.dumps(today_suggestions, ensure_ascii=False, indent=2) if today_suggestions else "Bugün henüz öneri üretilmemiş."}"""


@router.post("/message")
async def chat_message(req: ChatRequest) -> Dict[str, Any]:
    """Send message to Claude with brand context."""
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY ayarlanmamış")

    brand_context = _build_context(req.brand_id)

    system_prompt = f"""Sen bir sosyal medya içerik yönetim platformunun AI asistanısın.
Aktif markaya ait tüm verilere erişimin var ve performans analizi, strateji önerisi ve müşteri raporu hazırlayabilirsin.

{brand_context}

Yapabileceklerin:
- İçerik performansını analiz etmek
- Marka stratejisi önerileri sunmak
- Müşteriye gösterilebilir durum raporları oluşturmak
- Sosyal medya takvimi önermek
- Hangi içeriklerin işe yaradığını açıklamak

Müşteri raporu istendiğinde markdown formatında, profesyonel ve anlaşılır yaz.
Her zaman veri odaklı ve uygulanabilir öneriler sun. Türkçe yanıt ver."""

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        system=system_prompt,
        messages=messages,
    )

    return {"role": "assistant", "content": response.content[0].text}
