"""
Checkers Pure Game Logic for Cafe Fekr Bots.

Decoupled game engine containing 8x8 board representation, exact rule validation
(matching kafehfekrbackend/Entities/Games/Checkers/__init__.py 1:1), single & multi-jump
capture chaining, Super Pawn (King) promotion, and AI move generation across difficulty levels:
- Level 1: Easiest (Beginner / Casual Human, prefers captures/promotions with human variance) [DEFAULT]
- Level 2: Medium (Intermediate / Tactical, evaluates multi-jumps, captures, promotions, and safety)
- Level 3: Hard (Advanced / 2-ply lookahead evaluating material, King dominance, and board control)

All bots default to level=1, and lobby bots are strictly level 1.
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


PAWN_VALUE = 100
SUPER_PAWN_VALUE = 280

# Center & safe edge positional bonuses (c_index, r_index)
POSITION_BONUS = {
    (3, 2): 18, (3, 4): 22, (3, 6): 16,
    (4, 1): 16, (4, 3): 22, (4, 5): 18,
    (2, 1): 12, (2, 3): 15, (2, 5): 15, (2, 7): 14,
    (5, 0): 14, (5, 2): 15, (5, 4): 15, (5, 6): 12,
}


class CheckersGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Checkers",
            game_type_aliases=["checkers", "چکرز", "dama", "draughts"],
            level=level,
        )
        # 64 spots indexed by c_index * 8 + r_index (c_index = row 0..7, r_index = col 0..7)
        self.board: List[Dict[str, Any]] = []
        self.player1_pawns: int = 12
        self.player2_pawns: int = 12
        self.reset()

    def reset(self):
        """Resets the board to standard Checkers starting positions (matching backend)."""
        self.board = [
            {"pawn_gamer_id": 0, "is_super_pawn": False} for _ in range(64)
        ]
        p1_coords = [
            (0, 0), (0, 2), (0, 4), (0, 6),
            (1, 1), (1, 3), (1, 5), (1, 7),
            (2, 0), (2, 2), (2, 4), (2, 6),
        ]
        for c_idx, r_idx in p1_coords:
            self.board[c_idx * 8 + r_idx] = {
                "pawn_gamer_id": 1,
                "is_super_pawn": False,
            }

        p2_coords = [
            (5, 1), (5, 3), (5, 5), (5, 7),
            (6, 0), (6, 2), (6, 4), (6, 6),
            (7, 1), (7, 3), (7, 5), (7, 7),
        ]
        for c_idx, r_idx in p2_coords:
            self.board[c_idx * 8 + r_idx] = {
                "pawn_gamer_id": 2,
                "is_super_pawn": False,
            }

        self.player1_pawns = 12
        self.player2_pawns = 12

    # --- Board Coordinate & State Helpers (1:1 with kafehfekrbackend) ---

    @staticmethod
    def _is_valid_coordinate(col: int, row: int) -> bool:
        return 0 <= row < 8 and 0 <= col < 8

    def _get_spot(
        self, c_index: int, r_index: int, board_state: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        b = board_state if board_state is not None else self.board
        return b[c_index * 8 + r_index]

    def _is_target_peace_empty(
        self, r_index: int, c_index: int, board_state: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        return self._get_spot(c_index, r_index, board_state)["pawn_gamer_id"] == 0

    def _is_target_peace_enemy(
        self,
        r_index: int,
        c_index: int,
        gamer_id: int,
        board_state: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        occ = self._get_spot(c_index, r_index, board_state)["pawn_gamer_id"]
        return occ != 0 and occ != gamer_id

    @staticmethod
    def _check_is_last_peace(c_index: int, gamer_id: int) -> bool:
        if gamer_id == 1:
            return c_index == 7
        return c_index == 0

    # --- Exact Direction & Multi-Jump Move Generation (1:1 with Backend) ---

    def _get_direction1_right_pawn_move(
        self,
        r_index: int,
        c_index: int,
        gamer_id: int,
        check_move_list: list,
        is_multi_move: bool = False,
        board_state: Optional[List[Dict[str, Any]]] = None,
    ):
        new_r_index = r_index - 1
        new_c_index = c_index + 1
        if new_r_index < 0 or new_r_index > 7 or new_c_index < 0 or new_c_index > 7:
            return None, None, None, False
        if self._is_target_peace_empty(new_r_index, new_c_index, board_state) and not is_multi_move:
            return (new_r_index, new_c_index), None, None, False
        if self._is_target_peace_enemy(new_r_index, new_c_index, gamer_id, board_state):
            new_r1_index = new_r_index - 1
            new_c1_index = new_c_index + 1
            if self._is_valid_coordinate(new_c1_index, new_r1_index) and self._is_target_peace_empty(
                new_r1_index, new_c1_index, board_state
            ):
                check_move_list.append(
                    ((new_r1_index, new_c1_index), (new_r_index, new_c_index), (r_index, c_index), True)
                )
        return None, None, None, False

    def _get_direction1_left_pawn_move(
        self,
        r_index: int,
        c_index: int,
        gamer_id: int,
        check_move_list: list,
        is_multi_move: bool = False,
        board_state: Optional[List[Dict[str, Any]]] = None,
    ):
        new_r_index = r_index + 1
        new_c_index = c_index + 1
        if new_r_index < 0 or new_r_index > 7 or new_c_index < 0 or new_c_index > 7:
            return None, None, None, False
        if self._is_target_peace_empty(new_r_index, new_c_index, board_state) and not is_multi_move:
            return (new_r_index, new_c_index), None, None, False
        if self._is_target_peace_enemy(new_r_index, new_c_index, gamer_id, board_state):
            new_r1_index = new_r_index + 1
            new_c1_index = new_c_index + 1
            if self._is_valid_coordinate(new_c1_index, new_r1_index) and self._is_target_peace_empty(
                new_r1_index, new_c1_index, board_state
            ):
                check_move_list.append(
                    ((new_r1_index, new_c1_index), (new_r_index, new_c_index), (r_index, c_index), True)
                )
        return None, None, None, False

    def _get_direction2_right_pawn_move(
        self,
        r_index: int,
        c_index: int,
        gamer_id: int,
        check_move_list: list,
        is_multi_move: bool = False,
        board_state: Optional[List[Dict[str, Any]]] = None,
    ):
        new_r_index = r_index + 1
        new_c_index = c_index - 1
        if new_r_index < 0 or new_r_index > 7 or new_c_index < 0 or new_c_index > 7:
            return None, None, None, False
        if self._is_target_peace_empty(new_r_index, new_c_index, board_state) and not is_multi_move:
            return (new_r_index, new_c_index), None, None, False
        if self._is_target_peace_enemy(new_r_index, new_c_index, gamer_id, board_state):
            new_r1_index = new_r_index + 1
            new_c1_index = new_c_index - 1
            if self._is_valid_coordinate(new_c1_index, new_r1_index) and self._is_target_peace_empty(
                new_r1_index, new_c1_index, board_state
            ):
                check_move_list.append(
                    ((new_r1_index, new_c1_index), (new_r_index, new_c_index), (r_index, c_index), True)
                )
        return None, None, None, False

    def _get_direction2_left_pawn_move(
        self,
        r_index: int,
        c_index: int,
        gamer_id: int,
        check_move_list: list,
        is_multi_move: bool = False,
        board_state: Optional[List[Dict[str, Any]]] = None,
    ):
        new_r_index = r_index - 1
        new_c_index = c_index - 1
        if new_r_index < 0 or new_r_index > 7 or new_c_index < 0 or new_c_index > 7:
            return None, None, None, False
        if self._is_target_peace_empty(new_r_index, new_c_index, board_state) and not is_multi_move:
            return (new_r_index, new_c_index), None, None, False
        if self._is_target_peace_enemy(new_r_index, new_c_index, gamer_id, board_state):
            new_r1_index = new_r_index - 1
            new_c1_index = new_c_index - 1
            if self._is_valid_coordinate(new_c1_index, new_r1_index) and self._is_target_peace_empty(
                new_r1_index, new_c1_index, board_state
            ):
                check_move_list.append(
                    ((new_r1_index, new_c1_index), (new_r_index, new_c_index), (r_index, c_index), True)
                )
        return None, None, None, False

    def get_possible_moves_of_peace(
        self,
        r_index: int,
        c_index: int,
        gamer_id: int,
        board_state: Optional[List[Dict[str, Any]]] = None,
    ) -> List[List[Any]]:
        check_move_list: list = []

        def get_direction1_moves(r_idx: int, c_idx: int, g_id: int):
            temp_list = []
            right_res = self._get_direction1_right_pawn_move(
                r_idx, c_idx, g_id, check_move_list, False, board_state
            )
            left_res = self._get_direction1_left_pawn_move(
                r_idx, c_idx, g_id, check_move_list, False, board_state
            )
            temp_list.append([right_res[0], right_res[1], right_res[2]])
            temp_list.append([left_res[0], left_res[1], left_res[2]])
            safety = 0
            while len(check_move_list) != 0 and safety < 64:
                safety += 1
                indexes, removed_peace, source_start, is_multi_move = check_move_list[0]
                temp_list.append([indexes, removed_peace, source_start])
                if removed_peace is not None and indexes is not None:
                    r_next = self._get_direction1_right_pawn_move(
                        indexes[0], indexes[1], g_id, check_move_list, is_multi_move, board_state
                    )
                    l_next = self._get_direction1_left_pawn_move(
                        indexes[0], indexes[1], g_id, check_move_list, is_multi_move, board_state
                    )
                    check_move_list.append(r_next)
                    check_move_list.append(l_next)
                del check_move_list[0]
            return temp_list

        def get_direction2_moves(r_idx: int, c_idx: int, g_id: int):
            temp_list = []
            right_res = self._get_direction2_right_pawn_move(
                r_idx, c_idx, g_id, check_move_list, False, board_state
            )
            left_res = self._get_direction2_left_pawn_move(
                r_idx, c_idx, g_id, check_move_list, False, board_state
            )
            temp_list.append([right_res[0], right_res[1], right_res[2]])
            temp_list.append([left_res[0], left_res[1], left_res[2]])
            safety = 0
            while len(check_move_list) != 0 and safety < 64:
                safety += 1
                indexes, removed_peace, source_start, is_multi_move = check_move_list[0]
                temp_list.append([indexes, removed_peace, source_start])
                if removed_peace is not None and indexes is not None:
                    r_next = self._get_direction2_right_pawn_move(
                        indexes[0], indexes[1], g_id, check_move_list, is_multi_move, board_state
                    )
                    l_next = self._get_direction2_left_pawn_move(
                        indexes[0], indexes[1], g_id, check_move_list, is_multi_move, board_state
                    )
                    check_move_list.append(r_next)
                    check_move_list.append(l_next)
                del check_move_list[0]
            return temp_list

        moves = []
        spot = self._get_spot(c_index, r_index, board_state)
        if spot["is_super_pawn"]:
            temp_move_list = get_direction1_moves(r_index, c_index, gamer_id)
            temp_move_list += get_direction2_moves(r_index, c_index, gamer_id)
        elif gamer_id == 1:
            temp_move_list = get_direction1_moves(r_index, c_index, gamer_id)
        else:
            temp_move_list = get_direction2_moves(r_index, c_index, gamer_id)

        for move in temp_move_list:
            if move[0] is not None:
                moves.append(move)
        return moves

    def apply_move_to_board(
        self,
        s_c_index: int,
        s_r_index: int,
        t_c_index: int,
        t_r_index: int,
        gamer_id: int,
        board_state: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Applies a move and its single/multi-jump captures to board_state (or self.board).
        Returns the number of enemy pieces captured by this move.
        """
        b = board_state if board_state is not None else self.board
        moves = self.get_possible_moves_of_peace(s_r_index, s_c_index, gamer_id, b)
        captured_count = 0

        for move_data in moves:
            if move_data[0] == (t_r_index, t_c_index):
                was_super = b[s_c_index * 8 + s_r_index]["is_super_pawn"]
                becomes_super = was_super or self._check_is_last_peace(t_c_index, gamer_id)
                b[t_c_index * 8 + t_r_index] = {
                    "pawn_gamer_id": gamer_id,
                    "is_super_pawn": becomes_super,
                }
                b[s_c_index * 8 + s_r_index] = {
                    "pawn_gamer_id": 0,
                    "is_super_pawn": False,
                }

                if move_data[1] is not None:
                    remove_point = move_data[1]
                    source_peace_index = move_data[2]
                    safety = 0
                    while remove_point is not None and safety < 16:
                        safety += 1
                        rem_r, rem_c = remove_point[0], remove_point[1]
                        b[rem_c * 8 + rem_r] = {
                            "pawn_gamer_id": 0,
                            "is_super_pawn": False,
                        }
                        captured_count += 1
                        remove_point = None
                        if source_peace_index is not None and source_peace_index != (s_r_index, s_c_index):
                            for raw_move_data in moves:
                                if raw_move_data[0] == (source_peace_index[0], source_peace_index[1]):
                                    source_peace_index = raw_move_data[2]
                                    remove_point = raw_move_data[1]
                                    break
                break

        if board_state is None:
            self.player1_pawns = sum(1 for s in self.board if s["pawn_gamer_id"] == 1)
            self.player2_pawns = sum(1 for s in self.board if s["pawn_gamer_id"] == 2)

        return captured_count

    # --- Server Command Handling ---

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes server events related to Checkers board state."""
        if cmd_id in ("GameData", "ReconnectData"):
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                b_list = g_data.get("board", [])
                if isinstance(b_list, list) and len(b_list) == 64:
                    for i, spot in enumerate(b_list):
                        if isinstance(spot, dict):
                            self.board[i] = {
                                "pawn_gamer_id": int(
                                    spot.get("pawn_gamer_id", spot.get("gamer_id", 0))
                                ),
                                "is_super_pawn": bool(spot.get("is_super_pawn", False)),
                            }
                    self.player1_pawns = sum(1 for s in self.board if s["pawn_gamer_id"] == 1)
                    self.player2_pawns = sum(1 for s in self.board if s["pawn_gamer_id"] == 2)
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                data = payload.get("select_data", payload)
                s_c = data.get("s_c_index")
                s_r = data.get("s_r_index")
                t_c = data.get("t_c_index")
                t_r = data.get("t_r_index")
                gamer_id = data.get("gamer_id", 1)
                if None not in (s_c, s_r, t_c, t_r):
                    self.apply_move_to_board(
                        int(s_c), int(s_r), int(t_c), int(t_r), int(gamer_id)
                    )
            return True

        return False

    # --- Move Enumeration & AI Decision Engine ---

    def _get_detailed_moves_for_player(
        self, player_id: int, board_state: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns all valid moves for player_id with full metadata:
        {"src": (s_c, s_r), "tgt": (t_c, t_r), "captures": int, "promotes": bool}
        """
        b = board_state if board_state is not None else self.board
        detailed: List[Dict[str, Any]] = []

        for idx in range(64):
            spot = b[idx]
            if spot["pawn_gamer_id"] != player_id:
                continue
            s_c = idx // 8
            s_r = idx % 8
            was_super = spot["is_super_pawn"]
            raw_moves = self.get_possible_moves_of_peace(s_r, s_c, player_id, b)

            seen_targets = set()
            for m in raw_moves:
                t_r, t_c = m[0]
                if (t_c, t_r) in seen_targets:
                    continue
                seen_targets.add((t_c, t_r))

                # Count how many enemy pieces this path captures
                cap_count = 0
                if m[1] is not None:
                    rem_pt = m[1]
                    src_pt = m[2]
                    safety = 0
                    while rem_pt is not None and safety < 16:
                        safety += 1
                        cap_count += 1
                        rem_pt = None
                        if src_pt is not None and src_pt != (s_r, s_c):
                            for raw_m in raw_moves:
                                if raw_m[0] == (src_pt[0], src_pt[1]):
                                    src_pt = raw_m[2]
                                    rem_pt = raw_m[1]
                                    break

                promotes = (not was_super) and self._check_is_last_peace(t_c, player_id)
                detailed.append(
                    {
                        "src": (s_c, s_r),
                        "tgt": (t_c, t_r),
                        "captures": cap_count,
                        "promotes": promotes,
                    }
                )
        return detailed

    def get_legal_moves(self) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Returns list of valid ((s_c_index, s_r_index), (t_c_index, t_r_index)) moves."""
        my_id = self.my_player_num if self.my_player_num in (1, 2) else 1
        detailed = self._get_detailed_moves_for_player(my_id)
        return [(m["src"], m["tgt"]) for m in detailed]

    def is_critical_turn(self) -> bool:
        """Returns True if a capture or King promotion is available."""
        my_id = self.my_player_num if self.my_player_num in (1, 2) else 1
        detailed = self._get_detailed_moves_for_player(my_id)
        return any(m["captures"] > 0 or m["promotes"] for m in detailed)

    def compute_next_move(self) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        my_id = self.my_player_num if self.my_player_num in (1, 2) else 1
        detailed = self._get_detailed_moves_for_player(my_id)
        if not detailed:
            return None

        if self.level == 1:
            return self._compute_level_1(detailed, my_id)
        elif self.level == 2:
            return self._compute_level_2(detailed, my_id)
        else:
            return self._compute_level_3(detailed, my_id)

    def _compute_level_1(
        self, detailed: List[Dict[str, Any]], my_id: int
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Level 1 - Beginner / Casual Human [DEFAULT]:
        - 75% chance to take an available capture (especially multi-jumps) or promotion.
        - Otherwise plays a natural forward move.
        """
        captures = [m for m in detailed if m["captures"] > 0]
        if captures and random.random() < 0.78:
            captures.sort(key=lambda x: x["captures"], reverse=True)
            best_cap = captures[0]["captures"]
            top_caps = [m for m in captures if m["captures"] == best_cap]
            chosen = random.choice(top_caps)
            return (chosen["src"], chosen["tgt"])

        promotions = [m for m in detailed if m["promotes"]]
        if promotions and random.random() < 0.80:
            chosen = random.choice(promotions)
            return (chosen["src"], chosen["tgt"])

        chosen = random.choice(detailed)
        return (chosen["src"], chosen["tgt"])

    def _compute_level_2(
        self, detailed: List[Dict[str, Any]], my_id: int
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Level 2 - Medium / Tactical:
        - Evaluates captures, King promotions, center control, and avoids jumping into immediate recapture.
        """
        opp_id = 2 if my_id == 1 else 1
        best_score = -float("inf")
        best_move = (detailed[0]["src"], detailed[0]["tgt"])

        for m in detailed:
            s_c, s_r = m["src"]
            t_c, t_r = m["tgt"]
            score = 0.0
            score += m["captures"] * 180.0
            if m["promotes"]:
                score += 160.0
            score += POSITION_BONUS.get((t_c, t_r), 0)

            # Simulate move to check if opponent can immediately capture us
            sim_board = [dict(s) for s in self.board]
            self.apply_move_to_board(s_c, s_r, t_c, t_r, my_id, sim_board)
            opp_moves = self._get_detailed_moves_for_player(opp_id, sim_board)
            max_opp_cap = max((om["captures"] for om in opp_moves), default=0)
            score -= max_opp_cap * 130.0
            score += random.uniform(-10.0, 10.0)

            if score > best_score:
                best_score = score
                best_move = (m["src"], m["tgt"])

        return best_move

    def _compute_level_3(
        self, detailed: List[Dict[str, Any]], my_id: int
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Level 3 - Hard / Master:
        - 2-ply minimax lookahead evaluating material balance, Super Pawns, and opponent counter-captures.
        """
        opp_id = 2 if my_id == 1 else 1
        best_score = -float("inf")
        best_move = (detailed[0]["src"], detailed[0]["tgt"])

        for m in detailed:
            s_c, s_r = m["src"]
            t_c, t_r = m["tgt"]
            sim_board = [dict(s) for s in self.board]
            self.apply_move_to_board(s_c, s_r, t_c, t_r, my_id, sim_board)

            opp_moves = self._get_detailed_moves_for_player(opp_id, sim_board)
            if not opp_moves:
                return (m["src"], m["tgt"])

            worst_reply_score = float("inf")
            for om in opp_moves:
                os_c, os_r = om["src"]
                ot_c, ot_r = om["tgt"]
                reply_board = [dict(s) for s in sim_board]
                self.apply_move_to_board(os_c, os_r, ot_c, ot_r, opp_id, reply_board)
                eval_sc = self._evaluate_board(reply_board, my_id, opp_id)
                if eval_sc < worst_reply_score:
                    worst_reply_score = eval_sc

            if worst_reply_score > best_score:
                best_score = worst_reply_score
                best_move = (m["src"], m["tgt"])

        return best_move

    def _evaluate_board(
        self, board_state: List[Dict[str, Any]], my_id: int, opp_id: int
    ) -> float:
        score = 0.0
        for idx, spot in enumerate(board_state):
            g_id = spot["pawn_gamer_id"]
            if g_id == 0:
                continue
            c_idx = idx // 8
            r_idx = idx % 8
            val = SUPER_PAWN_VALUE if spot["is_super_pawn"] else PAWN_VALUE
            val += POSITION_BONUS.get((c_idx, r_idx), 0)
            # Advancement bonus for regular pawns
            if not spot["is_super_pawn"]:
                val += (c_idx * 6) if g_id == 1 else ((7 - c_idx) * 6)
            if g_id == my_id:
                score += val
            else:
                score -= val
        return score

    def build_move_command(
        self, move: Tuple[Tuple[int, int], Tuple[int, int]]
    ) -> dict:
        """Builds server command dict for Checkers piece selection."""
        (s_c, s_r), (t_c, t_r) = move
        return {
            "id": "SelectPeace",
            "data": {
                "s_c_index": s_c,
                "s_r_index": s_r,
                "t_c_index": t_c,
                "t_r_index": t_r,
            },
        }

    def format_state(self) -> str:
        """Returns clean ASCII board representation for terminal logs."""
        lines = [
            f"\n   Checkers | P1 (Red): {self.player1_pawns} | P2 (Blue): {self.player2_pawns}",
            "     0   1   2   3   4   5   6   7",
            "   +---+---+---+---+---+---+---+---+",
        ]
        for c_idx in range(8):
            row_str = f" {c_idx} |"
            for r_idx in range(8):
                spot = self.board[c_idx * 8 + r_idx]
                g_id = spot["pawn_gamer_id"]
                is_sup = spot["is_super_pawn"]
                if g_id == 1:
                    sym = "R" if is_sup else "r"
                elif g_id == 2:
                    sym = "B" if is_sup else "b"
                else:
                    sym = "·" if (c_idx + r_idx) % 2 == 0 else " "
                row_str += f" {sym} |"
            lines.append(row_str)
            lines.append("   +---+---+---+---+---+---+---+---+")
        lines.append("   (r/R = P1 Red Pawn/King, b/B = P2 Blue Pawn/King)\n")
        return "\n".join(lines)
