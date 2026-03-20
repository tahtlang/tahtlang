"""
TahtLang Language Server.

Features:
- Diagnostics (parse errors, unknown references)
- Completion (characters, tags, metrics, variants, card IDs)
- Hover (show entity definitions)
- Go to Definition (jump to entity declaration)
"""

from typing import Optional

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from tools.parser import ParseError, Parser, validate_game
from tools.parser.ast import Game
from tools.parser.lexer import Lexer, LineType


class TahtaLanguageServer(LanguageServer):
    """Language server for TahtLang."""

    def __init__(self):
        super().__init__("tahta-lsp", "v0.1")
        # Cached game data per workspace
        self.games: dict[str, Game] = {}
        # Entity lookup dicts: {uri: {"characters": {...}, ...}}
        self.entity_dicts: dict[str, dict[str, dict]] = {}
        # Entity locations: {uri: {entity_id: (line, col)}}
        self.entity_locations: dict[str, dict[str, tuple[int, int]]] = {}

    def get_game(self, uri: str) -> Optional[Game]:
        """Get cached game for a document."""
        return self.games.get(uri)

    @staticmethod
    def _make_diagnostic(line: int, message: str) -> lsp.Diagnostic:
        """Create a diagnostic object."""
        return lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=line, character=0),
                end=lsp.Position(line=line, character=79),
            ),
            message=message,
            severity=lsp.DiagnosticSeverity.Error,
            source="tahta",
        )

    def parse_document(self, uri: str, source: str) -> list[lsp.Diagnostic]:
        """Parse document and return diagnostics."""
        diagnostics = []

        try:
            parser = Parser()
            game = parser.parse_string(source, uri)
            self.games[uri] = game

            # Cache entity lookups
            self.entity_dicts[uri] = {
                "characters": {c.id: c for c in game.characters},
                "variants": {v.id: v for v in game.variants},
                "counters": {c.id: c for c in game.counters},
                "flags": {f.id: f for f in game.flags},
                "cards": {c.id: c for c in game.cards},
            }

            # Build entity location index
            self._index_entities(uri, source, game)

            # Validate references
            diagnostics.extend(self._validate_references(uri, source, game))

        except ParseError as e:
            # Create diagnostic from parse error
            line = e.location.line - 1 if e.location else 0
            diagnostics.append(self._make_diagnostic(line, e.message))

        return diagnostics

    def _index_entities(self, uri: str, source: str, game: Game):
        """Build index of entity locations for go-to-definition."""
        locations: dict[str, tuple[int, int]] = {}

        lexer = Lexer(source, uri)
        for line in lexer:
            if line.type == LineType.ENTITY_HEADER and line.entity_id:
                # Store 0-based line number
                locations[line.entity_id] = (line.line_number - 1, 0)

        self.entity_locations[uri] = locations

    def _validate_references(
        self, uri: str, source: str, game: Game
    ) -> list[lsp.Diagnostic]:
        """Validate references using the validator module."""
        diagnostics = []

        result = validate_game(game)
        for error in result.errors:
            # Get line number from error location
            line = error.location.line - 1 if error.location else 0
            diagnostics.append(self._make_diagnostic(line, error.message))

        return diagnostics

    def get_completions_at_position(
        self, uri: str, position: lsp.Position
    ) -> list[lsp.CompletionItem]:
        """Get completion items at position."""
        document = self.workspace.get_text_document(uri)
        game = self.get_game(uri)

        if not game or uri not in self.entity_dicts:
            return []

        try:
            line = document.lines[position.line]
        except IndexError:
            return []

        # Get text before cursor
        text_before = line[: position.character]
        stripped = text_before.lstrip()

        # Use cached lookup dicts
        dicts = self.entity_dicts[uri]
        return self._build_completion_items(stripped, position, dicts)

    def _build_completion_items(self, stripped: str, position, dicts):
        """Build completion items based on context."""
        items = []

        # After "character:" suggest character IDs
        if "character:" in stripped and not stripped.endswith("character:"):
            items.extend(self._suggest_variants(stripped, dicts["variants"]))
        elif stripped.endswith("character:"):
            items.extend(
                self._suggest_ids(
                    dicts["characters"],
                    lsp.CompletionItemKind.Class,
                    "Character",
                )
            )

        # After "card:" suggest card IDs
        elif stripped.endswith("card:"):
            items.extend(
                self._suggest_ids(
                    dicts["cards"], lsp.CompletionItemKind.Reference, "Card"
                )
            )

        # After "counter:" or "+counter:" or "-counter:" suggest counter IDs
        elif any(
            stripped.endswith(s)
            for s in ("counter:", "+counter:", "-counter:")
        ):
            items.extend(
                self._suggest_ids(
                    dicts["counters"], lsp.CompletionItemKind.Variable, ""
                )
            )

        # After "flag:" or "+flag:" or "-flag:" or "!flag:" suggest flag IDs
        elif any(
            stripped.endswith(s)
            for s in ("flag:", "+flag:", "-flag:", "!flag:")
        ):
            items.extend(
                self._suggest_ids(
                    dicts["flags"], lsp.CompletionItemKind.Constant, "Flag"
                )
            )

        # After "variant:" suggest variant IDs
        elif stripped.endswith("variant:"):
            items.extend(
                self._suggest_ids(
                    dicts["variants"],
                    lsp.CompletionItemKind.EnumMember,
                    "Variant",
                )
            )

        # In choice line, after colon suggest command prefixes
        elif stripped.startswith("*") and ":" in stripped:
            items.extend(self._suggest_command_prefixes())

        # At line start, suggest entity headers
        elif position.character == 0 or stripped == "":
            items.extend(self._suggest_snippets())
            items.extend(self._suggest_properties())

        return items

    def _suggest_variants(self, stripped, variants):
        items = []
        after_char = stripped.split("character:")[-1].strip()
        if "(" in after_char or "variant:" in after_char:
            for v_id, v in variants.items():
                items.append(
                    lsp.CompletionItem(
                        label=f"variant:{v_id}",
                        kind=lsp.CompletionItemKind.EnumMember,
                        detail=f"Variant: {v.name}",
                        documentation=v.prompt or None,
                        insert_text=f"variant:{v_id}",
                    )
                )
        return items

    def _suggest_ids(self, entities, kind, detail_prefix):
        items = []
        for e_id, e in entities.items():
            detail = f"{detail_prefix}: {e.name}" if detail_prefix else e.name
            if hasattr(e, "icon") and e.icon:
                detail = f"{e.icon} {e.name}"
            
            items.append(
                lsp.CompletionItem(
                    label=e_id,
                    kind=kind,
                    detail=detail,
                )
            )
        return items

    def _suggest_command_prefixes(self):
        return [
            lsp.CompletionItem(
                label="+counter:",
                kind=lsp.CompletionItemKind.Operator,
                detail="Increase counter",
                insert_text="+counter:",
            ),
            lsp.CompletionItem(
                label="-counter:",
                kind=lsp.CompletionItemKind.Operator,
                detail="Decrease counter",
                insert_text="-counter:",
            ),
            lsp.CompletionItem(
                label="+flag:",
                kind=lsp.CompletionItemKind.Operator,
                detail="Set flag",
                insert_text="+flag:",
            ),
            lsp.CompletionItem(
                label="-flag:",
                kind=lsp.CompletionItemKind.Operator,
                detail="Clear flag",
                insert_text="-flag:",
            ),
            lsp.CompletionItem(
                label="card:",
                kind=lsp.CompletionItemKind.Reference,
                detail="Queue card",
                insert_text="card:",
            ),
        ]

    def _suggest_snippets(self):
        return [
            lsp.CompletionItem(
                label="Card (card:id)",
                kind=lsp.CompletionItemKind.Snippet,
                detail="New card",
                insert_text=(
                    "${1:Card Name} (card:${2:card_id})\n"
                    "\tbearer: character:${3:character_id}\n"
                    "\tweight: ${4:10}\n"
                    "\t> ${5:Card text}\n"
                    "\t* ${6:Yes}: counter:${7:x} ${8:10}\n"
                    "\t* ${9:No}: counter:${10:y} ${11:-5}\n"
                ),
            ),
            lsp.CompletionItem(
                label="Character (character:id)",
                kind=lsp.CompletionItemKind.Snippet,
                detail="New character",
                insert_text=(
                    "${1:Character Name} "
                    "(character:${2:character_id})\n"
                    '\tprompt: "${3:visual description}"\n'
                ),
            ),
            lsp.CompletionItem(
                label="Counter (counter:id)",
                kind=lsp.CompletionItemKind.Snippet,
                detail="New counter (killer)",
                insert_text=(
                    "${1:Counter Name} "
                    "(counter:${2:counter_id}, killer)\n"
                    "\tstart: ${3:50}\n"
                    "\ticon: ${4:coin.png}\n"
                ),
            ),
            lsp.CompletionItem(
                label="Flag (flag:id)",
                kind=lsp.CompletionItemKind.Snippet,
                detail="New flag",
                insert_text="${1:Flag Name} (flag:${2:flag_id})\n",
            ),
            lsp.CompletionItem(
                label="Variant (variant:id)",
                kind=lsp.CompletionItemKind.Snippet,
                detail="New variant (emotion, state, pose)",
                insert_text=(
                    "${1:Variant Name} (variant:${2:variant_id})\n"
                    '\tprompt: "${3:visual description}"\n'
                ),
            ),
        ]

    def _suggest_properties(self):
        return [
            lsp.CompletionItem(
                label="bearer:",
                kind=lsp.CompletionItemKind.Property,
                detail="Card bearer character",
            ),
            lsp.CompletionItem(
                label="require:",
                kind=lsp.CompletionItemKind.Property,
                detail="Conditions for card to appear in pool",
            ),
            lsp.CompletionItem(
                label="weight:",
                kind=lsp.CompletionItemKind.Property,
                detail="Draw weight",
            ),
            lsp.CompletionItem(
                label="lockturn:",
                kind=lsp.CompletionItemKind.Property,
                detail="Cooldown (turn count)",
            ),
            lsp.CompletionItem(
                label="icon:",
                kind=lsp.CompletionItemKind.Property,
                detail="Icon (emoji or file)",
            ),
            lsp.CompletionItem(
                label="prompt:",
                kind=lsp.CompletionItemKind.Property,
                detail="AI visual description",
            ),
            lsp.CompletionItem(
                label="bind:",
                kind=lsp.CompletionItemKind.Property,
                detail="Bind flag to character",
            ),
        ]

    def get_hover_info(
        self, uri: str, position: lsp.Position
    ) -> Optional[lsp.Hover]:
        """Get hover information at position."""
        document = self.workspace.get_text_document(uri)
        game = self.get_game(uri)

        if not game or uri not in self.entity_dicts:
            return None

        word = document.word_at_position(position)
        if not word:
            return None

        dicts = self.entity_dicts[uri]
        
        # Check through entities
        if word in dicts["characters"]:
            return self._hover_character(dicts["characters"][word])
        if word in dicts["counters"]:
            return self._hover_counter(dicts["counters"][word])
        if word in dicts["variants"]:
            return self._hover_variant(dicts["variants"][word])
        if word in dicts["flags"]:
            return self._hover_flag(dicts["flags"][word])
        if word in dicts["cards"]:
            return self._hover_card(word, dicts["cards"][word])

        return None

    def _hover_character(self, char):
        content = f"## Character: {char.name}\n\n"
        if char.prompt:
            content += f"Prompt: {char.prompt}\n"
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown, value=content
            )
        )

    def _hover_counter(self, counter):
        content = f"## {counter.icon} {counter.name}\n\n"
        content += f"Start: {counter.start}"
        if counter.killer:
            content += "\n\n**Killer**: game over at 0 or 100"
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown, value=content
            )
        )

    def _hover_variant(self, variant):
        content = f"## Variant: {variant.name}\n\n"
        if variant.prompt:
            content += f"Prompt: {variant.prompt}"
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown, value=content
            )
        )

    def _hover_flag(self, flag):
        content = f"## Flag: {flag.name}"
        if flag.bind:
            content += f"\n\nBind: {flag.bind}"
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown, value=content
            )
        )

    def _hover_card(self, word, card):
        content = f"## Card: {word}\n\n"
        if card.bearer:
            content += f"Bearer: {card.bearer.character_id}"
            if card.bearer.variant_id:
                content += f" ({card.bearer.variant_id})"
            content += "\n\n"
        if card.text:
            content += f"> {card.text[:100]}..."
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown, value=content
            )
        )

    def get_definition(
        self, uri: str, position: lsp.Position
    ) -> Optional[lsp.Location]:
        """Get definition location for symbol at position."""
        document = self.workspace.get_text_document(uri)
        word = document.word_at_position(position)

        if not word:
            return None

        locations = self.entity_locations.get(uri, {})
        if word in locations:
            line, col = locations[word]
            return lsp.Location(
                uri=uri,
                range=lsp.Range(
                    start=lsp.Position(line=line, character=col),
                    end=lsp.Position(line=line, character=col + len(word)),
                ),
            )

        return None


# Create server instance
server = TahtaLanguageServer()


# ============================================================================
# LSP Feature Handlers
# ============================================================================


def _publish_diagnostics(ls: TahtaLanguageServer, uri: str, source: str):
    """Common logic for diagnostic publishing."""
    diagnostics = ls.parse_document(uri, source)
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
    )


@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: TahtaLanguageServer, params: lsp.DidOpenTextDocumentParams):
    """Handle document open."""
    uri = params.text_document.uri
    source = params.text_document.text
    _publish_diagnostics(ls, uri, source)


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(
    ls: TahtaLanguageServer, params: lsp.DidChangeTextDocumentParams
):
    """Handle document change."""
    uri = params.text_document.uri
    document = ls.workspace.get_text_document(uri)
    _publish_diagnostics(ls, uri, document.source)


@server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(ls: TahtaLanguageServer, params: lsp.DidSaveTextDocumentParams):
    """Handle document save."""
    uri = params.text_document.uri
    document = ls.workspace.get_text_document(uri)
    _publish_diagnostics(ls, uri, document.source)


@server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls: TahtaLanguageServer, params: lsp.DidCloseTextDocumentParams):
    """Handle document close - clean up cached data."""
    uri = params.text_document.uri
    ls.games.pop(uri, None)
    ls.entity_dicts.pop(uri, None)
    ls.entity_locations.pop(uri, None)


@server.feature(
    lsp.TEXT_DOCUMENT_COMPLETION,
    lsp.CompletionOptions(
        trigger_characters=[":", "#", ">", "(", "-"], resolve_provider=False
    ),
)
def completions(
    ls: TahtaLanguageServer, params: lsp.CompletionParams
) -> lsp.CompletionList:
    """Provide completion items."""
    items = ls.get_completions_at_position(
        params.text_document.uri, params.position
    )
    return lsp.CompletionList(is_incomplete=False, items=items)


@server.feature(lsp.TEXT_DOCUMENT_HOVER)
def hover(
    ls: TahtaLanguageServer, params: lsp.HoverParams
) -> Optional[lsp.Hover]:
    """Provide hover information."""
    return ls.get_hover_info(params.text_document.uri, params.position)


@server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
def definition(
    ls: TahtaLanguageServer, params: lsp.DefinitionParams
) -> Optional[lsp.Location]:
    """Go to definition."""
    return ls.get_definition(params.text_document.uri, params.position)


# ============================================================================
# Entry Point
# ============================================================================


def main():
    """Start the language server."""
    server.start_io()


if __name__ == "__main__":
    main()
