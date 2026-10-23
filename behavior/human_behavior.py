"""
Human Behavior Simulator for Cafe Fekr Bots.

Models human-like playing behavior:
- Realistic reaction and thinking delays (not instant robotic moves).
- Natural variation (jitter, hesitation, opening tempo vs endgame tempo).
- Difficulty-aware cognitive pacing:
    * Level 1 (Beginner): Casual, sometimes rushed, sometimes distracted.
    * Level 2 (Intermediate): Balanced thinking time, pauses on tactical checks.
    * Level 3 (Hard/Master): Deep, consistent pacing.
"""

import asyncio
import random


class HumanBehavior:
    def __init__(
        self,
        base_delay_min: float = 1.0,
        base_delay_max: float = 2.4,
        hesitation_chance: float = 0.25,
    ):
        self.base_delay_min = base_delay_min
        self.base_delay_max = base_delay_max
        self.hesitation_chance = hesitation_chance

    def calculate_thinking_delay(
        self,
        level: int = 1,
        is_critical: bool = False,
        legal_moves_count: int = 9,
    ) -> float:
        """
        Calculates a natural human thinking duration in seconds.
        """
        # Forced move: only 1 option available, humans react faster
        if legal_moves_count <= 1:
            return round(random.uniform(0.6, 1.2), 2)

        # Base cognitive delay based on difficulty level
        if level == 1:
            # Casual beginner: usually 1.0 - 2.2s, occasional quick click or delay
            delay = random.uniform(1.0, 2.2)
        elif level == 2:
            # Intermediate player: 1.2 - 2.5s
            delay = random.uniform(1.2, 2.5)
        else:
            # Master/Level 3: deliberate, calculating 1.4 - 2.8s
            delay = random.uniform(1.4, 2.8)

        # Critical situation (threat or winning shot) -> human hesitation / double check
        if is_critical:
            hesitation = random.uniform(0.3, 0.7)
            delay += hesitation
        elif random.random() < self.hesitation_chance:
            # Occasional casual distraction / hesitation
            delay += random.uniform(0.2, 0.6)

        # Clamp between sensible human bounds (minimum 0.7s, maximum 3.5s)
        delay = max(0.7, min(delay, 3.5))
        return round(delay, 2)

    async def simulate_thinking(
        self,
        level: int = 1,
        is_critical: bool = False,
        legal_moves_count: int = 9,
        bot_label: str = "Bot",
    ) -> float:
        """
        Asynchronously waits to simulate human thinking time and logs the action.
        """
        delay = self.calculate_thinking_delay(
            level=level,
            is_critical=is_critical,
            legal_moves_count=legal_moves_count,
        )
        print(f"[{bot_label}] Thinking like a human... ({delay}s)")
        await asyncio.sleep(delay)
        return delay
