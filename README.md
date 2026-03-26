# TahtLang

A domain-specific language for creating Reigns-style card games.

> "Taht" means "throne" in Turkish.

## What is TahtLang?

TahtLang is a human-readable text format for defining card game content. Instead of complex JSON or visual editors, you write `.taht` files that are easy to read, version control, and edit with any text editor.

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
    > My Sultan, the treasury is running low.
    * Raise taxes: counter:hazine 20, counter:halk -15
    * Wait: counter:hazine -5
```

## Features

- **Vim-friendly syntax**: Line-based editing (dd, yy, p work naturally)
- **Type prefixes**: Explicit references (`counter:`, `flag:`, `card:`, etc.) for autocomplete
- **Tree-sitter grammar**: Syntax highlighting for any editor
- **LSP server**: Real-time diagnostics, completion, hover, go-to-definition
- **Validator**: Catch errors before runtime

## Installation

### Tree-sitter Grammar (for syntax highlighting)

```bash
cd grammar
npm install
npx tree-sitter generate
```

### Python Tools (parser, validator, LSP)

```bash
pip install -e .
```

## Usage

### Validate a file

```bash
$ tahtlang examples/minimal.taht --validate
OK Validation successful
  10 cards
  4 characters
  4 counters
  2 flags
```

### Parse and dump AST

```bash
$ tahtlang examples/tutorial.taht --dump-ast
```

### Start LSP server

```bash
$ python -m tahtlang.lsp
```

## Editor Support

### Neovim

1. Symlink the `vim/` directory into your Neovim runtime:

```bash
ln -s /path/to/tahtlang/vim ~/.config/nvim/after
```

2. Register the tree-sitter parser in your config:

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

- [`examples/minimal.taht`](examples/minimal.taht) - Quick start, minimal game
- [`examples/tutorial.taht`](examples/tutorial.taht) - Annotated tutorial with explanations

## Documentation

- [Syntax Reference](docs/spec/syntax.md) - Complete language specification

## Project Structure

```
tahtlang/
├── grammar/               # Tree-sitter grammar
│   ├── grammar.js         # Parser definition
│   └── queries/           # Syntax highlighting
│
├── tools/                 # Python toolchain
│   ├── parser/            # AST builder & validator
│   ├── compiler/          # CLI tools
│   └── lsp/               # Language Server
│
├── docs/
│   └── spec/              # Language specification
│
└── examples/              # Example .taht files
```

## License

MIT
