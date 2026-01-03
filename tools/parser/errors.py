"""
Error types for the TahtaScript parser.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceLocation:
    """Location in source file for error reporting."""
    file: str
    line: int
    column: int = 0

    def __str__(self) -> str:
        if self.column:
            return f"{self.file}:{self.line}:{self.column}"
        return f"{self.file}:{self.line}"


class TahtaError(Exception):
    """Base error class with source location."""

    def __init__(self, message: str, location: Optional[SourceLocation] = None):
        self.message = message
        self.location = location
        super().__init__(self.format())

    def format(self) -> str:
        if self.location:
            return f"{self.location} - {self.message}"
        return self.message


class ParseError(TahtaError):
    """Syntax error during parsing."""
    pass


class ValidationError(TahtaError):
    """Semantic error during validation (e.g., unknown reference)."""
    pass
