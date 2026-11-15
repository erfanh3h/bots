"""
Notification Hub Actions for Cafe Fekr Social Bots.
"""

from typing import Any, Dict, Optional, Tuple
from .client import SocialApiClient


class NotificationActions:
    """Encapsulates all notification retrieval and preference actions."""

    def __init__(self, client: SocialApiClient):
        self.client = client

    def list_notifications(
        self,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 40
    ) -> Tuple[bool, int, Any]:
        """Fetch list of social notifications."""
        return self.client.get("/notifications/list", {
            "unread_only": unread_only,
            "skip": skip,
            "limit": limit
        })

    def mark_read(self, notification_id: str) -> Tuple[bool, int, Any]:
        """Mark a single notification as read."""
        return self.client.post("/notifications/read", {
            "notification_id": notification_id.strip()
        })

    def mark_all_read(self) -> Tuple[bool, int, Any]:
        """Mark all incoming notifications as read in bulk."""
        return self.client.post("/notifications/read-all", {})

    def update_preferences(self, preferences: Dict[str, bool]) -> Tuple[bool, int, Any]:
        """Update notification push and in-game preferences."""
        return self.client.post("/notifications/preferences", preferences)
