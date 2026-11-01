"""
Ranked Queue Matchmaking Driver for Cafe Fekr Bots.

Handles the Main Rank competitive mode:
1. Connects to /queue namespace using provided or authenticated token.
2. Auto-accepts match proposals (AcceptGame) with natural human thinking delay.
3. Competes in the 7-turn Pick & Ban pre-game phase like a real human player:
   - System Bans (3 games removed)
   - Strategic bans (counter-games) and picks (favorite high-confidence games)
   - Real human thinking delay (2.0 - 3.8s)
4. Transitions smoothly to /game namespace on StartGame:
   - Plays all games in the best-of-3 series at difficulty LEVEL = 2.
   - Handles multi-game series transitions on GamePlayData / GamePlayNavigate.
   - Concludes match cleanly when series finishes.
"""

import argparse
import asyncio
import base64
import json
import os
import sys
from typing import List, Optional
import socketio

# Ensure UTF-8 output on Windows console
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

# All supported two-player games for Main Rank
TWO_PLAYER_GAMES = [
    "TicTacToe",
    "RPC",
    "FekrBekr",
    "DotBox",
    "Checkers",
    "Othello",
    "FourInRow",
    "Mill",
    "Yatzy",
    "BackGammon",
    "Chess",
    "BattleShip",
    "Sudoku",
    "MSweeper",
    "Pentago",
    "BoxFour",
    "MNumbers",
    "Yinsh",
]


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


class RankBot:
    """
    Autonomous bot driver for Main Rank competitive matchmaking.
    Plays at Level 2 (Intermediate) across all games in the series.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        level: int = 2,  # Default level must always be 2 for Main Rank
        default_game_type: str = "Othello",
        auto_exit_after_match: bool = True,
    ):
        self.level = level
        self.default_game_type = default_game_type
        self.auto_exit_after_match = auto_exit_after_match

        # Resolve authentication token
        self.token = token or os.environ.get("BOT_TOKEN") or get_auth_token()
        token_claims = decode_token_payload(self.token)

        self.my_user_id = str(token_claims.get("id", BOT_USER_ID))
        self.bot_phone = str(token_claims.get("phone", BOT_PHONE))
        self.bot_name = str(token_claims.get("username", "ربات رنک"))

        self.queue_sio = socketio.AsyncClient()
        self.behavior = HumanBehavior()
        self.active_session: Optional[GameSession] = None
        self.active_game_logic: Optional[BaseGameLogic] = None

        # PreGame Pick & Ban state
        self.pre_game_id: Optional[str] = None
        self.my_pregame_index: int = 1  # 0 = Player 1, 1 = Player 2
        self.available_games: List[str] = list(TWO_PLAYER_GAMES)
        self.turn_history: List[tuple[int, str]] = []

        # Preferred games for picking (tactical 2-player games)
        self.preferred_pick_pool = [
            "Othello",
            "FourInRow",
            "Pentago",
            "Yatzy",
            "Checkers",
            "TicTacToe",
            "Mill",
            "DotBox",
        ]

        # Preferred games for banning (lengthy or puzzle games)
        self.preferred_ban_pool = [
            "BackGammon",
            "Chess",
            "BattleShip",
            "Sudoku",
            "MSweeper",
            "FekrBekr",
        ]

        self.is_running = False
        self._setup_queue_handlers()

    def _setup_queue_handlers(self):
        @self.queue_sio.on("connect", namespace="/queue")
        async def on_queue_connect():
            print(f"[RankBot:{self.bot_name}] Connected to /queue namespace. Waiting for matchmaking...")

        @self.queue_sio.on("disconnect", namespace="/queue")
        async def on_queue_disconnect():
            print(f"[RankBot:{self.bot_name}] Disconnected from /queue namespace.")

        @self.queue_sio.on("command", namespace="/queue")
        async def on_queue_command(data):
            await self._handle_queue_command(data)

    async def _handle_queue_command(self, data: dict):
        cmd_id = data.get("id")
        payload = data.get("data", {})

        print(f"[RankBot:{self.bot_name}] Queue Command: {cmd_id}")

        if cmd_id == "AcceptGame":
            # Handle match acceptance
            delay = round(self.behavior.calculate_thinking_delay(level=self.level, legal_moves_count=1) + 0.3, 2)
            print(f"[RankBot:{self.bot_name}] Match Found! Sending Accept in {delay}s...")
            await asyncio.sleep(delay)
            await self.emit_queue("user_command", {
                "id": "Accept",
                "user_id": self.my_user_id,
            })
            print(f"[RankBot:{self.bot_name}] Match Accepted sent.")

        elif cmd_id == "StartPreGame":
            if isinstance(payload, dict):
                self.pre_game_id = payload.get("id")
                queuers = payload.get("queuers", [])
                if queuers and queuers[0].get("user_id") == self.my_user_id:
                    self.my_pregame_index = 0
                else:
                    self.my_pregame_index = 1
                self.available_games = list(TWO_PLAYER_GAMES)
                self.turn_history.clear()
                print(f"[RankBot:{self.bot_name}] PreGame Started: {self.pre_game_id} | Position: Player {self.my_pregame_index + 1}")

        elif cmd_id == "SystemBannedGames":
            bans = payload if isinstance(payload, list) else []
            for b in bans:
                if b in self.available_games:
                    self.available_games.remove(b)
            print(f"[RankBot:{self.bot_name}] System Banned 3 games: {bans}. Remaining: {len(self.available_games)} games.")

        elif cmd_id == "SelectedGame":
            if isinstance(payload, dict):
                idx = payload.get("active_index", 0)
                g_type = payload.get("game_type", "")
                if g_type in self.available_games:
                    self.available_games.remove(g_type)
                self.turn_history.append((idx, g_type))
                action = "PICK" if idx in (3, 4, 7) else "BAN"
                print(f"[RankBot:{self.bot_name}] Turn {idx} ({action}) Result: {g_type}")

        elif cmd_id == "SelectGame":
            active_uid = str(payload)
            if active_uid == self.my_user_id and self.pre_game_id:
                # Bot turn to Pick or Ban!
                await self._handle_pick_ban_turn()

        elif cmd_id == "StartGame":
            game_id = payload.get("game_id") if isinstance(payload, dict) else str(payload)
            print(f"\n[RankBot:{self.bot_name}] PreGame Complete! Launching Ranked Match ID: {game_id}")
            # Disconnect from /queue cleanly before entering /game
            try:
                await self.queue_sio.disconnect()
            except Exception:
                pass
            await self._launch_game(game_id)

        elif cmd_id == "GameCanceled":
            print(f"[RankBot:{self.bot_name}] Queue match was cancelled. Resetting...")
            self.pre_game_id = None
            self.available_games = list(TWO_PLAYER_GAMES)
            self.turn_history.clear()

        elif cmd_id == "UserDisconnected":
            u_id = payload.get("user_id", "") if isinstance(payload, dict) else str(payload)
            print(f"[RankBot:{self.bot_name}] Opponent ({u_id}) disconnected during Pick & Ban. Draft paused.")

        elif cmd_id == "UserReconnected":
            u_id = payload.get("user_id", "") if isinstance(payload, dict) else str(payload)
            print(f"[RankBot:{self.bot_name}] Opponent ({u_id}) reconnected! Pick & Ban resumed.")

    async def _handle_pick_ban_turn(self):
        """Simulates human decision-making for picking or banning a game."""
        current_turn = len(self.turn_history) + 1
        is_pick_turn = current_turn in (3, 4)
        action_name = "PICK" if is_pick_turn else "BAN"

        # Human-like thinking delay (2.0 - 3.5s)
        think_time = round(self.behavior.calculate_thinking_delay(level=self.level, legal_moves_count=len(self.available_games)) + 1.0, 2)
        print(f"[RankBot:{self.bot_name}] My Turn ({action_name} - Turn {current_turn})! Thinking for {think_time}s...")
        await asyncio.sleep(think_time)

        chosen = None
        if is_pick_turn:
            for g in self.preferred_pick_pool:
                if g in self.available_games:
                    chosen = g
                    break
        else:
            for g in self.preferred_ban_pool:
                if g in self.available_games:
                    chosen = g
                    break

        if not chosen and self.available_games:
            import random
            chosen = random.choice(self.available_games)

        if chosen:
            print(f"[RankBot:{self.bot_name}] Selected {action_name}: {chosen}")
            await self.emit_queue("user_command", {
                "pre_game_id": self.pre_game_id,
                "id": "SelectGame",
                "game_type": chosen,
            })

    async def _launch_game(self, game_id: str):
        """Instantiates GameSession on /game to play the best-of-3 match at Level 2."""
        # Initial placeholder game logic; will be updated by GamePlayData / GamePlayNavigate
        first_game = self.default_game_type
        self.active_game_logic = get_game_logic(first_game, level=self.level)

        def on_game_finished(winner: int):
            self.active_game_logic = None
            self.is_running = False
            print(f"[RankBot:{self.bot_name}] Series finished! Match concluded.")
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

    async def emit_queue(self, event: str, data: dict):
        for _ in range(60):
            if self.queue_sio and "/queue" in self.queue_sio.namespaces:
                break
            await asyncio.sleep(0.05)

        try:
            if self.queue_sio and "/queue" in self.queue_sio.namespaces:
                await self.queue_sio.emit(event, data, namespace="/queue")
        except Exception as e:
            print(f"[RankBot:{self.bot_name}] Emit queue error: {e}")

    async def _shutdown_and_exit(self):
        await asyncio.sleep(0.5)
        if self.queue_sio and self.queue_sio.connected:
            await self.queue_sio.disconnect()
        if self.active_session:
            await self.active_session.disconnect()
        sys.exit(0)

    async def run(self):
        print("=" * 65)
        print(f"  ☕ Cafe Fekr - Main Rank Bot")
        print(f"  Name: {self.bot_name} | User ID: {self.my_user_id} | Phone: {self.bot_phone}")
        print(f"  Difficulty Level: {self.level} (Fixed for Main Rank)")
        print(f"  Pick & Ban: Enabled (7-Turn Series Matchmaking)")
        print(f"  Token: {self.token[:20]}...")
        print("=" * 65)

        print(f"\n[RankBot:{self.bot_name}] Connecting to /queue namespace...")
        await self.queue_sio.connect(
            SERVER_WS_URL,
            namespaces=["/queue"],
            auth={"token": self.token, "pre_game_id": None},
        )
        print(f"[RankBot:{self.bot_name}] Ready! Waiting in matchmaking queue for an opponent...\n")

        self.is_running = True
        try:
            while self.is_running:
                await asyncio.sleep(0.5)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print(f"\n[RankBot:{self.bot_name}] Shutting down...")
            if self.queue_sio and self.queue_sio.connected:
                await self.queue_sio.disconnect()
            if self.active_session:
                await self.active_session.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Cafe Fekr Main Rank Bot")
    parser.add_argument("token_pos", nargs="?", default="", help="JWT Token (positional)")
    parser.add_argument("--token", "-t", default="", help="JWT Token (flag)")
    parser.add_argument("--level", "-l", type=int, default=2, help="Difficulty level (default: 2)")
    args = parser.parse_args()

    token = args.token or args.token_pos or os.environ.get("BOT_TOKEN")
    if not token:
        # Prompt interactively if run in terminal without arguments
        try:
            entered = input("Enter Bot JWT Token (or press Enter to auto-authenticate): ").strip()
            if entered:
                token = entered
        except Exception:
            pass

    bot = RankBot(token=token, level=args.level)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print(f"\n[RankBot] Exited by user.")


if __name__ == "__main__":
    main()
