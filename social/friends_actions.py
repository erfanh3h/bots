"""
Friends and Player Relations Actions for Cafe Fekr Social Bots.
"""

from typing import Any, Dict, Optional, Tuple
from .client import SocialApiClient


class FriendsActions:
    """Encapsulates all friend-related social actions."""

    def __init__(self, client: SocialApiClient):
        self.client = client

    def search_players(self, query: str = "", limit: int = 25) -> Tuple[bool, int, Any]:
        """Search registered players by username or display name."""
        return self.client.get("/social/players/search", {"q": query, "limit": limit})

    def get_discover(self, limit: int = 15) -> Tuple[bool, int, Any]:
        """Get recommended friends and recent co-players."""
        return self.client.get("/social/friends/discover", {"limit": limit})

    def list_friends(self) -> Tuple[bool, int, Any]:
        """Retrieve list of confirmed friends with live presence."""
        return self.client.get("/social/friends")

    def list_requests(self) -> Tuple[bool, int, Any]:
        """Get pending incoming and outgoing friend requests."""
        return self.client.get("/social/friends/requests")

    def send_request(self, target_user_id: str, message: str = "") -> Tuple[bool, int, Any]:
        """Send a friend request to a target player."""
        return self.client.post("/social/friends/request", {
            "target_user_id": str(target_user_id).strip(),
            "message": message
        })

    def respond_request(self, request_id: str, action: str = "accept") -> Tuple[bool, int, Any]:
        """Respond to an incoming friend request ('accept' or 'reject')."""
        return self.client.post("/social/friends/respond", {
            "request_id": str(request_id).strip(),
            "action": action
        })

    def remove_friend(self, target_user_id: str) -> Tuple[bool, int, Any]:
        """Remove a player from friends list."""
        return self.client.post("/social/friends/remove", {
            "target_user_id": str(target_user_id).strip()
        })

    def block_player(self, target_user_id: str, reason: str = "") -> Tuple[bool, int, Any]:
        """Block a player to prevent messages and game invites."""
        return self.client.post("/social/block", {
            "target_user_id": str(target_user_id).strip(),
            "reason": reason
        })

    def unblock_player(self, target_user_id: str) -> Tuple[bool, int, Any]:
        """Unblock a previously blocked player."""
        return self.client.post("/social/unblock", {
            "target_user_id": str(target_user_id).strip()
        })

    def get_blocked(self) -> Tuple[bool, int, Any]:
        """Retrieve list of all currently blocked players."""
        return self.client.get("/social/blocks")
