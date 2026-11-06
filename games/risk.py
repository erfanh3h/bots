"""
Risk Strike AI Bot Game Logic for Cafe Fekr.

Implements full tactical decision-making for the tabletop game Risk Strike:
- Card drawing strategy (Continent vs Strategy vs Mixed)
- Strategy / Tactic card usage (Backup, Expand, Destroy, Bomb, Spy, Canon, Cancel, Army)
- Continent attack selection & Domination Token pursuit (first to 2 Domination Tokens wins)
- Attacker & Defender Army commitment and Ceasefire (Cancel) defense
"""

import random
from typing import Any, Dict, List, Optional
from .base_game import BaseGameLogic


CONTINENT_ADJACENCY: Dict[str, List[str]] = {
    "Asia": ["Asia", "Australia", "Europe", "Africa", "NorthAmerica"],
    "Australia": ["Australia", "Asia"],
    "Europe": ["Europe", "Asia", "NorthAmerica", "Africa"],
    "Africa": ["Africa", "Europe", "Asia", "SouthAmerica"],
    "SouthAmerica": ["SouthAmerica", "NorthAmerica", "Africa"],
    "NorthAmerica": ["NorthAmerica", "Europe", "Asia", "SouthAmerica"],
}

ALL_CONTINENTS = ["Asia", "NorthAmerica", "Europe", "Africa", "Australia", "SouthAmerica"]


class RiskGameLogic(BaseGameLogic):
    def __init__(self, level: int = 2):
        super().__init__(
            game_type="Risk",
            game_type_aliases=["risk", "risk_strike", "riskstrike", "ریسک", "ریسک استرایک"],
            level=level,
        )
        self.reset()

    def reset(self):
        self.current_turn: int = 1
        self.game_state: str = "StartGame"
        self.players_data: List[Dict[str, Any]] = []
        self.active_player_indexes: List[int] = [1, 2]
        self.my_continents: Dict[str, int] = {c: 0 for c in ALL_CONTINENTS}
        self.my_strategies: List[str] = []
        self.my_tokens: List[str] = []
        self.free_tokens: List[str] = list(ALL_CONTINENTS)
        self.active_attack: Optional[Dict[str, Any]] = None
        self.ignore_adjacency: bool = False
        self._pending_action: bool = False

    def _sync_my_private(self, priv: Dict[str, Any]):
        if not isinstance(priv, dict):
            return
        if "index" in priv and self.my_player_num is None:
            self.my_player_num = int(priv["index"])
        if isinstance(priv.get("continents"), dict):
            for c in ALL_CONTINENTS:
                self.my_continents[c] = int(priv["continents"].get(c, 0))
        if isinstance(priv.get("strategies"), list):
            self.my_strategies = [str(s) for s in priv["strategies"]]
        if isinstance(priv.get("tokens"), list):
            self.my_tokens = [str(t) for t in priv["tokens"]]

    def _sync_game_data(self, gd: Dict[str, Any]):
        if not isinstance(gd, dict):
            return
        if "current_turn" in gd:
            self.current_turn = int(gd["current_turn"])
        if "game_state" in gd:
            self.game_state = str(gd["game_state"])
        if isinstance(gd.get("active_player_indexes"), list):
            self.active_player_indexes = [int(x) for x in gd["active_player_indexes"]]
        if isinstance(gd.get("players_data"), list):
            self.players_data = gd["players_data"]
            my_role = self.my_player_num or 2
            for p in self.players_data:
                if isinstance(p, dict) and int(p.get("index", 0)) == my_role:
                    if isinstance(p.get("continents"), dict):
                        for c in ALL_CONTINENTS:
                            self.my_continents[c] = int(p["continents"].get(c, 0))
                    if isinstance(p.get("tokens"), list):
                        self.my_tokens = [str(t) for t in p["tokens"]]
        if isinstance(gd.get("tokens"), list):
            self.free_tokens = [str(t) for t in gd["tokens"]]
        if "active_attack" in gd:
            self.active_attack = gd["active_attack"]

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        my_role = self.my_player_num or 2
        self._pending_action = False

        if cmd_id in ("GameData", "ReconnectData") and isinstance(payload, dict):
            gd = payload.get("game_data", payload)
            self._sync_game_data(gd)
            if self.current_turn == my_role and self.game_state in ("Draw", "StartGame", "SelectAction"):
                self._pending_action = True
            return True

        if cmd_id == "UserData" and isinstance(payload, dict):
            self._sync_my_private(payload)
            return True

        if cmd_id in ("DrawCard", "CurrentTurn"):
            if isinstance(payload, dict):
                self.current_turn = int(payload.get("turn", self.current_turn))
                self.game_state = str(payload.get("game_state", "Draw"))
            elif isinstance(payload, int):
                self.current_turn = int(payload)
                self.game_state = "Draw"
            self.ignore_adjacency = False
            self.active_attack = None
            if self.current_turn == my_role:
                self._pending_action = True
            return True

        if cmd_id == "DrawResult" and isinstance(payload, dict):
            gamer_id = int(payload.get("gamer_id", 0))
            new_data = payload.get("new_data")
            if isinstance(new_data, dict):
                self._update_player_global(new_data)
            if "game_state" in payload:
                self.game_state = str(payload["game_state"])
            else:
                self.game_state = "SelectAction"
            if gamer_id == my_role and self.current_turn == my_role:
                self._pending_action = True
            return True

        if cmd_id == "DrawResultPrivate" and isinstance(payload, dict):
            if isinstance(payload.get("new_user_data"), dict):
                self._sync_my_private(payload["new_user_data"])
            if self.current_turn == my_role and self.game_state in ("DrawResult", "SelectAction"):
                self.game_state = "SelectAction"
                self._pending_action = True
            return True

        if cmd_id == "DeclareAttack" and isinstance(payload, dict):
            atk_id = int(payload.get("gamer_id", self.current_turn))
            tgt_id = int(payload.get("target_index", 0))
            src_c = str(payload.get("source_continent", "Asia"))
            tgt_c = str(payload.get("target_continent", "Asia"))
            self.game_state = str(payload.get("game_state", "AttackerArmy"))
            self.active_attack = {
                "attacker_id": atk_id,
                "defender_id": tgt_id,
                "source_continent": src_c,
                "target_continent": tgt_c,
            }
            if atk_id == my_role and self.game_state in ("DeclareAttack", "AttackerArmy"):
                self._pending_action = True
            elif tgt_id == my_role and self.game_state == "DefenderArmy":
                self._pending_action = True
            return True

        if cmd_id == "AttackArmy" and isinstance(payload, dict):
            tgt_id = int(payload.get("target_index", (self.active_attack or {}).get("defender_id", 0)))
            self.game_state = str(payload.get("game_state", "DefenderArmy"))
            if self.active_attack is not None:
                self.active_attack["attacker_army"] = int(payload.get("count", 0))
            if tgt_id == my_role:
                self._pending_action = True
            return True

        if cmd_id in ("RollResult", "Attack") and isinstance(payload, dict):
            if isinstance(payload.get("players_data"), list):
                self.players_data = payload["players_data"]
                for p in self.players_data:
                    if isinstance(p, dict) and int(p.get("index", 0)) == my_role:
                        if isinstance(p.get("continents"), dict):
                            for c in ALL_CONTINENTS:
                                self.my_continents[c] = int(p["continents"].get(c, 0))
                        if isinstance(p.get("tokens"), list):
                            self.my_tokens = [str(t) for t in p["tokens"]]
            self.active_attack = None
            self.game_state = str(payload.get("game_state", "SelectAction"))
            if not payload.get("is_game_finished", False) and self.current_turn == my_role and cmd_id == "Attack":
                self._pending_action = True
            return True

        if cmd_id == "StrategyResult" and isinstance(payload, dict):
            if isinstance(payload.get("players_data"), list):
                self.players_data = payload["players_data"]
            if payload.get("ignore_adjacency") and int(payload.get("gamer_id", 0)) == my_role:
                self.ignore_adjacency = True
            self.game_state = str(payload.get("game_state", "SelectAction"))
            if self.current_turn == my_role and self.game_state == "SelectAction":
                self._pending_action = True
            return True

        if cmd_id == "PassTurn" and isinstance(payload, dict):
            if isinstance(payload.get("new_data"), dict):
                self._update_player_global(payload["new_data"])
            return True

        return False

    def _update_player_global(self, p_dict: Dict[str, Any]):
        idx = int(p_dict.get("index", 0))
        replaced = False
        for i, existing in enumerate(self.players_data):
            if isinstance(existing, dict) and int(existing.get("index", 0)) == idx:
                self.players_data[i] = p_dict
                replaced = True
                break
        if not replaced and idx > 0:
            self.players_data.append(p_dict)
        if idx == (self.my_player_num or 2):
            if isinstance(p_dict.get("continents"), dict):
                for c in ALL_CONTINENTS:
                    self.my_continents[c] = int(p_dict["continents"].get(c, 0))
            if isinstance(p_dict.get("tokens"), list):
                self.my_tokens = [str(t) for t in p_dict["tokens"]]

    def should_continue_turn(self) -> bool:
        return self._pending_action

    def should_act_on_reconnect(self) -> bool:
        my_role = self.my_player_num or 2
        if self.active_attack and int(self.active_attack.get("defender_id", 0)) == my_role and self.game_state == "DefenderArmy":
            return True
        return self.current_turn == my_role

    def _count_my_strategy(self, name: str) -> int:
        return sum(1 for s in self.my_strategies if s.lower() == name.lower())

    def get_legal_moves(self) -> List[Dict[str, Any]]:
        my_role = self.my_player_num or 2

        # 1. Defense response when an opponent attacks the Bot
        if self.game_state == "DefenderArmy" and self.active_attack and int(self.active_attack.get("defender_id", 0)) == my_role:
            moves: List[Dict[str, Any]] = []
            army_cnt = self._count_my_strategy("Army")
            for c in range(0, min(3, army_cnt) + 1):
                moves.append({"action": "defender_army", "count": c})
            if self._count_my_strategy("Cancel") > 0:
                moves.append({"action": "defender_cancel"})
            return moves

        # All other states require it to be the Bot's turn
        if self.current_turn != my_role:
            return []

        # 2. Draw Phase: choose draw_type 1 (2 Continents), 2 (2 Strategies), or 3 (1 Continent + 1 Strategy)
        if self.game_state in ("StartGame", "Draw"):
            return [
                {"action": "draw", "draw_type": 1},
                {"action": "draw", "draw_type": 2},
                {"action": "draw", "draw_type": 3},
            ]

        # 3. Attacker Army Commitment Phase
        if self.game_state in ("DeclareAttack", "AttackerArmy") and self.active_attack:
            army_cnt = self._count_my_strategy("Army")
            return [{"action": "attacker_army", "count": c} for c in range(0, min(3, army_cnt) + 1)]

        # 4. SelectAction Phase: Strategy cards, Declare Attack, or Pass Turn
        if self.game_state in ("DrawResult", "SelectAction", "ActionResult"):
            moves = [{"action": "pass"}]

            # Available non-reactive Strategy cards in hand
            for strat in ("Backup", "Expand", "Destroy", "Bomb", "Spy", "Canon"):
                if self._count_my_strategy(strat) > 0:
                    moves.append({"action": "strategy", "strategy": strat})

            # Legal Continent Attacks against active opponents
            for src_c, my_cnt in self.my_continents.items():
                if my_cnt <= 0:
                    continue
                connected = ALL_CONTINENTS if self.ignore_adjacency else CONTINENT_ADJACENCY.get(src_c, [src_c])
                for p in self.players_data:
                    if not isinstance(p, dict):
                        continue
                    opp_id = int(p.get("index", 0))
                    if opp_id == my_role or opp_id not in self.active_player_indexes:
                        continue
                    opp_conts = p.get("continents", {})
                    if not isinstance(opp_conts, dict):
                        continue
                    for tgt_c in connected:
                        if int(opp_conts.get(tgt_c, 0)) > 0:
                            moves.append({
                                "action": "declare_attack",
                                "source_continent": src_c,
                                "target_continent": tgt_c,
                                "target_index": opp_id,
                            })
            return moves

        return []

    def is_critical_turn(self) -> bool:
        if len(self.my_tokens) >= 1:
            return True
        if self.active_attack is not None:
            return True
        return False

    def _score_move(self, move: Dict[str, Any]) -> float:
        act = move.get("action")
        my_total_c = sum(self.my_continents.values())
        my_army_cnt = self._count_my_strategy("Army")

        if act == "draw":
            dt = int(move.get("draw_type", 3))
            if dt == 1:
                # 2 Continents: great when low on continents or pushing for domination
                return 80.0 if my_total_c <= 4 else 55.0
            elif dt == 3:
                # 1 Continent + 1 Strategy: balanced championship choice
                return 75.0
            else:
                # 2 Strategies: good when we already have many continents but few tactics
                return 70.0 if len(self.my_strategies) <= 1 and my_total_c >= 6 else 40.0

        if act == "defender_cancel":
            # Cancel attack if defending a continent where we hold a token or only have 1 card left
            tgt_c = (self.active_attack or {}).get("target_continent", "Asia")
            if tgt_c in self.my_tokens or self.my_continents.get(tgt_c, 0) <= 1:
                return 160.0
            return 65.0

        if act == "defender_army":
            cnt = int(move.get("count", 0))
            tgt_c = (self.active_attack or {}).get("target_continent", "Asia")
            def_cards = self.my_continents.get(tgt_c, 1)
            atk_army = int((self.active_attack or {}).get("attacker_army", 0))
            if tgt_c in self.my_tokens or def_cards == 1 or atk_army > 0:
                return 60.0 + cnt * 35.0
            return 50.0 + (20.0 if cnt == 1 else -cnt * 10.0)

        if act == "attacker_army":
            cnt = int(move.get("count", 0))
            src_c = (self.active_attack or {}).get("source_continent", "Asia")
            my_c = self.my_continents.get(src_c, 1)
            # Commit 1-2 armies to reach 3+ dice
            needed = max(0, 3 - my_c)
            if cnt == min(my_army_cnt, max(1, needed)):
                return 110.0
            return 70.0 - abs(cnt - needed) * 15.0

        if act == "strategy":
            strat = move.get("strategy")
            if strat == "Backup":
                return 135.0
            if strat == "Expand":
                return 125.0
            if strat == "Destroy":
                return 145.0
            if strat == "Spy":
                return 120.0
            if strat == "Bomb":
                return 115.0
            if strat == "Canon":
                return 95.0 if my_total_c >= 3 else 30.0

        if act == "declare_attack":
            src_c = str(move.get("source_continent"))
            tgt_c = str(move.get("target_continent"))
            tgt_idx = int(move.get("target_index", 0))
            my_c = self.my_continents.get(src_c, 0)
            opp_c = 1
            opp_tokens = []
            for p in self.players_data:
                if isinstance(p, dict) and int(p.get("index", 0)) == tgt_idx:
                    opp_c = int(p.get("continents", {}).get(tgt_c, 1))
                    opp_tokens = p.get("tokens", [])
                    break

            # Base tactical advantage: our attacking cards + army cards vs opponent's defending cards
            advantage = (my_c + min(2, my_army_cnt)) - opp_c
            score = 45.0 + advantage * 28.0

            # Huge bonus if opponent only has 1 card in tgt_c (chance to wipe out & claim Domination Token!)
            if opp_c == 1:
                score += 45.0
            # Priority target if opponent holds a Domination Token
            if tgt_c in opp_tokens:
                score += 55.0
            elif len(opp_tokens) >= 1:
                score += 25.0
            # Penalty for attacking with our last card of a continent we hold a token for
            if src_c in self.my_tokens and my_c <= 2:
                score -= 60.0
            elif my_c == 1 and opp_c >= 2:
                score -= 50.0
            return score

        if act == "pass":
            return 50.0

        return 0.0

    def compute_next_move(self) -> Any:
        legal_moves = self.get_legal_moves()
        if not legal_moves:
            return None
        if len(legal_moves) == 1:
            return legal_moves[0]

        noise = 30.0 if self.level == 1 else (10.0 if self.level == 2 else 0.0)
        scored = [
            (self._score_move(m) + (random.uniform(-noise, noise) if noise > 0 else 0.0), m)
            for m in legal_moves
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def build_move_command(self, move: Any) -> dict:
        if not isinstance(move, dict):
            return {"id": "PassTurn", "data": {}}
        act = move.get("action")
        if act == "draw":
            return {"id": "DrawCard", "data": {"draw_type": int(move.get("draw_type", 3))}}
        if act == "declare_attack":
            return {
                "id": "DeclareAttack",
                "data": {
                    "source_continent": move["source_continent"],
                    "target_continent": move["target_continent"],
                    "target_index": int(move["target_index"]),
                },
            }
        if act == "attacker_army":
            return {"id": "AttackArmy", "data": {"count": int(move.get("count", 0))}}
        if act == "defender_army":
            return {"id": "DefenderArmy", "data": {"count": int(move.get("count", 0))}}
        if act == "defender_cancel":
            return {"id": "DefenderArmy", "data": {"count": 0, "cancel": True}}
        if act == "strategy":
            return {"id": "UseStrategy", "data": {"strategy": move.get("strategy")}}
        return {"id": "PassTurn", "data": {}}

    def format_state(self) -> str:
        return (
            f"[Risk] Turn: P{self.current_turn} | State: {self.game_state} | "
            f"Tokens: {self.my_tokens} | Continents: {sum(self.my_continents.values())} | "
            f"Strategies: {len(self.my_strategies)}"
        )
