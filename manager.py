"""
Bot Manager and Orchestration Engine for Cafe Fekr Bots.

Manages the lifecycle of LobbyBots, RankBots, MultiRankBots, and SocialBots.
Provides centralized logging, status tracking, health monitoring, and Web Admin API bindings.
"""

import asyncio
import datetime
import os
import sys
import time
import traceback
import urllib.request
import json
from typing import Any, Callable, Dict, List, Optional, Set

from bots.config import (
    SERVER_REST_URL,
    SERVER_WS_URL,
    BOT_PHONE,
    BOT_USER_ID,
    get_auth_token,
)
from bots.games import get_game_logic, list_supported_games
from bots.modes.lobby_bot import LobbyBot
from bots.modes.rank_bot import RankBot, TWO_PLAYER_GAMES
from bots.modes.multi_rank_bot import MultiRankBot
from bots.social.auth_helper import RealUserManager, REAL_USER_PROFILES
from bots.social.social_bot import SocialBot
from bots.social.runner import run_peer_flow_test

# 25 Games rich metadata catalog
GAME_METADATA: Dict[str, Dict[str, Any]] = {
    "tictactoe": {"name": "TicTacToe", "fa": "دوز", "players": 2, "category": "Classic", "icon": "⭕"},
    "chess": {"name": "Chess", "fa": "شطرنج", "players": 2, "category": "Strategy", "icon": "♟️"},
    "checkers": {"name": "Checkers", "fa": "چکرز", "players": 2, "category": "Classic", "icon": "⚪"},
    "fourinrow": {"name": "FourInRow", "fa": "دوز چهارتایی", "players": 2, "category": "Classic", "icon": "🔴"},
    "fekrbekr": {"name": "FekrBekr", "fa": "فکر بکر", "players": 2, "category": "Puzzle", "icon": "🧠"},
    "yatzy": {"name": "Yatzy", "fa": "یاتزی", "players": 2, "category": "Dice", "icon": "🎲"},
    "rpc": {"name": "RPC", "fa": "سنگ کاغذ قیچی", "players": 2, "category": "Quick", "icon": "✂️"},
    "backgammon": {"name": "BackGammon", "fa": "تخته نرد", "players": 2, "category": "Board", "icon": "🎯"},
    "othello": {"name": "Othello", "fa": "اتللو", "players": 2, "category": "Strategy", "icon": "⚫"},
    "mill": {"name": "Mill", "fa": "دوز ۹ تایی", "players": 2, "category": "Classic", "icon": "📐"},
    "dotbox": {"name": "DotBox", "fa": "نقطه خط", "players": 2, "category": "Classic", "icon": "✏️"},
    "mnumbers": {"name": "MNumbers", "fa": "کشف اعداد", "players": 2, "category": "Puzzle", "icon": "🔢"},
    "battleship": {"name": "BattleShip", "fa": "نبرد کشتی‌ها", "players": 2, "category": "Strategy", "icon": "🚢"},
    "sudoku": {"name": "Sudoku", "fa": "سودوکو", "players": 2, "category": "Puzzle", "icon": "🧩"},
    "msweeper": {"name": "MSweeper", "fa": "مین‌یاب", "players": 2, "category": "Puzzle", "icon": "💣"},
    "boxfour": {"name": "BoxFour", "fa": "چهارطرفه", "players": 2, "category": "Board", "icon": "⏹️"},
    "yinsh": {"name": "Yinsh", "fa": "یینش", "players": 2, "category": "Strategy", "icon": "💍"},
    "pentago": {"name": "Pentago", "fa": "پنتاگو", "players": 2, "category": "Strategy", "icon": "🔄"},
    "ludo": {"name": "Ludo", "fa": "منچ", "players": 4, "category": "Multiplayer", "icon": "🏁"},
    "risk": {"name": "Risk", "fa": "ریسک استرایک", "players": 4, "category": "Multiplayer", "icon": "⚔️"},
    "uno": {"name": "Uno", "fa": "اونو", "players": 4, "category": "Card", "icon": "🃏"},
    "quiz": {"name": "Quiz", "fa": "مسابقه اطلاعات عمومی", "players": 2, "category": "Trivia", "icon": "❓"},
    "quoridor": {"name": "Quoridor", "fa": "کوریدور", "players": 2, "category": "Strategy", "icon": "🧱"},
    "coup": {"name": "Coup", "fa": "کودتا", "players": 4, "category": "Multiplayer", "icon": "👑"},
    "monopoly": {"name": "Monopoly", "fa": "مونوپولی", "players": 4, "category": "Multiplayer", "icon": "🎩"},
}


class ManagedBot:
    """Wrapper holding bot process, state, task, and metadata."""

    def __init__(
        self,
        bot_id: str,
        bot_type: str,
        game_type: str,
        persona: Dict[str, Any],
        token: str,
        level: int = 1,
        auto_exit: bool = False,
    ):
        self.bot_id = bot_id
        self.bot_type = bot_type  # "lobby", "rank", "multi_rank"
        self.game_type = game_type
        self.persona = persona
        self.token = token
        self.level = level
        self.auto_exit = auto_exit
        self.status = "starting"  # starting, running, in_queue, pre_game, playing, finished, stopped, error
        self.detail = ""
        self.started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.finished_at: Optional[str] = None
        self.task: Optional[asyncio.Task] = None
        self.instance: Any = None
        self.logs: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "bot_type": self.bot_type,
            "game_type": self.game_type,
            "persona": {
                "username": self.persona.get("username", "Bot"),
                "phone": self.persona.get("phone", ""),
                "id": self.persona.get("_id", ""),
                "display_name": self.persona.get("display_name", self.persona.get("username", "Bot")),
            },
            "level": self.level,
            "auto_exit": self.auto_exit,
            "status": self.status,
            "detail": self.detail,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "log_count": len(self.logs),
        }


class BotManager:
    """Singleton Controller managing bots, system health, and logging."""

    _instance: Optional["BotManager"] = None

    def __init__(self):
        self.bots: Dict[str, ManagedBot] = {}
        self.global_logs: List[Dict[str, Any]] = []
        self.max_logs: int = 1500
        self.log_subscribers: Set[asyncio.Queue] = set()
        self.stats_subscribers: Set[asyncio.Queue] = set()
        self.counter: int = 0
        self._intercept_output()

    @classmethod
    def get_instance(cls) -> "BotManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _intercept_output(self):
        """Tees sys.stdout and sys.stderr so that all bot logs are captured and broadcast to the web admin."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        class InterceptWriter:
            def __init__(self, manager, orig, level="INFO"):
                self.manager = manager
                self.orig = orig
                self.level = level
                self.buf = ""
                self._in_write = False

            def write(self, text):
                if self._in_write:
                    try:
                        self.orig.write(text)
                    except Exception:
                        pass
                    return

                self._in_write = True
                try:
                    self.orig.write(text)
                    self.orig.flush()
                except Exception:
                    pass

                try:
                    if not isinstance(text, str):
                        text = str(text)
                    self.buf += text
                    while "\n" in self.buf:
                        line, self.buf = self.buf.split("\n", 1)
                        line = line.strip("\r")
                        if line:
                            self.manager.add_log(line, level=self.level)
                except Exception:
                    pass
                finally:
                    self._in_write = False

            def flush(self):
                try:
                    self.orig.flush()
                except Exception:
                    pass

            def __getattr__(self, name):
                return getattr(self.orig, name)

        sys.stdout = InterceptWriter(self, original_stdout, level="INFO")
        sys.stderr = InterceptWriter(self, original_stderr, level="ERROR")

    def add_log(self, message: str, level: str = "INFO", bot_id: Optional[str] = None):
        """Appends log entry and dispatches to live subscribers."""
        # Auto-detect bot_id if message mentions known bot ids or game types
        target_bot = bot_id
        if not target_bot:
            for b_id, b_obj in self.bots.items():
                uname = str(b_obj.persona.get("username", "")).strip()
                gtype = str(b_obj.game_type).strip()
                if b_id in message:
                    target_bot = b_id
                    break
                if gtype and f"[{gtype}" in message:
                    target_bot = b_id
                    break
                if uname and len(uname) > 2 and uname in message:
                    target_bot = b_id
                    break

        entry = {
            "time": datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "timestamp": time.time(),
            "level": level,
            "bot_id": target_bot or "system",
            "message": message,
        }

        self.global_logs.append(entry)
        if len(self.global_logs) > self.max_logs:
            self.global_logs.pop(0)

        if target_bot and target_bot in self.bots:
            self.bots[target_bot].logs.append(entry)
            if len(self.bots[target_bot].logs) > 300:
                self.bots[target_bot].logs.pop(0)

        # Notify active WebSocket listeners
        for q in list(self.log_subscribers):
            try:
                q.put_nowait(entry)
            except Exception:
                pass

    def get_personas(self) -> List[Dict[str, Any]]:
        """Returns list of personas available for bot instances."""
        personas: List[Dict[str, Any]] = [
            {
                "_id": BOT_USER_ID,
                "phone": BOT_PHONE,
                "username": "CafeFekrBot",
                "device_id": "bot_device_9131234567",
                "display_name": "🤖 ربات پیش‌فرض (09131234567)",
                "is_default": True,
            }
        ]
        real_users = RealUserManager.load_users()
        for u in real_users:
            personas.append({
                "_id": str(u.get("_id", "")),
                "phone": str(u.get("phone", "")),
                "username": str(u.get("username", "")),
                "device_id": str(u.get("device_id", "real_device")),
                "display_name": u.get("display_name", f"{u.get('username')} ({u.get('phone')})"),
                "is_default": False,
            })
        return personas

    def allocate_distinct_personas(self, count: int = 1, primary_spec: Optional[str | Dict] = None) -> List[tuple[Dict[str, Any], str]]:
        """
        Allocates `count` unique personas and their tokens, prioritizing unused personas.
        """
        active_uids = {
            str(b.persona.get("_id", ""))
            for b in self.bots.values()
            if b.status in ("starting", "running", "in_queue", "pre_game", "playing")
        }

        all_personas = self.get_personas()
        selected: List[tuple[Dict[str, Any], str]] = []
        used_ids = set()

        # 1. Primary requested persona
        if primary_spec:
            p, tok = self.resolve_persona_and_token(primary_spec)
            p_id = str(p.get("_id", ""))
            selected.append((p, tok))
            used_ids.add(p_id)

        # 2. Fill remaining from unused personas
        candidates = [p for p in all_personas if str(p.get("_id", "")) not in active_uids and str(p.get("_id", "")) not in used_ids]
        candidates += [p for p in all_personas if str(p.get("_id", "")) not in used_ids and p not in candidates]

        for p in candidates:
            if len(selected) >= count:
                break
            tok = RealUserManager.get_token(p)
            selected.append((p, tok))
            used_ids.add(str(p.get("_id", "")))

        # Fallback if count exceeds available unique personas
        while len(selected) < count:
            selected.append(self.resolve_persona_and_token("default"))

        return selected

    def resolve_persona_and_token(self, persona_spec: Optional[str | Dict] = None) -> tuple[Dict[str, Any], str]:
        """Resolves persona dict and valid signed JWT token."""
        if not persona_spec or persona_spec == "default" or persona_spec == BOT_USER_ID:
            token = get_auth_token()
            persona = {
                "_id": BOT_USER_ID,
                "phone": BOT_PHONE,
                "username": "CafeFekrBot",
                "device_id": "bot_device_9131234567",
                "display_name": "ربات پیش‌فرض کافه فکر",
            }
            return persona, token

        if isinstance(persona_spec, dict):
            token = RealUserManager.get_token(persona_spec)
            return persona_spec, token

        # By username or user_id
        user = RealUserManager.get_user_by_username(str(persona_spec)) or RealUserManager.get_user_by_id(str(persona_spec))
        if user:
            token = RealUserManager.get_token(user)
            return user, token

        # Fallback to default
        return self.resolve_persona_and_token("default")

    def get_games(self) -> List[Dict[str, Any]]:
        """Returns all 25 registered games with metadata."""
        canonical_keys = list_supported_games()
        res = []
        for k in canonical_keys:
            meta = GAME_METADATA.get(k.lower(), {})
            res.append({
                "id": k,
                "name": meta.get("name", k.capitalize()),
                "fa": meta.get("fa", k),
                "players": meta.get("players", 2),
                "category": meta.get("category", "Board"),
                "icon": meta.get("icon", "🎮"),
            })
        return res

    # -------------------------------------------------------------------------
    # Bot LifeCycle Operations
    # -------------------------------------------------------------------------

    async def start_lobby_bot(
        self,
        game_type: str,
        persona_spec: Optional[str | Dict] = None,
        target_lobby_id: Optional[str] = None,
        auto_exit: bool = False,
        count: int = 1,
    ) -> List[ManagedBot]:
        """Starts one or more LobbyBot instances listening for rooms or targeting a specific room."""
        count = max(1, min(10, count))
        allocated = self.allocate_distinct_personas(count=count, primary_spec=persona_spec)
        launched: List[ManagedBot] = []

        for idx, (persona, token) in enumerate(allocated):
            self.counter += 1
            bot_id = f"lobby_{game_type.lower()}_{self.counter}"

            m_bot = ManagedBot(
                bot_id=bot_id,
                bot_type="lobby",
                game_type=game_type,
                persona=persona,
                token=token,
                level=1,
                auto_exit=auto_exit,
            )
            self.bots[bot_id] = m_bot

            bot_instance = LobbyBot(
                game_logic_or_type=game_type,
                token=token,
                auto_exit_after_match=auto_exit,
            )
            bot_instance.my_user_id = str(persona.get("_id", BOT_USER_ID))
            bot_instance.bot_phone = str(persona.get("phone", BOT_PHONE))
            bot_instance.bot_name = str(persona.get("username", f"ربات {game_type}"))
            bot_instance.target_lobby_id = target_lobby_id
            m_bot.instance = bot_instance

            def make_on_exit(cur_bot, cur_id):
                def on_exit():
                    cur_bot.status = "finished"
                    cur_bot.finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.add_log(f"[{cur_id}] Lobby match concluded. Bot status: finished.", bot_id=cur_id)
                return on_exit

            bot_instance.on_exit_callback = make_on_exit(m_bot, bot_id)

            def make_run_wrapper(cur_bot, cur_id, cur_instance):
                async def run_wrapper():
                    cur_bot.status = "running"
                    self.add_log(f"[{cur_id}] Launched Lobby Bot for '{game_type}' as '{cur_bot.persona.get('username')}'", bot_id=cur_id)
                    run_task = None
                    try:
                        run_task = asyncio.create_task(cur_instance.run())
                        if target_lobby_id:
                            async def join_target_when_ready():
                                for _ in range(60):
                                    if cur_instance.lobby_sio and "/lobby" in cur_instance.lobby_sio.namespaces:
                                        await asyncio.sleep(0.2)
                                        await cur_instance.join_specific_lobby(target_lobby_id)
                                        break
                                    await asyncio.sleep(0.1)
                            asyncio.create_task(join_target_when_ready())
                        await run_task
                    except asyncio.CancelledError:
                        cur_bot.status = "stopped"
                        self.add_log(f"[{cur_id}] Lobby Bot task cancelled.", bot_id=cur_id)
                        if run_task and not run_task.done():
                            run_task.cancel()
                    except Exception as e:
                        cur_bot.status = "error"
                        cur_bot.detail = str(e)
                        self.add_log(f"[{cur_id}] Lobby Bot error: {e}", level="ERROR", bot_id=cur_id)
                    finally:
                        if cur_bot.status not in ("finished", "stopped", "error"):
                            cur_bot.status = "stopped"
                        cur_bot.finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return run_wrapper

            m_bot.task = asyncio.create_task(make_run_wrapper(m_bot, bot_id, bot_instance)())
            launched.append(m_bot)

            if idx < len(allocated) - 1:
                await asyncio.sleep(0.3)

        return launched

    async def create_and_join_lobby(
        self,
        game_type: str,
        lobby_name: str,
        count: int = 2,
        password: str = "",
        persona_spec: Optional[str | Dict] = None,
    ) -> ManagedBot:
        """Starts a LobbyBot and immediately creates a new room with host privileges."""
        self.counter += 1
        bot_id = f"lobby_host_{game_type.lower()}_{self.counter}"
        persona, token = self.resolve_persona_and_token(persona_spec)

        m_bot = ManagedBot(
            bot_id=bot_id,
            bot_type="lobby",
            game_type=game_type,
            persona=persona,
            token=token,
            level=1,
            auto_exit=False,
        )
        self.bots[bot_id] = m_bot

        bot_instance = LobbyBot(
            game_logic_or_type=game_type,
            token=token,
            auto_exit_after_match=False,
        )
        bot_instance.my_user_id = str(persona.get("_id", BOT_USER_ID))
        bot_instance.bot_phone = str(persona.get("phone", BOT_PHONE))
        bot_instance.bot_name = str(persona.get("username", "هاست لابی"))
        m_bot.instance = bot_instance

        async def run_wrapper():
            m_bot.status = "running"
            self.add_log(f"[{bot_id}] Host Lobby Bot starting room '{lobby_name}' ({game_type})...", bot_id=bot_id)
            run_task = None
            try:
                run_task = asyncio.create_task(bot_instance.run())
                async def create_room_when_ready():
                    for _ in range(60):
                        if bot_instance.lobby_sio and "/lobby" in bot_instance.lobby_sio.namespaces:
                            await asyncio.sleep(0.25)
                            await bot_instance.create_lobby_room(lobby_name=lobby_name, game_type=game_type, count=count, password=password)
                            break
                        await asyncio.sleep(0.1)
                asyncio.create_task(create_room_when_ready())
                await run_task
            except asyncio.CancelledError:
                m_bot.status = "stopped"
                if run_task and not run_task.done():
                    run_task.cancel()
            except Exception as e:
                m_bot.status = "error"
                m_bot.detail = str(e)
                self.add_log(f"[{bot_id}] Create lobby error: {e}", level="ERROR", bot_id=bot_id)
            finally:
                if m_bot.status not in ("finished", "stopped", "error"):
                    m_bot.status = "stopped"
                m_bot.finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        m_bot.task = asyncio.create_task(run_wrapper())
        return m_bot

    async def start_rank_bot(
        self,
        persona_spec: Optional[str | Dict] = None,
        level: int = 2,
        preferred_picks: Optional[List[str]] = None,
        preferred_bans: Optional[List[str]] = None,
        auto_exit: bool = False,
    ) -> ManagedBot:
        """Starts a Main Rank 1v1 Bot (Pick & Ban, Series Best-of-3)."""
        self.counter += 1
        bot_id = f"rank_1v1_{self.counter}"
        persona, token = self.resolve_persona_and_token(persona_spec)

        m_bot = ManagedBot(
            bot_id=bot_id,
            bot_type="rank",
            game_type="Series",
            persona=persona,
            token=token,
            level=level,
            auto_exit=auto_exit,
        )
        self.bots[bot_id] = m_bot

        bot_instance = RankBot(
            token=token,
            level=level,
            auto_exit_after_match=auto_exit,
        )
        if preferred_picks:
            bot_instance.preferred_pick_pool = preferred_picks
        if preferred_bans:
            bot_instance.preferred_ban_pool = preferred_bans

        m_bot.instance = bot_instance

        def on_exit():
            m_bot.status = "finished"
            m_bot.finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.add_log(f"[{bot_id}] Rank match series concluded.", bot_id=bot_id)

        bot_instance.on_exit_callback = on_exit

        async def run_wrapper():
            m_bot.status = "in_queue"
            self.add_log(f"[{bot_id}] Entering Main Rank queue (Level {level}) as '{persona.get('username')}'", bot_id=bot_id)
            try:
                await bot_instance.run()
            except asyncio.CancelledError:
                m_bot.status = "stopped"
            except Exception as e:
                m_bot.status = "error"
                m_bot.detail = str(e)
                self.add_log(f"[{bot_id}] Rank Bot error: {e}\n{traceback.format_exc()}", level="ERROR", bot_id=bot_id)
            finally:
                if m_bot.status not in ("finished", "stopped", "error"):
                    m_bot.status = "stopped"
                m_bot.finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        m_bot.task = asyncio.create_task(run_wrapper())
        return m_bot

    async def start_multi_rank_bot(
        self,
        game_type: str = "Ludo",
        persona_spec: Optional[str | Dict] = None,
        level: int = 2,
        auto_exit: bool = False,
        count: int = 1,
    ) -> List[ManagedBot]:
        """Starts one or more 4-Player Multiplayer Rank Bots (/multi-queue) for Ludo, Risk, Uno, Coup, Monopoly."""
        count = max(1, min(4, count))
        allocated = self.allocate_distinct_personas(count=count, primary_spec=persona_spec)
        launched: List[ManagedBot] = []

        for idx, (persona, token) in enumerate(allocated):
            self.counter += 1
            bot_id = f"multi_{game_type.lower()}_{self.counter}"

            m_bot = ManagedBot(
                bot_id=bot_id,
                bot_type="multi_rank",
                game_type=game_type,
                persona=persona,
                token=token,
                level=level,
                auto_exit=auto_exit,
            )
            self.bots[bot_id] = m_bot

            bot_instance = MultiRankBot(
                game_type=game_type,
                token=token,
                level=level,
                auto_exit_after_match=auto_exit,
            )
            m_bot.instance = bot_instance

            def make_on_exit(cur_bot, cur_id):
                def on_exit():
                    cur_bot.status = "finished"
                    cur_bot.finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.add_log(f"[{cur_id}] Multi-Rank match ({game_type}) concluded.", bot_id=cur_id)
                return on_exit

            bot_instance.on_exit_callback = make_on_exit(m_bot, bot_id)

            def make_run_wrapper(cur_bot, cur_id, cur_instance):
                async def run_wrapper():
                    cur_bot.status = "in_queue"
                    self.add_log(f"[{cur_id}] Entering Multi-Queue for '{game_type}' as '{cur_bot.persona.get('username')}'", bot_id=cur_id)
                    try:
                        await cur_instance.run()
                    except asyncio.CancelledError:
                        cur_bot.status = "stopped"
                    except Exception as e:
                        cur_bot.status = "error"
                        cur_bot.detail = str(e)
                        self.add_log(f"[{cur_id}] Multi-Rank error: {e}", level="ERROR", bot_id=cur_id)
                    finally:
                        if cur_bot.status not in ("finished", "stopped", "error"):
                            cur_bot.status = "stopped"
                        cur_bot.finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return run_wrapper

            m_bot.task = asyncio.create_task(make_run_wrapper(m_bot, bot_id, bot_instance)())
            launched.append(m_bot)

            if idx < len(allocated) - 1:
                await asyncio.sleep(0.35)

        return launched

    async def stop_bot(self, bot_id: str) -> bool:
        """Cleanly stops a specific running bot."""
        if bot_id not in self.bots:
            return False

        m_bot = self.bots[bot_id]
        self.add_log(f"[{bot_id}] Stopping bot...", bot_id=bot_id)

        # Disconnect bot instance cleanly
        if m_bot.instance and hasattr(m_bot.instance, "stop"):
            try:
                await m_bot.instance.stop()
            except Exception as e:
                self.add_log(f"[{bot_id}] Exception during stop(): {e}", level="WARN", bot_id=bot_id)

        # Cancel async task if still active
        if m_bot.task and not m_bot.task.done():
            m_bot.task.cancel()

        m_bot.status = "stopped"
        m_bot.finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.add_log(f"[{bot_id}] Bot successfully stopped.", bot_id=bot_id)
        return True

    async def stop_all_bots(self) -> int:
        """Stops all currently running bots."""
        stopped = 0
        for bot_id in list(self.bots.keys()):
            if self.bots[bot_id].status in ("starting", "running", "in_queue", "playing", "pre_game"):
                await self.stop_bot(bot_id)
                stopped += 1
        return stopped

    def get_all_bots(self) -> List[Dict[str, Any]]:
        """Returns snapshot of all bots."""
        return [b.to_dict() for b in self.bots.values()]

    def get_bot(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Returns details of a specific bot."""
        if bot_id in self.bots:
            return self.bots[bot_id].to_dict()
        return None

    def get_bot_logs(self, bot_id: str) -> List[Dict[str, Any]]:
        if bot_id in self.bots:
            return self.bots[bot_id].logs
        return []

    # -------------------------------------------------------------------------
    # Live Lobby Room Scanner
    # -------------------------------------------------------------------------

    async def fetch_live_lobbies(self) -> List[Dict[str, Any]]:
        """Queries /lobby on backend directly using a temporary socket client."""
        import socketio
        lobbies_result: List[Dict[str, Any]] = []
        token = get_auth_token()
        sio = socketio.AsyncClient()

        received_event = asyncio.Event()

        @sio.on("command", namespace="/lobby")
        async def on_lobby_cmd(data):
            if isinstance(data, dict) and data.get("id") == "LobbyList":
                lobbies = data.get("data", [])
                if isinstance(lobbies, list):
                    lobbies_result.extend(lobbies)
                received_event.set()

        try:
            await sio.connect(SERVER_WS_URL, namespaces=["/lobby"], auth={"token": token})
            await sio.emit("user_command", {"id": "LobbyRequestData", "data": {}}, namespace="/lobby")
            try:
                await asyncio.wait_for(received_event.wait(), timeout=1.8)
            except asyncio.TimeoutError:
                pass
        except Exception as e:
            self.add_log(f"[Scanner] Could not fetch live lobbies: {e}", level="WARN")
        finally:
            if sio.connected:
                await sio.disconnect()

        return lobbies_result

    # -------------------------------------------------------------------------
    # Social Operations Wrapper
    # -------------------------------------------------------------------------

    async def run_social_action(
        self,
        actor_spec: str,
        category: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Executes a one-off social action using SocialBot."""
        params = params or {}
        bot = SocialBot(actor_spec, base_url=SERVER_REST_URL)

        self.add_log(f"[Social] Actor '{bot.username}' running {category}.{action} with {params}")

        if category == "friends":
            if action == "list_friends":
                ok, st, data = bot.friends.list_friends()
            elif action == "list_requests":
                ok, st, data = bot.friends.list_requests()
            elif action == "send_request":
                target_uid = params.get("target_user_id", "")
                msg = params.get("message", "درخواست دوستی از پنل ربات")
                ok, st, data = bot.friends.send_request(target_uid, msg)
            elif action == "respond_request":
                req_id = params.get("request_id", "")
                decision = params.get("action", "accept")
                ok, st, data = bot.friends.respond_request(req_id, decision)
            else:
                return {"error": f"Unknown friends action: {action}"}

        elif category == "messages":
            if action == "send_dm":
                target_uid = params.get("target_user_id", "")
                content = params.get("text", "سلام!")
                ok, st, data = bot.messages.send_dm(target_uid, content)
            elif action == "get_dm_history":
                target_uid = params.get("target_user_id", "")
                ok, st, data = bot.messages.get_dm_history(target_uid)
            elif action == "mark_read":
                target_uid = params.get("target_user_id", "")
                ok, st, data = bot.messages.mark_read(target_uid)
            else:
                return {"error": f"Unknown message action: {action}"}

        elif category == "invitations":
            if action == "send_game_invite":
                target_uid = params.get("target_user_id", "")
                game = params.get("game_type", "TicTacToe")
                mode = params.get("invite_mode", "direct_match")
                ok, st, data = bot.invitations.send_game_invite(target_uid, game_type=game, invite_mode=mode)
            elif action == "list_pending_invites":
                ok, st, data = bot.invitations.list_pending_invites()
            elif action == "respond_invite":
                inv_id = params.get("invite_id", "")
                decision = params.get("action", "accept")
                ok, st, data = bot.invitations.respond_invite(inv_id, decision)
            else:
                return {"error": f"Unknown invitation action: {action}"}

        elif category == "clans":
            if action == "get_my_clan":
                ok, st, data = bot.clans.get_my_clan()
            elif action == "search_clans":
                q = params.get("query", "")
                ok, st, data = bot.clans.search_clans(q)
            elif action == "send_chat":
                clan_id = params.get("clan_id")
                msg = params.get("message", "پیام تستی از پنل ربات")
                ok, st, data = bot.clans.send_chat(msg, clan_id=clan_id)
            else:
                return {"error": f"Unknown clan action: {action}"}

        elif category == "notifications":
            if action == "list_notifications":
                ok, st, data = bot.notifications.list_notifications()
            else:
                return {"error": f"Unknown notification action: {action}"}
        else:
            return {"error": f"Unknown category: {category}"}

        return {"ok": ok, "status_code": st, "data": data}

    async def run_social_diagnostic(self, actor_spec: str = "akbari") -> List[Dict[str, Any]]:
        """Runs the complete social diagnostic matrix."""
        bot = SocialBot(actor_spec, base_url=SERVER_REST_URL)
        loop = asyncio.get_running_loop()
        self.add_log(f"[Social] Running full diagnostic as '{bot.username}'...")
        results = await loop.run_in_executor(None, bot.run_full_diagnostic)
        self.add_log(f"[Social] Diagnostic completed. {len(results)} checks performed.")
        return results

    async def run_peer_flow(self, actor_a: str = "akbari", actor_b: str = "Niliii22") -> str:
        """Executes the two-actor peer-to-peer social flow test."""
        loop = asyncio.get_running_loop()
        self.add_log(f"[Social] Initiating Peer Flow: '{actor_a}' <-> '{actor_b}'...")
        await loop.run_in_executor(None, run_peer_flow_test, actor_a, actor_b, SERVER_REST_URL)
        self.add_log(f"[Social] Peer Flow completed successfully.")
        return "Peer Flow Test Concluded"

    # -------------------------------------------------------------------------
    # Game Engine Tester
    # -------------------------------------------------------------------------

    def test_game_engine(self, game_type: str, level: int = 1) -> Dict[str, Any]:
        """Direct benchmark and move calculation verification for any registered game."""
        start_t = time.perf_counter()
        engine = get_game_logic(game_type, level=level)
        engine.on_game_start(f"test_bench_{int(time.time())}")

        bench_time = round((time.perf_counter() - start_t) * 1000, 2)
        return {
            "game_type": engine.game_type,
            "level": engine.level,
            "engine_class": engine.__class__.__name__,
            "init_time_ms": bench_time,
            "status": "ready",
            "supported_aliases": [engine.game_type],
        }

    # -------------------------------------------------------------------------
    # System Health Monitoring
    # -------------------------------------------------------------------------

    async def check_system_health(self) -> Dict[str, Any]:
        """Probes status of MongoDB, REST Server (5001), Realtime Backend (5000), and Bot Server (5003)."""
        loop = asyncio.get_running_loop()

        # 1. MongoDB check
        mongo_ok = False
        try:
            import pymongo
            client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=800)
            client.admin.command("ping")
            mongo_ok = True
        except Exception:
            mongo_ok = False

        # 2. REST Server check (5001)
        rest_ok = False
        try:
            def probe_rest():
                with urllib.request.urlopen("http://127.0.0.1:5001/health", timeout=1.0) as res:
                    return res.status == 200
            rest_ok = await loop.run_in_executor(None, probe_rest)
        except Exception:
            rest_ok = False

        # 3. Socket.IO Backend check (5000)
        backend_ok = False
        try:
            def probe_backend():
                with urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=1.0) as res:
                    return res.status == 200
            backend_ok = await loop.run_in_executor(None, probe_backend)
        except Exception:
            backend_ok = False

        active_count = len([b for b in self.bots.values() if b.status in ("starting", "running", "in_queue", "playing", "pre_game")])

        return {
            "services": {
                "mongodb": {"status": "online" if mongo_ok else "offline", "port": 27017},
                "rest_server": {"status": "online" if rest_ok else "offline", "port": 5001},
                "backend_ws": {"status": "online" if backend_ok else "offline", "port": 5000},
                "bots_server": {"status": "online", "port": 5003},
            },
            "active_bots_count": active_count,
            "total_games_supported": len(list_supported_games()),
            "system_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
