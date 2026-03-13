from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class Suggestion(BaseModel):
    """A single content suggestion for a platform."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    platform: str
    content_type: str
    title: str
    caption: str
    hashtags: List[str] = []
    visual_concept: str = ""
    cta: str = ""
    publish_time: str = ""
    publish_reason: str = ""
    similar_examples: List[str] = []
    viral_score: float = 0.0
    trend_source: str = ""
    feedback: Optional[str] = None
    feedback_reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return self.model_dump()


class DailySuggestions(BaseModel):
    """Container for a day's worth of suggestions."""
    date: str
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    suggestions: List[Suggestion] = []
    trends_used: List[Dict] = []
    email_sent: bool = False
    email_sent_at: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump()
