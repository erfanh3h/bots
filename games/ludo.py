"""
Ludo (منچ) Game Logic for Cafe Fekr Bot (Supports 2, 3, and 4 Players).

Matches exact rules and socket protocol of kafehfekrbackend/Entities/Games/Ludo:
- Supports 2, 3, or 4 players (gamer_id = 1..4):
  - Player 1 (Red):    entry at track index 0,  home stretch 36..39
  - Player 2 (Blue):   entry at track index 18, home stretch 40..43
  - Player 3 (Green):  entry at track index 27, home stretch 44..47
  - Player 4 (Yellow): entry at track index 9,  home stretch 48..51
- Special source indices for SelectPeace:
  - index = -2: Home Yard (requires dice == 6, moves 1 pawn to Start Portal -1)
  - index = -1: Start Portal (moves 1 pawn onto track at entry_idx + dice - 1)
  - index = 0..35: Main 36-tile circular track
  - index = 36..51: Player-specific 4-slot Home Stretch corridors
- Turn Lifecycle:
  1. Server emits CurrentTurn: {"turn": 1..4} (or {"turn": 1..4, "bonus": True}).
  2. Active player sends RollDice: {"id": "RollDice", "data": {}}.
  3. Server rolls 1..6:
     - If moves exist: emits RollResult: {"dice": d, "turn": t, "available_moves": [...]}.
     - If no moves exist: emits OutOfMove: {"turn": t, "dice": d} and rotates turn after 2s.
  4. Active player sends SelectPeace: {"id": "SelectPeace", "data": {"index": -2 | -1 | 0..51}}.
  5. Server broadcasts PeaceSelected and either grants a bonus turn (if dice == 6) or advances turn.

Difficulty Levels:
- Level 1 (Default): Beginner / Casual human player. Plays valid moves with light preference for captures/exits.
- Level 2: Intermediate / Tactical player. Prioritizes enemy captures, home stretch entry, and portal clearing.
- Level 3: Hard / Master player. Full danger/threat evaluation (1..6 tiles behind on ring), stack protection, and race equity.
"""

import copy
import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


START_RING_INDEX: Dict[int, int] = {
    1: 0,
    2: 18,
    3: 27,
    4: 9,
}

HOME_RANGE: Dict[int, List[int]] = {
    1: [36, 37, 38, 39],
    2: [40, 41, 42, 43],
    3: [44, 45, 46, 47],
    4: [48, 49, 50, 51],
}

GAMER_WIN_INDEXES_MAP: Dict[int, Dict[int, Dict[int, int]]] = {
    1: {
        30: {6: 36},
        31: {5: 36, 6: 37},
        32: {4: 36, 5: 37, 6: 38},
        33: {3: 36, 4: 37, 5: 38, 6: 39},
        34: {2: 36, 3: 37, 4: 38, 5: 39},
        35: {1: 36, 2: 37, 3: 38, 4: 39},
        36: {1: 37, 2: 38, 3: 39},
        37: {1: 38, 2: 39},
        38: {1: 39},
    },
    2: {
        12: {6: 40},
        13: {5: 40, 6: 41},
        14: {4: 40, 5: 41, 6: 42},
        15: {3: 40, 4: 41, 5: 42, 6: 43},
        16: {2: 40, 3: 41, 4: 42, 5: 43},
        17: {1: 40, 2: 41, 3: 42, 4: 43},
        40: {1: 41, 2: 42, 3: 43},
        41: {1: 42, 2: 43},
        42: {1: 43},
    },
    3: {
        21: {6: 44},
        22: {5: 44, 6: 45},
        23: {4: 44, 5: 45, 6: 46},
        24: {3: 44, 4: 45, 5: 46, 6: 47},
        25: {2: 44, 3: 45, 4: 46, 5: 47},
        26: {1: 44, 2: 45, 3: 46, 4: 47},
        44: {1: 45, 2: 46, 3: 47},
        45: {1: 46, 2: 47},
        46: {1: 47},
    },
    4: {
        3: {6: 48},
        4: {5: 48, 6: 49},
        5: {4: 48, 5: 49, 6: 50},
        6: {3: 48, 4: 49, 5: 50, 6: 51},
        7: {2: 48, 3: 49, 4: 50, 5: 51},
        8: {1: 48, 2: 49, 3: 50, 4: 51},
        48: {1: 49, 2: 50, 3: 51},
        49: {1: 50, 2: 51},
        50: {1: 51},
    },
}


class LudoGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Ludo",
            game_type_aliases=[
                "ludo",
                "منچ",
                "mench",
                "mensch",
            ],
            level=level,
        )
        self.players_count: int = 2
        self.board: List[Dict[str, int]] = []
        self.start_board: List[Dict[str, int]] = []
        self.players_out_pieces: List[int] = [4, 4, 4, 4]
        self.current_turn: int = 1
        self.current_dice: int = 0
        self.dices_rolled: bool = False
        self.server_available_moves: Optional[List[int]] = None
        self.rank1: Optional[int] = None
        self.rank2: Optional[int] = None
        self.reset()

    def reset(self):
        self.board = [{"count": 0, "equipped_user": 0} for _ in range(52)]
        self.start_board = [{"count": 0, "equipped_user": 0} for _ in range(4)]
        self.players_out_pieces = [4, 4, 4, 4]
        self.current_turn = 1
        self.current_dice = 0
        self.dices_rolled = False
        self.server_available_moves = None
        self.rank1 = None
        self.rank2 = None

    # ==========================================================================
    # Core State & Rule Helpers (Exact Port of LudoGameClass)
    # ==========================================================================
    @staticmethod
    def _compute_target_index(index: int, gamer_id: int, dice_val: int) -> Optional[int]:
        if dice_val <= 0:
            return None
        if index == -2:
            return -1 if dice_val == 6 else None
        if index == -1:
            entry = START_RING_INDEX.get(gamer_id, 0)
            return (entry + dice_val - 1) % 36

        win_map = GAMER_WIN_INDEXES_MAP.get(gamer_id, {})
        if index >= 36:
            return win_map.get(index, {}).get(dice_val, None)

        if index in win_map:
            dice_map = win_map[index]
            if dice_val in dice_map:
                return dice_map[dice_val]
            # Check if this dice_val overshoots the 4-slot home stretch (e.g. index 35 with dice 5 or 6, index 34 with dice 6)
            min_win_dice = min(dice_map.keys())
            if dice_val < min_win_dice:
                return (index + dice_val) % 36
            return None

        if 0 <= index < 36:
            return (index + dice_val) % 36
        return None

    def _compute_local_available_moves(self, gamer_id: int, dice_val: int) -> List[int]:
        if dice_val <= 0 or not (1 <= gamer_id <= 4):
            return []
        moves: List[int] = []

        for idx in range(52):
            sp = self.board[idx]
            if sp["equipped_user"] != gamer_id or sp["count"] <= 0:
                continue
            target = self._compute_target_index(idx, gamer_id, dice_val)
            if target is not None and 0 <= target < 52:
                if target >= 36 and self.board[target]["count"] > 0:
                    continue
                moves.append(idx)

        # Start portal (-1)
        if self.start_board[gamer_id - 1]["count"] > 0:
            moves.append(-1)

        # Home yard (-2) on rolling 6
        if self.players_out_pieces[gamer_id - 1] > 0 and dice_val == 6:
            moves.append(-2)

        return moves

    def _apply_move_to_self(
        self,
        gamer_id: int,
        src_index: int,
        target_index: int,
        move_type: str,
    ):
        if not (1 <= gamer_id <= 4):
            return
        if move_type == "out" or src_index == -2:
            self.players_out_pieces[gamer_id - 1] = max(0, self.players_out_pieces[gamer_id - 1] - 1)
            sb = self.start_board[gamer_id - 1]
            sb["equipped_user"] = gamer_id
            sb["count"] = sb.get("count", 0) + 1
        elif move_type == "start" or src_index == -1:
            sb = self.start_board[gamer_id - 1]
            sb["count"] = max(0, sb.get("count", 0) - 1)
            if sb["count"] == 0:
                sb["equipped_user"] = 0
            if 0 <= target_index < 52:
                td = self.board[target_index]
                if td["equipped_user"] not in (0, gamer_id) and target_index < 36:
                    enemy_id = td["equipped_user"]
                    self.players_out_pieces[enemy_id - 1] += td["count"]
                    td["count"] = 0
                td["equipped_user"] = gamer_id
                td["count"] += 1
        elif 0 <= src_index < 52:
            sd = self.board[src_index]
            sd["count"] = max(0, sd.get("count", 0) - 1)
            if sd["count"] == 0:
                sd["equipped_user"] = 0
            if 0 <= target_index < 52:
                td = self.board[target_index]
                if td["equipped_user"] not in (0, gamer_id) and target_index < 36:
                    enemy_id = td["equipped_user"]
                    self.players_out_pieces[enemy_id - 1] += td["count"]
                    td["count"] = 0
                td["equipped_user"] = gamer_id
                td["count"] += 1

    # ==========================================================================
    # Server Event Handling
    # ==========================================================================
    def should_continue_turn(self) -> bool:
        # In Ludo, bonus turns on rolling 6 are triggered by the server emitting CurrentTurn.
        return False

    def should_act_on_reconnect(self) -> bool:
        my_role = self.my_player_num or 2
        if self.current_turn != my_role:
            return False
        return len(self.get_legal_moves()) > 0

    def _sync_snapshots_from_payload(self, data: Dict[str, Any]):
        if "board" in data and isinstance(data["board"], list) and len(data["board"]) == 52:
            self.board = [
                {
                    "count": int(sp.get("count", 0)),
                    "equipped_user": int(sp.get("equipped_user", 0)),
                }
                for sp in data["board"]
            ]
        if "start_board" in data and isinstance(data["start_board"], list) and len(data["start_board"]) >= 2:
            sb_new = [{"count": 0, "equipped_user": 0} for _ in range(4)]
            for idx_sb, sp in enumerate(data["start_board"][:4]):
                if isinstance(sp, dict):
                    sb_new[idx_sb] = {
                        "count": int(sp.get("count", 0)),
                        "equipped_user": int(sp.get("equipped_user", 0)),
                    }
            self.start_board = sb_new
        if "players_out_pieces" in data and isinstance(data["players_out_pieces"], list) and len(data["players_out_pieces"]) >= 2:
            out_new = [4, 4, 4, 4]
            for idx_o, x in enumerate(data["players_out_pieces"][:4]):
                out_new[idx_o] = int(x)
            self.players_out_pieces = out_new

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "GameData":
            self.reset()
            if isinstance(payload, dict) and "gamers" in payload and isinstance(payload["gamers"], list):
                self.players_count = max(2, min(4, len(payload["gamers"])))
            return True

        elif cmd_id == "StartGame":
            self.is_game_active = True
            return True

        elif cmd_id == "CurrentTurn":
            turn = payload.get("turn", payload) if isinstance(payload, dict) else int(payload)
            self.current_turn = int(turn)
            self.dices_rolled = False
            self.current_dice = 0
            self.server_available_moves = None
            return True

        elif cmd_id == "RollResult":
            if isinstance(payload, dict):
                self.current_dice = int(payload.get("dice", 0))
                if "turn" in payload:
                    self.current_turn = int(payload["turn"])
                if "available_moves" in payload and isinstance(payload["available_moves"], list):
                    self.server_available_moves = [int(m) for m in payload["available_moves"]]
                else:
                    self.server_available_moves = None
            else:
                self.current_dice = int(payload)
                self.server_available_moves = None
            self.dices_rolled = True
            return True

        elif cmd_id == "OutOfMove":
            self.dices_rolled = True
            self.current_dice = 0
            self.server_available_moves = []
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                if any(k in payload for k in ("board", "start_board", "players_out_pieces")):
                    self._sync_snapshots_from_payload(payload)
                else:
                    gamer_id = int(payload.get("gamer_id", self.current_turn))
                    src_idx = int(payload.get("index", 0))
                    tgt_idx = int(payload.get("target_index", -1))
                    m_type = str(payload.get("type", "in"))
                    self._apply_move_to_self(gamer_id, src_idx, tgt_idx, m_type)
            self.current_dice = 0
            self.server_available_moves = []
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
                    self._sync_snapshots_from_payload(g_data)
                    if "players_count" in g_data:
                        self.players_count = max(2, min(4, int(g_data["players_count"])))
                    self.current_turn = int(g_data.get("current_turn", 1))
                    self.current_dice = int(g_data.get("current_dice", 0))
                    self.dices_rolled = bool(g_data.get("current_turn_player_rolled", False))
                    if "available_moves" in g_data and isinstance(g_data["available_moves"], list):
                        self.server_available_moves = [int(m) for m in g_data["available_moves"]]
            return True

        return False

    # ==========================================================================
    # Legal Move Generation & AI Decision Engine (Levels 1, 2, 3)
    # ==========================================================================
    def get_legal_moves(self) -> List[Dict[str, Any]]:
        my_role = self.my_player_num or 2
        if self.current_turn != my_role:
            return []

        if not self.dices_rolled:
            return [{"action": "roll"}]

        if self.current_dice <= 0:
            return []

        raw_indices = (
            self.server_available_moves
            if self.server_available_moves is not None
            else self._compute_local_available_moves(my_role, self.current_dice)
        )
        return [{"action": "move", "index": int(idx)} for idx in raw_indices]

    def is_critical_turn(self) -> bool:
        my_role = self.my_player_num or 2
        if self.current_turn != my_role or not self.dices_rolled:
            return False
        moves = self.get_legal_moves()
        return len(moves) > 1

    def _progress_on_track(self, gamer_id: int, spot_idx: int) -> int:
        """Returns 0..35 progress along gamer_id's circular path, or 36..39 for home stretch."""
        if spot_idx >= 36:
            home_slots = HOME_RANGE.get(gamer_id, [])
            if spot_idx in home_slots:
                return 36 + home_slots.index(spot_idx)
            return 36
        entry = START_RING_INDEX.get(gamer_id, 0)
        return (spot_idx - entry) % 36

    def _danger_at_ring_spot(self, gamer_id: int, ring_idx: int) -> float:
        """Estimates threat from enemy pawns 1..6 steps behind ring_idx on the 36-tile track."""
        if not (0 <= ring_idx < 36):
            return 0.0
        threat = 0.0
        for dist in range(1, 7):
            behind_idx = (ring_idx - dist) % 36
            sp = self.board[behind_idx]
            owner = sp["equipped_user"]
            if owner not in (0, gamer_id) and sp["count"] > 0:
                # Check if enemy at behind_idx would actually land on ring_idx with dice=dist
                enemy_target = self._compute_target_index(behind_idx, owner, dist)
                if enemy_target == ring_idx:
                    threat += 1.0
            # Also check enemy start portals (-1) that could hit ring_idx
            for enemy_id in range(1, self.players_count + 1):
                if enemy_id == gamer_id:
                    continue
                if self.start_board[enemy_id - 1]["count"] > 0:
                    if self._compute_target_index(-1, enemy_id, dist) == ring_idx:
                        threat += 0.85
        return threat

    def _score_move(self, src_index: int, gamer_id: int, dice_val: int) -> float:
        target = self._compute_target_index(src_index, gamer_id, dice_val)
        if target is None:
            return -9999.0

        score = 0.0

        # 1. Bringing a new pawn out of Home Yard (-2 -> -1) on rolling 6
        if src_index == -2:
            active_on_board = sum(
                sp["count"] for sp in self.board if sp["equipped_user"] == gamer_id
            ) + self.start_board[gamer_id - 1]["count"]
            if active_on_board == 0:
                return 420.0  # Must get a pawn onto the board
            return 165.0 + max(0, 3 - active_on_board) * 35.0

        # 2. Moving from Start Portal (-1) onto the main track
        if src_index == -1:
            score += 140.0
            if 0 <= target < 36:
                td = self.board[target]
                if td["equipped_user"] not in (0, gamer_id) and td["count"] > 0:
                    enemy_id = td["equipped_user"]
                    enemy_prog = self._progress_on_track(enemy_id, target)
                    score += 340.0 + td["count"] * 90.0 + enemy_prog * 3.5
                if self.level >= 3:
                    score -= self._danger_at_ring_spot(gamer_id, target) * 28.0
            return score

        # 3. Moving an existing pawn on the track (0..35) or inside Home Stretch (36..51)
        cur_prog = self._progress_on_track(gamer_id, src_index)
        tgt_prog = self._progress_on_track(gamer_id, target)

        # Capture bonus on main ring (0..35)
        if 0 <= target < 36:
            td = self.board[target]
            if td["equipped_user"] not in (0, gamer_id) and td["count"] > 0:
                enemy_id = td["equipped_user"]
                enemy_prog = self._progress_on_track(enemy_id, target)
                score += 360.0 + td["count"] * 95.0 + enemy_prog * 4.0

        # Entering safe Home Stretch (36..51) from the ring (0..35)
        if src_index < 36 and target >= 36:
            score += 290.0 + (tgt_prog - 36) * 20.0
        elif src_index >= 36 and target >= 36:
            # Advancing deeper inside Home Stretch
            score += 55.0 + (tgt_prog - cur_prog) * 15.0

        # Advancing along the main track
        if src_index < 36 and target < 36:
            score += cur_prog * 2.4 + dice_val * 3.0
            # Clear our own entry square so Start Portal pawns aren't stacked/vulnerable
            if src_index == START_RING_INDEX.get(gamer_id, 0):
                score += 45.0

        # Level 3: Tactical threat & safety analysis
        if self.level >= 3 and src_index < 36:
            cur_danger = self._danger_at_ring_spot(gamer_id, src_index)
            tgt_danger = self._danger_at_ring_spot(gamer_id, target) if target < 36 else 0.0
            stack_cnt = self.board[src_index]["count"]
            # Bonus for escaping a dangerous square
            score += cur_danger * (42.0 + cur_prog * 1.1)
            # Penalty for landing on a dangerous square
            dest_friendlies = self.board[target]["count"] if (target < 36 and self.board[target]["equipped_user"] == gamer_id) else 0
            score -= tgt_danger * (38.0 + tgt_prog * 1.1 + dest_friendlies * 25.0)
            # Slight penalty for breaking a safe stack unless capturing or entering home
            if stack_cnt > 1 and target < 36 and tgt_danger > 0:
                score -= 18.0

        return score

    def compute_next_move(self) -> Any:
        legal_moves = self.get_legal_moves()
        if not legal_moves:
            return None
        if len(legal_moves) == 1:
            return legal_moves[0]

        if self.level == 1:
            return self._choose_level_1(legal_moves)
        elif self.level == 2:
            return self._choose_level_2(legal_moves)
        else:
            return self._choose_level_3(legal_moves)

    def _choose_level_1(self, legal_moves: List[Dict[str, Any]]) -> Dict[str, Any]:
        my_role = self.my_player_num or 2
        # Casual human: 55% chance to pick a high-value move (capture/exit/home), 45% pure random
        if random.random() < 0.55 and len(legal_moves) > 1:
            scored = [
                (self._score_move(m["index"], my_role, self.current_dice) + random.uniform(-25.0, 25.0), m)
                for m in legal_moves
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]
        return random.choice(legal_moves)

    def _choose_level_2(self, legal_moves: List[Dict[str, Any]]) -> Dict[str, Any]:
        my_role = self.my_player_num or 2
        scored = [
            (self._score_move(m["index"], my_role, self.current_dice) + random.uniform(-8.0, 8.0), m)
            for m in legal_moves
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _choose_level_3(self, legal_moves: List[Dict[str, Any]]) -> Dict[str, Any]:
        my_role = self.my_player_num or 2
        scored = [
            (self._score_move(m["index"], my_role, self.current_dice), m)
            for m in legal_moves
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def build_move_command(self, move: Any) -> dict:
        if isinstance(move, dict) and move.get("action") == "roll":
            return {"id": "RollDice", "data": {}}
        idx = move["index"] if isinstance(move, dict) else int(move)
        return {
            "id": "SelectPeace",
            "data": {"index": int(idx)},
        }

    def format_state(self) -> str:
        home_counts = []
        for g_id in range(1, self.players_count + 1):
            hc = sum(self.board[idx]["count"] for idx in HOME_RANGE[g_id] if self.board[idx]["equipped_user"] == g_id)
            home_counts.append(f"P{g_id}:{hc}/4(out:{self.players_out_pieces[g_id - 1]})")
        return (
            f"[Ludo] Turn: P{self.current_turn} | Dice: {self.current_dice} | "
            f"{', '.join(home_counts)}"
        )
