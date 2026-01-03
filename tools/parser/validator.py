"""
Semantic validator for TahtLang.

The parser handles syntax, the validator handles semantics:
- Are all referenced counters defined?
- Are all referenced characters defined?
- Are all referenced flags defined?
- Are all referenced variants defined?
- Are all queued cards defined?
- Are imports valid and non-circular?
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re

from .ast import (
    Game, Card, Choice, Bearer, Weight, Counter, Import,
    Settings, Flag, Variant, Character,
    # Commands
    CounterMod, FlagSet, FlagClear, CardQueue, CardBranch, CardTimed,
    Command,
    # Conditions
    FlagCondition, CounterCondition, Condition,
    # Source location
    SourceLocation as ASTLocation
)
from .errors import ValidationError, SourceLocation
from .parser import Parser


@dataclass
class ValidationResult:
    """Result of validation with all errors found."""
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, message: str, loc: Optional[ASTLocation] = None):
        error_loc = None
        if loc:
            error_loc = SourceLocation(loc.file, loc.line)
        self.errors.append(ValidationError(message, error_loc))

    def add_warning(self, message: str):
        self.warnings.append(message)


class Validator:
    """
    Semantic validator for TahtLang games.

    Usage:
        validator = Validator()
        result = validator.validate(game)
        if not result.is_valid:
            for error in result.errors:
                print(error)
    """

    def __init__(self):
        self.result = ValidationResult()
        self.game: Optional[Game] = None

    def validate(self, game: Game) -> ValidationResult:
        """Validate a parsed game and return all errors found."""
        self.result = ValidationResult()
        self.game = game

        # Check for camelCase in IDs (should use snake_case)
        for counter in game.counters:
            self._check_snake_case(counter.id, "counter", counter.loc)
        for flag in game.flags:
            self._check_snake_case(flag.id, "flag", flag.loc)
        for variant in game.variants:
            self._check_snake_case(variant.id, "variant", variant.loc)
        for character in game.characters:
            self._check_snake_case(character.id, "character", character.loc)
        for card in game.cards:
            self._check_snake_case(card.id, "card", card.loc)

        # Collect all defined IDs and check for duplicates
        counter_ids = {c.id for c in game.counters}
        flag_ids = {f.id for f in game.flags}
        variant_ids = {v.id for v in game.variants}
        character_ids = {c.id for c in game.characters}

        # Check for duplicate card IDs
        card_ids: set[str] = set()
        for card in game.cards:
            if card.id in card_ids:
                self.result.add_error(
                    f"Duplicate kart ID'si: '{card.id}'",
                    card.loc
                )
            card_ids.add(card.id)

        # Validate each card
        for card in game.cards:
            self._validate_card(
                card,
                counter_ids=counter_ids,
                flag_ids=flag_ids,
                variant_ids=variant_ids,
                character_ids=character_ids,
                card_ids=card_ids
            )

        # Validate starting_flags in settings
        if game.settings:
            for flag in game.settings.starting_flags:
                if flag not in flag_ids:
                    self.result.add_error(
                        f"Tanimsiz flag: '{flag}' (starting_flags icinde)",
                        game.settings.loc
                    )

        # Validate flag bindings
        for flag in game.flags:
            if flag.bind:
                if flag.bind not in character_ids:
                    self.result.add_error(
                        f"Tanimsiz karakter: '{flag.bind}' (flag: {flag.id}, bind)",
                        flag.loc
                    )

        # Validate virtual counters
        for counter in game.counters:
            self._validate_virtual_counter(counter, counter_ids, character_ids)

        return self.result

    def _validate_virtual_counter(
        self,
        counter: Counter,
        counter_ids: set[str],
        character_ids: set[str]
    ):
        """Validate virtual counter source references."""
        if not counter.source:
            # No source = regular counter, skip
            return

        # If source is set, need either aggregate or track
        if counter.aggregate is None and counter.track is None:
            self.result.add_error(
                f"Virtual counter '{counter.id}' has source but no aggregate or track property",
                counter.loc
            )
            return

        # Aggregate counter: source should be counter references
        if counter.aggregate is not None:
            for ref in counter.source:
                if ref.lower().startswith('counter:'):
                    ref_id = ref[8:]  # Strip 'counter:' prefix
                    if ref_id not in counter_ids:
                        self.result.add_error(
                            f"Tanimsiz counter: '{ref_id}' (counter: {counter.id}, source)",
                            counter.loc
                        )
                else:
                    self.result.add_error(
                        f"Aggregate counter source must be counter refs, got: '{ref}' (counter: {counter.id})",
                        counter.loc
                    )

        # Tracking counter: source should be character references
        if counter.track is not None:
            for ref in counter.source:
                if ref.lower().startswith('character:'):
                    ref_id = ref[10:]  # Strip 'character:' prefix
                    if ref_id not in character_ids:
                        self.result.add_error(
                            f"Tanimsiz karakter: '{ref_id}' (counter: {counter.id}, source)",
                            counter.loc
                        )
                else:
                    self.result.add_error(
                        f"Tracking counter source must be character refs, got: '{ref}' (counter: {counter.id})",
                        counter.loc
                    )

    def _validate_card(
        self,
        card: Card,
        counter_ids: set[str],
        flag_ids: set[str],
        variant_ids: set[str],
        character_ids: set[str],
        card_ids: set[str]
    ):
        """Validate a single card."""
        # Validate ring card rules
        if card.ring:
            # Ring cards must have ID starting with '_'
            if not card.id.startswith('_'):
                self.result.add_error(
                    f"Ring kart ID'si '_' ile baslamali: '{card.id}' -> '_{card.id}'",
                    card.loc
                )
            # Ring cards CAN have weight, lockturn, and require
            # This allows Reigns-style conditional card variants:
            # - Same ID, different conditions → runtime picks matching one
            # - Weight determines selection probability among matching cards
            # - Lockturn provides cooldown after showing
        else:
            # Non-ring cards with '_' prefix should have ring modifier
            if card.id.startswith('_'):
                self.result.add_error(
                    f"'_' ile baslayan kart ID'si ring modifier gerektirir: '{card.id}'",
                    card.loc
                )

        # Validate bearer reference
        if card.bearer:
            if card.bearer.character_id not in character_ids:
                self.result.add_error(
                    f"Tanimsiz bearer: '{card.bearer.character_id}' (kart: {card.id})",
                    card.bearer.loc or card.loc
                )

            # Validate variant reference
            if card.bearer.variant_id and card.bearer.variant_id not in variant_ids:
                self.result.add_error(
                    f"Tanimsiz variant: '{card.bearer.variant_id}' (kart: {card.id})",
                    card.bearer.loc or card.loc
                )

        # Validate conditions in card.require
        for condition in card.require:
            self._validate_condition(
                condition,
                counter_ids, flag_ids,
                card.id
            )

        # Validate weight conditions
        for weight in card.weights:
            if weight.condition:
                self._validate_condition(
                    weight.condition,
                    counter_ids, flag_ids,
                    card.id
                )

        # Validate choices
        for choice in card.choices:
            self._validate_choice(
                choice, card.id,
                counter_ids, flag_ids, card_ids
            )

        # Validate text interpolation in card text
        if card.text:
            self._validate_text_interpolation(
                card.text, card.id, character_ids, card.loc
            )

    def _validate_choice(
        self,
        choice: Choice,
        card_id: str,
        counter_ids: set[str],
        flag_ids: set[str],
        card_ids: set[str]
    ):
        """Validate a card choice and its commands."""
        for cmd in choice.commands:
            self._validate_command(
                cmd, card_id, choice.label,
                counter_ids, flag_ids, card_ids
            )

    def _validate_command(
        self,
        cmd: Command,
        card_id: str,
        choice_label: str,
        counter_ids: set[str],
        flag_ids: set[str],
        card_ids: set[str]
    ):
        """Validate a single command."""
        context = f"kart: {card_id}, secenek: '{choice_label}'"

        if isinstance(cmd, CounterMod):
            if cmd.counter_id not in counter_ids:
                self.result.add_error(
                    f"Tanimsiz counter: '{cmd.counter_id}' ({context})",
                    cmd.loc
                )

        elif isinstance(cmd, FlagSet):
            if cmd.flag_id not in flag_ids:
                self.result.add_error(
                    f"Tanimsiz flag: '{cmd.flag_id}' ({context})",
                    cmd.loc
                )

        elif isinstance(cmd, FlagClear):
            if cmd.flag_id not in flag_ids:
                self.result.add_error(
                    f"Tanimsiz flag: '{cmd.flag_id}' ({context})",
                    cmd.loc
                )

        elif isinstance(cmd, CardQueue):
            if cmd.card_id not in card_ids:
                self.result.add_error(
                    f"Tanimsiz kart: '{cmd.card_id}' ({context})",
                    cmd.loc
                )

        elif isinstance(cmd, CardBranch):
            for branch_card_id in cmd.card_ids:
                if branch_card_id not in card_ids:
                    self.result.add_error(
                        f"Tanimsiz kart: '{branch_card_id}' ({context}, branch)",
                        cmd.loc
                    )

        elif isinstance(cmd, CardTimed):
            if cmd.card_id not in card_ids:
                self.result.add_error(
                    f"Tanimsiz kart: '{cmd.card_id}' ({context})",
                    cmd.loc
                )

    def _validate_condition(
        self,
        condition: Condition,
        counter_ids: set[str],
        flag_ids: set[str],
        card_id: str
    ):
        """Validate a condition (from require: or weight when)."""
        if isinstance(condition, FlagCondition):
            if condition.flag_id not in flag_ids:
                self.result.add_error(
                    f"Tanimsiz flag: '{condition.flag_id}' (kart: {card_id}, condition)",
                    condition.loc
                )

        elif isinstance(condition, CounterCondition):
            if condition.counter_id not in counter_ids:
                self.result.add_error(
                    f"Tanimsiz counter: '{condition.counter_id}' (kart: {card_id}, condition)",
                    condition.loc
                )

    def _validate_text_interpolation(
        self,
        text: str,
        card_id: str,
        character_ids: set[str],
        loc: Optional[ASTLocation] = None
    ):
        """Validate {character:X} references in card text."""
        # Find all {character:X} patterns
        pattern = r'\{character:([a-z_][a-z0-9_]*)\}'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            char_id = match.group(1)
            if char_id not in character_ids:
                self.result.add_error(
                    f"Tanimsiz karakter metinde: '{{character:{char_id}}}' (kart: {card_id})",
                    loc
                )


    def _check_snake_case(self, id_str: str, entity_type: str, loc: Optional[ASTLocation]):
        """Check if ID uses snake_case. Warn if camelCase detected."""
        # Skip ring card prefix
        check_str = id_str[1:] if id_str.startswith('_') else id_str

        # Look for lowercase letter followed by uppercase (camelCase pattern)
        if re.search(r'[a-z][A-Z]', check_str):
            # Suggest snake_case version
            snake_case = re.sub(r'([a-z])([A-Z])', r'\1_\2', id_str).lower()
            self.result.add_error(
                f"ID'lerde buyuk harf kullanilamaz, snake_case kullanin: "
                f"'{id_str}' -> '{snake_case}' ({entity_type})",
                loc
            )


def validate_game(game: Game) -> ValidationResult:
    """Convenience function to validate a game."""
    validator = Validator()
    return validator.validate(game)


def resolve_imports(filepath: str) -> tuple[Game, ValidationResult]:
    """
    Parse a .tahta file and recursively resolve all imports.

    Returns a merged Game with all entities from imported files,
    and a ValidationResult with any import-related errors.

    Usage:
        game, result = resolve_imports("main.tahta")
        if result.is_valid:
            # game contains all entities from main + imported files
    """
    result = ValidationResult()
    parser = Parser()

    # Track visited files to detect circular imports
    visited: set[str] = set()
    # Track import chain for error messages
    import_chain: list[str] = []

    # Collect all entities
    all_settings: Optional[Settings] = None
    all_counters: list[Counter] = []
    all_flags: list[Flag] = []
    all_variants: list[Variant] = []
    all_characters: list[Character] = []
    all_cards: list[Card] = []
    all_imports: list[Import] = []

    def resolve_file(file_path: str, base_dir: Path):
        nonlocal all_settings

        # Resolve to absolute path
        abs_path = (base_dir / file_path).resolve()
        abs_path_str = str(abs_path)

        # Check for circular import
        if abs_path_str in visited:
            # Find where in the chain the cycle starts
            if abs_path_str in import_chain:
                cycle_start = import_chain.index(abs_path_str)
                cycle = " -> ".join(import_chain[cycle_start:] + [abs_path_str])
                result.add_error(f"Circular import detected: {cycle}")
            return

        # Check file exists
        if not abs_path.exists():
            result.add_error(f"Import file not found: {file_path}")
            return

        # Mark as visited and add to chain
        visited.add(abs_path_str)
        import_chain.append(abs_path_str)

        try:
            # Parse the file
            game = parser.parse_file(abs_path_str)

            # Collect entities
            if game.settings and all_settings is None:
                all_settings = game.settings
            all_counters.extend(game.counters)
            all_flags.extend(game.flags)
            all_variants.extend(game.variants)
            all_characters.extend(game.characters)
            all_cards.extend(game.cards)
            all_imports.extend(game.imports)

            # Recursively resolve imports
            file_dir = abs_path.parent
            for imp in game.imports:
                resolve_file(imp.path, file_dir)

        except Exception as e:
            result.add_error(f"Error parsing {file_path}: {str(e)}")
        finally:
            # Remove from chain when done
            import_chain.pop()

    # Start resolution from the main file
    main_path = Path(filepath).resolve()
    resolve_file(main_path.name, main_path.parent)

    # Create merged game
    merged_game = Game(
        imports=tuple(all_imports),
        settings=all_settings,
        counters=tuple(all_counters),
        flags=tuple(all_flags),
        variants=tuple(all_variants),
        characters=tuple(all_characters),
        cards=tuple(all_cards)
    )

    return merged_game, result


def validate_with_imports(filepath: str) -> ValidationResult:
    """
    Parse a file with imports and validate the merged result.

    This is the main entry point for validating a multi-file project.
    """
    # First resolve all imports
    game, import_result = resolve_imports(filepath)

    # If import resolution failed, return those errors
    if not import_result.is_valid:
        return import_result

    # Now validate the merged game
    validation_result = validate_game(game)

    # Merge results
    validation_result.errors = import_result.errors + validation_result.errors
    validation_result.warnings = import_result.warnings + validation_result.warnings

    return validation_result
