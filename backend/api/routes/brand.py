"""Brand profile API route (single-brand backward compat) - reads from SQLite brand_id=1."""
from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter
from utils.date_utils import format_timestamp

import db

router = APIRouter()


@router.get("")
async def get_brand_profile() -> Dict[str, Any]:
    """Get the brand profile for brand_id=1 (Wellco Adult)."""
    with db.get_cursor() as cur:
        cur.execute("SELECT profile_json FROM brands WHERE id = 1")
        row = cur.fetchone()

    if not row or not row["profile_json"]:
        return {}

    return json.loads(row["profile_json"])


@router.put("")
async def update_brand_profile(data: dict) -> Dict[str, Any]:
    """Update the brand profile for brand_id=1."""
    data["updated_at"] = format_timestamp()
    with db.get_cursor() as cur:
        cur.execute(
            "UPDATE brands SET profile_json = ?, updated_at = datetime('now') WHERE id = 1",
            (json.dumps(data),),
        )
    return {"status": "ok", "message": "Brand profile updated"}
