"""
AST (Abstract Syntax Tree) models for TahtLang.

All game entities are represented as frozen dataclasses.
Tree-sitter produces CST, builder.py converts CST to these AST nodes.

Design decisions:
- Frozen dataclasses for immutability
- Every node has optional source location (file, line, column)
- Matches grammar.js structure closely for easy CST->AST conversion
"""

from dataclasses import dataclass, field
from typing import Optional, Union
from enum import Enum, auto


# =============================================================================
# Source Location (for error reporting)
# =============================================================================

@dataclass(frozen=True)
class SourceLocation:
    """Source code location for error reporting."""
    file: str
    line: int
    column: int = 0
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def __str__(self) -> str:
        if self.column:
            return f"{self.file}:{self.line}:{self.column}"
        return f"{self.file}:{self.line}"


# =============================================================================
# Conditions (for require: and weight: when clauses)
# =============================================================================

@dataclass(frozen=True)
class FlagCondition:
    """Flag presence/absence condition: flag:winter or !flag:winter"""
    flag_id: str
    negated: bool = False
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class CounterCondition:
    """Counter comparison: counter:hazine < 30 or counter:ordu > 50"""
    counter_id: str
    operator: str  # '<', '>', '=', '<=', '>='
    value: int
    loc: Optional[SourceLocation] = None


Condition = Union[FlagCondition, CounterCondition]


# =============================================================================
# Values (fixed or range)
# =============================================================================

@dataclass(frozen=True)
class FixedValue:
    """A fixed integer value: 20"""
    value: int
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class RangeValue:
    """A random range value: 10?30 (picks random between min and max)"""
    min_value: int
    max_value: int
    loc: Optional[SourceLocation] = None


ValueOrRange = Union[FixedValue, RangeValue]


# =============================================================================
# Commands (effects of choices)
# =============================================================================

@dataclass(frozen=True)
class CounterMod:
    """Modify a counter: counter:hazine 20 or counter:ordu -10?20

    Value includes the sign:
    - counter:treasure 20      -> add 20
    - counter:treasure -20     -> subtract 20
    - counter:treasure -20?-1  -> subtract random 1-20
    - counter:treasure -5?10   -> add random between -5 and +10
    """
    counter_id: str
    value: ValueOrRange  # Value includes sign (can be negative)
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class FlagSet:
    """Set a flag: +flag:winter"""
    flag_id: str
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class FlagClear:
    """Clear a flag: -flag:winter"""
    flag_id: str
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class CardQueue:
    """Queue a card immediately: card:intro"""
    card_id: str
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class CardBranch:
    """Queue a conditional branch: [card:_a, card:_b, card:_c]

    Runtime picks the first card whose require conditions are met.
    If none match, branch is skipped.
    """
    card_ids: tuple[str, ...]
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class CardTimed:
    """Queue a card after N turns: card:intro@5"""
    card_id: str
    delay: int
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class Trigger:
    """Trigger an effect: trigger:response "text" or trigger:sound "coin.wav"

    Trigger types:
    - response: Shows text after choice (card flips, shows response)
    - sound: Plays a sound effect
    """
    trigger_type: str  # "response", "sound"
    value: str         # Text or sound file name
    loc: Optional[SourceLocation] = None


Command = Union[CounterMod, FlagSet, FlagClear, CardQueue, CardBranch, CardTimed, Trigger]


# =============================================================================
# Weight (with optional condition)
# =============================================================================

@dataclass(frozen=True)
class Weight:
    """A weight value with optional 'when' condition."""
    value: float
    condition: Optional[Condition] = None
    loc: Optional[SourceLocation] = None


# =============================================================================
# Card components
# =============================================================================

@dataclass(frozen=True)
class Bearer:
    """Card bearer: character with optional variant (emotion, state, pose)."""
    character_id: str
    variant_id: Optional[str] = None
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class Choice:
    """A card choice (left or right swipe)."""
    label: str
    commands: tuple[Command, ...] = ()
    loc: Optional[SourceLocation] = None


# =============================================================================
# Entity Definitions
# =============================================================================

class AggregateType(Enum):
    """Aggregate function types for virtual counters."""
    AVERAGE = auto()
    SUM = auto()
    MIN = auto()
    MAX = auto()


class TrackType(Enum):
    """What to track for tracking counters."""
    YES = auto()  # Track yes responses
    NO = auto()   # Track no responses


@dataclass(frozen=True)
class Counter:
    """A game counter (e.g., hazine, ordu).

    Regular counter: start value, can be modified
    Virtual counter (aggregate): computed from other counters
    Virtual counter (tracking): counts player responses to a character
    """
    id: str
    name: str
    icon: str = ""
    start: int = 50
    color: str = ""
    killer: bool = False  # if True, game over when 0 or 100
    keep: bool = False    # if True, persists across reigns

    # Virtual counter - aggregate (e.g., overall = average of all killers)
    source: tuple[str, ...] = ()       # Source counter/character IDs
    aggregate: Optional[AggregateType] = None  # average, sum, min, max

    # Virtual counter - tracking (e.g., yes_merchant counts yes responses)
    track: Optional[TrackType] = None  # yes or no

    loc: Optional[SourceLocation] = None

    @property
    def is_virtual(self) -> bool:
        """True if this is a virtual (computed) counter."""
        return self.aggregate is not None or self.track is not None


@dataclass(frozen=True)
class Flag:
    """A game flag (boolean state)."""
    id: str
    name: str
    bind: Optional[str] = None  # Character ID this flag controls
    keep: bool = False          # if True, persists across reigns
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class Variant:
    """A character variant (emotion, state, pose) for portraits."""
    id: str
    name: str
    prompt: str = ""
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class Character:
    """A game character (role-based)."""
    id: str
    name: str
    prompt: str = ""
    loc: Optional[SourceLocation] = None


# Lockturn special values
LOCKTURN_ONCE = "once"      # Lock for this reign only (resets on king death)
LOCKTURN_DISPOSE = "dispose"  # Remove from game permanently after showing

# Type alias for lockturn: int (turns) | "once" | "dispose" | None
Lockturn = Union[int, str, None]


@dataclass(frozen=True)
class Card:
    """A game card.

    ring: If True, this is a chain card that:
      - Cannot be drawn from pool (no weight)
      - Only appears when queued by another card
      - ID must start with '_'

    lockturn: How long to lock card from pool after showing:
      - int (e.g., 60): Lock for N turns
      - "once": Lock for rest of reign (resets on king death)
      - "dispose": Remove permanently (intro cards, one-time events)
    """
    id: str
    name: str
    bearer: Optional[Bearer] = None
    text: str = ""
    require: tuple[Condition, ...] = ()
    weights: tuple[Weight, ...] = ()
    lockturn: Lockturn = None
    choices: tuple[Choice, ...] = ()
    ring: bool = False  # if True, chain-only card (queue'dan gelir)
    loc: Optional[SourceLocation] = None


@dataclass(frozen=True)
class Settings:
    """Game settings."""
    id: str  # Usually "main"
    name: str
    description: str = ""
    starting_flags: tuple[str, ...] = ()
    game_over_on_zero: bool = True
    game_over_on_max: bool = True
    loc: Optional[SourceLocation] = None


# =============================================================================
# Import statement
# =============================================================================

@dataclass(frozen=True)
class Import:
    """Import another .tahta file: import "path/to/file.tahta" """
    path: str  # Relative path to the file
    loc: Optional[SourceLocation] = None


# =============================================================================
# Game (root container)
# =============================================================================

@dataclass(frozen=True)
class Game:
    """Root container for all game data."""
    imports: tuple[Import, ...] = ()
    settings: Optional[Settings] = None
    counters: tuple[Counter, ...] = ()
    flags: tuple[Flag, ...] = ()
    variants: tuple[Variant, ...] = ()
    characters: tuple[Character, ...] = ()
    cards: tuple[Card, ...] = ()

    def get_counter(self, entity_id: str) -> Optional[Counter]:
        """Find counter by ID."""
        return next((c for c in self.counters if c.id == entity_id), None)

    def get_flag(self, entity_id: str) -> Optional[Flag]:
        """Find flag by ID."""
        return next((f for f in self.flags if f.id == entity_id), None)

    def get_variant(self, entity_id: str) -> Optional[Variant]:
        """Find variant by ID."""
        return next((v for v in self.variants if v.id == entity_id), None)

    def get_character(self, entity_id: str) -> Optional[Character]:
        """Find character by ID."""
        return next((c for c in self.characters if c.id == entity_id), None)

    def get_card(self, entity_id: str) -> Optional[Card]:
        """Find card by ID."""
        return next((c for c in self.cards if c.id == entity_id), None)
