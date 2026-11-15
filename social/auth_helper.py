"""
Authentication and Real User Manager for Cafe Fekr Social Bots.

Ensures social bot actions are executed using genuine user accounts (not flagged as bots),
either discovered dynamically from MongoDB or selected from verified real test user profiles.
Generates valid JWT tokens using the server's master secret key.
"""

import datetime
import os
import sys
from typing import Dict, List, Optional
from jose import jwt

# Fallback import for configuration
try:
    from bots.config import SERVER_REST_URL
except ImportError:
    SERVER_REST_URL = "http://127.0.0.1:5001"

# Master Secret Key & Algorithm used by kafehfekrserver/Entities/Security
SECRET_KEY = "09da5e74afaa9ma2565c818195b7b9563b93xc059f6f0f4cab6cf63b88e8d3e7"
ALGORITHM = "HS256"

# Known bot phones that server flags as is_bot - strictly excluded for real social actions
BOT_EXCLUSION_PHONES = {
    "09131234567",
    "9131234567",
    "09000000000",
    "09999999999",
}

# Verified Real Player Profiles (actual registered users in Cafe Fekr DB)
REAL_USER_PROFILES = [
    {
        "_id": "1YBZaK",
        "phone": "9141234567",
        "username": "akbari",
        "device_id": "TE1A.220922.025",
        "display_name": "علی اکبری (akbari)"
    },
    {
        "_id": "NHD6bL",
        "phone": "9121234567",
        "username": "Niliii22",
        "device_id": "device_test_123",
        "display_name": "نیلوفر (Niliii22)"
    },
    {
        "_id": "hGSOlz",
        "phone": "9107747079",
        "username": "Taghi2",
        "device_id": "device_1793731168.23166_2459",
        "display_name": "تقی ۲ (Taghi2)"
    },
    {
        "_id": "kFIrrF",
        "phone": "9111111111",
        "username": "Mahdi",
        "device_id": "TE1A.220922.025",
        "display_name": "مهدی (Mahdi)"
    },
    {
        "_id": "8stEJY",
        "phone": "9129876543",
        "username": "bahram",
        "device_id": "TP1A.220624.014",
        "display_name": "بهرام (bahram)"
    },
    {
        "_id": "8y6lDk",
        "phone": "9173121414",
        "username": "naghis",
        "device_id": "{52A273A2-240D-459C-BCF4-52B079E88CDB}",
        "display_name": "نقی (naghis)"
    },
    {
        "_id": "Lz2bHF",
        "phone": "9399999999",
        "username": "molla",
        "device_id": "TP1A.220624.014",
        "display_name": "ملا (molla)"
    },
    {
        "_id": "E7AxwY",
        "phone": "9372222222",
        "username": "Erder",
        "device_id": "TE1A.220922.025",
        "display_name": "اردر (Erder)"
    },
    {
        "_id": "kVjl1s",
        "phone": "9387804649",
        "username": "Eliza",
        "device_id": "TE1A.220922.025",
        "display_name": "الیزا (Eliza)"
    },
    {
        "_id": "hjOwbf",
        "phone": "9121111111",
        "username": "Taghi",
        "device_id": "TE1A.220922.025",
        "display_name": "تقی (Taghi)"
    },
]


class RealUserManager:
    """Manages discovery and JWT token generation for authentic human players."""

    _cached_users: List[Dict] = []
    _cached_tokens: Dict[str, str] = {}

    @classmethod
    def load_users(cls, force_db_refresh: bool = False) -> List[Dict]:
        """Loads real users from MongoDB if available, falling back to verified static catalog."""
        if cls._cached_users and not force_db_refresh:
            return cls._cached_users

        users: List[Dict] = []
        try:
            import pymongo
            mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
            client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
            db = client["KafehFekrDB"]
            db_users = list(db["users"].find(
                {"_id": {"$ne": "3goBRU"}},
                {"_id": 1, "username": 1, "phone": 1, "device_id": 1, "is_bot": 1}
            ).limit(40))

            for u in db_users:
                phone = str(u.get("phone", "")).strip()
                dev = str(u.get("device_id", "")).strip()
                if (
                    phone in BOT_EXCLUSION_PHONES
                    or dev.startswith("bot_")
                    or u.get("is_bot") is True
                    or not u.get("username")
                ):
                    continue
                users.append({
                    "_id": str(u["_id"]),
                    "phone": phone,
                    "username": str(u.get("username", "")),
                    "device_id": dev or "real_device_client",
                    "display_name": f"{u.get('username')} ({phone})"
                })
        except Exception as e:
            # Fall back to pre-verified catalog if DB is unreachable
            pass

        if not users:
            users = list(REAL_USER_PROFILES)

        cls._cached_users = users
        return users

    @classmethod
    def get_user_by_username(cls, username: str) -> Optional[Dict]:
        """Find user by username (case-insensitive)."""
        uname_lower = username.strip().lower()
        for u in cls.load_users():
            if u.get("username", "").lower() == uname_lower:
                return u
        return None

    @classmethod
    def get_user_by_id(cls, user_id: str) -> Optional[Dict]:
        """Find user by unique ID."""
        uid = str(user_id).strip()
        for u in cls.load_users():
            if str(u.get("_id", "")) == uid:
                return u
        return None

    @classmethod
    def get_token(cls, user_spec: str | Dict, force_new: bool = False) -> str:
        """
        Generates or retrieves a valid signed JWT access token for a given user.
        Accepts username, user_id, or user dict.
        """
        user_dict = None
        if isinstance(user_spec, dict):
            user_dict = user_spec
        elif isinstance(user_spec, str):
            user_dict = cls.get_user_by_username(user_spec) or cls.get_user_by_id(user_spec)

        if not user_dict:
            # Default to primary real user: akbari
            user_dict = REAL_USER_PROFILES[0]

        uid = str(user_dict.get("_id", "1YBZaK"))
        if not force_new and uid in cls._cached_tokens:
            return cls._cached_tokens[uid]

        phone = str(user_dict.get("phone", "9141234567"))
        device_id = str(user_dict.get("device_id", "TE1A.220922.025"))

        # Sign JWT token identical to server auth
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(weeks=52)
        payload = {
            "phone": phone,
            "id": uid,
            "device_id": device_id,
            "exp": expire
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        cls._cached_tokens[uid] = token
        return token

    @classmethod
    def get_test_pair(cls) -> tuple[Dict, Dict]:
        """Returns two distinct real users for peer-to-peer social flow testing."""
        users = cls.load_users()
        if len(users) >= 2:
            return users[0], users[1]
        return REAL_USER_PROFILES[0], REAL_USER_PROFILES[1]
