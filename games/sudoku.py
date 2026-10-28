"""Sudoku (سودوکو) Game Logic for Cafe Fekr Bots.
Decoupled game engine representing the 9x9 (81-cell) Sudoku board.
Matches kafehfekrbackend/Entities/Games/Sudoku/__init__.py and kafehfekr Flutter client 1:1.

IMPORTANT BOT REQUIREMENT (Per Specification):
- Current bot level MUST NOT be able to solve Sudoku. It is strictly for testing/sparring.
- The bot makes casual, locally plausible placements without full backtracking or exact constraint satisfaction.
- The bot never completes a full valid solution or auto-solves the puzzle.
"""
import random
from typing import Any, Dict, List, Optional, Tuple
from .base_game import BaseGameLogic

TOTAL_CELLS = 81
GRID_SIZE = 9
BOX_SIZE = 3

class SudokuGameLogic(BaseGameLogic):
    def __init__(self, level: int = 1):
        super().__init__(
            game_type="Sudoku",
            game_type_aliases=[
                "sudoku",
                "سودوکو",
            ],
            level=level,
        )
        self.is_simultaneous: bool = True
        self.board_values: List[int] = [0 for _ in range(TOTAL_CELLS)]
        self.is_base_number: List[bool] = [False for _ in range(TOTAL_CELLS)]
        self.is_board_initialized: bool = False

    def reset(self):
        """Resets the game state for a new round/match."""
        self.board_values = [0 for _ in range(TOTAL_CELLS)]
        self.is_base_number = [False for _ in range(TOTAL_CELLS)]
        self.is_board_initialized = False

    @staticmethod
    def get_row_col(index: int) -> Tuple[int, int]:
        return index // GRID_SIZE, index % GRID_SIZE

    @staticmethod
    def get_index(row: int, col: int) -> int:
        return row * GRID_SIZE + col

    def get_box_indices(self, box_r: int, box_c: int) -> List[int]:
        indices = []
        start_r = box_r * BOX_SIZE
        start_c = box_c * BOX_SIZE
        for r in range(start_r, start_r + BOX_SIZE):
            for c in range(start_c, start_c + BOX_SIZE):
                indices.append(self.get_index(r, c))
        return indices

    def handle_server_command(self, cmd_id: str, payload: Any) -> bool:
        """Parses incoming game state commands (StartGame, ReconnectData, etc.)."""
        if cmd_id == "StartGame":
            if isinstance(payload, dict) and "board" in payload:
                self._parse_board_data(payload["board"])
                return True
            return False
        elif cmd_id == "ReconnectData":
            if isinstance(payload, dict):
                g_data = payload.get("game_data", {})
                if isinstance(g_data, dict) and "board" in g_data:
                    self._parse_board_data(g_data["board"])
                    return True
            return False
        elif cmd_id == "WrongSolve":
            print("[Sudoku Bot] Server reported WrongSolve.")
            return True
        elif cmd_id in ("FinishGame", "GameFinished"):
            self.is_game_active = False
            return True
        return False

    def _parse_board_data(self, board_list: List[dict]):
        if not isinstance(board_list, list) or len(board_list) < TOTAL_CELLS:
            return
        self.board_values = [0 for _ in range(TOTAL_CELLS)]
        self.is_base_number = [False for _ in range(TOTAL_CELLS)]
        for i in range(min(TOTAL_CELLS, len(board_list))):
            item = board_list[i]
            if isinstance(item, dict):
                val = int(item.get("number", 0))
                is_base = bool(item.get("is_base_number", False))
                self.board_values[i] = val
                self.is_base_number[i] = is_base
        self.is_board_initialized = True
        print(f"[Sudoku Bot] Board initialized with {sum(self.is_base_number)} base clues.")

    def get_legal_moves(self) -> List[Tuple[int, int]]:
        """
        Returns a list of legal test candidate moves: (cell_idx, number).
        Only targets empty, non-base cells.
        """
        empty_indices = [
            i for i in range(TOTAL_CELLS)
            if not self.is_base_number[i] and self.board_values[i] == 0
        ]
        if not empty_indices:
            return []

        candidates: List[Tuple[int, int]] = []
        for idx in empty_indices:
            r, c = self.get_row_col(idx)
            used_nums = set()
            # Row numbers
            for c_i in range(GRID_SIZE):
                val = self.board_values[self.get_index(r, c_i)]
                if val > 0:
                    used_nums.add(val)
            # Column numbers
            for r_i in range(GRID_SIZE):
                val = self.board_values[self.get_index(r_i, c)]
                if val > 0:
                    used_nums.add(val)
            # 3x3 Box numbers
            b_r, b_c = r // BOX_SIZE, c // BOX_SIZE
            for b_idx in self.get_box_indices(b_r, b_c):
                val = self.board_values[b_idx]
                if val > 0:
                    used_nums.add(val)

            available = [n for n in range(1, 10) if n not in used_nums]
            for n in available:
                candidates.append((idx, n))
        return candidates

    def is_critical_turn(self) -> bool:
        return False

    def compute_next_move(self) -> Optional[Tuple[int, int]]:
        """
        Computes the bot next move.
        CRITICAL: Per instructions, bot level MUST NOT be able to solve Sudoku.
        It makes casual, locally plausible placements without global constraint search.
        """
        candidates = self.get_legal_moves()
        if not candidates:
            empty_indices = [
                i for i in range(TOTAL_CELLS)
                if not self.is_base_number[i] and self.board_values[i] == 0
            ]
            if not empty_indices:
                return None
            target_idx = random.choice(empty_indices)
            chosen_num = random.randint(1, 9)
            self.board_values[target_idx] = chosen_num
            return (target_idx, chosen_num)

        cells_map: Dict[int, List[int]] = {}
        for idx, num in candidates:
            if idx not in cells_map:
                cells_map[idx] = []
            cells_map[idx].append(num)

        chosen_idx = random.choice(list(cells_map.keys()))
        possible_nums = cells_map[chosen_idx]
        chosen_num = random.choice(possible_nums)

        self.board_values[chosen_idx] = chosen_num
        return (chosen_idx, chosen_num)

    def build_move_command(self, move: Tuple[int, int]) -> dict:
        cell_idx, number = move
        return {
            "id": "SelectPeace",
            "piece_id": cell_idx,
            "number": number,
            "data": {
                "piece_id": cell_idx,
                "number": number,
            }
        }

    def format_state(self) -> str:
        filled = sum(1 for v in self.board_values if v > 0)
        base_cnt = sum(1 for b in self.is_base_number if b)
        return f"Sudoku (Filled: {filled}/81, Base Clues: {base_cnt})"
