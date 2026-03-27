"""
Drivers for TahtLang runtime.

InteractiveDriver: Ncurses-based terminal UI for playing the game.
SimulationDriver: For running automated simulations to gather stats.
"""

import curses
import random
import textwrap
from typing import Dict, List

from .engine import GameEngine
from ..parser.ast import (
    CardBranch,
    CardQueue,
    CardTimed,
    Choice,
    CounterMod,
    FlagClear,
    FlagSet,
    FixedValue,
    Game,
    RangeValue,
    Trigger,
)


class InteractiveDriver:
    """Ncurses-based CLI driver for playing TahtLang games."""

    def __init__(self, game: Game):
        self.engine = GameEngine(game)
        self.selected_choice = 0

    def play(self):
        """Initialize curses and start the game loop."""
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        # Initial curses setup
        curses.curs_set(0)  # Hide cursor
        stdscr.keypad(True)
        curses.start_color()
        curses.use_default_colors()
        
        # Color pairs
        curses.init_pair(1, curses.COLOR_CYAN, -1)   # Headers
        curses.init_pair(2, curses.COLOR_YELLOW, -1) # Selection
        curses.init_pair(3, curses.COLOR_RED, -1)    # Killer stats / Error
        curses.init_pair(4, curses.COLOR_GREEN, -1)  # Non-killer stats
        curses.init_pair(5, curses.COLOR_BLUE, -1)   # Separators/Borders

        while not self.engine.state.is_game_over:
            card = self.engine.pick_next_card()
            if not card:
                self._draw_error(stdscr, "Pool Exhausted! No more cards available.")
                stdscr.getch()
                break

            self.selected_choice = 0
            
            while True:
                self._draw_screen(stdscr, card)
                key = stdscr.getch()

                if key == curses.KEY_UP:
                    self.selected_choice = (self.selected_choice - 1) % len(card.choices) if card.choices else 0
                elif key == curses.KEY_DOWN:
                    self.selected_choice = (self.selected_choice + 1) % len(card.choices) if card.choices else 0
                elif key in (curses.KEY_ENTER, 10, 13):
                    if card.choices:
                        self.engine.apply_choice(
                            card,
                            card.choices[self.selected_choice],
                        )
                    else:
                        self.engine.apply_choice(
                            card, Choice(label=""),
                        )
                    break
                elif key == ord('q'):
                    return

        self._draw_game_over(stdscr)
        stdscr.getch()

    def _draw_screen(self, stdscr, card):
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        split_x = int(width * 0.68)

        # --- BORDERS & DIVIDERS ---
        # Vertical divider
        for y in range(height - 1):
            stdscr.addstr(y, split_x, "┃", curses.color_pair(5))

        # Top bar divider
        stdscr.addstr(2, 0, "━" * split_x + "╋", curses.color_pair(5))
        
        # Footer divider
        footer_y = height - 5
        stdscr.addstr(footer_y, 0, "━" * split_x + "┻", curses.color_pair(5))

        # --- LEFT SIDE ---
        # 1. Top Bar: Killer Counters
        self._draw_killer_stats(stdscr, 1, 2)

        # 2. Card Header
        char_info = ""
        if card.bearer:
            char = self.engine.game.get_character(card.bearer.character_id)
            char_name = char.name if char else card.bearer.character_id
            variant = f" ({card.bearer.variant_id})" if card.bearer.variant_id else ""
            char_info = f" • {char_name}{variant}"
        
        stdscr.addstr(4, 2, f" {card.name.upper()} ", curses.A_REVERSE | curses.color_pair(1))
        stdscr.addstr(4, 2 + len(card.name) + 2, char_info, curses.color_pair(1))

        # 3. Card Text
        wrapped_text = textwrap.wrap(card.text, width=split_x - 8)
        curr_y = 7
        for line in wrapped_text:
            stdscr.addstr(curr_y, 4, line)
            curr_y += 1
        
        curr_y += 2

        # 4. Choices
        if not card.choices:
            stdscr.addstr(curr_y, 7, "[ Press Enter to continue ]", curses.A_BLINK)
        else:
            for i, choice in enumerate(card.choices):
                if i == self.selected_choice:
                    stdscr.addstr(curr_y, 4, " ➔ ", curses.color_pair(2))
                    stdscr.addstr(curr_y, 7, choice.label, curses.color_pair(2) | curses.A_BOLD)
                else:
                    stdscr.addstr(curr_y, 7, choice.label, curses.A_DIM)
                curr_y += 1

        # 5. Dynamic Footer (Effects)
        if card.choices:
            current_choice = card.choices[self.selected_choice]
            effects = [self._format_command(cmd) for cmd in current_choice.commands]
            effect_text = "EXPECTED EFFECTS: " + (", ".join(effects) if effects else "NONE")
            wrapped_effects = textwrap.wrap(effect_text, width=split_x - 6)
            for i, line in enumerate(wrapped_effects[:3]):
                stdscr.addstr(footer_y + 1 + i, 2, line, curses.A_DIM)

        # --- RIGHT SIDE ---
        # 1. Other Stats
        stdscr.addstr(1, split_x + 2, " COUNTERS ", curses.A_REVERSE | curses.color_pair(4))
        self._draw_other_stats(stdscr, 3, split_x + 3)

        # 2. Active Flags
        active_flags = sorted(list(self.engine.state.flags))
        flags_y = height // 2 - 2
        stdscr.addstr(flags_y, split_x + 2, f" FLAGS ({len(active_flags)}) ", curses.A_REVERSE | curses.color_pair(1))
        self._draw_flags(stdscr, flags_y + 2, split_x + 3, height - 8, active_flags)

        # 3. Engine Pool Status
        pool_y = height - 7
        stdscr.addstr(pool_y, split_x + 2, " POOLS ", curses.A_REVERSE | curses.color_pair(5))
        
        eligible = self.engine.get_eligible_cards()
        sched_count = sum(len(v) for v in self.engine.state.schedule.values())
        
        stdscr.addstr(pool_y + 2, split_x + 3, f"Random    : {len(eligible)}")
        stdscr.addstr(pool_y + 3, split_x + 3, f"Queue     : {len(self.engine.state.queue)}")
        stdscr.addstr(pool_y + 4, split_x + 3, f"Scheduled : {sched_count}")

        # --- BOTTOM GUIDE ---
        guide = " [q] Quit  [↑↓] Move  [Enter] Select"
        stdscr.addstr(height - 1, 0, guide[:width-1], curses.A_DIM)

        stdscr.refresh()

    def _draw_flags(self, stdscr, start_y, x, max_y, active_flags):
        curr_y = start_y
        if not active_flags:
            stdscr.addstr(curr_y, x, "No active flags", curses.A_DIM)
            return

        for f_id in active_flags:
            if curr_y >= max_y:
                stdscr.addstr(curr_y, x, "...", curses.A_DIM)
                break
            
            flag_def = self.engine.game.get_flag(f_id)
            name = flag_def.name if flag_def else f_id
            stdscr.addstr(curr_y, x, f"⚑ {name}", curses.color_pair(1))
            curr_y += 1

    def _draw_killer_stats(self, stdscr, y, x):
        stats = []
        for c_id, val in self.engine.state.counters.items():
            counter_def = self.engine.game.get_counter(c_id)
            if counter_def and counter_def.killer:
                name = counter_def.icon if counter_def.icon else c_id
                name = name.replace('"', '').replace("'", "")
                stats.append(f"{name} {val}%")
        
        stdscr.addstr(y, x, "  ".join(stats), curses.color_pair(3) | curses.A_BOLD)

    def _draw_other_stats(self, stdscr, start_y, x):
        curr_y = start_y
        for c_id, val in self.engine.state.counters.items():
            counter_def = self.engine.game.get_counter(c_id)
            if counter_def and not counter_def.killer:
                name = counter_def.icon if counter_def.icon else c_id
                name = name.replace('"', '').replace("'", "")
                stdscr.addstr(curr_y, x, f"• {name}: {val}", curses.color_pair(4))
                curr_y += 1

    def _format_command(self, cmd) -> str:
        if isinstance(cmd, CounterMod):
            return f"{cmd.counter_id} {self._format_value(cmd.value)}"
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

    @staticmethod
    def _format_value(val) -> str:
        if isinstance(val, FixedValue):
            if val.value > 0:
                return f"+{val.value}"
            return str(val.value)
        if isinstance(val, RangeValue):
            return f"{val.min_value}?{val.max_value}"
        raise ValueError(f"Unknown value: {type(val)}")

    def _draw_game_over(self, stdscr):
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        box_w, box_h = 44, 10
        y, x = (h - box_h) // 2, (w - box_w) // 2
        
        # Draw game over box
        for i in range(box_h):
            stdscr.addstr(y + i, x, "┃" + " " * (box_w-2) + "┃", curses.color_pair(3))
        stdscr.addstr(y, x, "┏" + "━" * (box_w-2) + "┓", curses.color_pair(3))
        stdscr.addstr(y + box_h - 1, x, "┗" + "━" * (box_w-2) + "┛", curses.color_pair(3))
        
        stdscr.addstr(y + 2, x + (box_w - 11) // 2, " GAME OVER ", curses.A_REVERSE | curses.A_BOLD)
        reason = self.engine.state.game_over_reason[:box_w-6]
        stdscr.addstr(y + 4, x + (box_w - len(reason)) // 2, reason)
        turns = f"Total Duration: {self.engine.state.current_turn} Turns"
        stdscr.addstr(y + 5, x + (box_w - len(turns)) // 2, turns)
        stdscr.addstr(y + 8, x + (box_w - 22) // 2, "Press any key to exit", curses.A_DIM)
        stdscr.refresh()

    def _draw_error(self, stdscr, msg):
        stdscr.addstr(10, 2, f" ERROR: {msg} ", curses.color_pair(3) | curses.A_REVERSE)
        stdscr.refresh()


class SimulationDriver:
    """Automated driver for gathering statistics and balancing data."""

    def __init__(self, game: Game):
        self.game = game
        self.card_counts: Dict[str, int] = {}
        self.total_turns = 0
        self.game_over_reasons: Dict[str, int] = {}

    def run_simulations(self, count: int = 100, max_turns: int = 1000) -> Dict:
        """Run multiple games and return a detailed metrics report."""
        self.card_counts = {card.id: 0 for card in self.game.cards}
        self.total_turns = 0
        self.game_over_reasons = {}
        
        for _ in range(count):
            engine = GameEngine(self.game)
            turns = 0
            
            while not engine.state.is_game_over and turns < max_turns:
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
            reason = engine.state.game_over_reason or "Pool exhausted"
            self.game_over_reasons[reason] = self.game_over_reasons.get(reason, 0) + 1
                
        return {
            "card_counts": self.card_counts,
            "avg_turns": self.total_turns / count,
            "game_over_reasons": self.game_over_reasons,
            "total_runs": count
        }
