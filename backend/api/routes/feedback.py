"""Feedback API routes - reads from SQLite."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query

import db

router = APIRouter()


@router.get("")
async def get_feedback(brand_id: int = Query(1)) -> Dict[str, Any]:
    """Get all feedback data for a brand."""
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT * FROM feedback WHERE brand_id = ? ORDER BY feedback_at DESC",
            (brand_id,),
        )
        rows = cur.fetchall()

    approved = [dict(r) for r in rows if r["action"] == "liked"]
    rejected = [dict(r) for r in rows if r["action"] == "disliked"]

    return {
        "approved_suggestions": approved,
        "rejected_suggestions": rejected,
    }


@router.get("/summary")
async def get_feedback_summary(brand_id: int = Query(1)) -> Dict[str, Any]:
    """Get feedback summary with platform/type breakdown."""
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT action, platform, content_type FROM feedback WHERE brand_id = ?",
            (brand_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]

    approved = [r for r in rows if r["action"] == "liked"]
    rejected = [r for r in rows if r["action"] == "disliked"]
    total = len(rows)

    platform_stats: Dict[str, Dict[str, int]] = {}
    for item in approved:
        p = item.get("platform") or "unknown"
        platform_stats.setdefault(p, {"liked": 0, "disliked": 0})
        platform_stats[p]["liked"] += 1
    for item in rejected:
        p = item.get("platform") or "unknown"
        platform_stats.setdefault(p, {"liked": 0, "disliked": 0})
        platform_stats[p]["disliked"] += 1

    type_stats: Dict[str, Dict[str, int]] = {}
    for item in approved:
        t = item.get("content_type") or "unknown"
        type_stats.setdefault(t, {"liked": 0, "disliked": 0})
        type_stats[t]["liked"] += 1
    for item in rejected:
        t = item.get("content_type") or "unknown"
        type_stats.setdefault(t, {"liked": 0, "disliked": 0})
        type_stats[t]["disliked"] += 1

    return {
        "total_feedback": total,
        "total_liked": len(approved),
        "total_disliked": len(rejected),
        "approval_rate": len(approved) / total if total > 0 else 0,
        "platform_stats": platform_stats,
        "content_type_stats": type_stats,
    }
