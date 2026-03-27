#!/usr/bin/env python3
"""
TahtLang CLI - Unified entry point for play, compile, and stats.
"""

import argparse
import json
import sys
from typing import Optional

from tahtlang.parser import ParseError
from tahtlang.parser.ast import (
    Bearer,
    Card,
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
from tahtlang.parser.validator import (
    resolve_imports,
    validate_game as validate_game_semantics,
)

VERSION = "0.2.0"


def print_banner(command_name: str):
    """Print a stylish banner for the CLI."""
    print(f"\n{'='*60}")
    print(f" TAHTLANG v{VERSION} | {command_name.upper()}")
    print(f"{'='*60}")


def value_to_dict(val):
    if isinstance(val, FixedValue):
        return {"type": "fixed", "value": val.value}
    elif isinstance(val, RangeValue):
        return {"type": "range", "min": val.min_value, "max": val.max_value}
    raise ValueError(f"Unknown value type: {type(val)}")


def command_to_dict(cmd) -> dict:
    if isinstance(cmd, CounterMod):
        return {
            "type": "counter_mod",
            "counter": cmd.counter_id,
            "value": value_to_dict(cmd.value),
        }
    if isinstance(cmd, FlagSet):
        return {"type": "flag_set", "flag": cmd.flag_id}
    if isinstance(cmd, FlagClear):
        return {"type": "flag_clear", "flag": cmd.flag_id}
    if isinstance(cmd, CardQueue):
        return {"type": "card_queue", "card": cmd.card_id}
    if isinstance(cmd, CardBranch):
        return {"type": "card_branch", "cards": list(cmd.card_ids)}
    if isinstance(cmd, CardTimed):
        return {"type": "card_timed", "card": cmd.card_id, "delay": cmd.delay}
    if isinstance(cmd, Trigger):
        return {
            "type": "trigger",
            "trigger_type": cmd.trigger_type.value,
            "value": cmd.value,
        }
    raise ValueError(f"Unknown command type: {type(cmd)}")


def condition_to_dict(cond) -> dict:
    if isinstance(cond, FlagCondition):
        return {"type": "flag", "flag": cond.flag_id, "negated": cond.negated}
    if isinstance(cond, CounterCondition):
        return {
            "type": "counter",
            "counter": cond.counter_id,
            "operator": cond.operator.value,
            "value": cond.value,
        }
    raise ValueError(f"Unknown condition type: {type(cond)}")


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


def character_to_dict(c) -> dict:
    d = {"id": c.id, "name": c.name, "prompt": c.prompt}
    if c.meta:
        d["meta"] = meta_to_dict(c.meta)
    return d


def meta_to_dict(
    meta: tuple[tuple[str, str], ...],
) -> dict:
    return {k: v for k, v in meta}


def card_to_dict(c: Card) -> dict:
    d = {
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
    if c.meta:
        d["meta"] = meta_to_dict(c.meta)
    return d


def game_to_dict(game: Game) -> dict:
    settings_dict = {}
    if game.settings:
        settings_dict = {
            "name": game.settings.name,
            "description": game.settings.description,
            "starting_flags": list(game.settings.starting_flags),
            "game_over_on_zero": game.settings.game_over_on_zero,
            "game_over_on_max": game.settings.game_over_on_max,
        }

    return {
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
                "source": list(c.source) if c.source else None,
                "aggregate": c.aggregate.name.lower() if c.aggregate else None,
                "track": c.track.name.lower() if c.track else None,
            }
            for c in game.counters
        },
        "flags": {
            f.id: {"id": f.id, "name": f.name, "bind": f.bind, "keep": f.keep}
            for f in game.flags
        },
        "variants": {
            v.id: {"id": v.id, "name": v.name, "prompt": v.prompt}
            for v in game.variants
        },
        "characters": {
            c.id: character_to_dict(c)
            for c in game.characters
        },
        "cards": {c.id: card_to_dict(c) for c in game.cards},
    }


def load_game(filepath: str) -> Game:
    """Helper to parse and validate a game file."""
    try:
        game, import_result = resolve_imports(filepath)
        if not import_result.is_valid:
            print("\n[!] Import Resolution Failed:", file=sys.stderr)
            for err in import_result.errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)
        
        result = validate_game_semantics(game)
        if not result.is_valid:
            print("\n[!] Validation Failed:", file=sys.stderr)
            for err in result.errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)
            
        return game
    except (ParseError, FileNotFoundError) as e:
        print(f"\n[!] Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_play(args):
    print_banner("Interactive Mode")
    game = load_game(args.input)
    from tahtlang.runtime.drivers import InteractiveDriver

    driver = InteractiveDriver(game)
    try:
        driver.play()
    except KeyboardInterrupt:
        print("\n\nExiting game... See you next time, Your Majesty!")


def cmd_compile(args):
    print_banner("Compiler")
    game = load_game(args.input)
    
    print(f"[*] Processing entities from '{args.input}'...")
    print(f"  - Cards: {len(game.cards)}")
    print(f"  - Characters: {len(game.characters)}")
    print(f"  - Counters: {len(game.counters)}")
    print(f"  - Flags: {len(game.flags)}")

    data = game_to_dict(game)
    indent = None if args.compact else 2
    json_str = json.dumps(data, ensure_ascii=False, indent=indent)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"\n[OK] Successfully compiled to: {args.output}")
    else:
        print("\n" + json_str)


def cmd_stats(args):
    print_banner("Balancing Analysis")
    game = load_game(args.input)
    
    from tahtlang.runtime.drivers import SimulationDriver
    driver = SimulationDriver(game)
    runs = args.runs if args.runs is not None else 100
    
    print(f"[*] Running {runs} automated simulations... (Patience, Your Majesty)")
    report = driver.run_simulations(count=runs)
    counts = report["card_counts"]

    print("\n[1] GAME OVER SUMMARY")
    print("-" * 30)
    # Sort reasons by count descending to show the "top killers" first
    reasons = report["game_over_reasons"].items()
    sorted_reasons = sorted(
        reasons, key=lambda x: x[1], reverse=True,
    )
    for reason, count in sorted_reasons:
        percent = (count / runs) * 100
        print(f" {reason:<22} | {count:>3} ({percent:>4.1f}%)")
    
    print(f"\n[*] Average game duration: {report['avg_turns']:.1f} turns")

    print("\n[2] CARD FREQUENCY ANALYSIS")
    print("-" * 50)
    sorted_counts = sorted(
        counts.items(), key=lambda x: x[1], reverse=True,
    )
    print(f"{'Card ID':<30} | {'Total Hits':<10} | {'Hits/Run'}")
    print("-" * 50)
    for card_id, count in sorted_counts:
        avg_hits = count / runs
        print(f"{card_id:<30} | {count:<10} | {avg_hits:>7.2f}")

    zero_cards = [cid for cid, c in counts.items() if c == 0]
    if zero_cards:
        print("\n[!] UNREACHABLE CONTENT ALERT")
        print("The following cards were never shown"
              " during the simulation:")
        for cid in zero_cards:
            print(f"  - {cid}")
        print("\n[Hint] Check if their 'require:' conditions are too strict.")
    print("\n" + "="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="TahtLang CLI - A domain-specific language for Reigns-style card games.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tahtlang game.taht              # Play the game in your terminal
  tahtlang stats game.taht        # Run 100 simulations and see card frequency
  tahtlang compile game.taht      # Compile to JSON for your game engine
  tahtlang stats game.taht --runs 500  # Run more simulations for better balancing

Documentation:
  https://github.com/tahtlang/tahtlang
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # tahtlang compile <input> [-o output]
    comp_p = subparsers.add_parser("compile", help="Compile .taht files into a JSON game data")
    comp_p.add_argument("input", help="The source .taht file to compile")
    comp_p.add_argument("-o", "--output", help="Save the JSON output to a specific file")
    comp_p.add_argument("--compact", action="store_true", help="Minimize the JSON output size")
    comp_p.set_defaults(func=cmd_compile)

    # tahtlang stats <input> [--runs N]
    stats_p = subparsers.add_parser("stats", help="Run automated simulations to test game balance")
    stats_p.add_argument("input", help="The .taht file to analyze")
    stats_p.add_argument(
        "--runs", type=int, default=100, help="How many times to simulate the game (default: 100)"
    )
    stats_p.set_defaults(func=cmd_stats)

    # tahtlang play <input> (or just tahtlang <input>)
    play_p = subparsers.add_parser("play", help="Play the game directly in the terminal")
    play_p.add_argument("input", help="The .taht file to play")
    play_p.set_defaults(func=cmd_play)

    # If no arguments at all, print a custom welcoming help
    if len(sys.argv) == 1:
        print_banner("Welcome")
        parser.print_help()
        sys.exit(0)

    # If first argument is not a command, it's an implicit 'play' command
    args = sys.argv[1:]
    if args and args[0] not in ["compile", "stats", "play", "-h", "--help"]:
        # Insert 'play' as the first argument if it's likely a filename
        if not args[0].startswith("-"):
            args.insert(0, "play")

    parsed_args = parser.parse_args(args)

    if hasattr(parsed_args, "func"):
        parsed_args.func(parsed_args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
