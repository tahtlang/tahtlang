"""
Line-based lexer for TahtLang.

TahtLang is line-oriented, so we don't need traditional tokenization.
Instead, we classify each line by its type and extract relevant parts.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, Optional

from .ast import SourceLocation


class LineType(Enum):
    """Types of lines in TahtLang."""

    EMPTY = auto()
    COMMENT = auto()
    # import "path/to/file.tahta"
    IMPORT = auto()
    # Name (type, id, ...flags)
    ENTITY_HEADER = auto()
    # key: value
    PROPERTY = auto()
    # starts with whitespace (for weight blocks)
    INDENTED = auto()
    # > value (card text)
    PRIMARY_VALUE = auto()
    # * label: commands
    CHOICE = auto()


class EntityType(Enum):
    """Entity types in TahtLang."""

    SETTINGS = "settings"
    COUNTER = "counter"
    FLAG = "flag"
    VARIANT = "variant"
    CHARACTER = "character"
    CARD = "card"


# Lookup: string -> EntityType (for header detection)
ENTITY_TYPE_MAP: dict[str, EntityType] = {e.value: e for e in EntityType}


class Modifier(Enum):
    """Entity modifiers in TahtLang."""

    KILLER = "killer"
    KEEP = "keep"
    RING = "ring"


# Lookup: string -> Modifier
MODIFIER_MAP: dict[str, Modifier] = {m.value: m for m in Modifier}


@dataclass
class Line:
    """A parsed line with metadata."""

    type: LineType
    raw: str
    line_number: int
    indent: int = 0

    # Extracted parts (depending on type)
    import_path: Optional[str] = None  # for IMPORT: "path/to/file.tahta"
    entity_name: Optional[str] = None  # for ENTITY_HEADER: "Yeniceri Ağası"
    entity_type: Optional[EntityType] = (
        None  # for ENTITY_HEADER: EntityType.CHARACTER
    )
    entity_id: Optional[str] = None  # for ENTITY_HEADER: "yeniceri_agasi"
    entity_modifiers: Optional[set[Modifier]] = (
        None  # for ENTITY_HEADER: {Modifier.KILLER}
    )
    key: Optional[str] = None  # for PROPERTY
    value: Optional[str] = None  # for PROPERTY, PRIMARY_VALUE, INDENTED
    choice_label: Optional[str] = None  # for CHOICE
    choice_commands: Optional[str] = None  # for CHOICE


class Lexer:
    """
    Line-based lexer for TahtLang.

    Usage:
        lexer = Lexer(source, filename)
        for line in lexer:
            print(line.type, line.raw)
    """

    # Patterns
    # Entity header: Name (type, id, ...flags)
    # e.g., "Hazine (counter, hazine, killer)"
    ENTITY_HEADER_PATTERN = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")
    PROPERTY_PATTERN = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_.-]*)\s*:\s*(.*)$")
    CHOICE_PATTERN = re.compile(r"^\*\s*([^:]+):\s*(.*)$")
    CHOICE_EMPTY_LABEL_PATTERN = re.compile(
        r"^\*\s*:\s*(.*)$"
    )  # * : commands (blind choice)
    CHOICE_NO_CMD_PATTERN = re.compile(r"^\*\s*(.+)$")

    def __init__(self, source: str, filename: str = "<string>"):
        self.source = source
        self.filename = filename
        self.lines = source.splitlines()
        self.pos = 0
        self.indent_char: Optional[str] = (
            None  # '\t' or ' ', detected from first indented line
        )

    def __iter__(self) -> Iterator[Line]:
        """Iterate over all lines."""
        for i, raw in enumerate(self.lines, start=1):
            yield self._classify_line(raw, i)

    def _require_indent(self, indent: int, line_number: int, sigil: str):
        """Raise ParseError if line is not indented."""
        if indent == 0:
            from .errors import ParseError

            raise ParseError(
                f"{sigil} line must be indented",
                SourceLocation(self.filename, line_number),
            )

    def _check_indent_consistency(self, raw: str, line_number: int):
        """
        Check that indentation is consistent (all tabs or spaces, not mixed).
        Raises ParseError if mixed indentation is detected.
        """
        if not raw or raw[0] not in "\t ":
            return  # No indent on this line

        # Get the indent portion
        indent_chars = ""
        for ch in raw:
            if ch in "\t ":
                indent_chars += ch
            else:
                break

        if not indent_chars:
            return

        # Check for mixed tabs and spaces in this line's indent
        has_tab = "\t" in indent_chars
        has_space = " " in indent_chars
        if has_tab and has_space:
            from .errors import ParseError

            raise ParseError(
                "Mixed indentation: cannot use both TAB and space "
                "on the same line",
                SourceLocation(self.filename, line_number),
            )

        # Detect indent style from first indented line
        first_char = indent_chars[0]
        if self.indent_char is None:
            self.indent_char = first_char
        elif self.indent_char != first_char:
            from .errors import ParseError

            expected = "TAB" if self.indent_char == "\t" else "space"
            found = "TAB" if first_char == "\t" else "space"
            raise ParseError(
                f"Inconsistent indentation: file uses {expected}, "
                f"but this line uses {found}",
                SourceLocation(self.filename, line_number),
            )

    def _try_parse_entity_header(
        self, stripped: str, raw: str, line_number: int, indent: int
    ) -> Optional[Line]:
        """Try to parse an entity header at column 0."""
        if indent != 0:
            return None

        match = self.ENTITY_HEADER_PATTERN.match(stripped)
        if not match:
            return None

        name = match.group(1).strip()
        parts = [p.strip() for p in match.group(2).split(",")]

        if not parts or ":" not in parts[0]:
            return None

        type_id = parts[0].split(":", 1)
        type_str = type_id[0].lower()
        entity_id = type_id[1] if len(type_id) > 1 else None
        raw_flags = parts[1:] if len(parts) > 1 else []

        entity_type = ENTITY_TYPE_MAP.get(type_str)
        if entity_type is None:
            return None

        # Normalize modifiers: lowercase + convert to enum
        modifiers: set[Modifier] = set()
        for f in raw_flags:
            flag_str = f.strip().lower()
            mod = MODIFIER_MAP.get(flag_str)
            if mod is not None:
                modifiers.add(mod)
            else:
                from .errors import ParseError

                raise ParseError(
                    f"Unknown modifier: '{f.strip()}'",
                    SourceLocation(self.filename, line_number),
                )

        return Line(
            LineType.ENTITY_HEADER,
            raw,
            line_number,
            indent,
            entity_name=name,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_modifiers=modifiers,
        )

    def _classify_line(self, raw: str, line_number: int) -> Line:
        """Classify a single line and extract its parts."""
        self._check_indent_consistency(raw, line_number)
        stripped = raw.lstrip()
        indent = len(raw) - len(stripped)

        if not stripped:
            return Line(LineType.EMPTY, raw, line_number, indent)
        if stripped.startswith("#"):
            return Line(LineType.COMMENT, raw, line_number, indent)

        # Dispatch based on prefix
        if indent == 0 and stripped.startswith("import "):
            return self._parse_import(raw, stripped, line_number, indent)
        if stripped.startswith(">"):
            return self._parse_primary_value(
                raw, stripped, line_number, indent
            )
        if stripped.startswith("*"):
            return self._parse_choice(raw, stripped, line_number, indent)

        # Entity header (only at col 0)
        entity_line = self._try_parse_entity_header(
            stripped, raw, line_number, indent
        )
        if entity_line:
            return entity_line

        # Property: key: value
        match = self.PROPERTY_PATTERN.match(stripped)
        if match:
            return self._parse_property(raw, match, line_number, indent)

        # Unknown indented content
        if indent > 0:
            return Line(
                LineType.INDENTED, raw, line_number, indent, value=stripped
            )

        # Unknown fallback
        return Line(
            LineType.PROPERTY, raw, line_number, indent, key=stripped, value=""
        )

    def _parse_import(self, raw, stripped, line_number, indent):
        rest = stripped[7:].strip()
        if (rest.startswith('"') and rest.endswith('"')) or (
            rest.startswith("'") and rest.endswith("'")
        ):
            return Line(
                LineType.IMPORT,
                raw,
                line_number,
                indent,
                import_path=rest[1:-1],
            )
        return Line(
            LineType.PROPERTY, raw, line_number, indent, key=stripped, value=""
        )

    def _parse_primary_value(self, raw, stripped, line_number, indent):
        self._require_indent(indent, line_number, "Content ('>')")
        return Line(
            LineType.PRIMARY_VALUE,
            raw,
            line_number,
            indent,
            value=stripped[1:].strip(),
        )

    def _parse_choice(self, raw, stripped, line_number, indent):
        self._require_indent(indent, line_number, "Choice ('*')")

        match = self.CHOICE_EMPTY_LABEL_PATTERN.match(stripped)
        if match:
            return Line(
                LineType.CHOICE,
                raw,
                line_number,
                indent,
                choice_label="",
                choice_commands=match.group(1).strip(),
            )

        match = self.CHOICE_PATTERN.match(stripped)
        if match:
            return Line(
                LineType.CHOICE,
                raw,
                line_number,
                indent,
                choice_label=match.group(1).strip(),
                choice_commands=match.group(2).strip(),
            )

        match = self.CHOICE_NO_CMD_PATTERN.match(stripped)
        if match:
            return Line(
                LineType.CHOICE,
                raw,
                line_number,
                indent,
                choice_label=match.group(1).strip(),
                choice_commands="",
            )

        return Line(
            LineType.PROPERTY, raw, line_number, indent, key=stripped, value=""
        )

    def _parse_property(self, raw, match, line_number, indent):
        if indent == 0:
            from .errors import ParseError

            raise ParseError(
                f"Property line must be indented ('{match.group(1)}')",
                SourceLocation(self.filename, line_number),
            )
        return Line(
            LineType.PROPERTY,
            raw,
            line_number,
            indent,
            key=match.group(1),
            value=match.group(2).strip(),
        )


def lex_file(filepath: str) -> Iterator[Line]:
    """Convenience function to lex a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    lexer = Lexer(source, filepath)
    yield from lexer
