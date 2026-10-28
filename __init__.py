"""
Bots Package for Cafe Fekr.

Modular architecture separating:
1. Pure Game Logics (bots.games)
2. Human Simulation (bots.behavior)
3. Matchmaking Drivers (bots.modes: LobbyBot, RankBot, GameSession)
"""

from .config import BOT_PHONE, BOT_USER_ID, get_auth_token
from .behavior import HumanBehavior
from .games import (
    BaseGameLogic,
    TicTacToeGameLogic,
    ChessGameLogic,
    FekrBekrGameLogic,
    BattleShipGameLogic,
    get_game_logic,
    register_game,
)
from .modes import GameSession, LobbyBot, RankBot

# Backward-compatibility & convenience aliases
BaseGameBot = LobbyBot
TicTacToeBot = lambda **kw: LobbyBot("TicTacToe", **kw)
ChessBot = lambda **kw: LobbyBot("Chess", **kw)
FekrBekrBot = lambda **kw: LobbyBot("FekrBekr", **kw)
BattleShipBot = lambda **kw: LobbyBot("BattleShip", **kw)

__all__ = [
    "BOT_PHONE",
    "BOT_USER_ID",
    "get_auth_token",
    "HumanBehavior",
    "BaseGameLogic",
    "TicTacToeGameLogic",
    "ChessGameLogic",
    "FekrBekrGameLogic",
    "get_game_logic",
    "register_game",
    "GameSession",
    "LobbyBot",
    "RankBot",
    "BaseGameBot",
    "TicTacToeBot",
    "ChessBot",
    "FekrBekrBot",
    "BattleShipGameLogic",
    "BattleShipBot",
]
