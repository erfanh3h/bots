"""
Watcher / Spectator Bot Driver for Cafe Fekr.

Connects to the Socket.IO /social namespace and streams live match events
for games being played on the server (Bot vs Bot, Human vs Bot, or Human vs Human).
Receives sanitized public board states, moves, player profiles, and spectator counts.
"""

import asyncio
import base64
import json
import os
import sys
from typing import Callable, Dict, List, Optional, Any
import socketio

def decode_token_payload(token: str) -> dict:
    """Extracts payload claims from JWT token without requiring the secret key."""
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            return json.loads(base64.urlsafe_b64decode(padded.encode()).decode("utf-8"))
    except Exception:
        pass
    return {}

if __package__ is None or __package__ == "":
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from bots.config import (
        SERVER_WS_URL,
        BOT_PHONE,
        BOT_USER_ID,
        get_auth_token,
    )
else:
    from ..config import (
        SERVER_WS_URL,
        BOT_PHONE,
        BOT_USER_ID,
        get_auth_token,
    )


class WatcherBot:
    """
    Bot driver dedicated to spectating live games via /social namespace.
    """

    def __init__(
        self,
        target_game_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
        token: Optional[str] = None,
        auto_leave_on_end: bool = True,
    ):
        self.target_game_id: Optional[str] = str(target_game_id) if target_game_id else None
        self.target_user_id: Optional[str] = str(target_user_id) if target_user_id else None
        self.auto_leave_on_end = auto_leave_on_end

        self.token = token or os.environ.get("BOT_TOKEN") or get_auth_token()
        token_claims = decode_token_payload(self.token)
        self.my_user_id = str(token_claims.get("id", BOT_USER_ID))
        self.bot_phone = str(token_claims.get("phone", BOT_PHONE))
        self.bot_name = str(token_claims.get("username", "ربات تماشاگر"))

        self.is_running = False
        self.status = "idle"  # idle, connecting, watching, finished, rejected, stopped, error
        self.active_game_id: Optional[str] = self.target_game_id
        self.game_type: str = "Unknown"
        self.spectator_count: int = 0
        self.participants: List[Dict[str, Any]] = []
        self.initial_state: Dict[str, Any] = {}
        self.last_state: Dict[str, Any] = {}
        self.last_event: Optional[Dict[str, Any]] = None
        self.moves_count: int = 0
        self.event_history: List[Dict[str, Any]] = []
        self.rejection_reason: Optional[str] = None
        self.winner: Optional[Any] = None

        self.on_exit_callback: Optional[Callable] = None
        self.on_event_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        self.sio: Optional[socketio.AsyncClient] = None
        self._loop_task: Optional[asyncio.Task] = None

    def _setup_handlers(self):
        @self.sio.on("connect", namespace="/social")
        async def on_connect():
            print(f"[WatcherBot] Connected to /social as '{self.bot_name}' ({self.my_user_id}).")
            await asyncio.sleep(0.3)
            await self.send_spectate_request()

        @self.sio.on("disconnect", namespace="/social")
        async def on_disconnect():
            print(f"[WatcherBot] Disconnected from /social namespace.")
            if self.status == "watching":
                self.status = "disconnected"

        @self.sio.on("command", namespace="/social")
        async def on_command(data):
            await self._handle_social_command(data)

    async def _handle_social_command(self, data: dict):
        cmd_id = data.get("id")
        payload = data.get("data", {})

        if cmd_id == "Logout":
            print(f"[WatcherBot] Token rejected on /social.")
            self.status = "error"
            self.rejection_reason = "token_rejected"

        elif cmd_id in ("SpectateAccepted", "SocialSpectateJoin"):
            self.status = "watching"
            self.active_game_id = str(payload.get("game_id", self.target_game_id or ""))
            self.game_type = str(payload.get("game_type", "Unknown"))
            self.spectator_count = int(payload.get("spectator_count", 1))
            self.participants = payload.get("participants", [])
            self.initial_state = payload.get("state", {})
            self.last_state = self.initial_state

            player_names = [p.get("username", "بازیکن") for p in self.participants] if self.participants else ["بازیکنان مسابقه"]
            print(f"\n{'='*60}")
            print(f" [WatcherBot] 👁️ Spectate ACCEPTED for Match '{self.active_game_id}'")
            print(f" [WatcherBot] Game Type: {self.game_type} | Watchers: {self.spectator_count}")
            print(f" [WatcherBot] Participants: {' vs '.join(player_names)}")
            print(f"{'='*60}\n")

        elif cmd_id == "SpectateRejected":
            self.rejection_reason = str(payload.get("reason", "unknown"))
            msg = payload.get("message", self.rejection_reason)

            # If the match is still in countdown / subgame initialization, retry gracefully!
            if self.rejection_reason in ("session_unavailable", "match_not_found") and getattr(self, "_retry_count", 0) < 6:
                self._retry_count = getattr(self, "_retry_count", 0) + 1
                print(f"[WatcherBot] Match is initializing ({self.rejection_reason}). Retrying in 1.5s (attempt {self._retry_count}/6)...")
                await asyncio.sleep(1.5)
                await self.send_spectate_request()
                return

            self.status = "rejected"
            print(f"[WatcherBot] ❌ Spectate REJECTED for '{payload.get('game_id')}': {msg}")
            if self.on_exit_callback:
                try:
                    res = self.on_exit_callback()
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception:
                    pass

        elif cmd_id == "SpectatorGameState":
            self.moves_count += 1
            self.last_event = payload
            self.event_history.append({
                "index": self.moves_count,
                "event": payload.get("id", "GameEvent"),
                "data": payload.get("data", {}),
            })
            if len(self.event_history) > 100:
                self.event_history.pop(0)

            event_id = payload.get("id", "GameEvent")
            event_data = payload.get("data", {})
            summary = str(event_data)[:90] + ("..." if len(str(event_data)) > 90 else "")
            print(f"[WatcherBot] 👁️ [Move #{self.moves_count}] {event_id} in '{self.active_game_id}': {summary}")

            if self.on_event_callback:
                try:
                    res = self.on_event_callback(payload)
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception:
                    pass

        elif cmd_id == "SpectatorCountUpdated":
            self.spectator_count = int(payload.get("count", self.spectator_count))
            print(f"[WatcherBot] Spectator count updated: {self.spectator_count} viewer(s)")

        elif cmd_id == "SpectatorGameEnded":
            self.status = "finished"
            self.winner = payload.get("winner", None)
            reason = payload.get("reason", "ended")
            print(f"\n{'='*60}")
            print(f" [WatcherBot] 🏁 Match '{self.active_game_id}' Finished!")
            print(f" [WatcherBot] Winner: Player {self.winner} (Reason: {reason})")
            print(f"{'='*60}\n")

            if self.on_exit_callback:
                try:
                    res = self.on_exit_callback()
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception:
                    pass

            if self.auto_leave_on_end:
                asyncio.create_task(self.stop())

    async def send_spectate_request(self, game_id: Optional[str] = None, user_id: Optional[str] = None):
        """Sends the RequestSpectate command to /social."""
        gid = game_id or self.target_game_id
        uid = user_id or self.target_user_id
        payload = {}
        if gid:
            payload["game_id"] = str(gid)
        if uid:
            payload["target_user_id"] = str(uid)
            payload["player_id"] = str(uid)

        self.status = "connecting"
        print(f"[WatcherBot] Requesting spectate: {payload}...")
        await self.emit_social("user_command", {
            "id": "RequestSpectate",
            "data": payload,
        })

    async def emit_social(self, event: str, data: dict):
        """Emits an event to /social safely."""
        for _ in range(60):
            if self.sio and "/social" in self.sio.namespaces:
                break
            await asyncio.sleep(0.05)

        try:
            if self.sio and "/social" in self.sio.namespaces:
                await self.sio.emit(event, data, namespace="/social")
            else:
                print(f"[WatcherBot] Error: /social is not connected.")
        except Exception as e:
            print(f"[WatcherBot] Emit social error: {e}")

    async def run(self):
        """Main lifecycle runner connecting to the server and maintaining spectator session."""
        self.is_running = True
        self.status = "connecting"
        self.sio = socketio.AsyncClient()
        self._setup_handlers()

        # Connect with retry loop
        connected = False
        for attempt in range(1, 4):
            if not self.is_running:
                break
            try:
                print(f"[WatcherBot] Connecting to /social (Attempt {attempt}/3)...")
                await self.sio.connect(
                    SERVER_WS_URL,
                    namespaces=["/social"],
                    auth={"token": self.token},
                )
                connected = True
                break
            except Exception as e:
                print(f"[WatcherBot] Connection attempt {attempt} failed: {e}")
                if attempt < 3:
                    await asyncio.sleep(2.0)

        if not connected:
            self.status = "error"
            self.rejection_reason = "cannot_connect_backend"
            print(f"[WatcherBot] Could not connect to {SERVER_WS_URL} on /social.")
            return

        # Keep alive while spectating
        while self.is_running:
            if self.status in ("finished", "rejected", "stopped"):
                break
            await asyncio.sleep(0.5)

    async def stop(self):
        """Cleanly leaves spectate room and disconnects."""
        self.is_running = False
        if self.active_game_id and self.sio and self.sio.connected:
            try:
                await self.sio.emit(
                    "user_command",
                    {"id": "LeaveSpectate", "data": {"game_id": self.active_game_id}},
                    namespace="/social",
                )
                await asyncio.sleep(0.2)
            except Exception:
                pass

        if self.sio:
            try:
                await self.sio.disconnect()
            except Exception:
                pass

        if self.status not in ("finished", "rejected"):
            self.status = "stopped"
        print(f"[WatcherBot] Stopped watching.")

    def get_state(self) -> Dict[str, Any]:
        """Returns snapshot of current spectator bot state."""
        return {
            "status": self.status,
            "target_game_id": self.target_game_id,
            "active_game_id": self.active_game_id,
            "game_type": self.game_type,
            "spectator_count": self.spectator_count,
            "participants": self.participants,
            "moves_count": self.moves_count,
            "winner": self.winner,
            "rejection_reason": self.rejection_reason,
            "recent_events": self.event_history[-10:],
        }
