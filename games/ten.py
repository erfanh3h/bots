"""
Ten (Make 10 / 4=10 / ده بساز) Game Logic & Multi-Level AI Engine.

Matches exact rules and protocol of `TenGameClass` and `TenGameSession`
in `kafehfekrbackend`:
- Simultaneous 3-round puzzle match (`max_rounds = 3`, first to 2 round wins or 3 rounds played).
- Server sends `CurrentTurn` with `[n1, n2, n3, n4]` (4 integers from `ten_games_list`).
- Players construct an arithmetic expression using all 4 numbers, 3 binary operators (`+`, `-`, `*`, `/`),
  and optional parentheses `( ... )` that evaluates to `10`.
- When solved, client emits `{"id": "Solve", "data": ""}`.
- Server responds with `FinishRound` (`{"Winner": round_winner}`), pauses 5s (`Ten_Sleep_Round_Time`),
  and advances to the next round (`NewRound` + `CurrentTurn`) or concludes the match (`FinishGame`).

Difficulty Levels:
- Level 1 (Beginner / Casual Human):
  Solves the 4=10 equation in ~18.0–28.0 seconds, giving human players a comfortable window to experiment
  with tile swaps, operators, and brackets.
- Level 2 (Intermediate / Fast Solver):
  Solves the 4=10 equation in ~11.0–17.5 seconds.
- Level 3 (Master / Mental Math Prodigy):
  Solves the 4=10 equation in ~6.0–10.5 seconds.
"""

import itertools
import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


class TenGameLogic(BaseGameLogic):
    OPERATORS = ["+", "-", "*", "/"]

    def __init__(self, level: int = 1):
        super().__init__(game_type="Ten", level=level)
        self.current_numbers: List[int] = []
        self.solved_expression: str = ""
        self.gamer1_score: int = 0
        self.gamer2_score: int = 0
        self.round_active: bool = False
        self.round_solved_by_bot: bool = False

    def reset(self):
        self.reset_board()

    def reset_board(self):
        self.current_numbers = []
        self.solved_expression = ""
        self.round_active = False
        self.round_solved_by_bot = False

    def on_new_round(self, round_num: int):
        self.current_round = int(round_num)
        self.reset_board()

    def on_round_finished(self, winner: Any):
        self.round_active = False
        self.round_solved_by_bot = True
        w = winner.get("Winner", 0) if isinstance(winner, dict) else int(winner or 0)
        if w == 1:
            self.gamer1_score += 1
        elif w == 2:
            self.gamer2_score += 1

    def is_round_still_active(self, expected_round: int) -> bool:
        return (
            self.round_active
            and not self.round_solved_by_bot
            and self.current_round == expected_round
            and len(self.current_numbers) == 4
        )

    def should_act_on_reconnect(self) -> bool:
        return self.round_active and not self.round_solved_by_bot and len(self.current_numbers) == 4

    def get_custom_thinking_delay(self) -> float:
        """
        Human-like 4=10 puzzle solving time based on bot level and puzzle complexity.
        """
        # Simpler puzzles (where direct sum a+b+c+d == 10 or simple +/- works) are solved slightly faster
        is_easy_puzzle = False
        if len(self.current_numbers) == 4:
            if sum(self.current_numbers) == 10:
                is_easy_puzzle = True

        if self.level <= 1:
            base = random.uniform(16.5, 25.0) if is_easy_puzzle else random.uniform(19.5, 28.5)
        elif self.level == 2:
            base = random.uniform(10.0, 15.0) if is_easy_puzzle else random.uniform(12.5, 18.0)
        else:
            base = random.uniform(5.5, 8.5) if is_easy_puzzle else random.uniform(7.0, 11.0)
        return round(base, 2)

    # ------------------------------------------------------------------ #
    # Server Command Synchronization
    # ------------------------------------------------------------------ #

    def handle_server_command(self, cmd_id: str, payload: Any):
        if cmd_id == "CurrentTurn":
            nums = []
            if isinstance(payload, list) and len(payload) >= 4:
                nums = [int(x) for x in payload[:4]]
            elif isinstance(payload, dict) and "numbers" in payload:
                raw = payload["numbers"]
                if isinstance(raw, list) and len(raw) >= 4:
                    nums = [int(x) for x in raw[:4]]
            if len(nums) == 4:
                self.current_numbers = nums
                self.solved_expression = self.solve_four_equals_ten(nums) or f"{nums[0]} + {nums[1]} + {nums[2]} + {nums[3]} = 10"
                self.round_active = True
                self.round_solved_by_bot = False

        elif cmd_id == "ReconnectData" and isinstance(payload, dict):
            g_data = payload.get("game_data", payload)
            if isinstance(g_data, dict):
                if "current_round" in g_data:
                    self.current_round = max(1, int(g_data["current_round"]))
                scores = g_data.get("scores", [])
                if isinstance(scores, list) and len(scores) >= 2:
                    self.gamer1_score = int(scores[0])
                    self.gamer2_score = int(scores[1])
                nums = g_data.get("current_numbers", [])
                if isinstance(nums, list) and len(nums) >= 4:
                    self.current_numbers = [int(x) for x in nums[:4]]
                    self.solved_expression = self.solve_four_equals_ten(self.current_numbers) or "Solve"
                    self.round_active = True
                    self.round_solved_by_bot = False

    # ------------------------------------------------------------------ #
    # 4=10 Exact Arithmetic Solver
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_op(a: Optional[float], op: str, b: Optional[float]) -> Optional[float]:
        if a is None or b is None:
            return None
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if abs(b) < 1e-9:
                return None
            return a / b
        return None

    @classmethod
    def _eval_linear(cls, vals: List[float], ops: List[str]) -> Optional[float]:
        nums = list(vals)
        operators = list(ops)
        i = 0
        while i < len(operators):
            if operators[i] in ("*", "/"):
                res = cls._apply_op(nums[i], operators[i], nums[i + 1])
                if res is None:
                    return None
                nums[i] = res
                nums.pop(i + 1)
                operators.pop(i)
            else:
                i += 1
        result = nums[0]
        for j, op in enumerate(operators):
            result = cls._apply_op(result, op, nums[j + 1])
            if result is None:
                return None
        return result

    @classmethod
    def _eval_with_bracket(
        cls, n: Tuple[int, int, int, int], ops: Tuple[str, str, str], bracket_mode: int, sign0: int = 1
    ) -> Optional[float]:
        v = [float(n[0] * sign0), float(n[1]), float(n[2]), float(n[3])]
        o = list(ops)
        if bracket_mode == 0:
            return cls._eval_linear(v, o)
        elif bracket_mode == 1:
            sub = cls._eval_linear([v[0], v[1]], [o[0]])
            return cls._eval_linear([sub, v[2], v[3]], [o[1], o[2]]) if sub is not None else None
        elif bracket_mode == 2:
            sub = cls._eval_linear([v[1], v[2]], [o[1]])
            return cls._eval_linear([v[0], sub, v[3]], [o[0], o[2]]) if sub is not None else None
        elif bracket_mode == 3:
            sub = cls._eval_linear([v[2], v[3]], [o[2]])
            return cls._eval_linear([v[0], v[1], sub], [o[0], o[1]]) if sub is not None else None
        elif bracket_mode == 4:
            sub = cls._eval_linear([v[0], v[1], v[2]], [o[0], o[1]])
            return cls._eval_linear([sub, v[3]], [o[2]]) if sub is not None else None
        elif bracket_mode == 5:
            sub = cls._eval_linear([v[1], v[2], v[3]], [o[1], o[2]])
            return cls._eval_linear([v[0], sub], [o[0]]) if sub is not None else None
        return None

    @classmethod
    def _format_expr(
        cls, n: Tuple[int, int, int, int], ops: Tuple[str, str, str], bracket_mode: int, sign0: int = 1
    ) -> str:
        n0 = f"-{n[0]}" if sign0 < 0 else str(n[0])
        n1, n2, n3 = str(n[1]), str(n[2]), str(n[3])
        o0, o1, o2 = ops
        if bracket_mode == 1:
            return f"({n0} {o0} {n1}) {o1} {n2} {o2} {n3} = 10"
        if bracket_mode == 2:
            return f"{n0} {o0} ({n1} {o1} {n2}) {o2} {n3} = 10"
        if bracket_mode == 3:
            return f"{n0} {o0} {n1} {o1} ({n2} {o2} {n3}) = 10"
        if bracket_mode == 4:
            return f"({n0} {o0} {n1} {o1} {n2}) {o2} {n3} = 10"
        if bracket_mode == 5:
            return f"{n0} {o0} ({n1} {o1} {n2} {o2} {n3}) = 10"
        return f"{n0} {o0} {n1} {o1} {n2} {o2} {n3} = 10"

    @classmethod
    def solve_four_equals_ten(cls, numbers: List[int]) -> Optional[str]:
        """
        Finds a valid 4=10 arithmetic expression using a permutation of `numbers`,
        3 operators (`+`, `-`, `*`, `/`), and at most one pair of parentheses.
        """
        if len(numbers) != 4:
            return None
        seen_perms = set()
        for perm in itertools.permutations(numbers):
            if perm in seen_perms:
                continue
            seen_perms.add(perm)
            for sign0 in (1, -1):
                for ops in itertools.product(cls.OPERATORS, repeat=3):
                    for b_mode in range(6):
                        val = cls._eval_with_bracket(perm, ops, b_mode, sign0)
                        if val is not None and abs(val - 10.0) < 1e-6:
                            return cls._format_expr(perm, ops, b_mode, sign0)
        return None

    # ------------------------------------------------------------------ #
    # Move Generation & Command Formatting
    # ------------------------------------------------------------------ #

    def get_legal_moves(self) -> List[Any]:
        if not self.round_active or self.round_solved_by_bot or len(self.current_numbers) != 4:
            return []
        return [""]

    def compute_next_move(self) -> Any:
        if not self.round_active or self.round_solved_by_bot or len(self.current_numbers) != 4:
            return None
        self.round_solved_by_bot = True
        self.round_active = False
        print(f"[Ten Bot] Solved 4=10 Puzzle: {self.solved_expression}")
        return ""

    def build_move_command(self, move: Any) -> Dict[str, Any]:
        return {
            "id": "Solve",
            "data": "",
        }

    def format_state(self) -> str:
        return (
            f"   [Ten 4=10] Round: {self.current_round}/3 | Scores: P1={self.gamer1_score}, P2={self.gamer2_score} | "
            f"Numbers: {self.current_numbers} | Solution: {self.solved_expression}"
        )
