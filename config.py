"""
Common Configuration and Authentication for Cafe Fekr Bots.
"""

import json
import sys
import urllib.parse
import urllib.request

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

SERVER_REST_URL = "http://127.0.0.1:5001"
SERVER_WS_URL = "http://127.0.0.1:5000"

BOT_PHONE = "09131234567"
BOT_DEVICE_ID = "bot_device_9131234567"
BOT_USER_ID = "3goBRU"

# Fallback token for test user 09131234567
_cached_token = ""


def get_auth_token(force_refresh: bool = False) -> str:
    """Retrieve verified fresh JWT token from REST API endpoint /code."""
    global _cached_token
    if _cached_token and not force_refresh:
        return _cached_token

    try:
        url = f"{SERVER_REST_URL}/code"
        data = urllib.parse.urlencode({
            "phone": BOT_PHONE,
            "code": "1234",
            "device_id": BOT_DEVICE_ID
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode())
            token = res_data.get("token", "")
            if token:
                _cached_token = token
                print(f"[Auth] Successfully authenticated 09131234567 (Token: {token[:16]}...)")
                return token
    except Exception as e:
        print(f"[Auth] Warning: Could not authenticate via REST API ({e}).")

    if _cached_token:
        return _cached_token

    # Default fallback JWT signed for bot_device_9131234567
    fallback_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJwaG9uZSI6IjA5MTMxMjM0NTY3IiwiaWQiOiIzZ29CUlUiLCJkZXZpY2VfaWQiOiJib3RfZGV2aWNlXzkxMzEyMzQ1NjciLCJleHAiOjE4MjM5MTQ0MjJ9."
        "bHRAT3TcW2efRPCT76Y8Gh64CRk5Bzb7PGE1TXUW-pI"
    )
    _cached_token = fallback_token
    return fallback_token
