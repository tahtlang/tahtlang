"""
Recursive descent parser for TahtLang.

No regex in this file - all parsing done with explicit string operations
for readability and debuggability.
"""

from pathlib import Path
from typing import Optional

from .lexer import Lexer, Line, LineType, EntityType, Modifier
from .ast import (
    Game, Settings, Counter, Flag, Variant, Character, Card,
    Choice, Bearer, Weight, SourceLocation, Import,
    # Commands
    CounterMod, FlagSet, FlagClear, CardQueue, CardBranch, CardTimed, Trigger,
    # Values
    FixedValue, RangeValue,
    # Conditions
    FlagCondition, CounterCondition,
    # Type aliases
    Command, Condition, ValueOrRange, Lockturn,
    # Lockturn constants
    LOCKTURN_ONCE, LOCKTURN_DISPOSE,
    # Virtual counter enums
    AggregateType, TrackType
)
from .errors import ParseError


class Parser:
    """
    Recursive descent parser for TahtLang.

    Usage:
        parser = Parser()
        game = parser.parse_file("game.tahta")
    """

    def __init__(self):
        self.current_file: str = ""
        self.lines: list[Line] = []
        self.pos: int = 0
        self.base_path: Path = Path(".")

        # Collect entities during parsing
        self._imports: list[Import] = []
        self._settings: Optional[Settings] = None
        self._counters: list[Counter] = []
        self._flags: list[Flag] = []
        self._variants: list[Variant] = []
        self._characters: list[Character] = []
        self._cards: list[Card] = []

    def parse_file(self, filepath: str) -> Game:
        """Parse a .tahta file and return the Game AST."""
        path = Path(filepath)
        self.base_path = path.parent
        self.current_file = str(path)

        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        return self.parse_string(source, str(path))

    def parse_string(self, source: str, filename: str = "<string>") -> Game:
        """Parse a string and return the Game AST."""
        self.current_file = filename
        lexer = Lexer(source, filename)
        self.lines = list(lexer)
        self.pos = 0

        # Reset collections
        self._imports = []
        self._settings = None
        self._counters = []
        self._flags = []
        self._variants = []
        self._characters = []
        self._cards = []

        self._parse_top_level()

        return Game(
            imports=tuple(self._imports),
            settings=self._settings,
            counters=tuple(self._counters),
            flags=tuple(self._flags),
            variants=tuple(self._variants),
            characters=tuple(self._characters),
            cards=tuple(self._cards)
        )

    def _parse_top_level(self):
        """Parse top-level elements: imports and entities."""
        while not self._eof():
            line = self._current()

            if line.type in (LineType.EMPTY, LineType.COMMENT):
                self._advance()
                continue

            if line.type == LineType.IMPORT:
                self._parse_import(line)
                self._advance()
                continue

            if line.type == LineType.ENTITY_HEADER:
                self._parse_entity()
                continue

            raise self._error(f"Unexpected line: {line.raw.strip()}")

    def _parse_import(self, line: Line):
        """Parse an import statement."""
        import_node = Import(
            path=line.import_path or "",
            loc=self._make_loc(line)
        )
        self._imports.append(import_node)

    def _parse_entity(self):
        """Parse an entity (card, character, counter, etc.)."""
        header = self._current()
        entity_type = header.entity_type
        entity_name = header.entity_name or ""
        entity_id = header.entity_id or ""
        modifiers = header.entity_modifiers or set()
        self._advance()

        if entity_type == EntityType.SETTINGS:
            self._parse_settings(entity_name, entity_id, header)
        elif entity_type == EntityType.COUNTER:
            self._parse_counter(entity_name, entity_id, modifiers, header)
        elif entity_type == EntityType.FLAG:
            self._parse_flag(entity_name, entity_id, modifiers, header)
        elif entity_type == EntityType.VARIANT:
            self._parse_variant(entity_name, entity_id, header)
        elif entity_type == EntityType.CHARACTER:
            self._parse_character(entity_name, entity_id, header)
        elif entity_type == EntityType.CARD:
            self._parse_card(entity_name, entity_id, modifiers, header)
        else:
            raise self._error(f"Unknown entity type: {entity_type}", header)

    def _make_loc(self, line: Line) -> SourceLocation:
        """Create a SourceLocation from a Line."""
        return SourceLocation(
            file=self.current_file,
            line=line.line_number,
            column=line.indent
        )

    SETTINGS_KEYS = {"description", "starting_flags", "game_over_on_zero", "game_over_on_max"}
    COUNTER_KEYS = {"start", "icon", "color", "source", "aggregate", "track"}
    FLAG_KEYS = {"bind"}
    VARIANT_KEYS = {"prompt"}
    CHARACTER_KEYS = {"prompt"}

    @staticmethod
    def _parse_bool(value: str, default: bool = True) -> bool:
        """Parse a boolean property value.

        'true' -> True, 'false' -> False, '' -> default
        """
        if not value:
            return default
        return value.lower().strip() == "true"

    def _parse_settings(self, name: str, entity_id: str, header: Line):
        """Parse settings entity."""
        props = self._collect_properties(valid_keys=self.SETTINGS_KEYS)

        starting_flags: tuple[str, ...] = ()
        if "starting_flags" in props:
            starting_flags = tuple(self._parse_flag_list(props["starting_flags"]))

        self._settings = Settings(
            id=entity_id or "main",
            name=name or "",
            description=self._strip_quotes(props.get("description", "")),
            starting_flags=starting_flags,
            game_over_on_zero=self._parse_bool(props.get("game_over_on_zero", "")),
            game_over_on_max=self._parse_bool(props.get("game_over_on_max", "")),
            loc=self._make_loc(header)
        )

    # Lookup tables for string -> enum conversion
    AGGREGATE_MAP = {
        "average": AggregateType.AVERAGE,
        "sum": AggregateType.SUM,
        "min": AggregateType.MIN,
        "max": AggregateType.MAX,
    }
    TRACK_MAP = {
        "yes": TrackType.YES,
        "no": TrackType.NO,
    }
    LOCKTURN_MAP = {
        "once": LOCKTURN_ONCE,
        "dispose": LOCKTURN_DISPOSE,
    }

    def _parse_counter(self, name: str, entity_id: str, modifiers: set[Modifier], header: Line):
        """Parse a counter entity. Primary field: start value

        Regular counter:
            Hazine (counter:hazine, killer)
                > 50

        Virtual counter (aggregate):
            Overall (counter:overall)
                source: [counter:spiritual, counter:military, counter:demography, counter:treasure]
                aggregate: average

        Virtual counter (tracking):
            Merchant Yes (counter:yes_merchant)
                source: [character:merchant]
                track: yes
        """
        props = self._collect_properties(primary_key="start", valid_keys=self.COUNTER_KEYS)

        # Primary value is start, parse as int
        start_str = props.get("start", "50")
        try:
            start = int(start_str)
        except ValueError:
            start = 50

        # Parse source list (for virtual counters)
        source: tuple[str, ...] = ()
        if "source" in props:
            source = tuple(self._parse_reference_list(props["source"]))

        # Parse aggregate and track types via lookup
        aggregate = self.AGGREGATE_MAP.get(props.get("aggregate", "").lower().strip())
        track = self.TRACK_MAP.get(props.get("track", "").lower().strip())

        counter = Counter(
            id=entity_id,
            name=name,
            icon=props.get("icon", ""),
            start=start,
            color=props.get("color", ""),
            killer=Modifier.KILLER in modifiers,
            keep=Modifier.KEEP in modifiers,
            source=source,
            aggregate=aggregate,
            track=track,
            loc=self._make_loc(header)
        )
        self._counters.append(counter)

    def _parse_flag(self, name: str, entity_id: str, modifiers: set[Modifier], header: Line):
        """Parse a flag entity."""
        props = self._collect_properties(valid_keys=self.FLAG_KEYS)

        # Parse bind property (strip character: prefix if present)
        bind = None
        if "bind" in props:
            bind = self._strip_type_prefix(props["bind"], "character")

        flag = Flag(
            id=entity_id,
            name=name,
            bind=bind,
            keep=Modifier.KEEP in modifiers,
            loc=self._make_loc(header)
        )
        self._flags.append(flag)

    def _parse_variant(self, name: str, entity_id: str, header: Line):
        """Parse a variant entity (emotion, state, pose)."""
        props = self._collect_properties(valid_keys=self.VARIANT_KEYS)

        variant = Variant(
            id=entity_id,
            name=name,
            prompt=self._strip_quotes(props.get("prompt", "")),
            loc=self._make_loc(header)
        )
        self._variants.append(variant)

    def _parse_character(self, name: str, entity_id: str, header: Line):
        """Parse a character entity."""
        props = self._collect_properties(valid_keys=self.CHARACTER_KEYS)

        character = Character(
            id=entity_id,
            name=name,
            prompt=self._strip_quotes(props.get("prompt", "")),
            loc=self._make_loc(header)
        )
        self._characters.append(character)

    def _parse_card(self, name: str, entity_id: str, modifiers: set[Modifier], header: Line):
        """Parse a card entity. Primary field: text"""
        bearer: Optional[Bearer] = None
        text: str = ""
        require: list[Condition] = []
        weights: list[Weight] = []
        lockturn: Lockturn = None
        choices: list[Choice] = []

        while not self._eof():
            line = self._current()

            # Stop at next entity
            if line.type == LineType.ENTITY_HEADER:
                break

            if line.type in (LineType.EMPTY, LineType.COMMENT):
                self._advance()
                continue

            if line.type == LineType.PRIMARY_VALUE:
                text = line.value or ""
                self._advance()
                continue

            if line.type == LineType.CHOICE:
                choices.append(self._parse_choice(line))
                self._advance()
                continue

            if line.type == LineType.PROPERTY:
                bearer, require, weights, lockturn = self._parse_card_property(
                    line, bearer, require, weights, lockturn
                )
                self._advance()
                continue

            if line.type == LineType.INDENTED:
                weight = self._parse_weight_line(line.value or "", line)
                if weight:
                    weights.append(weight)
                self._advance()
                continue

            self._advance()

        card = Card(
            id=entity_id,
            name=name,
            bearer=bearer,
            text=text,
            require=tuple(require),
            weights=tuple(weights),
            lockturn=lockturn,
            choices=tuple(choices),
            ring=Modifier.RING in modifiers,
            loc=self._make_loc(header)
        )
        self._cards.append(card)

    def _parse_card_property(
        self,
        line: Line,
        bearer: Optional[Bearer],
        require: list[Condition],
        weights: list[Weight],
        lockturn: Lockturn,
    ) -> tuple[Optional[Bearer], list[Condition], list[Weight], Lockturn]:
        """Parse a single card property line. Returns updated values."""
        key = line.key
        value = line.value or ""

        if key == "bearer":
            bearer = self._parse_bearer(value, line)
        elif key == "require":
            require = self._parse_condition_list(value, line)
        elif key == "weight" and value:
            weight = self._parse_weight_line(value, line)
            if weight:
                weights.append(weight)
        elif key == "lockturn":
            lockturn = self._parse_lockturn(value, line)
        else:
            raise self._error(f"Unknown card property: '{key}'", line)

        return bearer, require, weights, lockturn

    def _parse_lockturn(self, value: str, line: Line) -> Lockturn:
        """Parse lockturn value: integer, 'once', or 'dispose'."""
        special = self.LOCKTURN_MAP.get(value.lower().strip())
        if special is not None:
            return special
        try:
            return int(value)
        except ValueError:
            raise self._error(
                f"Invalid lockturn value: '{value}' (must be integer, 'once', or 'dispose')",
                line
            )

    def _parse_choice(self, line: Line) -> Choice:
        """Parse a choice line."""
        commands: tuple[Command, ...] = ()
        if line.choice_commands:
            commands = tuple(self._parse_commands(line.choice_commands, line))

        return Choice(
            label=line.choice_label or "",
            commands=commands,
            loc=self._make_loc(line)
        )

    # =========================================================================
    # String parsing helpers - NO REGEX, explicit and readable
    # =========================================================================

    def _parse_bearer(self, value: str, line: Line) -> Bearer:
        """Parse bearer with optional variant.

        'character:advisor'                -> Bearer('advisor', None)
        'character:advisor (variant:angry)' -> Bearer('advisor', 'angry')
        """
        value = value.strip()
        loc = self._make_loc(line)

        # No variant
        if '(' not in value or not value.endswith(')'):
            char_id = self._strip_type_prefix(value, 'character')
            return Bearer(character_id=char_id, variant_id=None, loc=loc)

        # Has variant: 'character:advisor (variant:angry)'
        paren_start = value.index('(')
        char_id = self._strip_type_prefix(value[:paren_start].strip(), 'character')
        variant_id = self._strip_type_prefix(value[paren_start + 1:-1].strip(), 'variant')
        return Bearer(character_id=char_id, variant_id=variant_id, loc=loc)

    def _strip_type_prefix(self, value: str, expected_type: str) -> str:
        """
        Strip type prefix from value.

        'counter:hazine' -> 'hazine'
        'hazine' -> 'hazine' (no prefix)
        """
        value = value.strip()
        prefix = expected_type + ':'
        if value.lower().startswith(prefix):
            return value[len(prefix):]
        return value

    def _parse_commands(self, commands_str: str, line: Line) -> list[Command]:
        """
        Parse comma-separated commands.
        Example: '+counter:hazine 20, -counter:halk 10, +flag:winter, card:next-event'
        Example with branch: '[card:_a, card:_b], +flag:done'

        Uses bracket-aware splitting to handle branch syntax.
        """
        commands = []

        # Split by comma, but respect brackets
        parts = self._split_commands(commands_str)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            cmd = self._parse_single_command(part, line)
            if cmd:
                commands.append(cmd)
            else:
                raise self._error(f"Unknown command: '{part}'", line)

        return commands

    def _split_commands(self, commands_str: str) -> list[str]:
        """
        Split commands by comma, respecting bracket groups.

        '[card:_a, card:_b], +flag:done' -> ['[card:_a, card:_b]', '+flag:done']
        """
        parts = []
        current = ""
        bracket_depth = 0

        for ch in commands_str:
            if ch == '[':
                bracket_depth += 1
                current += ch
            elif ch == ']':
                bracket_depth -= 1
                current += ch
            elif ch == ',' and bracket_depth == 0:
                # Split here
                if current.strip():
                    parts.append(current.strip())
                current = ""
            else:
                current += ch

        # Add last part
        if current.strip():
            parts.append(current.strip())

        return parts

    def _parse_single_command(self, part: str, line: Line) -> Optional[Command]:
        """
        Parse a single command. Dispatches to sub-parsers by prefix.

        Supported formats:
        - '[card:_a, card:_b]'        : conditional branch
        - 'card:id' / 'card:id@5'    : queue / timed queue
        - '+flag:id' / '-flag:id'    : set / clear flag
        - 'counter:id 20'            : modify counter (fixed or range)
        - 'trigger:type "value"'     : trigger effect
        """
        part = part.strip()
        part_lower = part.lower()

        if part.startswith('['):
            return self._parse_branch_cmd(part, line)
        if part_lower.startswith('card:'):
            return self._parse_card_cmd(part[5:], line)
        if part_lower.startswith('+flag:'):
            return FlagSet(flag_id=part[6:].strip(), loc=self._make_loc(line))
        if part_lower.startswith('-flag:'):
            return FlagClear(flag_id=part[6:].strip(), loc=self._make_loc(line))
        if part_lower.startswith('counter:'):
            return self._parse_counter_cmd(part[8:], line)
        if part_lower.startswith('trigger:'):
            return self._parse_trigger_cmd(part[8:], line)

        return None

    def _parse_branch_cmd(self, part: str, line: Line) -> Optional[CardBranch]:
        """Parse branch command.

        '[card:_a, card:_b]' -> CardBranch(card_ids=('_a', '_b'))
        """
        if not part.endswith(']'):
            return None
        inner = part[1:-1].strip()
        card_ids = []
        for ref in inner.split(','):
            ref = ref.strip()
            if ref.lower().startswith('card:'):
                card_ids.append(ref[5:])
            elif ref:
                card_ids.append(ref)
        if card_ids:
            return CardBranch(card_ids=tuple(card_ids), loc=self._make_loc(line))
        return None

    def _parse_card_cmd(self, rest: str, line: Line) -> Command:
        """Parse card command. rest = everything after 'card:'.

        'next'   -> CardQueue(card_id='next')
        'event@5' -> CardTimed(card_id='event', delay=5)
        """
        rest = rest.strip()
        loc = self._make_loc(line)
        if '@' in rest:
            at_pos = rest.index('@')
            card_id = rest[:at_pos].strip()
            delay = self._parse_unsigned_int(rest[at_pos + 1:])
            if delay is not None:
                return CardTimed(card_id=card_id, delay=delay, loc=loc)
        return CardQueue(card_id=rest, loc=loc)

    def _parse_counter_cmd(self, rest: str, line: Line) -> Optional[CounterMod]:
        """Parse counter modification. rest = everything after 'counter:'.

        'treasury 20'    -> CounterMod('treasury', FixedValue(20))
        'army -10?-5'    -> CounterMod('army', RangeValue(-10, -5))
        """
        if ' ' not in rest:
            return None
        tokens = rest.split(None, 1)
        if len(tokens) != 2:
            return None
        counter_id = tokens[0]
        value = self._parse_value_or_range(tokens[1], line)
        if not value:
            return None
        return CounterMod(counter_id=counter_id, value=value, loc=self._make_loc(line))

    def _parse_trigger_cmd(self, rest: str, line: Line) -> Optional[Trigger]:
        """Parse trigger command. rest = everything after 'trigger:'.

        'response "Well done!"' -> Trigger('response', 'Well done!')
        'sound "coin.wav"'      -> Trigger('sound', 'coin.wav')
        """
        if ' ' not in rest:
            return None
        space_pos = rest.index(' ')
        trigger_type = rest[:space_pos].strip()
        value = self._strip_quotes(rest[space_pos + 1:].strip())
        return Trigger(trigger_type=trigger_type, value=value, loc=self._make_loc(line))

    def _parse_value_or_range(self, s: str, line: Line) -> Optional[ValueOrRange]:
        """Parse a value or range.

        '20'    -> FixedValue(20)
        '10?30' -> RangeValue(10, 30)
        '10?'   -> RangeValue(0, 10)
        '?20'   -> RangeValue(0, 20)
        '-10?'  -> RangeValue(-10, 0)
        """
        s = s.strip()
        if '?' in s:
            return self._parse_range(s, line)
        try:
            return FixedValue(value=int(s), loc=self._make_loc(line))
        except ValueError:
            return None

    def _parse_range(self, s: str, line: Line) -> Optional[RangeValue]:
        """Parse a range value split by '?'.

        '10?30' -> RangeValue(10, 30)   both sides given
        '10?'   -> RangeValue(0, 10)    shorthand: 0 to N
        '-10?'  -> RangeValue(-10, 0)   shorthand: N to 0 (negative)
        '?20'   -> RangeValue(0, 20)    shorthand: 0 to N
        """
        parts = s.split('?')
        if len(parts) != 2:
            return None
        left = parts[0].strip()
        right = parts[1].strip()
        loc = self._make_loc(line)

        try:
            if left and right:
                return RangeValue(int(left), int(right), loc=loc)
            if left:
                val = int(left)
                if val >= 0:
                    return RangeValue(0, val, loc=loc)
                return RangeValue(val, 0, loc=loc)
            if right:
                return RangeValue(0, int(right), loc=loc)
        except ValueError:
            pass
        return None

    def _parse_unsigned_int(self, s: str) -> Optional[int]:
        """
        Parse an unsigned integer: '20', '10'
        Returns None if not a valid positive integer.
        """
        s = s.strip()
        if not s:
            return None

        try:
            value = int(s)
            return value if value >= 0 else None
        except ValueError:
            return None

    def _parse_weight_line(self, value: str, line: Line) -> Optional[Weight]:
        """Parse weight with optional condition.

        '1.0'                          -> Weight(1.0, None)
        '2.0 when counter:treasury < 30' -> Weight(2.0, CounterCondition(...))
        '0 when flag:war'              -> Weight(0.0, FlagCondition(...))
        """
        value = value.strip()
        if not value:
            return None

        # Split on ' when ' if present
        weight_str = value
        condition = None
        when_pos = value.lower().find(' when ')
        if when_pos > 0:
            weight_str = value[:when_pos].strip()
            condition = self._parse_single_condition(value[when_pos + 6:].strip(), line)

        try:
            return Weight(
                value=float(weight_str),
                condition=condition,
                loc=self._make_loc(line),
            )
        except ValueError:
            raise self._error(f"Invalid weight value: '{weight_str}'", line)

    @staticmethod
    def _split_bracketed_list(value: str) -> list[str]:
        """Split a comma-separated list, stripping optional brackets.

        '[a, b, c]' -> ['a', 'b', 'c']
        'a, b'      -> ['a', 'b']
        """
        value = value.strip()
        if value.startswith('[') and value.endswith(']'):
            value = value[1:-1].strip()
        return [p.strip() for p in value.split(',') if p.strip()]

    def _parse_flag_list(self, value: str) -> list[str]:
        """Parse a list of flags, stripping 'flag:' prefix.

        '[flag:intro, flag:war]' -> ['intro', 'war']
        'flag:intro'             -> ['intro']
        """
        return [
            self._strip_type_prefix(part, 'flag')
            for part in self._split_bracketed_list(value)
        ]

    def _parse_reference_list(self, value: str) -> list[str]:
        """Parse a list of typed references, preserving prefix.

        '[counter:a, counter:b]' -> ['counter:a', 'counter:b']
        """
        return self._split_bracketed_list(value)

    def _parse_condition_list(self, value: str, line: Line) -> list[Condition]:
        """
        Parse a list of conditions for require: property.

        Examples:
        - 'flag:tower'                      -> [FlagCondition('tower')]
        - '!flag:fortification'             -> [FlagCondition('fortification', negated=True)]
        - 'counter:military < 40'           -> [CounterCondition('military', '<', 40)]
        """
        conditions = []
        value = value.strip()

        if not value:
            return conditions

        # Split by comma
        parts = value.split(',')

        for part in parts:
            part = part.strip()
            if part:
                cond = self._parse_single_condition(part, line)
                if cond:
                    conditions.append(cond)

        return conditions

    # Operators ordered longest first for greedy matching
    CONDITION_OPERATORS = ('<=', '>=', '<', '>', '=')

    def _parse_single_condition(self, part: str, line: Line) -> Optional[Condition]:
        """Parse a single condition.

        'flag:tower'          -> FlagCondition('tower')
        '!flag:war'           -> FlagCondition('war', negated=True)
        'counter:treasury < 30' -> CounterCondition('treasury', '<', 30)
        'counter:army >= 50'  -> CounterCondition('army', '>=', 50)
        """
        part = part.strip()
        loc = self._make_loc(line)

        # Check for negation
        negated = False
        if part.startswith('!'):
            negated = True
            part = part[1:].strip()

        # Try counter condition: look for an operator
        counter_cond = self._try_parse_counter_condition(part, loc)
        if counter_cond:
            return counter_cond

        # Flag condition: 'flag:tower' or just 'tower' (legacy)
        flag_id = self._strip_type_prefix(part, 'flag')
        return FlagCondition(flag_id=flag_id, negated=negated, loc=loc)

    def _try_parse_counter_condition(
        self, part: str, loc: SourceLocation
    ) -> Optional[CounterCondition]:
        """Try to parse 'counter:id OP value'. Returns None if not a counter condition.

        'counter:treasury < 30' -> CounterCondition('treasury', '<', 30)
        'counter:army >= 50'    -> CounterCondition('army', '>=', 50)
        'flag:war'              -> None (not a counter condition)
        """
        for op in self.CONDITION_OPERATORS:
            if op not in part:
                continue
            op_pos = part.index(op)
            if op_pos == 0:
                continue
            left = part[:op_pos].strip()
            right = part[op_pos + len(op):].strip()
            counter_id = self._strip_type_prefix(left, 'counter')
            try:
                return CounterCondition(
                    counter_id=counter_id,
                    operator=op,
                    value=int(right),
                    loc=loc,
                )
            except ValueError:
                continue
        return None

    def _strip_quotes(self, value: str) -> str:
        """Remove surrounding quotes from a string."""
        value = value.strip()
        if len(value) >= 2:
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                return value[1:-1]
        return value

    def _collect_properties(
        self,
        primary_key: str = "_primary",
        valid_keys: Optional[set[str]] = None,
    ) -> dict[str, str]:
        """
        Collect all property lines until next entity or special line.

        The `> value` syntax sets the primary_key field.
        If valid_keys is given, raises error on unknown property keys.
        """
        props = {}

        while not self._eof():
            line = self._current()

            if line.type == LineType.ENTITY_HEADER:
                break
            if line.type == LineType.CHOICE:
                break

            if line.type == LineType.PRIMARY_VALUE:
                props[primary_key] = line.value or ""
                self._advance()
                continue

            if line.type == LineType.PROPERTY and line.key:
                if valid_keys is not None and line.key not in valid_keys:
                    raise self._error(
                        f"Unknown property: '{line.key}'", line
                    )
                props[line.key] = line.value or ""
                self._advance()
                continue

            if line.type in (LineType.EMPTY, LineType.COMMENT):
                self._advance()
                continue

            break

        return props

    # =========================================================================
    # Navigation helpers
    # =========================================================================

    def _current(self) -> Line:
        """Get current line."""
        return self.lines[self.pos]

    def _advance(self):
        """Move to next line."""
        self.pos += 1

    def _eof(self) -> bool:
        """Check if at end of file."""
        return self.pos >= len(self.lines)

    def _error(self, message: str, line: Optional[Line] = None) -> ParseError:
        """Create a parse error with location."""
        if line is None and not self._eof():
            line = self._current()

        loc = None
        if line:
            loc = SourceLocation(file=self.current_file, line=line.line_number)

        return ParseError(message, loc)
