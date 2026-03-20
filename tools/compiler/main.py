#!/usr/bin/env python3
"""
TahtLang Compiler CLI

Usage:
    python -m compiler game.tahta              # Output to stdout
    python -m compiler game.tahta -o game.json # Output to file
    python -m compiler game.tahta --validate   # Only validate, no output
"""

import argparse
import json
import sys

from tools.parser import ParseError
from tools.parser.ast import (
    Bearer,
    CardBranch,
    CardQueue,
    CardTimed,
    Choice,
    CounterCondition,
    CounterMod,
    FixedValue,
    FlagClear,
    FlagCondition,
    FlagSet,
    Game,
    RangeValue,
    Trigger,
    Weight,
)
from tools.parser.validator import (
    resolve_imports,
)
from tools.parser.validator import (
    validate_game as validate_game_semantics,
)


def game_to_dict(game: Game) -> dict:
    """Convert Game AST to a JSON-serializable dict."""

    def value_to_dict(val):
        if isinstance(val, FixedValue):
            return {"type": "fixed", "value": val.value}
        elif isinstance(val, RangeValue):
            return {
                "type": "range",
                "min": val.min_value,
                "max": val.max_value,
            }
        return None

    def command_to_dict(cmd) -> dict:
        if isinstance(cmd, CounterMod):
            return {
                "type": "counter_mod",
                "counter": cmd.counter_id,
                "value": value_to_dict(cmd.value),
            }
        elif isinstance(cmd, FlagSet):
            return {"type": "flag_set", "flag": cmd.flag_id}
        elif isinstance(cmd, FlagClear):
            return {"type": "flag_clear", "flag": cmd.flag_id}
        elif isinstance(cmd, CardQueue):
            return {"type": "card_queue", "card": cmd.card_id}
        elif isinstance(cmd, CardBranch):
            return {"type": "card_branch", "cards": list(cmd.card_ids)}
        elif isinstance(cmd, CardTimed):
            return {
                "type": "card_timed",
                "card": cmd.card_id,
                "delay": cmd.delay,
            }
        elif isinstance(cmd, Trigger):
            return {
                "type": "trigger",
                "trigger_type": cmd.trigger_type,
                "value": cmd.value,
            }
        return {}

    def condition_to_dict(cond) -> dict:
        if isinstance(cond, FlagCondition):
            return {
                "type": "flag",
                "flag": cond.flag_id,
                "negated": cond.negated,
            }
        elif isinstance(cond, CounterCondition):
            return {
                "type": "counter",
                "counter": cond.counter_id,
                "operator": cond.operator,
                "value": cond.value,
            }
        return {}

    def choice_to_dict(choice: Choice) -> dict:
        return {
            "label": choice.label,
            "commands": [command_to_dict(c) for c in choice.commands],
        }

    def weight_to_dict(w: Weight) -> dict:
        d = {"value": w.value}
        if w.condition:
            d["condition"] = condition_to_dict(w.condition)
        return d

    def bearer_to_dict(b: Bearer) -> dict:
        d = {"character": b.character_id}
        if b.variant_id:
            d["variant"] = b.variant_id
        return d

    # Build settings
    settings_dict = {}
    if game.settings:
        settings_dict = {
            "name": game.settings.name,
            "description": game.settings.description,
            "starting_flags": list(game.settings.starting_flags),
            "game_over_on_zero": game.settings.game_over_on_zero,
            "game_over_on_max": game.settings.game_over_on_max,
        }

    result = {
        "settings": settings_dict,
        "counters": {
            c.id: {
                "id": c.id,
                "name": c.name,
                "icon": c.icon,
                "start": c.start,
                "color": c.color,
                "killer": c.killer,
                "keep": c.keep,
                # Virtual counter fields
                "source": list(c.source) if c.source else None,
                "aggregate": c.aggregate.name.lower() if c.aggregate else None,
                "track": c.track.name.lower() if c.track else None,
            }
            for c in game.counters
        },
        "flags": {
            f.id: {
                "id": f.id,
                "name": f.name,
                "bind": f.bind,
                "keep": f.keep,
            }
            for f in game.flags
        },
        "variants": {
            v.id: {
                "id": v.id,
                "name": v.name,
                "prompt": v.prompt,
            }
            for v in game.variants
        },
        "characters": {
            c.id: {
                "id": c.id,
                "name": c.name,
                "prompt": c.prompt,
            }
            for c in game.characters
        },
        "cards": {
            c.id: {
                "id": c.id,
                "name": c.name,
                "bearer": bearer_to_dict(c.bearer) if c.bearer else None,
                "text": c.text,
                "require": [condition_to_dict(r) for r in c.require],
                "weights": [weight_to_dict(w) for w in c.weights],
                "lockturn": c.lockturn,
                "ring": c.ring,
                "choices": [choice_to_dict(ch) for ch in c.choices],
            }
            for c in game.cards
        },
    }

    return result


def main():
    arg_parser = argparse.ArgumentParser(
        description="TahtLang Compiler - compiles .tahta files to JSON"
    )
    arg_parser.add_argument("input", help="Input .tahta file")
    arg_parser.add_argument("-o", "--output", help="Output JSON file")
    arg_parser.add_argument(
        "--validate", action="store_true", help="Validate only, no output"
    )
    arg_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON (default)"
    )
    arg_parser.add_argument(
        "--compact", action="store_true", help="Compact JSON"
    )

    args = arg_parser.parse_args()

    # Parse with import resolution
    try:
        game, import_result = resolve_imports(args.input)
        if not import_result.is_valid:
            print("Import errors:", file=sys.stderr)
            for err in import_result.errors:
                print(f"  {err}", file=sys.stderr)
            sys.exit(1)
        result = validate_game_semantics(game)

    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate
    if not result.is_valid:
        print("Validation errors:", file=sys.stderr)
        for err in result.errors:
            print(f"  {err}", file=sys.stderr)
        sys.exit(1)

    if args.validate:
        print("OK Validation passed")
        print(f"  {len(game.cards)} cards")
        print(f"  {len(game.characters)} characters")
        print(f"  {len(game.counters)} counters")
        print(f"  {len(game.flags)} flags")
        sys.exit(0)

    # Convert to JSON
    data = game_to_dict(game)
    indent = None if args.compact else 2
    json_str = json.dumps(data, ensure_ascii=False, indent=indent)

    # Output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"OK Written to {args.output}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
