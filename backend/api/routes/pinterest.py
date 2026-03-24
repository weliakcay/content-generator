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


class PinFeedbackRequest(BaseModel):
    action: str  # "published" | "rejected"
    brand_id: int = 1

@router.post("/pins/{pin_id}/feedback")
def pin_feedback(pin_id: str, req: PinFeedbackRequest) -> Dict[str, Any]:
    """Record whether a pin was published or rejected. Used for weekly analysis."""
    if req.action not in ("published", "rejected"):
        raise HTTPException(status_code=400, detail="action must be 'published' or 'rejected'")
    now = datetime.now().isoformat()
    with db.get_cursor() as cur:
        # Store in feedback table
        cur.execute(
            """INSERT INTO feedback (brand_id, suggestion_id, action, platform, content_type, feedback_at)
               VALUES (?, ?, ?, 'pinterest', 'pin', ?)""",
            (req.brand_id, pin_id, req.action, now),
        )
        # Also tag the pin itself with feedback
        cur.execute(
            "UPDATE pins SET special_day = COALESCE(special_day, '') WHERE id = ?",
            (pin_id,),
        )
    return {"ok": True, "pin_id": pin_id, "action": req.action}


@router.get("/analysis/weekly")
def weekly_analysis(brand_id: int = Query(1)) -> Dict[str, Any]:
    """Weekly performance report: published vs rejected, tag stats, board stats."""
    with db.get_cursor() as cur:
        # Last 7 days pins
        cur.execute(
            """SELECT p.id, p.date, p.board, p.pin_title, p.style_code, p.palette_code,
                      p.pinterest_tags, p.keywords, f.action
               FROM pins p
               LEFT JOIN feedback f ON f.suggestion_id = p.id AND f.platform = 'pinterest'
               WHERE p.brand_id = ? AND p.date >= date('now', '-7 days')
               ORDER BY p.date DESC""",
            (brand_id,),
        )
        rows = cur.fetchall()

    pins = []
    tag_counts: Dict[str, int] = {}
    board_counts: Dict[str, Dict[str, int]] = {}
    style_counts: Dict[str, int] = {}

    for r in rows:
        p = dict(r)
        tags = json.loads(p.get("pinterest_tags") or "[]")
        kws = json.loads(p.get("keywords") or "[]")
        action = p.get("action") or "pending"

        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        board = p["board"]
        if board not in board_counts:
            board_counts[board] = {"published": 0, "rejected": 0, "pending": 0}
        board_counts[board][action] = board_counts[board].get(action, 0) + 1

        style = p.get("style_code", "?")
        style_counts[style] = style_counts.get(style, 0) + 1

        pins.append({
            "id": p["id"], "date": p["date"], "board": board,
            "title": p["pin_title"], "style": style,
            "tags": tags, "keywords": kws, "action": action,
        })

    published = [p for p in pins if p["action"] == "published"]
    rejected = [p for p in pins if p["action"] == "rejected"]
    pending = [p for p in pins if p["action"] == "pending"]

    return {
        "period": "last_7_days",
        "total_pins": len(pins),
        "published": len(published),
        "rejected": len(rejected),
        "pending": len(pending),
        "board_stats": board_counts,
        "tag_usage": dict(sorted(tag_counts.items(), key=lambda x: -x[1])),
        "style_usage": style_counts,
        "published_pins": [p["title"] for p in published],
        "rejected_pins": [{"title": p["title"], "board": p["board"]} for p in rejected],
    }


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
