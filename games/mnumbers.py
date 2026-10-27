"""
Match Numbers / MNumbers (کشف اعداد) Pure Game Logic for Cafe Fekr Bots.

Decoupled game engine containing the 36-tile (6x6 grid, 18 pairs of numbers 1..18)
board representation, exact rule validation (matching kafehfekrbackend/Entities/Games/MNumbers/__init__.py 1:1),
memory tracking of revealed tile values across turns, and AI pair selection across difficulty levels:
- Level 1: Easiest (Beginner / Casual Human, remembers recently revealed pairs with natural human memory decay) [DEFAULT]
- Level 2: Medium (Intermediate / Tactical memory, strong recall of medium-term revealed pairs & smart unseen exploration)
- Level 3: Hard (Master / Photographic memory, 100% recall of all revealed numbers & optimal unseen tile exploration)

All bots default to level=1, and lobby bots are strictly level 1.
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


TOTAL_TILES = 36


class MNumbersGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="MNumbers",
            game_type_aliases=[
                "mnumbers",
                "m_numbers",
                "matchnumbers",
                "match_numbers",
                "کشف اعداد",
                "کشف‌اعداد",
            ],
            level=level,
        )
        # 0 = available/unmatched, 1 = claimed by Player 1, 2 = claimed by Player 2
        self.equipped_user: List[int] = [0 for _ in range(TOTAL_TILES)]
        # Memory of revealed values: tile_idx (0..35) -> number value (1..18)
        self.known_values: Dict[int, int] = {}
        # Turn step when a tile was last revealed (used for human memory decay in Levels 1-2)
        self.reveal_step: Dict[int, int] = {}
        self.turn_counter: int = 0
        self.player1_score: int = 0
        self.player2_score: int = 0
        self.current_turn: int = 1
        self.reset()

    def reset(self):
        """Resets all 36 tiles and memory state for a new match."""
        self.equipped_user = [0 for _ in range(TOTAL_TILES)]
        self.known_values = {}
        self.reveal_step = {}
        self.turn_counter = 0
        self.player1_score = 0
        self.player2_score = 0
        self.current_turn = 1

    # --- Exact Backend Rule Helpers (1:1 with MNumbersGameClass) ---

    def is_peace_available(self, index: int) -> bool:
        return 0 <= index < TOTAL_TILES and self.equipped_user[index] == 0

    def check_game_ended(self) -> bool:
        for idx in range(TOTAL_TILES):
            if self.equipped_user[idx] == 0:
                return False
        return True

    def get_available_indices(self) -> List[int]:
        return [idx for idx in range(TOTAL_TILES) if self.equipped_user[idx] == 0]

    # --- BaseGameLogic Implementation ---

    def get_legal_moves(self) -> List[Tuple[int, int]]:
        """
        Returns available pair selections.
        To keep move count compact for HumanBehavior thinking time simulation,
        returns a representative list of available pairs (one per available tile).
        """
        avail = self.get_available_indices()
        if len(avail) < 2:
            return []
        moves: List[Tuple[int, int]] = []
        for i in range(len(avail) - 1):
            moves.append((avail[i], avail[i + 1]))
        return moves

    def should_act_on_reconnect(self) -> bool:
        my_role = self.my_player_num or 2
        return self.current_turn == my_role and not self.check_game_ended()

    def is_critical_turn(self) -> bool:
        """Returns True if there is a known matching pair on the board."""
        return len(self._find_known_matching_pairs(recall_all=True)) > 0

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "StartGame":
            self.reset()
            return True

        elif cmd_id == "CurrentTurn":
            turn = payload.get("turn", payload) if isinstance(payload, dict) else payload
            if turn is not None:
                self.current_turn = int(turn)
            self.turn_counter += 1
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                gamer_id = int(payload.get("user", payload.get("gamer_id", 0)))
                idx1 = int(payload.get("index1", -1))
                idx2 = int(payload.get("index2", -1))
                val1 = int(payload.get("value1", 0))
                val2 = int(payload.get("value2", 0))
                is_correct = bool(payload.get("is_correct", False))

                if 0 <= idx1 < TOTAL_TILES and val1 > 0:
                    self.known_values[idx1] = val1
                    self.reveal_step[idx1] = self.turn_counter
                if 0 <= idx2 < TOTAL_TILES and val2 > 0:
                    self.known_values[idx2] = val2
                    self.reveal_step[idx2] = self.turn_counter

                if is_correct and 0 <= idx1 < TOTAL_TILES and 0 <= idx2 < TOTAL_TILES:
                    self.equipped_user[idx1] = gamer_id
                    self.equipped_user[idx2] = gamer_id
                    if gamer_id == 1:
                        self.player1_score += 1
                    elif gamer_id == 2:
                        self.player2_score += 1
                return True

        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                if isinstance(g_data, dict):
                    board_arr = g_data.get("board", [])
                    if isinstance(board_arr, list) and len(board_arr) == TOTAL_TILES:
                        for i, spot in enumerate(board_arr):
                            if isinstance(spot, dict):
                                eq = int(spot.get("equipped_user", 0))
                                val = int(spot.get("value", 0))
                                self.equipped_user[i] = eq
                                if val > 0:
                                    self.known_values[i] = val
                                    self.reveal_step[i] = self.turn_counter
                    scores = g_data.get("scores", [])
                    if isinstance(scores, list) and len(scores) >= 2:
                        self.player1_score = int(scores[0])
                        self.player2_score = int(scores[1])
                    if "current_turn" in g_data:
                        self.current_turn = int(g_data["current_turn"])
                    return True

        return False

    # --- AI Decision Engine (Levels 1, 2, 3) ---

    def _can_recall_tile(self, idx: int) -> bool:
        """
        Determines whether the bot remembers the value at `idx` based on its difficulty level
        and how many turns ago `idx` was revealed.
        """
        if idx not in self.known_values:
            return False
        if self.level >= 3:
            # Level 3: Perfect photographic memory
            return True

        age = max(0, self.turn_counter - self.reveal_step.get(idx, 0))
        if self.level == 2:
            # Level 2: Strong intermediate memory
            if age <= 3:
                return True
            recall_prob = max(0.35, 0.90 - 0.08 * (age - 3))
            return random.random() < recall_prob

        # Level 1 (Beginner / Casual Human): Remembers very recent reveals, forgets older ones
        if age <= 1:
            return random.random() < 0.72
        elif age <= 3:
            return random.random() < 0.45
        elif age <= 5:
            return random.random() < 0.22
        return random.random() < 0.08

    def _find_known_matching_pairs(self, recall_all: bool = False) -> List[Tuple[int, int]]:
        """
        Finds all pairs of available indices `(i, j)` that share the same known number value.
        """
        avail = self.get_available_indices()
        by_value: Dict[int, List[int]] = {}
        for idx in avail:
            if idx in self.known_values:
                if recall_all or self._can_recall_tile(idx):
                    val = self.known_values[idx]
                    by_value.setdefault(val, []).append(idx)

        pairs: List[Tuple[int, int]] = []
        for val, indices in by_value.items():
            if len(indices) >= 2:
                pairs.append((indices[0], indices[1]))
        return pairs

    def compute_next_move(self) -> Optional[Dict[str, int]]:
        avail = self.get_available_indices()
        if len(avail) < 2:
            return None

        # 1. Check if we remember any complete matching pair!
        known_pairs = self._find_known_matching_pairs(recall_all=(self.level >= 3))
        if known_pairs:
            chosen = random.choice(known_pairs)
            return {"index1": chosen[0], "index2": chosen[1]}

        # 2. Separate available tiles into unseen vs previously seen
        unseen = [idx for idx in avail if idx not in self.known_values]
        seen = [idx for idx in avail if idx in self.known_values]

        # Level 2 & 3 prefer flipping 2 unseen tiles to maximize new information discovery
        if len(unseen) >= 2:
            if self.level >= 2 or random.random() < 0.78:
                pick = random.sample(unseen, 2)
                return {"index1": pick[0], "index2": pick[1]}

        # If exactly 1 unseen tile remains and at least 1 seen tile remains
        if len(unseen) == 1 and len(seen) >= 1:
            return {"index1": unseen[0], "index2": random.choice(seen)}

        # Fallback: pick any 2 distinct available tiles
        pick = random.sample(avail, 2)
        return {"index1": pick[0], "index2": pick[1]}

    def build_move_command(self, move: Any) -> Dict[str, Any]:
        """Serializes the selected pair `{"index1": idx1, "index2": idx2}` into `SelectPeace`."""
        if isinstance(move, dict):
            if "id" in move and "data" in move:
                return move
            if "index1" in move and "index2" in move:
                return {
                    "id": "SelectPeace",
                    "data": {
                        "index1": int(move["index1"]),
                        "index2": int(move["index2"]),
                    },
                }
        if isinstance(move, (list, tuple)) and len(move) >= 2:
            return {
                "id": "SelectPeace",
                "data": {
                    "index1": int(move[0]),
                    "index2": int(move[1]),
                },
            }
        raise ValueError(f"Invalid MNumbers move format: {move}")

    def format_state(self) -> str:
        matched_tiles = sum(1 for x in self.equipped_user if x != 0)
        return (
            f"  [MNumbers Board] Matched Tiles: {matched_tiles}/36 | "
            f"Known Memory: {len(self.known_values)} tiles | "
            f"Scores — P1(R): {self.player1_score} vs P2(B): {self.player2_score} | "
            f"Turn: Player {self.current_turn}"
        )
