"""
Cafe Fekr Bots Backend Server.

Runs on port 5003, providing:
1. REST API for managing and testing every part of the bots (Lobby, Rank, Multi-Queue, Social, Game Engines).
2. WebSocket real-time log streaming and state synchronization.
3. Interactive Web Admin panel served at http://localhost:5003/.
"""

import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from bots.manager import BotManager
from bots.social.auth_helper import RealUserManager

app = FastAPI(
    title="Cafe Fekr Bots Backend Server",
    description="Autonomous Bot Management & Realtime Testing Server for Cafe Fekr",
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = BotManager.get_instance()
WEB_ADMIN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_admin", "index.html")


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------

class LobbyStartRequest(BaseModel):
    game_type: str = "TicTacToe"
    persona_spec: Optional[str] = None
    target_lobby_id: Optional[str] = None
    auto_exit: bool = False
    count: int = 1  # Number of bots to launch (e.g. 1 to 3 for multiplayer games)


class LobbyCreateRequest(BaseModel):
    game_type: str = "TicTacToe"
    lobby_name: str = "اتاق چالش با ربات"
    count: int = 2
    password: str = ""
    persona_spec: Optional[str] = None


class RankStartRequest(BaseModel):
    persona_spec: Optional[str] = None
    level: int = 2
    preferred_picks: Optional[List[str]] = None
    preferred_bans: Optional[List[str]] = None
    auto_exit: bool = False


class MultiRankStartRequest(BaseModel):
    game_type: str = "Ludo"
    persona_spec: Optional[str] = None
    level: int = 2
    auto_exit: bool = False
    count: int = 1  # Number of bots to launch (e.g. 1 to 4)


class SocialActionRequest(BaseModel):
    actor_spec: str = "akbari"
    category: str
    action: str
    params: Optional[Dict[str, Any]] = None


class SocialDiagnosticRequest(BaseModel):
    actor_spec: str = "akbari"


class PeerFlowRequest(BaseModel):
    actor_a: str = "akbari"
    actor_b: str = "Niliii22"


class GameEngineTestRequest(BaseModel):
    game_type: str = "TicTacToe"
    level: int = 1


class TokenGenerateRequest(BaseModel):
    user_spec: str = "akbari"


# -----------------------------------------------------------------------------
# Web Admin UI Routes
# -----------------------------------------------------------------------------

@app.get("/", summary="Web Admin UI")
async def serve_admin_ui():
    if os.path.exists(WEB_ADMIN_PATH):
        return FileResponse(WEB_ADMIN_PATH)
    return JSONResponse({"status": "ok", "message": "Bot Backend Server running on port 5003. Web admin file not found."})


@app.get("/admin", summary="Web Admin UI Alias")
async def serve_admin_alias():
    return await serve_admin_ui()


@app.get("/health", summary="Health Check")
async def health_check():
    return {
        "status": "ok",
        "service": "bots-backend",
        "port": 5003,
        "active_bots": len([b for b in manager.bots.values() if b.status in ("starting", "running", "in_queue", "playing", "pre_game")]),
    }


# -----------------------------------------------------------------------------
# System & Configuration API
# -----------------------------------------------------------------------------

@app.get("/api/system/status", summary="System Health & Connectivity Status")
async def get_system_status():
    return await manager.check_system_health()


@app.get("/api/games", summary="List All 25 Supported Games")
async def get_supported_games():
    return manager.get_games()


@app.get("/api/personas", summary="List Available Bot Personas & Real Users")
async def get_personas():
    return manager.get_personas()


@app.post("/api/auth/token", summary="Generate JWT Token for Persona")
async def generate_token(req: TokenGenerateRequest):
    _, token = manager.resolve_persona_and_token(req.user_spec)
    return {"user_spec": req.user_spec, "token": token}


# -----------------------------------------------------------------------------
# Lobby Bots API
# -----------------------------------------------------------------------------

@app.get("/api/lobbies", summary="Scan Active Open Rooms on Backend (/lobby)")
async def scan_lobbies():
    return await manager.fetch_live_lobbies()


@app.post("/api/bots/lobby/start", summary="Start Lobby Bot (Auto-Join or Specific Room, supports multiple bots)")
async def start_lobby_bot(req: LobbyStartRequest):
    try:
        bots = await manager.start_lobby_bot(
            game_type=req.game_type,
            persona_spec=req.persona_spec,
            target_lobby_id=req.target_lobby_id,
            auto_exit=req.auto_exit,
            count=max(1, min(10, req.count)),
        )
        first_dict = bots[0].to_dict()
        first_dict["bots"] = [b.to_dict() for b in bots]
        first_dict["count"] = len(bots)
        return first_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bots/lobby/create", summary="Bot Creates and Hosts a New Lobby Room")
async def create_lobby_room(req: LobbyCreateRequest):
    try:
        m_bot = await manager.create_and_join_lobby(
            game_type=req.game_type,
            lobby_name=req.lobby_name,
            count=req.count,
            password=req.password,
            persona_spec=req.persona_spec,
        )
        return m_bot.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Rank Bots API
# -----------------------------------------------------------------------------

@app.post("/api/bots/rank/start", summary="Start Main Rank 1v1 Bot (/queue)")
async def start_rank_bot(req: RankStartRequest):
    try:
        m_bot = await manager.start_rank_bot(
            persona_spec=req.persona_spec,
            level=req.level,
            preferred_picks=req.preferred_picks,
            preferred_bans=req.preferred_bans,
            auto_exit=req.auto_exit,
        )
        return m_bot.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bots/multi-rank/start", summary="Start 4-Player Multi-Rank Bot (/multi-queue, supports multiple bots)")
async def start_multi_rank_bot(req: MultiRankStartRequest):
    try:
        bots = await manager.start_multi_rank_bot(
            game_type=req.game_type,
            persona_spec=req.persona_spec,
            level=req.level,
            auto_exit=req.auto_exit,
            count=max(1, min(4, req.count)),
        )
        first_dict = bots[0].to_dict()
        first_dict["bots"] = [b.to_dict() for b in bots]
        first_dict["count"] = len(bots)
        return first_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Bot Lifecycle Management API
# -----------------------------------------------------------------------------

@app.get("/api/bots", summary="Get All Managed Bots")
async def get_all_bots():
    return manager.get_all_bots()


@app.get("/api/bots/{bot_id}", summary="Get Specific Bot Details")
async def get_bot(bot_id: str):
    bot = manager.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


@app.get("/api/bots/{bot_id}/logs", summary="Get Logs for Specific Bot")
async def get_bot_logs(bot_id: str):
    return manager.get_bot_logs(bot_id)


@app.post("/api/bots/{bot_id}/stop", summary="Stop Specific Bot")
async def stop_bot(bot_id: str):
    ok = await manager.stop_bot(bot_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"status": "ok", "bot_id": bot_id, "action": "stopped"}


@app.post("/api/bots/stop-all", summary="Stop All Active Bots")
async def stop_all_bots():
    count = await manager.stop_all_bots()
    return {"status": "ok", "stopped_count": count}


# -----------------------------------------------------------------------------
# Social & Community Testing API
# -----------------------------------------------------------------------------

@app.post("/api/social/action", summary="Trigger Social Action")
async def trigger_social_action(req: SocialActionRequest):
    try:
        res = await manager.run_social_action(
            actor_spec=req.actor_spec,
            category=req.category,
            action=req.action,
            params=req.params,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/social/diagnostic", summary="Run Full Social Diagnostic Suite")
async def run_social_diagnostic(req: SocialDiagnosticRequest):
    try:
        res = await manager.run_social_diagnostic(actor_spec=req.actor_spec)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/social/peer-flow", summary="Run Two-Actor Peer-to-Peer Interaction Flow")
async def run_peer_flow(req: PeerFlowRequest):
    try:
        res = await manager.run_peer_flow(actor_a=req.actor_a, actor_b=req.actor_b)
        return {"status": "ok", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Game Engine Testing API
# -----------------------------------------------------------------------------

@app.post("/api/games/test-engine", summary="Direct Pure Engine Logic & AI Benchmark")
async def test_game_engine(req: GameEngineTestRequest):
    try:
        return manager.test_game_engine(game_type=req.game_type, level=req.level)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# WebSocket Live Streaming
# -----------------------------------------------------------------------------

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """Streams live console and bot logs to browser admin clients."""
    await websocket.accept()
    queue = asyncio.Queue(maxsize=1000)
    manager.log_subscribers.add(queue)

    try:
        # Send recent initial history (last 50 logs)
        for log in manager.global_logs[-50:]:
            await websocket.send_json(log)

        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        manager.log_subscribers.discard(queue)


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------

def run_server():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5003))

    print("\n" + "=" * 65)
    print("  ☕ Cafe Fekr — Autonomous Bot Backend Server")
    print(f"  Listening on: http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}")
    print(f"  Web Admin:    http://127.0.0.1:{port}/")
    print(f"  API Docs:     http://127.0.0.1:{port}/docs")
    print("=" * 65 + "\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
