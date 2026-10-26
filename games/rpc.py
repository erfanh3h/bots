"""
Rock Paper Scissors (RPC / سنگ کاغذ قیچی) Pure Game Logic for Cafe Fekr Bots.
Decoupled game engine containing rules, round/turn-round scoring parity with backend
RPCGameClass, and human-like strategic move generation across difficulty levels:
- Level 1: Beginner / Casual Human (Rock opening bias, Win-Stay Lose-Shift, prone to patterns).
- Level 2: Intermediate / Tactical (Counters Win-Stay Lose-Shift, tracks opponent frequency).
- Level 3: Master / Markov Transition Predictor (Conditional probability matrix + Nash equilibrium).
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


class RPCGameLogic(BaseGameLogic):
    ROCK = "rock"
    PAPER = "paper"
    CUTTER = "cutter"

    CHOICES = [ROCK, PAPER, CUTTER]

    # BEATS[a] gives the move that 'a' defeats
    BEATS = {
        ROCK: CUTTER,
        CUTTER: PAPER,
        PAPER: ROCK,
    }

    # BEATEN_BY[a] gives the move that defeats 'a'
    BEATEN_BY = {
        CUTTER: ROCK,
        PAPER: CUTTER,
        ROCK: PAPER,
    }

    CLOCKWISE_SHIFT = {
        ROCK: PAPER,
        PAPER: CUTTER,
        CUTTER: ROCK,
    }

    def __init__(self, level: int = 1):
        super().__init__(
            game_type="RPC",
            game_type_aliases=[
                "rpc",
                "rockpaperscissors",
                "rock_paper_scissors",
                "سنگ کاغذ قیچی",
                "سنگ_کاغذ_قیچی",
                "rps",
            ],
            level=level,
        )
        self.round_scores: List[int] = [0, 0]  # [P1, P2] turn-round wins in current round
        self.total_scores: List[int] = [0, 0]  # [P1, P2] match round wins (first to 2)
        self.current_turn_round: int = 1
        self.history: List[Dict[str, Any]] = []
        self.last_selected_move: Optional[str] = None
        self._last_clash_info: Optional[Dict[str, Any]] = None

    def reset(self):
        """Resets round state for a new round."""
        self.round_scores = [0, 0]
        self.current_turn_round = 1
        self.last_selected_move = None

    def on_game_start(self, game_id: str):
        super().on_game_start(game_id)
        self.round_scores = [0, 0]
        self.total_scores = [0, 0]
        self.current_turn_round = 1
        self.history.clear()
        self.last_selected_move = None
        self._last_clash_info = None

    def on_new_round(self, round_num: int):
        super().on_new_round(round_num)
        self.reset()

    def on_round_finished(self, winner: int):
        super().on_round_finished(winner)
        if winner in (1, 2):
            self.total_scores[winner - 1] += 1

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Processes server events for RPC game state."""
        if cmd_id == "GameData":
            if isinstance(payload, dict):
                if "round_scores" in payload and isinstance(payload["round_scores"], list):
                    self.round_scores = list(payload["round_scores"])
                if "total_scores" in payload and isinstance(payload["total_scores"], list):
                    self.total_scores = list(payload["total_scores"])
                if "current_round" in payload:
                    self.current_round = int(payload["current_round"])
                if "current_turn__round" in payload:
                    self.current_turn_round = int(payload["current_turn__round"])
            return True

        elif cmd_id == "NewTurnRound":
            self.last_selected_move = None
            return True

        elif cmd_id == "FinishTurnRound":
            if isinstance(payload, dict):
                winner = payload.get("Winner", 0)
                p1_sel = str(payload.get("P1_selection", "")).lower()
                p2_sel = str(payload.get("P2_selection", "")).lower()

                if p1_sel in self.CHOICES and p2_sel in self.CHOICES:
                    my_role = self.my_player_num if self.my_player_num in (1, 2) else 2
                    my_move = p1_sel if my_role == 1 else p2_sel
                    opp_move = p2_sel if my_role == 1 else p1_sel

                    # Determine result from bot's perspective: 1 = win, -1 = loss, 0 = tie
                    if winner == my_role:
                        res = 1
                    elif winner == 0:
                        res = 0
                    else:
                        res = -1

                    clash = {
                        "round": self.current_round,
                        "turn_round": self.current_turn_round,
                        "p1_move": p1_sel,
                        "p2_move": p2_sel,
                        "my_move": my_move,
                        "opp_move": opp_move,
                        "winner": winner,
                        "bot_result": res,
                    }
                    self.history.append(clash)
                    self._last_clash_info = clash

                if winner in (1, 2):
                    self.round_scores[winner - 1] += 1
                self.current_turn_round += 1
            return True

        elif cmd_id == "FinishRound":
            winner = payload.get("Winner", 0) if isinstance(payload, dict) else payload
            if winner in (1, 2):
                self.total_scores[winner - 1] += 1
            return True

        return False

    def get_legal_moves(self) -> List[str]:
        return list(self.CHOICES)

    def is_critical_turn(self) -> bool:
        """
        Critical turn triggers hesitation simulation when:
        - Match point or game deciding round
        - Turn round >= 4
        - Someone is 1 win away from taking the round
        """
        my_role = self.my_player_num if self.my_player_num in (1, 2) else 2
        opp_role = 2 if my_role == 1 else 1

        my_r_score = self.round_scores[my_role - 1]
        opp_r_score = self.round_scores[opp_role - 1]

        if my_r_score == 2 or opp_r_score == 2:
            return True
        if self.current_turn_round >= 4:
            return True
        if self.total_scores[0] == 1 and self.total_scores[1] == 1:
            return True
        return False

    def compute_next_move(self) -> str:
        """Computes move based on bot difficulty level (1=casual, 2=tactical, 3=master)."""
        if self.level == 1:
            move = self._compute_level_1()
        elif self.level == 2:
            move = self._compute_level_2()
        else:
            move = self._compute_level_3()

        self.last_selected_move = move
        return move

    # -------------------------------------------------------------------------
    # Level 1: Beginner / Casual Human (Prone to Natural Human Cognitive Biases)
    # -------------------------------------------------------------------------
    def _compute_level_1(self) -> str:
        # Opening turn of match: human rock opening bias (~45% Rock, 30% Scissors, 25% Paper)
        if not self.history:
            return random.choices(
                [self.ROCK, self.CUTTER, self.PAPER],
                weights=[0.45, 0.30, 0.25],
                k=1,
            )[0]

        last = self.history[-1]
        res = last["bot_result"]  # 1: win, -1: loss, 0: tie
        my_prev = last["my_move"]
        opp_prev = last["opp_move"]

        # Classic "Win-Stay, Lose-Shift" psychology (Wang et al., Nature 2014)
        if res == 1:
            # Beginner won last round: ~60% probability of repeating winning hand
            if random.random() < 0.60:
                return my_prev
            return random.choice(self.CHOICES)

        elif res == -1:
            # Beginner lost last round: ~65% probability of shifting to the hand that beats what opponent threw
            if random.random() < 0.65:
                return self.BEATEN_BY.get(opp_prev, random.choice(self.CHOICES))
            return random.choice(self.CHOICES)

        else:
            # Tie: ~50% probability of shifting clockwise (Rock -> Paper -> Scissors -> Rock)
            if random.random() < 0.50:
                return self.CLOCKWISE_SHIFT.get(my_prev, random.choice(self.CHOICES))
            return random.choice(self.CHOICES)

    # -------------------------------------------------------------------------
    # Level 2: Intermediate / Tactical (Counters Win-Stay & Tracks Frequency)
    # -------------------------------------------------------------------------
    def _compute_level_2(self) -> str:
        if not self.history:
            # Counters the human opening Rock bias by leading with Paper
            return random.choices(
                [self.PAPER, self.ROCK, self.CUTTER],
                weights=[0.60, 0.25, 0.15],
                k=1,
            )[0]

        last = self.history[-1]
        opp_prev = last["opp_move"]
        bot_prev = last["my_move"]
        res = last["bot_result"]

        # 1. Counter opponent's Win-Stay:
        # If opponent won (bot lost), opponent will likely repeat opp_prev. Counter it!
        if res == -1 and random.random() < 0.65:
            predicted_opp_move = opp_prev
            return self.BEATEN_BY[predicted_opp_move]

        # 2. Counter opponent's Lose-Shift:
        # If opponent lost (bot won), opponent will likely switch to beat bot_prev (BEATEN_BY[bot_prev]).
        # Anticipate that and beat their counter!
        if res == 1 and random.random() < 0.65:
            expected_opp_shift = self.BEATEN_BY[bot_prev]
            return self.BEATEN_BY[expected_opp_shift]

        # 3. Frequency Analysis over recent history
        opp_moves = [h["opp_move"] for h in self.history[-8:]]
        counts = {c: opp_moves.count(c) for c in self.CHOICES}
        most_common = max(counts, key=counts.get)
        if counts[most_common] >= len(opp_moves) * 0.45:
            # Opponent is noticeably favoring one hand; play its counter
            return self.BEATEN_BY[most_common]

        return random.choice(self.CHOICES)

    # -------------------------------------------------------------------------
    # Level 3: Master / Markov Transition Matrix + Nash Equilibrium
    # -------------------------------------------------------------------------
    def _compute_level_3(self) -> str:
        if len(self.history) < 2:
            return self._compute_level_2()

        # Build 1st-order Markov transition counts: (opp_prev_move, bot_result) -> opp_next_move
        transitions: Dict[Tuple[str, int], Dict[str, int]] = {}
        for i in range(len(self.history) - 1):
            curr = self.history[i]
            nxt = self.history[i + 1]
            state = (curr["opp_move"], curr["bot_result"])
            if state not in transitions:
                transitions[state] = {c: 0 for c in self.CHOICES}
            transitions[state][nxt["opp_move"]] += 1

        last = self.history[-1]
        current_state = (last["opp_move"], last["bot_result"])

        if current_state in transitions:
            state_counts = transitions[current_state]
            total = sum(state_counts.values())
            if total >= 2:
                # Calculate expected utility for each candidate move
                # Payoff matrix: win=+1, tie=0, loss=-1
                probs = {c: state_counts[c] / total for c in self.CHOICES}
                best_move = self.ROCK
                best_utility = -999.0
                for candidate in self.CHOICES:
                    # Utility of candidate = P(opp plays move candidate beats) * 1 - P(opp plays move that beats candidate) * 1
                    winning_against = self.BEATS[candidate]
                    losing_against = self.BEATEN_BY[candidate]
                    utility = probs[winning_against] - probs[losing_against]
                    if utility > best_utility:
                        best_utility = utility
                        best_move = candidate
                return best_move

        # Fallback to balanced Nash with anti-frequency bias
        opp_moves = [h["opp_move"] for h in self.history]
        counts = {c: opp_moves.count(c) for c in self.CHOICES}
        total_m = len(opp_moves)
        if total_m > 0:
            # Slightly favor countering their highest frequency move
            weights = [
                1.0 + (counts[self.BEATS[c]] / total_m) for c in self.CHOICES
            ]
            return random.choices(self.CHOICES, weights=weights, k=1)[0]

        return random.choice(self.CHOICES)

    def build_move_command(self, move: str) -> dict:
        return {
            "id": "SelectPeace",
            "data": move,
        }

    def format_state(self) -> str:
        my_role = self.my_player_num if self.my_player_num in (1, 2) else 2
        opp_role = 2 if my_role == 1 else 1

        p1_r = self.round_scores[0]
        p2_r = self.round_scores[1]
        p1_m = self.total_scores[0]
        p2_m = self.total_scores[1]

        def gems(score: int) -> str:
            return "● " * score + "○ " * max(0, 3 - score)

        clash_str = "No clash yet"
        if self._last_clash_info:
            c = self._last_clash_info
            w_str = f"Player {c['winner']}" if c["winner"] in (1, 2) else "Tie"
            clash_str = f"P1 ({c['p1_move']}) vs P2 ({c['p2_move']}) -> {w_str}"

        return (
            f"\n┌────────────────────────────────────────────────────────┐\n"
            f"│  Rock-Paper-Scissors (Round {self.current_round}/3, Turn-Round {self.current_turn_round}/5)    │\n"
            f"│  Match Score: P1 {p1_m} - {p2_m} P2                              │\n"
            f"│  Turn-Round Gems: P1 [{gems(p1_r).strip()}] vs P2 [{gems(p2_r).strip()}]        │\n"
            f"│  Last Clash: {clash_str:<40}  │\n"
            f"└────────────────────────────────────────────────────────┘\n"
        )
