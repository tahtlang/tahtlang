"""
TahtLang Parser

Parses .tahta files into an AST (Abstract Syntax Tree).
Used by both the compiler and the LSP server.
"""

from .ast import (
    LOCKTURN_DISPOSE,
    LOCKTURN_ONCE,
    AggregateType,
    Bearer,
    Card,
    CardBranch,
    CardQueue,
    CardTimed,
    Character,
    Choice,
    Counter,
    CounterCondition,
    CounterMod,
    FixedValue,
    Flag,
    FlagClear,
    FlagCondition,
    FlagSet,
    Game,
    Import,
    RangeValue,
    Settings,
    SourceLocation,
    TrackType,
    Trigger,
    Variant,
    Weight,
)
from .errors import ParseError, ValidationError
from .lexer import EntityType, Lexer, Modifier
from .parser import Parser
from .validator import (
    ValidationResult,
    Validator,
    resolve_imports,
    validate_game,
    validate_with_imports,
)

__all__ = [
    "Lexer",
    "Parser",
    "Validator",
    "ValidationResult",
    "validate_game",
    "resolve_imports",
    "validate_with_imports",
    "ParseError",
    "ValidationError",
    "EntityType",
    "Modifier",
    "LOCKTURN_DISPOSE",
    "LOCKTURN_ONCE",
    "AggregateType",
    "Bearer",
    "Card",
    "CardBranch",
    "CardQueue",
    "CardTimed",
    "Character",
    "Choice",
    "Counter",
    "CounterCondition",
    "CounterMod",
    "FixedValue",
    "Flag",
    "FlagClear",
    "FlagCondition",
    "FlagSet",
    "Game",
    "Import",
    "RangeValue",
    "Settings",
    "SourceLocation",
    "TrackType",
    "Trigger",
    "Variant",
    "Weight",
]
