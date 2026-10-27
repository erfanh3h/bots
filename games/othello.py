"""
Othello (اتللو) Pure Game Logic for Cafe Fekr Bots.

Decoupled game engine containing 8x8 board representation, exact rule validation
(matching kafehfekrbackend/Entities/Games/Othello/__init__.py 1:1), 8-directional
ray bracket checking, tile flipping, and AI move generation across difficulty levels:
- Level 1: Easiest (Beginner / Casual Human, prefers corners & good flips with human variance) [DEFAULT]
- Level 2: Medium (Intermediate / Positional & Tactical, avoids X/C-squares that gift corners)
- Level 3: Hard (Master / Alpha-Beta Minimax evaluating corner dominance, mobility, and disc count)

All bots default to level=1, and lobby bots are strictly level 1.
"""

import copy
import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


MOVE_DIRS: List[Tuple[int, int]] = [
    (-1, -1), (-1, 0), (-1, +1),
    (0, -1),           (0, +1),
    (+1, -1), (+1, 0), (+1, +1),
]

# Classic Othello Positional Weight Matrix (8x8)
# Corners (0,0), (0,7), (7,0), (7,7) are highest value (+120);
# X-squares (1,1), (1,6), (6,1), (6,6) and C-squares adjacent to empty corners carry heavy penalty.
POSITION_WEIGHTS: List[List[int]] = [
    [120, -24,  20,   8,   8,  20, -24, 120],
    [-24, -45,  -4,  -3,  -3,  -4, -45, -24],
    [ 20,  -4,  15,   4,   4,  15,  -4,  20],
    [  8,  -3,   4,   2,   2,   4,  -3,   8],
    [  8,  -3,   4,   2,   2,   4,  -3,   8],
    [ 20,  -4,  15,   4,   4,  15,  -4,  20],
    [-24, -45,  -4,  -3,  -3,  -4, -45, -24],
    [120, -24,  20,   8,   8,  20, -24, 120],
]

CORNERS: List[Tuple[int, int]] = [(0, 0), (0, 7), (7, 0), (7, 7)]


class OthelloGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Othello",
            game_type_aliases=[
                "othello",
                "reversi",
                "اتللو",
                "اوتلو",
            ],
            level=level,
        )
        # board[c_index][r_index] where index = c_index * 8 + r_index (0..63)
        self.board: List[List[int]] = [[0 for _ in range(8)] for _ in range(8)]
        self.player1_pawns: int = 30
        self.player2_pawns: int = 30
        self.player1_score: int = 2
        self.player2_score: int = 2
        self.current_turn: int = 1
        self.reset()

    def reset(self):
        """Resets the 8x8 board to standard Othello starting positions (matching backend 1:1)."""
        self.board = [[0 for _ in range(8)] for _ in range(8)]
        # Initial 4 center disks:
        # (3, 3) and (4, 4) -> Player 1 (Red)
        # (3, 4) and (4, 3) -> Player 2 (Blue)
        self.board[3][3] = 1
        self.board[4][4] = 1
        self.board[3][4] = 2
        self.board[4][3] = 2
        self.player1_pawns = 30
        self.player2_pawns = 30
        self.player1_score = 2
        self.player2_score = 2
        self.current_turn = 1

    # --- Coordinate & Rule Helpers (1:1 with kafehfekrbackend/Entities/Games/Othello/__init__.py) ---

    @staticmethod
    def is_valid_coord(row: int, col: int) -> bool:
        return 0 <= row < 8 and 0 <= col < 8

    def is_empty_place(
        self, move: Tuple[int, int], board_state: Optional[List[List[int]]] = None
    ) -> bool:
        b = board_state if board_state is not None else self.board
        return b[move[0]][move[1]] == 0

    def has_tile_to_flip(
        self,
        move: Tuple[int, int],
        direction: Tuple[int, int],
        gamer_id: int,
        board_state: Optional[List[List[int]]] = None,
    ) -> bool:
        """
        Determines whether placing `gamer_id` at `move = (c_index, r_index)`
        brackets at least 1 enemy tile along `direction = (dc, dr)`.
        Matches OthelloGameClass.has_tile_to_flip 1:1.
        """
        b = board_state if board_state is not None else self.board
        i = 1
        if self.is_valid_coord(move[0], move[1]):
            while True:
                row = move[0] + direction[0] * i
                col = move[1] + direction[1] * i
                if self.is_valid_coord(row, col):
                    if b[row][col] == 0:
                        return False
                    elif b[row][col] == gamer_id:
                        break
                    else:
                        i += 1
                else:
                    return False
        return i > 1

    def has_legal_move(
        self,
        move: Tuple[int, int],
        gamer_id: int,
        board_state: Optional[List[List[int]]] = None,
    ) -> bool:
        """Returns True if `move = (c_index, r_index)` flips tiles in at least one direction."""
        for direction in MOVE_DIRS:
            if self.has_tile_to_flip(move, direction, gamer_id, board_state):
                return True
        return False

    def is_legal_move(
        self,
        move: Tuple[int, int],
        gamer_id: int,
        board_state: Optional[List[List[int]]] = None,
    ) -> bool:
        """Returns True if `move = (c_index, r_index)` is empty and legal for `gamer_id`."""
        return (
            self.is_valid_coord(move[0], move[1])
            and self.is_empty_place(move, board_state)
            and self.has_legal_move(move, gamer_id, board_state)
        )

    def get_flipped_tiles(
        self,
        move: Tuple[int, int],
        gamer_id: int,
        board_state: Optional[List[List[int]]] = None,
    ) -> List[Tuple[int, int]]:
        """Returns list of all `(c_index, r_index)` enemy coordinates flipped by `move`."""
        b = board_state if board_state is not None else self.board
        flipped: List[Tuple[int, int]] = []
        if not self.is_legal_move(move, gamer_id, b):
            return flipped
        for direction in MOVE_DIRS:
            if self.has_tile_to_flip(move, direction, gamer_id, b):
                i = 1
                while True:
                    row = move[0] + direction[0] * i
                    col = move[1] + direction[1] * i
                    if b[row][col] == gamer_id:
                        break
                    flipped.append((row, col))
                    i += 1
        return flipped

    def flip_tiles(
        self,
        move: Tuple[int, int],
        gamer_id: int,
        board_state: Optional[List[List[int]]] = None,
    ) -> int:
        """
        Places `gamer_id` at `move = (c_index, r_index)` and flips all bracketed enemy tiles.
        Returns the number of flipped enemy tiles.
        """
        b = board_state if board_state is not None else self.board
        if not self.is_legal_move(move, gamer_id, b):
            return 0
        flipped = self.get_flipped_tiles(move, gamer_id, b)
        b[move[0]][move[1]] = gamer_id
        for row, col in flipped:
            b[row][col] = gamer_id

        if board_state is None:
            self._recalculate_scores()
        return len(flipped)

    def _recalculate_scores(self) -> None:
        s1 = 0
        s2 = 0
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == 1:
                    s1 += 1
                elif self.board[r][c] == 2:
                    s2 += 1
        self.player1_score = s1
        self.player2_score = s2

    # --- Server Command Handling ---

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes server events for Othello."""
        if cmd_id in ("GameData", "ReconnectData"):
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                b_list = g_data.get("board", [])
                if isinstance(b_list, list) and len(b_list) == 64:
                    for idx, val in enumerate(b_list):
                        c_idx = idx // 8
                        r_idx = idx % 8
                        if isinstance(val, dict):
                            occ = int(val.get("pawn_gamer_id", val.get("gamer_id", 0)))
                        else:
                            occ = int(val) if isinstance(val, (int, float)) else 0
                        self.board[c_idx][r_idx] = occ

                pawns = g_data.get("pawns_count")
                if isinstance(pawns, list) and len(pawns) >= 2:
                    self.player1_pawns = int(pawns[0])
                    self.player2_pawns = int(pawns[1])

                scores = g_data.get("scores")
                if isinstance(scores, list) and len(scores) >= 2:
                    self.player1_score = int(scores[0])
                    self.player2_score = int(scores[1])
                else:
                    self._recalculate_scores()
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                sdata = payload.get("select_data", payload)
                c_idx = sdata.get("c_index")
                r_idx = sdata.get("r_index")
                gamer_id = sdata.get("gamer_id", payload.get("gamer_id", 1))
                if c_idx is not None and r_idx is not None:
                    self.flip_tiles((int(c_idx), int(r_idx)), int(gamer_id))
                scores = payload.get("scores")
                if isinstance(scores, list) and len(scores) >= 2:
                    self.player1_score = int(scores[0])
                    self.player2_score = int(scores[1])
            return True

        elif cmd_id == "CurrentTurn":
            turn = payload if isinstance(payload, int) else (
                payload.get("current_turn", payload.get("turn", 1))
                if isinstance(payload, dict) else 1
            )
            if int(turn) == 1:
                self.player1_pawns = max(0, self.player1_pawns - 1)
            elif int(turn) == 2:
                self.player2_pawns = max(0, self.player2_pawns - 1)
            return True

        return False

    # --- Move Generation & AI Decision Engine ---

    def get_legal_moves(
        self,
        gamer_id: Optional[int] = None,
        board_state: Optional[List[List[int]]] = None,
    ) -> List[Tuple[int, int]]:
        """Returns all legal `(c_index, r_index)` moves for `gamer_id`."""
        gid = gamer_id if gamer_id is not None else (self.my_player_num or 1)
        b = board_state if board_state is not None else self.board
        moves: List[Tuple[int, int]] = []
        for c_idx in range(8):
            for r_idx in range(8):
                if self.is_legal_move((c_idx, r_idx), gid, b):
                    moves.append((c_idx, r_idx))
        return moves

    def is_critical_turn(self) -> bool:
        """Returns True if a corner is available or >= 5 tiles can be flipped in a single move."""
        my_id = self.my_player_num or 1
        legal = self.get_legal_moves(my_id)
        for mv in legal:
            if mv in CORNERS:
                return True
            if len(self.get_flipped_tiles(mv, my_id)) >= 5:
                return True
        return False

    def compute_next_move(self) -> Optional[Tuple[int, int]]:
        """Selects the best `(c_index, r_index)` move according to `self.level`."""
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
        - Takes an open corner 75% of the time if available.
        - Otherwise scores moves by flipped count + light positional preference + casual noise.
        """
        corner_moves = [m for m in legal if m in CORNERS]
        if corner_moves and random.random() < 0.75:
            return random.choice(corner_moves)

        scored: List[Tuple[float, Tuple[int, int]]] = []
        for mv in legal:
            flips = len(self.get_flipped_tiles(mv, my_id))
            pos_w = POSITION_WEIGHTS[mv[0]][mv[1]] * 0.35
            noise = random.uniform(-12.0, 12.0)
            scored.append((flips * 4.0 + pos_w + noise, mv))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _move_level_2(
        self, legal: List[Tuple[int, int]], my_id: int, opp_id: int
    ) -> Tuple[int, int]:
        """
        Level 2 (Intermediate / Tactical Human):
        - Always takes corners.
        - Avoids moves that immediately give the opponent a corner.
        - Balances positional weights and flipped tiles.
        """
        corner_moves = [m for m in legal if m in CORNERS]
        if corner_moves:
            return random.choice(corner_moves)

        best_score = -float("inf")
        best_move = legal[0]

        for mv in legal:
            b_copy = [row[:] for row in self.board]
            flips = self.flip_tiles(mv, my_id, b_copy)
            pos_w = float(POSITION_WEIGHTS[mv[0]][mv[1]])

            # Check if opponent gets a corner next turn
            opp_moves = self.get_legal_moves(opp_id, b_copy)
            gifts_corner = any(om in CORNERS for om in opp_moves)
            penalty = -95.0 if gifts_corner else 0.0

            score = pos_w + flips * 3.5 + penalty + random.uniform(-3.0, 3.0)
            if score > best_score:
                best_score = score
                best_move = mv

        return best_move

    def _move_level_3(
        self, legal: List[Tuple[int, int]], my_id: int, opp_id: int
    ) -> Tuple[int, int]:
        """
        Level 3 (Master / Alpha-Beta Minimax):
        - 3-ply Alpha-Beta search with positional weights, corner control, and mobility.
        """
        best_score = -float("inf")
        best_move = legal[0]
        alpha = -float("inf")
        beta = float("inf")

        ordered = sorted(
            legal,
            key=lambda m: POSITION_WEIGHTS[m[0]][m[1]],
            reverse=True,
        )

        for mv in ordered:
            b_copy = [row[:] for row in self.board]
            self.flip_tiles(mv, my_id, b_copy)
            score = self._alphabeta(b_copy, 2, alpha, beta, False, my_id, opp_id)
            if score > best_score:
                best_score = score
                best_move = mv
            alpha = max(alpha, best_score)

        return best_move

    def _alphabeta(
        self,
        board_state: List[List[int]],
        depth: int,
        alpha: float,
        beta: float,
        is_maximizing: bool,
        my_id: int,
        opp_id: int,
    ) -> float:
        cur_player = my_id if is_maximizing else opp_id
        legal = self.get_legal_moves(cur_player, board_state)

        if depth == 0 or not legal:
            return self._evaluate_board(board_state, my_id, opp_id)

        if is_maximizing:
            value = -float("inf")
            for mv in legal:
                b_next = [row[:] for row in board_state]
                self.flip_tiles(mv, my_id, b_next)
                value = max(
                    value,
                    self._alphabeta(b_next, depth - 1, alpha, beta, False, my_id, opp_id),
                )
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = float("inf")
            for mv in legal:
                b_next = [row[:] for row in board_state]
                self.flip_tiles(mv, opp_id, b_next)
                value = min(
                    value,
                    self._alphabeta(b_next, depth - 1, alpha, beta, True, my_id, opp_id),
                )
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value

    def _evaluate_board(
        self, board_state: List[List[int]], my_id: int, opp_id: int
    ) -> float:
        score = 0.0
        my_tiles = 0
        opp_tiles = 0

        for c in range(8):
            for r in range(8):
                occ = board_state[c][r]
                if occ == my_id:
                    score += POSITION_WEIGHTS[c][r]
                    my_tiles += 1
                elif occ == opp_id:
                    score -= POSITION_WEIGHTS[c][r]
                    opp_tiles += 1

        my_mob = len(self.get_legal_moves(my_id, board_state))
        opp_mob = len(self.get_legal_moves(opp_id, board_state))
        score += (my_mob - opp_mob) * 6.5
        score += (my_tiles - opp_tiles) * 1.5
        return score

    def build_move_command(self, move: Tuple[int, int]) -> dict:
        """
        Builds server command dict for Othello.
        Matches kafehfekrbackend/Controllers/GameSession/othello_game_session.py:
        data['id'] == commands.Select_Peace ('SelectPeace'),
        data['data'] == {'c_index': column_index, 'r_index': row_index}
        """
        return {
            "id": "SelectPeace",
            "data": {
                "c_index": int(move[0]),
                "r_index": int(move[1]),
            },
        }

    def format_state(self) -> str:
        """Returns readable 8x8 ASCII Othello board for terminal logs."""
        syms = {0: "·", 1: "R", 2: "B"}
        lines = [
            f"\n   Othello | Score R:{self.player1_score} - B:{self.player2_score} | Pawns Left R:{self.player1_pawns} B:{self.player2_pawns}",
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
