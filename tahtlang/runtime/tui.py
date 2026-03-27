"""
Textual TUI for TahtLang play mode.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Collapsible,
    Footer,
    Label,
    OptionList,
    Static,
)

from ..parser.ast import Choice, Game
from .drivers import _format_command
from .engine import GameEngine


class CounterStat(Static):
    """Killer counter displayed as 'Name: 42'."""

    ANIM_INTERVAL = 0.05
    DEFAULT_CSS = """
    CounterStat {
        width: auto;
        height: 1;
        margin: 0 2 0 0;
        text-style: bold;
    }
    CounterStat.danger {
        color: $error;
    }
    CounterStat.warning {
        color: $warning;
    }
    CounterStat.safe {
        color: $success;
    }
    """

    def __init__(self, name: str, counter_id: str):
        super().__init__(f"{name}: 50")
        self.counter_name = name
        self.counter_id = counter_id
        self._display_val = 50
        self._target_val = 50
        self._timer = None

    def set_value(self, val: int):
        self._target_val = val
        if self._timer is None and self._display_val != val:
            self._timer = self.set_interval(
                self.ANIM_INTERVAL, self._tick,
            )

    def _tick(self):
        if self._display_val < self._target_val:
            self._display_val += 1
            self._set_color("safe")
        elif self._display_val > self._target_val:
            self._display_val -= 1
            self._set_color("danger")

        self.update(
            f"{self.counter_name}: {self._display_val}",
        )

        if self._display_val == self._target_val:
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
            self._set_resting_color(self._display_val)

    def _set_resting_color(self, val: int):
        if val <= 20 or val >= 80:
            self._set_color("danger")
        elif val <= 40 or val >= 60:
            self._set_color("warning")
        else:
            self._set_color("safe")

    def _set_color(self, cls: str):
        self.set_classes(cls)


class DebugPanel(VerticalScroll):
    """Docked right sidebar with collapsible sections."""

    DEFAULT_CSS = """
    DebugPanel {
        dock: right;
        width: 32;
        height: 1fr;
        border-left: solid $primary-lighten-3;
        padding: 1 0;
    }
    DebugPanel Static {
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Collapsible(title="Counters", collapsed=False):
            yield Static("", id="dbg-counters")
        with Collapsible(title="Flags", collapsed=False):
            yield Static("", id="dbg-flags")
        with Collapsible(title="Pools", collapsed=False):
            yield Static("", id="dbg-pools")
        with Collapsible(title="Effects", collapsed=False):
            yield Static("", id="dbg-effects")

    def refresh_state(self, engine, card, selected):
        self._refresh_counters(engine)
        self._refresh_flags(engine)
        self._refresh_pools(engine)
        self._refresh_effects(card, selected)

    def _refresh_counters(self, engine):
        lines = []
        for c_id, val in engine.state.counters.items():
            cdef = engine.game.get_counter(c_id)
            if cdef and not cdef.killer:
                name = cdef.name or c_id
                lines.append(f"{name}: {val}")
        self.query_one(
            "#dbg-counters", Static,
        ).update("\n".join(lines) or "-")

    def _refresh_flags(self, engine):
        flags = sorted(engine.state.flags)
        if not flags:
            self.query_one(
                "#dbg-flags", Static,
            ).update("(none)")
            return
        lines = []
        for f_id in flags:
            fdef = engine.game.get_flag(f_id)
            name = fdef.name if fdef else f_id
            lines.append(f"* {name}")
        self.query_one(
            "#dbg-flags", Static,
        ).update("\n".join(lines))

    def _refresh_pools(self, engine):
        eligible = engine.get_eligible_cards()
        sched = sum(
            len(v)
            for v in engine.state.schedule.values()
        )
        queue = len(engine.state.queue)
        self.query_one(
            "#dbg-pools", Static,
        ).update(
            f"Random : {len(eligible)}\n"
            f"Queue  : {queue}\n"
            f"Sched  : {sched}"
        )

    def _refresh_effects(self, card, selected):
        widget = self.query_one(
            "#dbg-effects", Static,
        )
        if not card or not card.choices:
            widget.update("-")
            return
        chosen = card.choices[selected]
        lines = [
            _format_command(cmd)
            for cmd in chosen.commands
        ]
        widget.update("\n".join(lines) or "-")


class TahtApp(App):
    """TahtLang interactive game player."""

    CSS = """
    Screen {
        padding: 1 0 0 0;
    }

    #top-bar {
        dock: top;
        height: 1;
        padding: 0 2;
    }

    #card-panel {
        height: 1fr;
        padding: 1 2;
    }

    #bearer-label {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #card-text {
        margin-bottom: 1;
    }

    #choices {
        margin: 1 0 0 0;
        height: auto;
        max-height: 12;
        padding: 0;
        border: none;
    }

    #no-choices {
        margin-top: 1;
        color: $text-muted;
    }

    #game-over-box {
        align: center middle;
        width: 100%;
        height: 100%;
    }

    #game-over-inner {
        width: 50;
        height: auto;
        border: round $error;
        padding: 1 2;
    }

    #game-over-inner Label {
        width: 100%;
        text-align: center;
    }

    .go-title {
        text-style: bold reverse;
        margin-bottom: 1;
    }

    .go-counters {
        text-style: bold;
        margin-top: 1;
    }

    .go-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self, game: Game, debug: bool = False,
    ):
        super().__init__()
        self.engine = GameEngine(game)
        self.debug_mode = debug
        self.current_card = None

    def compose(self) -> ComposeResult:
        yield Horizontal(id="top-bar")
        if self.debug_mode:
            yield DebugPanel(id="debug-panel")
        with Vertical(id="card-panel"):
            yield Label("", id="bearer-label")
            yield Static("", id="card-text")
            yield OptionList(id="choices")
        yield Footer()

    def on_mount(self):
        self._build_counter_bars()
        self._next_card()

    def _build_counter_bars(self):
        top = self.query_one("#top-bar")
        for c_id in self.engine.state.counters:
            cdef = self.engine.game.get_counter(c_id)
            if cdef and cdef.killer:
                name = cdef.name or c_id
                top.mount(CounterStat(name, c_id))

    # ── Game flow ───────────────────────────────────

    def _next_card(self):
        if self.engine.state.is_game_over:
            self._show_game_over()
            return
        card = self.engine.pick_next_card()
        if not card:
            self._show_game_over()
            return
        self.current_card = card
        self._refresh_ui()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected,
    ):
        card = self.current_card
        if not card:
            return
        if card.choices:
            idx = event.option_index
            if 0 <= idx < len(card.choices):
                chosen = card.choices[idx]
                self.engine.apply_choice(card, chosen)
        else:
            self.engine.apply_choice(
                card, Choice(label=""),
            )
        self._next_card()

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted,
    ):
        if not self.debug_mode:
            return
        self._refresh_debug(event.option_index)

    # ── UI refresh ──────────────────────────────────

    def _refresh_ui(self):
        card = self.current_card
        if not card:
            return
        self._refresh_bearer(card)
        self._refresh_card_text(card)
        self._refresh_choices(card)
        self._refresh_counters()
        self._refresh_title(card)
        if self.debug_mode:
            self._refresh_debug(0)

    def _refresh_bearer(self, card):
        label = self.query_one("#bearer-label", Label)
        if not card.bearer:
            label.update("")
            return
        char = self.engine.game.get_character(
            card.bearer.character_id,
        )
        name = (
            char.name if char
            else card.bearer.character_id
        )
        variant = ""
        if card.bearer.variant_id:
            variant = f" ({card.bearer.variant_id})"
        label.update(f"{name}{variant}")

    def _refresh_card_text(self, card):
        self.query_one("#card-text", Static).update(
            card.text,
        )

    def _refresh_choices(self, card):
        option_list = self.query_one(
            "#choices", OptionList,
        )
        option_list.clear_options()
        if card.choices:
            for c in card.choices:
                option_list.add_option(c.label)
            option_list.highlighted = 0
            option_list.display = True
            option_list.focus()
        else:
            option_list.add_option(
                "Press Enter to continue"
            )
            option_list.highlighted = 0
            option_list.display = True
            option_list.focus()

    def _refresh_counters(self):
        for bar in self.query(CounterStat):
            val = self.engine.state.counters.get(
                bar.counter_id, 0,
            )
            bar.set_value(val)

    def _refresh_title(self, card):
        turn = self.engine.state.current_turn
        self.title = f"Turn {turn}"
        self.sub_title = card.name

    def _refresh_debug(self, selected_idx):
        self.query_one(DebugPanel).refresh_state(
            self.engine, self.current_card, selected_idx,
        )

    # ── Game over ───────────────────────────────────

    def _show_game_over(self):
        self.current_card = None

        finals = []
        for c_id, val in self.engine.state.counters.items():
            cdef = self.engine.game.get_counter(c_id)
            if cdef and cdef.killer:
                name = cdef.name or c_id
                finals.append(f"{name} {val}%")

        reason = (
            self.engine.state.game_over_reason
            or "Pool exhausted"
        )
        turns = self.engine.state.current_turn

        panel = self.query_one("#card-panel")
        panel.remove_children()

        inner = Vertical(id="game-over-inner")
        panel.mount(Vertical(inner, id="game-over-box"))
        inner.mount(Label(
            "GAME OVER", classes="go-title",
        ))
        inner.mount(Label(reason))
        inner.mount(Label(f"Duration: {turns} turns"))
        inner.mount(Label(
            "  ".join(finals), classes="go-counters",
        ))
        inner.mount(Label(
            "Press q to exit", classes="go-hint",
        ))

        self.title = "Game Over"
        self.sub_title = reason
