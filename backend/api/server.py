"""FastAPI server for the Wellco Adult Content Generator dashboard."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    suggestions, brand, brands, tracking, feedback,
    search_logs, stats, manual_run, pinterest,
    onboarding, brand_research, chat,
)
from db import init_db

app = FastAPI(
    title="Wellco Adult Content Generator API",
    version="1.0.0",
    description="Backend API for content generation dashboard",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suggestions.router, prefix="/api/suggestions", tags=["suggestions"])
app.include_router(brand.router, prefix="/api/brand", tags=["brand"])
app.include_router(brands.router, prefix="/api/brands", tags=["brands"])
app.include_router(tracking.router, prefix="/api/tracking", tags=["tracking"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(search_logs.router, prefix="/api/search-logs", tags=["search-logs"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(manual_run.router, prefix="/api/manual-run", tags=["manual-run"])
app.include_router(pinterest.router)
app.include_router(onboarding.router, prefix="/api/onboarding", tags=["onboarding"])
app.include_router(brand_research.router, prefix="/api/brands", tags=["brand-research"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "wellco-content-generator"}
