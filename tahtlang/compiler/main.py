#!/usr/bin/env python3
"""
TahtLang CLI - Unified entry point for play, compile, and stats.
"""

import argparse
import atexit
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from tahtlang.compiler.serializer import (
    cards_to_taht,
    entities_to_taht,
    game_to_taht,
)
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
)
from tahtlang.parser.validator import (
    validate_game as validate_game_semantics,
)
from tahtlang.runtime.drivers import (
    AutoplayDriver,
    InteractiveDriver,
    SimulationDriver,
)

VERSION = "0.6.0"


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


_GITHUB_RE = re.compile(
    r"^https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$"
)


def resolve_input(input_path: str) -> str:
    """If input is a GitHub URL, clone to a temp dir and
    return the path to main.taht inside it.
    Otherwise return the input as-is."""
    m = _GITHUB_RE.match(input_path)
    if not m:
        return input_path

    repo_url = f"https://github.com/{m.group(1)}.git"
    parent = tempfile.mkdtemp(prefix="tahtlang_")
    atexit.register(shutil.rmtree, parent, ignore_errors=True)
    tmp = os.path.join(parent, "repo")

    print(f"[*] Cloning {m.group(1)}...")
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, tmp],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"\n[!] Clone failed: {result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Find main.taht — check root then one level deep
    root = Path(tmp)
    for candidate in [
        root / "main.taht",
        *root.glob("*/main.taht"),
    ]:
        if candidate.is_file():
            print(f"[*] Found {candidate.relative_to(root)}")
            return str(candidate)

    # No main.taht, look for any .taht file
    taht_files = list(root.glob("**/*.taht"))
    if len(taht_files) == 1:
        print(
            f"[*] Found {taht_files[0].relative_to(root)}"
        )
        return str(taht_files[0])

    if taht_files:
        print(
            "\n[!] No main.taht found. Available:",
            file=sys.stderr,
        )
        for f in taht_files:
            print(
                f"  - {f.relative_to(root)}",
                file=sys.stderr,
            )
    else:
        print(
            "\n[!] No .taht files found in repo.",
            file=sys.stderr,
        )
    sys.exit(1)


def load_game(filepath: str) -> Game:
    """Helper to parse and validate a game file.
    Accepts a local path or a GitHub URL."""
    filepath = resolve_input(filepath)
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


INIT_TEMPLATE = """\
# {name}
# A Reigns-style card game

# Settings
Game Settings (settings:main)
\tstarting_flags: [flag:start]

# Counters (hitting 0 or 100 ends the game)
Treasury (counter:treasury, killer)
Army (counter:army, killer)
People (counter:people, killer)
Church (counter:church, killer)

# Flags
Game Start (flag:start)
War Active (flag:war)

# Characters
Advisor (character:advisor)
General (character:general)
Priest (character:priest)
Merchant (character:merchant)

# Cards

Welcome (card:welcome)
\tbearer: character:advisor
\tweight: 100
\trequire: flag:start
\tlockturn: dispose
\t> Welcome to your kingdom, Your Majesty. Your reign begins now.
\t* I am ready: -flag:start, card:_first_decision

First Decision (card:_first_decision, ring)
\tbearer: character:advisor
\t> Your treasury needs attention. What shall we do?
\t* Raise taxes: counter:treasury 20, counter:people -10
\t* Cut spending: counter:treasury 10, counter:army -10

Tax Proposal (card:tax-proposal)
\tbearer: character:merchant
\tweight: 1.0
\tweight: 2.0 when counter:treasury < 30
\tlockturn: 10
\t> The merchants request lower taxes, Your Majesty.
\t* Lower taxes: counter:treasury -15, counter:people 10
\t* Keep current rates: counter:people -5

Military Request (card:military-request)
\tbearer: character:general
\tweight: 1.0
\tlockturn: 8
\t> We need more soldiers, Your Majesty.
\t* Recruit more: counter:army 15, counter:treasury -20
\t* The army is sufficient: counter:army -5

Church Donation (card:church-donation)
\tbearer: character:priest
\tweight: 1.0
\tlockturn: 12
\t> The church asks for your generous donation.
\t* Donate generously: counter:church 20, counter:treasury -25
\t* A modest gift: counter:church 5, counter:treasury -5
\t* Decline: counter:church -15

War Declaration (card:war-declaration)
\tbearer: character:general
\tweight: 0.5
\trequire: !flag:war, counter:army > 40
\tlockturn: 30
\t> A neighboring kingdom threatens our borders!
\t* Prepare for war: +flag:war, counter:army -10, card:_war_battle@5
\t* Seek peace: counter:treasury -30, counter:people 10

War Battle (card:_war_battle, ring)
\tbearer: character:general
\trequire: flag:war
\t> The battle rages on. What are your orders?
\t* Attack: counter:army -20?-10, [card:_war_victory, card:_war_defeat]
\t* Defend: counter:army -10, card:_war_stalemate

War Victory (card:_war_victory, ring)
\tbearer: character:general
\trequire: counter:army > 30
\t> We have won! The enemy retreats!
\t* Celebrate: -flag:war, counter:people 20, counter:treasury 30

War Defeat (card:_war_defeat, ring)
\tbearer: character:general
\trequire: counter:army <= 30
\t> We have lost the battle...
\t* Retreat: -flag:war, counter:army -20, counter:people -15

War Stalemate (card:_war_stalemate, ring)
\tbearer: character:general
\t> Neither side gains ground.
\t* Continue fighting: card:_war_battle@3
\t* Negotiate peace: -flag:war, counter:treasury -20
"""


def cmd_init(args):
    name = args.name
    filename = f"{name}.taht"
    filepath = os.path.join(os.getcwd(), filename)

    if os.path.exists(filepath):
        print(f"[!] '{filename}' already exists.", file=sys.stderr)
        sys.exit(1)

    content = INIT_TEMPLATE.format(name=name)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print_banner("Init")
    print(f"[OK] Created '{filename}'")
    print(f"\n  Play it:   tahtlang {filename}")
    print(f"  Test it:   tahtlang stats {filename}")
    print(f"  Compile:   tahtlang compile {filename}")


def cmd_merge(args):
    print_banner("Merge")
    game = load_game(args.input)

    output = game_to_taht(game)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[OK] Merged to '{args.output}'")
    else:
        print(output)


def cmd_split(args):
    print_banner("Split")
    game = load_game(args.input)

    input_path = Path(args.input)
    name = input_path.stem
    out_dir = Path(args.output) if args.output else Path(name)
    cards_dir = out_dir / "kartlar"
    cards_dir.mkdir(parents=True, exist_ok=True)

    # Group cards by bearer character
    by_char = defaultdict(list)
    no_bearer = []
    for card in game.cards:
        if card.bearer:
            by_char[card.bearer.character_id].append(card)
        else:
            no_bearer.append(card)

    # Write main.taht: entities + imports + bearer-less cards
    imports = []
    for char_id in sorted(by_char):
        imports.append(
            f'import "kartlar/{char_id}.taht"'
        )

    main_parts = [entities_to_taht(game)]
    if no_bearer:
        main_parts.append(
            "# Kartlar\n" + cards_to_taht(tuple(no_bearer))
        )
    main_parts.append("\n".join(imports) + "\n")

    main_path = out_dir / "main.taht"
    with open(main_path, "w", encoding="utf-8") as f:
        f.write("\n".join(main_parts))

    print(f"  {main_path}")

    # Write per-character card files
    for char_id in sorted(by_char):
        cards = by_char[char_id]
        char_def = game.get_character(char_id)
        title = char_def.name if char_def else char_id
        content = (
            f"# {title}\n\n"
            + cards_to_taht(tuple(cards))
        )
        fpath = cards_dir / f"{char_id}.taht"
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  {fpath} ({len(cards)} cards)")

    total = len(game.cards)
    files = len(by_char) + 1
    print(f"\n[OK] {total} cards -> {files} files")


def cmd_play(args):
    if getattr(args, "autoplay", False):
        print_banner("Autoplay")
        game = load_game(args.input)
        seed = getattr(args, "seed", None)
        driver = AutoplayDriver(
            game, max_turns=200, seed=seed,
        )
        driver.play()
        return

    print_banner("Interactive Mode")
    game = load_game(args.input)
    debug = getattr(args, "debug", False)
    driver = InteractiveDriver(game, debug=debug)
    try:
        driver.play()
    except KeyboardInterrupt:
        print(
            "\n\nExiting game..."
            " See you next time, Your Majesty!"
        )


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
    driver = SimulationDriver(game)
    runs = args.runs if args.runs is not None else 100

    total_cards = len(game.cards)
    ring_cards = sum(1 for c in game.cards if c.ring)
    pool_cards = total_cards - ring_cards
    print(
        f"[*] {total_cards} cards"
        f" ({pool_cards} pool + {ring_cards} ring)"
    )
    print(
        f"[*] Running {runs} simulations..."
        " (Patience, Your Majesty)"
    )
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
        print(
            "\n[Hint] Check if their 'require:'"
            " conditions are too strict."
        )
    print("\n" + "="*60 + "\n")


def main():
    desc = (
        "TahtLang CLI - A DSL for"
        " Reigns-style card games."
    )
    epilog = """\
Examples:
  tahtlang game.taht           # Play
  tahtlang init myproject      # Scaffold
  tahtlang stats game.taht     # Balance test
  tahtlang compile game.taht   # Export JSON

Docs: https://github.com/tahtlang/tahtlang
"""
    parser = argparse.ArgumentParser(
        description=desc,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands",
    )

    # tahtlang init [name]
    init_p = subparsers.add_parser(
        "init", help="Create a starter game",
    )
    init_p.add_argument(
        "name", nargs="?", default="game",
        help="Project name (default: game)",
    )
    init_p.set_defaults(func=cmd_init)

    # tahtlang compile <input> [-o output]
    comp_p = subparsers.add_parser(
        "compile", help="Compile to JSON",
    )
    comp_p.add_argument(
        "input", help="Source .taht file",
    )
    comp_p.add_argument(
        "-o", "--output", help="Output file path",
    )
    comp_p.add_argument(
        "--compact", action="store_true",
        help="Minify JSON output",
    )
    comp_p.set_defaults(func=cmd_compile)

    # tahtlang stats <input> [--runs N]
    stats_p = subparsers.add_parser(
        "stats", help="Run balance simulations",
    )
    stats_p.add_argument(
        "input", help="Source .taht file",
    )
    stats_p.add_argument(
        "--runs", type=int, default=100,
        help="Simulation count (default: 100)",
    )
    stats_p.set_defaults(func=cmd_stats)

    # tahtlang play <input> (or just tahtlang <input>)
    play_p = subparsers.add_parser(
        "play", help="Play in the terminal",
    )
    play_p.add_argument(
        "input", help="Source .taht file",
    )
    play_p.add_argument(
        "--debug", action="store_true",
        help="Show debug panels",
    )
    play_p.add_argument(
        "--autoplay", action="store_true",
        help="Auto-play with random choices (text output)",
    )
    play_p.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for autoplay reproducibility",
    )
    play_p.set_defaults(func=cmd_play)

    # tahtlang merge <input> [-o output]
    merge_p = subparsers.add_parser(
        "merge", help="Merge imports into one file",
    )
    merge_p.add_argument(
        "input", help="Source main.taht file",
    )
    merge_p.add_argument(
        "-o", "--output", help="Output file path",
    )
    merge_p.set_defaults(func=cmd_merge)

    # tahtlang split <input> [-o dir]
    split_p = subparsers.add_parser(
        "split", help="Split into per-character files",
    )
    split_p.add_argument(
        "input", help="Source .taht file",
    )
    split_p.add_argument(
        "-o", "--output",
        help="Output directory (default: game name)",
    )
    split_p.set_defaults(func=cmd_split)

    # If no arguments at all, print a custom welcoming help
    if len(sys.argv) == 1:
        print_banner("Welcome")
        parser.print_help()
        sys.exit(0)

    # If first argument is not a command, it's an implicit 'play' command
    args = sys.argv[1:]
    commands = [
        "init", "compile", "stats", "play",
        "merge", "split", "-h", "--help",
    ]
    if args and args[0] not in commands:
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
