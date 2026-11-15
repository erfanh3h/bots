"""
Direct Match Invitations, Public Profiles, and Presence Actions for Cafe Fekr Social Bots.
"""

from typing import Any, Dict, Optional, Tuple
from .client import SocialApiClient


class InvitationActions:
    """Encapsulates game match invitations, public profile queries, and reports."""

    def __init__(self, client: SocialApiClient):
        self.client = client

    def send_game_invite(
        self,
        target_user_id: str,
        game_type: str = "Ludo",
        invite_mode: str = "direct_match",
        lobby_id: str = "",
        player_count: int = 2
    ) -> Tuple[bool, int, Any]:
        """Send a direct game challenge invitation to another player."""
        return self.client.post("/social/invitations/send", {
            "to_user_id": target_user_id.strip(),
            "target_user_id": target_user_id.strip(),
            "game_type": game_type,
            "invite_mode": invite_mode,
            "lobby_id": lobby_id,
            "player_count": player_count
        })

    def list_game_invites(self) -> Tuple[bool, int, Any]:
        """Retrieve incoming game match invitations."""
        return self.client.get("/social/invitations")

    def respond_game_invite(self, invite_id: str, action: str = "accept") -> Tuple[bool, int, Any]:
        """Accept or decline an incoming game match invitation."""
        return self.client.post("/social/invitations/respond", {
            "invite_id": invite_id.strip(),
            "action": action
        })

    def get_public_profile(self, target_user_id: str) -> Tuple[bool, int, Any]:
        """Retrieve full public card for any player (stats, clan, cosmetics, presence)."""
        return self.client.get(f"/social/profile/{target_user_id.strip()}")

    def customize_profile(
        self,
        avatar: Optional[int] = None,
        profile_frame: Optional[int] = None,
        profile_title: Optional[str] = None,
        status_message: Optional[str] = None
    ) -> Tuple[bool, int, Any]:
        """Update active player's cosmetic loadout and status bio."""
        payload = {}
        if avatar is not None:
            payload["avatar"] = int(avatar)
        if profile_frame is not None:
            payload["profile_frame"] = int(profile_frame)
        if profile_title is not None:
            payload["profile_title"] = str(profile_title).strip()
        if status_message is not None:
            payload["status_message"] = str(status_message).strip()
        return self.client.post("/social/profile/customize", payload)

    def get_overview(self) -> Tuple[bool, int, Any]:
        """Fetch general social overview with unread counters and presence."""
        return self.client.get("/social/overview")

    def get_leaderboards(
        self,
        board_type: str = "global_score",
        game_type: str = "",
        clan_id: str = ""
    ) -> Tuple[bool, int, Any]:
        """Retrieve social, competitive, or clan leaderboards."""
        return self.client.get("/social/leaderboards", {
            "board_type": board_type,
            "game_type": game_type,
            "clan_id": clan_id
        })

    def report_target(
        self,
        target_type: str,
        target_id: str,
        reason: str,
        details: str = ""
    ) -> Tuple[bool, int, Any]:
        """Submit a moderation report for a player, clan, or chat message."""
        return self.client.post("/social/report", {
            "target_type": target_type,
            "target_id": target_id.strip(),
            "reason": reason,
            "details": details
        })
