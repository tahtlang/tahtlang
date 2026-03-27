# TahtLang

A domain-specific language for creating Reigns-style card games.

> "Taht" means "throne" in Turkish.

## What is TahtLang?

TahtLang is a text format for defining card game content. Instead of
JSON or visual editors, you write `.taht` files that are easy to read,
version control, and edit with any text editor.

```taht
# Define your game elements
Hazine (counter:hazine, killer)
Ordu (counter:ordu, killer)
Winter (flag:winter)
Vezir (character:vezir)

# Define cards
Tax Collection (card:tax-collection)
    bearer: character:vezir
    weight: 1.0
    weight: 2.0 when counter:hazine < 30
    require: !flag:winter
    lockturn: 10
    > My Sultan, the treasury is running low.
    * Raise taxes: counter:hazine 20, counter:halk -15
    * Wait: counter:hazine -5
```

## Features

- **Three CLI modes**: `play` (interactive terminal UI), `compile`
  (JSON export), `stats` (automated balance testing)
- **Conditional weights**: Cards appear more often based on game state
- **Card chains**: Queue, schedule, and branch cards for story arcs
- **Metadata**: Attach arbitrary key-value data to cards and characters
  for your runtime (images, sounds, moods — anything)
- **Imports**: Split large games across multiple `.taht` files
- **Virtual counters**: Aggregate or track other counters/characters
- **Vim-friendly syntax**: Line-based editing (`dd`, `yy`, `p`)
- **Type prefixes**: Explicit references (`counter:`, `flag:`, `card:`)
  for autocomplete and go-to-definition
- **Tree-sitter grammar**: Syntax highlighting for any editor
- **LSP server**: Real-time diagnostics, completion, hover,
  go-to-definition
- **Validator**: Catches undefined references, unreachable cards,
  circular dependencies, and deadlock conditions before runtime

## Installation

```bash
pip install -e .
```

### Tree-sitter Grammar (optional, for syntax highlighting)

```bash
cd grammar
npm install
npx tree-sitter generate
```

## Usage

### Play a game in the terminal

```bash
tahtlang examples/minimal.taht
# or explicitly:
tahtlang play examples/minimal.taht
```

Ncurses-based UI with counter bars, card text, choice selection,
and game state panel. Arrow keys to navigate, Enter to select,
`q` to quit.

### Compile to JSON

```bash
tahtlang compile game.taht -o game.json
tahtlang compile game.taht --compact    # minified
```

Exports the full game (settings, counters, flags, characters, cards)
as JSON for your game engine (Unity, Godot, Defold, web, etc.).

### Balance testing

```bash
tahtlang stats game.taht              # 100 simulations
tahtlang stats game.taht --runs 500   # more runs
```

Runs automated simulations with random choices and reports:
- Game over causes and their frequency
- Average game duration
- Card frequency (how often each card appears)
- Unreachable content alerts (cards never shown)

### Validate

```bash
tahtlang compile game.taht > /dev/null
```

Validation runs automatically before play, compile, or stats.
Errors are reported with file and line number.

### Start LSP server

```bash
python -m tahtlang.lsp
```

## Language Overview

See [Syntax Reference](docs/spec/syntax.md) for the complete
specification. Quick summary:

### Entities

```taht
Game Settings (settings:main)
    starting_flags: [flag:start]

Treasury (counter:treasury, killer)   # killer = game over at 0 or 100
Cathedral (counter:cathedral, keep)   # keep = persists across reigns

War Active (flag:war)
Plague (flag:plague, keep)

Angry (variant:angry)                 # character emotion/state

Advisor (character:advisor)
    meta.portrait: advisor.png        # free-form metadata
```

### Cards

```taht
Tax Proposal (card:tax)
    bearer: character:advisor (variant:worried)
    weight: 1.0
    weight: 2.0 when counter:treasury < 30
    require: !flag:war, counter:people > 20
    lockturn: 10
    meta.image: tax_scroll.png
    > The merchants request lower taxes, Your Majesty.
    * Lower taxes: counter:treasury -15, counter:people 10
    * Keep rates: counter:people -5
    * Raise taxes: counter:treasury 20, counter:people -20, +flag:unrest
```

### Ring cards (story chains)

```taht
Battle (card:_battle, ring)
    bearer: character:general
    require: flag:war
    > The battle rages on!
    * Attack: counter:army -15, [card:_victory, card:_defeat]
    * Retreat: -flag:war, counter:army -10
```

Ring cards never appear in the random pool — they only show when
queued by another card via `card:id`, `card:id@N` (scheduled),
or `[card:a, card:b]` (branch).

### Metadata

Cards and characters support free-form `meta.*` properties:

```taht
Advisor (character:advisor)
    meta.portrait: advisor_portrait.png
    meta.voice: deep

Empty Vault (card:_go_vault, ring)
    meta.image: empty_vault.png
    meta.mood: dark
    meta.sound: vault_echo.ogg
    > The royal vaults echo with emptiness.
    * ...
```

TahtLang passes metadata through to JSON output without validation.
Your runtime decides what to do with it.

### Imports

```taht
import "characters.taht"
import "story/chapter1.taht"
```

## Editor Support

### Neovim

1. Symlink the `vim/` directory:

```bash
ln -s /path/to/tahtlang/vim ~/.config/nvim/after
```

2. Register the tree-sitter parser:

```lua
local parser_config = require(
  "nvim-treesitter.parsers"
).get_parser_configs()

parser_config.taht = {
  install_info = {
    url = "/path/to/tahtlang/grammar",
    files = { "src/parser.c" },
  },
  filetype = "taht",
}
```

3. Add LSP config:

```lua
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

### VS Code

Extension coming soon.

## Examples

- [`examples/minimal.taht`](examples/minimal.taht) — Playable minimal
  game with war storyline
- [`examples/manager.taht`](examples/manager.taht) — Full game with
  multiple story arcs
- [`examples/tutorial.taht`](examples/tutorial.taht) — Annotated
  tutorial with explanations

## Project Structure

```
tahtlang/
├── grammar/               # Tree-sitter grammar
│   ├── grammar.js
│   └── queries/           # Syntax highlighting queries
│
├── tahtlang/              # Python package
│   ├── parser/            # Lexer, parser, validator
│   ├── compiler/          # CLI (play, compile, stats)
│   ├── runtime/           # Game engine + drivers
│   └── lsp/               # Language Server Protocol
│
├── docs/spec/             # Language specification
└── examples/              # Example .taht files
```

## License

MIT
