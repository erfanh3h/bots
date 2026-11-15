"""
Clan and Guild Operations for Cafe Fekr Social Bots.
"""

from typing import Any, Dict, Optional, Tuple
from .client import SocialApiClient


class ClanActions:
    """Encapsulates all clan-related social actions."""

    def __init__(self, client: SocialApiClient):
        self.client = client

    def create_clan(
        self,
        name: str,
        tag: str,
        emblem_id: int = 1,
        description: str = "",
        join_type: str = "open"
    ) -> Tuple[bool, int, Any]:
        """Create a new clan/guild."""
        return self.client.post("/clans/create", {
            "name": name.strip(),
            "tag": tag.strip().upper(),
            "emblem_id": int(emblem_id),
            "description": description.strip(),
            "join_type": join_type
        })

    def search_clans(
        self,
        query: str = "",
        join_type: str = "",
        sort_by: str = "clan_score"
    ) -> Tuple[bool, int, Any]:
        """Search clans directory or fetch leaderboards."""
        return self.client.get("/clans/search", {
            "q": query,
            "join_type": join_type,
            "sort_by": sort_by
        })

    def get_my_clan(self) -> Tuple[bool, int, Any]:
        """Retrieve viewer's current clan overview, members list, and invitations."""
        return self.client.get("/clans/my")

    def get_details(self, clan_id: str) -> Tuple[bool, int, Any]:
        """Fetch detailed public profile and member roster for a specific clan."""
        return self.client.get(f"/clans/{clan_id.strip()}")

    def join_or_request(self, clan_id: str, message: str = "") -> Tuple[bool, int, Any]:
        """Directly join an open clan, or submit a join request for approval."""
        return self.client.post("/clans/join", {
            "clan_id": clan_id.strip(),
            "message": message
        })

    def respond_join_request(self, request_id: str, action: str = "accept") -> Tuple[bool, int, Any]:
        """Accept or decline an incoming clan join request (requires elder/leader permissions)."""
        return self.client.post("/clans/requests/respond", {
            "request_id": request_id.strip(),
            "action": action
        })

    def invite_to_clan(self, target_user_id: str) -> Tuple[bool, int, Any]:
        """Invite a player to join current clan."""
        return self.client.post("/clans/invite", {
            "target_user_id": target_user_id.strip()
        })

    def get_invitations(self) -> Tuple[bool, int, Any]:
        """Retrieve list of clan invitations sent to the viewer."""
        return self.client.get("/clans/invitations")

    def respond_invitation(self, invite_id: str, action: str = "accept") -> Tuple[bool, int, Any]:
        """Accept or decline an invitation to join a clan."""
        return self.client.post("/clans/invitations/respond", {
            "invite_id": invite_id.strip(),
            "action": action
        })

    def get_chat(self, clan_id: str = "", skip: int = 0, limit: int = 50) -> Tuple[bool, int, Any]:
        """Fetch clan chat history messages."""
        return self.client.get("/messages/clan", {
            "clan_id": clan_id,
            "skip": skip,
            "limit": limit
        })

    def send_chat(self, text: str, clan_id: str = "") -> Tuple[bool, int, Any]:
        """Post a message into clan chat feed."""
        return self.client.post("/messages/clan/send", {
            "text": text,
            "clan_id": clan_id
        })

    def delete_chat_message(self, message_id: str) -> Tuple[bool, int, Any]:
        """Delete a message from clan chat (sender or clan leader)."""
        return self.client.post("/messages/clan/delete", {
            "message_id": message_id.strip()
        })

    def create_friendly_challenge(
        self,
        game_type: str = "Monopoly",
        player_count: int = 2
    ) -> Tuple[bool, int, Any]:
        """Create an in-clan friendly challenge match announcement."""
        return self.client.post("/clans/friendly-challenge", {
            "game_type": game_type,
            "player_count": player_count
        })

    def join_friendly_challenge(self, challenge_id: str) -> Tuple[bool, int, Any]:
        """Join an active clan friendly challenge."""
        return self.client.post("/clans/friendly-challenge/join", {
            "challenge_id": challenge_id.strip()
        })

    def close_friendly_challenge(self, challenge_id: str) -> Tuple[bool, int, Any]:
        """Cancel or close a clan friendly challenge."""
        return self.client.post("/clans/friendly-challenge/close", {
            "challenge_id": challenge_id.strip()
        })

    def change_member_role(self, target_user_id: str, new_role: str) -> Tuple[bool, int, Any]:
        """Promote or demote a member ('member', 'elder', 'co_leader')."""
        return self.client.post("/clans/role", {
            "target_user_id": target_user_id.strip(),
            "new_role": new_role.strip()
        })

    def transfer_leadership(self, new_leader_id: str) -> Tuple[bool, int, Any]:
        """Transfer clan ownership and leadership to another member."""
        return self.client.post("/clans/transfer-leadership", {
            "new_leader_id": new_leader_id.strip()
        })

    def kick_member(self, target_user_id: str) -> Tuple[bool, int, Any]:
        """Kick a member from the clan."""
        return self.client.post("/clans/kick", {
            "target_user_id": target_user_id.strip()
        })

    def update_settings(
        self,
        description: Optional[str] = None,
        join_type: Optional[str] = None,
        required_score: Optional[int] = None
    ) -> Tuple[bool, int, Any]:
        """Update clan configuration, policy, and minimum score requirements."""
        payload = {}
        if description is not None:
            payload["description"] = description
        if join_type is not None:
            payload["join_type"] = join_type
        if required_score is not None:
            payload["required_score"] = int(required_score)
        return self.client.post("/clans/settings", payload)

    def leave_clan(self) -> Tuple[bool, int, Any]:
        """Voluntarily leave the clan (members and non-leaders)."""
        return self.client.post("/clans/leave", {})

    def disband_clan(self) -> Tuple[bool, int, Any]:
        """Permanently dissolve and disband the clan (leader only)."""
        return self.client.post("/clans/disband", {})
