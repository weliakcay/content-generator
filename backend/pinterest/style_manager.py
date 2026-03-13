from __future__ import annotations

import json
import random
from pathlib import Path
from utils.logger import get_logger
from utils.json_store import JsonStore

logger = get_logger("style_manager")

PINTEREST_DIR = Path(__file__).parent
HISTORY_PATH = PINTEREST_DIR / "style_history.json"
GEM_PATH = PINTEREST_DIR / "gem_instructions.json"


class StyleManager:
    """Manages style and palette rotation to ensure visual variety."""

    def __init__(self):
        self.store = JsonStore(HISTORY_PATH)
        self.gem = self._load_gem()
        self.styles = list(self.gem.get("styles", {}).keys())
        self.palettes = list(self.gem.get("palettes", {}).keys())

    def _load_gem(self) -> dict:
        with open(GEM_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_history(self, limit: int = 10) -> list:
        """Get recent style history."""
        data = self.store.read()
        history = data.get("history", [])
        return history[-limit:]

    def get_recent_styles(self, count: int = 3) -> list:
        """Get last N used style+palette combos."""
        history = self.get_history(count)
        return [(h.get("style"), h.get("palette")) for h in history]

    def select_next(self, board: str = None) -> dict:
        """Select next style and palette, avoiding recent repeats.

        Returns dict with: style_code, style_name, style_details, palette_code, palette_details
        """
        recent = self.get_recent_styles(3)
        recent_styles = [s for s, p in recent]
        recent_palettes = [p for s, p in recent]

        # Filter styles suitable for this board
        available_styles = self.styles.copy()
        if board:
            preferred = []
            for code in self.styles:
                style_data = self.gem["styles"][code]
                if board in style_data.get("use_for", []):
                    preferred.append(code)
            if preferred:
                available_styles = preferred

        # Remove recently used styles
        fresh_styles = [s for s in available_styles if s not in recent_styles]
        if not fresh_styles:
            fresh_styles = available_styles  # All used recently, allow any

        # Remove recently used palettes
        fresh_palettes = [p for p in self.palettes if p not in recent_palettes]
        if not fresh_palettes:
            fresh_palettes = self.palettes

        # Select
        style_code = random.choice(fresh_styles)
        palette_code = random.choice(fresh_palettes)

        style_details = self.gem["styles"][style_code]
        palette_details = self.gem["palettes"][palette_code]

        logger.info(f"Selected style: {style_code} ({style_details['name']}), palette: {palette_code} ({palette_details['name']})")

        return {
            "style_code": style_code,
            "style_name": style_details["name"],
            "style_details": style_details,
            "palette_code": palette_code,
            "palette_name": palette_details["name"],
            "palette_details": palette_details,
        }

    def record(self, date: str, style_code: str, palette_code: str, board: str = "", pin_title: str = ""):
        """Record a style+palette usage."""
        data = self.store.read()
        if "history" not in data:
            data["history"] = []

        data["history"].append({
            "date": date,
            "style": style_code,
            "palette": palette_code,
            "board": board,
            "pin_title": pin_title,
        })

        # Keep last 90 entries
        data["history"] = data["history"][-90:]
        self.store.write(data)
        logger.info(f"Recorded: {date} - {style_code}/{palette_code}")

    def get_rotation_stats(self) -> dict:
        """Get stats about style/palette usage for dashboard."""
        history = self.get_history(30)
        style_counts = {}
        palette_counts = {}

        for h in history:
            s = h.get("style", "")
            p = h.get("palette", "")
            style_counts[s] = style_counts.get(s, 0) + 1
            palette_counts[p] = palette_counts.get(p, 0) + 1

        return {
            "total_pins": len(history),
            "style_distribution": style_counts,
            "palette_distribution": palette_counts,
            "last_3": self.get_recent_styles(3),
        }
