"""Monopoly (مونوپولی) Game Logic for Cafe Fekr Bot (Supports 2, 3, and 4 Players)."""

import random
from typing import Any, Dict, List, Optional
from .base_game import BaseGameLogic

BOARD_META: List[Dict[str, Any]] = [
    {"id": 0, "type": "corner", "group": "", "price": 0, "house_cost": 0},
    {"id": 1, "type": "street", "group": "brown", "price": 60, "house_cost": 50},
    {"id": 2, "type": "chest", "group": "", "price": 0, "house_cost": 0},
    {"id": 3, "type": "street", "group": "brown", "price": 60, "house_cost": 50},
    {"id": 4, "type": "tax", "group": "", "price": 0, "house_cost": 0},
    {"id": 5, "type": "railroad", "group": "railroad", "price": 200, "house_cost": 0},
    {"id": 6, "type": "street", "group": "light_blue", "price": 100, "house_cost": 50},
    {"id": 7, "type": "street", "group": "light_blue", "price": 120, "house_cost": 50},
    {"id": 8, "type": "corner", "group": "", "price": 0, "house_cost": 0},
    {"id": 9, "type": "street", "group": "pink", "price": 140, "house_cost": 100},
    {"id": 10, "type": "utility", "group": "utility", "price": 150, "house_cost": 0},
    {"id": 11, "type": "street", "group": "pink", "price": 160, "house_cost": 100},
    {"id": 12, "type": "chance", "group": "", "price": 0, "house_cost": 0},
    {"id": 13, "type": "railroad", "group": "railroad", "price": 200, "house_cost": 0},
    {"id": 14, "type": "street", "group": "orange", "price": 180, "house_cost": 100},
    {"id": 15, "type": "street", "group": "orange", "price": 200, "house_cost": 100},
    {"id": 16, "type": "corner", "group": "", "price": 0, "house_cost": 0},
    {"id": 17, "type": "street", "group": "red", "price": 220, "house_cost": 150},
    {"id": 18, "type": "chance", "group": "", "price": 0, "house_cost": 0},
    {"id": 19, "type": "street", "group": "red", "price": 240, "house_cost": 150},
    {"id": 20, "type": "railroad", "group": "railroad", "price": 200, "house_cost": 0},
    {"id": 21, "type": "street", "group": "yellow", "price": 260, "house_cost": 150},
    {"id": 22, "type": "utility", "group": "utility", "price": 150, "house_cost": 0},
    {"id": 23, "type": "street", "group": "yellow", "price": 280, "house_cost": 150},
    {"id": 24, "type": "corner", "group": "", "price": 0, "house_cost": 0},
    {"id": 25, "type": "street", "group": "green", "price": 300, "house_cost": 200},
    {"id": 26, "type": "chest", "group": "", "price": 0, "house_cost": 0},
    {"id": 27, "type": "street", "group": "green", "price": 320, "house_cost": 200},
    {"id": 28, "type": "railroad", "group": "railroad", "price": 200, "house_cost": 0},
    {"id": 29, "type": "street", "group": "dark_blue", "price": 350, "house_cost": 200},
    {"id": 30, "type": "tax", "group": "", "price": 0, "house_cost": 0},
    {"id": 31, "type": "street", "group": "dark_blue", "price": 400, "house_cost": 200},
]

STREET_GROUPS: Dict[str, List[int]] = {
    "brown": [1, 3],
    "light_blue": [6, 7],
    "pink": [9, 11],
    "orange": [14, 15],
    "red": [17, 19],
    "yellow": [21, 23],
    "green": [25, 27],
    "dark_blue": [29, 31],
}


class MonopolyGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Monopoly",
            game_type_aliases=["monopoly", "مونوپولی", "منوپولی"],
            level=level,
        )
        self.players_count: int = 2
        self.current_turn: int = 1
        self.phase: str = "roll"
        self.state_seq: int = 0
        self.players: List[Dict[str, Any]] = []
        self.tiles: List[Dict[str, Any]] = []
        self.pending_tile_id: int = -1
        self.auction: Optional[Dict[str, Any]] = None
        self.debt: Optional[Dict[str, Any]] = None
        self.pending_trade: Optional[Dict[str, Any]] = None
        self.buildable_tiles: List[int] = []
        self.sellable_tiles: List[int] = []
        self.mortgageable_tiles: List[int] = []
        self.unmortgageable_tiles: List[int] = []
        self._acted_keys: set = set()
        self._scheduled_keys: set = set()
        self._needs_continuation_move: bool = False
        self.rank1: Optional[int] = None
        self.rank2: Optional[int] = None
        self.reset()

    def reset(self):
        self.current_turn = 1
        self.phase = "roll"
        self.state_seq = 0
        self.players = []
        self.tiles = []
        self.pending_tile_id = -1
        self.auction = None
        self.debt = None
        self.pending_trade = None
        self.buildable_tiles = []
        self.sellable_tiles = []
        self.mortgageable_tiles = []
        self.unmortgageable_tiles = []
        self._acted_keys = set()
        self._scheduled_keys = set()
        self._needs_continuation_move = False
        self.rank1 = None
        self.rank2 = None

    def _apply_state(self, state: Dict[str, Any]):
        if not isinstance(state, dict):
            return
        if "players_count" in state:
            self.players_count = int(state["players_count"])
        if "current_turn" in state:
            self.current_turn = int(state["current_turn"])
        elif "turn" in state:
            self.current_turn = int(state["turn"])
        if "phase" in state:
            self.phase = str(state["phase"])
        if "state_seq" in state:
            self.state_seq = int(state["state_seq"])
        if isinstance(state.get("players"), list):
            self.players = [dict(p) for p in state["players"]]
        if isinstance(state.get("tiles"), list):
            self.tiles = [dict(t) for t in state["tiles"]]
        if "pending_tile_id" in state:
            self.pending_tile_id = int(state.get("pending_tile_id", -1))
        self.auction = dict(state["auction"]) if isinstance(state.get("auction"), dict) else None
        self.debt = dict(state["debt"]) if isinstance(state.get("debt"), dict) else None
        self.pending_trade = dict(state["pending_trade"]) if isinstance(state.get("pending_trade"), dict) else None
        self.buildable_tiles = [int(x) for x in (state.get("buildable_tiles") or [])]
        self.sellable_tiles = [int(x) for x in (state.get("sellable_tiles") or [])]
        self.mortgageable_tiles = [int(x) for x in (state.get("mortgageable_tiles") or [])]
        self.unmortgageable_tiles = [int(x) for x in (state.get("unmortgageable_tiles") or [])]
        if state.get("rank1") is not None:
            self.rank1 = int(state["rank1"])
        if state.get("rank2") is not None:
            self.rank2 = int(state["rank2"])
        if state.get("is_game_finished"):
            self.is_game_active = False

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        self._needs_continuation_move = False
        if cmd_id == "GameData" and isinstance(payload, dict):
            g_data = payload.get("game_data")
            if isinstance(g_data, dict):
                self._apply_state(g_data)
            return True
        if cmd_id == "ReconnectData" and isinstance(payload, dict):
            self.is_game_active = True
            g_data = payload.get("game_data")
            if isinstance(g_data, dict):
                self._apply_state(g_data)
            return True
        if cmd_id == "StartGame" and isinstance(payload, dict):
            self.is_game_active = True
            self._apply_state(payload)
            return True
        if cmd_id == "CurrentTurn":
            self.is_game_active = True
            if isinstance(payload, dict):
                self._apply_state(payload)
            else:
                self.current_turn = int(payload)
            if self._needs_to_act() and self.current_turn == (self.my_player_num or 0):
                self._scheduled_keys.add(self._state_action_key())
            return True
        if cmd_id == "MonopolyState" and isinstance(payload, dict):
            self.is_game_active = True
            self._apply_state(payload)
            key = self._state_action_key()
            if self._needs_to_act() and key not in self._scheduled_keys and key not in self._acted_keys:
                self._scheduled_keys.add(key)
                self._needs_continuation_move = True
            return True
        if cmd_id == "MonopolyEvent" and isinstance(payload, dict):
            self.is_game_active = True
            if isinstance(payload.get("state"), dict):
                self._apply_state(payload["state"])
            return True
        if cmd_id == "UserData" and isinstance(payload, dict):
            self._apply_state(payload)
            return True
        return False

    def _me(self) -> Dict[str, Any]:
        my_id = self.my_player_num or 0
        for p in self.players:
            if int(p.get("gamer_id", 0)) == int(my_id):
                return p
        return {}

    def _tile_owner(self, tid: int) -> int:
        if 0 <= tid < len(self.tiles):
            return int(self.tiles[tid].get("owner", 0))
        return 0

    def _unowned_purchasable_count(self) -> int:
        cnt = 0
        for meta in BOARD_META:
            if meta["type"] in ("street", "railroad", "utility"):
                if self._tile_owner(meta["id"]) == 0:
                    cnt += 1
        return cnt

    def _would_complete_group(self, player_id: int, tile_id: int) -> bool:
        grp = BOARD_META[tile_id]["group"]
        if grp in STREET_GROUPS:
            others = [t for t in STREET_GROUPS[grp] if t != tile_id]
            return all(self._tile_owner(t) == player_id for t in others)
        return False

    def _opponent_needs_tile(self, tile_id: int) -> bool:
        my_id = self.my_player_num or 0
        grp = BOARD_META[tile_id]["group"]
        if grp in STREET_GROUPS:
            others = [t for t in STREET_GROUPS[grp] if t != tile_id]
            return any(self._tile_owner(t) not in (0, my_id) for t in others)
        return False

    def _needs_to_act(self) -> bool:
        if not self.is_game_active or self.phase == "finished":
            return False
        my_id = self.my_player_num or 0
        if my_id <= 0:
            return False
        me = self._me()
        if me and (me.get("bankrupt") or not me.get("alive", True)):
            return False
        if self.phase in ("roll", "buy_or_auction", "manage"):
            return self.current_turn == my_id
        if self.phase == "auction" and self.auction:
            return int(self.auction.get("current_bidder", 0)) == my_id
        if self.phase == "debt" and self.debt:
            return int(self.debt.get("player_id", 0)) == my_id
        if self.phase == "trade" and self.pending_trade:
            return int(self.pending_trade.get("to_player", 0)) == my_id
        return False

    def _state_action_key(self) -> tuple:
        if self.phase == "auction" and self.auction:
            return (self.state_seq, self.phase, int(self.auction.get("current_bid", 0)), int(self.auction.get("current_bidder", 0)))
        return (self.state_seq, self.phase, self.current_turn)

    def should_continue_turn(self) -> bool:
        if self._needs_continuation_move:
            self._needs_continuation_move = False
            return self._needs_to_act() and (self._state_action_key() not in self._acted_keys)
        return False

    def should_act_on_reconnect(self) -> bool:
        key = self._state_action_key()
        if self._needs_to_act() and key not in self._scheduled_keys and key not in self._acted_keys:
            self._scheduled_keys.add(key)
            return True
        return False

    def is_critical_turn(self) -> bool:
        return self.phase in ("buy_or_auction", "auction", "debt", "trade")

    def get_legal_moves(self) -> List[Dict[str, Any]]:
        if not self._needs_to_act():
            return []
        my_id = self.my_player_num or 0
        me = self._me()
        my_cash = int(me.get("cash", 0))

        if self.phase == "roll":
            if me.get("in_jail"):
                moves: List[Dict[str, Any]] = [{"cmd": "MonopolyAction", "action": "roll_jail"}]
                if int(me.get("jail_cards", 0)) > 0:
                    moves.append({"cmd": "MonopolyAction", "action": "use_jail_card"})
                if my_cash >= 50:
                    moves.append({"cmd": "MonopolyAction", "action": "pay_bail"})
                return moves
            moves = [{"cmd": "MonopolyRoll"}]
            for tid in self.buildable_tiles:
                moves.append({"cmd": "MonopolyAction", "action": "build_house", "tile_id": tid})
            return moves

        if self.phase == "buy_or_auction":
            tid = self.pending_tile_id
            moves = [{"cmd": "MonopolyAction", "action": "decline_buy"}]
            if 0 <= tid < len(BOARD_META) and my_cash >= int(BOARD_META[tid]["price"]):
                moves.append({"cmd": "MonopolyAction", "action": "buy_property"})
            return moves

        if self.phase == "auction" and self.auction:
            moves = [{"cmd": "MonopolyAuction", "decision": "pass", "amount": 0}]
            cur_bid = int(self.auction.get("current_bid", 0))
            min_next = 10 if cur_bid == 0 else cur_bid + 10
            if my_cash >= min_next and int(self.auction.get("highest_bidder", 0)) != my_id:
                moves.append({"cmd": "MonopolyAuction", "decision": "bid", "amount": min_next})
            return moves

        if self.phase == "debt" and self.debt:
            amt = int(self.debt.get("amount", 0))
            if my_cash >= amt:
                return [{"cmd": "MonopolyAction", "action": "pay_debt"}]
            moves = []
            for tid in self.mortgageable_tiles:
                moves.append({"cmd": "MonopolyAction", "action": "mortgage", "tile_id": tid})
            for tid in self.sellable_tiles:
                moves.append({"cmd": "MonopolyAction", "action": "sell_house", "tile_id": tid})
            if not moves:
                moves.append({"cmd": "MonopolyAction", "action": "declare_bankruptcy"})
            return moves

        if self.phase == "trade" and self.pending_trade:
            return [
                {"cmd": "MonopolyTrade", "action": "accept"},
                {"cmd": "MonopolyTrade", "action": "reject"},
            ]

        if self.phase == "manage":
            moves = [{"cmd": "MonopolyAction", "action": "end_turn"}]
            for tid in self.buildable_tiles:
                moves.append({"cmd": "MonopolyAction", "action": "build_house", "tile_id": tid})
            for tid in self.unmortgageable_tiles:
                moves.append({"cmd": "MonopolyAction", "action": "unmortgage", "tile_id": tid})
            return moves

        return []

    def compute_next_move(self) -> Optional[Dict[str, Any]]:
        legal = self.get_legal_moves()
        if not legal:
            return None
        self._acted_keys.add(self._state_action_key())

        my_id = self.my_player_num or 0
        me = self._me()
        my_cash = int(me.get("cash", 0))

        if self.phase == "roll":
            if me.get("in_jail"):
                unowned = self._unowned_purchasable_count()
                if int(me.get("jail_cards", 0)) > 0 and (unowned >= 4 or self.level >= 2):
                    return {"cmd": "MonopolyAction", "action": "use_jail_card"}
                if my_cash >= 220 and unowned >= 5:
                    return {"cmd": "MonopolyAction", "action": "pay_bail"}
                return {"cmd": "MonopolyAction", "action": "roll_jail"}
            if self.buildable_tiles and my_cash >= 260 and self.level >= 2:
                best_tid = max(self.buildable_tiles, key=lambda t: BOARD_META[t]["price"])
                if my_cash - BOARD_META[best_tid]["house_cost"] >= 120:
                    return {"cmd": "MonopolyAction", "action": "build_house", "tile_id": best_tid}
            return {"cmd": "MonopolyRoll"}

        if self.phase == "buy_or_auction":
            tid = self.pending_tile_id
            if 0 <= tid < len(BOARD_META):
                price = int(BOARD_META[tid]["price"])
                if my_cash >= price:
                    completes = self._would_complete_group(my_id, tid)
                    blocks = self._opponent_needs_tile(tid)
                    reserve = 0 if (completes or blocks or self.level == 1) else 50
                    if my_cash - price >= reserve:
                        return {"cmd": "MonopolyAction", "action": "buy_property"}
            return {"cmd": "MonopolyAction", "action": "decline_buy"}

        if self.phase == "auction" and self.auction:
            tid = int(self.auction.get("tile_id", 0))
            base_price = int(BOARD_META[tid]["price"])
            cur_bid = int(self.auction.get("current_bid", 0))
            min_next = 10 if cur_bid == 0 else cur_bid + 10
            if int(self.auction.get("highest_bidder", 0)) == my_id:
                return {"cmd": "MonopolyAuction", "decision": "pass", "amount": 0}
            completes = self._would_complete_group(my_id, tid)
            blocks = self._opponent_needs_tile(tid)
            mult = 1.25 if completes else (1.08 if blocks else (0.78 if self.level == 1 else 0.95))
            max_willing = int(base_price * mult)
            cash_limit = my_cash if completes else max(0, my_cash - 40)
            if min_next <= min(max_willing, cash_limit):
                return {"cmd": "MonopolyAuction", "decision": "bid", "amount": min_next}
            return {"cmd": "MonopolyAuction", "decision": "pass", "amount": 0}

        if self.phase == "debt" and self.debt:
            amt = int(self.debt.get("amount", 0))
            if my_cash >= amt:
                return {"cmd": "MonopolyAction", "action": "pay_debt"}
            if self.mortgageable_tiles:
                tid = min(self.mortgageable_tiles, key=lambda t: BOARD_META[t]["price"])
                return {"cmd": "MonopolyAction", "action": "mortgage", "tile_id": tid}
            if self.sellable_tiles:
                tid = min(self.sellable_tiles, key=lambda t: BOARD_META[t]["house_cost"])
                return {"cmd": "MonopolyAction", "action": "sell_house", "tile_id": tid}
            return {"cmd": "MonopolyAction", "action": "declare_bankruptcy"}

        if self.phase == "trade" and self.pending_trade:
            tr = self.pending_trade
            o_cash = int(tr.get("offer_cash", 0))
            r_cash = int(tr.get("request_cash", 0))
            o_tiles = [int(t) for t in (tr.get("offer_tiles") or [])]
            r_tiles = [int(t) for t in (tr.get("request_tiles") or [])]
            gain = o_cash
            for tid in o_tiles:
                gain += int(BOARD_META[tid]["price"])
                if self._would_complete_group(my_id, tid):
                    gain += 180
            loss = r_cash
            for tid in r_tiles:
                loss += int(BOARD_META[tid]["price"])
                if self._opponent_needs_tile(tid):
                    loss += 180
            if gain >= loss - (60 if self.level == 1 else 0):
                return {"cmd": "MonopolyTrade", "action": "accept"}
            return {"cmd": "MonopolyTrade", "action": "reject"}

        if self.phase == "manage":
            if self.buildable_tiles:
                best_tid = max(self.buildable_tiles, key=lambda t: BOARD_META[t]["price"])
                cost = int(BOARD_META[best_tid]["house_cost"])
                reserve = 100 if self.level >= 2 else 150
                if my_cash - cost >= reserve:
                    return {"cmd": "MonopolyAction", "action": "build_house", "tile_id": best_tid}
            if self.unmortgageable_tiles:
                tid = min(self.unmortgageable_tiles, key=lambda t: BOARD_META[t]["price"])
                cost = int(round((BOARD_META[tid]["price"] // 2) * 1.1))
                if my_cash - cost >= 180:
                    return {"cmd": "MonopolyAction", "action": "unmortgage", "tile_id": tid}
            return {"cmd": "MonopolyAction", "action": "end_turn"}

        return random.choice(legal)

    def build_move_command(self, move: Any) -> dict:
        if not isinstance(move, dict):
            return {"id": "MonopolyRoll", "data": {}}
        cmd = str(move.get("cmd", "MonopolyAction"))
        if cmd == "MonopolyRoll":
            return {"id": "MonopolyRoll", "data": {}}
        if cmd == "MonopolyAuction":
            return {
                "id": "MonopolyAuction",
                "data": {
                    "decision": str(move.get("decision", "pass")),
                    "amount": int(move.get("amount", 0)),
                },
            }
        if cmd == "MonopolyTrade":
            return {"id": "MonopolyTrade", "data": {"action": str(move.get("action", "reject"))}}
        data_out: Dict[str, Any] = {"action": str(move.get("action", "end_turn"))}
        if "tile_id" in move:
            data_out["tile_id"] = int(move["tile_id"])
        return {"id": "MonopolyAction", "data": data_out}

    def format_state(self) -> str:
        me = self._me()
        return (
            f"[Monopoly] Seq:{self.state_seq} Phase:{self.phase} Turn:P{self.current_turn} | "
            f"Cash:${me.get('cash', 0)} Pos:{me.get('position', 0)}"
        )
