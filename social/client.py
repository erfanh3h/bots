"""
Social API Client for Cafe Fekr Bots.

Handles REST communication with http://127.0.0.1:5001 with bearer authentication,
proper header construction, JSON payload serialization, and robust error handling.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple


class SocialApiClient:
    """Authenticated HTTP client dedicated to Cafe Fekr Social APIs."""

    def __init__(self, token: str, base_url: str = "http://127.0.0.1:5001", timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def set_token(self, token: str) -> None:
        """Update active JWT authorization token."""
        self.token = token

    def _get_headers(self, is_json: bool = True) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "CafeFekrSocialBot/1.0",
        }
        if is_json:
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
        return headers

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, int, Any]:
        """Performs HTTP GET request. Returns (ok: bool, status_code: int, data: Any)."""
        ep = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = f"{self.base_url}{ep}"
        if params:
            clean_params = {k: v for k, v in params.items() if v is not None}
            if clean_params:
                url += "?" + urllib.parse.urlencode(clean_params)

        req = urllib.request.Request(url, headers=self._get_headers(is_json=True), method="GET")
        return self._send_request(req)

    def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        form_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, int, Any]:
        """Performs HTTP POST request. Supports both JSON and Form encoding."""
        ep = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = f"{self.base_url}{ep}"

        if form_data is not None:
            data_bytes = urllib.parse.urlencode(form_data).encode("utf-8")
            headers = self._get_headers(is_json=False)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            payload = json_data or {}
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers = self._get_headers(is_json=True)

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        return self._send_request(req)

    def delete(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, int, Any]:
        """Performs HTTP DELETE request."""
        ep = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = f"{self.base_url}{ep}"
        payload = json_data or {}
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
        headers = self._get_headers(is_json=True)
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="DELETE")
        return self._send_request(req)

    def _send_request(self, req: urllib.request.Request) -> Tuple[bool, int, Any]:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = {"raw": raw}
                return True, status, parsed
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw)
            except Exception:
                parsed = {"detail": raw or str(e)}
            return False, e.code, parsed
        except urllib.error.URLError as e:
            return False, 0, {"detail": f"Connection error: {e.reason}"}
        except Exception as e:
            return False, -1, {"detail": f"Unexpected error: {str(e)}"}
