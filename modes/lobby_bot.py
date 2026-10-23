"""
Lobby Matchmaking Driver for Cafe Fekr Bots.

Handles connection to the /lobby namespace, discovers rooms matching the bot's
target game, auto-joins, auto-readies, and launches a GameSession upon match start.

Per requirements:
- Lobby bots are strictly Level 1 (easiest / beginner).
"""

import asyncio
import sys
from typing import Optional
import socketio

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
    Strictly plays at Level 1 (easiest / casual beginner human).
    """

    def __init__(
        self,
        game_logic_or_type: BaseGameLogic | str,
        token: Optional[str] = None,
        auto_exit_after_match: bool = True,
    ):
        # Enforce Level 1 for all lobby bots
        if isinstance(game_logic_or_type, str):
            self.game_logic: BaseGameLogic = get_game_logic(game_logic_or_type, level=1)
        else:
            self.game_logic: BaseGameLogic = game_logic_or_type
            self.game_logic.level = 1  # Strictly Level 1 for lobby bots

        self.token = token or get_auth_token()
        self.my_user_id = BOT_USER_ID
        self.auto_exit_after_match = auto_exit_after_match

        self.active_lobby_id: Optional[str] = None
        self.active_game_id: Optional[str] = None
        self.is_ready: bool = False

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

        elif cmd_id == "LobbyPlayerReady":
            ready_uid = payload.get("user_id")
            print(f"[Lobby] Player {ready_uid} marked as READY.")

        elif cmd_id == "LobbyPlayersUpdate":
            queuers = payload.get("queuers", [])
            print(f"[Lobby] Room update: {len(queuers)} player(s) present.")

        elif cmd_id == "StartGame":
            self.active_game_id = payload.get("game_id")
            print("\n" + "=" * 55)
            print(f" [Lobby] Match Started by Host! Game ID: {self.active_game_id}")
            print(f" [Lobby] Bot Playing Level: {self.game_logic.level} (Beginner / Casual Human)")
            print("=" * 55)
            await self._start_game_session(self.active_game_id)

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

        queuers_count = lobby.get("queuers_length", len(lobby.get("queuers", [])))
        max_count = lobby.get("lobby_count", 2)
        room_game_type = str(lobby.get("game_type", ""))

        if self.game_logic.matches_game_type(room_game_type) and queuers_count < max_count:
            room_title = lobby.get("lobby_name", lobby_id)
            print(f"[{self.game_logic.game_type} LobbyBot] Found matching room '{room_title}' (ID: {lobby_id}). Joining...")
            self.active_lobby_id = lobby_id
            self.is_ready = False
            await self.emit_lobby(
                "user_command",
                {"id": "LobbyJoin", "data": {"lobby_id": lobby_id}},
            )

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
            if self.auto_exit_after_match:
                print(f"[{self.game_logic.game_type} LobbyBot] Match finished! Exiting bot process.")
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
            await self.lobby_sio.disconnect()
        sys.exit(0)

    async def run(self):
        print("=" * 60)
        print(f"  ☕ Cafe Fekr - Lobby Bot [{self.game_logic.game_type}]")
        print(f"  Mode: Lobby | Difficulty Level: {self.game_logic.level} (Beginner / Human)")
        print(f"  Phone: {BOT_PHONE} | User ID: {self.my_user_id}")
        print("=" * 60)

        print(f"\n[LobbyBot] Connecting to /lobby namespace...")
        await self.lobby_sio.connect(
            SERVER_WS_URL,
            namespaces=["/lobby"],
            auth={"token": self.token},
        )
        print(f"[LobbyBot] Connected! Listening for {self.game_logic.game_type} rooms...")
        print("[LobbyBot] -> Create a room in-game, and I will auto-join, ready up, and play!\n")

        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[LobbyBot] Shutting down...")
            if self.lobby_sio and self.lobby_sio.connected:
                await self.lobby_sio.disconnect()
            if self.active_session:
                await self.active_session.disconnect()


if __name__ == "__main__":
    game_arg = sys.argv[1] if len(sys.argv) > 1 else "TicTacToe"
    bot = LobbyBot(game_arg)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print(f"\n[{game_arg} LobbyBot] Exited.")
