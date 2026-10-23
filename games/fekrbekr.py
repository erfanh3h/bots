"""
FekrBekr (Mastermind / Codebreaker) Pure Game Logic for Cafe Fekr Bots.

Decoupled game engine for the 4-peg 8-color FekrBekr game:
- Generates valid unique secret code during setup phase (SaveBoard).
- Tracks simultaneous rounds and pin feedback (Black/2: exact, White/1: color).
- Provides AI deduction across difficulty levels:
  * Level 1: Easiest (Beginner / Casual Human, imperfect deductions) [DEFAULT]
  * Level 2: Medium (Intermediate / Consistent candidate elimination)
  * Level 3: Hard (Master / Optimal candidate solver)

All bots default to level=1, and lobby bots are strictly level 1.
"""

import itertools
import random
from typing import Any, List, Optional, Tuple

from .base_game import BaseGameLogic

COLOR_NAMES = {
    1: "Red",
    2: "Blue",
    3: "Green",
    4: "Gold",
    5: "Purple",
    6: "Orange",
    7: "Cyan",
    8: "White",
}


def evaluate_feedback(secret: Tuple[int, ...], guess: List[int]) -> Tuple[int, int]:
    """
    Simulates server feedback evaluation:
    - exact: number of pegs matching both color and position (black pins / 2)
    - color: number of pegs matching color but wrong position (white pins / 1)
    """
    exact = sum(1 for i in range(4) if guess[i] == secret[i])
    color = sum(1 for g in guess if g in secret) - exact
    return exact, color


class FekrBekrGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="FekrBekr",
            game_type_aliases=["fekrbekr", "fekr", "فکربکر", "فکر بکر", "mastermind", "codebreaker"],
            level=level,  # Default level must always be 1
        )
        self.all_permutations = list(itertools.permutations(range(1, 9), 4))
        self.secret_code: List[int] = []
        self.has_saved_board: bool = False
        self.guess_history: List[dict] = []
        self.opponent_history: List[dict] = []
        self.candidates: List[Tuple[int, ...]] = []
        self.reset()

    def reset(self):
        """Resets the state for a new match/round."""
        self.secret_code = self._generate_secret_code()
        self.has_saved_board = False
        self.guess_history.clear()
        self.opponent_history.clear()
        self.candidates = list(self.all_permutations)
        self.current_round = 0

    def on_game_start(self, game_id: str):
        super().on_game_start(game_id)
        self.reset()

    def _generate_secret_code(self) -> List[int]:
        """Generates a random secret code with 4 distinct colors from 1..8."""
        return random.sample(range(1, 9), 4)

    def should_send_initial_board(self) -> bool:
        """Returns True if the bot has not yet submitted its secret code."""
        return not self.has_saved_board

    def get_initial_board_move(self) -> dict:
        """Builds the SaveBoard payload with our secret code."""
        self.has_saved_board = True
        return {
            "id": "SaveBoard",
            "data": list(self.secret_code),
        }

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes incoming server events for FekrBekr."""
        if cmd_id in ("GameData", "ReconnectData"):
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                if isinstance(g_data, dict):
                    if "current_round" in g_data:
                        self.current_round = g_data.get("current_round", 0)
                    if g_data.get("is_player_rdy", False):
                        self.has_saved_board = True
            return True

        elif cmd_id == "CurrentTurn":
            if isinstance(payload, dict) and "current_round" in payload:
                self.current_round = payload["current_round"]
            elif isinstance(payload, int):
                self.current_round = payload
            return True

        elif cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                gamer_id = payload.get("gamer_id")
                data = payload.get("data", [])
                result = payload.get("result", [])

                exact = result.count(2)
                color = result.count(1)
                miss = result.count(0)

                my_id = self.my_player_num or 2
                if gamer_id == my_id:
                    # Our guess feedback!
                    self.guess_history.append({
                        "round": self.current_round,
                        "guess": list(data),
                        "exact": exact,
                        "color": color,
                        "miss": miss,
                    })
                    # Filter candidates
                    self._filter_candidates(data, exact, color)
                else:
                    # Opponent guess feedback
                    self.opponent_history.append({
                        "round": self.current_round,
                        "guess": list(data),
                        "exact": exact,
                        "color": color,
                        "miss": miss,
                    })
            return True

        return False

    def _filter_candidates(self, guess: List[int], exact: int, color: int):
        """Prunes candidate pool to only those consistent with feedback."""
        if not guess or len(guess) != 4:
            return

        self.candidates = [
            c for c in self.candidates
            if evaluate_feedback(c, guess) == (exact, color)
        ]

    def get_legal_moves(self) -> List[List[int]]:
        """Returns candidate pool or fallback sample."""
        if self.candidates:
            return [list(c) for c in self.candidates]
        return [list(c) for c in self.all_permutations]

    def is_critical_turn(self) -> bool:
        """
        Returns True if we are very close to solving (e.g. 3 exact pins)
        or nearing maximum rounds (round >= 10).
        """
        if self.guess_history:
            last = self.guess_history[-1]
            if last["exact"] == 3:
                return True
        if self.current_round >= 10:
            return True
        return False

    def compute_next_move(self) -> List[int]:
        """Computes the next guess based on difficulty level (1, 2, 3)."""
        if self.level == 1:
            return self._compute_level_1()
        elif self.level == 2:
            return self._compute_level_2()
        else:
            return self._compute_level_3()

    def _compute_level_1(self) -> List[int]:
        """
        Level 1 - Beginner / Casual Human:
        - Novice deduction: occasionally preserves known colors, but often makes exploratory or imperfect guesses.
        - Has a 40% chance to pick from the consistent candidate pool, and 60% chance to pick a casual random permutation.
        - Cracks the code slowly (9-12 rounds) or runs out of turns, giving the user a great chance to win.
        """
        if self.current_round == 1:
            return random.sample(range(1, 9), 4)

        # 40% chance to make an intelligent deduction from candidates
        if self.candidates and random.random() < 0.40:
            return list(random.choice(self.candidates))

        # Partial memory simulation: keep 1 or 2 colors from best previous guess
        if self.guess_history:
            best_guess = max(self.guess_history, key=lambda g: g["exact"] * 2 + g["color"])
            if best_guess["exact"] + best_guess["color"] > 0:
                retained_colors = random.sample(best_guess["guess"], min(2, len(best_guess["guess"])))
                other_pool = [c for c in range(1, 9) if c not in retained_colors]
                needed = 4 - len(retained_colors)
                new_guess = retained_colors + random.sample(other_pool, needed)
                random.shuffle(new_guess)
                return new_guess

        return random.sample(range(1, 9), 4)

    def _compute_level_2(self) -> List[int]:
        """
        Level 2 - Intermediate / Smart Human:
        - Strictly consistent with feedback 80% of the time.
        - Typically solves in 6-8 rounds.
        """
        if self.current_round == 1:
            return [1, 2, 3, 4]

        if self.candidates:
            if random.random() < 0.85:
                return list(random.choice(self.candidates))
            else:
                return list(self.candidates[0])

        return random.sample(range(1, 9), 4)

    def _compute_level_3(self) -> List[int]:
        """
        Level 3 - Hard / Master:
        - Optimal candidate solver.
        - Evaluates candidate pool to maximize information gain.
        - Cracks the code in 4-5 rounds.
        """
        if self.current_round == 1:
            return [1, 2, 3, 4]

        if not self.candidates:
            return random.sample(range(1, 9), 4)

        if len(self.candidates) <= 2:
            return list(self.candidates[0])

        # Minimax: pick the guess that minimizes the worst-case remaining candidate count
        sample_pool = self.candidates[:25] if len(self.candidates) > 25 else self.candidates
        best_guess = list(self.candidates[0])
        min_max_remaining = float("inf")

        for guess in sample_pool:
            counts = {}
            for cand in self.candidates:
                fb = evaluate_feedback(cand, list(guess))
                counts[fb] = counts.get(fb, 0) + 1
            max_remaining = max(counts.values()) if counts else 0
            if max_remaining < min_max_remaining:
                min_max_remaining = max_remaining
                best_guess = list(guess)

        return best_guess

    def build_move_command(self, move: List[int]) -> dict:
        """Builds server command dict for FekrBekr guess."""
        return {
            "id": "SelectPeace",
            "data": list(move),
        }

    def format_state(self) -> str:
        """Returns clean ASCII board representation for terminal logs."""
        code_str = " ".join(f"{c}({COLOR_NAMES.get(c, '?')[:3]})" for c in self.secret_code)
        lines = [
            f"\n  ==================== FEKR BEKR (Round {self.current_round}/12) ====================",
            f"  My Secret Code: [ {code_str} ]",
            "  -----------------------------------------------------------------------",
        ]

        if self.guess_history:
            lines.append("  My Guesses History:")
            for item in self.guess_history:
                g_str = "-".join(str(x) for x in item["guess"])
                names = " ".join(COLOR_NAMES.get(x, "?")[:3] for x in item["guess"])
                pins = "●" * item["exact"] + "○" * item["color"] + "·" * item["miss"]
                lines.append(
                    f"    R{item['round']:02d}: [{g_str}] ({names:<16}) -> Pins: {pins:<4} "
                    f"({item['exact']} Exact, {item['color']} Color)"
                )
        else:
            lines.append("  No guesses recorded yet.")

        lines.append(f"  Remaining Candidates: {len(self.candidates)}")
        lines.append("  =======================================================================\n")
        return "\n".join(lines)
