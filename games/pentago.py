"""
Pentago (پنتاگو) Bot Game Logic Engine for Cafe Fekr.
Matches backend Entities/Games/Pentago/__init__.py & PentagoGameSession 100%.

Board & Protocol:
- 36 cells (0..35) arranged in 4 quadrants of 9 cells each (3x3 row-major per quadrant):
  * Quadrant 0 (Top-Left):     0..8
  * Quadrant 1 (Top-Right):    9..17
  * Quadrant 2 (Bottom-Left):  18..26
  * Quadrant 3 (Bottom-Right): 27..35

- Two-step turn:
  * Step 1 (selection_played == False):
    Place a marble on an empty cell (0..35).
    Bot emits: {"id": "SelectPeace", "data": cell_id}
  * Step 2 (selection_played == True and rotation_played == False, triggered automatically
    via should_continue_turn() right after PeaceSelected):
    Rotate one of the 4 quadrants by 90 degrees (rotation_id in 1..8).
      - Odd rotation_id (1, 3, 5, 7): Counter-Clockwise (CCW) on Quadrant 0, 1, 2, 3
      - Even rotation_id (2, 4, 6, 8): Clockwise (CW) on Quadrant 0, 1, 2, 3
    Bot emits: {"id": "RotatePeace", "data": rotation_id}
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


class PentagoGameLogic(BaseGameLogic):
    """Pentago 3-level tactical bot engine."""

    NUM_CELLS = 36
    QUADRANT_CENTERS = {4, 13, 22, 31}

    # Exact 32 5-in-a-row win conditions from Entities/Games/Pentago/__init__.py
    WIN_CONDITIONS: List[List[int]] = [
        [0, 1, 2, 9, 10], [1, 2, 9, 10, 11], [3, 4, 5, 12, 13], [4, 5, 12, 13, 14],
        [6, 7, 8, 15, 16], [7, 8, 15, 16, 17], [18, 19, 20, 27, 28], [19, 20, 27, 28, 29],
        [21, 22, 23, 30, 31], [22, 23, 30, 31, 32], [24, 25, 26, 33, 34], [25, 26, 33, 34, 35],
        [0, 3, 6, 18, 21], [3, 6, 18, 21, 24], [1, 4, 7, 19, 22], [4, 7, 19, 22, 25],
        [2, 5, 8, 20, 23], [5, 8, 20, 23, 26], [9, 12, 15, 27, 30], [12, 15, 27, 30, 33],
        [10, 13, 16, 28, 31], [13, 16, 28, 31, 34], [11, 14, 17, 29, 32], [14, 17, 29, 32, 35],
        [21, 19, 8, 12, 10], [25, 23, 27, 16, 14], [1, 5, 15, 28, 32], [3, 7, 20, 30, 34],
        [24, 22, 20, 15, 13], [11, 13, 15, 20, 22], [0, 4, 8, 27, 31], [35, 31, 27, 8, 4],
    ]

    def __init__(self, level: int = 1):
        super().__init__(game_type="Pentago", level=level)
        self.game_type_aliases = ["pentago", "پنتاگو"]
        self.board: List[int] = [0] * self.NUM_CELLS
        self.selection_played: bool = False
        self.rotation_played: bool = False
        self.current_turn: int = 1
        self.pawns: List[int] = [18, 18]
        self._planned_rotation_id: Optional[int] = None
        self.reset()

    def reset(self):
        self.board = [0] * self.NUM_CELLS
        self.selection_played = False
        self.rotation_played = False
        self.current_turn = 1
        self.pawns = [18, 18]
        self._planned_rotation_id = None

    def _sync_board_array(self, raw_board: Any):
        if isinstance(raw_board, list) and len(raw_board) >= self.NUM_CELLS:
            for i in range(self.NUM_CELLS):
                val = raw_board[i]
                self.board[i] = int(val) if val is not None else 0

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "GameData":
            self.reset()
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                if isinstance(g_data, dict):
                    if "board" in g_data:
                        self._sync_board_array(g_data["board"])
                    if "pawns" in g_data and isinstance(g_data["pawns"], list) and len(g_data["pawns"]) >= 2:
                        self.pawns = [int(g_data["pawns"][0]), int(g_data["pawns"][1])]
                    self.selection_played = bool(g_data.get("selection_played", False))
                    self.rotation_played = bool(g_data.get("rotation_played", False))
                    if "current_turn" in g_data:
                        self.current_turn = int(g_data["current_turn"])
            return True

        if cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict):
                    if "board" in g_data:
                        self._sync_board_array(g_data["board"])
                    if "pawns" in g_data and isinstance(g_data["pawns"], list) and len(g_data["pawns"]) >= 2:
                        self.pawns = [int(g_data["pawns"][0]), int(g_data["pawns"][1])]
                    self.selection_played = bool(g_data.get("selection_played", False))
                    self.rotation_played = bool(g_data.get("rotation_played", False))
                    if "current_turn" in g_data:
                        self.current_turn = int(g_data["current_turn"])
            return True

        if cmd_id == "CurrentTurn":
            if isinstance(payload, dict):
                self.current_turn = int(payload.get("turn", 1))
            else:
                self.current_turn = int(payload)
            self.selection_played = False
            self.rotation_played = False
            self._planned_rotation_id = None
            return True

        if cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                user_id = int(payload.get("user", payload.get("gamer_id", self.current_turn)))
                cell_id = payload.get("target_peace", payload.get("cell_id", payload.get("piece_id", -1)))
                idx = int(cell_id)
                if 0 <= idx < self.NUM_CELLS:
                    self.board[idx] = user_id
                self.selection_played = True
            return True

        if cmd_id == "PeaceRotated":
            if isinstance(payload, dict):
                if "board" in payload and isinstance(payload["board"], list):
                    self._sync_board_array(payload["board"])
                elif "rotation_id" in payload:
                    rot_id = int(payload["rotation_id"])
                    self.board = self.simulate_rotate(self.board, rot_id)
                self.rotation_played = True
                self._planned_rotation_id = None
            return True

        return False

    def should_continue_turn(self) -> bool:
        """
        Returns True right after PeaceSelected on the bot's own turn so GameSession
        immediately executes Step 2 (RotatePeace).
        """
        my_id = self.my_player_num or 2
        return (
            self.current_turn == my_id
            and self.selection_played
            and not self.rotation_played
        )

    def should_act_on_reconnect(self) -> bool:
        my_id = self.my_player_num or 2
        return self.current_turn == my_id and not self.rotation_played

    @staticmethod
    def simulate_rotate(board: List[int], rotation_id: int) -> List[int]:
        """
        Mirrors Entities/Games/Pentago/__init__.py rotate_piece(rotation_id) 100%.
        Odd rotation_id (1, 3, 5, 7) -> Counter-Clockwise (CCW)
        Even rotation_id (2, 4, 6, 8) -> Clockwise (CW)
        """
        if not (1 <= rotation_id <= 8):
            return list(board)
        quad_idx = (rotation_id - 1) // 2
        base = quad_idx * 9
        q = board[base:base + 9]
        grid = [q[0:3], q[3:6], q[6:9]]
        if rotation_id % 2 == 1:
            # Counter-Clockwise
            rot = [list(row) for row in zip(*grid)][::-1]
        else:
            # Clockwise
            rot = [list(row) for row in zip(*grid[::-1])]
        flat = [cell for row in rot for cell in row]
        res = list(board)
        res[base:base + 9] = flat
        return res

    @classmethod
    def has_five_in_row(cls, board: List[int], player_id: int) -> bool:
        for cond in cls.WIN_CONDITIONS:
            if all(board[idx] == player_id for idx in cond):
                return True
        return False

    def get_legal_moves(self) -> List[Any]:
        my_id = self.my_player_num or 2
        if self.current_turn != my_id or self.rotation_played:
            return []
        if not self.selection_played:
            return [i for i in range(self.NUM_CELLS) if self.board[i] == 0]
        return [1, 2, 3, 4, 5, 6, 7, 8]

    def is_critical_turn(self) -> bool:
        my_id = self.my_player_num or 2
        opp_id = 1 if my_id == 2 else 2
        for cond in self.WIN_CONDITIONS:
            my_c = sum(1 for idx in cond if self.board[idx] == my_id)
            opp_c = sum(1 for idx in cond if self.board[idx] == opp_id)
            if (my_c >= 3 and opp_c == 0) or (opp_c >= 3 and my_c == 0):
                return True
        return False

    def compute_next_move(self) -> Any:
        legal = self.get_legal_moves()
        if not legal:
            return None

        my_id = self.my_player_num or 2
        opp_id = 1 if my_id == 2 else 2

        # STEP 2: Rotate a quadrant (1..8)
        if self.selection_played and not self.rotation_played:
            if self._planned_rotation_id is not None and self._planned_rotation_id in legal:
                rot_id = self._planned_rotation_id
                self._planned_rotation_id = None
                return ("RotatePeace", rot_id)
            best_rot = self._choose_best_rotation_for_current_board(self.board, my_id, opp_id)
            return ("RotatePeace", best_rot)

        # STEP 1: Select an empty cell (0..35) and plan Step 2 rotation (1..8)
        cell_id, rot_id = self._choose_best_cell_and_rotation(legal, my_id, opp_id)
        self._planned_rotation_id = rot_id
        return ("SelectPeace", cell_id)

    def _choose_best_cell_and_rotation(
        self, empty_cells: List[int], my_id: int, opp_id: int
    ) -> Tuple[int, int]:
        # 1. Check for immediate winning (cell_id, rot_id) pair
        win_pair = self._find_immediate_win(self.board, empty_cells, my_id, opp_id)
        if win_pair is not None:
            if self.level >= 2 or random.random() < 0.70:
                return win_pair

        # 2. Evaluate all (cell_id, rot_id) pairs
        candidates: List[Tuple[float, int, int, List[int]]] = []
        for cell_id in empty_cells:
            placed_board = list(self.board)
            placed_board[cell_id] = my_id
            center_bonus = 24.0 if cell_id in self.QUADRANT_CENTERS else 0.0

            for rot_id in range(1, 9):
                rotated = self.simulate_rotate(placed_board, rot_id)
                if self.has_five_in_row(rotated, opp_id):
                    # Avoid rotating opponent into a 5-in-a-row
                    continue
                sc = self._evaluate_board(rotated, my_id, opp_id) + center_bonus + random.uniform(-1.5, 1.5)
                candidates.append((sc, cell_id, rot_id, rotated))

        if not candidates:
            return random.choice(empty_cells), random.randint(1, 8)

        candidates.sort(key=lambda x: x[0], reverse=True)

        if self.level == 1:
            top_k = max(1, len(candidates) // 2)
            _, c_id, r_id, _ = random.choice(candidates[:top_k])
            return c_id, r_id

        if self.level == 2:
            # Check top 8 candidates for opponent immediate win threat
            best_l2: List[Tuple[float, int, int]] = []
            for sc, c_id, r_id, rot_board in candidates[:12]:
                opp_empty = [i for i, v in enumerate(rot_board) if v == 0]
                opp_win = self._find_immediate_win(rot_board, opp_empty, opp_id, my_id)
                adj_sc = sc - (40000.0 if opp_win is not None else 0.0)
                best_l2.append((adj_sc, c_id, r_id))
            best_l2.sort(key=lambda x: x[0], reverse=True)
            top_pool = best_l2[: min(3, len(best_l2))]
            _, c_id, r_id = random.choice(top_pool)
            return c_id, r_id

        # Level 3: Deep tactical lookahead against opponent's 1-turn win threats across top 28 candidates
        best_score = -1e12
        best_pair = (candidates[0][1], candidates[0][2])
        inspect_count = min(len(candidates), 28)
        for idx in range(inspect_count):
            sc, c_id, r_id, rot_board = candidates[idx]
            opp_empty = [i for i, v in enumerate(rot_board) if v == 0]
            opp_win = self._find_immediate_win(rot_board, opp_empty, opp_id, my_id)
            total_sc = sc - (60000.0 if opp_win is not None else 0.0)
            if total_sc > best_score:
                best_score = total_sc
                best_pair = (c_id, r_id)
        return best_pair

    def _find_immediate_win(
        self,
        board: List[int],
        empty_cells: List[int],
        player_id: int,
        other_id: int,
    ) -> Optional[Tuple[int, int]]:
        simultaneous_fallback: Optional[Tuple[int, int]] = None
        for cell_id in empty_cells:
            placed = list(board)
            placed[cell_id] = player_id
            for rot_id in range(1, 9):
                rotated = self.simulate_rotate(placed, rot_id)
                if self.has_five_in_row(rotated, player_id):
                    if not self.has_five_in_row(rotated, other_id):
                        return (cell_id, rot_id)
                    if simultaneous_fallback is None:
                        simultaneous_fallback = (cell_id, rot_id)
        return simultaneous_fallback

    def _choose_best_rotation_for_current_board(
        self, board: List[int], my_id: int, opp_id: int
    ) -> int:
        best_rot = 1
        best_score = -1e12
        for rot_id in range(1, 9):
            rotated = self.simulate_rotate(board, rot_id)
            if self.has_five_in_row(rotated, my_id) and not self.has_five_in_row(rotated, opp_id):
                return rot_id
            if self.has_five_in_row(rotated, opp_id):
                sc = -100000.0
            else:
                sc = self._evaluate_board(rotated, my_id, opp_id) + random.uniform(-1.0, 1.0)
            if sc > best_score:
                best_score = sc
                best_rot = rot_id
        return best_rot

    @classmethod
    def _evaluate_board(cls, board: List[int], my_id: int, opp_id: int) -> float:
        score = 0.0
        for cond in cls.WIN_CONDITIONS:
            my_c = 0
            opp_c = 0
            for idx in cond:
                val = board[idx]
                if val == my_id:
                    my_c += 1
                elif val == opp_id:
                    opp_c += 1

            if my_c > 0 and opp_c > 0:
                continue
            if my_c > 0:
                if my_c == 5:
                    score += 100000.0
                elif my_c == 4:
                    score += 950.0
                elif my_c == 3:
                    score += 115.0
                elif my_c == 2:
                    score += 18.0
                else:
                    score += 3.0
            elif opp_c > 0:
                if opp_c == 5:
                    score -= 100000.0
                elif opp_c == 4:
                    score -= 1250.0
                elif opp_c == 3:
                    score -= 145.0
                elif opp_c == 2:
                    score -= 22.0
                else:
                    score -= 3.0

        for c_idx in cls.QUADRANT_CENTERS:
            if board[c_idx] == my_id:
                score += 20.0
            elif board[c_idx] == opp_id:
                score -= 20.0

        return score

    def build_move_command(self, move: Any) -> dict:
        if isinstance(move, tuple) and len(move) == 2:
            cmd_name, val = move
            if cmd_name == "SelectPeace":
                return {"id": "SelectPeace", "data": int(val)}
            if cmd_name == "RotatePeace":
                return {"id": "RotatePeace", "data": int(val)}
        if self.selection_played and not self.rotation_played:
            return {"id": "RotatePeace", "data": int(move)}
        return {"id": "SelectPeace", "data": int(move)}

    def format_state(self) -> str:
        step_str = "RotateQuadrant" if self.selection_played else "PlaceMarble"
        filled = sum(1 for v in self.board if v != 0)
        return f"Pentago [Turn:P{self.current_turn} | Step:{step_str} | MarblesOnBoard:{filled}/36]"
