# TahtLang

Reigns-style card game DSL. Python toolchain (lexer → parser → validator → compiler) + Tree-sitter grammar for Vim syntax highlighting.

## Run

```bash
python -m tools.compiler examples/minimal.tahta --validate
python -m tools.compiler game.tahta --pretty
python -m pytest tests/
```

## Code Style

- **79-character line limit.** No exceptions. Code goes down, not right.
- **No deep nesting.** If indentation reaches 4+ levels, flatten with early returns, guard clauses, or extract a method.
- **No string comparisons for known values.** Use enums. If a value comes from a fixed set (entity types, modifiers, aggregate types), it must be an enum, not a string.
- **Dict lookup over elif chains.** If you're mapping strings to values (aggregate names → enum, lockturn keywords → constants), use a dict, not if/elif.
- **One method, one job.** If a method dispatches by type/prefix, split: dispatcher picks the type, sub-method does the work. No 80-line if chains.
- **No silent failures.** Unknown property? Unknown command? Invalid value? Raise an error. Never return None and silently skip.
- **Normalize early.** If a value needs lowercasing or stripping, do it once at the boundary (lexer), not repeatedly in the consumer (parser).
- **Tests are public API only.** Test through `parse_string`, `validate_game`, `game_to_dict`. Never test private methods directly — this gives freedom to refactor internals.
