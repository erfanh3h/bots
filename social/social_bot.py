"""
Unified Social Bot Orchestrator for Cafe Fekr.

Operates as an authentic player persona executing full social interaction suites:
friends, clan management, direct messaging, matchmaking invitations, notifications,
and moderation flows.
"""

import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .auth_helper import RealUserManager
from .client import SocialApiClient
from .friends_actions import FriendsActions
from .clan_actions import ClanActions
from .messaging_actions import MessagingActions
from .notification_actions import NotificationActions
from .invitation_actions import InvitationActions


class SocialBot:
    """
    Autonomous Social Agent representing a real player in the Cafe Fekr social ecosystem.
    """

    def __init__(
        self,
        user_spec: Optional[str | Dict] = None,
        base_url: str = "http://127.0.0.1:5001",
        timeout: float = 8.0
    ):
        # 1. Resolve authentic human user profile
        if isinstance(user_spec, dict):
            self.user = user_spec
        elif isinstance(user_spec, str):
            found = RealUserManager.get_user_by_username(user_spec) or RealUserManager.get_user_by_id(user_spec)
            self.user = found or RealUserManager.load_users()[0]
        else:
            self.user = RealUserManager.load_users()[0]

        self.user_id = str(self.user.get("_id", ""))
        self.username = str(self.user.get("username", "Player"))
        self.phone = str(self.user.get("phone", ""))

        # 2. Authenticate with real token
        self.token = RealUserManager.get_token(self.user)
        self.client = SocialApiClient(token=self.token, base_url=base_url, timeout=timeout)

        # 3. Mount modular action sub-systems
        self.friends = FriendsActions(self.client)
        self.clans = ClanActions(self.client)
        self.messages = MessagingActions(self.client)
        self.notifications = NotificationActions(self.client)
        self.invitations = InvitationActions(self.client)

    def __repr__(self) -> str:
        return f"<SocialBot user='{self.username}' id='{self.user_id}' phone='{self.phone}'>"

    # =========================================================================
    # High-level Automated Testing and Flow Verification
    # =========================================================================

    def run_full_diagnostic(self, peer_user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Executes a diagnostic run across all social categories and reports result matrix.
        """
        results: List[Dict[str, Any]] = []

        def log_step(category: str, action: str, ok: bool, status: int, detail: Any):
            results.append({
                "category": category,
                "action": action,
                "ok": ok,
                "status": status,
                "detail": detail
            })

        print(f"\n=======================================================")
        print(f"  [SocialBot Diagnostic] Running as {self.username} ({self.user_id})")
        print(f"=======================================================\n")

        # --- 1. Overview & Profiles ---
        print("[1/5] Testing Social Overview & Profiles...")
        ok, st, d = self.invitations.get_overview()
        log_step("Overview", "get_overview", ok, st, d)

        ok, st, d = self.invitations.get_public_profile(self.user_id)
        log_step("Profile", "get_self_public_profile", ok, st, d)

        ok, st, d = self.invitations.customize_profile(profile_title="بازیکن فعال باشگاه", status_message="تست بات اجتماعی")
        log_step("Profile", "customize_profile", ok, st, d)

        # --- 2. Friends System ---
        print("[2/5] Testing Friends System...")
        ok, st, d = self.friends.list_friends()
        log_step("Friends", "list_friends", ok, st, d)

        ok, st, d = self.friends.list_requests()
        log_step("Friends", "list_requests", ok, st, d)

        ok, st, d = self.friends.get_discover()
        log_step("Friends", "get_discover", ok, st, d)

        ok, st, d = self.friends.search_players("a", limit=5)
        log_step("Friends", "search_players", ok, st, d)

        ok, st, d = self.friends.get_blocked()
        log_step("Friends", "get_blocked", ok, st, d)

        if peer_user_id:
            ok, st, d = self.friends.send_request(peer_user_id, "سلام! بازی دوستانه؟")
            log_step("Friends", f"send_request_to_{peer_user_id}", ok, st, d)

        # --- 3. Clans System ---
        print("[3/5] Testing Clans System...")
        ok, st, d = self.clans.get_my_clan()
        log_step("Clans", "get_my_clan", ok, st, d)

        ok, st, d = self.clans.search_clans("", sort_by="clan_score")
        log_step("Clans", "search_clans", ok, st, d)

        ok, st, d = self.clans.get_invitations()
        log_step("Clans", "get_clan_invitations", ok, st, d)

        ok, st, d = self.clans.get_chat(skip=0, limit=10)
        log_step("Clans", "get_clan_chat", ok, st, d)

        # --- 4. Messaging & DMs ---
        print("[4/5] Testing Messaging & DMs...")
        ok, st, d = self.messages.list_conversations()
        log_step("Messages", "list_conversations", ok, st, d)

        if peer_user_id:
            ok, st, d = self.messages.send_dm(peer_user_id, "سلام، این پیام تست خودکار است.")
            log_step("Messages", f"send_dm_to_{peer_user_id}", ok, st, d)

            ok, st, d = self.messages.get_messages(peer_user_id, limit=5)
            log_step("Messages", f"get_messages_{peer_user_id}", ok, st, d)

            ok, st, d = self.messages.mark_read(peer_user_id)
            log_step("Messages", f"mark_read_{peer_user_id}", ok, st, d)

        # --- 5. Notifications & Invitations ---
        print("[5/5] Testing Notifications & Game Invites...")
        ok, st, d = self.notifications.list_notifications(unread_only=False)
        log_step("Notifications", "list_notifications", ok, st, d)

        ok, st, d = self.notifications.mark_all_read()
        log_step("Notifications", "mark_all_read", ok, st, d)

        ok, st, d = self.invitations.list_game_invites()
        log_step("Invitations", "list_game_invites", ok, st, d)

        ok, st, d = self.invitations.get_leaderboards("global_score")
        log_step("Leaderboards", "get_global_leaderboard", ok, st, d)

        if peer_user_id:
            ok, st, d = self.invitations.send_game_invite(peer_user_id, game_type="Monopoly", invite_mode="direct_match")
            log_step("Invitations", f"send_game_invite_to_{peer_user_id}", ok, st, d)

        print("\nDiagnostic complete! Evaluated %d actions.\n" % len(results))
        return results
