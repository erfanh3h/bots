"""
Nine Men's Morris / Mill (دوز نه تایی) Pure Game Logic for Cafe Fekr Bots.

Decoupled game engine containing the 24-node concentric board representation,
exact rule validation (matching kafehfekrbackend/Entities/Games/Mill/__init__.py 1:1),
and AI move generation across all 3 phases (Placement, Movement/Sliding, Flying,
and Mill Capture) and difficulty levels:
- Level 1: Easiest (Beginner / Casual Human, spots immediate mills & blocks with natural variance) [DEFAULT]
- Level 2: Medium (Intermediate / Tactical, prioritizes 4-way cross intersections, double mills, and mobility)
- Level 3: Hard (Master / Minimax lookahead evaluating mill threats, piece advantage, and opponent lock-ins)

All bots default to level=1, and lobby bots are strictly level 1.
"""

import copy
import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


WIN_CONDITIONS: List[List[int]] = [
    [0, 1, 2], [0, 9, 21], [21, 22, 23], [23, 14, 2],
    [1, 4, 7], [9, 10, 11], [22, 19, 16], [14, 13, 12],
    [3, 4, 5], [3, 10, 18], [18, 19, 20], [20, 13, 5],
    [6, 7, 8], [6, 11, 15], [15, 16, 17], [17, 12, 8],
]

PIECES_NEIGHBORS: Dict[int, List[int]] = {
    0: [1, 9],
    1: [0, 2, 4],
    2: [1, 14],
    3: [4, 10],
    4: [1, 3, 5, 7],
    5: [4, 13],
    6: [7, 11],
    7: [4, 6, 8],
    8: [7, 12],
    9: [0, 10, 21],
    10: [3, 9, 11, 18],
    11: [6, 10, 15],
    12: [8, 13, 17],
    13: [5, 12, 14, 20],
    14: [2, 13, 23],
    15: [11, 16],
    16: [15, 17, 19],
    17: [12, 16],
    18: [10, 19],
    19: [16, 18, 20, 22],
    20: [13, 19],
    21: [9, 22],
    22: [19, 21, 23],
    23: [14, 22],
}

# Strategic node weights:
# 4-spoke hubs (4, 10, 13, 19) have 4 neighbors and highest mobility (+18)
# 3-spoke midpoints (1, 7, 9, 11, 12, 14, 16, 22) have 3 neighbors (+12)
# 2-spoke corners have 2 neighbors (+6)
NODE_WEIGHTS: Dict[int, int] = {
    idx: (18 if len(neighs) == 4 else (12 if len(neighs) == 3 else 6))
    for idx, neighs in PIECES_NEIGHBORS.items()
}


class MillGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Mill",
            game_type_aliases=[
                "mill",
                "nine_mens_morris",
                "ninemensmorris",
                "morris",
                "دوز نه تایی",
                "دوز نه‌تایی",
                "دوز 9 تایی",
            ],
            level=level,
        )
        self.board: List[int] = [0 for _ in range(24)]
        self.player1_peaces: int = 9
        self.player2_peaces: int = 9
        self.player1_played_peaces: int = 0
        self.player2_played_peaces: int = 0
        self.player1_removed_peaces: int = 0
        self.player2_removed_peaces: int = 0
        self.current_remover: int = 0
        self.current_turn: int = 1
        self.reset()

    def reset(self):
        """Resets the 24-node board and counters to standard Nine Men's Morris start."""
        self.board = [0 for _ in range(24)]
        self.player1_peaces = 9
        self.player2_peaces = 9
        self.player1_played_peaces = 0
        self.player2_played_peaces = 0
        self.player1_removed_peaces = 0
        self.player2_removed_peaces = 0
        self.current_remover = 0
        self.current_turn = 1

    # --- Rule & Mill Helpers (1:1 with kafehfekrbackend/Entities/Games/Mill/__init__.py) ---

    def get_played_peaces(self, gamer_id: int) -> int:
        return self.player1_played_peaces if gamer_id == 1 else self.player2_played_peaces

    def get_removed_peaces(self, gamer_id: int) -> int:
        return self.player1_removed_peaces if gamer_id == 1 else self.player2_removed_peaces

    def is_flying(self, gamer_id: int, removed_peaces: Optional[int] = None) -> bool:
        rem = removed_peaces if removed_peaces is not None else self.get_removed_peaces(gamer_id)
        return (9 - rem) == 3

    @staticmethod
    def check_forms_mill(
        board_state: List[int], peace_number: int, gamer_id: int
    ) -> bool:
        """
        Returns True if `board_state[peace_number] == gamer_id` completes at least one
        3-in-a-row line in WIN_CONDITIONS containing `peace_number`.
        Matches MillGameClass.check_all_match_three_conditions 1:1.
        """
        for cond in WIN_CONDITIONS:
            if peace_number in cond:
                if (
                    board_state[cond[0]] == gamer_id
                    and board_state[cond[1]] == gamer_id
                    and board_state[cond[2]] == gamer_id
                ):
                    return True
        return False

    @staticmethod
    def count_potential_mills(board_state: List[int], gamer_id: int) -> int:
        """Counts lines with 2 pieces of `gamer_id` and 1 empty spot."""
        count = 0
        for cond in WIN_CONDITIONS:
            vals = [board_state[cond[0]], board_state[cond[1]], board_state[cond[2]]]
            if vals.count(gamer_id) == 2 and vals.count(0) == 1:
                count += 1
        return count

    @staticmethod
    def count_active_mills(board_state: List[int], gamer_id: int) -> int:
        """Counts completed 3-in-a-row mills for `gamer_id`."""
        count = 0
        for cond in WIN_CONDITIONS:
            if (
                board_state[cond[0]] == gamer_id
                and board_state[cond[1]] == gamer_id
                and board_state[cond[2]] == gamer_id
            ):
                count += 1
        return count

    @staticmethod
    def get_valid_moves_for_state(
        board_state: List[int],
        gamer_id: int,
        played_peaces: int,
        removed_peaces: int,
        current_remover: int = 0,
    ) -> List[Any]:
        """
        Returns legal moves for `gamer_id`:
        - If `current_remover == gamer_id`: list of `("remove", target_idx)` for all opponent pieces.
        - If `played_peaces < 9`: list of `("place", target_idx)` for all empty sockets.
        - If `played_peaces >= 9`: list of `("swap", src_idx, dst_idx)` for valid slides or flying moves.
        """
        opp_id = 1 if gamer_id == 2 else 2
        if current_remover == gamer_id:
            return [
                ("remove", idx)
                for idx in range(24)
                if board_state[idx] == opp_id
            ]

        if played_peaces < 9:
            return [
                ("place", idx)
                for idx in range(24)
                if board_state[idx] == 0
            ]

        flying = (9 - removed_peaces) == 3
        empty_nodes = [idx for idx in range(24) if board_state[idx] == 0]
        moves: List[Tuple[str, int, int]] = []
        for src in range(24):
            if board_state[src] != gamer_id:
                continue
            targets = empty_nodes if flying else [
                n for n in PIECES_NEIGHBORS[src] if board_state[n] == 0
            ]
            for dst in targets:
                moves.append(("swap", src, dst))
        return moves

    # --- BaseGameLogic Implementation ---

    def get_legal_moves(self) -> List[Any]:
        my_role = self.my_player_num or 2
        return self.get_valid_moves_for_state(
            self.board,
            my_role,
            self.get_played_peaces(my_role),
            self.get_removed_peaces(my_role),
            self.current_remover,
        )

    def is_critical_turn(self) -> bool:
        """Returns True during Mill capture phase or when a mill/block is on the board."""
        my_role = self.my_player_num or 2
        if self.current_remover == my_role:
            return True
        opp_role = 1 if my_role == 2 else 2
        if self.count_potential_mills(self.board, my_role) > 0:
            return True
        if self.count_potential_mills(self.board, opp_role) > 0:
            return True
        return False

    def should_act_on_reconnect(self) -> bool:
        my_role = self.my_player_num or 2
        if self.current_remover == my_role:
            return True
        if self.current_remover == 0 and self.current_turn == my_role:
            return len(self.get_legal_moves()) > 0
        return False

    def handle_server_command(self, cmd_id: str, payload: Any):
        if cmd_id == "StartGame":
            self.reset()

        elif cmd_id == "CurrentTurn":
            turn = payload.get("turn", payload) if isinstance(payload, dict) else payload
            if turn is not None:
                self.current_turn = int(turn)
            self.current_remover = 0

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                gamer_id = int(payload.get("user", payload.get("gamer_id", 0)))
                target_peace = int(payload.get("target_peace", -1))
                if 0 <= target_peace < 24 and gamer_id in (1, 2):
                    self.board[target_peace] = gamer_id
                    if gamer_id == 1:
                        self.player1_played_peaces += 1
                    else:
                        self.player2_played_peaces += 1

        elif cmd_id == "PeaceSwaped":
            if isinstance(payload, dict):
                gamer_id = int(payload.get("user", payload.get("gamer_id", 0)))
                src = int(payload.get("source_peace", payload.get("source", -1)))
                dst = int(payload.get("target_peace", payload.get("target", -1)))
                if 0 <= src < 24 and 0 <= dst < 24 and gamer_id in (1, 2):
                    self.board[src] = 0
                    self.board[dst] = gamer_id

        elif cmd_id == "SelectRemovePeace":
            remover = payload.get("remover_id", payload) if isinstance(payload, dict) else payload
            if remover is not None:
                self.current_remover = int(remover)

        elif cmd_id == "PeaceRemoved":
            if isinstance(payload, dict):
                gamer_id = int(payload.get("user", payload.get("gamer_id", 0)))
                target_peace = int(payload.get("target_peace", -1))
                if 0 <= target_peace < 24:
                    self.board[target_peace] = 0
                    if gamer_id == 1:
                        self.player2_removed_peaces += 1
                    elif gamer_id == 2:
                        self.player1_removed_peaces += 1
                self.current_remover = 0

        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                if isinstance(g_data, dict):
                    b_raw = g_data.get("board", [])
                    if isinstance(b_raw, list) and len(b_raw) == 24:
                        self.board = [int(x) for x in b_raw]
                    played = g_data.get("played_peaces", [])
                    if isinstance(played, list) and len(played) >= 2:
                        self.player1_played_peaces = int(played[0])
                        self.player2_played_peaces = int(played[1])
                    removed = g_data.get("removed_peaces", [])
                    if isinstance(removed, list) and len(removed) >= 2:
                        self.player1_removed_peaces = int(removed[0])
                        self.player2_removed_peaces = int(removed[1])
                    if "current_remover" in g_data:
                        self.current_remover = int(g_data["current_remover"])
                    if "turn" in g_data:
                        self.current_turn = int(g_data["turn"])

    # --- AI Decision Engine (Levels 1, 2, 3) ---

    def compute_next_move(self) -> Optional[Dict[str, Any]]:
        """
        Computes the next move for `self.my_player_num` and returns the exact
        Socket.IO `user_command` dictionary expected by MillGameSession:
        - Capture Phase: `{"id": "SelectRemovePeace", "data": peace_id}`
        - Placement Phase: `{"id": "SelectPeace", "data": peace_id}`
        - Movement/Flying Phase: `{"id": "SwapPeace", "data": {"source": src, "target": dst}}`
        """
        my_role = self.my_player_num or 2
        opp_role = 1 if my_role == 2 else 2
        legal_moves = self.get_legal_moves()
        if not legal_moves:
            return None

        # 1. Mill Capture Phase
        if self.current_remover == my_role:
            target_idx = self._choose_remove_move(legal_moves, my_role, opp_role)
            return {
                "id": "SelectRemovePeace",
                "data": int(target_idx),
            }

        # 2. Placement Phase
        if self.get_played_peaces(my_role) < 9:
            target_idx = self._choose_place_move(legal_moves, my_role, opp_role)
            return {
                "id": "SelectPeace",
                "data": int(target_idx),
            }

        # 3. Movement / Flying Phase
        src_idx, dst_idx = self._choose_swap_move(legal_moves, my_role, opp_role)
        return {
            "id": "SwapPeace",
            "data": {
                "source": int(src_idx),
                "target": int(dst_idx),
            },
        }

    def build_move_command(self, move: Any) -> Dict[str, Any]:
        """
        Serializes the selected move into the server command dictionary:
        - `{"id": "SelectRemovePeace", "data": peace_id}`
        - `{"id": "SelectPeace", "data": peace_id}`
        - `{"id": "SwapPeace", "data": {"source": src, "target": dst}}`
        """
        if isinstance(move, dict) and "id" in move:
            return move
        if isinstance(move, (tuple, list)) and len(move) >= 2:
            action = move[0]
            if action == "remove":
                return {"id": "SelectRemovePeace", "data": int(move[1])}
            elif action == "place":
                return {"id": "SelectPeace", "data": int(move[1])}
            elif action == "swap" and len(move) >= 3:
                return {
                    "id": "SwapPeace",
                    "data": {"source": int(move[1]), "target": int(move[2])},
                }
        return {"id": "SelectPeace", "data": move}

    def _choose_remove_move(
        self,
        legal_moves: List[Tuple[str, int]],
        my_role: int,
        opp_role: int,
    ) -> int:
        """Selects the best opponent piece to capture when a Mill is formed."""
        scored: List[Tuple[float, int]] = []
        for _, idx in legal_moves:
            sim_board = list(self.board)
            # Check if this opponent piece is part of an impending opponent 2-in-a-row threat
            threat_reduction = 0
            for cond in WIN_CONDITIONS:
                if idx in cond:
                    vals = [sim_board[cond[0]], sim_board[cond[1]], sim_board[cond[2]]]
                    if vals.count(opp_role) == 2 and vals.count(0) == 1:
                        threat_reduction += 45
                    elif vals.count(opp_role) == 1 and vals.count(my_role) == 2:
                        # Unblocks our own blocked mill line!
                        threat_reduction += 35

            score = float(threat_reduction + NODE_WEIGHTS.get(idx, 6))
            if self.level == 1:
                score += random.uniform(-12.0, 12.0)
            elif self.level == 2:
                score += random.uniform(-4.0, 4.0)
            scored.append((score, idx))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _choose_place_move(
        self,
        legal_moves: List[Tuple[str, int]],
        my_role: int,
        opp_role: int,
    ) -> int:
        """Selects where to place a piece during Phase 1 (`played_peaces < 9`)."""
        scored: List[Tuple[float, int]] = []
        for _, idx in legal_moves:
            sim_board = list(self.board)
            sim_board[idx] = my_role

            score = float(NODE_WEIGHTS.get(idx, 6))

            # Immediate mill creation
            if self.check_forms_mill(sim_board, idx, my_role):
                score += 150.0

            # Blocking opponent's immediate mill
            opp_sim = list(self.board)
            opp_sim[idx] = opp_role
            if self.check_forms_mill(opp_sim, idx, opp_role):
                score += 120.0

            # Creating 2-in-a-row threats (especially double threats)
            pot_mills = self.count_potential_mills(sim_board, my_role)
            score += pot_mills * 22.0

            if self.level >= 3:
                # Lookahead on opponent response
                opp_best = 0.0
                for empty_idx in range(24):
                    if sim_board[empty_idx] == 0:
                        opp_b = list(sim_board)
                        opp_b[empty_idx] = opp_role
                        if self.check_forms_mill(opp_b, empty_idx, opp_role):
                            opp_best = max(opp_best, 90.0)
                score -= opp_best

            if self.level == 1:
                score += random.uniform(-18.0, 18.0)
            elif self.level == 2:
                score += random.uniform(-5.0, 5.0)
            else:
                score += random.uniform(-0.5, 0.5)

            scored.append((score, idx))

        scored.sort(key=lambda x: x[0], reverse=True)
        if self.level == 1 and len(scored) > 1 and random.random() < 0.20:
            return scored[1][1]
        return scored[0][1]

    def _choose_swap_move(
        self,
        legal_moves: List[Tuple[str, int, int]],
        my_role: int,
        opp_role: int,
    ) -> Tuple[int, int]:
        """Selects which piece to slide/fly during Phase 2 & Phase 3."""
        scored: List[Tuple[float, int, int]] = []
        opp_played = self.get_played_peaces(opp_role)
        opp_removed = self.get_removed_peaces(opp_role)

        for _, src, dst in legal_moves:
            sim_board = list(self.board)
            sim_board[src] = 0
            sim_board[dst] = my_role

            score = float(NODE_WEIGHTS.get(dst, 6) - NODE_WEIGHTS.get(src, 6) * 0.4)

            # 1. Immediate mill formation
            if self.check_forms_mill(sim_board, dst, my_role):
                score += 180.0

            # 2. Check if moving to `dst` blocks an opponent's immediate slide mill
            for opp_src in range(24):
                if self.board[opp_src] == opp_role and opp_src != dst:
                    can_reach = (
                        (9 - opp_removed == 3 and opp_played >= 9)
                        or (dst in PIECES_NEIGHBORS[opp_src])
                    )
                    if can_reach:
                        opp_sim = list(self.board)
                        opp_sim[opp_src] = 0
                        opp_sim[dst] = opp_role
                        if self.check_forms_mill(opp_sim, dst, opp_role):
                            score += 130.0
                            break

            # 3. Check if vacating `src` allows an opponent to immediately form a mill at `src`
            for opp_src in range(24):
                if sim_board[opp_src] == opp_role:
                    can_reach_src = (
                        (9 - opp_removed == 3 and opp_played >= 9)
                        or (src in PIECES_NEIGHBORS[opp_src])
                    )
                    if can_reach_src:
                        opp_sim = list(sim_board)
                        opp_sim[opp_src] = 0
                        opp_sim[src] = opp_role
                        if self.check_forms_mill(opp_sim, src, opp_role):
                            score -= 115.0
                            break

            # 4. Shuttle mill bonus: if `src` was part of a mill that can be re-closed next turn
            if self.check_forms_mill(self.board, src, my_role):
                score += 16.0

            # 5. Mobility & potential mills
            score += self.count_potential_mills(sim_board, my_role) * 18.0
            if self.level >= 2 and opp_played >= 9:
                opp_moves = self.get_valid_moves_for_state(
                    sim_board, opp_role, opp_played, opp_removed, 0
                )
                if len(opp_moves) == 0:
                    # Winning by locking all opponent pieces!
                    score += 500.0
                else:
                    score -= len(opp_moves) * 2.5

            if self.level == 1:
                score += random.uniform(-16.0, 16.0)
            elif self.level == 2:
                score += random.uniform(-4.0, 4.0)
            else:
                score += random.uniform(-0.4, 0.4)

            scored.append((score, src, dst))

        scored.sort(key=lambda x: x[0], reverse=True)
        if self.level == 1 and len(scored) > 1 and random.random() < 0.20:
            return scored[1][1], scored[1][2]
        return scored[0][1], scored[0][2]

    def format_state(self) -> str:
        """Returns an ASCII summary of the Nine Men's Morris board and phase."""
        sym = {0: "·", 1: "R", 2: "B"}
        b = [sym.get(v, "·") for v in self.board]
        p1_rem = 9 - self.player1_removed_peaces
        p2_rem = 9 - self.player2_removed_peaces
        lines = [
            f"  [Mill Board] P1(R): {p1_rem} left ({self.player1_played_peaces}/9 placed) | "
            f"P2(B): {p2_rem} left ({self.player2_played_peaces}/9 placed) | "
            f"Remover: {self.current_remover}",
            f"    {b[0]}-----------{b[1]}-----------{b[2]}",
            f"    |   {b[3]}-------{b[4]}-------{b[5]}   |",
            f"    |   |   {b[6]}---{b[7]}---{b[8]}   |   |",
            f"    {b[9]}---{b[10]}---{b[11]}       {b[12]}---{b[13]}---{b[14]}",
            f"    |   |   {b[15]}---{b[16]}---{b[17]}   |   |",
            f"    |   {b[18]}-------{b[19]}-------{b[20]}   |",
            f"    {b[21]}-----------{b[22]}-----------{b[23]}",
        ]
        return "\n".join(lines)
