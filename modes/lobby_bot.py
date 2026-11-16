"""
Lobby Matchmaking Driver for Cafe Fekr Bots.

Handles connection to the /lobby namespace, discovers rooms matching the bot's
target game, auto-joins, auto-readies, and launches a GameSession upon match start.

Per requirements:
- Lobby bots are strictly Level 1 (easiest / beginner).
"""

import asyncio
import base64
import json
import os
import sys
from typing import Callable, List, Optional
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
    from bots.behavior.human_behavior import HumanBehavior
    from bots.games.base_game import BaseGameLogic
    from bots.games import get_game_logic
    from bots.modes.game_session import GameSession
else:
    from ..config import (
        SERVER_WS_URL,
        BOT_PHONE,
        BOT_USER_ID,
        get_auth_token,
    )
    from ..behavior.human_behavior import HumanBehavior
    from ..games.base_game import BaseGameLogic
    from ..games import get_game_logic
    from .game_session import GameSession


class LobbyBot:
    """
    Bot driver dedicated to the /lobby matchmaking system.
    Plays at the configured Level (default 1 for casual, or 2/3 for Bot vs Bot challenges).
    """

    def __init__(
        self,
        game_logic_or_type: BaseGameLogic | str,
        token: Optional[str] = None,
        auto_exit_after_match: bool = True,
        level: int = 1,
        auto_start_when_full: bool = False,
    ):
        self.level = max(1, min(3, level))
        if isinstance(game_logic_or_type, str):
            self.game_logic: BaseGameLogic = get_game_logic(game_logic_or_type, level=self.level)
        else:
            self.game_logic: BaseGameLogic = game_logic_or_type
            self.game_logic.level = self.level

        self.token = token or os.environ.get("BOT_TOKEN") or get_auth_token()
        token_claims = decode_token_payload(self.token)
        self.my_user_id = str(token_claims.get("id", BOT_USER_ID))
        self.bot_phone = str(token_claims.get("phone", BOT_PHONE))
        self.bot_name = str(token_claims.get("username", f"ربات {self.game_logic.game_type}"))
        self.auto_exit_after_match = auto_exit_after_match
        self.auto_start_when_full = auto_start_when_full

        self.target_lobby_id: Optional[str] = None
        self.on_exit_callback: Optional[Callable] = None
        self.is_running = False
        self.is_host = False
        self._start_sent = False
        self.active_lobby_id: Optional[str] = None
        self.active_game_id: Optional[str] = None
        self.is_ready: bool = False
        self.latest_lobbies: List[dict] = []

        self.behavior = HumanBehavior()
        self.lobby_sio = socketio.AsyncClient()
        self.active_session: Optional[GameSession] = None

        self._setup_lobby_handlers()

    def _setup_lobby_handlers(self):
        @self.lobby_sio.on("connect", namespace="/lobby")
        async def on_lobby_connect():
            print(f"[{self.game_logic.game_type} LobbyBot] Connected to /lobby namespace.")
            await asyncio.sleep(0.2)
            await self.emit_lobby("user_command", {"id": "LobbyRequestData", "data": {}})

        @self.lobby_sio.on("disconnect", namespace="/lobby")
        async def on_lobby_disconnect():
            print(f"[{self.game_logic.game_type} LobbyBot] Disconnected from /lobby.")

        @self.lobby_sio.on("command", namespace="/lobby")
        async def on_lobby_command(data):
            await self._handle_lobby_command(data)

    async def _handle_lobby_command(self, data: dict):
        cmd_id = data.get("id")
        payload = data.get("data", {})

        if cmd_id == "Logout":
            print(f"[{self.game_logic.game_type} LobbyBot] Token rejected. Fetching fresh token...")
            self.token = get_auth_token(force_refresh=True)

        elif cmd_id == "LobbyList":
            lobbies = payload if isinstance(payload, list) else []
            self.latest_lobbies = lobbies
            print(f"[Lobby] Received active lobbies list ({len(lobbies)} rooms).")
            for lobby in lobbies:
                await self.try_join_lobby(lobby)

        elif cmd_id == "LobbyCreated":
            lobby_name = payload.get("lobby_name", "Unknown")
            lobby_id = payload.get("lobby_id", "")
            print(f"[Lobby] New room discovered: '{lobby_name}' (ID: {lobby_id})")
            await self.try_join_lobby(payload)

        elif cmd_id == "LobbyData":
            self.active_lobby_id = payload.get("lobby_id")
            creator_id = payload.get("creator_id")
            queuers_length = payload.get("queuers_length", len(payload.get("queuers", [])))
            max_count = int(payload.get("lobby_count", 2) or 2)

            if creator_id == self.my_user_id:
                self.is_host = True
                print(f"[Lobby] Bot is HOST of room: {self.active_lobby_id} ({queuers_length}/{max_count} players).")
                if self.auto_start_when_full and queuers_length >= max_count:
                    print(f"[Lobby] Room is full! Host auto-starting game in 0.8s...")
                    asyncio.create_task(self._delayed_host_start_game())
            else:
                if not self.is_ready:
                    self.is_ready = True
                    print(f"[Lobby] Inside room: {self.active_lobby_id}. Automatically sending Player Ready...")
                    await asyncio.sleep(0.3)
                    await self.emit_lobby("user_command", {"id": "LobbyPlayerReady", "data": {}})
                    print("[Lobby] Status: AUTO-READY! Waiting for host to click Start Match...")

        elif cmd_id in ["LobbyDeleted", "LobbyKick", "LobbyFull", "LobbyNotExists"]:
            print(f"[Lobby] Left room or room unavailable ({cmd_id}).")
            self.active_lobby_id = None
            self.is_ready = False
            self.is_host = False
            self._start_sent = False

        elif cmd_id == "LobbyPlayerReady":
            ready_uid = payload.get("user_id")
            print(f"[Lobby] Player {ready_uid} marked as READY.")

        elif cmd_id == "LobbyPlayersUpdate":
            queuers = payload.get("queuers", [])
            count = payload.get("count", len(queuers))
            max_count = int(payload.get("lobby_count", 2) or 2)
            print(f"[Lobby] Room update: {count}/{max_count} player(s) present.")
            if self.is_host and self.auto_start_when_full and count >= max_count:
                print(f"[Lobby] Capacity reached ({count}/{max_count})! Host auto-starting game...")
                asyncio.create_task(self._delayed_host_start_game())

        elif cmd_id == "StartGame":
            self.active_game_id = payload.get("game_id")
            print("\n" + "=" * 55)
            print(f" [Lobby] Match Started! Game ID: {self.active_game_id}")
            print(f" [Lobby] Bot Playing Level: {self.game_logic.level}")
            print("=" * 55)
            await self._start_game_session(self.active_game_id)

    async def _delayed_host_start_game(self):
        if self._start_sent:
            return
        self._start_sent = True
        await asyncio.sleep(0.8)
        print(f"[{self.game_logic.game_type} LobbyBot] Emitting LobbyStartGame command...")
        await self.emit_lobby("user_command", {"id": "LobbyStartGame", "data": {}})

    async def try_join_lobby(self, lobby: dict):
        if self.active_lobby_id:
            return  # Already joined a room

        lobby_id = lobby.get("lobby_id")
        if not lobby_id:
            return

        # Do not join rooms created by this bot user
        creator_id = lobby.get("creator_id")
        if creator_id == self.my_user_id:
            return

        # If a specific target lobby was requested, join only that
        if self.target_lobby_id and lobby_id != self.target_lobby_id:
            return

        queuers_count = lobby.get("queuers_length", len(lobby.get("queuers", [])))
        max_count = lobby.get("lobby_count", 2)
        room_game_type = str(lobby.get("game_type", ""))

        if self.target_lobby_id == lobby_id or (self.game_logic.matches_game_type(room_game_type) and queuers_count < max_count):
            room_title = lobby.get("lobby_name", lobby_id)
            print(f"[{self.game_logic.game_type} LobbyBot] Found matching room '{room_title}' (ID: {lobby_id}). Joining...")
            self.active_lobby_id = lobby_id
            self.is_ready = False
            await self.emit_lobby(
                "user_command",
                {"id": "LobbyJoin", "data": {"lobby_id": lobby_id}},
            )

    async def join_specific_lobby(self, lobby_id: str, password: str = ""):
        """Directly joins a specific room ID."""
        self.target_lobby_id = lobby_id
        self.active_lobby_id = lobby_id
        self.is_ready = False
        print(f"[{self.game_logic.game_type} LobbyBot] Explicitly joining room '{lobby_id}'...")
        payload = {"lobby_id": lobby_id}
        if password:
            payload["password"] = password
        await self.emit_lobby("user_command", {"id": "LobbyJoin", "data": payload})

    async def create_lobby_room(self, lobby_name: str, game_type: Optional[str] = None, count: int = 2, password: str = ""):
        """Instructs the bot to create a new lobby room."""
        gtype = game_type or self.game_logic.game_type
        print(f"[{self.game_logic.game_type} LobbyBot] Creating lobby room '{lobby_name}' ({gtype})...")
        await self.emit_lobby("user_command", {
            "id": "LobbyCreate",
            "data": {
                "lobby_name": lobby_name,
                "game_type": gtype,
                "lobby_count": max(2, min(4, count)),
                "lobby_password": password
            }
        })

    async def emit_lobby(self, event: str, data: dict):
        for _ in range(60):
            if self.lobby_sio and "/lobby" in self.lobby_sio.namespaces:
                break
            await asyncio.sleep(0.05)

        try:
            if self.lobby_sio and "/lobby" in self.lobby_sio.namespaces:
                await self.lobby_sio.emit(event, data, namespace="/lobby")
            else:
                print(f"[{self.game_logic.game_type} LobbyBot] Error: /lobby is not connected.")
        except Exception as e:
            print(f"[{self.game_logic.game_type} LobbyBot] Emit lobby error: {e}")

    async def _start_game_session(self, game_id: str):
        def on_game_finished(winner: int):
            self.active_lobby_id = None
            self.active_game_id = None
            self.is_ready = False
            print(f"[{self.game_logic.game_type} LobbyBot] Match finished! Final Winner: Player {winner}")
            if self.on_exit_callback:
                try:
                    res = self.on_exit_callback()
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception:
                    pass
            if self.auto_exit_after_match:
                print(f"[{self.game_logic.game_type} LobbyBot] Exiting bot process.")
                asyncio.create_task(self._shutdown_and_exit())

        self.active_session = GameSession(
            game_id=game_id,
            token=self.token,
            game_logic=self.game_logic,
            behavior=self.behavior,
            my_user_id=self.my_user_id,
            on_finished_callback=on_game_finished,
        )
        await self.active_session.start()

    async def _shutdown_and_exit(self):
        await asyncio.sleep(0.5)
        if self.lobby_sio and self.lobby_sio.connected:
            try:
                await self.lobby_sio.disconnect()
            except Exception:
                pass
        if self.active_session:
            try:
                await self.active_session.disconnect()
            except Exception:
                pass
        self.is_running = False
        if self.on_exit_callback:
            try:
                res = self.on_exit_callback()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        else:
            sys.exit(0)

    async def stop(self):
        """Cleanly stops the bot and disconnects all sockets."""
        self.is_running = False
        if self.active_session:
            try:
                await self.active_session.disconnect()
            except Exception:
                pass
        if self.lobby_sio and self.lobby_sio.connected:
            try:
                await self.lobby_sio.disconnect()
            except Exception:
                pass

    async def run(self):
        print("=" * 60)
        print(f"  ☕ Cafe Fekr - Lobby Bot [{self.game_logic.game_type}]")
        print(f"  Name: {self.bot_name} | User ID: {self.my_user_id} | Phone: {self.bot_phone}")
        print(f"  Mode: Lobby | Difficulty Level: {self.game_logic.level} (Beginner / Human)")
        print("=" * 60)

        self.is_running = True
        connected = False
        retry_count = 0
        max_retries = 3

        while self.is_running and not connected and retry_count < max_retries:
            try:
                retry_count += 1
                print(f"\n[LobbyBot] Connecting to /lobby namespace (Attempt {retry_count}/{max_retries})...")
                await self.lobby_sio.connect(
                    SERVER_WS_URL,
                    namespaces=["/lobby"],
                    auth={"token": self.token},
                )
                connected = True
            except Exception as e:
                print(f"[LobbyBot] Connection attempt {retry_count} failed: {e}")
                if retry_count < max_retries and self.is_running:
                    await asyncio.sleep(2.0)
                else:
                    self.is_running = False
                    raise

        if not connected:
            self.is_running = False
            return

        print(f"[LobbyBot] Connected! Listening for {self.game_logic.game_type} rooms...")
        print("[LobbyBot] -> Create a room in-game, and I will auto-join, ready up, and play!\n")
        try:
            while self.is_running:
                await asyncio.sleep(0.5)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[LobbyBot] Shutting down...")
            await self.stop()
        finally:
            self.is_running = False


if __name__ == "__main__":
    game_arg = sys.argv[1] if len(sys.argv) > 1 else "TicTacToe"
    bot = LobbyBot(game_arg)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print(f"\n[{game_arg} LobbyBot] Exited.")
