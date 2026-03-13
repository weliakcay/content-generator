from __future__ import annotations

import requests
from typing import Optional
from utils.logger import get_logger
import config

logger = get_logger("pinterest_client")

BASE_URLS = {
    "sandbox": "https://api-sandbox.pinterest.com/v5",
    "production": "https://api.pinterest.com/v5",
}


class PinterestClient:
    """Pinterest API v5 client for board/pin management and analytics."""

    def __init__(self, access_token: str = None, env: str = None):
        self.access_token = access_token or config.PINTEREST_ACCESS_TOKEN
        self.env = env or config.PINTEREST_ENV
        self.base_url = BASE_URLS.get(self.env, BASE_URLS["sandbox"])
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an authenticated request to Pinterest API."""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("headers", self.headers)

        logger.info(f"{method.upper()} {url}")
        resp = requests.request(method, url, **kwargs)

        if resp.status_code >= 400:
            logger.error(f"Pinterest API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()

        return resp.json()

    # ── Auth / Account ──────────────────────────────────────────────

    def get_account(self) -> dict:
        """Get authenticated user account info."""
        return self._request("GET", "/user_account")

    def test_connection(self) -> dict:
        """Test API connection and return status."""
        try:
            account = self.get_account()
            return {
                "status": "ok",
                "username": account.get("username", ""),
                "env": self.env,
                "base_url": self.base_url,
            }
        except requests.HTTPError as e:
            return {
                "status": "error",
                "error": str(e),
                "env": self.env,
                "hint": "Token scope'larini kontrol edin: boards:read, boards:write, pins:read, pins:write, user_accounts:read",
            }

    # ── Boards ──────────────────────────────────────────────────────

    def get_boards(self, page_size: int = 25, bookmark: str = None) -> dict:
        """List all boards for authenticated user."""
        params = {"page_size": page_size}
        if bookmark:
            params["bookmark"] = bookmark
        return self._request("GET", "/boards", params=params)

    def get_board(self, board_id: str) -> dict:
        """Get a specific board by ID."""
        return self._request("GET", f"/boards/{board_id}")

    def create_board(self, name: str, description: str = "", privacy: str = "PUBLIC") -> dict:
        """Create a new board."""
        data = {
            "name": name,
            "description": description,
            "privacy": privacy,
        }
        return self._request("POST", "/boards", json=data)

    def get_board_pins(self, board_id: str, page_size: int = 25) -> dict:
        """List pins on a board."""
        params = {"page_size": page_size}
        return self._request("GET", f"/boards/{board_id}/pins", params=params)

    # ── Pins ────────────────────────────────────────────────────────

    def create_pin(
        self,
        board_id: str,
        title: str,
        description: str,
        image_url: str,
        link: Optional[str] = None,
        alt_text: Optional[str] = None,
    ) -> dict:
        """Create a pin on a board.

        Args:
            board_id: Target board ID
            title: Pin title (max 100 chars)
            description: Pin description
            image_url: Public URL of the image to pin
            link: Destination URL when pin is clicked
            alt_text: Alt text for accessibility
        """
        data = {
            "board_id": board_id,
            "title": title[:100],
            "description": description,
            "media_source": {
                "source_type": "image_url",
                "url": image_url,
            },
        }
        if link:
            data["link"] = link
        if alt_text:
            data["alt_text"] = alt_text

        logger.info(f"Creating pin: '{title}' on board {board_id}")
        return self._request("POST", "/pins", json=data)

    def get_pin(self, pin_id: str) -> dict:
        """Get a specific pin by ID."""
        return self._request("GET", f"/pins/{pin_id}")

    def delete_pin(self, pin_id: str) -> None:
        """Delete a pin."""
        url = f"{self.base_url}/pins/{pin_id}"
        resp = requests.delete(url, headers=self.headers)
        resp.raise_for_status()
        logger.info(f"Deleted pin: {pin_id}")

    # ── Analytics ───────────────────────────────────────────────────

    def get_pin_analytics(
        self,
        pin_id: str,
        start_date: str,
        end_date: str,
        metric_types: list = None,
    ) -> dict:
        """Get analytics for a specific pin.

        Args:
            pin_id: Pin ID
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            metric_types: List of metrics (IMPRESSION, PIN_CLICK, OUTBOUND_CLICK, SAVE, etc.)
        """
        if metric_types is None:
            metric_types = ["IMPRESSION", "PIN_CLICK", "SAVE", "OUTBOUND_CLICK"]

        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": ",".join(metric_types),
            "app_types": "ALL",
        }
        return self._request("GET", f"/pins/{pin_id}/analytics", params=params)

    def get_account_analytics(
        self,
        start_date: str,
        end_date: str,
        metric_types: list = None,
    ) -> dict:
        """Get account-level analytics.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            metric_types: List of metrics
        """
        if metric_types is None:
            metric_types = ["IMPRESSION", "PIN_CLICK", "SAVE", "OUTBOUND_CLICK", "ENGAGEMENT"]

        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": ",".join(metric_types),
            "app_types": "ALL",
        }
        return self._request("GET", "/user_account/analytics", params=params)
