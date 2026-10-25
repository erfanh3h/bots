"""
Games Registry and Factory for Cafe Fekr Bots.

Provides decoupling between matchmaking modes (Lobby, Rank) and specific game engines.
New games can be registered here and instantly used by all bot drivers.
"""

from typing import Dict, List, Optional, Type
from .base_game import BaseGameLogic
from .tictactoe import TicTacToeGameLogic
from .chess import ChessGameLogic
from .checkers import CheckersGameLogic
from .fekrbekr import FekrBekrGameLogic
from .yatzy import YatzyGameLogic

_GAME_REGISTRY: Dict[str, Type[BaseGameLogic]] = {}
_ALIAS_MAP: Dict[str, str] = {}


def register_game(
    name: str,
    cls: Type[BaseGameLogic],
    aliases: Optional[List[str]] = None,
):
    """Registers a game logic engine."""
    canonical = name.strip().lower()
    _GAME_REGISTRY[canonical] = cls
    _ALIAS_MAP[canonical] = canonical
    if aliases:
        for alias in aliases:
            _ALIAS_MAP[alias.strip().lower()] = canonical


def get_game_logic(game_type: str, level: int = 1) -> BaseGameLogic:
    """
    Factory function that creates and returns a game logic instance.
    Defaults to level=1 (easiest/beginner).
    """
    if not game_type:
        return TicTacToeGameLogic(level=1)

    key = str(game_type).strip().lower()
    canonical = _ALIAS_MAP.get(key, key)

    if canonical in _GAME_REGISTRY:
        cls = _GAME_REGISTRY[canonical]
        return cls(level=level)

    for alias, canon in _ALIAS_MAP.items():
        if alias in key or key in alias:
            return _GAME_REGISTRY[canon](level=level)

    raise ValueError(
        f"Game type '{game_type}' is not supported yet. "
        f"Registered games: {list(_GAME_REGISTRY.keys())}"
    )


def list_supported_games() -> List[str]:
    """Returns a list of all registered canonical game names."""
    return list(_GAME_REGISTRY.keys())


# Register built-in games
register_game(
    name="TicTacToe",
    cls=TicTacToeGameLogic,
    aliases=["tictactoe", "دوز", "tic", "ttt"],
)

register_game(
    name="Chess",
    cls=ChessGameLogic,
    aliases=["chess", "شطرنج", "satranj"],
)

register_game(
    name="Checkers",
    cls=CheckersGameLogic,
    aliases=["checkers", "چکرز", "dama", "draughts"],
)

register_game(
    name="FekrBekr",
    cls=FekrBekrGameLogic,
    aliases=["fekrbekr", "fekrobekr", "mastermind", "فکربکر", "فکر بکر"],
)

register_game(
    name="Yatzy",
    cls=YatzyGameLogic,
    aliases=["yatzy", "yahtzee", "یاتزی", "پنج تاس"],
)

__all__ = [
    "BaseGameLogic",
    "TicTacToeGameLogic",
    "ChessGameLogic",
    "CheckersGameLogic",
    "FekrBekrGameLogic",
    "YatzyGameLogic",
    "register_game",
    "get_game_logic",
    "list_supported_games",
]
