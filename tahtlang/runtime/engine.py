"""
Core Game Engine for TahtLang.

This module handles the game state, card selection, and effect application.
It doesn't handle I/O (no print or input); that's for the drivers.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..parser.ast import (
    Card,
    CardBranch,
    CardQueue,
    CardTimed,
    Choice,
    Condition,
    CounterCondition,
    CounterMod,
    FixedValue,
    FlagClear,
    FlagCondition,
    FlagSet,
    Game,
    Operator,
    RangeValue,
    Trigger,
)


@dataclass
class GameState:
    """Current state of a running game."""

    counters: Dict[str, int] = field(default_factory=dict)
    flags: Set[str] = field(default_factory=set)
    # card_id -> turns remaining until unlocked
    locks: Dict[str, int] = field(default_factory=dict)
    # cards to show permanently locked for this reign
    locks_once: Set[str] = field(default_factory=set)
    # card queue (immediate)
    queue: List[str] = field(default_factory=list)
    # scheduled cards: turn_to_appear -> [card_ids]
    schedule: Dict[int, List[str]] = field(default_factory=dict)
    current_turn: int = 0
    is_game_over: bool = False
    game_over_reason: str = ""


class GameEngine:
    """
    Drives the game logic based on the Game AST and current State.
    """

    def __init__(self, game: Game):
        self.game = game
        self.state = GameState()
        self._reset_state()

    def _reset_state(self):
        """Initialize state from game AST."""
        # Initial counters
        for c in self.game.counters:
            if not c.is_virtual:
                self.state.counters[c.id] = c.start

        # Initial flags
        if self.game.settings:
            for f_id in self.game.settings.starting_flags:
                self.state.flags.add(f_id)

    def get_eligible_cards(self) -> List[Tuple[Card, float]]:
        """Return a list of (Card, current_weight) for the random pool."""
        eligible = []
        for card in self.game.cards:
            # 1. Skip ring cards (they only come from queue)
            if card.ring:
                continue

            # 2. Check locks
            if card.id in self.state.locks or card.id in self.state.locks_once:
                continue

            # 3. Check requirements
            if not self._check_conditions(card.require):
                continue

            # 4. Calculate total weight
            weight = self._calculate_weight(card)
            if weight > 0:
                eligible.append((card, weight))

        return eligible

    def _check_conditions(self, conditions: Tuple[Condition, ...]) -> bool:
        """Check if all conditions are met."""
        for cond in conditions:
            if isinstance(cond, FlagCondition):
                is_set = cond.flag_id in self.state.flags
                if cond.negated:
                    if is_set:
                        return False
                elif not is_set:
                    return False

            elif isinstance(cond, CounterCondition):
                val = self.state.counters.get(cond.counter_id, 0)
                if not self._compare(val, cond.operator, cond.value):
                    return False
        return True

    @staticmethod
    def _compare(val: int, op: Operator, target: int) -> bool:
        if op == Operator.LT:
            return val < target
        if op == Operator.LTE:
            return val <= target
        if op == Operator.GT:
            return val > target
        if op == Operator.GTE:
            return val >= target
        if op == Operator.EQ:
            return val == target
        raise ValueError(f"Unknown operator: {op}")

    def _calculate_weight(self, card: Card) -> float:
        """Sum weights whose conditions pass. Default to 0 if no weights."""
        if not card.weights:
            return 0.0

        total = 0.0
        for w in card.weights:
            if w.condition is None or self._check_conditions((w.condition,)):
                total += w.value
        return total

    def pick_next_card(self) -> Optional[Card]:
        """Determine which card to show next."""
        # 1. Check scheduled cards for current turn
        scheduled = self.state.schedule.get(self.state.current_turn, [])
        if scheduled:
            card_id = scheduled.pop(0)
            return self.game.get_card(card_id)

        # 2. Check immediate queue
        if self.state.queue:
            card_id = self.state.queue.pop(0)
            return self.game.get_card(card_id)

        # 3. Random pool
        eligible = self.get_eligible_cards()
        if not eligible:
            return None

        cards, weights = zip(*eligible)
        return random.choices(cards, weights=weights, k=1)[0]

    def apply_choice(self, card: Card, choice: Choice):
        """Apply effects of a choice and advance turn."""
        # 1. Apply commands
        for cmd in choice.commands:
            self._apply_command(cmd)

        # 2. Apply card lock
        self._apply_lock(card)

        # 3. Check game over
        self._check_game_over()

        # 4. Advance turn
        self._advance_turn()

    def _apply_command(self, cmd):
        if isinstance(cmd, CounterMod):
            val = self._resolve_value(cmd.value)
            current = self.state.counters.get(cmd.counter_id, 0)
            self.state.counters[cmd.counter_id] = max(0, min(100, current + val))

        elif isinstance(cmd, FlagSet):
            self.state.flags.add(cmd.flag_id)

        elif isinstance(cmd, FlagClear):
            self.state.flags.discard(cmd.flag_id)

        elif isinstance(cmd, CardQueue):
            self.state.queue.append(cmd.card_id)

        elif isinstance(cmd, CardBranch):
            # Pick first card whose requirements pass
            for c_id in cmd.card_ids:
                card = self.game.get_card(c_id)
                if card and self._check_conditions(card.require):
                    self.state.queue.append(c_id)
                    break

        elif isinstance(cmd, CardTimed):
            target_turn = self.state.current_turn + cmd.delay
            if target_turn not in self.state.schedule:
                self.state.schedule[target_turn] = []
            self.state.schedule[target_turn].append(cmd.card_id)

        else:
            raise ValueError(
                f"Unknown command type: {type(cmd)}"
            )

    def _resolve_value(self, val_or_range) -> int:
        if isinstance(val_or_range, FixedValue):
            return val_or_range.value
        if isinstance(val_or_range, RangeValue):
            return random.randint(
                val_or_range.min_value,
                val_or_range.max_value,
            )
        raise ValueError(
            f"Unknown value type: {type(val_or_range)}"
        )

    def _apply_lock(self, card: Card):
        if card.lockturn in ("dispose", "once"):
            self.state.locks_once.add(card.id)
        elif isinstance(card.lockturn, int) and card.lockturn > 0:
            self.state.locks[card.id] = card.lockturn

    def _check_game_over(self):
        """Check if any killer counters hit 0 or 100."""
        for counter_def in self.game.counters:
            if not counter_def.killer:
                continue
            
            val = self.state.counters.get(counter_def.id, 50)
            if val <= 0:
                self.state.is_game_over = True
                self.state.game_over_reason = f"{counter_def.name} hit 0"
                break
            if val >= 100:
                self.state.is_game_over = True
                self.state.game_over_reason = f"{counter_def.name} hit 100"
                break

    def _advance_turn(self):
        self.state.current_turn += 1
        
        # Update lock timers
        to_remove = []
        for c_id in self.state.locks:
            self.state.locks[c_id] -= 1
            if self.state.locks[c_id] <= 0:
                to_remove.append(c_id)
        
        for c_id in to_remove:
            del self.state.locks[c_id]
