"""Pinterest API routes - pins from SQLite, brand identity per brand."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db

PINTEREST_DIR = Path(__file__).parent.parent.parent / "pinterest"

router = APIRouter(prefix="/api/pinterest", tags=["pinterest"])

# Files that remain global templates (not per-brand)
GLOBAL_FILES = {
    "prompt_config": "prompt_config.json",
    "gem_instructions": "gem_instructions.json",
    "pinterest_rules": "pinterest_rules.json",
}


def _row_to_pin(row: Any) -> Dict[str, Any]:
    p = dict(row)
    for field in ("hashtags", "pinterest_tags", "keywords"):
        raw = p.get(field)
        p[field] = json.loads(raw) if raw else []
    raw_colors = p.get("palette_colors")
    p["palette_colors"] = json.loads(raw_colors) if raw_colors else {}
    return p


# ── Pin endpoints ────────────────────────────────────────────────────────────

@router.get("/pins")
def get_pins(brand_id: int = Query(1), date: Optional[str] = Query(None)) -> Dict[str, Any]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT * FROM pins WHERE brand_id = ? AND date = ? ORDER BY created_at",
            (brand_id, date),
        )
        rows = cur.fetchall()
    if not rows:
        return {"date": date, "pins": [], "generated_at": None}
    pins = [_row_to_pin(r) for r in rows]
    return {"date": date, "pins": pins, "generated_at": pins[0].get("created_at")}


@router.get("/pins/dates")
def get_pin_dates(brand_id: int = Query(1)) -> Dict[str, List[str]]:
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT date FROM pins WHERE brand_id = ? ORDER BY date DESC",
            (brand_id,),
        )
        rows = cur.fetchall()
    return {"dates": [r["date"] for r in rows]}


@router.get("/today")
def get_today_info(brand_id: int = Query(1)) -> Dict[str, Any]:
    from pinterest.pin_generator import get_todays_board
    return get_todays_board()


@router.get("/styles/stats")
def get_style_stats() -> Dict[str, Any]:
    from pinterest.style_manager import StyleManager
    return StyleManager().get_rotation_stats()


@router.get("/topics/stats")
def get_topic_stats() -> Dict[str, Any]:
    from pinterest.topic_tracker import TopicTracker
    return TopicTracker().get_stats()


# ── Generation endpoints ─────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    style_override: Optional[str] = None
    palette_override: Optional[str] = None


_generate_status: Dict[str, Any] = {"running": False, "result": None, "error": None}


@router.post("/generate")
def generate_pin(req: GenerateRequest = None, brand_id: int = Query(1)) -> Dict[str, Any]:
    if _generate_status["running"]:
        return {"status": "already_running", "message": "Pin üretimi devam ediyor..."}

    def _run() -> None:
        _generate_status["running"] = True
        _generate_status["result"] = None
        _generate_status["error"] = None
        try:
            from pinterest.pin_generator import generate_pin_content
            style = req.style_override if req else None
            palette = req.palette_override if req else None
            pin = generate_pin_content(style_override=style, palette_override=palette, brand_id=brand_id)
            _generate_status["result"] = pin
        except Exception as e:
            _generate_status["error"] = str(e)
        finally:
            _generate_status["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": "Pin üretimi başlatıldı..."}


@router.get("/generate/status")
def generate_status() -> Dict[str, Any]:
    return {
        "running": _generate_status["running"],
        "has_result": _generate_status["result"] is not None,
        "error": _generate_status["error"],
        "pin": _generate_status["result"],
    }


@router.post("/generate-and-email")
def generate_and_email(req: GenerateRequest = None, brand_id: int = Query(1)) -> Dict[str, Any]:
    if _generate_status["running"]:
        return {"status": "already_running"}

    def _run() -> None:
        _generate_status["running"] = True
        _generate_status["result"] = None
        _generate_status["error"] = None
        try:
            from pinterest.pin_generator import generate_pin_content
            from pinterest.pin_email import send_pin_email
            style = req.style_override if req else None
            palette = req.palette_override if req else None
            pin = generate_pin_content(style_override=style, palette_override=palette, brand_id=brand_id)
            _generate_status["result"] = pin
            if pin:
                send_pin_email(pin)
        except Exception as e:
            _generate_status["error"] = str(e)
        finally:
            _generate_status["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": "Pin üretimi ve email gönderimi başlatıldı..."}


# ── Instructions / Config Management ─────────────────────────────────────────

@router.get("/instructions")
def list_instructions(brand_id: int = Query(1)) -> Dict[str, Any]:
    """List all instruction configs. Global files + brand-specific identity."""
    result: Dict[str, Any] = {}

    # Global template files
    for key, filename in GLOBAL_FILES.items():
        filepath = PINTEREST_DIR / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                result[key] = json.load(f)
        else:
            result[key] = {}

    # Brand-specific identity from DB
    with db.get_cursor() as cur:
        cur.execute("SELECT pinterest_identity_json FROM brands WHERE id = ?", (brand_id,))
        row = cur.fetchone()
    if row and row["pinterest_identity_json"]:
        result["brand_identity"] = json.loads(row["pinterest_identity_json"])
    else:
        result["brand_identity"] = {}

    return result


@router.get("/instructions/{config_key}")
def get_instruction(config_key: str, brand_id: int = Query(1)) -> Any:
    """Get a specific instruction config."""
    if config_key in GLOBAL_FILES:
        filepath = PINTEREST_DIR / GLOBAL_FILES[config_key]
        if not filepath.exists():
            return {}
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    if config_key == "brand_identity":
        with db.get_cursor() as cur:
            cur.execute("SELECT pinterest_identity_json FROM brands WHERE id = ?", (brand_id,))
            row = cur.fetchone()
        if row and row["pinterest_identity_json"]:
            return json.loads(row["pinterest_identity_json"])
        return {}

    raise HTTPException(
        status_code=404,
        detail=f"Unknown config: {config_key}. Available: {list(GLOBAL_FILES.keys()) + ['brand_identity']}",
    )


@router.put("/instructions/{config_key}")
def update_instruction(config_key: str, data: dict, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Update a specific instruction config."""
    if config_key in GLOBAL_FILES:
        filepath = PINTEREST_DIR / GLOBAL_FILES[config_key]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "config": config_key, "message": "Güncellendi"}

    if config_key == "brand_identity":
        with db.get_cursor() as cur:
            cur.execute(
                "UPDATE brands SET pinterest_identity_json = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(data), brand_id),
            )
        return {"status": "ok", "config": config_key, "message": "Marka Pinterest kimliği güncellendi"}

    raise HTTPException(status_code=404, detail=f"Unknown config: {config_key}")
