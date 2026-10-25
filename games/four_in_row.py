"""
Four-in-a-Row (FourInRow / دوز چهارتایی) Pure Game Logic for Cafe Fekr Bots.

Decoupled game engine containing 8x8 gravity-drop board representation, exact rule validation
(matching kafehfekrbackend/Entities/Games/FourInRow/__init__.py 1:1), and AI move generation
across difficulty levels:
- Level 1: Easiest (Beginner / Casual Human, occasional win/block awareness, center preference) [DEFAULT]
- Level 2: Medium (Intermediate / Tactical Human, takes immediate wins, blocks threats, avoids gifting wins above)
- Level 3: Hard (Master / Alpha-Beta Minimax search with positional & window heuristics)

All bots default to level=1, and lobby bots are strictly level 1.
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


MOVE_DIRS: List[Tuple[int, int]] = [
    (-1, -1), (-1, 0), (-1, +1),
    (0, -1),           (0, +1),
    (+1, -1), (+1, 0), (+1, +1),
]

# Center columns (3, 4) offer maximum horizontal and diagonal 4-in-a-row connectivity
COLUMN_WEIGHTS = [2, 4, 7, 11, 11, 7, 4, 2]


class FourInRowGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="FourInRow",
            game_type_aliases=[
                "fourinrow",
                "four_in_row",
                "four-in-a-row",
                "connect4",
                "connectfour",
                "دوز چهارتایی",
                "چهار در یک ردیف",
            ],
            level=level,
        )
        # board[c_index][r_index] where c_index is vertical row (0=top..7=bottom),
        # and r_index is horizontal column (0=left..7=right)
        self.board: List[List[int]] = [[0 for _ in range(8)] for _ in range(8)]
        self.player1_pawns: int = 32
        self.player2_pawns: int = 32
        self.reset()

    def reset(self):
        """Resets the 8x8 gravity rack to empty state with 32 pawns per player."""
        self.board = [[0 for _ in range(8)] for _ in range(8)]
        self.player1_pawns = 32
        self.player2_pawns = 32

    # --- Coordinate & Gravity Helpers (1:1 with kafehfekrbackend) ---

    @staticmethod
    def _is_valid_coordinate(col: int, row: int) -> bool:
        return 0 <= row < 8 and 0 <= col < 8

    def get_possible_piece_column(
        self, r_index: int, board_state: Optional[List[List[int]]] = None
    ) -> int:
        """
        Returns the lowest empty vertical row index (c_index from 7 down to 0)
        for horizontal column r_index (0..7), or -1 if the column is full.
        Matches FourInRowGameClass.get_possible_piece_column 1:1.
        """
        if r_index < 0 or r_index >= 8:
            return -1
        b = board_state if board_state is not None else self.board
        for c_idx in range(7, -1, -1):
            if b[c_idx][r_index] == 0:
                return c_idx
        return -1

    def submit_piece(
        self,
        c_index: int,
        r_index: int,
        gamer_id: int,
        board_state: Optional[List[List[int]]] = None,
    ) -> None:
        b = board_state if board_state is not None else self.board
        if self._is_valid_coordinate(c_index, r_index):
            b[c_index][r_index] = gamer_id
            if board_state is None:
                if gamer_id == 1:
                    self.player1_pawns = max(0, self.player1_pawns - 1)
                elif gamer_id == 2:
                    self.player2_pawns = max(0, self.player2_pawns - 1)

    def is_win_happen(
        self,
        gamer_id: int,
        position: Tuple[int, int],
        board_state: Optional[List[List[int]]] = None,
    ) -> bool:
        """
        Exact 1:1 mirror of FourInRowGameClass.is_win_happen(gamer_id, position)
        plus full 4-in-a-row line check through `position = (c_index, r_index)`.
        Note: In kafehfekrbackend, `is_win_happen` checks single-ray directions from `position`.
        """
        b = board_state if board_state is not None else self.board
        # 1. Exact backend single-ray check (triggers immediate server Finish_Game)
        for direction in MOVE_DIRS:
            i = 1
            while True:
                if i == 4:
                    return True
                col = position[0] + direction[0] * i
                row = position[1] + direction[1] * i
                if self._is_valid_coordinate(col, row) and b[col][row] == gamer_id:
                    i += 1
                else:
                    break
        return False

    def _has_any_four_in_line(
        self,
        gamer_id: int,
        position: Tuple[int, int],
        board_state: Optional[List[List[int]]] = None,
    ) -> bool:
        """Checks whether placing `gamer_id` at `position = (c_index, r_index)` creates 4 contiguous pieces along any axis."""
        b = board_state if board_state is not None else self.board
        c0, r0 = position
        for dc, dr in ((0, 1), (1, 0), (1, 1), (1, -1)):
            count = 1
            for sign in (1, -1):
                step = 1
                while step < 4:
                    nc = c0 + dc * step * sign
                    nr = r0 + dr * step * sign
                    if self._is_valid_coordinate(nc, nr) and b[nc][nr] == gamer_id:
                        count += 1
                        step += 1
                    else:
                        break
            if count >= 4:
                return True
        return False

    # --- Server Command Handling ---

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes server events for Four-in-a-Row."""
        if cmd_id in ("GameData", "ReconnectData"):
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                b_list = g_data.get("board", [])
                if isinstance(b_list, list) and len(b_list) == 64:
                    for idx, val in enumerate(b_list):
                        c_idx = idx // 8
                        r_idx = idx % 8
                        self.board[c_idx][r_idx] = int(val) if isinstance(val, (int, float)) else 0
                pawns = g_data.get("pawns_count")
                if isinstance(pawns, list) and len(pawns) >= 2:
                    self.player1_pawns = int(pawns[0])
                    self.player2_pawns = int(pawns[1])
                else:
                    p1_used = sum(1 for row in self.board for v in row if v == 1)
                    p2_used = sum(1 for row in self.board for v in row if v == 2)
                    self.player1_pawns = max(0, 32 - p1_used)
                    self.player2_pawns = max(0, 32 - p2_used)
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                sdata = payload.get("select_data", payload)
                c_idx = sdata.get("c_index")
                r_idx = sdata.get("r_index")
                gamer_id = sdata.get("gamer_id", payload.get("gamer_id", 1))
                if c_idx is not None and r_idx is not None:
                    self.submit_piece(int(c_idx), int(r_idx), int(gamer_id))
            return True

        return False

    # --- Move Generation & AI Decision Engine ---

    def get_legal_moves(self, board_state: Optional[List[List[int]]] = None) -> List[int]:
        """Returns all valid horizontal column indices r_index in [0..7] that are not full."""
        b = board_state if board_state is not None else self.board
        return [r_idx for r_idx in range(8) if self.get_possible_piece_column(r_idx, b) != -1]

    def is_critical_turn(self) -> bool:
        """Returns True if either player has an immediate winning column."""
        my_id = self.my_player_num if self.my_player_num in (1, 2) else 2
        opp_id = 2 if my_id == 1 else 1
        return (
            self._find_winning_column(my_id) is not None
            or self._find_winning_column(opp_id) is not None
        )

    def compute_next_move(self) -> Optional[int]:
        legal = self.get_legal_moves()
        if not legal:
            return None

        my_id = self.my_player_num if self.my_player_num in (1, 2) else 2
        opp_id = 2 if my_id == 1 else 1

        if self.level == 1:
            return self._compute_level_1(legal, my_id, opp_id)
        elif self.level == 2:
            return self._compute_level_2(legal, my_id, opp_id)
        else:
            return self._compute_level_3(legal, my_id, opp_id)

    # ---------------------------------------------------------
    # Level 1: Easiest (Beginner / Casual Human) [DEFAULT]
    # ---------------------------------------------------------
    def _compute_level_1(self, legal: List[int], my_id: int, opp_id: int) -> int:
        # 45% chance to spot an immediate 4-in-a-row win
        win_col = self._find_winning_column(my_id)
        if win_col is not None and random.random() < 0.45:
            return win_col

        # 35% chance to block opponent's immediate 4-in-a-row threat
        block_col = self._find_winning_column(opp_id)
        if block_col is not None and random.random() < 0.35:
            return block_col

        # Weighted preference toward central columns (2, 3, 4, 5) with human randomness
        weights = [COLUMN_WEIGHTS[r] + random.uniform(0, 4.0) for r in legal]
        return random.choices(legal, weights=weights, k=1)[0]

    # ---------------------------------------------------------
    # Level 2: Medium (Intermediate / Tactical Human)
    # ---------------------------------------------------------
    def _compute_level_2(self, legal: List[int], my_id: int, opp_id: int) -> int:
        # 1. Always take an immediate server win
        win_col = self._find_winning_column(my_id)
        if win_col is not None:
            return win_col

        # 2. Block opponent's immediate win (90% consistency)
        block_col = self._find_winning_column(opp_id)
        if block_col is not None and random.random() < 0.90:
            return block_col

        # 3. Filter out columns that immediately gift opponent a win on the row above (c_idx - 1)
        safe_moves = [r for r in legal if not self._gifts_opponent_win(r, my_id, opp_id)]
        candidates = safe_moves if safe_moves else legal

        # 4. Score candidates by local connectivity + center preference
        best_col = candidates[0]
        best_score = -float("inf")
        for r_idx in candidates:
            c_idx = self.get_possible_piece_column(r_idx)
            self.board[c_idx][r_idx] = my_id
            score = self._evaluate_board(my_id, opp_id) + random.uniform(-6.0, 6.0)
            self.board[c_idx][r_idx] = 0
            if score > best_score:
                best_score = score
                best_col = r_idx
        return best_col

    # ---------------------------------------------------------
    # Level 3: Hard (Master / Alpha-Beta Minimax Search)
    # ---------------------------------------------------------
    def _compute_level_3(self, legal: List[int], my_id: int, opp_id: int) -> int:
        # 1. Immediate win check
        win_col = self._find_winning_column(my_id)
        if win_col is not None:
            return win_col

        # 2. Immediate forced block check
        block_col = self._find_winning_column(opp_id)
        if block_col is not None:
            return block_col

        # Order columns center-first for optimal alpha-beta pruning
        ordered = sorted(legal, key=lambda r: COLUMN_WEIGHTS[r], reverse=True)
        best_col = ordered[0]
        best_score = -float("inf")
        alpha = -float("inf")
        beta = float("inf")

        for r_idx in ordered:
            c_idx = self.get_possible_piece_column(r_idx)
            self.board[c_idx][r_idx] = my_id
            score = self._alphabeta(
                depth=3,
                alpha=alpha,
                beta=beta,
                is_maximizing=False,
                my_id=my_id,
                opp_id=opp_id,
                last_move=(c_idx, r_idx, my_id),
            )
            self.board[c_idx][r_idx] = 0
            if score > best_score:
                best_score = score
                best_col = r_idx
            alpha = max(alpha, best_score)

        return best_col

    def _alphabeta(
        self,
        depth: int,
        alpha: float,
        beta: float,
        is_maximizing: bool,
        my_id: int,
        opp_id: int,
        last_move: Tuple[int, int, int],
    ) -> float:
        lc, lr, l_player = last_move
        if self.is_win_happen(l_player, (lc, lr)):
            return (10000.0 + depth * 100.0) if l_player == my_id else (-10000.0 - depth * 100.0)

        legal = self.get_legal_moves()
        if depth == 0 or not legal:
            return self._evaluate_board(my_id, opp_id)

        ordered = sorted(legal, key=lambda r: COLUMN_WEIGHTS[r], reverse=True)

        if is_maximizing:
            value = -float("inf")
            for r_idx in ordered:
                c_idx = self.get_possible_piece_column(r_idx)
                self.board[c_idx][r_idx] = my_id
                value = max(
                    value,
                    self._alphabeta(
                        depth - 1, alpha, beta, False, my_id, opp_id, (c_idx, r_idx, my_id)
                    ),
                )
                self.board[c_idx][r_idx] = 0
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = float("inf")
            for r_idx in ordered:
                c_idx = self.get_possible_piece_column(r_idx)
                self.board[c_idx][r_idx] = opp_id
                value = min(
                    value,
                    self._alphabeta(
                        depth - 1, alpha, beta, True, my_id, opp_id, (c_idx, r_idx, opp_id)
                    ),
                )
                self.board[c_idx][r_idx] = 0
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value

    # --- Threat & Heuristic Helpers ---

    def _find_winning_column(self, gamer_id: int) -> Optional[int]:
        """Checks if dropping a piece in any legal column triggers an immediate win."""
        # First check exact backend unidirectional ray win (guarantees server Finish_Game)
        for r_idx in self.get_legal_moves():
            c_idx = self.get_possible_piece_column(r_idx)
            self.board[c_idx][r_idx] = gamer_id
            is_server_win = self.is_win_happen(gamer_id, (c_idx, r_idx))
            self.board[c_idx][r_idx] = 0
            if is_server_win:
                return r_idx

        # Also check any 4-in-a-line completion
        for r_idx in self.get_legal_moves():
            c_idx = self.get_possible_piece_column(r_idx)
            self.board[c_idx][r_idx] = gamer_id
            is_line_win = self._has_any_four_in_line(gamer_id, (c_idx, r_idx))
            self.board[c_idx][r_idx] = 0
            if is_line_win:
                return r_idx
        return None

    def _gifts_opponent_win(self, r_index: int, my_id: int, opp_id: int) -> bool:
        """Returns True if playing in r_index allows opp_id to win immediately on top of our piece."""
        c_idx = self.get_possible_piece_column(r_index)
        if c_idx <= 0:
            return False
        self.board[c_idx][r_index] = my_id
        above_c = c_idx - 1
        self.board[above_c][r_index] = opp_id
        opp_wins = self.is_win_happen(opp_id, (above_c, r_index)) or self._has_any_four_in_line(
            opp_id, (above_c, r_index)
        )
        self.board[above_c][r_index] = 0
        self.board[c_idx][r_index] = 0
        return opp_wins

    def _evaluate_board(self, my_id: int, opp_id: int) -> float:
        score = 0.0
        # 1. Center column control bonus
        for c_idx in range(8):
            for r_idx in range(8):
                occ = self.board[c_idx][r_idx]
                if occ == my_id:
                    score += COLUMN_WEIGHTS[r_idx]
                elif occ == opp_id:
                    score -= COLUMN_WEIGHTS[r_idx]

        # 2. Evaluate all 4-cell windows (horizontal, vertical, both diagonals)
        # Horizontal
        for c in range(8):
            for r in range(5):
                window = [self.board[c][r + i] for i in range(4)]
                score += self._score_window(window, my_id, opp_id)
        # Vertical
        for r in range(8):
            for c in range(5):
                window = [self.board[c + i][r] for i in range(4)]
                score += self._score_window(window, my_id, opp_id)
        # Positive Diagonal (\)
        for c in range(5):
            for r in range(5):
                window = [self.board[c + i][r + i] for i in range(4)]
                score += self._score_window(window, my_id, opp_id)
        # Negative Diagonal (/)
        for c in range(3, 8):
            for r in range(5):
                window = [self.board[c - i][r + i] for i in range(4)]
                score += self._score_window(window, my_id, opp_id)

        return score

    @staticmethod
    def _score_window(window: List[int], my_id: int, opp_id: int) -> float:
        my_cnt = window.count(my_id)
        opp_cnt = window.count(opp_id)
        empty_cnt = window.count(0)
        if my_cnt > 0 and opp_cnt > 0:
            return 0.0
        if my_cnt == 4:
            return 500.0
        if my_cnt == 3 and empty_cnt == 1:
            return 28.0
        if my_cnt == 2 and empty_cnt == 2:
            return 6.0
        if opp_cnt == 4:
            return -500.0
        if opp_cnt == 3 and empty_cnt == 1:
            return -34.0
        if opp_cnt == 2 and empty_cnt == 2:
            return -7.0
        return 0.0

    def build_move_command(self, move: int) -> dict:
        """
        Builds server command dict for FourInRow.
        Matches kafehfekrbackend/Controllers/GameSession/four_in_row_game_session.py:
        data['id'] == commands.Select_Peace ('SelectPeace'), data['data'] == {'r_index': row_index}
        """
        return {
            "id": "SelectPeace",
            "data": {
                "r_index": int(move),
            },
        }

    def format_state(self) -> str:
        """Returns readable 8x8 ASCII gravity rack for terminal logs."""
        syms = {0: "·", 1: "R", 2: "B"}
        lines = [
            f"\n   FourInRow | P1 (Red): {self.player1_pawns} | P2 (Blue): {self.player2_pawns}",
            "     0   1   2   3   4   5   6   7",
            "   +---+---+---+---+---+---+---+---+",
        ]
        for c_idx in range(8):
            row_str = f" {c_idx} |"
            for r_idx in range(8):
                val = self.board[c_idx][r_idx]
                row_str += f" {syms.get(val, '·')} |"
            lines.append(row_str)
            lines.append("   +---+---+---+---+---+---+---+---+")
        lines.append("   (R = P1 Red Disc, B = P2 Blue Disc)\n")
        return "\n".join(lines)
