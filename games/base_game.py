"""
Abstract Base Game Logic for Cafe Fekr.

Pure game logic engine decoupled from networking, websockets, and matchmaking.
Any game (TicTacToe, Othello, Chess, FourInRow, etc.) extends this class.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class BaseGameLogic(ABC):
    """
    Abstract interface for pure game logic and decision-making.
    
    Difficulty levels:
        - 1: Easiest (Beginner / Casual human, prone to mistakes). [DEFAULT]
        - 2: Medium (Intermediate / Tactical player).
        - 3: Hard (Master / Optimal or Minimax search).
    """

    def __init__(
        self,
        game_type: str = "Unknown",
        game_type_aliases: Optional[List[str]] = None,
        level: int = 1,
    ):
        self.game_type = game_type
        self.game_type_aliases = [
            a.lower() for a in (game_type_aliases or [game_type])
        ]
        self._level = self._validate_level(level)
        self.my_player_num: Optional[int] = None
        self.is_game_active: bool = False
        self.current_round: int = 1

    @staticmethod
    def _validate_level(level: int) -> int:
        if level not in (1, 2, 3):
            # Fallback to level 1 default
            print(f"[Warning] Invalid level {level}. Setting to default level 1.")
            return 1
        return level

    @property
    def level(self) -> int:
        return self._level

    @level.setter
    def level(self, value: int):
        self._level = self._validate_level(value)

    def set_player_role(self, player_num: int):
        self.my_player_num = player_num

    def matches_game_type(self, target_game_type: str) -> bool:
        """Checks if a string (e.g. from a room or queue) matches this game."""
        if not target_game_type:
            return True
        norm = str(target_game_type).strip().lower()
        if norm == "" or norm == self.game_type.lower():
            return True
        for alias in self.game_type_aliases:
            if alias in norm or norm in alias:
                return True
        return False

    @abstractmethod
    def reset(self):
        """Resets the game state for a new round/match."""
        pass

    def on_game_start(self, game_id: str):
        """Called when a match session begins."""
        self.is_game_active = True
        self.current_round = 1
        self.reset()

    def on_new_round(self, round_num: int):
        """Called when a new round in a match begins."""
        self.current_round = round_num
        self.reset()

    def on_round_finished(self, winner: int):
        """Called when a round finishes."""
        pass

    def on_game_finished(self, winner: int):
        """Called when the entire match concludes."""
        self.is_game_active = False

    @abstractmethod
    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """
        Parses incoming game state commands (e.g., GameData, PeaceSelected).
        Returns True if the command was recognized and handled.
        """
        pass

    @abstractmethod
    def get_legal_moves(self) -> List[Any]:
        """Returns list of valid moves given the current state."""
        pass

    def is_critical_turn(self) -> bool:
        """
        Determines if the current turn has a critical tactical opportunity
        (e.g., an immediate win or blocking an opponent win).
        Used by the human simulator to add natural hesitation/double-checking.
        """
        return False

    @abstractmethod
    def compute_next_move(self) -> Any:
        """
        Computes the bot's next move using the algorithm corresponding
        to self.level (1 = easiest, 2 = medium, 3 = hard).
        """
        pass

    @abstractmethod
    def build_move_command(self, move: Any) -> dict:
        """
        Serializes the selected move into the server command dictionary.
        Example: {"id": "SelectPeace", "data": cell_index}
        """
        pass

    def format_state(self) -> str:
        """Returns a string representation of the current game state."""
        return f"{self.game_type} (Round {self.current_round})"
