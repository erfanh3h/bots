"""
UNO (اونو) Game Logic for Cafe Fekr Bot (Supports 2, 3, and 4 Players).

Matches exact rules and socket protocol of kafehfekrbackend/Entities/Games/Uno:
- Supports 2, 3, or 4 players (gamer_id = 1..4).
- Cards have: {"uid": int, "color": "red"|"blue"|"green"|"yellow"|"wild", "value": "0".."9"|"skip"|"reverse"|"draw2"|"wild"|"wild_draw4"}.
- Commands:
  - PlayCard: {"id": "PlayCard", "data": {"card_uid": int, "chosen_color": str}}
  - DrawCard: {"id": "DrawCard", "data": {}}
  - PassTurn: {"id": "PassTurn", "data": {}}
"""

import random
from typing import Any, Dict, List, Optional
from .base_game import BaseGameLogic


UNO_COLORS = ("red", "blue", "green", "yellow")


class UnoGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Uno",
            game_type_aliases=["uno", "اونو", "uno_card"],
            level=level,
        )
        self.players_count: int = 2
        self.current_turn: int = 1
        self.direction: int = 1
        self.current_color: str = "red"
        self.current_value: str = "0"
        self.top_card: Dict[str, Any] = {"uid": 0, "color": "red", "value": "0"}
        self.my_hand: List[Dict[str, Any]] = []
        self.playable_uids: List[int] = []
        self.hands_count: List[int] = [7, 7, 7, 7]
        self.draw_pile_count: int = 80
        self.has_drawn_this_turn: bool = False
        self._needs_continuation_move: bool = False
        self.rank1: Optional[int] = None
        self.rank2: Optional[int] = None
        self.reset()

    def reset(self):
        self.current_turn = 1
        self.direction = 1
        self.current_color = "red"
        self.current_value = "0"
        self.top_card = {"uid": 0, "color": "red", "value": "0"}
        self.my_hand = []
        self.playable_uids = []
        self.hands_count = [7, 7, 7, 7]
        self.draw_pile_count = 80
        self.has_drawn_this_turn = False
        self._needs_continuation_move = False
        self.rank1 = None
        self.rank2 = None

    def is_card_playable(self, card: Dict[str, Any]) -> bool:
        if not isinstance(card, dict):
            return False
        col = str(card.get("color", ""))
        val = str(card.get("value", ""))
        if col == "wild" or val in ("wild", "wild_draw4"):
            return True
        if col == self.current_color or val == self.current_value:
            return True
        return False

    def _sync_from_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        if "players_count" in data:
            self.players_count = max(2, min(4, int(data["players_count"])))
        if "current_turn" in data:
            self.current_turn = int(data["current_turn"])
        elif "turn" in data:
            self.current_turn = int(data["turn"])
        if "direction" in data:
            self.direction = int(data["direction"])
        if "current_color" in data and data["current_color"]:
            self.current_color = str(data["current_color"])
        if "current_value" in data and data["current_value"] is not None:
            self.current_value = str(data["current_value"])
        if "top_card" in data and isinstance(data["top_card"], dict):
            self.top_card = dict(data["top_card"])
        if "hands_count" in data and isinstance(data["hands_count"], list):
            self.hands_count = [int(x) for x in data["hands_count"]]
            if len(self.hands_count) >= 2:
                self.players_count = len(self.hands_count)
        if "draw_pile_count" in data:
            self.draw_pile_count = int(data["draw_pile_count"])
        if "has_drawn_this_turn" in data:
            self.has_drawn_this_turn = bool(data["has_drawn_this_turn"])
        if "hand" in data and isinstance(data["hand"], list):
            self.my_hand = [dict(c) for c in data["hand"] if isinstance(c, dict)]
        if "playable_uids" in data and isinstance(data["playable_uids"], list):
            self.playable_uids = [int(u) for u in data["playable_uids"]]

    def should_continue_turn(self) -> bool:
        if self._needs_continuation_move:
            self._needs_continuation_move = False
            return True
        return False

    def should_act_on_reconnect(self) -> bool:
        my_role = self.my_player_num or 2
        if self.current_turn != my_role:
            return False
        return len(self.get_legal_moves()) > 0

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "GameData":
            self.reset()
            if isinstance(payload, dict):
                gamers = payload.get("gamers", [])
                if isinstance(gamers, list) and len(gamers) >= 2:
                    self.players_count = max(2, min(4, len(gamers)))
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict):
                    self._sync_from_dict(g_data)
            return True

        elif cmd_id == "UserData":
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
            return True

        elif cmd_id == "StartGame":
            self.is_game_active = True
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
            return True

        elif cmd_id == "CurrentTurn":
            self._needs_continuation_move = False
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
                self.has_drawn_this_turn = bool(payload.get("has_drawn_this_turn", False))
            else:
                self.current_turn = int(payload)
                self.has_drawn_this_turn = False
            return True

        elif cmd_id == "CardPlayed":
            self._needs_continuation_move = False
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
                if "next_turn" in payload:
                    self.current_turn = int(payload["next_turn"])
                self.has_drawn_this_turn = False
            return True

        elif cmd_id == "DrawResultPrivate":
            if isinstance(payload, dict):
                u_data = payload.get("user_data")
                if isinstance(u_data, dict):
                    self._sync_from_dict(u_data)
                else:
                    self._sync_from_dict(payload)
                my_role = self.my_player_num or 2
                turn_passed = bool(payload.get("turn_passed", False))
                if not turn_passed and self.current_turn == my_role:
                    self._needs_continuation_move = True
            return True

        elif cmd_id == "DrawResult":
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
                turn_passed = bool(payload.get("turn_passed", False))
                if "next_turn" in payload:
                    self.current_turn = int(payload["next_turn"])
                my_role = self.my_player_num or 2
                if not turn_passed and int(payload.get("gamer_id", 0)) == my_role:
                    self._needs_continuation_move = True
            return True

        elif cmd_id == "PassTurn":
            self._needs_continuation_move = False
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
                if "next_turn" in payload:
                    self.current_turn = int(payload["next_turn"])
                self.has_drawn_this_turn = False
            return True

        elif cmd_id == "WinHappened":
            if isinstance(payload, dict):
                if payload.get("rank1") is not None:
                    self.rank1 = int(payload["rank1"])
                if payload.get("rank2") is not None:
                    self.rank2 = int(payload["rank2"])
            return True

        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                gamers = payload.get("gamers", [])
                if isinstance(gamers, list) and len(gamers) >= 2:
                    self.players_count = max(2, min(4, len(gamers)))
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict):
                    self._sync_from_dict(g_data)
                u_data = payload.get("user_data", {})
                if isinstance(u_data, dict):
                    self._sync_from_dict(u_data)
            return True

        return False

    def _choose_best_wild_color(self) -> str:
        counts = {c: 0 for c in UNO_COLORS}
        for card in self.my_hand:
            col = str(card.get("color", ""))
            if col in counts:
                counts[col] += 1
        if self.level == 1 and random.random() < 0.30:
            return random.choice(UNO_COLORS)
        best_col = max(UNO_COLORS, key=lambda c: counts[c])
        if counts[best_col] == 0:
            return random.choice(UNO_COLORS)
        return best_col

    def get_legal_moves(self) -> List[Dict[str, Any]]:
        my_role = self.my_player_num or 2
        if self.current_turn != my_role:
            return []

        playable_cards = [c for c in self.my_hand if self.is_card_playable(c)]
        moves: List[Dict[str, Any]] = []
        best_color = self._choose_best_wild_color()

        for c in playable_cards:
            col = str(c.get("color", ""))
            val = str(c.get("value", ""))
            chosen = best_color if (col == "wild" or val in ("wild", "wild_draw4")) else col
            moves.append({
                "action": "play",
                "card_uid": int(c["uid"]),
                "card": c,
                "chosen_color": chosen,
            })

        if moves:
            return moves

        if not self.has_drawn_this_turn:
            return [{"action": "draw"}]
        return [{"action": "pass"}]

    def is_critical_turn(self) -> bool:
        my_role = self.my_player_num or 2
        if self.current_turn != my_role:
            return False
        if len(self.my_hand) <= 2:
            return True
        if any(cnt <= 2 for idx, cnt in enumerate(self.hands_count) if (idx + 1) != my_role):
            return True
        return False

    def _next_opponent_hand_size(self) -> int:
        my_role = self.my_player_num or 2
        if not self.hands_count:
            return 7
        n = len(self.hands_count)
        next_idx = ((my_role - 1) + self.direction) % n
        return self.hands_count[next_idx]

    def _score_card_move(self, move: Dict[str, Any]) -> float:
        card = move.get("card", {})
        col = str(card.get("color", ""))
        val = str(card.get("value", ""))
        next_opp_cards = self._next_opponent_hand_size()

        score = 0.0

        color_counts = {c: 0 for c in UNO_COLORS}
        for c in self.my_hand:
            cc = str(c.get("color", ""))
            if cc in color_counts:
                color_counts[cc] += 1

        if col in color_counts:
            score += 35.0 + color_counts[col] * 12.0

        if val in ("draw2", "skip", "reverse"):
            score += 45.0
            if next_opp_cards <= 2:
                score += 140.0
            elif next_opp_cards <= 4:
                score += 55.0
        elif val.isdigit():
            score += 20.0 + int(val) * 2.5
        elif val == "wild":
            if next_opp_cards <= 2:
                score += 65.0
            else:
                score -= 25.0
        elif val == "wild_draw4":
            if next_opp_cards <= 2:
                score += 220.0
            elif next_opp_cards <= 3:
                score += 85.0
            else:
                score -= 40.0

        return score

    def compute_next_move(self) -> Any:
        self._needs_continuation_move = False
        legal_moves = self.get_legal_moves()
        if not legal_moves:
            return None
        if len(legal_moves) == 1:
            return legal_moves[0]

        if self.level == 1:
            scored = [
                (self._score_card_move(m) + random.uniform(-40.0, 40.0), m)
                for m in legal_moves
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]
        elif self.level == 2:
            scored = [
                (self._score_card_move(m) + random.uniform(-10.0, 10.0), m)
                for m in legal_moves
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]
        else:
            scored = [(self._score_card_move(m), m) for m in legal_moves]
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]

    def build_move_command(self, move: Any) -> dict:
        if not isinstance(move, dict):
            return {"id": "DrawCard", "data": {}}
        action = move.get("action", "draw")
        if action == "play":
            return {
                "id": "PlayCard",
                "data": {
                    "card_uid": int(move["card_uid"]),
                    "chosen_color": str(move.get("chosen_color", self.current_color)),
                },
            }
        if action == "pass":
            return {"id": "PassTurn", "data": {}}
        return {"id": "DrawCard", "data": {}}

    def format_state(self) -> str:
        return (
            f"[UNO] Turn: P{self.current_turn} | Top: {self.current_color.upper()} {self.current_value} | "
            f"Hands: {self.hands_count} | My Cards: {len(self.my_hand)}"
        )
