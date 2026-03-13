"""Tracking config API routes - reads/writes brand tracking_json from SQLite."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db
from utils.date_utils import format_timestamp, today_str

router = APIRouter()


class InfluencerRequest(BaseModel):
    name: str
    platform: str
    handle: str
    relevance: str = ""
    active: bool = True


class HashtagRequest(BaseModel):
    tag: str
    platform: str
    priority: str = "medium"


class KeywordRequest(BaseModel):
    keyword: str
    platforms: List[str]
    search_frequency: str = "daily"


def _get_tracking(brand_id: int) -> Dict[str, Any]:
    with db.get_cursor() as cur:
        cur.execute("SELECT tracking_json FROM brands WHERE id = ?", (brand_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Brand not found")
    return json.loads(row["tracking_json"] or "{}")


def _save_tracking(brand_id: int, data: Dict[str, Any]) -> None:
    data["updated_at"] = format_timestamp()
    with db.get_cursor() as cur:
        cur.execute(
            "UPDATE brands SET tracking_json = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(data), brand_id),
        )


@router.get("")
async def get_tracking_config(brand_id: int = Query(1)) -> Dict[str, Any]:
    """Get the tracking configuration for a brand."""
    return _get_tracking(brand_id)


@router.put("")
async def update_tracking_config(data: dict, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Replace the full tracking configuration for a brand."""
    _save_tracking(brand_id, data)
    return {"status": "ok", "message": "Tracking config updated"}


@router.post("/influencers")
async def add_influencer(req: InfluencerRequest, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Add a new influencer to track."""
    data = _get_tracking(brand_id)
    data.setdefault("influencers", []).append({
        "name": req.name,
        "platform": req.platform,
        "handle": req.handle,
        "relevance": req.relevance,
        "added_date": today_str(),
        "active": req.active,
    })
    _save_tracking(brand_id, data)
    return {"status": "ok", "message": f"Influencer {req.handle} added"}


@router.delete("/influencers/{handle}")
async def remove_influencer(handle: str, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Remove an influencer from tracking."""
    data = _get_tracking(brand_id)
    data["influencers"] = [
        i for i in data.get("influencers", [])
        if i.get("handle") != handle and i.get("handle") != f"@{handle}"
    ]
    _save_tracking(brand_id, data)
    return {"status": "ok", "message": f"Influencer {handle} removed"}


@router.post("/hashtags")
async def add_hashtag(req: HashtagRequest, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Add a new hashtag to track."""
    data = _get_tracking(brand_id)
    data.setdefault("hashtags", []).append({
        "tag": req.tag if req.tag.startswith("#") else f"#{req.tag}",
        "platform": req.platform,
        "priority": req.priority,
        "added_date": today_str(),
    })
    _save_tracking(brand_id, data)
    return {"status": "ok", "message": f"Hashtag {req.tag} added"}


@router.delete("/hashtags/{tag}")
async def remove_hashtag(tag: str, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Remove a hashtag from tracking."""
    data = _get_tracking(brand_id)
    data["hashtags"] = [
        h for h in data.get("hashtags", [])
        if h.get("tag") != f"#{tag}" and h.get("tag") != tag
    ]
    _save_tracking(brand_id, data)
    return {"status": "ok", "message": f"Hashtag {tag} removed"}


@router.post("/keywords")
async def add_keyword(req: KeywordRequest, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Add a new keyword to track."""
    data = _get_tracking(brand_id)
    data.setdefault("keywords", []).append({
        "keyword": req.keyword,
        "platforms": req.platforms,
        "search_frequency": req.search_frequency,
    })
    _save_tracking(brand_id, data)
    return {"status": "ok", "message": f"Keyword '{req.keyword}' added"}


@router.delete("/keywords/{keyword}")
async def remove_keyword(keyword: str, brand_id: int = Query(1)) -> Dict[str, Any]:
    """Remove a keyword from tracking."""
    data = _get_tracking(brand_id)
    data["keywords"] = [
        k for k in data.get("keywords", [])
        if k.get("keyword") != keyword
    ]
    _save_tracking(brand_id, data)
    return {"status": "ok", "message": f"Keyword '{keyword}' removed"}
