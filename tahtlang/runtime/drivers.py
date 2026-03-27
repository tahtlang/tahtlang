"""
Drivers for TahtLang runtime.

InteractiveDriver: Textual-based terminal UI for playing.
SimulationDriver: Headless automated simulations for stats.
AutoplayDriver: Text-based automated playthrough with full output.
"""

import random
import sys
from typing import Dict, Optional, TextIO

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


# ── Autoplay Driver (text-based playthrough) ──

class AutoplayDriver:
    """
    Plays a full game automatically, printing each turn's
    card text, choices, selected choice, and counter state.
    Output is plain text readable by humans or LLMs.
    """

    def __init__(
        self,
        game: Game,
        max_turns: int = 200,
        seed: Optional[int] = None,
        out: TextIO = sys.stdout,
    ):
        self.game = game
        self.max_turns = max_turns
        self.out = out
        if seed is not None:
            random.seed(seed)

    def _counter_bar(self, engine: GameEngine) -> str:
        """Format killer counters as a status line."""
        parts = []
        for c in self.game.counters:
            if not c.killer:
                continue
            val = engine.state.counters.get(c.id, 0)
            parts.append(f"{c.name}:{val}")
        return " | ".join(parts)

    def _format_effects(self, choice: Choice) -> str:
        """Format choice effects."""
        if not choice.commands:
            return "no effect"
        return ", ".join(
            _format_command(cmd) for cmd in choice.commands
        )

    def play(self):
        engine = GameEngine(self.game)
        turn = 0

        self.out.write("=" * 60 + "\n")
        self.out.write(" AUTOPLAY START\n")
        self.out.write("=" * 60 + "\n\n")

        while (
            not engine.state.is_game_over
            and turn < self.max_turns
        ):
            card = engine.pick_next_card()
            if not card:
                self.out.write(
                    "\n[!] No cards left in pool.\n"
                )
                break

            turn += 1

            # Header
            self.out.write(f"--- Turn {turn} ---\n")
            self.out.write(
                f"[{self._counter_bar(engine)}]\n"
            )

            # Card info
            bearer_str = ""
            if card.bearer:
                char = self.game.get_character(
                    card.bearer.character_id,
                )
                name = char.name if char else card.bearer.character_id
                if card.bearer.variant_id:
                    var = self.game.get_variant(
                        card.bearer.variant_id,
                    )
                    var_name = (
                        var.name if var
                        else card.bearer.variant_id
                    )
                    bearer_str = f"{name} ({var_name})"
                else:
                    bearer_str = name

            if bearer_str:
                self.out.write(f"{bearer_str}:\n")
            self.out.write(f'  "{card.text}"\n')

            # Choices
            if not card.choices:
                self.out.write("  (no choices)\n")
                engine.apply_choice(
                    card, Choice(label=""),
                )
            else:
                for i, ch in enumerate(card.choices):
                    effects = self._format_effects(ch)
                    self.out.write(
                        f"  [{i+1}] {ch.label}"
                        f"  ({effects})\n"
                    )

                pick = random.randint(
                    0, len(card.choices) - 1,
                )
                chosen = card.choices[pick]
                self.out.write(
                    f"  >>> Pick: [{pick+1}]"
                    f" {chosen.label}\n"
                )
                engine.apply_choice(card, chosen)

            self.out.write("\n")

        # Game over
        self.out.write("=" * 60 + "\n")
        if engine.state.is_game_over:
            self.out.write(
                f" GAME OVER: {engine.state.game_over_reason}\n"
            )
        else:
            self.out.write(
                f" {turn} turns played, game did not end.\n"
            )
        self.out.write(
            f"[{self._counter_bar(engine)}]\n"
        )
        self.out.write("=" * 60 + "\n")
