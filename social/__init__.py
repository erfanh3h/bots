"""
Cafe Fekr Social Bots Module.

Exports:
- SocialBot: Full autonomous player bot for social actions.
- RealUserManager: Real user discovery and authentic JWT token issuer.
- SocialApiClient: Authenticated REST client.
- Action submodules: FriendsActions, ClanActions, MessagingActions, NotificationActions, InvitationActions.
"""

from .auth_helper import RealUserManager, REAL_USER_PROFILES
from .client import SocialApiClient
from .friends_actions import FriendsActions
from .clan_actions import ClanActions
from .messaging_actions import MessagingActions
from .notification_actions import NotificationActions
from .invitation_actions import InvitationActions
from .social_bot import SocialBot

__all__ = [
    "SocialBot",
    "RealUserManager",
    "REAL_USER_PROFILES",
    "SocialApiClient",
    "FriendsActions",
    "ClanActions",
    "MessagingActions",
    "NotificationActions",
    "InvitationActions",
]
