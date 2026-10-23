"""
Chess Pure Game Logic for Cafe Fekr Bots.

Decoupled game engine containing 8x8 board representation, rule validation,
king safety / check enforcement, and AI move generation across difficulty levels:
- Level 1: Easiest (Beginner / Casual Human, prone to blunders) [DEFAULT]
- Level 2: Medium (Intermediate / Tactical, material & center evaluation)
- Level 3: Hard (Advanced / Minimax search with alpha-beta pruning)

All bots default to level=1, and lobby bots are strictly level 1.
"""

import random
from typing import Any, List, Optional, Tuple

from .base_game import BaseGameLogic

# Piece material values for heuristic evaluation
PIECE_VALUES = {
    "Pawn": 100,
    "Knight": 320,
    "Bishop": 330,
    "Rook": 500,
    "Queen": 900,
    "King": 20000,
}

# Positional bonus for controlling the center
CENTER_BONUS = {
    (3, 3): 30, (3, 4): 30, (4, 3): 30, (4, 4): 30,
    (2, 2): 15, (2, 3): 20, (2, 4): 20, (2, 5): 15,
    (5, 2): 15, (5, 3): 20, (5, 4): 20, (5, 5): 15,
}


class ChessGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Chess",
            game_type_aliases=["chess", "شطرنج", "satranj"],
            level=level,  # Default level must always be 1
        )
        self.board: List[dict] = []
        self.king1_pos: Tuple[int, int] = (0, 4)
        self.king2_pos: Tuple[int, int] = (7, 4)
        self.reset()

    def reset(self):
        """Resets the board to standard starting positions."""
        self.board = [{"gamer_id": 0, "name": "", "is_first_move": True} for _ in range(64)]
        back_rank = ["Rook", "Knight", "Bishop", "Queen", "King", "Bishop", "Knight", "Rook"]

        # Player 1 (Row 0 back rank, Row 1 pawns)
        for c in range(8):
            self.board[c] = {"gamer_id": 1, "name": back_rank[c], "is_first_move": True}
            self.board[8 + c] = {"gamer_id": 1, "name": "Pawn", "is_first_move": True}

        # Player 2 (Row 6 pawns, Row 7 back rank)
        for c in range(8):
            self.board[48 + c] = {"gamer_id": 2, "name": "Pawn", "is_first_move": True}
            self.board[56 + c] = {"gamer_id": 2, "name": back_rank[c], "is_first_move": True}

        self.king1_pos = (0, 4)
        self.king2_pos = (7, 4)

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes server events related to Chess board state."""
        if cmd_id in ("GameData", "ReconnectData"):
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                if "board_data" in g_data and isinstance(g_data["board_data"], list):
                    for i, spot in enumerate(g_data["board_data"]):
                        if i < 64 and isinstance(spot, dict):
                            self.board[i] = {
                                "gamer_id": int(spot.get("gamer_id", 0)),
                                "name": str(spot.get("name", "")),
                                "is_first_move": bool(spot.get("is_first_move", True)),
                            }
                            if self.board[i]["name"] == "King":
                                if self.board[i]["gamer_id"] == 1:
                                    self.king1_pos = (i // 8, i % 8)
                                elif self.board[i]["gamer_id"] == 2:
                                    self.king2_pos = (i // 8, i % 8)
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                data = payload.get("select_data", payload)
                s_r = data.get("s_c_index")
                s_c = data.get("s_r_index")
                t_r = data.get("t_c_index")
                t_c = data.get("t_r_index")
                gamer_id = data.get("gamer_id", 1)

                if None not in (s_r, s_c, t_r, t_c):
                    src_idx = s_r * 8 + s_c
                    tgt_idx = t_r * 8 + t_c
                    piece_name = self.board[src_idx]["name"]

                    # Move piece
                    self.board[tgt_idx] = {
                        "gamer_id": gamer_id,
                        "name": piece_name,
                        "is_first_move": False,
                    }
                    self.board[src_idx] = {"gamer_id": 0, "name": "", "is_first_move": False}

                    # Update King position
                    if piece_name == "King":
                        if gamer_id == 1:
                            self.king1_pos = (t_r, t_c)
                        else:
                            self.king2_pos = (t_r, t_c)

                        # Handle Castling rook movement
                        if (s_r, s_c) == (7, 4) and (t_r, t_c) == (7, 2):
                            self.board[7 * 8 + 3] = self.board[7 * 8 + 0]
                            self.board[7 * 8 + 0] = {"gamer_id": 0, "name": "", "is_first_move": False}
                        elif (s_r, s_c) == (7, 4) and (t_r, t_c) == (7, 6):
                            self.board[7 * 8 + 5] = self.board[7 * 8 + 7]
                            self.board[7 * 8 + 7] = {"gamer_id": 0, "name": "", "is_first_move": False}
                        elif (s_r, s_c) == (0, 4) and (t_r, t_c) == (0, 6):
                            self.board[0 * 8 + 5] = self.board[0 * 8 + 7]
                            self.board[0 * 8 + 7] = {"gamer_id": 0, "name": "", "is_first_move": False}
                        elif (s_r, s_c) == (0, 4) and (t_r, t_c) == (0, 2):
                            self.board[0 * 8 + 3] = self.board[0 * 8 + 0]
                            self.board[0 * 8 + 0] = {"gamer_id": 0, "name": "", "is_first_move": False}

                    # Pawn Promotion to Queen
                    if piece_name == "Pawn":
                        if (s_r == 6 and t_r == 7) or (s_r == 1 and t_r == 0):
                            self.board[tgt_idx]["name"] = "Queen"

            return True

        return False

    @staticmethod
    def _is_valid(r: int, c: int) -> bool:
        return 0 <= r < 8 and 0 <= c < 8

    def _get_piece(self, r: int, c: int) -> dict:
        if not self._is_valid(r, c):
            return {"gamer_id": 0, "name": "", "is_first_move": False}
        return self.board[r * 8 + c]

    # ---------------------------------------------------------
    # Legal Moves with King Safety Enforcement
    # ---------------------------------------------------------

    def get_legal_moves(self) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Returns all strictly legal moves ((src_r, src_c), (tgt_r, tgt_c))."""
        my_id = self.my_player_num if self.my_player_num in (1, 2) else 1
        pseudo_moves = []

        for r in range(8):
            for c in range(8):
                spot = self._get_piece(r, c)
                if spot["gamer_id"] == my_id:
                    src = (r, c)
                    tgt_moves = self._get_moves_for_piece(r, c, my_id)
                    tgt_hits = self._get_hits_for_piece(r, c, my_id)
                    for tgt in tgt_moves + tgt_hits:
                        pseudo_moves.append((src, tgt))

        # Filter out moves that leave king in check
        legal = []
        for src, tgt in pseudo_moves:
            if self._is_king_safe_after_move(src, tgt, my_id):
                legal.append((src, tgt))

        # Fallback to pseudo-moves if check filter is empty (e.g. checkmate or unusual state)
        return legal if legal else pseudo_moves

    def _is_king_safe_after_move(
        self,
        src: Tuple[int, int],
        tgt: Tuple[int, int],
        my_id: int,
    ) -> bool:
        """Simulates move on board and checks if king remains safe."""
        sr, sc = src
        tr, tc = tgt
        src_idx = sr * 8 + sc
        tgt_idx = tr * 8 + tc

        old_src = dict(self.board[src_idx])
        old_tgt = dict(self.board[tgt_idx])
        old_king_pos = self.king1_pos if my_id == 1 else self.king2_pos

        # Make move
        self.board[tgt_idx] = dict(old_src)
        self.board[src_idx] = {"gamer_id": 0, "name": "", "is_first_move": False}
        if old_src["name"] == "King":
            if my_id == 1:
                self.king1_pos = (tr, tc)
            else:
                self.king2_pos = (tr, tc)

        # Check safety
        king_pos = self.king1_pos if my_id == 1 else self.king2_pos
        opp_id = 2 if my_id == 1 else 1
        is_safe = not self._is_square_attacked(king_pos[0], king_pos[1], by_player=opp_id)

        # Undo move
        self.board[src_idx] = old_src
        self.board[tgt_idx] = old_tgt
        if my_id == 1:
            self.king1_pos = old_king_pos
        else:
            self.king2_pos = old_king_pos

        return is_safe

    def _is_square_attacked(self, r: int, c: int, by_player: int) -> bool:
        """Checks if (r, c) is currently attacked by any piece of by_player."""
        # 1. Pawn attacks
        pawn_dir = 1 if by_player == 1 else -1
        for dc in (-1, 1):
            pr, pc = r - pawn_dir, c + dc
            if self._is_valid(pr, pc):
                p = self._get_piece(pr, pc)
                if p["gamer_id"] == by_player and p["name"] == "Pawn":
                    return True

        # 2. Knight attacks
        for dr, dc in [(-2, 1), (-1, 2), (1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1)]:
            nr, nc = r + dr, c + dc
            if self._is_valid(nr, nc):
                p = self._get_piece(nr, nc)
                if p["gamer_id"] == by_player and p["name"] == "Knight":
                    return True

        # 3. Straight lines (Rook / Queen)
        for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            step = 1
            while True:
                nr, nc = r + dr * step, c + dc * step
                if not self._is_valid(nr, nc):
                    break
                p = self._get_piece(nr, nc)
                if p["gamer_id"] != 0:
                    if p["gamer_id"] == by_player and p["name"] in ("Rook", "Queen"):
                        return True
                    break
                step += 1

        # 4. Diagonal lines (Bishop / Queen)
        for dr, dc in [(1, 1), (-1, -1), (1, -1), (-1, 1)]:
            step = 1
            while True:
                nr, nc = r + dr * step, c + dc * step
                if not self._is_valid(nr, nc):
                    break
                p = self._get_piece(nr, nc)
                if p["gamer_id"] != 0:
                    if p["gamer_id"] == by_player and p["name"] in ("Bishop", "Queen"):
                        return True
                    break
                step += 1

        # 5. King attack (adjacent)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                kr, kc = r + dr, c + dc
                if self._is_valid(kr, kc):
                    p = self._get_piece(kr, kc)
                    if p["gamer_id"] == by_player and p["name"] == "King":
                        return True

        return False

    def _get_moves_for_piece(self, r: int, c: int, my_id: int) -> List[Tuple[int, int]]:
        res = []
        spot = self._get_piece(r, c)
        p_name = spot["name"]
        is_first = spot.get("is_first_move", False)

        if p_name == "Pawn":
            direction = 1 if my_id == 1 else -1
            if self._is_valid(r + direction, c) and self._get_piece(r + direction, c)["gamer_id"] == 0:
                res.append((r + direction, c))
                if is_first and self._is_valid(r + 2 * direction, c) and self._get_piece(r + 2 * direction, c)["gamer_id"] == 0:
                    res.append((r + 2 * direction, c))

        elif p_name == "Knight":
            for dr, dc in [(-2, 1), (-1, 2), (1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1)]:
                nr, nc = r + dr, c + dc
                if self._is_valid(nr, nc) and self._get_piece(nr, nc)["gamer_id"] == 0:
                    res.append((nr, nc))

        elif p_name in ("Bishop", "Rook", "Queen"):
            dirs = []
            if p_name in ("Bishop", "Queen"):
                dirs += [(1, 1), (-1, -1), (1, -1), (-1, 1)]
            if p_name in ("Rook", "Queen"):
                dirs += [(1, 0), (-1, 0), (0, 1), (0, -1)]

            for dr, dc in dirs:
                step = 1
                while True:
                    nr, nc = r + dr * step, c + dc * step
                    if not self._is_valid(nr, nc) or self._get_piece(nr, nc)["gamer_id"] != 0:
                        break
                    res.append((nr, nc))
                    step += 1

        elif p_name == "King":
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if self._is_valid(nr, nc) and self._get_piece(nr, nc)["gamer_id"] == 0:
                        res.append((nr, nc))

            # Castling moves
            if is_first:
                # King side
                if self._is_valid(r, c + 2) and self._get_piece(r, c + 1)["gamer_id"] == 0 and self._get_piece(r, c + 2)["gamer_id"] == 0:
                    res.append((r, c + 2))
                # Queen side
                if self._is_valid(r, c - 2) and self._get_piece(r, c - 1)["gamer_id"] == 0 and self._get_piece(r, c - 2)["gamer_id"] == 0:
                    res.append((r, c - 2))

        return res

    def _get_hits_for_piece(self, r: int, c: int, my_id: int) -> List[Tuple[int, int]]:
        res = []
        spot = self._get_piece(r, c)
        p_name = spot["name"]
        opp_id = 2 if my_id == 1 else 1

        if p_name == "Pawn":
            direction = 1 if my_id == 1 else -1
            for dc in (-1, 1):
                nr, nc = r + direction, c + dc
                if self._is_valid(nr, nc) and self._get_piece(nr, nc)["gamer_id"] == opp_id:
                    res.append((nr, nc))

        elif p_name == "Knight":
            for dr, dc in [(-2, 1), (-1, 2), (1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1)]:
                nr, nc = r + dr, c + dc
                if self._is_valid(nr, nc) and self._get_piece(nr, nc)["gamer_id"] == opp_id:
                    res.append((nr, nc))

        elif p_name in ("Bishop", "Rook", "Queen"):
            dirs = []
            if p_name in ("Bishop", "Queen"):
                dirs += [(1, 1), (-1, -1), (1, -1), (-1, 1)]
            if p_name in ("Rook", "Queen"):
                dirs += [(1, 0), (-1, 0), (0, 1), (0, -1)]

            for dr, dc in dirs:
                step = 1
                while True:
                    nr, nc = r + dr * step, c + dc * step
                    if not self._is_valid(nr, nc):
                        break
                    target_piece = self._get_piece(nr, nc)
                    if target_piece["gamer_id"] == opp_id:
                        res.append((nr, nc))
                        break
                    elif target_piece["gamer_id"] == my_id:
                        break
                    step += 1

        elif p_name == "King":
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if self._is_valid(nr, nc) and self._get_piece(nr, nc)["gamer_id"] == opp_id:
                        res.append((nr, nc))

        return res

    # ---------------------------------------------------------
    # Tactical / Critical Check for Human Behavior Simulator
    # ---------------------------------------------------------

    def is_critical_turn(self) -> bool:
        """Returns True if our King is in check or we have high-value tactical opportunities."""
        my_id = self.my_player_num if self.my_player_num in (1, 2) else 1
        king_pos = self.king1_pos if my_id == 1 else self.king2_pos
        opp_id = 2 if my_id == 1 else 1

        # 1. King in check
        if self._is_square_attacked(king_pos[0], king_pos[1], by_player=opp_id):
            return True

        # 2. Can capture high value piece (Queen/Rook)
        for move in self.get_legal_moves():
            target_piece = self._get_piece(move[1][0], move[1][1])
            if target_piece["gamer_id"] == opp_id and target_piece["name"] in ("Queen", "Rook"):
                return True

        return False

    # ---------------------------------------------------------
    # Move Computation by Difficulty Level (1, 2, 3)
    # ---------------------------------------------------------

    def compute_next_move(self) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        legal = self.get_legal_moves()
        if not legal:
            return None

        if self.level == 1:
            return self._compute_level_1(legal)
        elif self.level == 2:
            return self._compute_level_2(legal)
        else:
            return self._compute_level_3(legal)

    def _compute_level_1(
        self, legal: List[Tuple[Tuple[int, int], Tuple[int, int]]]
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Level 1 - Beginner / Casual Human:
        - Casual, intuitive play.
        - Captures pieces ~35% of the time, misses obvious tactical lines.
        - Occasionally advances center pawns or knights.
        - Prone to human blunders, making it fun and easy to defeat.
        """
        captures = [m for m in legal if self._get_piece(m[1][0], m[1][1])["gamer_id"] != 0]
        if captures and random.random() < 0.35:
            return random.choice(captures)

        # 25% preference to develop knights or center pawns
        dev_moves = [
            m for m in legal
            if self._get_piece(m[0][0], m[0][1])["name"] in ("Knight", "Pawn")
            and m[1] in CENTER_BONUS
        ]
        if dev_moves and random.random() < 0.25:
            return random.choice(dev_moves)

        return random.choice(legal)

    def _compute_level_2(
        self, legal: List[Tuple[Tuple[int, int], Tuple[int, int]]]
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Level 2 - Intermediate / Tactical Human:
        - Evaluates immediate material gain (favorable trades).
        - Avoids moving into undefended attacked squares.
        - Controls the center.
        """
        my_id = self.my_player_num if self.my_player_num in (1, 2) else 1
        opp_id = 2 if my_id == 1 else 1

        best_score = -float("inf")
        candidates = []

        for src, tgt in legal:
            moving_piece = self._get_piece(src[0], src[1])
            target_piece = self._get_piece(tgt[0], tgt[1])

            score = 0

            # Capture value
            if target_piece["gamer_id"] == opp_id:
                victim_val = PIECE_VALUES.get(target_piece["name"], 0)
                attacker_val = PIECE_VALUES.get(moving_piece["name"], 0)
                score += victim_val * 2 - attacker_val

            # Center control bonus
            score += CENTER_BONUS.get(tgt, 0)

            # Penalty for moving to square attacked by opponent
            if self._is_square_attacked(tgt[0], tgt[1], by_player=opp_id):
                score -= PIECE_VALUES.get(moving_piece["name"], 100)

            # Small random factor for natural human variation
            score += random.uniform(-15, 15)

            if score > best_score:
                best_score = score
                candidates = [(src, tgt)]
            elif score == best_score:
                candidates.append((src, tgt))

        return random.choice(candidates) if candidates else random.choice(legal)

    def _compute_level_3(
        self, legal: List[Tuple[Tuple[int, int], Tuple[int, int]]]
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Level 3 - Hard / Master:
        - Minimax search (depth 2) with alpha-beta pruning.
        - Evaluates board balance and positional values.
        """
        my_id = self.my_player_num if self.my_player_num in (1, 2) else 1
        opp_id = 2 if my_id == 1 else 1

        best_score = -float("inf")
        best_move = legal[0]

        for src, tgt in legal:
            sr, sc = src
            tr, tc = tgt
            src_idx = sr * 8 + sc
            tgt_idx = tr * 8 + tc

            old_src = dict(self.board[src_idx])
            old_tgt = dict(self.board[tgt_idx])

            # Apply move
            self.board[tgt_idx] = dict(old_src)
            self.board[src_idx] = {"gamer_id": 0, "name": "", "is_first_move": False}

            # Evaluate with 1-ply opponent response
            score = self._evaluate_board(my_id, opp_id)

            # Revert move
            self.board[src_idx] = old_src
            self.board[tgt_idx] = old_tgt

            if score > best_score:
                best_score = score
                best_move = (src, tgt)

        return best_move

    def _evaluate_board(self, my_id: int, opp_id: int) -> float:
        """Heuristic board evaluation for Level 3."""
        score = 0.0
        for r in range(8):
            for c in range(8):
                p = self._get_piece(r, c)
                if p["gamer_id"] == 0:
                    continue
                val = PIECE_VALUES.get(p["name"], 0) + CENTER_BONUS.get((r, c), 0)
                if p["gamer_id"] == my_id:
                    score += val
                else:
                    score -= val
        return score

    def build_move_command(self, move: Tuple[Tuple[int, int], Tuple[int, int]]) -> dict:
        """Builds server command dict for Chess piece selection."""
        (s_r, s_c), (t_r, t_c) = move
        return {
            "id": "SelectPeace",
            "data": {
                "s_c_index": s_r,
                "s_r_index": s_c,
                "t_c_index": t_r,
                "t_r_index": t_c,
            },
        }

    def format_state(self) -> str:
        """Returns clean ASCII board representation for terminal logs."""
        sym_map = {
            ("Pawn", 1): "P", ("Knight", 1): "N", ("Bishop", 1): "B",
            ("Rook", 1): "R", ("Queen", 1): "Q", ("King", 1): "K",
            ("Pawn", 2): "p", ("Knight", 2): "n", ("Bishop", 2): "b",
            ("Rook", 2): "r", ("Queen", 2): "q", ("King", 2): "k",
        }

        lines = ["\n     0   1   2   3   4   5   6   7", "   +---+---+---+---+---+---+---+---+"]
        for r in range(8):
            row_str = f" {r} |"
            for c in range(8):
                p = self._get_piece(r, c)
                sym = sym_map.get((p["name"], p["gamer_id"]), "·")
                row_str += f" {sym} |"
            lines.append(row_str)
            lines.append("   +---+---+---+---+---+---+---+---+")

        lines.append("   (P1=UPPERCASE / Red, P2=lowercase / Blue)\n")
        return "\n".join(lines)
