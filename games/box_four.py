"""
BoxFour (چهارطرفه / BoxFour) Game Logic for Cafe Fekr Bots.
Decoupled game engine representing the 5x5 chain-reaction territory expansion board.
Matches kafehfekrbackend/Entities/Games/BoxFour/__init__.py and kafehfekr Flutter client 1:1.

Rules Summary:
- 5x5 grid (indices 0..24, where c_index = index // 5, r_index = index % 5).
- Initial state:
  - (c=2, r=1) -> index 11: Player 1 (Red), value = 3
  - (c=2, r=3) -> index 13: Player 2 (Blue), value = 3
- On a player's turn, they must select a cell currently owned by them (`equipped_user == gamer_id`).
- If the selected cell has `value < 3`, its value increments by 1 (`value + 1`).
- If the selected cell has `value == 3`, it triggers `spread_number((c, r), gamer_id)`:
  - The cell resets to `(value = 0, equipped_user = 0)`.
  - Each of its 4 orthogonal neighbors `MOVE_DIRS = [(-1, 0), (0, -1), (0, 1), (1, 0)]` inside the 5x5 grid
    is captured by `gamer_id` and incremented by 1 (or recursively explodes if its value was already 3).
- A player wins as soon as the opponent has 0 territories left on the board.
"""

import random
from typing import Any, List, Optional, Tuple
from .base_game import BaseGameLogic

MOVE_DIRS: List[Tuple[int, int]] = [
    (-1, 0),
    (0, -1),
    (0, 1),
    (1, 0),
]

# Positional weights for 5x5 grid (central cells have 4 orthogonal neighbors; edges have 3; corners have 2)
POSITION_WEIGHTS: List[List[float]] = [
    [2.0, 3.0, 3.5, 3.0, 2.0],
    [3.0, 4.5, 5.5, 4.5, 3.0],
    [3.5, 5.5, 7.0, 5.5, 3.5],
    [3.0, 4.5, 5.5, 4.5, 3.0],
    [2.0, 3.0, 3.5, 3.0, 2.0],
]


class BoxFourGameLogic(BaseGameLogic):
    """
    Complete BoxFour (چهارطرفه) implementation with 3 human-like AI levels:
    - Level 1 (Beginner / Casual Human): Plays valid owned cells with light preference for charging/expanding and casual noise so human players can enjoyably beat it.
    - Level 2 (Intermediate / Tactical): Evaluates 1-ply chain reactions and territory swing while avoiding self-wiping blunders.
    - Level 3 (Master / Minimax Lookahead): 2-ply lookahead maximizing territory differential, charge potential, and elimination wins.
    """

    def __init__(self, level: int = 1):
        super().__init__(
            game_type="BoxFour",
            game_type_aliases=[
                "boxfour",
                "box_four",
                "box-four",
                "چهارطرفه",
                "چهار طرفه",
                "چهارخانه",
            ],
            level=level,
        )
        self.values: List[List[int]] = [[0 for _ in range(5)] for _ in range(5)]
        self.owners: List[List[int]] = [[0 for _ in range(5)] for _ in range(5)]
        self.player1_score: int = 1
        self.player2_score: int = 1
        self.current_turn: int = 1
        self.reset()

    def reset(self) -> None:
        """Resets the 5x5 board to standard BoxFour starting positions (matching backend 1:1)."""
        self.values = [[0 for _ in range(5)] for _ in range(5)]
        self.owners = [[0 for _ in range(5)] for _ in range(5)]
        # Initial pieces matching BoxFourGameClass.init_board():
        # self.board[2][1].set_value(3, 1)
        # self.board[2][3].set_value(3, 2)
        self.values[2][1] = 3
        self.owners[2][1] = 1
        self.values[2][3] = 3
        self.owners[2][3] = 2
        self.player1_score = 1
        self.player2_score = 1
        self.current_turn = 1

    @staticmethod
    def is_valid_coord(col: int, row: int) -> bool:
        return 0 <= row < 5 and 0 <= col < 5

    def get_legal_moves(
        self,
        gamer_id: int,
        owners_state: Optional[List[List[int]]] = None,
    ) -> List[Tuple[int, int]]:
        """Returns all `(c_index, r_index)` coordinates currently owned by `gamer_id`."""
        own = owners_state if owners_state is not None else self.owners
        legal: List[Tuple[int, int]] = []
        for c in range(5):
            for r in range(5):
                if own[c][r] == gamer_id:
                    legal.append((c, r))
        return legal

    def simulate_move(
        self,
        move: Tuple[int, int],
        gamer_id: int,
        values_state: List[List[int]],
        owners_state: List[List[int]],
    ) -> None:
        """Applies `submit_piece_for_user` + `spread_number` in-place on `values_state` and `owners_state`."""
        c, r = move
        if not self.is_valid_coord(c, r):
            return
        cur_val = values_state[c][r]
        if cur_val < 3:
            values_state[c][r] = cur_val + 1
            owners_state[c][r] = gamer_id
        else:
            self._spread_number(c, r, gamer_id, values_state, owners_state, depth=0)

    def _spread_number(
        self,
        c: int,
        r: int,
        gamer_id: int,
        values_state: List[List[int]],
        owners_state: List[List[int]],
        depth: int = 0,
    ) -> None:
        if depth > 60:
            return
        values_state[c][r] = 0
        owners_state[c][r] = 0
        for dc, dr in MOVE_DIRS:
            ny = c + dc
            nx = r + dr
            if self.is_valid_coord(ny, nx):
                cur_val = values_state[ny][nx]
                if cur_val < 3:
                    values_state[ny][nx] = cur_val + 1
                    owners_state[ny][nx] = gamer_id
                else:
                    self._spread_number(ny, nx, gamer_id, values_state, owners_state, depth + 1)

    def _recalculate_scores(self) -> None:
        s1 = 0
        s2 = 0
        for c in range(5):
            for r in range(5):
                if self.owners[c][r] == 1:
                    s1 += 1
                elif self.owners[c][r] == 2:
                    s2 += 1
        self.player1_score = s1
        self.player2_score = s2

    # --- Server Command Handling ---

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes incoming BoxFour server commands."""
        if cmd_id in ("GameData", "ReconnectData"):
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                b_list = g_data.get("board", [])
                if isinstance(b_list, list) and len(b_list) == 25:
                    for idx, item in enumerate(b_list):
                        c_idx = idx // 5
                        r_idx = idx % 5
                        if isinstance(item, dict):
                            self.values[c_idx][r_idx] = int(item.get("value", 0))
                            self.owners[c_idx][r_idx] = int(
                                item.get("equipped_user", item.get("selected_user", 0))
                            )
                scores = g_data.get("scores")
                if isinstance(scores, list) and len(scores) >= 2:
                    self.player1_score = int(scores[0])
                    self.player2_score = int(scores[1])
                else:
                    self._recalculate_scores()
                if "current_turn" in g_data:
                    self.current_turn = int(g_data["current_turn"])
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                sdata = payload.get("select_data", payload)
                c_idx = sdata.get("c_index")
                r_idx = sdata.get("r_index")
                gamer_id = int(sdata.get("gamer_id", payload.get("gamer_id", 1)))
                if c_idx is not None and r_idx is not None:
                    self.simulate_move((int(c_idx), int(r_idx)), gamer_id, self.values, self.owners)
                    self._recalculate_scores()
            return True

        elif cmd_id == "CurrentTurn":
            turn = (
                payload
                if isinstance(payload, int)
                else (
                    payload.get("current_turn", payload.get("turn", 1))
                    if isinstance(payload, dict)
                    else 1
                )
            )
            self.current_turn = int(turn)
            return True

        return False

    # --- Bot Decision Engine ---

    def get_available_moves_count(self) -> int:
        my_id = self.my_player_num or 1
        return len(self.get_legal_moves(my_id))

    def is_move_obvious(self) -> bool:
        my_id = self.my_player_num or 1
        opp_id = 2 if my_id == 1 else 1
        legal = self.get_legal_moves(my_id)
        if len(legal) <= 1:
            return True
        # Check if any single move immediately eliminates all opponent cells
        for mv in legal:
            v_copy = [row[:] for row in self.values]
            o_copy = [row[:] for row in self.owners]
            self.simulate_move(mv, my_id, v_copy, o_copy)
            if not self.get_legal_moves(opp_id, o_copy):
                return True
        return False

    def compute_next_move(self) -> Optional[Tuple[int, int]]:
        """Selects `(c_index, r_index)` move according to `self.level`."""
        my_id = self.my_player_num or 1
        opp_id = 2 if my_id == 1 else 1
        legal = self.get_legal_moves(my_id)
        if not legal:
            return None
        if len(legal) == 1:
            return legal[0]

        if self.level == 1:
            return self._move_level_1(legal, my_id, opp_id)
        elif self.level == 2:
            return self._move_level_2(legal, my_id, opp_id)
        else:
            return self._move_level_3(legal, my_id, opp_id)

    def _move_level_1(
        self, legal: List[Tuple[int, int]], my_id: int, opp_id: int
    ) -> Tuple[int, int]:
        """
        Level 1 (Beginner / Casual Human):
        - Plays a casual human-like move with generous randomness so the player can enjoyably beat it.
        """
        scored: List[Tuple[float, Tuple[int, int]]] = []
        for mv in legal:
            v_copy = [row[:] for row in self.values]
            o_copy = [row[:] for row in self.owners]
            self.simulate_move(mv, my_id, v_copy, o_copy)
            my_cnt = len(self.get_legal_moves(my_id, o_copy))
            opp_cnt = len(self.get_legal_moves(opp_id, o_copy))
            cur_v = self.values[mv[0]][mv[1]]
            score = (my_cnt - opp_cnt) * 2.5 + cur_v * 1.5 + random.uniform(-6.0, 6.0)
            scored.append((score, mv))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _move_level_2(
        self, legal: List[Tuple[int, int]], my_id: int, opp_id: int
    ) -> Tuple[int, int]:
        """
        Level 2 (Intermediate / Tactical):
        - Evaluates immediate territory capture, charge buildup, and avoids leaving cells vulnerable next to enemy 3s.
        """
        best_score = -float("inf")
        best_move = legal[0]
        for mv in legal:
            v_copy = [row[:] for row in self.values]
            o_copy = [row[:] for row in self.owners]
            self.simulate_move(mv, my_id, v_copy, o_copy)
            score = self._evaluate_board(v_copy, o_copy, my_id, opp_id) + random.uniform(-1.5, 1.5)
            if score > best_score:
                best_score = score
                best_move = mv
        return best_move

    def _move_level_3(
        self, legal: List[Tuple[int, int]], my_id: int, opp_id: int
    ) -> Tuple[int, int]:
        """
        Level 3 (Master / 2-Ply Minimax):
        - Simulates our move and the opponent's strongest counter-explosion.
        """
        best_score = -float("inf")
        best_move = legal[0]
        for mv in legal:
            v_copy = [row[:] for row in self.values]
            o_copy = [row[:] for row in self.owners]
            self.simulate_move(mv, my_id, v_copy, o_copy)
            opp_legal = self.get_legal_moves(opp_id, o_copy)
            if not opp_legal:
                return mv  # Immediate victory!
            worst_reply = float("inf")
            for omv in opp_legal:
                v2 = [row[:] for row in v_copy]
                o2 = [row[:] for row in o_copy]
                self.simulate_move(omv, opp_id, v2, o2)
                reply_eval = self._evaluate_board(v2, o2, my_id, opp_id)
                if reply_eval < worst_reply:
                    worst_reply = reply_eval
            if worst_reply > best_score:
                best_score = worst_reply
                best_move = mv
        return best_move

    def _evaluate_board(
        self,
        values_state: List[List[int]],
        owners_state: List[List[int]],
        my_id: int,
        opp_id: int,
    ) -> float:
        my_cells = 0
        opp_cells = 0
        score = 0.0
        for c in range(5):
            for r in range(5):
                own = owners_state[c][r]
                val = values_state[c][r]
                pos_w = POSITION_WEIGHTS[c][r]
                if own == my_id:
                    my_cells += 1
                    score += 10.0 + val * 3.2 + pos_w * 0.4
                elif own == opp_id:
                    opp_cells += 1
                    score -= 10.0 + val * 3.2 + pos_w * 0.4
        if opp_cells == 0 and my_cells > 0:
            return 10000.0
        if my_cells == 0 and opp_cells > 0:
            return -10000.0
        return score

    def build_move_command(self, move: Tuple[int, int]) -> dict:
        """
        Builds server command dict for BoxFour.
        Matches kafehfekrbackend/Controllers/GameSession/box_four_game_session.py:
        data['id'] == commands.Select_Peace ('SelectPeace'),
        data['data'] == {'c_index': c_index, 'r_index': r_index}
        """
        return {
            "id": "SelectPeace",
            "data": {
                "c_index": int(move[0]),
                "r_index": int(move[1]),
            },
        }

    def format_state(self) -> str:
        """Returns readable 5x5 ASCII BoxFour board for terminal logs."""
        lines = [
            f"\n   BoxFour (چهارطرفه) | Score R:{self.player1_score} - B:{self.player2_score}",
            "     0    1    2    3    4",
            "   +----+----+----+----+----+",
        ]
        for c_idx in range(5):
            row_str = f" {c_idx} |"
            for r_idx in range(5):
                own = self.owners[c_idx][r_idx]
                val = self.values[c_idx][r_idx]
                if own == 1:
                    cell_txt = f"R{val}"
                elif own == 2:
                    cell_txt = f"B{val}"
                else:
                    cell_txt = "··"
                row_str += f" {cell_txt} |"
            lines.append(row_str)
            lines.append("   +----+----+----+----+----+")
        return "\n".join(lines)
