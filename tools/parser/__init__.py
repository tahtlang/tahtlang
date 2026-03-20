"""
TahtLang Parser

Parses .tahta files into an AST (Abstract Syntax Tree).
Used by both the compiler and the LSP server.
"""

from .ast import (
    Game, Settings, Counter, Flag, Variant, Character, Card,
    Choice, Bearer, Weight, SourceLocation, Import,
    CounterMod, FlagSet, FlagClear, CardQueue, CardBranch, CardTimed, Trigger,
    FixedValue, RangeValue,
    FlagCondition, CounterCondition,
    AggregateType, TrackType,
    LOCKTURN_ONCE, LOCKTURN_DISPOSE,
)
from .lexer import Lexer
from .parser import Parser
from .validator import Validator, ValidationResult, validate_game, resolve_imports, validate_with_imports
from .errors import ParseError, ValidationError

__all__ = [
    'Lexer',
    'Parser',
    'Validator',
    'ValidationResult',
    'validate_game',
    'resolve_imports',
    'validate_with_imports',
    'ParseError',
    'ValidationError',
]
