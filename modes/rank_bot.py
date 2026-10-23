"""
Ranked Queue Matchmaking Driver for Cafe Fekr Bots.

Handles connection to the /queue namespace, auto-accepts matches, dynamically resolves
the game logic for ANY game chosen by the server/matchmaker, and launches a GameSession.

By default, any instantiated bot sets level = 1 (easiest / beginner).
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


class RankBot:
    """
    Bot driver dedicated to the /queue (Ranked) matchmaking system.
    Capable of playing any game by resolving game logic dynamically on match start.
    Default level is 1 across all bots.
    """

    def __init__(
        self,
        default_game_type: str = "TicTacToe",
        level: int = 1,  # Default level must always be 1
        token: Optional[str] = None,
        auto_exit_after_match: bool = True,
    ):
        self.default_game_type = default_game_type
        self.level = level  # By default set to 1
        self.token = token or get_auth_token()
        self.my_user_id = BOT_USER_ID
        self.auto_exit_after_match = auto_exit_after_match

        self.queue_sio = socketio.AsyncClient()
        self.behavior = HumanBehavior()
        self.active_session: Optional[GameSession] = None
        self.active_game_logic: Optional[BaseGameLogic] = None

        self._setup_queue_handlers()

    def _setup_queue_handlers(self):
        @self.queue_sio.on("connect", namespace="/queue")
        async def on_queue_connect():
            print(f"[RankBot] Connected to /queue namespace. Waiting for matchmaking...")

        @self.queue_sio.on("disconnect", namespace="/queue")
        async def on_queue_disconnect():
            print("[RankBot] Disconnected from /queue namespace.")

        @self.queue_sio.on("command", namespace="/queue")
        async def on_queue_command(data):
            await self._handle_queue_command(data)

    async def _handle_queue_command(self, data: dict):
        cmd_id = data.get("id")
        payload = data.get("data", {})

        print(f"[RankBot] Queue command received: {cmd_id}")

        if cmd_id == "StartPreGame":
            # Match found! Send Accept command
            pre_game_id = payload.get("id")
            print(f"[RankBot] Pre-game match proposal: {pre_game_id}. Sending Accept...")
            await asyncio.sleep(self.behavior.calculate_thinking_delay(level=self.level, legal_moves_count=1))
            await self.emit_queue("user_command", {
                "id": "Accept",
                "user_id": self.my_user_id,
                "pre_game_id": pre_game_id,
            })

        elif cmd_id == "StartGame":
            game_id = payload.get("game_id")
            # Extract game type selected by rank matchmaker, or fallback to default
            game_type = payload.get("game_type", self.default_game_type)
            print("\n" + "=" * 55)
            print(f" [RankBot] Ranked Match Started! ID: {game_id} | Game: {game_type}")
            print(f" [RankBot] Difficulty Level: {self.level} (Default: 1)")
            print("=" * 55)
            await self._launch_game(game_id, game_type)

        elif cmd_id == "GameCanceled":
            print("[RankBot] Match proposal was canceled or declined.")

    async def _launch_game(self, game_id: str, game_type: str):
        # Dynamically instantiate game logic for ANY game mode
        self.active_game_logic = get_game_logic(game_type, level=self.level)

        def on_game_finished(winner: int):
            self.active_game_logic = None
            if self.auto_exit_after_match:
                print(f"[RankBot] Match concluded! Exiting process.")
                asyncio.create_task(self._shutdown_and_exit())

        self.active_session = GameSession(
            game_id=game_id,
            token=self.token,
            game_logic=self.active_game_logic,
            behavior=self.behavior,
            my_user_id=self.my_user_id,
            on_finished_callback=on_game_finished,
        )
        await self.active_session.start()

    async def emit_queue(self, event: str, data: dict):
        for _ in range(60):
            if self.queue_sio and "/queue" in self.queue_sio.namespaces:
                break
            await asyncio.sleep(0.05)

        try:
            if self.queue_sio and "/queue" in self.queue_sio.namespaces:
                await self.queue_sio.emit(event, data, namespace="/queue")
        except Exception as e:
            print(f"[RankBot] Emit queue error: {e}")

    async def _shutdown_and_exit(self):
        await asyncio.sleep(0.5)
        if self.queue_sio and self.queue_sio.connected:
            await self.queue_sio.disconnect()
        sys.exit(0)

    async def run(self):
        print("=" * 60)
        print(f"  ☕ Cafe Fekr - Rank Bot (Plays All Games)")
        print(f"  Mode: Ranked Queue | Difficulty Level: {self.level} (Default: 1)")
        print(f"  Phone: {BOT_PHONE} | User ID: {self.my_user_id}")
        print("=" * 60)

        print(f"\n[RankBot] Connecting to /queue namespace...")
        await self.queue_sio.connect(
            SERVER_WS_URL,
            namespaces=["/queue"],
            auth={"token": self.token, "pre_game_id": None},
        )
        print("[RankBot] Ready! Waiting for ranked matchmaking opponents...\n")

        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[RankBot] Shutting down...")
            if self.queue_sio and self.queue_sio.connected:
                await self.queue_sio.disconnect()
            if self.active_session:
                await self.active_session.disconnect()


if __name__ == "__main__":
    game_arg = sys.argv[1] if len(sys.argv) > 1 else "TicTacToe"
    bot = RankBot(default_game_type=game_arg, level=1)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print(f"\n[RankBot] Exited.")
