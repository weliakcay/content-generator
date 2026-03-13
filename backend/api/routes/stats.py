"""Statistics API routes - queries SQLite."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Query

import db

router = APIRouter()


@router.get("")
async def get_stats(brand_id: int = Query(1)) -> Dict[str, Any]:
    """Get overall statistics for a brand."""
    with db.get_cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) as total, AVG(viral_score) as avg_score,
                      COUNT(DISTINCT date) as total_days
               FROM suggestions WHERE brand_id = ?""",
            (brand_id,),
        )
        row = dict(cur.fetchone())

        cur.execute(
            """SELECT platform, COUNT(*) as count
               FROM suggestions WHERE brand_id = ?
               GROUP BY platform""",
            (brand_id,),
        )
        platform_counts = {r["platform"]: r["count"] for r in cur.fetchall()}

        cur.execute(
            "SELECT COUNT(*) as c FROM feedback WHERE brand_id = ? AND action = 'liked'",
            (brand_id,),
        )
        approved = cur.fetchone()["c"]

        cur.execute(
            "SELECT COUNT(*) as c FROM feedback WHERE brand_id = ? AND action = 'disliked'",
            (brand_id,),
        )
        rejected = cur.fetchone()["c"]

        cur.execute(
            "SELECT COUNT(*) as c FROM search_logs WHERE brand_id = ?",
            (brand_id,),
        )
        total_searches = cur.fetchone()["c"]

    total_feedback = approved + rejected

    return {
        "total_suggestions": row.get("total", 0),
        "total_days": row.get("total_days", 0),
        "avg_viral_score": round(row.get("avg_score") or 0, 1),
        "total_searches": total_searches,
        "total_feedback": total_feedback,
        "approval_rate": approved / max(total_feedback, 1),
        "platform_distribution": platform_counts,
    }


@router.get("/daily")
async def get_daily_stats(brand_id: int = Query(1)) -> Dict[str, Any]:
    """Get daily stats for the last 30 days."""
    today = date.today()
    daily_data: List[Dict[str, Any]] = []

    for i in range(30):
        d = today - timedelta(days=i)
        date_str = d.isoformat()

        with db.get_cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) as cnt, AVG(viral_score) as avg_score,
                          SUM(CASE WHEN feedback='liked' THEN 1 ELSE 0 END) as liked,
                          SUM(CASE WHEN feedback='disliked' THEN 1 ELSE 0 END) as disliked,
                          MAX(email_sent) as email_sent
                   FROM suggestions WHERE brand_id = ? AND date = ?""",
                (brand_id, date_str),
            )
            row = dict(cur.fetchone())

        daily_data.append({
            "date": date_str,
            "suggestions_count": row.get("cnt") or 0,
            "avg_viral_score": round(row.get("avg_score") or 0, 1),
            "liked": row.get("liked") or 0,
            "disliked": row.get("disliked") or 0,
            "email_sent": bool(row.get("email_sent")),
        })

    return {"daily": list(reversed(daily_data))}
