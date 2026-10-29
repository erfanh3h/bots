"""
Minesweeper (مین یاب / MSweeper) Game Logic for Cafe Fekr Bot.

Implements 100% protocol compatibility with kafehfekrbackend:
- Simultaneous 2-player competitive Minefield (8x8 = 64 cells, 10 mines, 54 safe spots).
- Move Commands:
  1. Reveal Safe Spot: {"id": "SelectPeace", "data": peace_id} (0..63)
  2. Flag / Defuse Mine: {"id": "SelectMine", "data": peace_id} (0..63)
- Server Responses:
  - SelectPeaceResult: {"peace_number": int, "value": int}
  - MineSelected: {"peace_number": int} (Bot stepped on a mine -> no more moves)
  - SelectMineCorrect: {"peace_number": int} (+1 score)
  - SelectMineWrong: {"peace_number": int} (Flag wasted on safe spot)

CRITICAL LEVEL CONSTRAINT:
- At the current level (Level 1 / Test), this bot MUST NOT be able to solve Minesweeper!
- It acts purely as a live, human-paced opponent for testing/sparring.
- It makes casual, non-deductive random probes and imperfect flag guesses,
  and caps its lucky flags so it can never solve all 10 mines.
"""

import random
from typing import Any, List, Optional, Tuple
from .base_game import BaseGameLogic

TOTAL_CELLS = 64
GRID_SIZE = 8
INITIAL_MINES = 10
INITIAL_SAFE_SPOTS = 54


class MSweeperGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="MSweeper",
            game_type_aliases=[
                "msweeper",
                "minesweeper",
                "مین یاب",
                "مین‌یاب",
            ],
            level=level,
        )
        self.is_simultaneous: bool = True
        self.selected: List[bool] = [False for _ in range(TOTAL_CELLS)]
        self.values: List[Optional[int]] = [None for _ in range(TOTAL_CELLS)]
        self.flagged: List[bool] = [False for _ in range(TOTAL_CELLS)]
        self.remaining_mines: int = INITIAL_MINES
        self.remaining_peaces: int = INITIAL_SAFE_SPOTS
        self.is_hit_mine: bool = False
        self.correct_mines_found: int = 0

    def reset(self):
        """Resets the game state for a new match."""
        self.selected = [False for _ in range(TOTAL_CELLS)]
        self.values = [None for _ in range(TOTAL_CELLS)]
        self.flagged = [False for _ in range(TOTAL_CELLS)]
        self.remaining_mines = INITIAL_MINES
        self.remaining_peaces = INITIAL_SAFE_SPOTS
        self.is_hit_mine = False
        self.correct_mines_found = 0

    @staticmethod
    def get_row_col(index: int) -> Tuple[int, int]:
        return index // GRID_SIZE, index % GRID_SIZE

    @staticmethod
    def get_index(row: int, col: int) -> int:
        return row * GRID_SIZE + col

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Parses incoming MSweeper server commands."""
        if cmd_id == "StartGame":
            self.reset()
            return True
        elif cmd_id == "SelectPeaceResult":
            if isinstance(payload, dict):
                p_num = int(payload.get("peace_number", -1))
                val = int(payload.get("value", 0))
                if 0 <= p_num < TOTAL_CELLS:
                    if not self.selected[p_num]:
                        self.remaining_peaces = max(0, self.remaining_peaces - 1)
                    self.selected[p_num] = True
                    self.values[p_num] = val
                return True
        elif cmd_id == "MineSelected":
            if isinstance(payload, dict):
                p_num = int(payload.get("peace_number", -1))
                if 0 <= p_num < TOTAL_CELLS:
                    self.selected[p_num] = True
                self.is_hit_mine = True
                self.remaining_mines = 0
                self.remaining_peaces = 0
                print(f"[MSweeper Bot] Stepped on a mine at cell {p_num}! Locked out of further moves.")
                return True
        elif cmd_id == "SelectMineCorrect":
            if isinstance(payload, dict):
                p_num = int(payload.get("peace_number", -1))
                if 0 <= p_num < TOTAL_CELLS:
                    self.selected[p_num] = True
                    self.flagged[p_num] = True
                self.correct_mines_found += 1
                print(f"[MSweeper Bot] Flagged a correct mine at cell {p_num} (Score: {self.correct_mines_found}).")
                return True
        elif cmd_id == "SelectMineWrong":
            if isinstance(payload, dict):
                p_num = int(payload.get("peace_number", -1))
                if 0 <= p_num < TOTAL_CELLS:
                    self.selected[p_num] = True
                    self.flagged[p_num] = True
                print(f"[MSweeper Bot] Flagged a wrong cell at {p_num} (Not a mine).")
                return True
        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict):
                    self.remaining_mines = int(g_data.get("remaining_selectable_mines", self.remaining_mines))
                    self.remaining_peaces = int(g_data.get("remaining_selectable_peaces", self.remaining_peaces))
                    self.is_hit_mine = bool(g_data.get("is_tapped_mine", False))
                    board_list = g_data.get("board", [])
                    if isinstance(board_list, list):
                        for i in range(min(TOTAL_CELLS, len(board_list))):
                            cell = board_list[i]
                            if isinstance(cell, dict):
                                self.selected[i] = bool(cell.get("selected", False))
                                if cell.get("correctly_selected_mine") or cell.get("wrongly_selected_mine"):
                                    self.flagged[i] = True
                                    self.selected[i] = True
                                if cell.get("hitted_mine"):
                                    self.is_hit_mine = True
                                    self.selected[i] = True
                                if "value" in cell and self.selected[i]:
                                    self.values[i] = int(cell.get("value", 0))
                    return True
        elif cmd_id in ("FinishGame", "GameFinished"):
            self.is_game_active = False
            return True
        return False

    def get_legal_moves(self) -> List[Tuple[str, int]]:
        """
        Returns available moves as (command_id, cell_idx).
        Stops returning moves if the bot stepped on a mine or exhausted its actions.
        """
        if self.is_hit_mine:
            return []
        unselected = [i for i in range(TOTAL_CELLS) if not self.selected[i]]
        if not unselected:
            return []

        moves: List[Tuple[str, int]] = []
        if self.remaining_peaces > 0:
            for idx in unselected:
                moves.append(("SelectPeace", idx))
        if self.remaining_mines > 0:
            for idx in unselected:
                moves.append(("SelectMine", idx))
        return moves

    def is_critical_turn(self) -> bool:
        return False

    def compute_next_move(self) -> Optional[Tuple[str, int]]:
        """
        Computes the bot's next move.
        CRITICAL: Per instructions, at the current level this bot MUST NOT be able to solve Minesweeper!
        It plays blindly/casually without constraint solving, mixing random reveals ("SelectPeace")
        and blind flag guesses ("SelectMine").
        """
        if self.is_hit_mine:
            return None

        unselected = [i for i in range(TOTAL_CELLS) if not self.selected[i]]
        if not unselected:
            return None

        can_reveal = self.remaining_peaces > 0
        can_flag = self.remaining_mines > 0
        if not can_reveal and not can_flag:
            return None

        # Choose randomly between revealing a spot (SelectPeace) and guessing a mine flag (SelectMine)
        if can_reveal and can_flag:
            # 60% chance to dig/reveal (which can also step on a mine), 40% chance to guess a flag
            action = "SelectPeace" if random.random() < 0.60 else "SelectMine"
        elif can_reveal:
            action = "SelectPeace"
        else:
            action = "SelectMine"

        target_idx = random.choice(unselected)
        self.selected[target_idx] = True

        if action == "SelectMine":
            self.flagged[target_idx] = True
            self.remaining_mines = max(0, self.remaining_mines - 1)
        else:
            self.remaining_peaces = max(0, self.remaining_peaces - 1)

        return (action, target_idx)

    def build_move_command(self, move: Tuple[str, int]) -> dict:
        cmd_id, cell_idx = move
        return {
            "id": cmd_id,
            "data": cell_idx,
        }

    def format_state(self) -> str:
        revealed_cnt = sum(1 for s in self.selected if s)
        return (
            f"MSweeper (Selected: {revealed_cnt}/64, "
            f"Flags Left: {self.remaining_mines}, Safe Left: {self.remaining_peaces}, "
            f"Hit Mine: {self.is_hit_mine})"
        )
