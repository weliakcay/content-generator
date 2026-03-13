"""Multi-brand management API routes."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db

router = APIRouter()


# ── Pydantic models ─────────────────────────────────────────────────────────

class BrandCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    website_url: Optional[str] = None
    description: Optional[str] = None


class BrandUpdate(BaseModel):
    name: Optional[str] = None
    website_url: Optional[str] = None
    description: Optional[str] = None
    profile_json: Optional[Dict[str, Any]] = None
    identity_json: Optional[Dict[str, Any]] = None
    tracking_json: Optional[Dict[str, Any]] = None
    pinterest_identity_json: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "brand"


def _parse_brand_row(row: Any) -> Dict[str, Any]:
    """Convert a sqlite3.Row to dict, parsing JSON blobs."""
    result = dict(row)
    for field in ("profile_json", "identity_json", "tracking_json", "pinterest_identity_json"):
        raw = result.get(field)
        if raw:
            try:
                result[field] = json.loads(raw)
            except Exception:
                result[field] = {}
        else:
            result[field] = {}
    result["is_active"] = bool(result.get("is_active", 1))
    return result


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_brands() -> Dict[str, Any]:
    """List all brands."""
    with db.get_cursor() as cur:
        cur.execute(
            "SELECT id, name, slug, website_url, description, is_active, created_at, updated_at "
            "FROM brands ORDER BY id"
        )
        rows = cur.fetchall()
    return {
        "brands": [
            {
                "id": r["id"],
                "name": r["name"],
                "slug": r["slug"],
                "website_url": r["website_url"],
                "description": r["description"],
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    }


@router.post("", status_code=201)
async def create_brand(data: BrandCreate) -> Dict[str, Any]:
    """Create a new brand."""
    slug = data.slug or _slugify(data.name)

    # Check slug uniqueness
    with db.get_cursor() as cur:
        cur.execute("SELECT id FROM brands WHERE slug = ?", (slug,))
        if cur.fetchone():
            # Append a suffix to make it unique
            with db.get_cursor() as cur2:
                cur2.execute("SELECT COUNT(*) as c FROM brands")
                count = cur2.fetchone()["c"]
            slug = f"{slug}-{count + 1}"

    default_profile: Dict[str, Any] = {
        "brand_name": data.name,
        "tone_of_voice": "",
        "core_values": [],
        "target_audience": "",
        "product_categories": [],
        "dont_use": [],
        "language": "Turkish",
        "platforms": {
            "pinterest": {
                "priority": "high",
                "style": "",
                "daily_suggestions": 2,
                "content_types": ["pin"],
                "preferred_formats": [],
            },
            "instagram": {
                "priority": "high",
                "style": "",
                "daily_suggestions": 2,
                "content_types": ["post", "reel"],
                "preferred_formats": [],
            },
            "tiktok": {
                "priority": "medium",
                "style": "",
                "daily_suggestions": 1,
                "content_types": ["video"],
                "preferred_formats": [],
            },
        },
        "content_guidelines": {
            "max_hashtags": 15,
            "use_emojis": True,
            "include_cta": True,
            "sfw_only": True,
        },
    }

    with db.get_cursor() as cur:
        cur.execute(
            """INSERT INTO brands (name, slug, website_url, description, profile_json)
               VALUES (?, ?, ?, ?, ?)""",
            (data.name, slug, data.website_url, data.description, json.dumps(default_profile)),
        )
        brand_id = cur.lastrowid

    return {"id": brand_id, "name": data.name, "slug": slug, "status": "created"}


@router.get("/{brand_id}")
async def get_brand(brand_id: int) -> Dict[str, Any]:
    """Get a brand by ID including all JSON config blobs."""
    with db.get_cursor() as cur:
        cur.execute("SELECT * FROM brands WHERE id = ?", (brand_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Brand not found")
    return _parse_brand_row(row)


@router.put("/{brand_id}")
async def update_brand(brand_id: int, data: BrandUpdate) -> Dict[str, Any]:
    """Update brand fields. Only provided fields are updated."""
    updates: List[str] = []
    values: List[Any] = []

    if data.name is not None:
        updates.append("name = ?")
        values.append(data.name)
    if data.website_url is not None:
        updates.append("website_url = ?")
        values.append(data.website_url)
    if data.description is not None:
        updates.append("description = ?")
        values.append(data.description)
    if data.profile_json is not None:
        updates.append("profile_json = ?")
        values.append(json.dumps(data.profile_json))
    if data.identity_json is not None:
        updates.append("identity_json = ?")
        values.append(json.dumps(data.identity_json))
    if data.tracking_json is not None:
        updates.append("tracking_json = ?")
        values.append(json.dumps(data.tracking_json))
    if data.pinterest_identity_json is not None:
        updates.append("pinterest_identity_json = ?")
        values.append(json.dumps(data.pinterest_identity_json))
    if data.is_active is not None:
        updates.append("is_active = ?")
        values.append(1 if data.is_active else 0)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = datetime('now')")
    values.append(brand_id)

    with db.get_cursor() as cur:
        cur.execute(
            f"UPDATE brands SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Brand not found")

    return {"status": "ok", "brand_id": brand_id}


@router.delete("/{brand_id}")
async def delete_brand(brand_id: int) -> Dict[str, Any]:
    """Delete a brand. Brand id=1 (Wellco Adult) cannot be deleted."""
    if brand_id == 1:
        raise HTTPException(status_code=400, detail="Default brand cannot be deleted")

    with db.get_cursor() as cur:
        cur.execute("SELECT id FROM brands WHERE id = ?", (brand_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Brand not found")
        cur.execute("DELETE FROM brands WHERE id = ?", (brand_id,))

    return {"status": "ok", "deleted_brand_id": brand_id}
