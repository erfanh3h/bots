"""
Multiplayer Rank Queue Matchmaking Driver for Cafe Fekr Bots (/multi-queue).

Handles the 4-Player Multiplayer Rank mode for Ludo and Risk Strike:
1. Connects to /multi-queue namespace with auth={"token": token, "game_type": game_type}.
2. Waits until 4 players join the queue and StartGame is emitted.
3. Disconnects from /multi-queue and transitions smoothly to /game namespace to play the 4-player match.
"""

import argparse
import asyncio
import base64
import json
import os
import sys
from typing import Optional
import socketio

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

if __package__ is None or __package__ == "":
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


def decode_token_payload(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            return json.loads(base64.urlsafe_b64decode(padded.encode()).decode("utf-8"))
    except Exception:
        pass
    return {}


class MultiRankBot:
    """
    Autonomous bot driver for 4-player Multiplayer Rank (/multi-queue) matchmaking.
    Supports Ludo and Risk Strike.
    """

    def __init__(
        self,
        game_type: str = "Ludo",
        token: Optional[str] = None,
        level: int = 2,
        auto_exit_after_match: bool = True,
    ):
        raw_gt = str(game_type).strip().lower()
        if raw_gt == "risk":
            self.game_type = "Risk"
        elif raw_gt == "uno":
            self.game_type = "Uno"
        else:
            self.game_type = "Ludo"
        self.level = level
        self.auto_exit_after_match = auto_exit_after_match

        self.token = token or os.environ.get("BOT_TOKEN") or get_auth_token()
        token_claims = decode_token_payload(self.token)

        self.my_user_id = str(token_claims.get("id", BOT_USER_ID))
        self.bot_phone = str(token_claims.get("phone", BOT_PHONE))
        self.bot_name = str(token_claims.get("username", "ربات رنک چندنفره"))

        self.queue_sio = socketio.AsyncClient()
        self.behavior = HumanBehavior()
        self.active_session: Optional[GameSession] = None
        self.active_game_logic: Optional[BaseGameLogic] = None
        self.is_running = False
        self._setup_queue_handlers()

    def _setup_queue_handlers(self):
        @self.queue_sio.on("connect", namespace="/multi-queue")
        async def on_queue_connect():
            print(f"[MultiRankBot:{self.bot_name}] Connected to /multi-queue ({self.game_type}). Waiting for 4 players...")

        @self.queue_sio.on("disconnect", namespace="/multi-queue")
        async def on_queue_disconnect():
            print(f"[MultiRankBot:{self.bot_name}] Disconnected from /multi-queue.")

        @self.queue_sio.on("command", namespace="/multi-queue")
        async def on_queue_command(data):
            await self._handle_queue_command(data)

    async def _handle_queue_command(self, data: dict):
        if not isinstance(data, dict):
            return
        cmd_id = data.get("id")
        payload = data.get("data", {})

        if cmd_id in ("Queue_Status", "QueueStatus"):
            cnt = payload.get("queuers_count", 1) if isinstance(payload, dict) else 1
            req = payload.get("required_count", 4) if isinstance(payload, dict) else 4
            print(f"[MultiRankBot:{self.bot_name}] Queue Status ({self.game_type}): {cnt}/{req} players")

        elif cmd_id in ("Start_Game", "StartGame"):
            game_id = payload.get("game_id") if isinstance(payload, dict) else str(payload)
            matched_type = payload.get("game_type", self.game_type) if isinstance(payload, dict) else self.game_type
            print(f"\n[MultiRankBot:{self.bot_name}] 4 Players Ready! Launching {matched_type} Match ID: {game_id}")
            try:
                await self.queue_sio.disconnect()
            except Exception:
                pass
            await self._launch_game(game_id, matched_type)

    async def _launch_game(self, game_id: str, game_type: str):
        self.active_game_logic = get_game_logic(game_type, level=self.level)

        def on_game_finished(winner: int):
            self.active_game_logic = None
            self.is_running = False
            print(f"[MultiRankBot:{self.bot_name}] 4-Player Match finished!")
            if self.auto_exit_after_match:
                asyncio.create_task(self._shutdown_and_exit())

        self.active_session = GameSession(
            game_id=game_id,
            token=self.token,
            game_logic=self.active_game_logic,
            behavior=self.behavior,
            my_user_id=self.my_user_id,
            on_finished_callback=on_game_finished,
        )
        self.active_session.bot_phone = self.bot_phone
        self.active_session.level = self.level
        await self.active_session.start()

    async def _shutdown_and_exit(self):
        await asyncio.sleep(0.5)
        if self.queue_sio and self.queue_sio.connected:
            await self.queue_sio.disconnect()
        if self.active_session:
            await self.active_session.disconnect()
        sys.exit(0)

    async def run(self):
        print("=" * 65)
        print(f"  ☕ Cafe Fekr - 4-Player Multiplayer Rank Bot ({self.game_type})")
        print(f"  Name: {self.bot_name} | User ID: {self.my_user_id} | Phone: {self.bot_phone}")
        print(f"  Difficulty Level: {self.level}")
        print("=" * 65)

        await self.queue_sio.connect(
            SERVER_WS_URL,
            namespaces=["/multi-queue"],
            auth={"token": self.token, "game_type": self.game_type},
        )

        self.is_running = True
        try:
            while self.is_running:
                await asyncio.sleep(0.5)
        except (KeyboardInterrupt, asyncio.CancelledError):
            if self.queue_sio and self.queue_sio.connected:
                await self.queue_sio.disconnect()
            if self.active_session:
                await self.active_session.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Cafe Fekr 4-Player Multiplayer Rank Bot")
    parser.add_argument("game_type", nargs="?", default="Ludo", help="Game type: Ludo or Risk")
    parser.add_argument("--token", "-t", default="", help="JWT Token")
    parser.add_argument("--level", "-l", type=int, default=2, help="Difficulty level (default: 2)")
    args = parser.parse_args()

    token = args.token or os.environ.get("BOT_TOKEN")
    bot = MultiRankBot(game_type=args.game_type, token=token, level=args.level)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n[MultiRankBot] Exited by user.")


if __name__ == "__main__":
    main()
