"""
Recursive descent parser for TahtLang.

No regex in this file - all parsing done with explicit string operations
for readability and debuggability.
"""

from pathlib import Path
from typing import Optional

from .lexer import Lexer, Line, LineType
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

            raise self._error(f"Beklenmeyen satir: {line.raw.strip()}")

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
        entity_name = header.entity_name
        entity_id = header.entity_id
        entity_flags = header.entity_flags or []
        self._advance()

        if entity_type == "settings":
            self._parse_settings(entity_name, entity_id, header)
        elif entity_type == "counter":
            self._parse_counter(entity_name, entity_id, entity_flags, header)
        elif entity_type == "flag":
            self._parse_flag(entity_name, entity_id, entity_flags, header)
        elif entity_type == "variant":
            self._parse_variant(entity_name, entity_id, header)
        elif entity_type == "character":
            self._parse_character(entity_name, entity_id, header)
        elif entity_type == "card":
            self._parse_card(entity_name, entity_id, entity_flags, header)
        else:
            raise self._error(f"Bilinmeyen entity tipi: {entity_type}", header)

    def _make_loc(self, line: Line) -> SourceLocation:
        """Create a SourceLocation from a Line."""
        return SourceLocation(
            file=self.current_file,
            line=line.line_number,
            column=line.indent
        )

    def _parse_settings(self, name: str, entity_id: str, header: Line):
        """Parse settings entity."""
        props = self._collect_properties()

        starting_flags: tuple[str, ...] = ()
        if "starting_flags" in props:
            starting_flags = tuple(self._parse_flag_list(props["starting_flags"]))

        game_over_on_zero = True
        if "game_over_on_zero" in props:
            game_over_on_zero = props["game_over_on_zero"].lower() == "true"

        game_over_on_max = True
        if "game_over_on_max" in props:
            game_over_on_max = props["game_over_on_max"].lower() == "true"

        self._settings = Settings(
            id=entity_id or "main",
            name=name or "",
            description=self._strip_quotes(props.get("description", "")),
            starting_flags=starting_flags,
            game_over_on_zero=game_over_on_zero,
            game_over_on_max=game_over_on_max,
            loc=self._make_loc(header)
        )

    def _parse_counter(self, name: str, entity_id: str, flags: list[str], header: Line):
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
        props = self._collect_properties(primary_key="start")

        # Primary value is start, parse as int
        start_str = props.get("start", "50")
        try:
            start = int(start_str)
        except ValueError:
            start = 50

        # Check for flags in header
        flags_lower = [f.lower() for f in flags]
        killer = "killer" in flags_lower
        keep = "keep" in flags_lower

        # Parse source list (for virtual counters)
        source: tuple[str, ...] = ()
        if "source" in props:
            source = tuple(self._parse_reference_list(props["source"]))

        # Parse aggregate type
        aggregate: Optional[AggregateType] = None
        if "aggregate" in props:
            agg_str = props["aggregate"].lower().strip()
            if agg_str == "average":
                aggregate = AggregateType.AVERAGE
            elif agg_str == "sum":
                aggregate = AggregateType.SUM
            elif agg_str == "min":
                aggregate = AggregateType.MIN
            elif agg_str == "max":
                aggregate = AggregateType.MAX

        # Parse track type
        track: Optional[TrackType] = None
        if "track" in props:
            track_str = props["track"].lower().strip()
            if track_str == "yes":
                track = TrackType.YES
            elif track_str == "no":
                track = TrackType.NO

        counter = Counter(
            id=entity_id,
            name=name,
            icon=props.get("icon", ""),
            start=start,
            color=props.get("color", ""),
            killer=killer,
            keep=keep,
            source=source,
            aggregate=aggregate,
            track=track,
            loc=self._make_loc(header)
        )
        self._counters.append(counter)

    def _parse_flag(self, name: str, entity_id: str, flags: list[str], header: Line):
        """Parse a flag entity."""
        props = self._collect_properties()

        # Check for keep flag in header
        flags_lower = [f.lower() for f in flags]
        keep = "keep" in flags_lower

        # Parse bind property (strip character: prefix if present)
        bind = None
        if "bind" in props:
            bind = self._strip_type_prefix(props["bind"], "character")

        flag = Flag(
            id=entity_id,
            name=name,
            bind=bind,
            keep=keep,
            loc=self._make_loc(header)
        )
        self._flags.append(flag)

    def _parse_variant(self, name: str, entity_id: str, header: Line):
        """Parse a variant entity (emotion, state, pose)."""
        props = self._collect_properties()

        variant = Variant(
            id=entity_id,
            name=name,
            prompt=self._strip_quotes(props.get("prompt", "")),
            loc=self._make_loc(header)
        )
        self._variants.append(variant)

    def _parse_character(self, name: str, entity_id: str, header: Line):
        """Parse a character entity."""
        props = self._collect_properties()

        character = Character(
            id=entity_id,
            name=name,
            prompt=self._strip_quotes(props.get("prompt", "")),
            loc=self._make_loc(header)
        )
        self._characters.append(character)

    def _parse_card(self, name: str, entity_id: str, flags: list[str], header: Line):
        """Parse a card entity. Primary field: text"""
        bearer: Optional[Bearer] = None
        text: str = ""
        require: list[Condition] = []
        weights: list[Weight] = []
        lockturn: Lockturn = None
        choices: list[Choice] = []

        # Check for ring flag in header
        flags_lower = [f.lower() for f in flags]
        ring = "ring" in flags_lower

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
                choice = self._parse_choice(line)
                choices.append(choice)
                self._advance()
                continue

            if line.type == LineType.PROPERTY:
                key = line.key
                value = line.value or ""

                if key == "bearer":
                    bearer = self._parse_bearer(value, line)

                elif key == "require":
                    require = self._parse_condition_list(value, line)

                elif key == "weight":
                    if value:
                        weight = self._parse_weight_line(value, line)
                        if weight:
                            weights.append(weight)

                elif key == "lockturn":
                    value_lower = value.lower().strip()
                    if value_lower == "once":
                        lockturn = LOCKTURN_ONCE
                    elif value_lower == "dispose":
                        lockturn = LOCKTURN_DISPOSE
                    else:
                        try:
                            lockturn = int(value)
                        except ValueError:
                            raise self._error(
                                f"Gecersiz lockturn degeri: '{value}' (tam sayi, 'once' veya 'dispose' olmali)",
                                line
                            )

                self._advance()
                continue

            if line.type == LineType.INDENTED:
                weight = self._parse_weight_line(line.value, line)
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
            ring=ring,
            loc=self._make_loc(header)
        )
        self._cards.append(card)

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
        """
        Parse bearer value with optional variant.

        Format: 'character:sadrazam (variant:angry)' -> Bearer('sadrazam', 'angry')
        No variant: 'character:sadrazam' -> Bearer('sadrazam', None)
        """
        value = value.strip()
        variant_id: Optional[str] = None

        # Check if there's a parenthesis with variant
        if '(' in value and value.endswith(')'):
            paren_start = value.index('(')
            character = value[:paren_start].strip()
            variant = value[paren_start + 1:-1].strip()

            # Strip prefix from character if present
            character_id = self._strip_type_prefix(character, 'character')
            # Strip prefix from variant if present
            variant_id = self._strip_type_prefix(variant, 'variant')
        else:
            # No variant - just strip prefix if present
            character_id = self._strip_type_prefix(value, 'character')

        return Bearer(
            character_id=character_id,
            variant_id=variant_id,
            loc=self._make_loc(line)
        )

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
                raise self._error(f"Bilinmeyen komut: '{part}'", line)

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
        Parse a single command. Supported formats:
        - 'card:next-event'           : queue a card
        - 'card:next-event@5'         : queue a card after 5 turns
        - '[card:_a, card:_b]'        : conditional branch (first matching card)
        - '+flag:winter'              : add flag
        - '-flag:winter'              : remove flag
        - 'counter:hazine 20'         : add 20 to counter
        - 'counter:hazine -10'        : subtract 10 from counter
        - 'counter:hazine 10?30'      : add random 10-30 to counter
        - 'counter:hazine -20?-1'     : subtract random 1-20 from counter
        - 'counter:hazine -5?10'      : add random between -5 and +10
        """
        part = part.strip()
        loc = self._make_loc(line)

        # Branch syntax: [card:_a, card:_b, card:_c]
        if part.startswith('[') and part.endswith(']'):
            inner = part[1:-1].strip()
            card_ids = []
            for ref in inner.split(','):
                ref = ref.strip()
                if ref.lower().startswith('card:'):
                    card_ids.append(ref[5:])  # Strip 'card:' prefix
                elif ref:
                    card_ids.append(ref)  # Allow without prefix too
            if card_ids:
                return CardBranch(card_ids=tuple(card_ids), loc=loc)

        # Card commands: 'card:id' (queue) or 'card:id@19' (timed)
        if part.lower().startswith('card:'):
            rest = part[5:].strip()
            # Check for timed syntax: card:id@N
            if '@' in rest:
                at_pos = rest.index('@')
                card_id = rest[:at_pos].strip()
                delay_str = rest[at_pos + 1:].strip()
                delay = self._parse_unsigned_int(delay_str)
                if delay is not None:
                    return CardTimed(card_id=card_id, delay=delay, loc=loc)
            else:
                # Immediate queue
                return CardQueue(card_id=rest, loc=loc)

        # Flag add: '+flag:winter'
        if part.lower().startswith('+flag:'):
            flag_id = part[6:].strip()
            return FlagSet(flag_id=flag_id, loc=loc)

        # Flag remove: '-flag:winter'
        if part.lower().startswith('-flag:'):
            flag_id = part[6:].strip()
            return FlagClear(flag_id=flag_id, loc=loc)

        # Counter modify: 'counter:hazine 20' or 'counter:hazine -10?30'
        # Value includes the sign (positive or negative)
        if part.lower().startswith('counter:'):
            rest = part[8:]  # After 'counter:'
            if ' ' in rest:
                tokens = rest.split(None, 1)
                if len(tokens) == 2:
                    counter_id = tokens[0]
                    value = self._parse_value_or_range(tokens[1], line)
                    if value:
                        return CounterMod(counter_id=counter_id, value=value, loc=loc)

        # Trigger commands: 'trigger:response "text"' or 'trigger:sound "file.wav"'
        if part.lower().startswith('trigger:'):
            rest = part[8:]  # After 'trigger:'
            # Find trigger type (response, sound) and value (quoted string)
            if ' ' in rest:
                space_pos = rest.index(' ')
                trigger_type = rest[:space_pos].strip()
                value_str = rest[space_pos + 1:].strip()
                # Strip quotes from value
                value = self._strip_quotes(value_str)
                return Trigger(trigger_type=trigger_type, value=value, loc=loc)

        return None

    def _parse_value_or_range(self, s: str, line: Line) -> Optional[ValueOrRange]:
        """
        Parse a value or range.

        Formats:
        - '20'    -> FixedValue(20)
        - '10?30' -> RangeValue(10, 30)    # 10 to 30
        - '10?'   -> RangeValue(0, 10)     # 0 to 10 (shorthand)
        - '?20'   -> RangeValue(0, 20)     # 0 to 20 (shorthand)
        - '-10?'  -> RangeValue(-10, 0)    # -10 to 0 (negative shorthand)
        """
        s = s.strip()
        loc = self._make_loc(line)

        # Check for range syntax with ?
        if '?' in s:
            parts = s.split('?')
            if len(parts) == 2:
                left = parts[0].strip()
                right = parts[1].strip()

                try:
                    # Case: '10?30' -> range 10 to 30
                    if left and right:
                        min_val = int(left)
                        max_val = int(right)
                        return RangeValue(min_value=min_val, max_value=max_val, loc=loc)

                    # Case: '10?' -> range 0 to 10 (or -10 to 0 if negative)
                    elif left and not right:
                        val = int(left)
                        if val >= 0:
                            return RangeValue(min_value=0, max_value=val, loc=loc)
                        else:
                            return RangeValue(min_value=val, max_value=0, loc=loc)

                    # Case: '?20' -> range 0 to 20
                    elif not left and right:
                        max_val = int(right)
                        return RangeValue(min_value=0, max_value=max_val, loc=loc)

                except ValueError:
                    return None
        else:
            # Fixed value
            try:
                return FixedValue(value=int(s), loc=loc)
            except ValueError:
                return None

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
        """
        Parse weight with optional condition.
        Examples:
        - '1.0'                              -> Weight(1.0, None)
        - '2.0 when counter:hazine < 30'     -> Weight(2.0, CounterCondition(...))
        - '0 when flag:war'                  -> Weight(0.0, FlagCondition(...))
        """
        value = value.strip()
        if not value:
            return None

        loc = self._make_loc(line)

        # Check if there's a 'when' keyword
        when_pos = value.lower().find(' when ')
        if when_pos > 0:
            weight_str = value[:when_pos].strip()
            condition_str = value[when_pos + 6:].strip()  # 6 = len(' when ')
            try:
                weight_value = float(weight_str)
                condition = self._parse_single_condition(condition_str, line)
                return Weight(value=weight_value, condition=condition, loc=loc)
            except ValueError:
                raise self._error(f"Gecersiz weight degeri: '{weight_str}'", line)
        else:
            # No condition, just a number
            try:
                return Weight(value=float(value), condition=None, loc=loc)
            except ValueError:
                raise self._error(f"Gecersiz weight degeri: '{value}'", line)

    def _parse_flag_list(self, value: str) -> list[str]:
        """
        Parse a list of flags.
        - 'flag:intro'              -> ['intro']
        - 'flag:intro, flag:war'    -> ['intro', 'war']
        - '[flag:intro, flag:war]'  -> ['intro', 'war']  (bracketed list)
        """
        flags = []
        value = value.strip()

        # Strip brackets if present
        if value.startswith('[') and value.endswith(']'):
            value = value[1:-1].strip()

        # Split by comma
        parts = value.split(',')

        for part in parts:
            part = part.strip()
            # Remove flag: prefix
            if part.lower().startswith('flag:'):
                part = part[5:]
            if part:
                flags.append(part)

        return flags

    def _parse_reference_list(self, value: str) -> list[str]:
        """
        Parse a bracketed list of typed references.
        - '[counter:a, counter:b]'    -> ['counter:a', 'counter:b']
        - '[character:merchant]'      -> ['character:merchant']
        - 'counter:a, counter:b'      -> ['counter:a', 'counter:b']  (no brackets)

        Preserves the type prefix for later validation.
        """
        refs = []
        value = value.strip()

        # Strip brackets if present
        if value.startswith('[') and value.endswith(']'):
            value = value[1:-1].strip()

        # Split by comma
        parts = value.split(',')

        for part in parts:
            part = part.strip()
            if part:
                refs.append(part)

        return refs

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

    def _parse_single_condition(self, part: str, line: Line) -> Optional[Condition]:
        """
        Parse a single condition.

        - 'flag:tower'              -> FlagCondition('tower')
        - '!flag:war'               -> FlagCondition('war', negated=True)
        - 'counter:hazine < 30'     -> CounterCondition('hazine', '<', 30)
        - 'counter:ordu > 50'       -> CounterCondition('ordu', '>', 50)
        - 'counter:nb_war = 1'      -> CounterCondition('nb_war', '=', 1)
        """
        part = part.strip()
        loc = self._make_loc(line)

        # Check for negation
        negated = False
        if part.startswith('!'):
            negated = True
            part = part[1:].strip()

        # Counter condition: 'counter:hazine < 30' or 'counter:nb_war = 1'
        # Supports: <, >, =, <=, >=
        if '<' in part or '>' in part or '=' in part:
            # Find the operator (check two-char operators first)
            op_pos = -1
            op = ''
            for i, ch in enumerate(part):
                if ch in '<>':
                    # Check for <= or >=
                    if i + 1 < len(part) and part[i + 1] == '=':
                        op_pos = i
                        op = part[i:i+2]  # '<=' or '>='
                        break
                    else:
                        op_pos = i
                        op = ch
                        break
                elif ch == '=':
                    op_pos = i
                    op = ch
                    break

            if op_pos > 0:
                left = part[:op_pos].strip()
                right = part[op_pos + len(op):].strip()

                counter_id = self._strip_type_prefix(left, 'counter')
                try:
                    value = int(right)
                    return CounterCondition(counter_id=counter_id, operator=op, value=value, loc=loc)
                except ValueError:
                    pass

        # Flag condition: 'flag:tower' or just 'tower' (legacy)
        flag_id = self._strip_type_prefix(part, 'flag')
        return FlagCondition(flag_id=flag_id, negated=negated, loc=loc)

    def _strip_quotes(self, value: str) -> str:
        """Remove surrounding quotes from a string."""
        value = value.strip()
        if len(value) >= 2:
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                return value[1:-1]
        return value

    def _collect_properties(self, primary_key: str = "_primary") -> dict[str, str]:
        """
        Collect all property lines until next entity or special line.

        The `> value` syntax sets the primary_key field.
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
