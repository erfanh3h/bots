"""
BackGammon (تخته نرد) Game Logic for Cafe Fekr Bot.

Matches exact rules and socket protocol of kafehfekrbackend/Entities/Games/BackGammon:
- 24 points (indices 0..23).
- Player 1 (Red, gamer_id=1) moves in +1 direction (0 -> 23), home board 18..23,
  enters from bar at index = -1 (into 0..5), bears off at target_index == 24.
- Player 2 (Blue, gamer_id=2) moves in -1 direction (23 -> 0), home board 0..5,
  enters from bar at index = 24 (into 23..18), bears off at target_index == -1.
- Turn Lifecycle:
  1. Server emits CurrentTurn: {"turn": 1 or 2} (30s turn timer).
  2. Active player sends RollDice: {"id": "RollDice", "data": {}}.
  3. Server rolls 2 dice (or 4 dice on doubles) and checks have_available_move:
     - If moves exist: emits RollResult: {"dices": [d1, d2, ...]}.
     - If no moves exist: emits OutOfMove: {"turn": turn, "dices": [...]} and passes turn in 4s.
  4. Active player sends SelectPeace: {"id": "SelectPeace", "data": {"index": -1..24, "dice_index": 0..k}}
     for each playable die until current_dices is empty or no legal moves remain.
  5. Server broadcasts PeaceSelected: {"gamer_id": g, "index": idx, "dice_index": d_idx} after each die move.
  6. First player to bear off all 15 checkers (score == 15) wins the match.

Difficulty Levels:
- Level 1 (Default): Beginner / Casual human player. Plays valid moves with light preference for hits/bear-offs.
- Level 2: Intermediate / Tactical player. Evaluates blot hits, anchoring/making points, and blot safety.
- Level 3: Hard / Master player. Multi-die sequence lookahead across all rolled dice to maximize board equity.
"""

import copy
import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


def _is_valid_index(index: int) -> bool:
    return 0 <= index < 24


def _is_valid_index_in_end_phase(index: int, gamer_id: int) -> bool:
    if gamer_id == 1:
        return 0 <= index <= 24
    if gamer_id == 2:
        return -1 <= index < 24
    return False


class BackGammonGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="BackGammon",
            game_type_aliases=[
                "backgammon",
                "back_gammon",
                "تخته نرد",
                "تخته‌نرد",
                "nard",
                "takhtenard",
            ],
            level=level,
        )
        # board[0..23]: {"count": int, "equipped_user": int}
        self.board: List[Dict[str, int]] = []
        self.current_dices: List[int] = []
        self.dices_rolled: bool = False
        self.current_turn: int = 1
        self.p1_score: int = 0
        self.p2_score: int = 0
        self.p1_out_pieces: int = 0
        self.p2_out_pieces: int = 0
        self.p1_is_in_end_phase: bool = False
        self.p2_is_in_end_phase: bool = False
        self.reset()

    def reset(self):
        """Resets board to standard Backgammon initial configuration."""
        self.board = [{"count": 0, "equipped_user": 0} for _ in range(24)]
        # Exact match with BackGammonGameClass.init_board()
        self._set_spot(0, 1, 2)
        self._set_spot(23, 2, 2)
        self._set_spot(5, 2, 5)
        self._set_spot(18, 1, 5)
        self._set_spot(7, 2, 3)
        self._set_spot(16, 1, 3)
        self._set_spot(11, 1, 5)
        self._set_spot(12, 2, 5)

        self.current_dices = []
        self.dices_rolled = False
        self.current_turn = 1
        self.p1_score = 0
        self.p2_score = 0
        self.p1_out_pieces = 0
        self.p2_out_pieces = 0
        self.p1_is_in_end_phase = False
        self.p2_is_in_end_phase = False

    def _set_spot(self, idx: int, gamer_id: int, count: int):
        if 0 <= idx < 24:
            self.board[idx] = {
                "count": count,
                "equipped_user": gamer_id if count > 0 else 0,
            }

    # ==========================================================================
    # Core State & Rule Helpers (Exact Port of BackGammonGameClass)
    # ==========================================================================

    @staticmethod
    def _check_end_phase_on_state(
        board: List[Dict[str, int]],
        p1_score: int,
        p2_score: int,
        gamer_id: int,
    ) -> bool:
        if gamer_id == 1:
            total = p1_score
            for pt in range(18, 24):
                if board[pt]["equipped_user"] == 1:
                    total += board[pt]["count"]
            return total == 15
        else:
            total = p2_score
            for pt in range(0, 6):
                if board[pt]["equipped_user"] == 2:
                    total += board[pt]["count"]
            return total == 15

    def _update_end_phase(self, gamer_id: int):
        if gamer_id == 1:
            self.p1_is_in_end_phase = self._check_end_phase_on_state(
                self.board, self.p1_score, self.p2_score, 1
            )
        else:
            self.p2_is_in_end_phase = self._check_end_phase_on_state(
                self.board, self.p1_score, self.p2_score, 2
            )

    @staticmethod
    def _can_move_on_state(
        board: List[Dict[str, int]],
        is_in_end_phase: bool,
        source_idx: int,
        dice_val: int,
        gamer_id: int,
    ) -> bool:
        multiple = 1 if gamer_id == 1 else -1
        destination = source_idx + (dice_val * multiple)

        if is_in_end_phase:
            if not _is_valid_index_in_end_phase(destination, gamer_id):
                return False
            if destination != -1 and destination != 24:
                spot = board[destination]
                if spot["equipped_user"] != 0 and spot["equipped_user"] != gamer_id and spot["count"] > 1:
                    return False
        else:
            if not _is_valid_index(destination):
                return False
            spot = board[destination]
            if spot["equipped_user"] != 0 and spot["equipped_user"] != gamer_id and spot["count"] > 1:
                return False
        return True

    def _apply_move_to_self(self, index: int, dice_val: int, gamer_id: int) -> bool:
        """Applies a single checker move to the bot's internal state (matches BackGammonGameClass.move_piece)."""
        if index == -1 or index == 24:
            if gamer_id == 1:
                self.p1_out_pieces = max(0, self.p1_out_pieces - 1)
            else:
                self.p2_out_pieces = max(0, self.p2_out_pieces - 1)
        elif 0 <= index < 24:
            self.board[index]["count"] = max(0, self.board[index]["count"] - 1)
            if self.board[index]["count"] == 0:
                self.board[index]["equipped_user"] = 0

        multiple = 1 if gamer_id == 1 else -1
        target_index = index + (dice_val * multiple)
        is_in_end_phase = (
            self.p1_is_in_end_phase if gamer_id == 1 else self.p2_is_in_end_phase
        )

        if is_in_end_phase and (target_index == -1 or target_index == 24):
            if gamer_id == 1:
                self.p1_score += 1
            else:
                self.p2_score += 1
        elif 0 <= target_index < 24:
            target_spot = self.board[target_index]
            if target_spot["equipped_user"] != 0 and target_spot["equipped_user"] != gamer_id:
                if target_spot["count"] == 1:
                    if gamer_id == 1:
                        self.p2_out_pieces += 1
                    else:
                        self.p1_out_pieces += 1
                    target_spot["count"] = 1
                    target_spot["equipped_user"] = gamer_id
                else:
                    return False
            else:
                target_spot["count"] += 1
                target_spot["equipped_user"] = gamer_id

        self._update_end_phase(gamer_id)
        return True

    # ==========================================================================
    # Server Event Handling
    # ==========================================================================

    def should_continue_turn(self) -> bool:
        """Returns True if the bot still has remaining playable dice in the current turn."""
        my_role = self.my_player_num or 2
        if self.current_turn != my_role or not self.dices_rolled:
            return False
        if not self.current_dices:
            return False
        return len(self.get_legal_moves()) > 0

    def should_act_on_reconnect(self) -> bool:
        my_role = self.my_player_num or 2
        if self.current_turn != my_role:
            return False
        return len(self.get_legal_moves()) > 0

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "GameData":
            self.reset()
            return True

        elif cmd_id == "StartGame":
            self.is_game_active = True
            return True

        elif cmd_id == "CurrentTurn":
            turn = payload.get("turn", payload) if isinstance(payload, dict) else int(payload)
            self.current_turn = int(turn)
            self.dices_rolled = False
            self.current_dices = []
            return True

        elif cmd_id == "RollResult":
            self.dices_rolled = True
            if isinstance(payload, dict) and "dices" in payload:
                self.current_dices = [int(d) for d in payload["dices"]]
            return True

        elif cmd_id == "OutOfMove":
            self.dices_rolled = True
            self.current_dices = []
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                gamer_id = int(payload.get("gamer_id", 0))
                index = int(payload.get("index", 0))
                dice_index = int(payload.get("dice_index", 0))
                if 0 <= dice_index < len(self.current_dices):
                    dice_val = self.current_dices[dice_index]
                    # Remove first occurrence of dice_val (exact match with Python backend self.current_dices.remove)
                    self.current_dices.remove(dice_val)
                    self._apply_move_to_self(index, dice_val, gamer_id)
            return True

        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict):
                    b_arr = g_data.get("board", [])
                    if isinstance(b_arr, list) and len(b_arr) == 24:
                        for i in range(24):
                            sp = b_arr[i]
                            if isinstance(sp, dict):
                                self.board[i] = {
                                    "count": int(sp.get("count", 0)),
                                    "equipped_user": int(sp.get("equipped_user", 0)),
                                }
                    scores = g_data.get("scores", [0, 0])
                    if isinstance(scores, list) and len(scores) >= 2:
                        self.p1_score = int(scores[0])
                        self.p2_score = int(scores[1])
                    out_arr = g_data.get("out_pieces", [0, 0])
                    if isinstance(out_arr, list) and len(out_arr) >= 2:
                        self.p1_out_pieces = int(out_arr[0])
                        self.p2_out_pieces = int(out_arr[1])
                    end_arr = g_data.get("end_phases", [False, False])
                    if isinstance(end_arr, list) and len(end_arr) >= 2:
                        self.p1_is_in_end_phase = bool(end_arr[0])
                        self.p2_is_in_end_phase = bool(end_arr[1])
                    self.current_turn = int(g_data.get("current_turn", 1))
                    self.dices_rolled = bool(g_data.get("current_turn_player_rolled", False))
                    raw_dices = g_data.get("current_dices", [])
                    self.current_dices = [int(d) for d in raw_dices] if isinstance(raw_dices, list) else []
            return True

        return False

    # ==========================================================================
    # Legal Move Generation & AI Decision Engine (Levels 1, 2, 3)
    # ==========================================================================

    def get_legal_moves(self) -> List[Dict[str, Any]]:
        my_role = self.my_player_num or 2
        if self.current_turn != my_role:
            return []

        # Step 1: If dice have not been rolled yet, the only legal action is RollDice
        if not self.dices_rolled:
            return [{"action": "roll"}]

        if not self.current_dices:
            return []

        out_cnt = self.p1_out_pieces if my_role == 1 else self.p2_out_pieces
        is_in_end = self.p1_is_in_end_phase if my_role == 1 else self.p2_is_in_end_phase
        moves: List[Dict[str, Any]] = []

        if out_cnt > 0:
            bar_idx = -1 if my_role == 1 else 24
            for d_idx, d_val in enumerate(self.current_dices):
                if self._can_move_on_state(self.board, is_in_end, bar_idx, d_val, my_role):
                    moves.append({
                        "action": "move",
                        "index": bar_idx,
                        "dice_index": d_idx,
                        "dice_val": d_val,
                    })
        else:
            for pt in range(24):
                if self.board[pt]["equipped_user"] == my_role and self.board[pt]["count"] > 0:
                    for d_idx, d_val in enumerate(self.current_dices):
                        if self._can_move_on_state(self.board, is_in_end, pt, d_val, my_role):
                            moves.append({
                                "action": "move",
                                "index": pt,
                                "dice_index": d_idx,
                                "dice_val": d_val,
                            })
        return moves

    def is_critical_turn(self) -> bool:
        if not self.dices_rolled:
            return False
        moves = self.get_legal_moves()
        my_role = self.my_player_num or 2
        mult = 1 if my_role == 1 else -1
        for m in moves:
            if m.get("action") == "move":
                dest = m["index"] + m["dice_val"] * mult
                if dest in (-1, 24):
                    return True
                if 0 <= dest < 24:
                    sp = self.board[dest]
                    if sp["equipped_user"] not in (0, my_role) and sp["count"] == 1:
                        return True
        return False

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
        """Level 1 (Beginner): Casual human play — slight preference for bear-off/hits, otherwise random."""
        my_role = self.my_player_num or 2
        mult = 1 if my_role == 1 else -1
        for m in legal_moves:
            dest = m["index"] + m["dice_val"] * mult
            if dest in (-1, 24) and random.random() < 0.75:
                return m
        return random.choice(legal_moves)

    def _choose_level_2(self, legal_moves: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Level 2 (Intermediate): Scores single moves using tactical Backgammon heuristics."""
        my_role = self.my_player_num or 2
        best_score = -1e9
        best_moves = []
        for m in legal_moves:
            sc = self._score_single_move(self.board, self.p1_score, self.p2_score, m, my_role)
            if sc > best_score:
                best_score = sc
                best_moves = [m]
            elif abs(sc - best_score) < 1e-5:
                best_moves.append(m)
        return random.choice(best_moves)

    def _choose_level_3(self, legal_moves: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Level 3 (Master): Multi-die sequence lookahead!
        Ensures the first move played does not block the second die when a 2-move sequence exists,
        and maximizes resulting board equity (borne-off checkers, hits, made points, blot safety).
        """
        my_role = self.my_player_num or 2
        best_val = -1e9
        best_first_move = legal_moves[0]

        # Deduplicate equivalent (index, dice_val) pairs to keep search fast on doubles
        seen_pairs = set()
        for m in legal_moves:
            pair_key = (m["index"], m["dice_val"])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            sim_board = copy.deepcopy(self.board)
            sim_p1_sc = self.p1_score
            sim_p2_sc = self.p2_score
            sim_p1_out = self.p1_out_pieces
            sim_p2_out = self.p2_out_pieces
            sim_dices = list(self.current_dices)
            sim_dices.remove(m["dice_val"])

            sim_p1_sc, sim_p2_sc, sim_p1_out, sim_p2_out = self._simulate_step(
                sim_board, sim_p1_sc, sim_p2_sc, sim_p1_out, sim_p2_out,
                m["index"], m["dice_val"], my_role
            )

            # Look ahead 1 more die if dice remain
            seq_val = self._evaluate_board_state(
                sim_board, sim_p1_sc, sim_p2_sc, sim_p1_out, sim_p2_out, my_role
            )
            if sim_dices:
                next_d = sim_dices[0]
                out_c = sim_p1_out if my_role == 1 else sim_p2_out
                in_end = self._check_end_phase_on_state(sim_board, sim_p1_sc, sim_p2_sc, my_role)
                best_second = -1e9
                found_second = False
                candidates = [-1 if my_role == 1 else 24] if out_c > 0 else [
                    pt for pt in range(24)
                    if sim_board[pt]["equipped_user"] == my_role and sim_board[pt]["count"] > 0
                ]
                for pt2 in candidates:
                    if self._can_move_on_state(sim_board, in_end, pt2, next_d, my_role):
                        found_second = True
                        b2 = copy.deepcopy(sim_board)
                        s1, s2, o1, o2 = self._simulate_step(
                            b2, sim_p1_sc, sim_p2_sc, sim_p1_out, sim_p2_out,
                            pt2, next_d, my_role
                        )
                        v2 = self._evaluate_board_state(b2, s1, s2, o1, o2, my_role)
                        if v2 > best_second:
                            best_second = v2
                if found_second:
                    # Huge bonus for playing a move that enables playing the 2nd die!
                    seq_val = best_second + 120.0

            if seq_val > best_val:
                best_val = seq_val
                best_first_move = m

        return best_first_move

    def _simulate_step(
        self,
        board: List[Dict[str, int]],
        p1_sc: int,
        p2_sc: int,
        p1_out: int,
        p2_out: int,
        index: int,
        dice_val: int,
        gamer_id: int,
    ) -> Tuple[int, int, int, int]:
        if index in (-1, 24):
            if gamer_id == 1:
                p1_out = max(0, p1_out - 1)
            else:
                p2_out = max(0, p2_out - 1)
        elif 0 <= index < 24:
            board[index]["count"] = max(0, board[index]["count"] - 1)
            if board[index]["count"] == 0:
                board[index]["equipped_user"] = 0

        mult = 1 if gamer_id == 1 else -1
        target = index + dice_val * mult
        in_end = self._check_end_phase_on_state(board, p1_sc, p2_sc, gamer_id)

        if in_end and target in (-1, 24):
            if gamer_id == 1:
                p1_sc += 1
            else:
                p2_sc += 1
        elif 0 <= target < 24:
            sp = board[target]
            if sp["equipped_user"] not in (0, gamer_id) and sp["count"] == 1:
                if gamer_id == 1:
                    p2_out += 1
                else:
                    p1_out += 1
                sp["count"] = 1
                sp["equipped_user"] = gamer_id
            else:
                sp["count"] += 1
                sp["equipped_user"] = gamer_id

        return p1_sc, p2_sc, p1_out, p2_out

    def _score_single_move(
        self,
        board: List[Dict[str, int]],
        p1_sc: int,
        p2_sc: int,
        move: Dict[str, Any],
        gamer_id: int,
    ) -> float:
        sim_b = copy.deepcopy(board)
        s1, s2, o1, o2 = self._simulate_step(
            sim_b, p1_sc, p2_sc, self.p1_out_pieces, self.p2_out_pieces,
            move["index"], move["dice_val"], gamer_id
        )
        return self._evaluate_board_state(sim_b, s1, s2, o1, o2, gamer_id)

    def _evaluate_board_state(
        self,
        board: List[Dict[str, int]],
        p1_sc: int,
        p2_sc: int,
        p1_out: int,
        p2_out: int,
        gamer_id: int,
    ) -> float:
        my_sc = p1_sc if gamer_id == 1 else p2_sc
        opp_sc = p2_sc if gamer_id == 1 else p1_sc
        my_out = p1_out if gamer_id == 1 else p2_out
        opp_out = p2_out if gamer_id == 1 else p1_out

        score = (my_sc - opp_sc) * 260.0 + (opp_out - my_out) * 165.0

        for pt in range(24):
            sp = board[pt]
            owner = sp["equipped_user"]
            cnt = sp["count"]
            if owner == 0 or cnt == 0:
                continue
            progress = pt if owner == 1 else (23 - pt)
            is_home = progress >= 18
            if owner == gamer_id:
                score += cnt * progress * 1.8
                if cnt >= 2:
                    # Made point / anchor bonus
                    score += 36.0 if is_home else 24.0
                elif cnt == 1:
                    # Single blot penalty (higher penalty closer to home if opponent can hit)
                    score -= 32.0 + progress * 1.2
            else:
                score -= cnt * progress * 1.5
                if cnt == 1:
                    score += 18.0

        return score

    def build_move_command(self, move: Any) -> dict:
        if isinstance(move, dict) and move.get("action") == "roll":
            return {"id": "RollDice", "data": {}}
        return {
            "id": "SelectPeace",
            "data": {
                "index": int(move["index"]),
                "dice_index": int(move["dice_index"]),
            },
        }

    def format_state(self) -> str:
        return (
            f"[BackGammon] Turn: P{self.current_turn} | "
            f"Scores: P1={self.p1_score}/15, P2={self.p2_score}/15 | "
            f"Bar: P1={self.p1_out_pieces}, P2={self.p2_out_pieces} | "
            f"Dices: {self.current_dices}"
        )
