"""
Yinsh (یینش) Bot Game Logic Engine for Cafe Fekr.
Matches backend Entities/Games/Yinsh/__init__.py & YinshGameSession 100%.

Phases & Protocol:
- Phase 1 (is_setup_ring_phase == True):
  Each player places 5 rings on empty spots (0..84).
  Bot emits: {"id": "SubmitRing", "data": piece_id}
- Phase 2 (is_setup_ring_phase == False):
  Two-step turn:
  * Step 2A (last_selected_piece_id == -1):
    Select one of own rings (ring_user == my_player_num) that has at least 1 valid landing spot.
    Bot emits: {"id": "SelectPeace", "data": source_piece_id}
  * Step 2B (last_selected_piece_id != -1, triggered automatically via should_continue_turn() after PeaceSelected):
    Move the selected ring along one of the 6 hex directions to a valid landing spot.
    Bot emits: {"id": "MoveRing", "data": {"target_id": target_piece_id}}
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic

ALL_DIRECTIONS_LIST = [1, 2, 3, 4, 5, 6]
DOOZ_DIRECTIONS_LIST = [[1, 4], [2, 5], [3, 6]]

ALL_PIECE_DIRECTIONS: List[List[Tuple[int, int]]] = [
    [(2, 1), (3, 6), (4, 5)],
    [(2, 2), (3, 7), (4, 6), (5, 0)],
    [(2, 3), (3, 8), (4, 7), (5, 1)],
    [(3, 9), (4, 8), (5, 2)],
    [(2, 5), (3, 12), (4, 11)],
    [(1, 0), (2, 6), (3, 13), (4, 12), (5, 4)],
    [(1, 1), (2, 7), (3, 14), (4, 13), (5, 5), (6, 0)],
    [(1, 2), (2, 8), (3, 15), (4, 14), (5, 6), (6, 1)],
    [(1, 3), (2, 9), (3, 16), (4, 15), (5, 7), (6, 2)],
    [(2, 10), (3, 17), (4, 16), (5, 8), (6, 3)],
    [(3, 18), (4, 17), (5, 9)],
    [(1, 4), (2, 12), (3, 20), (4, 19)],
    [(1, 5), (2, 13), (3, 21), (4, 20), (5, 11), (6, 4)],
    [(1, 6), (2, 14), (3, 22), (4, 21), (5, 12), (6, 5)],
    [(1, 7), (2, 15), (3, 23), (4, 22), (5, 13), (6, 6)],
    [(1, 8), (2, 16), (3, 24), (4, 23), (5, 14), (6, 7)],
    [(1, 9), (2, 17), (3, 25), (4, 24), (5, 15), (6, 8)],
    [(1, 10), (2, 18), (3, 26), (4, 25), (5, 16), (6, 9)],
    [(3, 27), (4, 26), (5, 17), (6, 10)],
    [(1, 11), (2, 20), (3, 29), (4, 28)],
    [(1, 12), (2, 21), (3, 30), (4, 29), (5, 19), (6, 11)],
    [(1, 13), (2, 22), (3, 31), (4, 30), (5, 20), (6, 12)],
    [(1, 14), (2, 23), (3, 32), (4, 31), (5, 21), (6, 13)],
    [(1, 15), (2, 24), (3, 33), (4, 32), (5, 22), (6, 14)],
    [(1, 16), (2, 25), (3, 34), (4, 33), (5, 23), (6, 15)],
    [(1, 17), (2, 26), (3, 35), (4, 34), (5, 24), (6, 16)],
    [(1, 18), (2, 27), (3, 36), (4, 35), (5, 25), (6, 17)],
    [(3, 37), (4, 36), (5, 26), (6, 18)],
    [(1, 19), (2, 29), (3, 38)],
    [(1, 20), (2, 30), (3, 39), (4, 38), (5, 28), (6, 19)],
    [(1, 21), (2, 31), (3, 40), (4, 39), (5, 29), (6, 20)],
    [(1, 22), (2, 32), (3, 41), (4, 40), (5, 30), (6, 21)],
    [(1, 23), (2, 33), (3, 42), (4, 41), (5, 31), (6, 22)],
    [(1, 24), (2, 34), (3, 43), (4, 42), (5, 32), (6, 23)],
    [(1, 25), (2, 35), (3, 44), (4, 43), (5, 33), (6, 24)],
    [(1, 26), (2, 36), (3, 45), (4, 44), (5, 34), (6, 25)],
    [(1, 27), (2, 37), (3, 46), (4, 45), (5, 35), (6, 26)],
    [(4, 46), (5, 36), (6, 27)],
    [(1, 29), (2, 39), (3, 48), (4, 47), (6, 28)],
    [(1, 30), (2, 40), (3, 49), (4, 48), (5, 38), (6, 29)],
    [(1, 31), (2, 41), (3, 50), (4, 49), (5, 39), (6, 30)],
    [(1, 32), (2, 42), (3, 51), (4, 50), (5, 40), (6, 31)],
    [(1, 33), (2, 43), (3, 52), (4, 51), (5, 41), (6, 32)],
    [(1, 34), (2, 44), (3, 53), (4, 52), (5, 42), (6, 33)],
    [(1, 35), (2, 45), (3, 54), (4, 53), (5, 43), (6, 34)],
    [(1, 36), (2, 46), (3, 55), (4, 54), (5, 44), (6, 35)],
    [(1, 37), (3, 56), (4, 55), (5, 45), (6, 36)],
    [(1, 38), (2, 48), (3, 57)],
    [(1, 39), (2, 49), (3, 58), (4, 57), (5, 47), (6, 38)],
    [(1, 40), (2, 50), (3, 59), (4, 58), (5, 48), (6, 39)],
    [(1, 41), (2, 51), (3, 60), (4, 59), (5, 49), (6, 40)],
    [(1, 42), (2, 52), (3, 61), (4, 60), (5, 50), (6, 41)],
    [(1, 43), (2, 53), (3, 62), (4, 61), (5, 51), (6, 42)],
    [(1, 44), (2, 54), (3, 63), (4, 62), (5, 52), (6, 43)],
    [(1, 45), (2, 55), (3, 64), (4, 63), (5, 53), (6, 44)],
    [(1, 46), (2, 56), (3, 65), (4, 64), (5, 54), (6, 45)],
    [(4, 65), (5, 55), (6, 46)],
    [(1, 48), (2, 58), (3, 66), (6, 47)],
    [(1, 49), (2, 59), (3, 67), (4, 66), (5, 57), (6, 48)],
    [(1, 50), (2, 60), (3, 68), (4, 67), (5, 58), (6, 49)],
    [(1, 51), (2, 61), (3, 69), (4, 68), (5, 59), (6, 50)],
    [(1, 52), (2, 62), (3, 70), (4, 69), (5, 60), (6, 51)],
    [(1, 53), (2, 63), (3, 71), (4, 70), (5, 61), (6, 52)],
    [(1, 54), (2, 64), (3, 72), (4, 71), (5, 62), (6, 53)],
    [(1, 55), (2, 65), (3, 73), (4, 72), (5, 63), (6, 54)],
    [(1, 56), (4, 73), (5, 64), (6, 55)],
    [(1, 58), (2, 67), (3, 74), (6, 57)],
    [(1, 59), (2, 68), (3, 75), (4, 74), (5, 66), (6, 58)],
    [(1, 60), (2, 69), (3, 76), (4, 75), (5, 67), (6, 59)],
    [(1, 61), (2, 70), (3, 77), (4, 76), (5, 68), (6, 60)],
    [(1, 62), (2, 71), (3, 78), (4, 77), (5, 69), (6, 61)],
    [(1, 63), (2, 72), (3, 79), (4, 78), (5, 70), (6, 62)],
    [(1, 64), (2, 73), (3, 80), (4, 79), (5, 71), (6, 63)],
    [(1, 65), (4, 80), (5, 72), (6, 64)],
    [(1, 67), (2, 75), (6, 66)],
    [(1, 68), (2, 76), (3, 81), (5, 74), (6, 67)],
    [(1, 69), (2, 77), (3, 82), (4, 81), (5, 75), (6, 68)],
    [(1, 70), (2, 78), (3, 83), (4, 82), (5, 76), (6, 69)],
    [(1, 71), (2, 79), (3, 84), (4, 83), (5, 77), (6, 70)],
    [(1, 72), (2, 80), (4, 84), (5, 78), (6, 71)],
    [(1, 73), (5, 79), (6, 72)],
    [(1, 76), (2, 82), (6, 75)],
    [(1, 77), (2, 83), (5, 81), (6, 76)],
    [(1, 78), (2, 84), (5, 82), (6, 77)],
    [(1, 79), (5, 83), (6, 78)],
]

# Central interior spots preferred for ring placement
CENTER_SPOTS = {
    21, 22, 23, 24, 25,
    30, 31, 32, 33, 34, 35,
    39, 40, 41, 42, 43, 44, 45,
    49, 50, 51, 52, 53, 54,
    59, 60, 61, 62, 63,
}


class YinshGameLogic(BaseGameLogic):
    """Yinsh 3-level bot engine."""

    NUM_SPOTS = 85

    def __init__(self, level: int = 1):
        super().__init__(game_type="Yinsh", level=level)
        self.neighbors: List[Dict[int, int]] = [
            {d: nbr for d, nbr in ALL_PIECE_DIRECTIONS[i]} for i in range(self.NUM_SPOTS)
        ]
        self.ring_owners: List[Optional[int]] = [None] * self.NUM_SPOTS
        self.disk_owners: List[Optional[int]] = [None] * self.NUM_SPOTS
        self.is_setup_ring_phase: bool = True
        self.player1_rings: int = 5
        self.player2_rings: int = 5
        self.player1_score: int = 0
        self.player2_score: int = 0
        self.disk_count: int = 51
        self.last_selected_piece_id: int = -1
        self.current_turn: int = 1
        self.current_remover: int = 0
        self._planned_target_id: Optional[int] = None

    def reset(self):
        self.ring_owners = [None] * self.NUM_SPOTS
        self.disk_owners = [None] * self.NUM_SPOTS
        self.is_setup_ring_phase = True
        self.player1_rings = 5
        self.player2_rings = 5
        self.player1_score = 0
        self.player2_score = 0
        self.disk_count = 51
        self.last_selected_piece_id = -1
        self.current_turn = 1
        self.current_remover = 0
        self._planned_target_id = None

    def _sync_board_array(self, board_list: List[Any]):
        if not isinstance(board_list, list) or len(board_list) < self.NUM_SPOTS:
            return
        for i in range(self.NUM_SPOTS):
            cell = board_list[i]
            if isinstance(cell, dict):
                self.ring_owners[i] = cell.get("ring_user", None)
                self.disk_owners[i] = cell.get("disk_user", None)

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id in ("GameData", "StartGame"):
            if isinstance(payload, dict) and "board" in payload:
                self._sync_board_array(payload["board"])
            return True

        if cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict):
                    self.is_setup_ring_phase = bool(g_data.get("is_setup_ring_phase", False))
                    self.player1_score = int(g_data.get("player1_score", 0))
                    self.player2_score = int(g_data.get("player2_score", 0))
                    self.player1_rings = int(g_data.get("player1_rings", 0))
                    self.player2_rings = int(g_data.get("player2_rings", 0))
                    self.disk_count = int(g_data.get("disk_count", 51))
                    self.last_selected_piece_id = int(g_data.get("last_selected_piece_id", -1))
                    self.current_turn = int(g_data.get("current_turn", 1))
                    self.current_remover = int(g_data.get("current_remover", 0))
                    if "board" in g_data:
                        self._sync_board_array(g_data["board"])
            return True

        if cmd_id == "CurrentTurn":
            if isinstance(payload, dict):
                self.current_turn = int(payload.get("turn", 1))
                if "is_setup_ring_phase" in payload:
                    self.is_setup_ring_phase = bool(payload["is_setup_ring_phase"])
            else:
                self.current_turn = int(payload)
            self.current_remover = 0
            self.last_selected_piece_id = -1
            self._planned_target_id = None
            return True

        if cmd_id == "RingSubmited":
            if isinstance(payload, dict):
                gid = int(payload.get("gamer_id", 1))
                pid = int(payload.get("piece_id", -1))
                if 0 <= pid < self.NUM_SPOTS:
                    self.ring_owners[pid] = gid
                if gid == 1:
                    self.player1_rings = max(0, self.player1_rings - 1)
                else:
                    self.player2_rings = max(0, self.player2_rings - 1)
                if self.player1_rings == 0 and self.player2_rings == 0:
                    self.is_setup_ring_phase = False
            return True

        if cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                gid = int(payload.get("gamer_id", 1))
                pid = int(payload.get("piece_id", -1))
                if 0 <= pid < self.NUM_SPOTS:
                    self.disk_owners[pid] = gid
                    self.disk_count = max(0, self.disk_count - 1)
                    self.last_selected_piece_id = pid
            return True

        if cmd_id == "RingMoved":
            if isinstance(payload, dict):
                gid = int(payload.get("gamer_id", 1))
                src = int(payload.get("source_id", self.last_selected_piece_id))
                dst = int(payload.get("target_id", -1))
                rots = payload.get("rotations_list", [])
                if 0 <= src < self.NUM_SPOTS:
                    self.ring_owners[src] = None
                if 0 <= dst < self.NUM_SPOTS:
                    self.ring_owners[dst] = gid
                if isinstance(rots, list):
                    for r_pid in rots:
                        idx = int(r_pid)
                        if 0 <= idx < self.NUM_SPOTS and self.disk_owners[idx] is not None:
                            self.disk_owners[idx] = 2 if self.disk_owners[idx] == 1 else 1
                self.last_selected_piece_id = -1
                self._planned_target_id = None
            return True

        if cmd_id == "RemovePeace":
            if isinstance(payload, dict):
                pid = int(payload.get("piece_id", -1))
                if 0 <= pid < self.NUM_SPOTS:
                    self.disk_owners[pid] = None
                    self.disk_count = min(51, self.disk_count + 1)
            self.last_selected_piece_id = -1
            self._planned_target_id = None
            return True

        if cmd_id == "SelectRemovePeace":
            rem = payload.get("remover_id", payload) if isinstance(payload, dict) else payload
            self.current_remover = int(rem) if rem is not None else 0
            self.last_selected_piece_id = -1
            self._planned_target_id = None
            return True

        if cmd_id == "WinHappened":
            if isinstance(payload, dict):
                win_data = payload.get("win_data", [])
                rem_rings = payload.get("removed_rings", [])
                fallback_gid = int(payload.get("gamer_id", 1))
                if isinstance(win_data, list):
                    for item in win_data:
                        if isinstance(item, dict):
                            fallback_gid = int(item.get("gamer_id", fallback_gid))
                            for pid in item.get("data", []):
                                idx = int(pid)
                                if 0 <= idx < self.NUM_SPOTS:
                                    self.disk_owners[idx] = None
                                    self.disk_count = min(51, self.disk_count + 1)
                if isinstance(rem_rings, list):
                    for r_pid in rem_rings:
                        if r_pid is not None and 0 <= int(r_pid) < self.NUM_SPOTS:
                            r_idx = int(r_pid)
                            r_owner = self.ring_owners[r_idx] or fallback_gid
                            self.ring_owners[r_idx] = None
                            if r_owner == 1:
                                self.player1_score += 1
                            else:
                                self.player2_score += 1
                if "current_remover" in payload:
                    self.current_remover = int(payload["current_remover"])
            return True

        return False

    def should_continue_turn(self) -> bool:
        """Returns True right after PeaceSelected on the bot's own turn so it immediately sends MoveRing."""
        my_id = self.my_player_num or 2
        return (
            not self.is_setup_ring_phase
            and self.current_turn == my_id
            and self.last_selected_piece_id != -1
        )

    def should_act_on_reconnect(self) -> bool:
        my_id = self.my_player_num or 2
        return self.current_turn == my_id

    # --- Direction & Move Helpers ---

    def get_valid_targets_for_ring(
        self,
        ring_id: int,
        ring_owners: Optional[List[Optional[int]]] = None,
        disk_owners: Optional[List[Optional[int]]] = None,
    ) -> List[int]:
        r_own = ring_owners if ring_owners is not None else self.ring_owners
        d_own = disk_owners if disk_owners is not None else self.disk_owners
        targets: List[int] = []
        if not (0 <= ring_id < self.NUM_SPOTS):
            return targets

        for d in ALL_DIRECTIONS_LIST:
            cur = ring_id
            jumped_disk = False
            while d in self.neighbors[cur]:
                nxt = self.neighbors[cur][d]
                if r_own[nxt] is not None:
                    break
                if d_own[nxt] is not None:
                    jumped_disk = True
                    cur = nxt
                else:
                    targets.append(nxt)
                    if jumped_disk:
                        break
                    cur = nxt
        return targets

    def get_flipped_disks(
        self,
        source_id: int,
        target_id: int,
        ring_owners: Optional[List[Optional[int]]] = None,
        disk_owners: Optional[List[Optional[int]]] = None,
    ) -> List[int]:
        r_own = ring_owners if ring_owners is not None else self.ring_owners
        d_own = disk_owners if disk_owners is not None else self.disk_owners
        for d in ALL_DIRECTIONS_LIST:
            cur = source_id
            flipped: List[int] = []
            while d in self.neighbors[cur]:
                nxt = self.neighbors[cur][d]
                if nxt == target_id:
                    return flipped
                if r_own[nxt] is not None:
                    break
                if d_own[nxt] is not None:
                    flipped.append(nxt)
                cur = nxt
        return []

    def get_legal_moves(self, gamer_id: Optional[int] = None) -> List[Any]:
        player = gamer_id if gamer_id is not None else (self.my_player_num or 2)
        if self.current_remover == player:
            return [i for i in range(self.NUM_SPOTS) if self.ring_owners[i] == player]
        if self.is_setup_ring_phase:
            return [
                i
                for i in range(self.NUM_SPOTS)
                if self.ring_owners[i] is None and self.disk_owners[i] is None
            ]

        if self.last_selected_piece_id == -1:
            selectable_rings: List[int] = []
            for i in range(self.NUM_SPOTS):
                if self.ring_owners[i] == player:
                    if self.get_valid_targets_for_ring(i):
                        selectable_rings.append(i)
            return selectable_rings
        else:
            return self.get_valid_targets_for_ring(self.last_selected_piece_id)

    def _longest_line_for_player(self, disk_owners: List[Optional[int]], player: int) -> Tuple[int, int]:
        """Returns (max_run_length, total_runs_of_3_or_more) for player."""
        max_len = 0
        runs_3plus = 0
        for pid in range(self.NUM_SPOTS):
            if disk_owners[pid] != player:
                continue
            for pair in DOOZ_DIRECTIONS_LIST:
                d_pos = pair[0]
                d_neg = pair[1]
                # Only start counting at the beginning of a run
                prev_id = self.neighbors[pid].get(d_neg)
                if prev_id is not None and disk_owners[prev_id] == player:
                    continue
                run = 1
                cur = pid
                while d_pos in self.neighbors[cur]:
                    nxt = self.neighbors[cur][d_pos]
                    if disk_owners[nxt] == player:
                        run += 1
                        cur = nxt
                    else:
                        break
                if run > max_len:
                    max_len = run
                if run >= 3:
                    runs_3plus += run
        return max_len, runs_3plus

    def _evaluate_move_pair(self, player: int, source_id: int, target_id: int) -> float:
        opp = 1 if player == 2 else 2
        sim_disks = list(self.disk_owners)
        sim_disks[source_id] = player
        flipped = self.get_flipped_disks(source_id, target_id)
        my_flips = 0
        opp_flips = 0
        for fid in flipped:
            if sim_disks[fid] == opp:
                sim_disks[fid] = player
                my_flips += 1
            elif sim_disks[fid] == player:
                sim_disks[fid] = opp
                opp_flips += 1

        my_max, my_3plus = self._longest_line_for_player(sim_disks, player)
        opp_max, opp_3plus = self._longest_line_for_player(sim_disks, opp)

        score = 0.0
        if my_max >= 5:
            score += 1000.0
        if opp_max >= 5:
            score -= 900.0
        score += my_max * 18.0 + my_3plus * 6.0
        score -= opp_max * 20.0 + opp_3plus * 7.0
        score += (my_flips - opp_flips) * 8.5
        if target_id in CENTER_SPOTS:
            score += 4.0
        return score

    def is_critical_turn(self) -> bool:
        if self.is_setup_ring_phase:
            return False
        return self.player1_score >= 2 or self.player2_score >= 2

    def compute_next_move(self) -> Any:
        my_id = self.my_player_num or 2
        legal = self.get_legal_moves(my_id)
        if not legal:
            return None

        # Ring Removal Selection Phase (after forming 5-in-a-row)
        if self.current_remover == my_id:
            if self.level == 1:
                return ("SelectRemovePeace", random.choice(legal))
            # Prefer removing our least mobile / outer-edge ring so our strongest rings remain on the board
            scored_rings = []
            for r_id in legal:
                mobility = len(self.get_valid_targets_for_ring(r_id))
                center_bonus = 2 if r_id in CENTER_SPOTS else 0
                scored_rings.append((mobility + center_bonus, r_id))
            scored_rings.sort(key=lambda x: x[0])
            return ("SelectRemovePeace", scored_rings[0][1])

        # Phase 1: Setup Ring Placement
        if self.is_setup_ring_phase:
            center_legal = [pid for pid in legal if pid in CENTER_SPOTS]
            if self.level == 1:
                pool = center_legal if (center_legal and random.random() < 0.65) else legal
                return ("SubmitRing", random.choice(pool))
            else:
                pool = center_legal if center_legal else legal
                return ("SubmitRing", random.choice(pool))

        # Phase 2A: Select one of our rings (and plan its destination)
        if self.last_selected_piece_id == -1:
            all_pairs: List[Tuple[float, int, int]] = []
            for r_id in legal:
                targets = self.get_valid_targets_for_ring(r_id)
                for t_id in targets:
                    sc = self._evaluate_move_pair(my_id, r_id, t_id)
                    all_pairs.append((sc + random.uniform(-1.5, 1.5), r_id, t_id))

            if not all_pairs:
                chosen_ring = random.choice(legal)
                self._planned_target_id = None
                return ("SelectPeace", chosen_ring)

            all_pairs.sort(key=lambda x: x[0], reverse=True)
            if self.level == 1:
                # Level 1 (Casual/Beginner): immediately take a 5-in-a-row win if obvious, otherwise pick from top 45% or random
                if all_pairs[0][0] >= 900.0 and random.random() < 0.75:
                    _, best_r, best_t = all_pairs[0]
                else:
                    top_k = max(1, len(all_pairs) // 2)
                    _, best_r, best_t = random.choice(all_pairs[:top_k])
            elif self.level == 2:
                top_k = min(3, len(all_pairs))
                _, best_r, best_t = random.choice(all_pairs[:top_k])
            else:
                _, best_r, best_t = all_pairs[0]

            self._planned_target_id = best_t
            return ("SelectPeace", best_r)

        # Phase 2B: Move the selected ring to target_id
        if self._planned_target_id is not None and self._planned_target_id in legal:
            target = self._planned_target_id
            self._planned_target_id = None
            return ("MoveRing", target)

        scored_targets: List[Tuple[float, int]] = []
        for t_id in legal:
            sc = self._evaluate_move_pair(my_id, self.last_selected_piece_id, t_id)
            scored_targets.append((sc + random.uniform(-1.0, 1.0), t_id))
        scored_targets.sort(key=lambda x: x[0], reverse=True)
        return ("MoveRing", scored_targets[0][1])

    def build_move_command(self, move: Any) -> dict:
        if isinstance(move, tuple) and len(move) == 2:
            cmd_name, val = move
            if cmd_name == "SubmitRing":
                return {"id": "SubmitRing", "data": int(val)}
            if cmd_name == "SelectPeace":
                return {"id": "SelectPeace", "data": int(val)}
            if cmd_name == "MoveRing":
                return {"id": "MoveRing", "data": {"target_id": int(val)}}
            if cmd_name == "SelectRemovePeace":
                return {"id": "SelectRemovePeace", "data": int(val)}
        if self.current_remover == (self.my_player_num or 2):
            return {"id": "SelectRemovePeace", "data": int(move)}
        if self.is_setup_ring_phase:
            return {"id": "SubmitRing", "data": int(move)}
        if self.last_selected_piece_id == -1:
            return {"id": "SelectPeace", "data": int(move)}
        return {"id": "MoveRing", "data": {"target_id": int(move)}}

    def format_state(self) -> str:
        phase_str = "SetupRings" if self.is_setup_ring_phase else f"Play(Selected={self.last_selected_piece_id})"
        return (
            f"Yinsh [{phase_str}] | Scores P1:{self.player1_score} P2:{self.player2_score} "
            f"| Disks left:{self.disk_count}"
        )
