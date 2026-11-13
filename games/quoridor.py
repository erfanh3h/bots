"""
Quoridor (کوریدور) Bot Game Logic Engine for Cafe Fekr.
Matches backend Entities/Games/Quoridor/__init__.py & QuoridorGameSession 100%.

Protocol:
- 9x9 board:
  * Player 1 starts at [8, 4], goal row = 0
  * Player 2 starts at [0, 4], goal row = 8
- 10 walls per player on 8x8 interior intersections (0..7, 0..7):
  * Orientation "H" at (wr, wc) blocks (wr, wc)<->(wr+1, wc) and (wr, wc+1)<->(wr+1, wc+1)
  * Orientation "V" at (wr, wc) blocks (wr, wc)<->(wr, wc+1) and (wr+1, wc)<->(wr+1, wc+1)
- Bot emits:
  * {"id": "SelectPeace", "data": {"action": "move", "row": r, "col": c}}
  * {"id": "SelectPeace", "data": {"action": "wall", "row": wr, "col": wc, "orientation": "H"|"V"}}
"""

from collections import deque
import random
from typing import Any, Dict, List, Optional, Set, Tuple
from .base_game import BaseGameLogic


class QuoridorGameLogic(BaseGameLogic):
    """Quoridor 3-level strategic bot engine."""

    BOARD_SIZE = 9
    WALL_GRID_SIZE = 8
    INITIAL_WALLS = 10

    def __init__(self, level: int = 1):
        super().__init__(game_type="Quoridor", level=level)
        self.game_type_aliases = ["quoridor", "کوریدور", "دیوارها"]
        self.pawns: Dict[int, List[int]] = {1: [8, 4], 2: [0, 4]}
        self.walls_left: Dict[int, int] = {1: self.INITIAL_WALLS, 2: self.INITIAL_WALLS}
        self.h_walls: Set[Tuple[int, int]] = set()
        self.v_walls: Set[Tuple[int, int]] = set()
        self.current_turn: int = 1
        self.reset()

    def reset(self):
        self.pawns = {1: [8, 4], 2: [0, 4]}
        self.walls_left = {1: self.INITIAL_WALLS, 2: self.INITIAL_WALLS}
        self.h_walls = set()
        self.v_walls = set()
        self.current_turn = 1

    def _sync_from_game_data(self, g_data: Dict[str, Any]):
        if not isinstance(g_data, dict):
            return
        raw_pawns = g_data.get("pawns")
        if isinstance(raw_pawns, list) and len(raw_pawns) >= 2:
            if isinstance(raw_pawns[0], (list, tuple)) and len(raw_pawns[0]) >= 2:
                self.pawns[1] = [int(raw_pawns[0][0]), int(raw_pawns[0][1])]
            if isinstance(raw_pawns[1], (list, tuple)) and len(raw_pawns[1]) >= 2:
                self.pawns[2] = [int(raw_pawns[1][0]), int(raw_pawns[1][1])]
        elif isinstance(raw_pawns, dict):
            for k in (1, "1"):
                if k in raw_pawns and len(raw_pawns[k]) >= 2:
                    self.pawns[1] = [int(raw_pawns[k][0]), int(raw_pawns[k][1])]
            for k in (2, "2"):
                if k in raw_pawns and len(raw_pawns[k]) >= 2:
                    self.pawns[2] = [int(raw_pawns[k][0]), int(raw_pawns[k][1])]

        raw_walls = g_data.get("walls_left")
        if isinstance(raw_walls, list) and len(raw_walls) >= 2:
            self.walls_left[1] = int(raw_walls[0])
            self.walls_left[2] = int(raw_walls[1])
        elif isinstance(raw_walls, dict):
            self.walls_left[1] = int(raw_walls.get(1, raw_walls.get("1", self.walls_left[1])))
            self.walls_left[2] = int(raw_walls.get(2, raw_walls.get("2", self.walls_left[2])))

        if "h_walls" in g_data and isinstance(g_data["h_walls"], list):
            self.h_walls = {(int(w[0]), int(w[1])) for w in g_data["h_walls"] if isinstance(w, (list, tuple)) and len(w) >= 2}
        if "v_walls" in g_data and isinstance(g_data["v_walls"], list):
            self.v_walls = {(int(w[0]), int(w[1])) for w in g_data["v_walls"] if isinstance(w, (list, tuple)) and len(w) >= 2}
        if "current_turn" in g_data:
            self.current_turn = int(g_data["current_turn"])

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        if cmd_id == "GameData":
            self.reset()
            if isinstance(payload, dict):
                g_data = payload.get("game_data", payload)
                self._sync_from_game_data(g_data)
            return True

        if cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", {})
                self._sync_from_game_data(g_data)
            return True

        if cmd_id == "CurrentTurn":
            if isinstance(payload, dict):
                self.current_turn = int(payload.get("turn", payload.get("current_turn", 1)))
            elif payload is not None:
                self.current_turn = int(payload)
            return True

        if cmd_id == "PeaceSelected":
            if isinstance(payload, dict):
                if "pawns" in payload or "h_walls" in payload or "v_walls" in payload:
                    self._sync_from_game_data(payload)
                else:
                    gid = int(payload.get("gamer_id", payload.get("user", 0)))
                    act = str(payload.get("action", "")).lower()
                    if act == "move" and gid in (1, 2):
                        self.pawns[gid] = [int(payload.get("row", 0)), int(payload.get("col", 0))]
                    elif act == "wall":
                        wr = int(payload.get("row", 0))
                        wc = int(payload.get("col", 0))
                        ori = str(payload.get("orientation", "")).upper()
                        if gid in (1, 2) and self.walls_left[gid] > 0:
                            self.walls_left[gid] -= 1
                        if ori == "H":
                            self.h_walls.add((wr, wc))
                        elif ori == "V":
                            self.v_walls.add((wr, wc))
            return True

        return False

    def _is_blocked(self, r1: int, c1: int, r2: int, c2: int, h_set: Set[Tuple[int, int]], v_set: Set[Tuple[int, int]]) -> bool:
        if not (0 <= r2 < self.BOARD_SIZE and 0 <= c2 < self.BOARD_SIZE):
            return True
        dr = r2 - r1
        dc = c2 - c1
        if abs(dr) + abs(dc) != 1:
            return True
        if dr == -1:
            wr = r1 - 1
            return (wr, c1) in h_set or (wr, c1 - 1) in h_set
        if dr == 1:
            wr = r1
            return (wr, c1) in h_set or (wr, c1 - 1) in h_set
        if dc == -1:
            wc = c1 - 1
            return (r1, wc) in v_set or (r1 - 1, wc) in v_set
        if dc == 1:
            wc = c1
            return (r1, wc) in v_set or (r1 - 1, wc) in v_set
        return True

    def get_legal_pawn_moves(
        self,
        gamer_id: int,
        pawns: Optional[Dict[int, List[int]]] = None,
        h_set: Optional[Set[Tuple[int, int]]] = None,
        v_set: Optional[Set[Tuple[int, int]]] = None,
    ) -> List[List[int]]:
        if pawns is None:
            pawns = self.pawns
        if h_set is None:
            h_set = self.h_walls
        if v_set is None:
            v_set = self.v_walls
        r, c = pawns[gamer_id]
        opp_id = 2 if gamer_id == 1 else 1
        orow, ocol = pawns[opp_id]
        legal = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if self._is_blocked(r, c, nr, nc, h_set, v_set):
                continue
            if nr == orow and nc == ocol:
                jr, jc = nr + dr, nc + dc
                if not self._is_blocked(nr, nc, jr, jc, h_set, v_set):
                    legal.append([jr, jc])
                else:
                    if dr != 0:
                        for sc in (-1, 1):
                            if not self._is_blocked(nr, nc, nr, nc + sc, h_set, v_set):
                                legal.append([nr, nc + sc])
                    else:
                        for sr in (-1, 1):
                            if not self._is_blocked(nr, nc, nr + sr, nc, h_set, v_set):
                                legal.append([nr + sr, nc])
            else:
                legal.append([nr, nc])
        return legal

    def _bfs_shortest_path(
        self,
        start_rc: List[int],
        goal_row: int,
        h_set: Set[Tuple[int, int]],
        v_set: Set[Tuple[int, int]],
    ) -> Tuple[int, List[Tuple[int, int]]]:
        """Returns (shortest_steps, path_cells_from_start_to_goal) ignoring pawn collision, or (999, [])."""
        sr, sc = start_rc[0], start_rc[1]
        if sr == goal_row:
            return (0, [(sr, sc)])
        visited = {(sr, sc)}
        parent: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {(sr, sc): None}
        q = deque([(sr, sc, 0)])
        while q:
            r, c, d = q.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if (nr, nc) in visited:
                    continue
                if self._is_blocked(r, c, nr, nc, h_set, v_set):
                    continue
                visited.add((nr, nc))
                parent[(nr, nc)] = (r, c)
                if nr == goal_row:
                    path = []
                    cur: Optional[Tuple[int, int]] = (nr, nc)
                    while cur is not None:
                        path.append(cur)
                        cur = parent[cur]
                    path.reverse()
                    return (d + 1, path)
                q.append((nr, nc, d + 1))
        return (999, [])

    def can_place_wall(self, gamer_id: int, wr: int, wc: int, orientation: str) -> bool:
        if self.walls_left.get(gamer_id, 0) <= 0:
            return False
        if not (0 <= wr < self.WALL_GRID_SIZE and 0 <= wc < self.WALL_GRID_SIZE):
            return False
        ori = orientation.upper()
        if (wr, wc) in self.h_walls or (wr, wc) in self.v_walls:
            return False
        if ori == "H":
            if (wr, wc - 1) in self.h_walls or (wr, wc + 1) in self.h_walls:
                return False
            new_h = self.h_walls | {(wr, wc)}
            new_v = self.v_walls
        elif ori == "V":
            if (wr - 1, wc) in self.v_walls or (wr + 1, wc) in self.v_walls:
                return False
            new_h = self.h_walls
            new_v = self.v_walls | {(wr, wc)}
        else:
            return False

        d1, _ = self._bfs_shortest_path(self.pawns[1], 0, new_h, new_v)
        if d1 >= 999:
            return False
        d2, _ = self._bfs_shortest_path(self.pawns[2], self.BOARD_SIZE - 1, new_h, new_v)
        if d2 >= 999:
            return False
        return True

    def _goal_row(self, gamer_id: int) -> int:
        return 0 if gamer_id == 1 else (self.BOARD_SIZE - 1)

    def _candidate_walls_around_path(self, path: List[Tuple[int, int]], opp_rc: List[int]) -> List[Tuple[int, int, str]]:
        candidates: Set[Tuple[int, int, str]] = set()
        pts = list(path[:5]) + [(opp_rc[0], opp_rc[1])]
        for r, c in pts:
            for wr in range(max(0, r - 1), min(self.WALL_GRID_SIZE, r + 2)):
                for wc in range(max(0, c - 1), min(self.WALL_GRID_SIZE, c + 2)):
                    candidates.add((wr, wc, "H"))
                    candidates.add((wr, wc, "V"))
        return list(candidates)

    def _choose_best_pawn_move(self, my_id: int) -> Optional[List[int]]:
        legal = self.get_legal_pawn_moves(my_id)
        if not legal:
            return None
        my_goal = self._goal_row(my_id)
        best_dist = 999
        best_moves: List[List[int]] = []
        for mr, mc in legal:
            if mr == my_goal:
                return [mr, mc]
            d, _ = self._bfs_shortest_path([mr, mc], my_goal, self.h_walls, self.v_walls)
            if d < best_dist:
                best_dist = d
                best_moves = [[mr, mc]]
            elif d == best_dist:
                best_moves.append([mr, mc])
        best_moves.sort(key=lambda m: abs(m[1] - 4))
        return best_moves[0] if self.level >= 2 else random.choice(best_moves)

    def is_critical_turn(self) -> bool:
        my_id = self.my_player_num or self.current_turn or 2
        opp_id = 2 if my_id == 1 else 1
        my_dist, _ = self._bfs_shortest_path(self.pawns[my_id], self._goal_row(my_id), self.h_walls, self.v_walls)
        opp_dist, _ = self._bfs_shortest_path(self.pawns[opp_id], self._goal_row(opp_id), self.h_walls, self.v_walls)
        return my_dist <= 2 or opp_dist <= 2

    def get_legal_moves(self) -> List[Dict[str, Any]]:
        my_id = self.my_player_num or self.current_turn or 2
        moves: List[Dict[str, Any]] = [
            {"action": "move", "row": int(mr), "col": int(mc)}
            for mr, mc in self.get_legal_pawn_moves(my_id)
        ]
        if self.walls_left.get(my_id, 0) > 0:
            for wr in range(self.WALL_GRID_SIZE):
                for wc in range(self.WALL_GRID_SIZE):
                    for ori in ("H", "V"):
                        if self.can_place_wall(my_id, wr, wc, ori):
                            moves.append({"action": "wall", "row": wr, "col": wc, "orientation": ori})
        return moves

    def compute_next_move(
        self,
        legal_moves: Optional[List[Any]] = None,
        is_continuation: bool = False,
    ) -> Dict[str, Any]:
        my_id = self.my_player_num or self.current_turn or 2
        opp_id = 2 if my_id == 1 else 1
        my_goal = self._goal_row(my_id)
        opp_goal = self._goal_row(opp_id)

        legal_pawn_moves = self.get_legal_pawn_moves(my_id)
        for mr, mc in legal_pawn_moves:
            if mr == my_goal:
                return {"action": "move", "row": int(mr), "col": int(mc)}

        my_dist, _ = self._bfs_shortest_path(self.pawns[my_id], my_goal, self.h_walls, self.v_walls)
        opp_dist, opp_path = self._bfs_shortest_path(self.pawns[opp_id], opp_goal, self.h_walls, self.v_walls)

        best_pawn = self._choose_best_pawn_move(my_id)

        if self.level <= 1:
            if self.walls_left.get(my_id, 0) > 0 and opp_dist <= 5 and random.random() < 0.22:
                cands = self._candidate_walls_around_path(opp_path, self.pawns[opp_id])
                random.shuffle(cands)
                for wr, wc, ori in cands[:20]:
                    if self.can_place_wall(my_id, wr, wc, ori):
                        return {"action": "wall", "row": int(wr), "col": int(wc), "orientation": ori}
            if best_pawn is not None:
                if len(legal_pawn_moves) > 1 and random.random() < 0.15:
                    best_pawn = random.choice(legal_pawn_moves)
                return {"action": "move", "row": int(best_pawn[0]), "col": int(best_pawn[1])}

        best_wall: Optional[Tuple[int, int, str]] = None
        best_wall_score = -999.0

        if self.walls_left.get(my_id, 0) > 0 and (opp_dist <= my_dist + (1 if self.level >= 3 else 0) or opp_dist <= 3):
            cands = self._candidate_walls_around_path(opp_path, self.pawns[opp_id])
            for wr, wc, ori in cands:
                if not self.can_place_wall(my_id, wr, wc, ori):
                    continue
                if ori == "H":
                    new_h = self.h_walls | {(wr, wc)}
                    new_v = self.v_walls
                else:
                    new_h = self.h_walls
                    new_v = self.v_walls | {(wr, wc)}
                new_opp_d, _ = self._bfs_shortest_path(self.pawns[opp_id], opp_goal, new_h, new_v)
                new_my_d, _ = self._bfs_shortest_path(self.pawns[my_id], my_goal, new_h, new_v)
                if new_opp_d >= 999 or new_my_d >= 999:
                    continue
                gain = float(new_opp_d - opp_dist) - float(new_my_d - my_dist)
                score = gain - (0.25 if new_my_d > my_dist else 0.0)
                if score > best_wall_score:
                    best_wall_score = score
                    best_wall = (wr, wc, ori)

        min_wall_gain = 1.5 if opp_dist > 2 else 0.75
        if best_wall is not None and best_wall_score >= min_wall_gain:
            if not (my_dist <= 2 and opp_dist > 2):
                wr, wc, ori = best_wall
                return {"action": "wall", "row": int(wr), "col": int(wc), "orientation": ori}

        if best_pawn is not None:
            return {"action": "move", "row": int(best_pawn[0]), "col": int(best_pawn[1])}

        if self.walls_left.get(my_id, 0) > 0:
            for wr in range(self.WALL_GRID_SIZE):
                for wc in range(self.WALL_GRID_SIZE):
                    for ori in ("H", "V"):
                        if self.can_place_wall(my_id, wr, wc, ori):
                            return {"action": "wall", "row": int(wr), "col": int(wc), "orientation": ori}

        return {"action": "move", "row": int(self.pawns[my_id][0]), "col": int(self.pawns[my_id][1])}

    def build_move_command(self, move: Any) -> Dict[str, Any]:
        if isinstance(move, dict):
            if "id" in move and "data" in move:
                return move
            return {"id": "SelectPeace", "data": move}
        if isinstance(move, (list, tuple)) and len(move) == 2:
            return {"id": "SelectPeace", "data": {"action": "move", "row": int(move[0]), "col": int(move[1])}}
        if isinstance(move, (list, tuple)) and len(move) == 3:
            return {
                "id": "SelectPeace",
                "data": {"action": "wall", "row": int(move[0]), "col": int(move[1]), "orientation": str(move[2]).upper()},
            }
        return {"id": "SelectPeace", "data": move}

    def choose_move(self, is_continuation: bool = False) -> Dict[str, Any]:
        return self.build_move_command(self.compute_next_move(is_continuation=is_continuation))

    def format_state(self) -> str:
        return (
            f"Quoridor [P1:{self.pawns[1]} W:{self.walls_left[1]} | "
            f"P2:{self.pawns[2]} W:{self.walls_left[2]} | Turn:P{self.current_turn}]"
        )
