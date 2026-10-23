"""
TicTacToe Pure Game Logic for Cafe Fekr.

Decoupled game engine containing board representation, rule validation,
and AI move generation across difficulty levels (1: easiest, 2: medium, 3: hard).
Default level is 1.
"""

import random
from typing import Any, List, Optional

from .base_game import BaseGameLogic


class TicTacToeGameLogic(BaseGameLogic):
    WIN_LINES = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
        [0, 4, 8], [2, 4, 6]              # Diagonals
    ]

    def __init__(self, level: int = 1):
        super().__init__(
            game_type="TicTacToe",
            game_type_aliases=["tictactoe", "دوز", "tic", "ttt"],
            level=level,  # Default level 1
        )
        self.board: List[int] = [0] * 9  # 0: empty, 1: P1 (X), 2: P2 (O)
        self.scores: List[int] = [0, 0]

    def reset(self):
        """Resets the board for a new round."""
        self.board = [0] * 9

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes server events related to TicTacToe board state."""
        if cmd_id == "GameData":
            if isinstance(payload, dict):
                if "board" in payload and isinstance(payload["board"], list):
                    self.board = list(payload["board"])
                if "scores" in payload and isinstance(payload["scores"], list):
                    self.scores = list(payload["scores"])
                if "current_round" in payload:
                    self.current_round = payload.get("current_round", 1)
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                user = payload.get("user")
                cell = payload.get("target_peace")
                if cell is not None and 0 <= cell < 9:
                    self.board[cell] = user
            return True

        return False

    def get_legal_moves(self) -> List[int]:
        """Returns all open cell indices [0..8]."""
        return [i for i, val in enumerate(self.board) if val == 0]

    def is_critical_turn(self) -> bool:
        """
        Returns True if someone has an immediate winning threat,
        so human behavior can simulate hesitation / double-checking.
        """
        my_sym = self.my_player_num if self.my_player_num in (1, 2) else 2
        opp_sym = 2 if my_sym == 1 else 1

        return (
            self._find_winning_cell(my_sym) is not None
            or self._find_winning_cell(opp_sym) is not None
        )

    def compute_next_move(self) -> Optional[int]:
        """Computes move based on difficulty level (1=easiest, 2=medium, 3=hard)."""
        legal = self.get_legal_moves()
        if not legal:
            return None

        if self.level == 1:
            return self._compute_level_1(legal)
        elif self.level == 2:
            return self._compute_level_2(legal)
        else:
            return self._compute_level_3(legal)

    # ---------------------------------------------------------
    # Level 1: Easiest (Beginner / Casual Human, Prone to Errors)
    # ---------------------------------------------------------
    def _compute_level_1(self, legal: List[int]) -> int:
        """
        Level 1 - Beginner:
        - Casual, imperfect play.
        - 30% chance to take an immediate winning move.
        - 20% chance to block an opponent's immediate win (often misses blocks).
        - Plays mostly randomly or instinctively.
        """
        my_sym = self.my_player_num if self.my_player_num in (1, 2) else 2
        opp_sym = 2 if my_sym == 1 else 1

        # Occasional win realization (30%)
        win_move = self._find_winning_cell(my_sym)
        if win_move is not None and random.random() < 0.30:
            return win_move

        # Occasional block (20% - beginners often overlook threats)
        block_move = self._find_winning_cell(opp_sym)
        if block_move is not None and random.random() < 0.20:
            return block_move

        # 40% chance to instinctively play center or corner if open
        if random.random() < 0.40:
            preferred = [c for c in [4, 0, 2, 6, 8] if c in legal]
            if preferred:
                return random.choice(preferred)

        # Fallback to random legal move
        return random.choice(legal)

    # ---------------------------------------------------------
    # Level 2: Medium (Intermediate / Tactical Human)
    # ---------------------------------------------------------
    def _compute_level_2(self, legal: List[int]) -> int:
        """
        Level 2 - Intermediate:
        - Always takes an immediate win.
        - Blocks opponent's immediate win (85% consistency).
        - Prefers center, then corners, then edges.
        """
        my_sym = self.my_player_num if self.my_player_num in (1, 2) else 2
        opp_sym = 2 if my_sym == 1 else 1

        # 1. Immediate Win
        win_move = self._find_winning_cell(my_sym)
        if win_move is not None:
            return win_move

        # 2. Block Opponent Win (85% rate)
        block_move = self._find_winning_cell(opp_sym)
        if block_move is not None and random.random() < 0.85:
            return block_move

        # 3. Center preference
        if 4 in legal and random.random() < 0.75:
            return 4

        # 4. Corners preference
        corners = [c for c in [0, 2, 6, 8] if c in legal]
        if corners:
            return random.choice(corners)

        # 5. Edges / Any
        return random.choice(legal)

    # ---------------------------------------------------------
    # Level 3: Hard (Master / Optimal Minimax Search)
    # ---------------------------------------------------------
    def _compute_level_3(self, legal: List[int]) -> int:
        """
        Level 3 - Hard / Master:
        - Unbeatable Minimax search with depth weighting.
        - Guarantees win or tie.
        """
        my_sym = self.my_player_num if self.my_player_num in (1, 2) else 2
        opp_sym = 2 if my_sym == 1 else 1

        # If opening move on empty board, picking center or a corner is optimal
        if len(legal) == 9:
            return random.choice([4, 0, 2, 6, 8])

        best_score = -float("inf")
        best_move = legal[0]

        for move in legal:
            self.board[move] = my_sym
            score = self._minimax(depth=0, is_maximizing=False, my_sym=my_sym, opp_sym=opp_sym)
            self.board[move] = 0

            if score > best_score:
                best_score = score
                best_move = move

        return best_move

    def _minimax(self, depth: int, is_maximizing: bool, my_sym: int, opp_sym: int) -> int:
        if self._check_win(my_sym):
            return 10 - depth
        if self._check_win(opp_sym):
            return depth - 10

        legal = self.get_legal_moves()
        if not legal or depth >= 6:
            return 0  # Tie or max depth reached

        if is_maximizing:
            max_eval = -float("inf")
            for move in legal:
                self.board[move] = my_sym
                eval_score = self._minimax(depth + 1, False, my_sym, opp_sym)
                self.board[move] = 0
                max_eval = max(max_eval, eval_score)
            return max_eval
        else:
            min_eval = float("inf")
            for move in legal:
                self.board[move] = opp_sym
                eval_score = self._minimax(depth + 1, True, my_sym, opp_sym)
                self.board[move] = 0
                min_eval = min(min_eval, eval_score)
            return min_eval

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _find_winning_cell(self, symbol: int) -> Optional[int]:
        """Checks if placing symbol in any empty cell results in an immediate win."""
        for cell in self.get_legal_moves():
            self.board[cell] = symbol
            if self._check_win(symbol):
                self.board[cell] = 0
                return cell
            self.board[cell] = 0
        return None

    def _check_win(self, symbol: int) -> bool:
        """Checks whether the given symbol has 3 in a line."""
        for a, b, c in self.WIN_LINES:
            if self.board[a] == self.board[b] == self.board[c] == symbol:
                return True
        return False

    def build_move_command(self, move: int) -> dict:
        """Builds server command dict for TicTacToe."""
        return {
            "id": "SelectPeace",
            "data": move
        }

    def format_state(self) -> str:
        """Returns pretty formatted 3x3 board."""
        syms = {0: "·", 1: "X", 2: "O"}
        rows = [
            f"  {syms[self.board[0]]} | {syms[self.board[1]]} | {syms[self.board[2]]}",
            f"  {syms[self.board[3]]} | {syms[self.board[4]]} | {syms[self.board[5]]}",
            f"  {syms[self.board[6]]} | {syms[self.board[7]]} | {syms[self.board[8]]}",
        ]
        return "\n" + "\n  ---------\n".join(rows) + "\n"
