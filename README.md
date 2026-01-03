# TahtLang

A domain-specific language for creating Reigns-style card games.

> "Taht" means "throne" in Turkish.

## What is TahtLang?

TahtLang is a human-readable text format for defining card game content. Instead of complex JSON or visual editors, you write `.tahta` files that are easy to read, version control, and edit with any text editor.

```tahta
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
$ python -m tools.compiler examples/minimal.tahta --validate
OK Validation successful
  10 cards
  4 characters
  4 counters
  2 flags
```

### Parse and dump AST

```bash
$ python -m tools.compiler examples/tutorial.tahta --dump-ast
```

### Start LSP server

```bash
$ python -m tools.lsp
```

## Editor Support

### Neovim

Add to your tree-sitter config and point to the grammar directory.

### VS Code

Extension coming soon.

## Examples

- [`examples/minimal.tahta`](examples/minimal.tahta) - Quick start, minimal game
- [`examples/tutorial.tahta`](examples/tutorial.tahta) - Annotated tutorial with explanations

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
└── examples/              # Example .tahta files
```

## License

MIT
