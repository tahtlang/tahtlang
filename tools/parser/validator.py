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

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .ast import (
    Card,
    CardBranch,
    CardQueue,
    CardTimed,
    Character,
    Choice,
    Command,
    Condition,
    Counter,
    CounterCondition,
    # Commands
    CounterMod,
    Flag,
    FlagClear,
    # Conditions
    FlagCondition,
    FlagSet,
    Game,
    Import,
    Settings,
    # Source location
    SourceLocation,
    Variant,
)
from .errors import ParseError, ValidationError
from .parser import Parser


@dataclass
class ValidationResult:
    """Result of validation with all errors found."""

    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, message: str, loc: Optional[SourceLocation] = None):
        self.errors.append(ValidationError(message, loc))

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

        self._check_all_snake_cases(game)

        # Collect all defined IDs and check for duplicates
        ids = self._collect_and_check_ids(game)

        # Validate each card
        for card in game.cards:
            self._validate_card(card, ids)

        # Validate starting_flags in settings
        if game.settings:
            self._validate_starting_flags(game.settings, ids["flags"])

        # Validate flag bindings
        for flag in game.flags:
            if flag.bind and flag.bind not in ids["characters"]:
                self.result.add_error(
                    f"Undefined character: '{flag.bind}' "
                    f"(flag: {flag.id}, bind)",
                    flag.loc,
                )

        # Validate virtual counters
        for counter in game.counters:
            self._validate_virtual_counter(
                counter, ids["counters"], ids["characters"]
            )

        return self.result

    def _check_all_snake_cases(self, game):
        for collection, type_name in [
            (game.counters, "counter"),
            (game.flags, "flag"),
            (game.variants, "variant"),
            (game.characters, "character"),
            (game.cards, "card"),
        ]:
            for entity in collection:
                self._check_snake_case(entity.id, type_name, entity.loc)

    def _collect_and_check_ids(self, game):
        return {
            "counters": self._check_duplicate_ids(game.counters, "counter"),
            "flags": self._check_duplicate_ids(game.flags, "flag"),
            "variants": self._check_duplicate_ids(game.variants, "variant"),
            "characters": self._check_duplicate_ids(
                game.characters, "character"
            ),
            "cards": self._check_duplicate_ids(game.cards, "card"),
        }

    def _validate_starting_flags(self, settings, flag_ids):
        for flag in settings.starting_flags:
            if flag not in flag_ids:
                self.result.add_error(
                    f"Undefined flag: '{flag}' (in starting_flags)",
                    settings.loc,
                )

    def _check_duplicate_ids(
        self, entities, entity_type_name: str
    ) -> set[str]:
        """Check for duplicate IDs and return a set of all IDs."""
        ids: set[str] = set()
        for entity in entities:
            if entity.id in ids:
                self.result.add_error(
                    f"Duplicate {entity_type_name} ID: '{entity.id}'",
                    entity.loc,
                )
            ids.add(entity.id)
        return ids

    def _validate_virtual_counter(
        self, counter: Counter, counter_ids: set[str], character_ids: set[str]
    ):
        """Validate virtual counter source references."""
        if not counter.source:
            return

        if counter.aggregate is None and counter.track is None:
            self.result.add_error(
                f"Virtual counter '{counter.id}' has source "
                "but no aggregate or track property",
                counter.loc,
            )
            return

        if counter.aggregate is not None:
            self._validate_aggregate_counter(counter, counter_ids)

        if counter.track is not None:
            self._validate_tracking_counter(counter, character_ids)

    def _validate_aggregate_counter(self, counter, counter_ids):
        for ref in counter.source:
            if ref.startswith("counter:"):
                ref_id = ref[8:]
                if ref_id not in counter_ids:
                    self.result.add_error(
                        f"Undefined counter: '{ref_id}' "
                        f"(counter: {counter.id}, source)",
                        counter.loc,
                    )
            else:
                self.result.add_error(
                    "Aggregate counter source must be counter refs, "
                    f"got: '{ref}' (counter: {counter.id})",
                    counter.loc,
                )

    def _validate_tracking_counter(self, counter, character_ids):
        for ref in counter.source:
            if ref.startswith("character:"):
                ref_id = ref[10:]
                if ref_id not in character_ids:
                    self.result.add_error(
                        f"Undefined character: '{ref_id}' "
                        f"(counter: {counter.id}, source)",
                        counter.loc,
                    )
            else:
                self.result.add_error(
                    "Tracking counter source must be character refs, "
                    f"got: '{ref}' (counter: {counter.id})",
                    counter.loc,
                )

    def _validate_card(self, card: Card, ids: dict):
        """Validate a single card."""
        self._validate_card_id_and_ring(card)

        if card.bearer:
            self._validate_bearer(card, ids["characters"], ids["variants"])

        # Validate conditions in card.require
        for condition in card.require:
            self._validate_condition(
                condition, ids["counters"], ids["flags"], card.id
            )

        # Validate weight conditions
        for weight in card.weights:
            if weight.condition:
                self._validate_condition(
                    weight.condition, ids["counters"], ids["flags"], card.id
                )

        # Validate choices
        for choice in card.choices:
            self._validate_choice(choice, card.id, ids)

        # Validate text interpolation in card text
        if card.text:
            self._validate_text_interpolation(
                card.text, card.id, ids["characters"], card.loc
            )

    def _validate_card_id_and_ring(self, card):
        if card.ring:
            if not card.id.startswith("_"):
                self.result.add_error(
                    "Ring card ID must start with '_': "
                    f"'{card.id}' -> '_{card.id}'",
                    card.loc,
                )
        elif card.id.startswith("_"):
            self.result.add_error(
                "Card ID starting with '_' requires ring modifier: "
                f"'{card.id}'",
                card.loc,
            )

    def _validate_bearer(self, card, character_ids, variant_ids):
        if card.bearer.character_id not in character_ids:
            self.result.add_error(
                f"Undefined bearer: '{card.bearer.character_id}' "
                f"(card: {card.id})",
                card.bearer.loc or card.loc,
            )

        v_id = card.bearer.variant_id
        if v_id and v_id not in variant_ids:
            self.result.add_error(
                f"Undefined variant: '{v_id}' " f"(card: {card.id})",
                card.bearer.loc or card.loc,
            )

    def _validate_choice(
        self,
        choice: Choice,
        card_id: str,
        ids: dict,
    ):
        """Validate a card choice and its commands."""
        for cmd in choice.commands:
            self._validate_command(cmd, card_id, choice.label, ids)

    def _validate_command(
        self,
        cmd: Command,
        card_id: str,
        choice_label: str,
        ids: dict,
    ):
        """Validate a single command."""
        context = f"card: {card_id}, choice: '{choice_label}'"

        if isinstance(cmd, CounterMod):
            self._check_id_ref(
                cmd.counter_id,
                ids["counters"],
                f"Undefined counter: '{{}}' ({context})",
                cmd.loc,
            )
        elif isinstance(cmd, (FlagSet, FlagClear)):
            self._check_id_ref(
                cmd.flag_id,
                ids["flags"],
                f"Undefined flag: '{{}}' ({context})",
                cmd.loc,
            )
        elif isinstance(cmd, (CardQueue, CardTimed)):
            self._check_id_ref(
                cmd.card_id,
                ids["cards"],
                f"Undefined card: '{{}}' ({context})",
                cmd.loc,
            )
        elif isinstance(cmd, CardBranch):
            for branch_card_id in cmd.card_ids:
                self._check_id_ref(
                    branch_card_id,
                    ids["cards"],
                    f"Undefined card: '{{}}' ({context}, branch)",
                    cmd.loc,
                )

    def _check_id_ref(self, ref_id, id_set, msg_template, loc):
        if ref_id not in id_set:
            self.result.add_error(msg_template.format(ref_id), loc)

    def _validate_condition(
        self,
        condition: Condition,
        counter_ids: set[str],
        flag_ids: set[str],
        card_id: str,
    ):
        """Validate a condition (from require: or weight when)."""
        if isinstance(condition, FlagCondition):
            if condition.flag_id not in flag_ids:
                self.result.add_error(
                    f"Undefined flag: '{condition.flag_id}' "
                    f"(card: {card_id}, condition)",
                    condition.loc,
                )

        elif isinstance(condition, CounterCondition):
            if condition.counter_id not in counter_ids:
                self.result.add_error(
                    f"Undefined counter: '{condition.counter_id}' "
                    f"(card: {card_id}, condition)",
                    condition.loc,
                )

    def _validate_text_interpolation(
        self,
        text: str,
        card_id: str,
        character_ids: set[str],
        loc: Optional[SourceLocation] = None,
    ):
        """Validate {character:X} references in card text."""
        # Find all {character:X} patterns
        pattern = r"\{character:([a-z_][a-z0-9_]*)\}"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            char_id = match.group(1)
            if char_id not in character_ids:
                self.result.add_error(
                    "Undefined character in text: "
                    f"'{{character:{char_id}}}' (card: {card_id})",
                    loc,
                )

    def _check_snake_case(
        self, id_str: str, entity_type: str, loc: Optional[SourceLocation]
    ):
        """Check if ID uses snake_case. Warn if camelCase detected."""
        # Skip ring card prefix
        check_str = id_str[1:] if id_str.startswith("_") else id_str

        # Look for lowercase letter followed by uppercase (camelCase pattern)
        if re.search(r"[a-z][A-Z]", check_str):
            # Suggest snake_case version
            snake_case = re.sub(r"([a-z])([A-Z])", r"\1_\2", id_str).lower()
            self.result.add_error(
                f"IDs must use snake_case, no uppercase allowed: "
                f"'{id_str}' -> '{snake_case}' ({entity_type})",
                loc,
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
                cycle = " -> ".join(
                    import_chain[cycle_start:] + [abs_path_str]
                )
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

        except (ParseError, OSError) as e:
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
        cards=tuple(all_cards),
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
    validation_result.warnings = (
        import_result.warnings + validation_result.warnings
    )

    return validation_result
