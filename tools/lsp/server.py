"""
TahtLang Language Server.

Features:
- Diagnostics (parse errors, unknown references)
- Completion (characters, tags, metrics, variants, card IDs)
- Hover (show entity definitions)
- Go to Definition (jump to entity declaration)
"""

import sys
from pathlib import Path
from typing import Optional

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

# Add parent to path for imports
tools_dir = Path(__file__).parent.parent
sys.path.insert(0, str(tools_dir))

from parser import Parser, ParseError, validate_game
from parser.lexer import Lexer, LineType
from parser.ast import Game


class TahtaLanguageServer(LanguageServer):
    """Language server for TahtLang."""

    def __init__(self):
        super().__init__("tahta-lsp", "v0.1")
        # Cached game data per workspace
        self.games: dict[str, Game] = {}
        # Entity locations: {uri: {entity_id: (line, col)}}
        self.entity_locations: dict[str, dict[str, tuple[int, int]]] = {}

    def get_game(self, uri: str) -> Optional[Game]:
        """Get cached game for a document."""
        return self.games.get(uri)

    def parse_document(self, uri: str, source: str) -> list[lsp.Diagnostic]:
        """Parse document and return diagnostics."""
        diagnostics = []

        try:
            parser = Parser()
            game = parser.parse_string(source, uri)
            self.games[uri] = game

            # Build entity location index
            self._index_entities(uri, source, game)

            # Validate references
            diagnostics.extend(self._validate_references(uri, source, game))

        except ParseError as e:
            # Create diagnostic from parse error
            line = e.location.line - 1 if e.location else 0
            diagnostics.append(lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=line, character=0),
                    end=lsp.Position(line=line, character=100)
                ),
                message=e.message,
                severity=lsp.DiagnosticSeverity.Error,
                source="tahta"
            ))

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

    def _validate_references(self, uri: str, source: str, game: Game) -> list[lsp.Diagnostic]:
        """Validate references using the validator module."""
        diagnostics = []

        result = validate_game(game)
        for error in result.errors:
            # Get line number from error location
            line = error.location.line - 1 if error.location else 0

            diagnostics.append(lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=line, character=0),
                    end=lsp.Position(line=line, character=100)
                ),
                message=error.message,
                severity=lsp.DiagnosticSeverity.Error,
                source="tahta"
            ))

        return diagnostics

    def get_completions_at_position(self, uri: str, position: lsp.Position) -> list[lsp.CompletionItem]:
        """Get completion items at position."""
        document = self.workspace.get_text_document(uri)
        game = self.get_game(uri)

        if not game:
            return []

        try:
            line = document.lines[position.line]
        except IndexError:
            return []

        # Get text before cursor
        text_before = line[:position.character]
        stripped = text_before.lstrip()

        items = []

        # Build lookup dicts for easy access
        characters = {c.id: c for c in game.characters}
        variants = {v.id: v for v in game.variants}
        counters = {c.id: c for c in game.counters}
        flags = {f.id: f for f in game.flags}
        cards = {c.id: c for c in game.cards}

        # After "character:" suggest character IDs
        if 'character:' in stripped and not stripped.endswith('character:'):
            # Character already typed, check for variant
            after_char = stripped.split('character:')[-1].strip()
            if '(' in after_char or 'variant:' in after_char:
                # Inside parentheses or after variant:, suggest variants
                for variant_id, variant in variants.items():
                    items.append(lsp.CompletionItem(
                        label=f"variant:{variant_id}",
                        kind=lsp.CompletionItemKind.EnumMember,
                        detail=f"Variant: {variant.name}",
                        documentation=variant.prompt or None,
                        insert_text=f"variant:{variant_id}"
                    ))
        elif stripped.endswith('character:'):
            # Just typed "character:", suggest character IDs
            for char_id, char in characters.items():
                items.append(lsp.CompletionItem(
                    label=char_id,
                    kind=lsp.CompletionItemKind.Class,
                    detail=f"Karakter: {char.name}"
                ))

        # After "card:" suggest card IDs
        elif stripped.endswith('card:'):
            for card_id, card in cards.items():
                items.append(lsp.CompletionItem(
                    label=card_id,
                    kind=lsp.CompletionItemKind.Reference,
                    detail=f"Kart: {card.text[:50]}..." if card.text else "Kart"
                ))

        # After "counter:" or "+counter:" or "-counter:" suggest counter IDs
        elif stripped.endswith('counter:') or stripped.endswith('+counter:') or stripped.endswith('-counter:'):
            for counter_id, counter in counters.items():
                items.append(lsp.CompletionItem(
                    label=counter_id,
                    kind=lsp.CompletionItemKind.Variable,
                    detail=f"{counter.icon} {counter.name}"
                ))

        # After "flag:" or "+flag:" or "-flag:" or "!flag:" suggest flag IDs
        elif stripped.endswith('flag:') or stripped.endswith('+flag:') or stripped.endswith('-flag:') or stripped.endswith('!flag:'):
            for flag_id, flag in flags.items():
                items.append(lsp.CompletionItem(
                    label=flag_id,
                    kind=lsp.CompletionItemKind.Constant,
                    detail=f"Flag: {flag.name}"
                ))

        # After "variant:" suggest variant IDs
        elif stripped.endswith('variant:'):
            for variant_id, variant in variants.items():
                items.append(lsp.CompletionItem(
                    label=variant_id,
                    kind=lsp.CompletionItemKind.EnumMember,
                    detail=f"Variant: {variant.name}",
                    documentation=variant.prompt or None
                ))

        # In choice line, after colon suggest command prefixes
        elif stripped.startswith("*") and ":" in stripped:
            # Suggest counter operations
            items.append(lsp.CompletionItem(
                label="+counter:",
                kind=lsp.CompletionItemKind.Operator,
                detail="Counter artir",
                insert_text="+counter:"
            ))
            items.append(lsp.CompletionItem(
                label="-counter:",
                kind=lsp.CompletionItemKind.Operator,
                detail="Counter azalt",
                insert_text="-counter:"
            ))
            # Suggest flag operations
            items.append(lsp.CompletionItem(
                label="+flag:",
                kind=lsp.CompletionItemKind.Operator,
                detail="Flag ekle",
                insert_text="+flag:"
            ))
            items.append(lsp.CompletionItem(
                label="-flag:",
                kind=lsp.CompletionItemKind.Operator,
                detail="Flag kaldir",
                insert_text="-flag:"
            ))
            items.append(lsp.CompletionItem(
                label="card:",
                kind=lsp.CompletionItemKind.Reference,
                detail="Kart kuyruga ekle",
                insert_text="card:"
            ))

        # At line start, suggest entity headers
        elif position.character == 0 or stripped == "":
            items.extend([
                lsp.CompletionItem(
                    label="Kart (card:id)",
                    kind=lsp.CompletionItemKind.Snippet,
                    detail="Yeni kart",
                    insert_text="${1:Kart Adi} (card:${2:card-id})\n\tbearer: character:${3:character-id}\n\tweight: ${4:10}\n\t> ${5:Kart metni}\n\t* ${6:Evet}: +counter:${7:x} ${8:10}\n\t* ${9:Hayir}: -counter:${10:y} ${11:5}\n"
                ),
                lsp.CompletionItem(
                    label="Karakter (character:id)",
                    kind=lsp.CompletionItemKind.Snippet,
                    detail="Yeni karakter",
                    insert_text="${1:Karakter Adi} (character:${2:character-id})\n\tprompt: \"${3:gorsel tanim}\"\n"
                ),
                lsp.CompletionItem(
                    label="Counter (counter:id)",
                    kind=lsp.CompletionItemKind.Snippet,
                    detail="Yeni counter (killer)",
                    insert_text="${1:Counter Adi} (counter:${2:counter-id}, killer)\n\tstart: ${3:50}\n\ticon: ${4:coin.png}\n"
                ),
                lsp.CompletionItem(
                    label="Flag (flag:id)",
                    kind=lsp.CompletionItemKind.Snippet,
                    detail="Yeni flag",
                    insert_text="${1:Flag Adi} (flag:${2:flag-id})\n"
                ),
                lsp.CompletionItem(
                    label="Variant (variant:id)",
                    kind=lsp.CompletionItemKind.Snippet,
                    detail="Yeni variant (duygu, durum, poz)",
                    insert_text="${1:Variant Adi} (variant:${2:variant-id})\n\tprompt: \"${3:gorsel tanim}\"\n"
                ),
            ])

            # Also suggest property keys inside an entity
            items.extend([
                lsp.CompletionItem(label="bearer:", kind=lsp.CompletionItemKind.Property, detail="Karti sunan karakter"),
                lsp.CompletionItem(label="require:", kind=lsp.CompletionItemKind.Property, detail="Kartin havuzda olma kosullari"),
                lsp.CompletionItem(label="weight:", kind=lsp.CompletionItemKind.Property, detail="Cekilme agirligi"),
                lsp.CompletionItem(label="lockturn:", kind=lsp.CompletionItemKind.Property, detail="Cooldown (turn sayisi)"),
                lsp.CompletionItem(label="icon:", kind=lsp.CompletionItemKind.Property, detail="Ikon (emoji veya dosya)"),
                lsp.CompletionItem(label="prompt:", kind=lsp.CompletionItemKind.Property, detail="AI gorsel tanimi"),
                lsp.CompletionItem(label="bind:", kind=lsp.CompletionItemKind.Property, detail="Flag ile karakter baglama"),
            ])

        return items

    def get_hover_info(self, uri: str, position: lsp.Position) -> Optional[lsp.Hover]:
        """Get hover information at position."""
        document = self.workspace.get_text_document(uri)
        game = self.get_game(uri)

        if not game:
            return None

        word = document.word_at_position(position)
        if not word:
            return None

        # Build lookup dicts
        characters = {c.id: c for c in game.characters}
        variants = {v.id: v for v in game.variants}
        counters = {c.id: c for c in game.counters}
        flags = {f.id: f for f in game.flags}
        cards = {c.id: c for c in game.cards}

        # Check if it's a character
        if word in characters:
            char = characters[word]
            content = f"## Karakter: {char.name}\n\n"
            if char.prompt:
                content += f"Prompt: {char.prompt}\n"
            return lsp.Hover(
                contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=content
                )
            )

        # Check if it's a counter
        if word in counters:
            counter = counters[word]
            content = f"## {counter.icon} {counter.name}\n\n"
            content += f"Baslangic: {counter.start}"
            if counter.killer:
                content += "\n\n**Killer**: 0 veya 100'de oyun biter"
            return lsp.Hover(
                contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=content
                )
            )

        # Check if it's a variant
        if word in variants:
            variant = variants[word]
            content = f"## Variant: {variant.name}\n\n"
            if variant.prompt:
                content += f"Prompt: {variant.prompt}"
            return lsp.Hover(
                contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=content
                )
            )

        # Check if it's a flag
        if word in flags:
            flag = flags[word]
            content = f"## Flag: {flag.name}"
            if flag.bind:
                content += f"\n\nBind: {flag.bind}"
            return lsp.Hover(
                contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=content
                )
            )

        # Check if it's a card
        if word in cards:
            card = cards[word]
            content = f"## Kart: {word}\n\n"
            if card.bearer:
                content += f"Bearer: {card.bearer.character_id}"
                if card.bearer.variant_id:
                    content += f" ({card.bearer.variant_id})"
                content += "\n\n"
            if card.text:
                content += f"> {card.text[:100]}..."
            return lsp.Hover(
                contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=content
                )
            )

        return None

    def get_definition(self, uri: str, position: lsp.Position) -> Optional[lsp.Location]:
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
                    end=lsp.Position(line=line, character=col + len(word))
                )
            )

        return None


# Create server instance
server = TahtaLanguageServer()


# ============================================================================
# LSP Feature Handlers
# ============================================================================

@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: TahtaLanguageServer, params: lsp.DidOpenTextDocumentParams):
    """Handle document open."""
    uri = params.text_document.uri
    source = params.text_document.text

    diagnostics = ls.parse_document(uri, source)
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
    )


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: TahtaLanguageServer, params: lsp.DidChangeTextDocumentParams):
    """Handle document change."""
    uri = params.text_document.uri
    document = ls.workspace.get_text_document(uri)
    source = document.source

    diagnostics = ls.parse_document(uri, source)
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
    )


@server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(ls: TahtaLanguageServer, params: lsp.DidSaveTextDocumentParams):
    """Handle document save."""
    uri = params.text_document.uri
    document = ls.workspace.get_text_document(uri)
    source = document.source

    diagnostics = ls.parse_document(uri, source)
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
    )


@server.feature(
    lsp.TEXT_DOCUMENT_COMPLETION,
    lsp.CompletionOptions(
        trigger_characters=[':', '#', '>', '(', '-'],
        resolve_provider=False
    )
)
def completions(ls: TahtaLanguageServer, params: lsp.CompletionParams) -> lsp.CompletionList:
    """Provide completion items."""
    items = ls.get_completions_at_position(
        params.text_document.uri,
        params.position
    )
    return lsp.CompletionList(is_incomplete=False, items=items)


@server.feature(lsp.TEXT_DOCUMENT_HOVER)
def hover(ls: TahtaLanguageServer, params: lsp.HoverParams) -> Optional[lsp.Hover]:
    """Provide hover information."""
    return ls.get_hover_info(params.text_document.uri, params.position)


@server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
def definition(ls: TahtaLanguageServer, params: lsp.DefinitionParams) -> Optional[lsp.Location]:
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
