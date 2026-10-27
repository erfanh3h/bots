"""
Dots & Boxes / DotBox (نقطه خط) Pure Game Logic for Cafe Fekr Bots.

Decoupled game engine containing the 60-line & 25-box (5x5 boxes, 6x6 dots) board
representation, exact rule validation (matching kafehfekrbackend/Entities/Games/DotBox/__init__.py 1:1),
bonus turn continuation on box completion, and AI move generation across difficulty levels:
- Level 1: Easiest (Beginner / Casual Human, spots box captures & prefers safe lines with human variance) [DEFAULT]
- Level 2: Medium (Intermediate / Tactical, prioritizes double-box captures & avoids gifting 3rd walls)
- Level 3: Hard (Master / Chain-length & sacrifice evaluator, minimizes opponent chain captures when forced)

All bots default to level=1, and lobby bots are strictly level 1.
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


BOXES_NEIGHBORS: Dict[int, List[int]] = {
    0: [0, 5, 6, 11],
    1: [1, 6, 7, 12],
    2: [2, 7, 8, 13],
    3: [3, 8, 9, 14],
    4: [4, 9, 10, 15],
    5: [11, 16, 17, 22],
    6: [12, 17, 18, 23],
    7: [13, 18, 19, 24],
    8: [14, 19, 20, 25],
    9: [15, 20, 21, 26],
    10: [22, 27, 28, 33],
    11: [23, 28, 29, 34],
    12: [24, 29, 30, 35],
    13: [25, 30, 31, 36],
    14: [26, 31, 32, 37],
    15: [33, 38, 39, 44],
    16: [34, 39, 40, 45],
    17: [35, 40, 41, 46],
    18: [36, 41, 42, 47],
    19: [37, 42, 43, 48],
    20: [44, 49, 50, 55],
    21: [45, 50, 51, 56],
    22: [46, 51, 52, 57],
    23: [47, 52, 53, 58],
    24: [48, 53, 54, 59],
}

# Precomputed reverse lookup: line_id (0..59) -> list of box_ids (0..24) touching that line
LINE_TO_BOXES: Dict[int, List[int]] = {i: [] for i in range(60)}
for _box_id, _lines in BOXES_NEIGHBORS.items():
    for _line_id in _lines:
        LINE_TO_BOXES[_line_id].append(_box_id)


class DotBoxGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="DotBox",
            game_type_aliases=[
                "dotbox",
                "dot_box",
                "dotsandboxes",
                "dots_and_boxes",
                "نقطه خط",
                "نقطه‌خط",
            ],
            level=level,
        )
        self.lines_board: List[int] = [0 for _ in range(60)]
        self.boxes_board: List[int] = [0 for _ in range(25)]
        self.gamer1_score: int = 0
        self.gamer2_score: int = 0
        self.current_turn: int = 1
        self._continue_turn: bool = False
        self.reset()

    def reset(self):
        """Resets all 60 lines and 25 boxes to empty."""
        self.lines_board = [0 for _ in range(60)]
        self.boxes_board = [0 for _ in range(25)]
        self.gamer1_score = 0
        self.gamer2_score = 0
        self.current_turn = 1
        self._continue_turn = False

    # --- Exact Backend Rule Helpers (1:1 with DotBoxGameClass) ---

    def check_game_ended(self, lines_state: Optional[List[int]] = None) -> bool:
        board = lines_state if lines_state is not None else self.lines_board
        for peace in board:
            if peace == 0:
                return False
        return True

    @staticmethod
    def check_each_box_in_raw_happen(
        neighbors: List[int], lines_state: List[int]
    ) -> bool:
        for line_idx in neighbors:
            if lines_state[line_idx] == 0:
                return False
        return True

    @classmethod
    def check_box_win_happen(
        cls, peace_number: int, lines_state: List[int]
    ) -> Tuple[bool, List[int]]:
        """
        Checks if placing `peace_number` (assuming `lines_state[peace_number] != 0`)
        completes 1 or 2 adjacent boxes.
        Matches DotBoxGameClass.check_box_win_happen 1:1.
        """
        win_results: List[int] = []
        for box_id in LINE_TO_BOXES.get(peace_number, []):
            neighbors = BOXES_NEIGHBORS[box_id]
            if cls.check_each_box_in_raw_happen(neighbors, lines_state):
                win_results.append(box_id)
        return (len(win_results) > 0), win_results

    @staticmethod
    def count_box_walls(box_id: int, lines_state: List[int]) -> int:
        count = 0
        for line_idx in BOXES_NEIGHBORS[box_id]:
            if lines_state[line_idx] != 0:
                count += 1
        return count

    # --- BaseGameLogic Implementation ---

    def get_legal_moves(self) -> List[int]:
        """Returns all unselected line indices (0..59)."""
        return [idx for idx in range(60) if self.lines_board[idx] == 0]

    def should_continue_turn(self) -> bool:
        """
        Returns True when the bot's last `PeaceSelected` completed at least one box
        and the game has not ended yet (since DotBoxGameSession keeps the same player's
        turn active without emitting a new CurrentTurn event).
        """
        if self._continue_turn and not self.check_game_ended():
            self._continue_turn = False
            return True
        self._continue_turn = False
        return False

    def should_act_on_reconnect(self) -> bool:
        my_role = self.my_player_num or 2
        return self.current_turn == my_role and not self.check_game_ended()

    def is_critical_turn(self) -> bool:
        """Returns True if there is an immediate box capture on the board."""
        for box_id in range(25):
            if self.boxes_board[box_id] == 0 and self.count_box_walls(box_id, self.lines_board) == 3:
                return True
        return False

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "StartGame":
            self.reset()
            return True

        elif cmd_id == "CurrentTurn":
            turn = payload.get("turn", payload) if isinstance(payload, dict) else payload
            if turn is not None:
                self.current_turn = int(turn)
            self._continue_turn = False
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                gamer_id = int(payload.get("user", payload.get("gamer_id", 0)))
                peace_number = int(payload.get("target_peace", -1))
                if 0 <= peace_number < 60 and gamer_id in (1, 2):
                    self.lines_board[peace_number] = gamer_id
                    is_win, win_list = self.check_box_win_happen(
                        peace_number, self.lines_board
                    )
                    if is_win:
                        for box_idx in win_list:
                            if self.boxes_board[box_idx] == 0:
                                self.boxes_board[box_idx] = gamer_id
                                if gamer_id == 1:
                                    self.gamer1_score += 1
                                else:
                                    self.gamer2_score += 1
                        self.current_turn = gamer_id
                        my_role = self.my_player_num or 2
                        self._continue_turn = (
                            (gamer_id == my_role) and not self.check_game_ended()
                        )
                    else:
                        self._continue_turn = False
                    return True

        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                if isinstance(g_data, dict):
                    l_board = g_data.get("lines_board", [])
                    if isinstance(l_board, list) and len(l_board) == 60:
                        self.lines_board = [int(x) for x in l_board]
                    b_board = g_data.get("boxes_board", [])
                    if isinstance(b_board, list) and len(b_board) == 25:
                        self.boxes_board = [int(x) for x in b_board]
                    scores = g_data.get("scores", [])
                    if isinstance(scores, list) and len(scores) >= 2:
                        self.gamer1_score = int(scores[0])
                        self.gamer2_score = int(scores[1])
                    if "current_turn" in g_data:
                        self.current_turn = int(g_data["current_turn"])
                    self._continue_turn = False
                    return True

        return False

    # --- AI Decision Engine (Levels 1, 2, 3) ---

    def compute_next_move(self) -> Optional[int]:
        legal = self.get_legal_moves()
        if not legal:
            return None
        if len(legal) == 1:
            return legal[0]

        scored: List[Tuple[float, int]] = []
        for line_id in legal:
            score = self._evaluate_line_move(line_id)
            scored.append((score, line_id))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Level 1 slight human imperfection when no immediate box capture is missed
        if self.level == 1 and len(scored) > 1 and random.random() < 0.18:
            # Still prefer capturing a box most of the time
            if scored[0][0] < 100.0 or scored[1][0] >= 100.0:
                return scored[1][1]

        return scored[0][1]

    def _evaluate_line_move(self, line_id: int) -> float:
        """
        Scores placing `line_id`:
        - Immediate box capture (`3` walls -> `4` walls): +200 per box (+420 for double capture!)
        - Safe move (`0` or `1` wall -> `1` or `2` walls): +25 (prefers 0->1 over 1->2)
        - Dangerous sacrifice (`2` walls -> `3` walls, gifting opponent a capture):
          - Penalized by `-90 - 35 * opponent_chain_length`
        """
        sim_lines = list(self.lines_board)
        sim_lines[line_id] = self.my_player_num or 2

        adj_boxes = LINE_TO_BOXES.get(line_id, [])
        boxes_completed = 0
        third_walls_created = 0
        second_walls_created = 0

        for box_id in adj_boxes:
            walls_after = self.count_box_walls(box_id, sim_lines)
            if walls_after == 4:
                boxes_completed += 1
            elif walls_after == 3:
                third_walls_created += 1
            elif walls_after == 2:
                second_walls_created += 1

        score = 0.0
        if boxes_completed > 0:
            score += boxes_completed * 210.0
            # If completing this box also creates a 3rd wall in the adjacent box,
            # that's actually GREAT for us because we get a bonus turn and will capture that box next!
            if third_walls_created > 0:
                score += 65.0
        else:
            if third_walls_created == 0:
                # Safe move! Prefer edges touching boxes with fewer walls (0->1 better than 1->2)
                score += 30.0 - (second_walls_created * 6.0)
            else:
                # Sacrifice move: gives opponent at least one 3-walled box
                if self.level >= 2:
                    chain_gifted = self._estimate_opponent_chain_capture(sim_lines)
                    score -= 90.0 + (chain_gifted * 38.0)
                else:
                    score -= 85.0 * third_walls_created

        # Add level-dependent human jitter
        if self.level == 1:
            score += random.uniform(-16.0, 16.0)
        elif self.level == 2:
            score += random.uniform(-3.5, 3.5)
        else:
            score += random.uniform(-0.4, 0.4)

        return score

    @classmethod
    def _estimate_opponent_chain_capture(cls, sim_lines: List[int]) -> int:
        """
        Simulates how many boxes the opponent can greedily chain-capture if given
        the board state `sim_lines`. Used by Levels 2 & 3 to pick the smallest sacrifice.
        """
        lines = list(sim_lines)
        captured = 0
        while True:
            found_capture = False
            for box_id, neighbors in BOXES_NEIGHBORS.items():
                empty_lines = [l_idx for l_idx in neighbors if lines[l_idx] == 0]
                if len(empty_lines) == 1:
                    fill_line = empty_lines[0]
                    lines[fill_line] = 9
                    # Count how many boxes this single line just closed (1 or 2)
                    for b2 in LINE_TO_BOXES[fill_line]:
                        if all(lines[n] != 0 for n in BOXES_NEIGHBORS[b2]):
                            captured += 1
                    found_capture = True
                    break
            if not found_capture:
                break
        return captured

    def build_move_command(self, move: Any) -> Dict[str, Any]:
        """Serializes the selected line index (0..59) into `SelectPeace`."""
        if isinstance(move, dict) and "id" in move:
            return move
        return {
            "id": "SelectPeace",
            "data": int(move),
        }

    def format_state(self) -> str:
        filled_lines = sum(1 for x in self.lines_board if x != 0)
        return (
            f"  [DotBox Board] Lines: {filled_lines}/60 | "
            f"Boxes — P1(R): {self.gamer1_score} vs P2(B): {self.gamer2_score} | "
            f"Turn: Player {self.current_turn}"
        )
