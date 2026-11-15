"""
Direct Messaging and Chat Operations for Cafe Fekr Social Bots.
"""

from typing import Any, Dict, Optional, Tuple
from .client import SocialApiClient


class MessagingActions:
    """Encapsulates all direct messaging and private conversation actions."""

    def __init__(self, client: SocialApiClient):
        self.client = client

    def list_conversations(self, skip: int = 0, limit: int = 40) -> Tuple[bool, int, Any]:
        """Retrieve recent active direct message conversations."""
        return self.client.get("/messages/conversations", {
            "skip": skip,
            "limit": limit
        })

    def get_messages(self, partner_id: str, skip: int = 0, limit: int = 50) -> Tuple[bool, int, Any]:
        """Fetch conversation message thread with a specific partner."""
        return self.client.get(f"/messages/direct/{partner_id.strip()}", {
            "skip": skip,
            "limit": limit
        })

    def send_dm(self, recipient_id: str, text: str) -> Tuple[bool, int, Any]:
        """Send a direct message to a player."""
        return self.client.post("/messages/direct/send", {
            "to_user_id": recipient_id.strip(),
            "recipient_id": recipient_id.strip(),
            "text": text
        })

    def mark_read(self, partner_id: str) -> Tuple[bool, int, Any]:
        """Acknowledge and mark messages from a partner as read."""
        return self.client.post("/messages/direct/read", {
            "partner_id": partner_id.strip()
        })
