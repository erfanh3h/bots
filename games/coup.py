"""
Coup (کودتا) Game Logic for Cafe Fekr Bot (Supports 2, 3, and 4 Players).

Matches exact rules and socket protocol of kafehfekrbackend/Entities/Games/Coup:
- Supports 2, 3, or 4 players (gamer_id = 1..4).
- Roles: duke, assassin, captain, ambassador, contessa (3 of each = 15 deck cards).
- Client Commands:
  - CoupAction: {"id": "CoupAction", "data": {"action": str, "target_id": int}}
  - CoupChallenge: {"id": "CoupChallenge", "data": {}}
  - CoupBlock: {"id": "CoupBlock", "data": {"block_role": str}}
  - CoupPass: {"id": "CoupPass", "data": {}}
  - CoupLoseInfluence: {"id": "CoupLoseInfluence", "data": {"card_index": int}}
  - CoupExchange: {"id": "CoupExchange", "data": {"keep_indices": [int, ...]}}
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic


COUP_ROLES = ("duke", "assassin", "captain", "ambassador", "contessa")
ROLE_PRIORITY = {
    "duke": 95,
    "assassin": 88,
    "contessa": 82,
    "captain": 76,
    "ambassador": 55,
}
ACTION_ALLOWED_BLOCKS = {
    "foreign_aid": ("duke",),
    "assassinate": ("contessa",),
    "steal": ("captain", "ambassador"),
}


class CoupGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Coup",
            game_type_aliases=["coup", "کودتا", "کودتاه"],
            level=level,
        )
        self.players_count: int = 2
        self.current_turn: int = 1
        self.phase: str = "action"
        self.state_seq: int = 0
        self.players: List[Dict[str, Any]] = []
        self.my_cards: List[Dict[str, Any]] = []
        self.exchange_cards: List[Dict[str, Any]] = []
        self.exchange_keep_count: int = 0

        self.pending_action: Optional[str] = None
        self.pending_actor: int = 0
        self.pending_target: int = 0
        self.pending_claimed_role: str = ""
        self.pending_blocker: int = 0
        self.pending_block_role: str = ""
        self.eligible_responders: List[int] = []
        self.passed_players: List[int] = []
        self.pending_loss_player: int = 0
        self.deck_remaining: int = 11

        self._needs_continuation_move: bool = False
        self._acted_keys: set = set()
        self.rank1: Optional[int] = None
        self.rank2: Optional[int] = None
        self.reset()

    def reset(self):
        self.current_turn = 1
        self.phase = "action"
        self.state_seq = 0
        self.players = []
        self.my_cards = []
        self.exchange_cards = []
        self.exchange_keep_count = 0
        self.pending_action = None
        self.pending_actor = 0
        self.pending_target = 0
        self.pending_claimed_role = ""
        self.pending_blocker = 0
        self.pending_block_role = ""
        self.eligible_responders = []
        self.passed_players = []
        self.pending_loss_player = 0
        self.deck_remaining = 11
        self._needs_continuation_move = False
        self._acted_keys = set()
        self.rank1 = None
        self.rank2 = None

    def _sync_from_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        if "players_count" in data:
            self.players_count = max(2, min(4, int(data["players_count"])))
        if "current_turn" in data:
            self.current_turn = int(data["current_turn"])
        elif "turn" in data:
            self.current_turn = int(data["turn"])
        if "phase" in data and data["phase"]:
            self.phase = str(data["phase"])
        if "state_seq" in data:
            self.state_seq = int(data["state_seq"])
        if "players" in data and isinstance(data["players"], list):
            self.players = [dict(p) for p in data["players"] if isinstance(p, dict)]
            if len(self.players) >= 2:
                self.players_count = len(self.players)
        if "my_cards" in data and isinstance(data["my_cards"], list):
            self.my_cards = [dict(c) for c in data["my_cards"] if isinstance(c, dict)]
        if "exchange_cards" in data and isinstance(data["exchange_cards"], list):
            self.exchange_cards = [dict(c) for c in data["exchange_cards"] if isinstance(c, dict)]
        if "exchange_keep_count" in data:
            self.exchange_keep_count = int(data["exchange_keep_count"] or 0)
        if "pending_action" in data:
            self.pending_action = data["pending_action"]
        if "pending_actor" in data:
            self.pending_actor = int(data["pending_actor"] or 0)
        if "pending_target" in data:
            self.pending_target = int(data["pending_target"] or 0)
        if "pending_claimed_role" in data:
            self.pending_claimed_role = str(data["pending_claimed_role"] or "")
        if "pending_blocker" in data:
            self.pending_blocker = int(data["pending_blocker"] or 0)
        if "pending_block_role" in data:
            self.pending_block_role = str(data["pending_block_role"] or "")
        if "eligible_responders" in data and isinstance(data["eligible_responders"], list):
            self.eligible_responders = [int(x) for x in data["eligible_responders"]]
        if "passed_players" in data and isinstance(data["passed_players"], list):
            self.passed_players = [int(x) for x in data["passed_players"]]
        if "pending_loss_player" in data:
            self.pending_loss_player = int(data["pending_loss_player"] or 0)
        if "deck_remaining" in data:
            self.deck_remaining = int(data["deck_remaining"] or 0)

    def _get_player_entry(self, pid: int) -> Dict[str, Any]:
        for p in self.players:
            if int(p.get("gamer_id", 0)) == int(pid):
                return p
        return {}

    def _is_alive(self, pid: int) -> bool:
        p = self._get_player_entry(pid)
        if not p:
            return True
        return bool(p.get("alive", True))

    def _my_coins(self) -> int:
        my_role = self.my_player_num or 2
        p = self._get_player_entry(my_role)
        return int(p.get("coins", 2))

    def _my_hidden_roles(self) -> List[str]:
        return [
            str(c.get("role", ""))
            for c in self.my_cards
            if not c.get("revealed", False) and c.get("role")
        ]

    def _known_role_counts(self) -> Dict[str, int]:
        counts = {r: 0 for r in COUP_ROLES}
        for r in self._my_hidden_roles():
            if r in counts:
                counts[r] += 1
        for p in self.players:
            for c in p.get("cards", []):
                if isinstance(c, dict) and c.get("revealed", False):
                    r = str(c.get("role", ""))
                    if r in counts:
                        counts[r] += 1
        return counts

    def _alive_opponents(self) -> List[Dict[str, Any]]:
        my_role = self.my_player_num or 2
        return [
            p for p in self.players
            if int(p.get("gamer_id", 0)) != my_role and bool(p.get("alive", False))
        ]

    def _prompt_key(self) -> Tuple[int, str, int]:
        my_role = self.my_player_num or 2
        return (self.state_seq, self.phase, my_role)

    def _needs_my_action(self) -> bool:
        if not self.is_game_active or self.phase == "finished":
            return False
        my_role = self.my_player_num or 2
        if not self._is_alive(my_role):
            return False
        if self._prompt_key() in self._acted_keys:
            return False

        if self.phase == "action":
            return self.current_turn == my_role
        if self.phase in ("challenge_action", "block_action", "challenge_block"):
            return my_role in self.eligible_responders and my_role not in self.passed_players
        if self.phase == "lose_influence":
            return self.pending_loss_player == my_role
        if self.phase == "exchange":
            return self.current_turn == my_role and len(self.exchange_cards) >= max(1, self.exchange_keep_count)
        return False

    def should_continue_turn(self) -> bool:
        if self._needs_continuation_move:
            self._needs_continuation_move = False
            return self._needs_my_action()
        return False

    def should_act_on_reconnect(self) -> bool:
        return self._needs_my_action()

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "GameData":
            self.reset()
            if isinstance(payload, dict):
                gamers = payload.get("gamers", [])
                if isinstance(gamers, list) and len(gamers) >= 2:
                    self.players_count = max(2, min(4, len(gamers)))
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict):
                    self._sync_from_dict(g_data)
            return True

        elif cmd_id == "UserData":
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
                if self.phase == "exchange" and self._needs_my_action():
                    self._needs_continuation_move = True
            return True

        elif cmd_id == "StartGame":
            self.is_game_active = True
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
            return True

        elif cmd_id == "CurrentTurn":
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
            else:
                self.current_turn = int(payload)
            return True

        elif cmd_id == "CoupState":
            self.is_game_active = True
            if isinstance(payload, dict):
                self._sync_from_dict(payload)
            if self._needs_my_action():
                self._needs_continuation_move = True
            return True

        elif cmd_id == "CoupEvent":
            if isinstance(payload, dict) and isinstance(payload.get("state"), dict):
                self._sync_from_dict(payload["state"])
            return True

        elif cmd_id == "WinHappened":
            if isinstance(payload, dict):
                if payload.get("rank1") is not None:
                    self.rank1 = int(payload["rank1"])
                if payload.get("rank2") is not None:
                    self.rank2 = int(payload["rank2"])
            self.phase = "finished"
            self._needs_continuation_move = False
            return True

        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                gamers = payload.get("gamers", [])
                if isinstance(gamers, list) and len(gamers) >= 2:
                    self.players_count = max(2, min(4, len(gamers)))
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict):
                    self._sync_from_dict(g_data)
                u_data = payload.get("user_data", {})
                if isinstance(u_data, dict):
                    self._sync_from_dict(u_data)
            return True

        return False

    def get_legal_moves(self) -> List[Dict[str, Any]]:
        my_role = self.my_player_num or 2
        if not self._is_alive(my_role) or self.phase == "finished":
            return []

        if self.phase == "action":
            if self.current_turn != my_role:
                return []
            my_coins = self._my_coins()
            opps = self._alive_opponents()
            if not opps:
                return []

            moves: List[Dict[str, Any]] = []
            if my_coins >= 7:
                for opp in opps:
                    moves.append({"cmd": "CoupAction", "action": "coup", "target_id": int(opp["gamer_id"])})
            if my_coins >= 10:
                return moves

            moves.append({"cmd": "CoupAction", "action": "income", "target_id": 0})
            moves.append({"cmd": "CoupAction", "action": "foreign_aid", "target_id": 0})
            moves.append({"cmd": "CoupAction", "action": "tax", "target_id": 0})
            moves.append({"cmd": "CoupAction", "action": "exchange", "target_id": 0})
            if my_coins >= 3:
                for opp in opps:
                    moves.append({"cmd": "CoupAction", "action": "assassinate", "target_id": int(opp["gamer_id"])})
            for opp in opps:
                moves.append({"cmd": "CoupAction", "action": "steal", "target_id": int(opp["gamer_id"])})
            return moves

        if self.phase == "challenge_action":
            if my_role not in self.eligible_responders or my_role in self.passed_players:
                return []
            return [{"cmd": "CoupPass"}, {"cmd": "CoupChallenge"}]

        if self.phase == "block_action":
            if my_role not in self.eligible_responders or my_role in self.passed_players:
                return []
            moves = [{"cmd": "CoupPass"}]
            for b_role in ACTION_ALLOWED_BLOCKS.get(self.pending_action or "", ()):
                moves.append({"cmd": "CoupBlock", "block_role": b_role})
            return moves

        if self.phase == "challenge_block":
            if my_role not in self.eligible_responders or my_role in self.passed_players:
                return []
            return [{"cmd": "CoupPass"}, {"cmd": "CoupChallenge"}]

        if self.phase == "lose_influence":
            if self.pending_loss_player != my_role:
                return []
            moves = []
            for idx, c in enumerate(self.my_cards):
                if not c.get("revealed", False):
                    moves.append({"cmd": "CoupLoseInfluence", "card_index": idx, "role": c.get("role", "")})
            return moves

        if self.phase == "exchange":
            if self.current_turn != my_role or not self.exchange_cards:
                return []
            keep_cnt = max(1, min(self.exchange_keep_count or len(self._my_hidden_roles()), len(self.exchange_cards)))
            return [{"cmd": "CoupExchange", "keep_count": keep_cnt}]

        return []

    def is_critical_turn(self) -> bool:
        my_role = self.my_player_num or 2
        if self.phase in ("lose_influence", "challenge_action", "challenge_block"):
            return True
        if self.phase == "block_action" and self.pending_action == "assassinate" and self.pending_target == my_role:
            return True
        if self._my_coins() >= 7:
            return True
        return len(self._my_hidden_roles()) <= 1

    def _pick_best_target(self, prefer_rich: bool = False) -> int:
        opps = self._alive_opponents()
        if not opps:
            return 0
        def threat_score(opp: Dict[str, Any]) -> float:
            coins = int(opp.get("coins", 0))
            cards = int(opp.get("alive_cards", 2))
            base = coins * (2.5 if prefer_rich else 1.6) + (2 - cards) * 6.0
            if coins >= 7:
                base += 8.0
            return base + random.uniform(0.0, 1.5)
        opps_sorted = sorted(opps, key=threat_score, reverse=True)
        return int(opps_sorted[0]["gamer_id"])

    def _choose_action(self) -> Dict[str, Any]:
        my_coins = self._my_coins()
        hidden = self._my_hidden_roles()
        target = self._pick_best_target(prefer_rich=False)
        rich_target = self._pick_best_target(prefer_rich=True)

        if my_coins >= 10:
            return {"cmd": "CoupAction", "action": "coup", "target_id": target}

        if my_coins >= 7:
            if self.level >= 2 or random.random() < 0.85:
                return {"cmd": "CoupAction", "action": "coup", "target_id": target}

        if my_coins >= 3:
            if "assassin" in hidden and random.random() < 0.85:
                return {"cmd": "CoupAction", "action": "assassinate", "target_id": target}
            bluff_assassinate = 0.08 if self.level == 1 else (0.18 if self.level == 2 else 0.24)
            if random.random() < bluff_assassinate:
                return {"cmd": "CoupAction", "action": "assassinate", "target_id": target}

        candidates: List[Tuple[float, Dict[str, Any]]] = []
        candidates.append((25.0, {"cmd": "CoupAction", "action": "income", "target_id": 0}))
        candidates.append((34.0 if self.level >= 2 else 30.0, {"cmd": "CoupAction", "action": "foreign_aid", "target_id": 0}))

        if "duke" in hidden:
            candidates.append((85.0, {"cmd": "CoupAction", "action": "tax", "target_id": 0}))
        else:
            bluff_duke = 0.14 if self.level == 1 else (0.30 if self.level == 2 else 0.40)
            if random.random() < bluff_duke:
                candidates.append((62.0, {"cmd": "CoupAction", "action": "tax", "target_id": 0}))

        rich_coins = int(self._get_player_entry(rich_target).get("coins", 0))
        if rich_coins >= 1:
            if "captain" in hidden:
                candidates.append((72.0 + rich_coins * 3.0, {"cmd": "CoupAction", "action": "steal", "target_id": rich_target}))
            elif self.level >= 2 and random.random() < 0.22:
                candidates.append((50.0, {"cmd": "CoupAction", "action": "steal", "target_id": rich_target}))

        if "ambassador" in hidden:
            weak_hand = ("duke" not in hidden and "assassin" not in hidden)
            candidates.append((68.0 if weak_hand else 32.0, {"cmd": "CoupAction", "action": "exchange", "target_id": 0}))
        elif self.level >= 2 and "duke" not in hidden and random.random() < 0.14:
            candidates.append((42.0, {"cmd": "CoupAction", "action": "exchange", "target_id": 0}))

        noise = 28.0 if self.level == 1 else (12.0 if self.level == 2 else 6.0)
        candidates.sort(key=lambda item: item[0] + random.uniform(-noise, noise), reverse=True)
        return candidates[0][1]

    def _choose_challenge_action(self) -> Dict[str, Any]:
        my_role = self.my_player_num or 2
        claimed = self.pending_claimed_role
        counts = self._known_role_counts()
        if claimed in counts and counts[claimed] >= 3:
            return {"cmd": "CoupChallenge"}

        if (
            self.pending_action == "assassinate"
            and self.pending_target == my_role
            and len(self._my_hidden_roles()) == 1
            and "contessa" not in self._my_hidden_roles()
        ):
            if random.random() < 0.45:
                return {"cmd": "CoupChallenge"}

        base_chance = 0.12 if self.level == 1 else (0.18 if self.level == 2 else 0.22)
        if claimed in counts and counts[claimed] == 2:
            base_chance += 0.28
        if self.pending_target == my_role:
            base_chance += 0.08
        if random.random() < base_chance:
            return {"cmd": "CoupChallenge"}
        return {"cmd": "CoupPass"}

    def _choose_block_action(self) -> Dict[str, Any]:
        my_role = self.my_player_num or 2
        hidden = self._my_hidden_roles()
        action = self.pending_action or ""

        if action == "foreign_aid":
            if "duke" in hidden:
                if self.level == 1 and random.random() < 0.20:
                    return {"cmd": "CoupPass"}
                return {"cmd": "CoupBlock", "block_role": "duke"}
            if self.level >= 2 and random.random() < 0.18:
                return {"cmd": "CoupBlock", "block_role": "duke"}
            return {"cmd": "CoupPass"}

        if action == "assassinate" and self.pending_target == my_role:
            if "contessa" in hidden:
                return {"cmd": "CoupBlock", "block_role": "contessa"}
            if len(hidden) == 1:
                if random.random() < (0.50 if self.level == 1 else 0.80):
                    return {"cmd": "CoupBlock", "block_role": "contessa"}
            elif self.level >= 2 and random.random() < 0.24:
                return {"cmd": "CoupBlock", "block_role": "contessa"}
            return {"cmd": "CoupPass"}

        if action == "steal" and self.pending_target == my_role:
            if "captain" in hidden:
                return {"cmd": "CoupBlock", "block_role": "captain"}
            if "ambassador" in hidden:
                return {"cmd": "CoupBlock", "block_role": "ambassador"}
            if self.level >= 2 and random.random() < 0.20:
                return {"cmd": "CoupBlock", "block_role": random.choice(["captain", "ambassador"])}
            return {"cmd": "CoupPass"}

        return {"cmd": "CoupPass"}

    def _choose_challenge_block(self) -> Dict[str, Any]:
        my_role = self.my_player_num or 2
        claimed = self.pending_block_role
        counts = self._known_role_counts()
        if claimed in counts and counts[claimed] >= 3:
            return {"cmd": "CoupChallenge"}

        chance = 0.14 if self.level == 1 else (0.24 if self.level == 2 else 0.30)
        if claimed in counts and counts[claimed] == 2:
            chance += 0.28
        if self.pending_actor == my_role:
            chance += 0.12
            blocker_entry = self._get_player_entry(self.pending_blocker)
            if self.pending_action == "assassinate" and int(blocker_entry.get("alive_cards", 2)) == 1:
                chance = max(chance, 0.55)
        if random.random() < chance:
            return {"cmd": "CoupChallenge"}
        return {"cmd": "CoupPass"}

    def _choose_lose_influence(self, legal_moves: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.level == 1:
            return random.choice(legal_moves)
        scored = sorted(
            legal_moves,
            key=lambda m: ROLE_PRIORITY.get(str(m.get("role", "")), 50),
        )
        return scored[0]

    def _choose_exchange(self) -> Dict[str, Any]:
        keep_cnt = max(1, min(self.exchange_keep_count or len(self._my_hidden_roles()), len(self.exchange_cards)))
        indexed = list(enumerate(self.exchange_cards))
        if self.level == 1:
            chosen = [idx for idx, _ in random.sample(indexed, keep_cnt)]
            return {"cmd": "CoupExchange", "keep_indices": sorted(chosen)}

        chosen_indices: List[int] = []
        chosen_roles: set = set()
        indexed.sort(key=lambda item: ROLE_PRIORITY.get(str(item[1].get("role", "")), 50), reverse=True)
        for idx, card in indexed:
            role = str(card.get("role", ""))
            if len(chosen_indices) < keep_cnt and role not in chosen_roles:
                chosen_indices.append(idx)
                chosen_roles.add(role)
        for idx, _ in indexed:
            if len(chosen_indices) < keep_cnt and idx not in chosen_indices:
                chosen_indices.append(idx)
        return {"cmd": "CoupExchange", "keep_indices": sorted(chosen_indices)}

    def compute_next_move(self) -> Any:
        self._needs_continuation_move = False
        legal_moves = self.get_legal_moves()
        if not legal_moves:
            return None

        self._acted_keys.add(self._prompt_key())

        if self.phase == "action":
            return self._choose_action()
        if self.phase == "challenge_action":
            return self._choose_challenge_action()
        if self.phase == "block_action":
            return self._choose_block_action()
        if self.phase == "challenge_block":
            return self._choose_challenge_block()
        if self.phase == "lose_influence":
            return self._choose_lose_influence(legal_moves)
        if self.phase == "exchange":
            return self._choose_exchange()
        return legal_moves[0]

    def build_move_command(self, move: Any) -> dict:
        if not isinstance(move, dict):
            return {"id": "CoupPass", "data": {}}
        cmd = str(move.get("cmd", "CoupPass"))
        if cmd == "CoupAction":
            return {
                "id": "CoupAction",
                "data": {
                    "action": str(move.get("action", "income")),
                    "target_id": int(move.get("target_id", 0)),
                },
            }
        if cmd == "CoupBlock":
            return {
                "id": "CoupBlock",
                "data": {
                    "block_role": str(move.get("block_role", "duke")),
                },
            }
        if cmd == "CoupLoseInfluence":
            return {
                "id": "CoupLoseInfluence",
                "data": {
                    "card_index": int(move.get("card_index", 0)),
                },
            }
        if cmd == "CoupExchange":
            return {
                "id": "CoupExchange",
                "data": {
                    "keep_indices": [int(i) for i in move.get("keep_indices", [])],
                },
            }
        if cmd == "CoupChallenge":
            return {"id": "CoupChallenge", "data": {}}
        return {"id": "CoupPass", "data": {}}

    def format_state(self) -> str:
        return (
            f"[COUP] Seq:{self.state_seq} Phase:{self.phase} Turn:P{self.current_turn} | "
            f"Coins:{self._my_coins()} MyCards:{self._my_hidden_roles()}"
        )
