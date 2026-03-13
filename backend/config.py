import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR.parent / "data"))

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Email
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")

# API Server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Pinterest API
PINTEREST_APP_ID = os.getenv("PINTEREST_APP_ID", "")
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "")
PINTEREST_ENV = os.getenv("PINTEREST_ENV", "sandbox")

# Scraping
SCRAPE_RATE_LIMIT = int(os.getenv("SCRAPE_RATE_LIMIT_SECONDS", "3"))
SCRAPE_MAX_RETRIES = int(os.getenv("SCRAPE_MAX_RETRIES", "3"))
SCRAPE_HEADLESS = os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"

# Schedule
DAILY_RUN_TIME = os.getenv("DAILY_RUN_TIME", "08:00")
SUGGESTIONS_COUNT = int(os.getenv("SUGGESTIONS_COUNT", "5"))

# Database
DB_PATH = DATA_DIR / "content_generator.db"

# Data file paths
BRAND_PROFILE_PATH = DATA_DIR / "brand_profile.json"
TRACKING_CONFIG_PATH = DATA_DIR / "tracking_config.json"
FEEDBACK_PATH = DATA_DIR / "feedback.json"
SEARCH_LOGS_PATH = DATA_DIR / "search_logs.json"
SUGGESTIONS_DIR = DATA_DIR / "suggestions"
TRENDS_DIR = DATA_DIR / "trends"


def load_brand_profile() -> dict:
    from utils.json_store import JsonStore
    return JsonStore(BRAND_PROFILE_PATH).read()


def load_tracking_config() -> dict:
    from utils.json_store import JsonStore
    return JsonStore(TRACKING_CONFIG_PATH).read()


def load_feedback() -> dict:
    from utils.json_store import JsonStore
    return JsonStore(FEEDBACK_PATH).read()
