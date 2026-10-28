"""
BattleShip ("نبرد کشتی") Pure Game Logic for Cafe Fekr Bots.

2-Phase Naval Strategy Game:
- Phase 1 (Fleet Setup - 60s):
  Places 4 ships of lengths 2, 3, 4, 5 on an 8x8 grid (cells 0..63) without overlap
  and sends:
    {"id": "SaveBoard", "data": {"2": [...], "3": [...], "4": [...], "5": [...]}}
- Phase 2 (Artillery Combat - 12s per turn):
  Fires at opponent's 8x8 grid (0..63) using:
    {"id": "SelectPeace", "data": cell_index}
  When a shot hits a ship (number in [2, 3, 4, 5], is_turn_win_happened == True),
  the server grants an immediate bonus turn to the same player without emitting
  a new CurrentTurn event.

Difficulty Levels:
- Level 1: Easiest (Beginner / Casual Human — random shots with occasional follow-up) [DEFAULT]
- Level 2: Medium (Hunt & Target — follows up on unsunk ship hits)
- Level 3: Hard (Checkerboard parity search + collinear ship targeting)
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic

GRID_SIZE = 8
TOTAL_CELLS = 64
SHIP_LENGTHS = [5, 4, 3, 2]


class BattleShipGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="BattleShip",
            game_type_aliases=[
                "battleship",
                "battle_ship",
                "نبرد کشتی",
                "کشتی جنگی",
                "نبردکشتی",
            ],
            level=level,  # Default level must always be 1
        )
        self.my_fleet: Dict[str, List[int]] = {}
        self.has_saved_board: bool = False
        self.is_play_phase: bool = False
        self.my_shots: Dict[int, int] = {}      # cell_index -> hit_number (0=miss, 2..5=ship)
        self.opp_shots: Dict[int, int] = {}     # cell_index -> hit_number on our board
        self.scores: List[int] = [0, 0]
        self._bonus_turn_pending: bool = False
        self._should_act_reconnect: bool = False
        self.reset()

    def reset(self):
        """Resets board state for a new match."""
        self.my_fleet = self._generate_random_fleet()
        self.has_saved_board = False
        self.is_play_phase = False
        self.my_shots.clear()
        self.opp_shots.clear()
        self.scores = [0, 0]
        self._bonus_turn_pending = False
        self._should_act_reconnect = False
        self.current_round = 1

    def on_game_start(self, game_id: str):
        super().on_game_start(game_id)
        self.reset()

    def _generate_random_fleet(self) -> Dict[str, List[int]]:
        """Generates a valid non-overlapping placement for ships of length 5, 4, 3, 2 on 8x8."""
        occupied = set()
        fleet: Dict[str, List[int]] = {}

        for length in SHIP_LENGTHS:
            placed = False
            for _ in range(200):
                horiz = random.choice([True, False])
                if horiz:
                    r = random.randint(0, GRID_SIZE - 1)
                    c = random.randint(0, GRID_SIZE - length)
                    cells = [r * GRID_SIZE + (c + i) for i in range(length)]
                else:
                    r = random.randint(0, GRID_SIZE - length)
                    c = random.randint(0, GRID_SIZE - 1)
                    cells = [(r + i) * GRID_SIZE + c for i in range(length)]

                if not any(idx in occupied for idx in cells):
                    for idx in cells:
                        occupied.add(idx)
                    fleet[str(length)] = sorted(cells)
                    placed = True
                    break

            if not placed:
                # Fallback deterministic non-overlapping vertical layout
                return {
                    "5": [0, 8, 16, 24, 32],
                    "4": [2, 10, 18, 26],
                    "3": [4, 12, 20],
                    "2": [6, 14],
                }

        return fleet

    def should_send_initial_board(self) -> bool:
        """Returns True in Phase 1 if the bot has not yet sent SaveBoard."""
        return not self.has_saved_board and not self.is_play_phase

    def get_initial_board_move(self) -> dict:
        """Builds the SaveBoard command dictionary with all 4 ship placements."""
        if not self.my_fleet or len(self.my_fleet) != 4:
            self.my_fleet = self._generate_random_fleet()
        self.has_saved_board = True
        return {
            "id": "SaveBoard",
            "data": dict(self.my_fleet),
        }

    def should_continue_turn(self) -> bool:
        """Returns True if the bot just scored a Hit and earned an immediate bonus shot."""
        if self._bonus_turn_pending:
            self._bonus_turn_pending = False
            return True
        return False

    def should_act_on_reconnect(self) -> bool:
        if self._should_act_reconnect:
            self._should_act_reconnect = False
            return True
        return False

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes incoming BattleShip server events."""
        if cmd_id == "GameData":
            self.reset()
            return True

        elif cmd_id == "StartGame":
            self.is_play_phase = False
            self.has_saved_board = False
            return True

        elif cmd_id == "CurrentTurn":
            self.is_play_phase = True
            self.has_saved_board = True
            self._bonus_turn_pending = False
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                sdata = payload.get("select_data", payload)
                if not isinstance(sdata, dict):
                    sdata = payload
                idx = int(sdata.get("index", -1))
                gamer_id = int(sdata.get("gamer_id", 0))
                number = int(sdata.get("number", 0))
                is_win = bool(sdata.get("is_turn_win_happened", number > 0))

                my_role = self.my_player_num or 2
                if 0 <= idx < TOTAL_CELLS:
                    if gamer_id == my_role:
                        self.my_shots[idx] = number
                        if number > 0:
                            self.scores[my_role - 1] += 1
                        total_my_hits = sum(1 for v in self.my_shots.values() if v > 0)
                        self._bonus_turn_pending = bool(is_win and total_my_hits < 14)
                    else:
                        self.opp_shots[idx] = number
                        if number > 0 and gamer_id in (1, 2):
                            self.scores[gamer_id - 1] += 1
                        self._bonus_turn_pending = False
            return True

        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                if isinstance(g_data, dict):
                    self.is_play_phase = bool(g_data.get("is_play_phase", False))
                    is_rdy = bool(g_data.get("is_player_rdy", False))
                    if self.is_play_phase or is_rdy:
                        self.has_saved_board = True

                    sc = g_data.get("scores", [0, 0])
                    if isinstance(sc, list) and len(sc) >= 2:
                        self.scores = [int(sc[0]), int(sc[1])]

                    my_role = self.my_player_num or 2
                    p1_board = g_data.get("player1_board", [])
                    p2_board = g_data.get("player2_board", [])
                    opp_board = p2_board if my_role == 1 else p1_board
                    my_board = p1_board if my_role == 1 else p2_board

                    self.my_shots.clear()
                    for idx, spot in enumerate(opp_board):
                        if isinstance(spot, dict) and spot.get("is_selected", False):
                            self.my_shots[idx] = int(spot.get("number", 0))

                    self.opp_shots.clear()
                    for idx, spot in enumerate(my_board):
                        if isinstance(spot, dict) and spot.get("is_selected", False):
                            self.opp_shots[idx] = int(spot.get("number", 0))

                    c_turn = int(g_data.get("current_turn", 0))
                    if self.is_play_phase and c_turn == my_role:
                        self._should_act_reconnect = True
            return True

        return False

    def get_legal_moves(self) -> List[int]:
        """Returns all un-shot cell indices (0..63) on the opponent's board."""
        return [idx for idx in range(TOTAL_CELLS) if idx not in self.my_shots]

    def _get_orthogonal_neighbors(self, idx: int) -> List[int]:
        r, c = divmod(idx, GRID_SIZE)
        neighbors = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                n_idx = nr * GRID_SIZE + nc
                if n_idx not in self.my_shots:
                    neighbors.append(n_idx)
        return neighbors

    def _get_unsunk_hits_by_ship(self) -> Dict[int, List[int]]:
        """Returns dictionary {ship_length: [hit_indices]} for ships that are hit but not yet sunk."""
        hits_by_len: Dict[int, List[int]] = {2: [], 3: [], 4: [], 5: []}
        for idx, num in self.my_shots.items():
            if num in hits_by_len:
                hits_by_len[num].append(idx)
        unsunk = {}
        for s_len, cells in hits_by_len.items():
            if 0 < len(cells) < s_len:
                unsunk[s_len] = sorted(cells)
        return unsunk

    def _get_smart_target_candidates(self) -> List[int]:
        """Finds high-probability target cells adjacent to damaged (unsunk) enemy ships."""
        unsunk = self._get_unsunk_hits_by_ship()
        if not unsunk:
            return []

        collinear_targets: List[int] = []
        neighbor_targets: List[int] = []

        for s_len, cells in unsunk.items():
            if len(cells) >= 2:
                # Determine orientation (horizontal if diff == 1, vertical if diff == 8)
                diff = cells[1] - cells[0]
                if diff == 1:
                    # Horizontal line: check left of first and right of last in same row
                    r0, c_first = divmod(cells[0], GRID_SIZE)
                    _, c_last = divmod(cells[-1], GRID_SIZE)
                    if c_first - 1 >= 0:
                        cand = r0 * GRID_SIZE + (c_first - 1)
                        if cand not in self.my_shots:
                            collinear_targets.append(cand)
                    if c_last + 1 < GRID_SIZE:
                        cand = r0 * GRID_SIZE + (c_last + 1)
                        if cand not in self.my_shots:
                            collinear_targets.append(cand)
                elif diff == GRID_SIZE:
                    # Vertical line: check above first and below last in same col
                    r_first, c0 = divmod(cells[0], GRID_SIZE)
                    r_last, _ = divmod(cells[-1], GRID_SIZE)
                    if r_first - 1 >= 0:
                        cand = (r_first - 1) * GRID_SIZE + c0
                        if cand not in self.my_shots:
                            collinear_targets.append(cand)
                    if r_last + 1 < GRID_SIZE:
                        cand = (r_last + 1) * GRID_SIZE + c0
                        if cand not in self.my_shots:
                            collinear_targets.append(cand)

            for c_idx in cells:
                for n_idx in self._get_orthogonal_neighbors(c_idx):
                    if n_idx not in neighbor_targets:
                        neighbor_targets.append(n_idx)

        if collinear_targets:
            return collinear_targets
        return neighbor_targets

    def is_critical_turn(self) -> bool:
        return bool(self._get_unsunk_hits_by_ship())

    def compute_next_move(self) -> Optional[int]:
        legal = self.get_legal_moves()
        if not legal:
            return None

        if self.level <= 1:
            return self._compute_level_1(legal)
        elif self.level == 2:
            return self._compute_level_2(legal)
        else:
            return self._compute_level_3(legal)

    def _compute_level_1(self, legal: List[int]) -> int:
        """
        Level 1 - Beginner / Casual Human (Default):
        - Fires mostly random shots across the board.
        - If an enemy ship is damaged, follows up on adjacent cells 45% of the time
          so the bot feels natural and fun to play against without being oppressive.
        """
        targets = self._get_smart_target_candidates()
        if targets and random.random() < 0.45:
            return random.choice(targets)
        return random.choice(legal)

    def _compute_level_2(self, legal: List[int]) -> int:
        """
        Level 2 - Intermediate (Hunt & Target):
        - Always targets adjacent/collinear cells when an unsunk ship is damaged.
        - Otherwise fires random shots.
        """
        targets = self._get_smart_target_candidates()
        if targets:
            return random.choice(targets)
        return random.choice(legal)

    def _compute_level_3(self, legal: List[int]) -> int:
        """
        Level 3 - Hard (Parity Search + Collinear Target):
        - Finishes off damaged ships using collinear deduction.
        - Uses checkerboard parity cells ((r + c) % 2 == 0) in open water.
        """
        targets = self._get_smart_target_candidates()
        if targets:
            return random.choice(targets)
        parity_cells = [idx for idx in legal if ((idx // GRID_SIZE) + (idx % GRID_SIZE)) % 2 == 0]
        if parity_cells:
            return random.choice(parity_cells)
        return random.choice(legal)

    def build_move_command(self, move: int) -> dict:
        return {
            "id": "SelectPeace",
            "data": int(move),
        }

    def format_state(self) -> str:
        my_hits = sum(1 for v in self.my_shots.values() if v > 0)
        opp_hits = sum(1 for v in self.opp_shots.values() if v > 0)
        return (
            f"BattleShip [Phase={'Combat' if self.is_play_phase else 'Setup'} | "
            f"My Hits: {my_hits}/14 | Opp Hits: {opp_hits}/14 | Shots Fired: {len(self.my_shots)}/64]"
        )
