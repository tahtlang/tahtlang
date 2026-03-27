"""
Drivers for TahtLang runtime.

InteractiveDriver: Ncurses-based terminal UI for playing the game.
SimulationDriver: For running automated simulations to gather stats.
"""

import curses
import random
import textwrap
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

# Curses color pair constants
CLR_HEADER = 1
CLR_SELECT = 2
CLR_KILLER = 3
CLR_STAT = 4
CLR_BORDER = 5


class InteractiveDriver:
    """Ncurses-based CLI driver for playing TahtLang games."""

    def __init__(self, game: Game):
        self.engine = GameEngine(game)
        self.selected_choice = 0

    def play(self):
        """Initialize curses and start the game loop."""
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(CLR_HEADER, curses.COLOR_CYAN, -1)
        curses.init_pair(CLR_SELECT, curses.COLOR_YELLOW, -1)
        curses.init_pair(CLR_KILLER, curses.COLOR_RED, -1)
        curses.init_pair(CLR_STAT, curses.COLOR_GREEN, -1)
        curses.init_pair(CLR_BORDER, curses.COLOR_BLUE, -1)

        while not self.engine.state.is_game_over:
            card = self.engine.pick_next_card()
            if not card:
                self._draw_error(
                    stdscr, "Pool Exhausted!",
                )
                stdscr.getch()
                break

            self.selected_choice = 0

            while True:
                self._draw_screen(stdscr, card)
                key = stdscr.getch()

                if key == curses.KEY_UP:
                    self._move_choice(-1, card)
                elif key == curses.KEY_DOWN:
                    self._move_choice(1, card)
                elif key in (curses.KEY_ENTER, 10, 13):
                    if card.choices:
                        chosen = card.choices[
                            self.selected_choice
                        ]
                        self.engine.apply_choice(
                            card, chosen,
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

    def _move_choice(self, direction, card):
        if card.choices:
            n = len(card.choices)
            self.selected_choice = (
                (self.selected_choice + direction) % n
            )

    def _draw_screen(self, stdscr, card):
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        split_x = int(width * 0.68)

        self._draw_borders(stdscr, height, split_x)
        self._draw_left_panel(
            stdscr, card, height, split_x,
        )
        self._draw_right_panel(
            stdscr, height, split_x,
        )

        guide = " [q] Quit  [↑↓] Move  [Enter] Select"
        stdscr.addstr(
            height - 1, 0,
            guide[:width - 1],
            curses.A_DIM,
        )
        stdscr.refresh()

    def _draw_borders(self, stdscr, height, split_x):
        border = curses.color_pair(CLR_BORDER)
        for y in range(height - 1):
            stdscr.addstr(y, split_x, "┃", border)

        top_line = "━" * split_x + "╋"
        stdscr.addstr(2, 0, top_line, border)

        footer_y = height - 5
        footer_line = "━" * split_x + "┻"
        stdscr.addstr(footer_y, 0, footer_line, border)

    def _draw_left_panel(
        self, stdscr, card, height, split_x,
    ):
        footer_y = height - 5

        # 1. Top bar: killer counters
        self._draw_killer_stats(stdscr, 1, 2)

        # 2. Card header
        self._draw_card_header(
            stdscr, card, split_x,
        )

        # 3. Card text
        wrapped = textwrap.wrap(
            card.text, width=split_x - 8,
        )
        curr_y = 7
        for line in wrapped:
            stdscr.addstr(curr_y, 4, line)
            curr_y += 1

        curr_y += 2

        # 4. Choices
        curr_y = self._draw_choices(
            stdscr, card, curr_y,
        )

        # 5. Effect preview
        self._draw_effects(
            stdscr, card, footer_y, split_x,
        )

    def _draw_card_header(self, stdscr, card, split_x):
        char_info = ""
        if card.bearer:
            char = self.engine.game.get_character(
                card.bearer.character_id,
            )
            char_name = (
                char.name if char
                else card.bearer.character_id
            )
            variant = ""
            if card.bearer.variant_id:
                variant = f" ({card.bearer.variant_id})"
            char_info = f" • {char_name}{variant}"

        header_attr = (
            curses.A_REVERSE | curses.color_pair(CLR_HEADER)
        )
        label = f" {card.name.upper()} "
        stdscr.addstr(4, 2, label, header_attr)
        stdscr.addstr(
            4, 2 + len(label),
            char_info,
            curses.color_pair(CLR_HEADER),
        )

    def _draw_choices(self, stdscr, card, curr_y):
        if not card.choices:
            stdscr.addstr(
                curr_y, 7,
                "[ Press Enter to continue ]",
                curses.A_BLINK,
            )
            return curr_y + 1

        sel_attr = (
            curses.color_pair(CLR_SELECT) | curses.A_BOLD
        )
        for i, choice in enumerate(card.choices):
            if i == self.selected_choice:
                stdscr.addstr(
                    curr_y, 4, " ➔ ",
                    curses.color_pair(CLR_SELECT),
                )
                stdscr.addstr(
                    curr_y, 7, choice.label, sel_attr,
                )
            else:
                stdscr.addstr(
                    curr_y, 7, choice.label, curses.A_DIM,
                )
            curr_y += 1
        return curr_y

    def _draw_effects(
        self, stdscr, card, footer_y, split_x,
    ):
        if not card.choices:
            return
        chosen = card.choices[self.selected_choice]
        effects = [
            self._format_command(cmd)
            for cmd in chosen.commands
        ]
        joined = ", ".join(effects) if effects else "NONE"
        text = f"EXPECTED EFFECTS: {joined}"
        wrapped = textwrap.wrap(text, width=split_x - 6)
        for i, line in enumerate(wrapped[:3]):
            stdscr.addstr(
                footer_y + 1 + i, 2, line, curses.A_DIM,
            )

    def _draw_right_panel(self, stdscr, height, split_x):
        x = split_x + 2
        x_inner = split_x + 3

        # 1. Counters
        header_attr = (
            curses.A_REVERSE | curses.color_pair(CLR_STAT)
        )
        stdscr.addstr(1, x, " COUNTERS ", header_attr)
        self._draw_other_stats(stdscr, 3, x_inner)

        # 2. Flags
        active_flags = sorted(self.engine.state.flags)
        flags_y = height // 2 - 2
        flags_label = f" FLAGS ({len(active_flags)}) "
        flag_attr = (
            curses.A_REVERSE
            | curses.color_pair(CLR_HEADER)
        )
        stdscr.addstr(flags_y, x, flags_label, flag_attr)
        self._draw_flags(
            stdscr, flags_y + 2, x_inner,
            height - 8, active_flags,
        )

        # 3. Pool status
        pool_y = height - 7
        pool_attr = (
            curses.A_REVERSE
            | curses.color_pair(CLR_BORDER)
        )
        stdscr.addstr(pool_y, x, " POOLS ", pool_attr)

        eligible = self.engine.get_eligible_cards()
        sched_count = sum(
            len(v)
            for v in self.engine.state.schedule.values()
        )
        queue_len = len(self.engine.state.queue)

        stdscr.addstr(
            pool_y + 2, x_inner,
            f"Random    : {len(eligible)}",
        )
        stdscr.addstr(
            pool_y + 3, x_inner,
            f"Queue     : {queue_len}",
        )
        stdscr.addstr(
            pool_y + 4, x_inner,
            f"Scheduled : {sched_count}",
        )

    def _draw_flags(
        self, stdscr, start_y, x, max_y, active_flags,
    ):
        curr_y = start_y
        if not active_flags:
            stdscr.addstr(
                curr_y, x, "No active flags", curses.A_DIM,
            )
            return

        for f_id in active_flags:
            if curr_y >= max_y:
                stdscr.addstr(
                    curr_y, x, "...", curses.A_DIM,
                )
                break

            flag_def = self.engine.game.get_flag(f_id)
            name = flag_def.name if flag_def else f_id
            stdscr.addstr(
                curr_y, x,
                f"⚑ {name}",
                curses.color_pair(CLR_HEADER),
            )
            curr_y += 1

    def _draw_killer_stats(self, stdscr, y, x):
        stats = []
        for c_id, val in self.engine.state.counters.items():
            cdef = self.engine.game.get_counter(c_id)
            if cdef and cdef.killer:
                name = cdef.icon if cdef.icon else c_id
                name = name.replace('"', '').replace("'", "")
                stats.append(f"{name} {val}%")

        attr = curses.color_pair(CLR_KILLER) | curses.A_BOLD
        stdscr.addstr(y, x, "  ".join(stats), attr)

    def _draw_other_stats(self, stdscr, start_y, x):
        curr_y = start_y
        for c_id, val in self.engine.state.counters.items():
            cdef = self.engine.game.get_counter(c_id)
            if cdef and not cdef.killer:
                name = cdef.icon if cdef.icon else c_id
                name = name.replace('"', '').replace("'", "")
                stdscr.addstr(
                    curr_y, x,
                    f"• {name}: {val}",
                    curses.color_pair(CLR_STAT),
                )
                curr_y += 1

    def _format_command(self, cmd) -> str:
        if isinstance(cmd, CounterMod):
            return (
                f"{cmd.counter_id}"
                f" {self._format_value(cmd.value)}"
            )
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
        red = curses.color_pair(CLR_KILLER)

        for i in range(box_h):
            fill = "┃" + " " * (box_w - 2) + "┃"
            stdscr.addstr(y + i, x, fill, red)
        top = "┏" + "━" * (box_w - 2) + "┓"
        bot = "┗" + "━" * (box_w - 2) + "┛"
        stdscr.addstr(y, x, top, red)
        stdscr.addstr(y + box_h - 1, x, bot, red)

        go_attr = curses.A_REVERSE | curses.A_BOLD
        stdscr.addstr(
            y + 2, x + (box_w - 11) // 2,
            " GAME OVER ", go_attr,
        )
        reason = self.engine.state.game_over_reason
        reason = reason[:box_w - 6]
        stdscr.addstr(
            y + 4, x + (box_w - len(reason)) // 2, reason,
        )
        turns = (
            f"Total Duration:"
            f" {self.engine.state.current_turn} Turns"
        )
        stdscr.addstr(
            y + 5, x + (box_w - len(turns)) // 2, turns,
        )
        stdscr.addstr(
            y + 8, x + (box_w - 22) // 2,
            "Press any key to exit",
            curses.A_DIM,
        )
        stdscr.refresh()

    def _draw_error(self, stdscr, msg):
        attr = (
            curses.color_pair(CLR_KILLER) | curses.A_REVERSE
        )
        stdscr.addstr(10, 2, f" ERROR: {msg} ", attr)
        stdscr.refresh()


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
