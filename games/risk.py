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

try:
    from Bots.games.base_game import BaseGameLogic
except ImportError:
    from games.base_game import BaseGameLogic


CONTINENT_ADJACENCY: Dict[str, List[str]] = {
    "Asia": ["Asia", "Australia", "Europe", "Africa", "NorthAmerica"],
    "Australia": ["Australia", "Asia"],
    "Europe": ["Europe", "Asia", "NorthAmerica", "Africa"],
    "Africa": ["Africa", "Europe", "Asia", "SouthAmerica"],
    "SouthAmerica": ["SouthAmerica", "NorthAmerica", "Africa"],
    "NorthAmerica": ["NorthAmerica", "Europe", "Asia", "SouthAmerica"],
}

ALL_CONTINENTS = ["Asia", "NorthAmerica", "Europe", "Africa", "Australia", "SouthAmerica"]

DOMINATION_THRESHOLDS: Dict[str, int] = {
    "Asia": 8,
    "NorthAmerica": 6,
    "Europe": 5,
    "Africa": 4,
    "Australia": 3,
    "SouthAmerica": 3,
}


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
        self.is_game_finished: bool = False
        self.players_data: List[Dict[str, Any]] = []
        self.active_player_indexes: List[int] = [1, 2]
        self.my_continents: Dict[str, int] = {c: 0 for c in ALL_CONTINENTS}
        self.my_strategies: List[str] = []
        self.my_tokens: List[str] = []
        self.free_tokens: List[str] = list(ALL_CONTINENTS)
        self.active_attack: Optional[Dict[str, Any]] = None
        self.ignore_adjacency: bool = False
        self.attacks_this_turn: int = 0
        self.canon_played_this_turn: bool = False
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

        if cmd_id == "GameData" and isinstance(payload, dict):
            gd = payload.get("game_data", payload)
            self._sync_game_data(gd)
            return True

        if cmd_id == "ReconnectData" and isinstance(payload, dict):
            gd = payload.get("game_data", payload)
            self._sync_game_data(gd)
            if isinstance(payload.get("user_data"), dict):
                self._sync_my_private(payload["user_data"])
            if not self.is_game_finished:
                if self.game_state == "DefenderArmy" and self.active_attack and int(self.active_attack.get("defender_id", 0)) == my_role:
                    self._pending_action = True
                elif self.current_turn == my_role and self.game_state in ("Draw", "SelectAction", "AttackerArmy"):
                    self._pending_action = True
            return True

        if cmd_id == "UserData" and isinstance(payload, dict):
            self._sync_my_private(payload)
            return True

        if cmd_id == "StartGame":
            if isinstance(payload, dict):
                if "turn" in payload:
                    self.current_turn = int(payload["turn"])
                if "game_state" in payload:
                    self.game_state = str(payload["game_state"])
            return True

        if cmd_id in ("DrawCard", "CurrentTurn"):
            if isinstance(payload, dict):
                self.current_turn = int(payload.get("turn", self.current_turn))
                self.game_state = str(payload.get("game_state", "Draw"))
            elif isinstance(payload, int):
                self.current_turn = int(payload)
                self.game_state = "Draw"
            self.ignore_adjacency = False
            self.attacks_this_turn = 0
            self.canon_played_this_turn = False
            self.active_attack = None
            if not self.is_game_finished and self.current_turn == my_role:
                self._pending_action = True
            return True

        if cmd_id == "DrawResult" and isinstance(payload, dict):
            new_data = payload.get("new_data")
            if isinstance(new_data, dict):
                self._update_player_global(new_data)
            if isinstance(payload.get("players_data"), list):
                self.players_data = payload["players_data"]
            if isinstance(payload.get("tokens"), list):
                self.free_tokens = [str(t) for t in payload["tokens"]]
            if payload.get("is_game_finished", False):
                self.is_game_finished = True
                self.game_state = "GameFinished"
                self._pending_action = False
                return True
            if "game_state" in payload:
                self.game_state = str(payload["game_state"])
            else:
                self.game_state = "SelectAction"
            # Wait for DrawResultPrivate so our private hand is synced before acting
            return True

        if cmd_id == "DrawResultPrivate" and isinstance(payload, dict):
            if isinstance(payload.get("new_user_data"), dict):
                self._sync_my_private(payload["new_user_data"])
            if len(self.my_tokens) >= 2:
                self.is_game_finished = True
                self.game_state = "GameFinished"
                self._pending_action = False
                return True
            draw_type = int(payload.get("draw_type", 3))
            # Only continue turn on start-of-turn draw (draw_type 1, 2, or 3), NEVER on end-of-turn pass draw (draw_type 4)
            if draw_type in (1, 2, 3) and not self.is_game_finished and self.current_turn == my_role:
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
            if atk_id == my_role:
                self.attacks_this_turn += 1
                if self.game_state in ("DeclareAttack", "AttackerArmy"):
                    self._pending_action = True
            elif tgt_id == my_role and self.game_state == "DefenderArmy":
                self._pending_action = True
            return True

        if cmd_id == "AttackArmy" and isinstance(payload, dict):
            tgt_id = int(payload.get("target_index", (self.active_attack or {}).get("defender_id", 0)))
            self.game_state = str(payload.get("game_state", "DefenderArmy"))
            if self.active_attack is not None:
                self.active_attack["attacker_army"] = int(payload.get("count", 0))
            if not self.is_game_finished and tgt_id == my_role:
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
            if isinstance(payload.get("tokens"), list):
                self.free_tokens = [str(t) for t in payload["tokens"]]
            if payload.get("is_game_finished", False):
                self.active_attack = None
                self.is_game_finished = True
                self.game_state = "GameFinished"
                self._pending_action = False
                return True
            self.game_state = str(payload.get("game_state", "SelectAction"))
            if payload.get("battle_continues", False) and self.game_state == "Attack":
                self.active_attack = {
                    "attacker_id": int(payload.get("attacker_id", self.current_turn)),
                    "defender_id": int(payload.get("defender_id", 0)),
                    "source_continent": str(payload.get("source_continent", "Asia")),
                    "target_continent": str(payload.get("target_continent", "Asia")),
                    "attacker_army": int(payload.get("attacker_army", 0)),
                    "defender_army": int(payload.get("defender_army", 0)),
                    "battle_started": True,
                }
            else:
                self.active_attack = None
            # Note: bot_controller.py and game_session.py automatically invoke _take_turn() on RollResult
            if cmd_id == "Attack" and self.current_turn == my_role:
                self._pending_action = True
            return True

        if cmd_id == "StrategyResult" and isinstance(payload, dict):
            if isinstance(payload.get("players_data"), list):
                self.players_data = payload["players_data"]
                for p in self.players_data:
                    if isinstance(p, dict) and int(p.get("index", 0)) == my_role:
                        if isinstance(p.get("continents"), dict):
                            for c in ALL_CONTINENTS:
                                self.my_continents[c] = int(p["continents"].get(c, 0))
                        if isinstance(p.get("tokens"), list):
                            self.my_tokens = [str(t) for t in p["tokens"]]
            if isinstance(payload.get("tokens"), list):
                self.free_tokens = [str(t) for t in payload["tokens"]]
            if payload.get("is_game_finished", False):
                self.active_attack = None
                self.is_game_finished = True
                self.game_state = "GameFinished"
                self._pending_action = False
                return True
            if payload.get("ignore_adjacency") and int(payload.get("gamer_id", 0)) == my_role:
                self.ignore_adjacency = True
            if payload.get("strategy") == "Canon" and int(payload.get("gamer_id", 0)) == my_role:
                self.canon_played_this_turn = True
            self.game_state = str(payload.get("game_state", "SelectAction"))
            if payload.get("attack_canceled"):
                self.active_attack = None
                return True
            if not self.is_game_finished and self.current_turn == my_role and self.game_state == "SelectAction":
                self._pending_action = True
            return True

        if cmd_id == "PassTurn" and isinstance(payload, dict):
            if isinstance(payload.get("new_data"), dict):
                self._update_player_global(payload["new_data"])
            self._pending_action = False
            return True

        if cmd_id in ("FinishGame", "GameFinished"):
            self.is_game_finished = True
            self.game_state = "GameFinished"
            self._pending_action = False
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

    def should_continue_turn(self) -> bool:
        return bool(self._pending_action) and not self.is_game_finished

    def should_act_on_reconnect(self) -> bool:
        return bool(self._pending_action) and not self.is_game_finished

    def _count_my_strategy(self, name: str) -> int:
        return sum(1 for s in self.my_strategies if s.lower() == name.lower())

    def _get_active_opponents(self) -> List[Dict[str, Any]]:
        my_role = self.my_player_num or 2
        opps = []
        for p in self.players_data:
            if not isinstance(p, dict):
                continue
            opp_id = int(p.get("index", 0))
            if opp_id != my_role and opp_id in self.active_player_indexes:
                opps.append(p)
        opps.sort(
            key=lambda p: (
                len(p.get("tokens", [])) if isinstance(p.get("tokens"), list) else 0,
                sum(int(v) for v in (p.get("continents") or {}).values()) if isinstance(p.get("continents"), dict) else 0,
                int(p.get("strategies_count", 0)),
            ),
            reverse=True,
        )
        return opps

    def get_legal_moves(self) -> List[Any]:
        if self.is_game_finished:
            return []
        my_role = self.my_player_num or 2

        # 1. Defender Response Phase (only before battle_started; no new Army cards after attack starts!)
        if self.game_state == "DefenderArmy" and self.active_attack and not self.active_attack.get("battle_started", False):
            def_id = int(self.active_attack.get("defender_id", 0))
            if def_id == my_role:
                tgt_c = str(self.active_attack.get("target_continent", "Asia"))
                def_cards = max(1, int(self.my_continents.get(tgt_c, 1)))
                base_def_dice = min(2, def_cards)
                max_extra = max(0, 4 - base_def_dice)
                army_cnt = self._count_my_strategy("Army")
                moves = [{"action": "defender_army", "count": c} for c in range(0, min(max_extra, army_cnt) + 1)]
                if self._count_my_strategy("Cancel") > 0:
                    moves.append({"action": "defender_cancel"})
                return moves
            return []

        if self.current_turn != my_role:
            return []

        # 2. Start-of-Turn Draw Phase: Choose draw_type 1 (2 Continents), 2 (2 Strategies), or 3 (1 Continent + 1 Strategy)
        if self.game_state in ("StartGame", "Draw"):
            return [
                {"action": "draw", "draw_type": 1},
                {"action": "draw", "draw_type": 2},
                {"action": "draw", "draw_type": 3},
            ]

        # 3. Attacker Army Commitment Phase (only before battle_started)
        if self.game_state in ("DeclareAttack", "AttackerArmy") and self.active_attack and not self.active_attack.get("battle_started", False):
            src_c = str(self.active_attack.get("source_continent", "Asia"))
            atk_cards = max(1, int(self.my_continents.get(src_c, 1)))
            base_atk_dice = min(3, atk_cards)
            max_extra = max(0, 5 - base_atk_dice)
            army_cnt = self._count_my_strategy("Army")
            return [{"action": "attacker_army", "count": c} for c in range(0, min(max_extra, army_cnt) + 1)]

        # 3b. Ongoing Multi-Round Attack Phase (no new Army cards allowed once attack has started!)
        if self.game_state == "Attack" and self.active_attack:
            return [
                {"action": "continue_attack"},
                {"action": "stop_attack"},
            ]

        # 4. SelectAction Phase: Strategy cards, Declare Attack, or Pass Turn
        if self.game_state in ("DrawResult", "SelectAction", "ActionResult"):
            moves = [{"action": "pass"}]
            opponents = self._get_active_opponents()

            # Compute legal Continent Attacks against active opponents (max 1 attack per turn)
            attack_moves = []
            if self.attacks_this_turn < 1:
                for src_c, my_cnt in self.my_continents.items():
                    if my_cnt <= 0:
                        continue
                    connected = ALL_CONTINENTS if self.ignore_adjacency else CONTINENT_ADJACENCY.get(src_c, [src_c])
                    for p in opponents:
                        opp_id = int(p.get("index", 0))
                        opp_conts = p.get("continents", {})
                        if not isinstance(opp_conts, dict):
                            continue
                        for tgt_c in connected:
                            if int(opp_conts.get(tgt_c, 0)) > 0:
                                attack_moves.append({
                                    "action": "declare_attack",
                                    "source_continent": src_c,
                                    "target_continent": tgt_c,
                                    "target_index": opp_id,
                                })

            # Available non-reactive Strategy cards in hand with strict target validation
            if self._count_my_strategy("Backup") > 0:
                moves.append({"action": "strategy", "strategy": "Backup"})
            if self._count_my_strategy("Expand") > 0 and not self.ignore_adjacency:
                moves.append({"action": "strategy", "strategy": "Expand"})
            if sum(self.my_continents.values()) == 0 and self._count_my_strategy("Army") > 0:
                moves.append({"action": "strategy", "strategy": "Army"})

            if self._count_my_strategy("Destroy") > 0:
                for p in opponents:
                    opp_id = int(p.get("index", 0))
                    opp_conts = p.get("continents", {}) if isinstance(p.get("continents"), dict) else {}
                    avail_c = [c for c, cnt in opp_conts.items() if int(cnt) > 0]
                    if avail_c:
                        avail_c.sort(
                            key=lambda c: (
                                1 if (c not in self.my_tokens and int(opp_conts[c]) >= DOMINATION_THRESHOLDS.get(c, 4) - 1) else 0,
                                int(opp_conts[c]) / max(1, DOMINATION_THRESHOLDS.get(c, 4)),
                            ),
                            reverse=True,
                        )
                        moves.append({
                            "action": "strategy",
                            "strategy": "Destroy",
                            "target_index": opp_id,
                            "target_continent": avail_c[0],
                        })
                        break

            for strat in ("Spy", "Bomb"):
                if self._count_my_strategy(strat) > 0:
                    for p in opponents:
                        opp_id = int(p.get("index", 0))
                        opp_conts = p.get("continents", {}) if isinstance(p.get("continents"), dict) else {}
                        has_c = sum(int(v) for v in opp_conts.values()) > 0
                        has_s = int(p.get("strategies_count", 0)) > 0
                        if has_c or has_s:
                            moves.append({
                                "action": "strategy",
                                "strategy": strat,
                                "target_index": opp_id,
                            })
                            break

            if self._count_my_strategy("Canon") > 0 and not self.canon_played_this_turn and len(attack_moves) > 0:
                moves.append({"action": "strategy", "strategy": "Canon"})

            moves.extend(attack_moves)
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
            close_to_dom = any(
                c not in self.my_tokens and self.my_continents.get(c, 0) >= DOMINATION_THRESHOLDS.get(c, 4) - 1
                for c in ALL_CONTINENTS
            )
            if dt == 1:
                if close_to_dom or my_total_c <= 4:
                    return 118.0
                return 68.0
            elif dt == 3:
                return 84.0
            else:
                return 72.0 if len(self.my_strategies) <= 1 and my_total_c >= 7 else 40.0

        if act == "defender_cancel":
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
            needed = max(0, 3 - my_c)
            if cnt == min(my_army_cnt, max(1, needed)):
                return 110.0
            return 70.0 - abs(cnt - needed) * 15.0

        if act == "continue_attack":
            src_c = (self.active_attack or {}).get("source_continent", "Asia")
            tgt_c = (self.active_attack or {}).get("target_continent", "Asia")
            tgt_idx = int((self.active_attack or {}).get("defender_id", 0))
            my_c = self.my_continents.get(src_c, 0) + int((self.active_attack or {}).get("attacker_army", 0))
            opp_c = 1
            for p in self.players_data:
                if isinstance(p, dict) and int(p.get("index", 0)) == tgt_idx:
                    opp_c = int(p.get("continents", {}).get(tgt_c, 1)) + int((self.active_attack or {}).get("defender_army", 0))
                    break
            if my_c >= opp_c or opp_c == 1:
                return 115.0
            return 45.0

        if act == "stop_attack":
            return 65.0

        if act == "strategy":
            strat = move.get("strategy")
            if strat == "Backup":
                return 135.0
            if strat == "Army":
                return 130.0
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
                    opp_tokens = p.get("tokens", []) if isinstance(p.get("tokens"), list) else []
                    break

            advantage = (my_c + min(2, my_army_cnt)) - opp_c
            score = 48.0 + advantage * 28.0 - (self.attacks_this_turn * 22.0)
            tgt_thresh = DOMINATION_THRESHOLDS.get(tgt_c, 4)
            if opp_c >= tgt_thresh - 1 and tgt_c not in opp_tokens:
                score += 60.0
            if opp_c == 1:
                score += 45.0
            if len(opp_tokens) >= 1:
                score += 25.0
            src_thresh = DOMINATION_THRESHOLDS.get(src_c, 4)
            if src_c not in self.my_tokens and my_c == src_thresh - 1 and opp_c >= 2:
                score -= 45.0
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
        if act == "continue_attack":
            return {"id": "Attack", "data": {}}
        if act == "stop_attack":
            return {"id": "CancelAttack", "data": {"stop": True}}
        if act == "strategy":
            payload: Dict[str, Any] = {"strategy": move.get("strategy")}
            if "target_index" in move and move["target_index"] is not None:
                payload["target_index"] = int(move["target_index"])
            if "target_continent" in move and move["target_continent"]:
                payload["target_continent"] = str(move["target_continent"])
            return {"id": "UseStrategy", "data": payload}
        return {"id": "PassTurn", "data": {}}

    def format_state(self) -> str:
        return (
            f"[Risk] Turn: P{self.current_turn} | State: {self.game_state} | "
            f"Tokens: {self.my_tokens} | Continents: {sum(self.my_continents.values())} | "
            f"Strategies: {len(self.my_strategies)}"
        )
