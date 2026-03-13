"""Manual pipeline trigger API routes."""
from __future__ import annotations

import threading
from typing import Any, Dict

from fastapi import APIRouter, Query

router = APIRouter()

_pipeline_running = False
_pipeline_lock = threading.Lock()


@router.post("")
async def trigger_pipeline(
    brand_id: int = Query(1),
    skip_scrape: bool = False,
    skip_email: bool = False,
) -> Dict[str, Any]:
    """Trigger a manual pipeline run for a brand."""
    global _pipeline_running

    with _pipeline_lock:
        if _pipeline_running:
            return {"status": "already_running", "message": "Pipeline zaten çalışıyor"}
        _pipeline_running = True

    def run() -> None:
        global _pipeline_running
        try:
            from main import run_pipeline
            run_pipeline(brand_id=brand_id, skip_scrape=skip_scrape, skip_email=skip_email)
        finally:
            with _pipeline_lock:
                _pipeline_running = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    return {"status": "started", "message": "Pipeline başlatıldı"}


@router.get("/status")
async def pipeline_status() -> Dict[str, bool]:
    """Check if pipeline is currently running."""
    return {"running": _pipeline_running}
