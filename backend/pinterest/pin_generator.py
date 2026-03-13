from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

import config
import db
from utils.logger import get_logger
from pinterest.style_manager import StyleManager
from pinterest.topic_tracker import TopicTracker

logger = get_logger("pin_generator")

PINTEREST_DIR = Path(__file__).parent

DAY_MAP = {0: "pazartesi", 1: "sali", 2: "carsamba", 3: "persembe", 4: "cuma", 5: "cumartesi", 6: "pazar"}
DAY_NAMES_TR = {0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"}


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_brand_identity(brand_id: int = 1) -> dict:
    """Load brand Pinterest identity from DB, fallback to static file."""
    with db.get_cursor() as cur:
        cur.execute("SELECT pinterest_identity_json FROM brands WHERE id = ?", (brand_id,))
        row = cur.fetchone()
    if row and row["pinterest_identity_json"]:
        data = json.loads(row["pinterest_identity_json"])
        if data:
            return data
    # Fallback to static file (for Wellco Adult)
    return _load_json(PINTEREST_DIR / "brand_identity.json")


def get_todays_board(date: datetime = None) -> dict:
    if date is None:
        date = datetime.now()
    gem = _load_json(PINTEREST_DIR / "gem_instructions.json")
    day_key = DAY_MAP[date.weekday()]
    calendar_entry = gem["weekly_calendar"].get(day_key, {})
    special_day = check_special_day(date, gem)

    if special_day:
        board = special_day.get("board_override", calendar_entry.get("board", ""))
        theme = special_day.get("theme", calendar_entry.get("theme", ""))
    else:
        board = calendar_entry.get("board", "")
        theme = calendar_entry.get("theme", "")

    return {
        "board": board,
        "theme": theme,
        "day_key": day_key,
        "day_name": DAY_NAMES_TR[date.weekday()],
        "description_length": calendar_entry.get("description_length", "ORTA"),
        "tone": calendar_entry.get("tone", ""),
        "content_focus": calendar_entry.get("content_focus", ""),
        "special_day": special_day,
    }


def check_special_day(date: datetime, gem: dict = None) -> Optional[dict]:
    if gem is None:
        gem = _load_json(PINTEREST_DIR / "gem_instructions.json")
    date_str = date.strftime("%m-%d")
    for sd in gem.get("special_days", []):
        sd_date = sd["date"]
        prep_days = sd.get("prep_days_before", 0)
        if date_str == sd_date:
            return sd
        if prep_days > 0:
            sd_month, sd_day = map(int, sd_date.split("-"))
            try:
                sd_datetime = date.replace(month=sd_month, day=sd_day)
                diff = (sd_datetime - date).days
                if 0 < diff <= prep_days:
                    return {**sd, "prep_mode": True, "days_until": diff}
            except ValueError:
                pass
    return None


def generate_pin_content(
    board_info: dict = None,
    date: datetime = None,
    style_override: str = None,
    palette_override: str = None,
    brand_id: int = 1,
) -> Optional[dict]:
    """Generate a Pinterest pin using Claude API and save to SQLite."""
    if date is None:
        date = datetime.now()
    if board_info is None:
        board_info = get_todays_board(date)

    date_str = date.strftime("%Y-%m-%d")
    board = board_info["board"]

    # Load configs
    gem = _load_json(PINTEREST_DIR / "gem_instructions.json")
    brand = _load_brand_identity(brand_id)
    rules = _load_json(PINTEREST_DIR / "pinterest_rules.json")

    # Style rotation
    style_mgr = StyleManager()
    if style_override and palette_override:
        style_info = {
            "style_code": style_override,
            "style_name": gem["styles"][style_override]["name"],
            "style_details": gem["styles"][style_override],
            "palette_code": palette_override,
            "palette_name": gem["palettes"][palette_override]["name"],
            "palette_details": gem["palettes"][palette_override],
        }
    else:
        style_info = style_mgr.select_next(board)

    # Topic avoidance
    topic_tracker = TopicTracker()
    avoidance_prompt = topic_tracker.suggest_avoidance_prompt(board)

    desc_length = board_info.get("description_length", "ORTA")
    length_spec = gem.get("description_lengths", {}).get(desc_length, {})
    board_rules = rules.get("board_categories", {}).get(board, {})
    posting_time = rules.get("best_posting_times", {}).get(board_info["day_key"], {})

    special_ctx = ""
    if board_info.get("special_day"):
        sd = board_info["special_day"]
        if sd.get("prep_mode"):
            special_ctx = f"ÖZEL GÜN YAKLAŞIYOR: {sd['name']} ({sd.get('days_until', '?')} gün sonra)."
        else:
            special_ctx = f"BUGÜN ÖZEL GÜN: {sd['name']}."

    # Load custom prompt config
    prompt_config_path = PINTEREST_DIR / "prompt_config.json"
    prompt_config = _load_json(prompt_config_path) if prompt_config_path.exists() else {}
    extra_instructions = prompt_config.get("extra_instructions", "")
    quality_notes = prompt_config.get("quality_notes", "")
    visual_prompt_guide = prompt_config.get("visual_prompt_guide", "")

    # Brand name from identity
    brand_name = brand.get("brand_name", "Marka")
    brand_voice = brand.get("brand_voice", {})
    brand_tone = brand_voice.get("tone", "")
    brand_personality = brand_voice.get("personality", [])
    target_audience = brand.get("target_audience", {})
    dont_use = brand.get("dont_use", [])

    system_prompt = f"""Sen {brand_name} markasının profesyonel Pinterest içerik stratejistisin.
Amacın: Pinterest'te KAYDEDİLECEK, TIKLANACAK ve PAYLAŞILACAK içerik üretmek.

═══ MARKA ═══
Marka: {brand_name} | Ton: {brand_tone}
Kişilik: {', '.join(brand_personality) if isinstance(brand_personality, list) else brand_personality}
Hedef: {target_audience.get('age_range', '')} yaş, {target_audience.get('gender', '')}
YASAKLAR: {', '.join(dont_use) if isinstance(dont_use, list) else dont_use}

═══ BUGÜN ═══
Tarih: {date_str} | Gün: {board_info['day_name']}
Pano: {board} | Tema: {board_info['theme']}
Odak: {board_info['content_focus']}
Ton: {board_info['tone']}
{f'⚡ {special_ctx}' if special_ctx else ''}

═══ GÖRSEL STİL ═══
Stil: {style_info['style_code']} - {style_info['style_name']} → {style_info['style_details']['description']}
Palette: {style_info['palette_code']} - {style_info['palette_name']}
Renkler: Primary {style_info['palette_details']['primary']}, Secondary {style_info['palette_details']['secondary']}, Accent {style_info['palette_details']['accent']}

═══ KRİTİK KURALLAR ═══
{avoidance_prompt}

{extra_instructions}

{quality_notes}

═══ ÇIKTI TALİMATLARI ═══

1. pin_title (max 100 karakter): İlk 40 karakterde anahtar kelime, rakam kullan
2. pin_description (300-500 karakter): Hook + somut bilgi + CTA
3. visual_prompt (YAYINA HAZIR): ASLA placeholder kullanma, tüm Türkçe metinleri tam yaz
   {visual_prompt_guide}
4. hashtags: 6-8, Türkçe+İngilizce, marka hashtag'i dahil
5. pinterest_tags: 3-5, # olmadan
6. file_name: kebab-case, Türkçe karakter yok, .jpg
7. alt_text (200-400 karakter): SEO uyumlu
8. topic: 2-4 kelime
9. keywords: 5-8 anahtar kelime

SADECE JSON döndür:
{{
  "pin_title": "",
  "pin_description": "",
  "hashtags": [],
  "pinterest_tags": [],
  "file_name": "",
  "alt_text": "",
  "topic": "",
  "keywords": [],
  "visual_prompt": ""
}}"""

    pin_content = _call_claude(system_prompt)
    if pin_content is None:
        logger.error("Claude API failed, no pin generated")
        return None

    # Enrich with metadata
    pin_content["id"] = uuid.uuid4().hex[:8]
    pin_content["date"] = date_str
    pin_content["day_name"] = board_info["day_name"]
    pin_content["board"] = board
    pin_content["theme"] = board_info["theme"]
    pin_content["style_code"] = style_info["style_code"]
    pin_content["style_name"] = style_info["style_name"]
    pin_content["palette_code"] = style_info["palette_code"]
    pin_content["palette_name"] = style_info["palette_name"]
    pin_content["palette_colors"] = style_info["palette_details"]
    pin_content["posting_time"] = posting_time.get("optimal", "20:00-22:00")
    pin_content["special_day"] = board_info.get("special_day", {}).get("name") if board_info.get("special_day") else None
    pin_content["created_at"] = datetime.now().isoformat()

    # Save to SQLite
    _save_pin(pin_content, date_str, brand_id)

    # Record style and topic
    style_mgr.record(date=date_str, style_code=style_info["style_code"],
                     palette_code=style_info["palette_code"], board=board,
                     pin_title=pin_content.get("pin_title", ""))
    topic_tracker.record(date=date_str, board=board, topic=pin_content.get("topic", ""),
                         keywords=pin_content.get("keywords", []),
                         pin_title=pin_content.get("pin_title", ""))

    logger.info(f"Pin generated: '{pin_content.get('pin_title', '')}' for {board}")
    return pin_content


def _call_claude(prompt: str) -> Optional[dict]:
    if not config.ANTHROPIC_API_KEY:
        logger.warning("No ANTHROPIC_API_KEY")
        return None
    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        logger.error(f"No JSON found in response: {text[:200]}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return None
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return None


def _save_pin(pin: dict, date_str: str, brand_id: int = 1) -> None:
    """Save pin to SQLite pins table."""
    with db.get_cursor() as cur:
        cur.execute(
            """INSERT OR REPLACE INTO pins
                (id, brand_id, date, board, theme, pin_title, pin_description,
                 hashtags, pinterest_tags, file_name, alt_text, visual_prompt,
                 topic, keywords, style_code, style_name, palette_code, palette_name,
                 palette_colors, posting_time, special_day, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                pin["id"], brand_id, date_str,
                pin.get("board"), pin.get("theme"),
                pin.get("pin_title"), pin.get("pin_description"),
                json.dumps(pin.get("hashtags", [])),
                json.dumps(pin.get("pinterest_tags", [])),
                pin.get("file_name"), pin.get("alt_text"), pin.get("visual_prompt"),
                pin.get("topic"), json.dumps(pin.get("keywords", [])),
                pin.get("style_code"), pin.get("style_name"),
                pin.get("palette_code"), pin.get("palette_name"),
                json.dumps(pin.get("palette_colors", {})),
                pin.get("posting_time"), pin.get("special_day"),
                pin.get("created_at"),
            ),
        )
    logger.info(f"Pin saved to DB for brand_id={brand_id}, date={date_str}")


# Legacy helpers (kept for backward compat with route)
def get_pin(date_str: str = None) -> Optional[dict]:
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    with db.get_cursor() as cur:
        cur.execute("SELECT * FROM pins WHERE date = ? ORDER BY created_at", (date_str,))
        rows = cur.fetchall()
    if not rows:
        return None
    pins = []
    for r in rows:
        p = dict(r)
        for field in ("hashtags", "pinterest_tags", "keywords"):
            p[field] = json.loads(p.get(field) or "[]")
        p["palette_colors"] = json.loads(p.get("palette_colors") or "{}")
        pins.append(p)
    return {"date": date_str, "pins": pins, "generated_at": pins[0].get("created_at")}


def get_available_dates() -> list:
    with db.get_cursor() as cur:
        cur.execute("SELECT DISTINCT date FROM pins ORDER BY date DESC")
        return [r["date"] for r in cur.fetchall()]
