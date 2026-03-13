"""Search logs API routes - reads from SQLite."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

import db

router = APIRouter()


@router.get("")
async def get_search_logs(
    brand_id: int = Query(1),
    platform: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Get search logs with optional platform filter."""
    query = "SELECT * FROM search_logs WHERE brand_id = ?"
    params: list = [brand_id]

    if platform:
        query += " AND platform = ?"
        params.append(platform)

    query += " ORDER BY logged_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with db.get_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

        # Count total without pagination
        count_query = "SELECT COUNT(*) as c FROM search_logs WHERE brand_id = ?"
        count_params: list = [brand_id]
        if platform:
            count_query += " AND platform = ?"
            count_params.append(platform)
        cur.execute(count_query, count_params)
        total = cur.fetchone()["c"]

    logs = []
    for r in rows:
        log = dict(r)
        log["top_results"] = json.loads(log.get("top_results") or "[]")
        logs.append(log)

    return {"logs": logs, "total": total, "limit": limit, "offset": offset}
