"""
Game Session Controller for Cafe Fekr Bots.

Manages connection to the Socket.IO /game namespace during an active match.
Delegates move calculations to the attached BaseGameLogic and paces turns
using the HumanBehavior simulator.
"""

import asyncio
from typing import Callable, Optional
import socketio

if __package__ is None or __package__ == "":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from bots.config import SERVER_WS_URL, BOT_PHONE, BOT_USER_ID
    from bots.behavior.human_behavior import HumanBehavior
    from bots.games.base_game import BaseGameLogic
else:
    from ..config import SERVER_WS_URL, BOT_PHONE, BOT_USER_ID
    from ..behavior.human_behavior import HumanBehavior
    from ..games.base_game import BaseGameLogic


class GameSession:
    def __init__(
        self,
        game_id: str,
        token: str,
        game_logic: BaseGameLogic,
        behavior: Optional[HumanBehavior] = None,
        my_user_id: str = BOT_USER_ID,
        on_finished_callback: Optional[Callable[[int], None]] = None,
    ):
        self.game_id = game_id
        self.token = token
        self.game_logic = game_logic
        self.behavior = behavior or HumanBehavior()
        self.my_user_id = my_user_id
        self.on_finished_callback = on_finished_callback

        self.sio: Optional[socketio.AsyncClient] = None
        self.is_active = False

    async def start(self):
        """Initializes and connects to the /game namespace."""
        self.is_active = True
        self.game_logic.on_game_start(self.game_id)

        self.sio = socketio.AsyncClient()
        self._setup_handlers()

        # Brief pause to allow backend instantiation of game session
        await asyncio.sleep(0.35)

        for attempt in range(1, 4):
            try:
                print(f"[GameSession] Connecting to /game (Attempt {attempt}/3) [Game ID: {self.game_id}]...")
                await self.sio.connect(
                    SERVER_WS_URL,
                    namespaces=["/game"],
                    auth={"token": self.token, "game_id": self.game_id},
                )
                break
            except Exception as e:
                print(f"[GameSession] Connection attempt {attempt} failed: {e}")
                await asyncio.sleep(0.5)

    def _setup_handlers(self):
        @self.sio.on("connect", namespace="/game")
        async def on_connect():
            print(f"[GameSession] Connected to /game namespace for Match ID: {self.game_id}")

        @self.sio.on("disconnect", namespace="/game")
        async def on_disconnect():
            print("[GameSession] Disconnected from /game namespace.")
            self.is_active = False

        @self.sio.on("command", namespace="/game")
        async def on_command(data):
            await self._handle_command(data)

    async def emit(self, event: str, data: dict):
        """Emits an event to /game namespace safely once acknowledged."""
        for _ in range(60):
            if self.sio and "/game" in self.sio.namespaces:
                break
            await asyncio.sleep(0.05)

        try:
            if self.sio and "/game" in self.sio.namespaces:
                await self.sio.emit(event, data, namespace="/game")
        except Exception as e:
            print(f"[GameSession] Emit error: {e}")

    async def _handle_command(self, data: dict):
        cmd_id = data.get("id")
        payload = data.get("data")

        if cmd_id in ("GamePlayData", "GamePlayTime", "GamePlayNavigate", "WaitTime"):
            # Pre-game intro / transition commands before the active GameSession starts
            return

        elif cmd_id == "GameData":
            # Extract player role (1 or 2). Note: Do NOT send SaveBoard here because the server
            # is still running the 5s Start_Game_Time timer before emitting StartGame.
            if isinstance(payload, dict) and "gamers" in payload:
                for gamer in payload["gamers"]:
                    p_uid = gamer.get("user_id") if isinstance(gamer, dict) else ""
                    if p_uid == self.my_user_id or BOT_PHONE in str(gamer):
                        role = gamer.get("gamer_id", 2)
                        self.game_logic.set_player_role(role)
                        print(f"[GameSession] Confirmed Player Role: Player {role}")
                        break
            self.game_logic.handle_server_command(cmd_id, payload)

        elif cmd_id == "UserData":
            if isinstance(payload, list):
                for idx, player in enumerate(payload):
                    p_uid = player.get("user_id") if isinstance(player, dict) else ""
                    if p_uid == self.my_user_id or BOT_PHONE in str(player):
                        self.game_logic.set_player_role(idx + 1)
                        print(f"[GameSession] Assigned Role: Player {idx + 1}")
            elif isinstance(payload, dict):
                role = payload.get("user", 2)
                self.game_logic.set_player_role(role)
                print(f"[GameSession] Assigned Role: Player {role}")

        elif cmd_id == "StartGame":
            # Phase 1 (or match start) has officially started on the server!
            self.game_logic.handle_server_command(cmd_id, payload)
            if hasattr(self.game_logic, "should_send_initial_board") and self.game_logic.should_send_initial_board():
                init_move = self.game_logic.get_initial_board_move()
                print(f"[{self.game_logic.game_type} Bot] Sending initial board setup: {init_move}")
                await self.behavior.simulate_thinking(level=self.game_logic.level, is_critical=False, legal_moves_count=1)
                await self.emit("user_command", init_move)

        elif cmd_id == "ReconnectData":
            self.game_logic.handle_server_command(cmd_id, payload)
            if hasattr(self.game_logic, "should_send_initial_board") and self.game_logic.should_send_initial_board():
                init_move = self.game_logic.get_initial_board_move()
                print(f"[{self.game_logic.game_type} Bot] Sending initial board setup on reconnect: {init_move}")
                await self.behavior.simulate_thinking(level=self.game_logic.level, is_critical=False, legal_moves_count=1)
                await self.emit("user_command", init_move)
            elif hasattr(self.game_logic, "should_act_on_reconnect") and self.game_logic.should_act_on_reconnect():
                await self._take_turn()

        elif cmd_id == "CurrentTurn":
            my_role = self.game_logic.my_player_num or 2
            if isinstance(payload, dict) and ("current_round" in payload or "current_turn" in payload or "dices" in payload):
                # Simultaneous round-based turn (e.g. FekrBekr, Yatzy)
                self.game_logic.handle_server_command(cmd_id, payload)
                rnd = payload.get("current_round", payload.get("current_turn", 1))
                print(f"\n[GameSession] Simultaneous Turn (Round {rnd}) [My Role: Player {my_role}]")
                await self._take_turn()
            else:
                turn = payload
                print(f"\n[GameSession] Current Turn: Player {turn} (My Role: Player {my_role})")
                if turn == my_role:
                    await self._take_turn()
                else:
                    print(f"[{self.game_logic.game_type} Bot] Opponent's turn. Waiting...")

        elif cmd_id == "RollResult":
            self.game_logic.handle_server_command(cmd_id, payload)
            if hasattr(self.game_logic, "format_state"):
                print(self.game_logic.format_state())
            await self._take_turn()

        elif cmd_id == "PeaceSelected":
            self.game_logic.handle_server_command(cmd_id, payload)
            if hasattr(self.game_logic, "format_state"):
                print(self.game_logic.format_state())

        elif cmd_id == "FinishRound":
            winner = payload.get("Winner", 0) if isinstance(payload, dict) else payload
            print(f"\n>>> [GameSession] Round Finished! Winner: Player {winner} <<<\n")
            self.game_logic.on_round_finished(winner)

        elif cmd_id == "NewRound":
            rnd = payload
            print(f"[GameSession] Round {rnd} Started!")
            self.game_logic.on_new_round(rnd)

        elif cmd_id == "UserDisconnected":
            u_id = payload.get("user_id", "") if isinstance(payload, dict) else payload
            print(f"[GameSession] User {u_id} disconnected. Match is paused on server.")

        elif cmd_id == "UserReconnected":
            u_id = payload.get("user_id", "") if isinstance(payload, dict) else payload
            print(f"[GameSession] User {u_id} reconnected. Match resumed.")

        elif cmd_id in ("FinishGame", "GameFinished"):
            winner = payload.get("Winner", 0) if isinstance(payload, dict) else payload
            print("\n" + "=" * 55)
            print(f" [GameSession] Match Concluded! Final Winner: Player {winner}")
            print("=" * 55 + "\n")
            self.is_active = False
            self.game_logic.on_game_finished(winner)
            await self.disconnect()
            if self.on_finished_callback:
                self.on_finished_callback(winner)

        else:
            # Dispatch any game-specific event to logic handler
            self.game_logic.handle_server_command(cmd_id, payload)

    async def _take_turn(self):
        """Simulates human thinking time and computes & emits the next move."""
        if not self.sio or not self.sio.connected:
            return

        legal_moves = self.game_logic.get_legal_moves()
        if not legal_moves:
            return

        is_critical = self.game_logic.is_critical_turn()

        # Human-like delay simulation
        await self.behavior.simulate_thinking(
            level=self.game_logic.level,
            is_critical=is_critical,
            legal_moves_count=len(legal_moves),
            bot_label=f"{self.game_logic.game_type} Bot (Lvl {self.game_logic.level})",
        )

        # Decide move using pure game logic
        move = self.game_logic.compute_next_move()
        if move is None:
            return

        # Prepare and emit command
        cmd_dict = self.game_logic.build_move_command(move)
        cmd_id = cmd_dict.get("id", "user_command")
        cmd_data = cmd_dict.get("data", move)

        print(f"[{self.game_logic.game_type} Bot] Playing move -> {move} (Command: {cmd_id})")
        await self.emit("user_command", {"id": cmd_id, "data": cmd_data})

    async def disconnect(self):
        """Disconnects socket client."""
        if self.sio and self.sio.connected:
            try:
                await self.sio.disconnect()
            except Exception:
                pass
        self.is_active = False
