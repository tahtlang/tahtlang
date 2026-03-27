# TahtLang

Write card games in plain text. Play them in the terminal. Export to JSON for Unity, Godot, or your own engine.

> *"Taht"* means *"throne"* in Turkish.

<!-- TODO: Add a GIF/screenshot of `tahtlang play` here -->

## Why?

If you've played [Reigns](https://reignsgame.com/reigns/), you know the format: a character shows up, says something, you pick left or right. Four stats go up and down. You die. You try again.

The game logic isn't complex. The content is. A Reigns-style game needs hundreds of cards with interconnected conditions, branching storylines, and careful stat balancing. Managing all that in JSON, a spreadsheet, or a visual editor is painful.

TahtLang is a text format designed for this. You write `.taht` files:

```taht
Tax Proposal (card:tax)
	bearer: character:advisor
	weight: 1.0
	weight: 3.0 when counter:treasury < 20
	lockturn: 10
	> The merchants request lower taxes, Your Majesty.
	* Lower taxes: counter:treasury -15, counter:people 10
	* Raise taxes: counter:treasury 20, counter:people -20

War Declaration (card:war)
	bearer: character:general
	weight: 0.5
	require: !flag:war, counter:army > 40
	> Enemies threaten our borders!
	* Go to war: +flag:war, counter:army -10, card:_battle@5
	* Seek peace: counter:treasury -30
```

Then:

```bash
tahtlang game.taht           # Play it right now in your terminal
tahtlang stats game.taht     # Simulate 100 games, find balance issues
tahtlang compile game.taht   # Export JSON for your game engine
```

## What you get

**As a game designer**, you get a text format that lets you write cards fast, version control everything with git, and catch mistakes before runtime. The validator tells you when you reference a flag that doesn't exist, a character you never defined, or a card that can never appear.

**As a game developer**, you get a clean JSON export with everything you need: counters, flags, characters, cards, conditions, weights, metadata. Parse it in Unity, Godot, Defold, Love2D, a web app — whatever your engine is.

**As both**, you get `tahtlang stats` which simulates hundreds of games and shows you which cards never appear, which counters cause the most deaths, and how long an average game lasts.

## Quick start

```bash
pip install tahtlang
tahtlang init                # Creates game.taht with a playable starter game
tahtlang game.taht           # Play it
```

Or grab a binary from [releases](https://github.com/tahtlang/tahtlang/releases) — no Python needed.

## How it works

A `.taht` file defines **entities** and **cards**:

```taht
# Four stats — hitting 0 or 100 kills you
Treasury (counter:treasury, killer)
Army (counter:army, killer)
People (counter:people, killer)
Faith (counter:faith, killer)

# Characters present cards
Advisor (character:advisor)
General (character:general)
```

Cards have **weights** (how often they appear), **conditions** (when they can appear), and **choices** (what the player can do):

```taht
Plague (card:plague)
	bearer: character:advisor
	weight: 0.3
	weight: 2.0 when counter:people > 80
	require: !flag:plague_active
	lockturn: 30
	> A terrible plague spreads through the kingdom.
	* Quarantine the city: counter:people -20, counter:treasury -10, +flag:plague_active
	* Pray: counter:faith 15, counter:people -30
```

Cards can **chain** into story arcs:

```taht
Battle (card:_battle, ring)
	bearer: character:general
	require: flag:war
	> The battle rages!
	* Attack: counter:army -15, [card:_victory, card:_defeat]
	* Retreat: -flag:war, counter:army -5

Victory (card:_victory, ring)
	require: counter:army > 30
	> We won!
	* Celebrate: -flag:war, counter:people 20, counter:treasury 30

Defeat (card:_defeat, ring)
	require: counter:army <= 30
	> We lost...
	* Retreat: -flag:war, counter:army -20, counter:people -15
```

Attach any data your engine needs with **metadata**:

```taht
Advisor (character:advisor)
	meta.portrait: advisor.png
	meta.voice: deep

Plague (card:plague)
	meta.image: plague_city.png
	meta.sound: coughing.ogg
	meta.mood: dark
```

TahtLang doesn't care what metadata you attach — it passes it through to JSON for your runtime.

## Balance testing

```
$ tahtlang stats game.taht --runs 500

[1] GAME OVER SUMMARY
------------------------------
 Treasury hit 0         | 187 (37.4%)
 People hit 0           | 143 (28.6%)
 Army hit 100           |  98 (19.6%)
 Faith hit 0            |  72 (14.4%)

[*] Average game duration: 24.3 turns

[2] CARD FREQUENCY ANALYSIS
--------------------------------------------------
Card ID                        | Total Hits | Hits/Run
--------------------------------------------------
tax-proposal                   | 1847       |    3.69
military-request               | 1203       |    2.41
plague                         | 423        |    0.85
_battle                        | 0          |    0.00

[!] UNREACHABLE CONTENT ALERT
  - _battle

[Hint] Check if their 'require:' conditions are too strict.
```

## JSON output

```bash
tahtlang compile game.taht -o game.json
```

```json
{
  "counters": {
    "treasury": {"id": "treasury", "name": "Treasury", "start": 50, "killer": true}
  },
  "cards": {
    "plague": {
      "id": "plague",
      "bearer": {"character": "advisor"},
      "text": "A terrible plague spreads through the kingdom.",
      "weights": [{"value": 0.3}, {"value": 2.0, "condition": {"counter": "people", "operator": ">", "value": 80}}],
      "require": [{"type": "flag", "flag": "plague_active", "negated": true}],
      "choices": [
        {"label": "Quarantine the city", "commands": [...]},
        {"label": "Pray", "commands": [...]}
      ],
      "meta": {"image": "plague_city.png", "sound": "coughing.ogg", "mood": "dark"}
    }
  }
}
```

Parse this in your engine. The structure is stable and documented in the [syntax reference](docs/spec/syntax.md).

## Editor support

TahtLang has a **Tree-sitter grammar** for syntax highlighting and an **LSP server** for diagnostics, completion, and go-to-definition.

### Neovim

```bash
ln -s /path/to/tahtlang/vim ~/.config/nvim/after
```

```lua
-- Tree-sitter parser
local parser_config = require("nvim-treesitter.parsers").get_parser_configs()
parser_config.taht = {
  install_info = {
    url = "/path/to/tahtlang/grammar",
    files = { "src/parser.c" },
  },
  filetype = "taht",
}

-- LSP
vim.api.nvim_create_autocmd("FileType", {
  pattern = "taht",
  callback = function()
    vim.lsp.start({
      name = "tahtlang-lsp",
      cmd = { "python", "-m", "tahtlang.lsp" },
      root_dir = vim.fn.getcwd(),
    })
  end,
})
```

## Examples

```bash
tahtlang init                       # scaffold a starter game
tahtlang examples/minimal.taht     # play the included demo
```

[`examples/minimal.taht`](examples/minimal.taht) is a small playable kingdom game. [`examples/tutorial.taht`](examples/tutorial.taht) has annotated explanations of every feature.

## Full documentation

- [Syntax Reference](docs/spec/syntax.md) — complete language specification
- `tahtlang init` — scaffold a new game
- `tahtlang --help` — all CLI options

## Install

```bash
pip install tahtlang
```

Or via Homebrew:

```bash
brew tap tahtlang/tahtlang
brew install tahtlang
```

Or grab a binary from [GitHub Releases](https://github.com/tahtlang/tahtlang/releases).

## License

MIT
