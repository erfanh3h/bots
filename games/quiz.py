import random
from typing import Any, List, Optional
from .base_game import BaseGameLogic


class QuizGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Quiz",
            game_type_aliases=["quiz", "کوییز", "مسابقه", "اطلاعات عمومی"],
            level=level,
        )
        self.current_turn: int = 1
        self.total_questions: int = 10
        self.has_answered_current_turn: bool = False

    def reset(self):
        self.current_turn = 1
        self.has_answered_current_turn = False

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "CurrentTurn":
            if isinstance(payload, dict):
                self.current_turn = int(payload.get("turn", self.current_turn))
                self.total_questions = int(payload.get("total_questions", 10))
            self.has_answered_current_turn = False
            return True
        elif cmd_id == "FinishTurnRound":
            self.has_answered_current_turn = True
            return True
        return False

    def get_legal_moves(self) -> List[int]:
        if self.has_answered_current_turn:
            return []
        return [1, 2, 3, 4]

    def compute_next_move(self) -> Optional[int]:
        if self.has_answered_current_turn:
            return None
        self.has_answered_current_turn = True
        return random.choice([1, 2, 3, 4])

    def build_move_command(self, move: Any) -> dict:
        return {"id": "SelectPeace", "data": {"option": move}}
