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
from .four_in_row import FourInRowGameLogic
from .fekrbekr import FekrBekrGameLogic
from .yatzy import YatzyGameLogic
from .rpc import RPCGameLogic
from .backgammon import BackGammonGameLogic
from .othello import OthelloGameLogic
from .mill import MillGameLogic
from .dotbox import DotBoxGameLogic
from .mnumbers import MNumbersGameLogic
from .battleship import BattleShipGameLogic
from .sudoku import SudokuGameLogic
from .msweeper import MSweeperGameLogic

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
    name="FourInRow",
    cls=FourInRowGameLogic,
    aliases=[
        "fourinrow",
        "four_in_row",
        "four-in-a-row",
        "connect4",
        "connectfour",
        "دوز چهارتایی",
        "چهار در یک ردیف",
    ],
)

register_game(
    name="FekrBekr",
    cls=FekrBekrGameLogic,
    aliases=[
        "fekrbekr",
        "fekr_bekr",
        "mastermind",
        "فکر بکر",
        "فکربکر",
    ],
)

register_game(
    name="Yatzy",
    cls=YatzyGameLogic,
    aliases=[
        "yatzy",
        "yahtzee",
        "یاتزی",
    ],
)

register_game(
    name="RPC",
    cls=RPCGameLogic,
    aliases=[
        "rpc",
        "rockpaperscissors",
        "rock_paper_scissors",
        "سنگ کاغذ قیچی",
        "سنگ_کاغذ_قیچی",
        "rps",
    ],
)

register_game(
    name="BackGammon",
    cls=BackGammonGameLogic,
    aliases=[
        "backgammon",
        "back_gammon",
        "تخته نرد",
        "تخته‌نرد",
        "nard",
        "takhtenard",
    ],
)

register_game(
    name="Othello",
    cls=OthelloGameLogic,
    aliases=[
        "othello",
        "reversi",
        "اتللو",
        "اوتلو",
    ],
)

register_game(
    name="Mill",
    cls=MillGameLogic,
    aliases=[
        "mill",
        "nine_mens_morris",
        "ninemensmorris",
        "morris",
        "دوز نه تایی",
        "دوز نه‌تایی",
        "دوز 9 تایی",
    ],
)

register_game(
    name="DotBox",
    cls=DotBoxGameLogic,
    aliases=[
        "dotbox",
        "dot_box",
        "dotsandboxes",
        "dots_and_boxes",
        "نقطه خط",
        "نقطه‌خط",
    ],
)

register_game(
    name="MNumbers",
    cls=MNumbersGameLogic,
    aliases=[
        "mnumbers",
        "m_numbers",
        "matchnumbers",
        "match_numbers",
        "کشف اعداد",
        "کشف‌اعداد",
    ],
)

register_game(
    name="BattleShip",
    cls=BattleShipGameLogic,
    aliases=[
        "battleship",
        "battle_ship",
        "نبرد کشتی",
        "کشتی جنگی",
        "نبردکشتی",
    ],
)

register_game(
    name="Sudoku",
    cls=SudokuGameLogic,
    aliases=[
        "sudoku",
        "سودوکو",
    ],
)

register_game(
    name="MSweeper",
    cls=MSweeperGameLogic,
    aliases=[
        "msweeper",
        "minesweeper",
        "مین یاب",
        "مین‌یاب",
    ],
)

__all__ = [
    "MSweeperGameLogic",
    "SudokuGameLogic",
    "BaseGameLogic",
    "TicTacToeGameLogic",
    "ChessGameLogic",
    "CheckersGameLogic",
    "FourInRowGameLogic",
    "FekrBekrGameLogic",
    "YatzyGameLogic",
    "RPCGameLogic",
    "BackGammonGameLogic",
    "OthelloGameLogic",
    "MillGameLogic",
    "DotBoxGameLogic",
    "MNumbersGameLogic",
    "BattleShipGameLogic",
    "register_game",
    "get_game_logic",
    "list_supported_games",
]
