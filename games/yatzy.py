"""
Yatzy (پنج تاس / یاتزی) Game Logic for Cafe Fekr Bot.
Matches exact rules and socket protocol of kafehfekrbackend/Entities/Games/Yatzy:
- 12 simultaneous rounds (60s per round, 5s wait between rounds).
- Each round starts with 5 rolled dice from server (rolled_dice_times = 1 -> up to 2 re-rolls).
- RollDice command: {"id": "RollDice", "data": {"selected_indexes": [0..4]}} (indices in selected_indexes are KEPT/HELD).
- RollResult event: {"dices": [d0, d1, d2, d3, d4]} sent privately after RollDice.
- SelectPeace command: {"id": "SelectPeace", "data": {"index": 0..11}} locks a category for the round.

Difficulty Levels:
- Level 1 (Default): Beginner / Casual human player. Rolls 0-1 extra times, picks casual categories.
- Level 2: Intermediate / Tactical player. Holds pairs/triples and prioritizes high-scoring categories.
- Level 3: Hard / Master player. Optimizes dice holds for Yahtzee/Straight/FullHouse and category selection.
"""

import random
from collections import Counter
from typing import Any, Dict, List, Optional

from .base_game import BaseGameLogic

CATEGORY_NAMES = {
    0: "Ones (تاس ۱)",
    1: "Twos (تاس ۲)",
    2: "Threes (تاس ۳)",
    3: "Fours (تاس ۴)",
    4: "Fives (تاس ۵)",
    5: "Sixes (تاس ۶)",
    6: "3-of-a-Kind (۳ تایی)",
    7: "4-of-a-Kind (۴ تایی)",
    8: "Chance (هر ترکیب)",
    9: "Full House (فول هاوس)",
    10: "Large Straight (ردیف بزرگ)",
    11: "Yatzy (یاتزی)",
}


def calculate_category_score(dices: List[int], category_idx: int) -> int:
    """Exact port of YatzyGameClass.calculate_score from kafehfekrbackend."""
    if not dices or len(dices) != 5:
        return 0
    counts = Counter(dices)
    total_sum = sum(dices)

    if 0 <= category_idx <= 5:
        target_num = category_idx + 1
        return sum(d for d in dices if d == target_num)
    elif category_idx == 6:  # 3-of-a-Kind
        return total_sum if any(c >= 3 for c in counts.values()) else 0
    elif category_idx == 7:  # 4-of-a-Kind
        return total_sum if any(c >= 4 for c in counts.values()) else 0
    elif category_idx == 8:  # Chance
        return total_sum
    elif category_idx == 9:  # Full House (3 of one + 2 of another)
        three_num = -1
        for num in range(1, 7):
            if counts[num] >= 3:
                three_num = num
                break
        if three_num != -1:
            for num in range(1, 7):
                if num != three_num and counts[num] >= 2:
                    return 25
        return 0
    elif category_idx == 10:  # Large Straight (1-5 or 2-6)
        s = set(dices)
        if {1, 2, 3, 4, 5}.issubset(s) or {2, 3, 4, 5, 6}.issubset(s):
            return 40
        return 0
    elif category_idx == 11:  # Yatzy (5 of a kind)
        return 50 if any(c >= 5 for c in counts.values()) else 0
    return 0


class YatzyGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Yatzy",
            game_type_aliases=["yatzy", "yahtzee", "یاتزی", "پنج تاس"],
            level=level,
        )
        self.my_board_selected: List[bool] = [False] * 12
        self.opp_board_selected: List[bool] = [False] * 12
        self.my_board_scores: List[int] = [0] * 12
        self.opp_board_scores: List[int] = [0] * 12
        self.current_dices: List[int] = [1, 2, 3, 4, 5]
        self.rolled_dice_times: int = 1
        self.is_round_done: bool = False
        self.player1_score: int = 0
        self.player2_score: int = 0
        self.reset()

    def reset(self):
        """Resets state for a new 12-round Yatzy match."""
        self.my_board_selected = [False] * 12
        self.opp_board_selected = [False] * 12
        self.my_board_scores = [0] * 12
        self.opp_board_scores = [0] * 12
        self.current_dices = [1, 2, 3, 4, 5]
        self.rolled_dice_times = 1
        self.is_round_done = False
        self.player1_score = 0
        self.player2_score = 0
        self.current_round = 1

    def should_act_on_reconnect(self) -> bool:
        return not self.is_round_done and any(not sel for sel in self.my_board_selected)

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Handles incoming server events for Yatzy."""
        if cmd_id == "GameData":
            self.reset()
            return True

        elif cmd_id == "StartGame":
            self.current_round = 1
            return True

        elif cmd_id == "CurrentTurn":
            if isinstance(payload, dict):
                self.current_round = int(payload.get("current_turn", payload.get("current_round", self.current_round)))
                dices = payload.get("dices", [])
                if isinstance(dices, list) and len(dices) == 5:
                    self.current_dices = [int(x) for x in dices]
            elif isinstance(payload, int):
                self.current_round = payload
            self.rolled_dice_times = 1
            self.is_round_done = False
            return True

        elif cmd_id == "RollResult":
            if isinstance(payload, dict):
                dices = payload.get("dices", [])
                if isinstance(dices, list) and len(dices) == 5:
                    self.current_dices = [int(x) for x in dices]
            self.rolled_dice_times = min(3, self.rolled_dice_times + 1)
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                gamer_id = int(payload.get("gamer_id", 0))
                sel_idx = int(payload.get("selected_index", 0))
                score = int(payload.get("score", 0))
                self.player1_score = int(payload.get("player1_score", self.player1_score))
                self.player2_score = int(payload.get("player2_score", self.player2_score))
                my_id = self.my_player_num or 2
                if 0 <= sel_idx < 12:
                    if gamer_id == my_id:
                        self.my_board_selected[sel_idx] = True
                        self.my_board_scores[sel_idx] = score
                        self.is_round_done = True
                    else:
                        self.opp_board_selected[sel_idx] = True
                        self.opp_board_scores[sel_idx] = score
            return True

        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                if isinstance(g_data, dict):
                    self.current_round = int(g_data.get("current_round", 1))
                    self.is_round_done = bool(g_data.get("is_round_done", False))
                    self.rolled_dice_times = int(g_data.get("rolled_dice_times", 1))
                    dices = g_data.get("current_dices", [])
                    if isinstance(dices, list) and len(dices) == 5:
                        self.current_dices = [int(x) for x in dices]
                    scores = g_data.get("scores", [0, 0])
                    if isinstance(scores, list) and len(scores) >= 2:
                        self.player1_score = int(scores[0])
                        self.player2_score = int(scores[1])

                    my_id = self.my_player_num or 2
                    p1_b = g_data.get("player1_board", [])
                    p2_b = g_data.get("player2_board", [])
                    my_b = p1_b if my_id == 1 else p2_b
                    opp_b = p2_b if my_id == 1 else p1_b
                    for i in range(min(12, len(my_b))):
                        if isinstance(my_b[i], dict):
                            self.my_board_selected[i] = bool(my_b[i].get("is_selected", False))
                            self.my_board_scores[i] = int(my_b[i].get("score", 0))
                    for i in range(min(12, len(opp_b))):
                        if isinstance(opp_b[i], dict):
                            self.opp_board_selected[i] = bool(opp_b[i].get("is_selected", False))
                            self.opp_board_scores[i] = int(opp_b[i].get("score", 0))
            return True

        return False

    def get_open_categories(self) -> List[int]:
        return [i for i in range(12) if not self.my_board_selected[i]]

    def get_legal_moves(self) -> List[Dict[str, Any]]:
        if self.is_round_done:
            return []
        open_cats = self.get_open_categories()
        if not open_cats:
            return []
        moves: List[Dict[str, Any]] = [{"action": "select", "index": i} for i in open_cats]
        if self.rolled_dice_times < 3:
            moves.append({"action": "roll", "selected_indexes": []})
        return moves

    def is_critical_turn(self) -> bool:
        return self.current_round >= 10

    def compute_next_move(self) -> Optional[Dict[str, Any]]:
        if self.is_round_done:
            return None
        open_cats = self.get_open_categories()
        if not open_cats:
            return None

        if self.level == 1:
            return self._compute_level_1(open_cats)
        elif self.level == 2:
            return self._compute_level_2(open_cats)
        else:
            return self._compute_level_3(open_cats)

    def _choose_held_dice_indices(self) -> List[int]:
        """Chooses which dice indices (0..4) to hold before re-rolling."""
        counts = Counter(self.current_dices)
        most_common_val, most_common_cnt = counts.most_common(1)[0]

        # Check if we have 4 sequential dice for Large Straight (when category 10 is open)
        if not self.my_board_selected[10]:
            for seq in ([1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6]):
                if all(v in self.current_dices for v in seq):
                    held = []
                    used_vals = set()
                    for idx, val in enumerate(self.current_dices):
                        if val in seq and val not in used_vals:
                            held.append(idx)
                            used_vals.add(val)
                    return held

        # Hold dice matching the most frequent value (if >= 2)
        if most_common_cnt >= 2:
            return [idx for idx, val in enumerate(self.current_dices) if val == most_common_val]

        # Otherwise hold high dice (5 or 6)
        return [idx for idx, val in enumerate(self.current_dices) if val >= 5]

    def _compute_level_1(self, open_cats: List[int]) -> Dict[str, Any]:
        """
        Level 1 - Beginner / Casual Human:
        - 45% chance to roll again if rolls remain (holding matching dice).
        - Picks among positive-scoring categories with casual randomness, or first open category.
        """
        if self.rolled_dice_times < 3 and random.random() < 0.45:
            held = self._choose_held_dice_indices()
            if len(held) < 5:
                return {"action": "roll", "selected_indexes": held}

        scored_cats = [(i, calculate_category_score(self.current_dices, i)) for i in open_cats]
        positive_cats = [(i, sc) for i, sc in scored_cats if sc > 0]
        if positive_cats:
            # 60% pick one of the top scoring categories, 40% pick any positive category
            positive_cats.sort(key=lambda x: x[1], reverse=True)
            if random.random() < 0.60:
                chosen_idx = positive_cats[0][0]
            else:
                chosen_idx = random.choice(positive_cats)[0]
            return {"action": "select", "index": chosen_idx}

        return {"action": "select", "index": open_cats[0]}

    def _compute_level_2(self, open_cats: List[int]) -> Dict[str, Any]:
        """
        Level 2 - Intermediate / Smart Human:
        - Re-rolls unless already holding a strong score (>= 22 points).
        - Selects the highest scoring available category.
        """
        scored_cats = [(i, calculate_category_score(self.current_dices, i)) for i in open_cats]
        best_cat, best_score = max(scored_cats, key=lambda x: x[1])

        if self.rolled_dice_times < 3 and best_score < 22:
            held = self._choose_held_dice_indices()
            if len(held) < 5:
                return {"action": "roll", "selected_indexes": held}

        if best_score > 0:
            return {"action": "select", "index": best_cat}
        return {"action": "select", "index": open_cats[0]}

    def _compute_level_3(self, open_cats: List[int]) -> Dict[str, Any]:
        """
        Level 3 - Hard / Master:
        - Maximizes category efficiency and re-rolls strategically when best_score < 25.
        """
        scored_cats = [(i, calculate_category_score(self.current_dices, i)) for i in open_cats]
        best_cat, best_score = max(scored_cats, key=lambda x: x[1])

        if self.rolled_dice_times < 3 and best_score < 25:
            held = self._choose_held_dice_indices()
            if len(held) < 5:
                return {"action": "roll", "selected_indexes": held}

        if best_score > 0:
            # Prefer high-value special combinations over burning Chance early
            non_chance = [(i, sc) for i, sc in scored_cats if i != 8 and sc >= best_score - 3 and sc > 0]
            if non_chance:
                return {"action": "select", "index": max(non_chance, key=lambda x: x[1])[0]}
            return {"action": "select", "index": best_cat}

        # Forced to score 0: sacrifice hardest or lowest-value category first (Yatzy -> Ones -> Twos -> 4x)
        sacrifice_order = [11, 0, 1, 7, 10, 9, 2, 6, 3, 4, 5, 8]
        for s_idx in sacrifice_order:
            if s_idx in open_cats:
                return {"action": "select", "index": s_idx}
        return {"action": "select", "index": open_cats[0]}

    def build_move_command(self, move: Dict[str, Any]) -> dict:
        if move.get("action") == "roll":
            return {
                "id": "RollDice",
                "data": {"selected_indexes": list(move.get("selected_indexes", []))},
            }
        return {
            "id": "SelectPeace",
            "data": {"index": int(move.get("index", 0))},
        }

    def format_state(self) -> str:
        dices_str = " ".join(f"[{d}]" for d in self.current_dices)
        lines = [
            f"\n  ==================== YATZY (Round {self.current_round}/12 | Roll {self.rolled_dice_times}/3) ====================",
            f"  Current Dice: {dices_str} | Scores -> P1: {self.player1_score} | P2: {self.player2_score}",
            "  -------------------------------------------------------------------------",
        ]
        for i in range(12):
            status = f"LOCKED ({self.my_board_scores[i]:2d})" if self.my_board_selected[i] else f"Open (Preview: {calculate_category_score(self.current_dices, i):2d})"
            lines.append(f"    [{i:02d}] {CATEGORY_NAMES[i]:<28}: {status}")
        lines.append("  =========================================================================\n")
        return "\n".join(lines)
