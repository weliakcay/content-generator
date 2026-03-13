"""Suggestions API routes - reads/writes from SQLite."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db
from utils.date_utils import today_str, now_str

router = APIRouter()


class FeedbackRequest(BaseModel):
    action: str  # "liked" or "disliked"
    reason: Optional[str] = None


def _row_to_suggestion(row: Any) -> Dict[str, Any]:
    s = dict(row)
    for field in ("hashtags", "similar_examples"):
        raw = s.get(field)
        s[field] = json.loads(raw) if raw else []
    s["email_sent"] = bool(s.get("email_sent", 0))
    return s


@router.get("")
async def list_suggestions(
    brand_id: int = Query(1),
    date_filter: Optional[str] = Query(None, alias="date"),
) -> Dict[str, Any]:
    """List suggestions for a brand on a given date."""
    target_date = date_filter or today_str()

    with db.get_cursor() as cur:
        cur.execute(
            "SELECT * FROM suggestions WHERE brand_id = ? AND date = ? ORDER BY viral_score DESC",
            (brand_id, target_date),
        )
        rows = cur.fetchall()

    if not rows:
        return {"date": target_date, "suggestions": [], "generated_at": None}

    suggestions = [_row_to_suggestion(r) for r in rows]
    generated_at = suggestions[0].get("generated_at") if suggestions else None

    return {
        "date": target_date,
        "generated_at": generated_at,
        "suggestions": suggestions,
        "email_sent": any(s.get("email_sent") for s in suggestions),
    }


@router.get("/dates")
async def list_available_dates(brand_id: int = Query(1)) -> Dict[str, Any]:
    """List all dates that have suggestions for a brand."""
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT date FROM suggestions WHERE brand_id = ? ORDER BY date DESC",
            (brand_id,),
        )
        rows = cur.fetchall()
    return {"dates": [r["date"] for r in rows]}


@router.get("/{suggestion_id}")
async def get_suggestion(suggestion_id: str, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Get a single suggestion by ID."""
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT * FROM suggestions WHERE id = ? AND brand_id = ?",
            (suggestion_id, brand_id),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return _row_to_suggestion(row)


@router.post("/{suggestion_id}/feedback")
async def submit_feedback(
    suggestion_id: str,
    req: FeedbackRequest,
    brand_id: int = Query(1),
) -> Dict[str, Any]:
    """Submit like/dislike feedback for a suggestion."""
    if req.action not in ("liked", "disliked"):
        raise HTTPException(status_code=400, detail="Action must be 'liked' or 'disliked'")

    now = now_str()

    with db.get_cursor() as cur:
        cur.execute(
            "SELECT id, platform, content_type FROM suggestions WHERE id = ? AND brand_id = ?",
            (suggestion_id, brand_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        platform = row["platform"]
        content_type = row["content_type"]

        cur.execute(
            "UPDATE suggestions SET feedback = ?, feedback_reason = ?, feedback_at = ? WHERE id = ? AND brand_id = ?",
            (req.action, req.reason, now, suggestion_id, brand_id),
        )

    with db.get_cursor() as cur:
        cur.execute(
            "INSERT INTO feedback (brand_id, suggestion_id, action, platform, content_type, reason, feedback_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (brand_id, suggestion_id, req.action, platform, content_type, req.reason, now),
        )

    return {"status": "ok", "suggestion_id": suggestion_id, "action": req.action}
