"""
Serialize Game AST back to .taht format.
"""

from tahtlang.parser.ast import (
    CardBranch,
    CardQueue,
    CardTimed,
    CounterCondition,
    CounterMod,
    FixedValue,
    FlagClear,
    FlagCondition,
    FlagSet,
    Game,
    RangeValue,
    Trigger,
)


def game_to_taht(game: Game) -> str:
    """Serialize full game to .taht format."""
    parts = []
    parts.append(_serialize_settings(game.settings))
    parts.append(_serialize_counters(game.counters))
    parts.append(_serialize_flags(game.flags))
    parts.append(_serialize_variants(game.variants))
    parts.append(
        _serialize_characters(game.characters)
    )
    parts.append(_serialize_cards(game.cards))
    return "\n".join(p for p in parts if p)


def entities_to_taht(game: Game) -> str:
    """Serialize only entities (no cards)."""
    parts = []
    parts.append(_serialize_settings(game.settings))
    parts.append(_serialize_counters(game.counters))
    parts.append(_serialize_flags(game.flags))
    parts.append(_serialize_variants(game.variants))
    parts.append(
        _serialize_characters(game.characters)
    )
    return "\n".join(p for p in parts if p)


def cards_to_taht(cards: tuple) -> str:
    """Serialize a list of cards."""
    return _serialize_cards(cards)


# ── Settings ────────────────────────────────────

def _serialize_settings(settings):
    if not settings:
        return ""
    lines = [
        f"{settings.name} (settings:{settings.id})"
    ]
    if settings.description:
        lines.append(
            f'\tdescription: "{settings.description}"'
        )
    if settings.starting_flags:
        flags = ", ".join(
            f"flag:{f}" for f in settings.starting_flags
        )
        lines.append(f"\tstarting_flags: [{flags}]")
    if not settings.game_over_on_zero:
        lines.append("\tgame_over_on_zero: false")
    if not settings.game_over_on_max:
        lines.append("\tgame_over_on_max: false")
    return "\n".join(lines) + "\n"


# ── Counters ────────────────────────────────────

def _serialize_counters(counters):
    if not counters:
        return ""
    parts = []
    for c in counters:
        parts.append(_serialize_counter(c))
    return "\n".join(parts) + "\n"


def _serialize_counter(c):
    mods = []
    if c.killer:
        mods.append("killer")
    if c.keep:
        mods.append("keep")
    mod_str = ", ".join(mods)
    if mod_str:
        mod_str = ", " + mod_str
    lines = [f"{c.name} (counter:{c.id}{mod_str})"]
    if not c.is_virtual:
        lines.append(f"\tstart: {c.start}")
    if c.icon:
        lines.append(f"\ticon: {c.icon}")
    if c.color:
        lines.append(f"\tcolor: {c.color}")
    if c.source:
        refs = ", ".join(c.source)
        lines.append(f"\tsource: [{refs}]")
    if c.aggregate:
        lines.append(
            f"\taggregate: {c.aggregate.name.lower()}"
        )
    if c.track:
        lines.append(
            f"\ttrack: {c.track.name.lower()}"
        )
    return "\n".join(lines) + "\n"


# ── Flags ───────────────────────────────────────

def _serialize_flags(flags):
    if not flags:
        return ""
    parts = []
    for f in flags:
        mod = ", keep" if f.keep else ""
        line = f"{f.name} (flag:{f.id}{mod})"
        if f.bind:
            line += f"\n\tbind: character:{f.bind}"
        parts.append(line)
    return "\n".join(parts) + "\n"


# ── Variants ────────────────────────────────────

def _serialize_variants(variants):
    if not variants:
        return ""
    parts = []
    for v in variants:
        line = f"{v.name} (variant:{v.id})"
        if v.prompt:
            line += f'\n\tprompt: "{v.prompt}"'
        parts.append(line)
    return "\n".join(parts) + "\n"


# ── Characters ──────────────────────────────────

def _serialize_characters(characters):
    if not characters:
        return ""
    parts = []
    for c in characters:
        lines = [f"{c.name} (character:{c.id})"]
        if c.prompt:
            lines.append(f'\tprompt: "{c.prompt}"')
        for k, v in c.meta:
            lines.append(f"\tmeta.{k}: {v}")
        parts.append("\n".join(lines))
    return "\n".join(parts) + "\n"


# ── Cards ───────────────────────────────────────

def _serialize_cards(cards):
    if not cards:
        return ""
    parts = []
    for c in cards:
        parts.append(_serialize_card(c))
    return "\n".join(parts)


def _serialize_card(c):
    lines = [_card_header(c)]
    _card_properties(c, lines)
    _card_choices(c, lines)
    return "\n".join(lines) + "\n"


def _card_header(c):
    mod_str = ", ring" if c.ring else ""
    return f"{c.name} (card:{c.id}{mod_str})"


def _card_properties(c, lines):
    if c.bearer:
        bearer = f"character:{c.bearer.character_id}"
        if c.bearer.variant_id:
            bearer += (
                f" (variant:{c.bearer.variant_id})"
            )
        lines.append(f"\tbearer: {bearer}")

    for w in c.weights:
        lines.append(f"\tweight: {_format_weight(w)}")

    if c.require:
        conds = ", ".join(
            _format_condition(r) for r in c.require
        )
        lines.append(f"\trequire: {conds}")

    if c.lockturn is not None:
        lines.append(f"\tlockturn: {c.lockturn}")

    for k, v in c.meta:
        lines.append(f"\tmeta.{k}: {v}")

    if c.text:
        lines.append(f"\t> {c.text}")


def _card_choices(c, lines):
    for ch in c.choices:
        cmds = ", ".join(
            _format_command(cmd) for cmd in ch.commands
        )
        if cmds:
            lines.append(f"\t* {ch.label}: {cmds}")
        else:
            lines.append(f"\t* {ch.label}:")


# ── Conditions ──────────────────────────────────

def _format_condition(cond):
    if isinstance(cond, FlagCondition):
        prefix = "!" if cond.negated else ""
        return f"{prefix}flag:{cond.flag_id}"
    if isinstance(cond, CounterCondition):
        return (
            f"counter:{cond.counter_id}"
            f" {cond.operator.value} {cond.value}"
        )
    raise ValueError(f"Unknown condition: {type(cond)}")


# ── Weights ─────────────────────────────────────

def _format_weight(w):
    val = str(w.value)
    if w.value == int(w.value):
        val = str(int(w.value))
    else:
        val = str(w.value)
    if w.condition:
        cond = _format_condition(w.condition)
        return f"{val} when {cond}"
    return val


# ── Commands ────────────────────────────────────

def _format_command(cmd):
    if isinstance(cmd, CounterMod):
        return (
            f"counter:{cmd.counter_id}"
            f" {_format_value(cmd.value)}"
        )
    if isinstance(cmd, FlagSet):
        return f"+flag:{cmd.flag_id}"
    if isinstance(cmd, FlagClear):
        return f"-flag:{cmd.flag_id}"
    if isinstance(cmd, CardQueue):
        return f"card:{cmd.card_id}"
    if isinstance(cmd, CardTimed):
        return f"card:{cmd.card_id}@{cmd.delay}"
    if isinstance(cmd, CardBranch):
        refs = ", ".join(
            f"card:{cid}" for cid in cmd.card_ids
        )
        return f"[{refs}]"
    if isinstance(cmd, Trigger):
        return (
            f'trigger:{cmd.trigger_type.value}'
            f' "{cmd.value}"'
        )
    raise ValueError(f"Unknown command: {type(cmd)}")


def _format_value(val):
    if isinstance(val, FixedValue):
        return str(val.value)
    if isinstance(val, RangeValue):
        return f"{val.min_value}?{val.max_value}"
    raise ValueError(f"Unknown value: {type(val)}")
