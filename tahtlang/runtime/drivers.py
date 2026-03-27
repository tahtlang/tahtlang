"""
Drivers for TahtLang runtime.

InteractiveDriver: Textual-based terminal UI for playing.
SimulationDriver: Headless automated simulations for stats.
"""

import random
from typing import Dict

from ..parser.ast import (
    CardBranch,
    CardQueue,
    CardTimed,
    Choice,
    CounterMod,
    FixedValue,
    FlagClear,
    FlagSet,
    Game,
    RangeValue,
    Trigger,
)
from .engine import GameEngine

# ── Format helpers (shared by both drivers) ─────

def _format_value(val) -> str:
    if isinstance(val, FixedValue):
        if val.value > 0:
            return f"+{val.value}"
        return str(val.value)
    if isinstance(val, RangeValue):
        return f"{val.min_value}?{val.max_value}"
    raise ValueError(f"Unknown value: {type(val)}")


def _format_command(cmd) -> str:
    if isinstance(cmd, CounterMod):
        return f"{cmd.counter_id} {_format_value(cmd.value)}"
    if isinstance(cmd, FlagSet):
        return f"+{cmd.flag_id}"
    if isinstance(cmd, FlagClear):
        return f"-{cmd.flag_id}"
    if isinstance(cmd, CardQueue):
        return f"queue:{cmd.card_id}"
    if isinstance(cmd, CardTimed):
        return f"sched:{cmd.card_id}@{cmd.delay}"
    if isinstance(cmd, CardBranch):
        return f"branch({len(cmd.card_ids)})"
    if isinstance(cmd, Trigger):
        return f"trigger:{cmd.trigger_type.value}"
    raise ValueError(f"Unknown command: {type(cmd)}")


# ── Interactive Driver (Textual) ────────────────

class InteractiveDriver:
    """Textual-based CLI driver for playing TahtLang."""

    def __init__(self, game: Game, debug: bool = False):
        self.game = game
        self.debug = debug

    def play(self):
        from .tui import TahtApp
        app = TahtApp(self.game, debug=self.debug)
        app.run()


# ── Simulation Driver (headless) ────────────────

class SimulationDriver:
    """Automated driver for gathering statistics."""

    def __init__(self, game: Game):
        self.game = game
        self.card_counts: Dict[str, int] = {}
        self.total_turns = 0
        self.game_over_reasons: Dict[str, int] = {}

    def run_simulations(
        self, count: int = 100, max_turns: int = 1000,
    ) -> Dict:
        """Run multiple games and return metrics."""
        self.card_counts = {
            card.id: 0 for card in self.game.cards
        }
        self.total_turns = 0
        self.game_over_reasons = {}

        for _ in range(count):
            self._run_single(max_turns)

        return {
            "card_counts": self.card_counts,
            "avg_turns": self.total_turns / count,
            "game_over_reasons": self.game_over_reasons,
            "total_runs": count,
        }

    def _run_single(self, max_turns):
        engine = GameEngine(self.game)
        turns = 0

        while (
            not engine.state.is_game_over
            and turns < max_turns
        ):
            card = engine.pick_next_card()
            if not card:
                break

            self.card_counts[card.id] += 1

            if not card.choices:
                engine.apply_choice(
                    card, Choice(label=""),
                )
            else:
                choice = random.choice(card.choices)
                engine.apply_choice(card, choice)

            turns += 1

        self.total_turns += turns
        reason = (
            engine.state.game_over_reason
            or "Pool exhausted"
        )
        self.game_over_reasons[reason] = (
            self.game_over_reasons.get(reason, 0) + 1
        )
