"""Tests for the semantic validator."""


from tools.parser import Parser, ValidationResult, validate_game


def validate(source: str) -> ValidationResult:
    """Helper: parse and validate source, return result."""
    game = Parser().parse_string(source, "<test>")
    return validate_game(game)


def assert_valid(source: str):
    """Assert source validates without errors."""
    result = validate(source)
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"


def assert_errors(source: str, *fragments: str):
    """Assert source has validation errors containing given fragments."""
    result = validate(source)
    assert not result.is_valid, "Expected validation errors"
    error_messages = " ".join(str(e) for e in result.errors)
    for fragment in fragments:
        assert fragment in error_messages, (
            f"Expected '{fragment}' in errors, got: {error_messages}"
        )


# =========================================================================
# Valid games
# =========================================================================


MINIMAL_VALID = (
    "Treasury (counter:treasury, killer)\n"
    "Advisor (character:advisor)\n"
    "Welcome (card:welcome)\n"
    "\tbearer: character:advisor\n"
    "\tweight: 1.0\n"
    "\t> Welcome!\n"
    "\t* Thanks: counter:treasury 10\n"
)


class TestValidGames:
    def test_minimal_valid(self):
        assert_valid(MINIMAL_VALID)

    def test_game_with_all_entity_types(self):
        source = (
            "Game (settings:main)\n"
            "Treasury (counter:treasury, killer)\n"
            "War (flag:war)\n"
            "Angry (variant:angry)\n"
            "Advisor (character:advisor)\n"
            "Welcome (card:welcome)\n"
            "\tbearer: character:advisor (variant:angry)\n"
            "\trequire: flag:war, counter:treasury > 50\n"
            "\tweight: 1.0\n"
            "\t> Welcome!\n"
            "\t* Accept: counter:treasury -10, +flag:war\n"
            "\t* Decline: counter:treasury 5, -flag:war\n"
        )
        assert_valid(source)

    def test_ring_card_valid(self):
        source = (
            "Advisor (character:advisor)\n"
            "Battle (card:_battle, ring)\n"
            "\tbearer: character:advisor\n"
            "\t> Fight!\n"
            "\t* Ok:\n"
        )
        assert_valid(source)


# =========================================================================
# Duplicate ID detection
# =========================================================================


class TestDuplicateIDs:
    def test_duplicate_counter(self):
        source = "X (counter:x)\nX (counter:x)"
        assert_errors(source, "Duplicate counter ID")

    def test_duplicate_flag(self):
        source = "A (flag:a)\nB (flag:a)"
        assert_errors(source, "Duplicate flag ID")

    def test_duplicate_variant(self):
        source = "A (variant:a)\nB (variant:a)"
        assert_errors(source, "Duplicate variant ID")

    def test_duplicate_character(self):
        source = "A (character:a)\nB (character:a)"
        assert_errors(source, "Duplicate character ID")

    def test_duplicate_card(self):
        source = "A (card:a)\nB (card:a)"
        assert_errors(source, "Duplicate card ID")

    def test_same_id_different_types_ok(self):
        """Same ID in different entity types is allowed."""
        source = (
            "X (counter:x)\n"
            "X (flag:x)\n"
            "X (character:x)\n"
            "X (card:x)\n"
            "\tbearer: character:x\n"
            "\tweight: 1\n"
            "\t> text\n"
            "\t* go: counter:x 1\n"
        )
        assert_valid(source)


# =========================================================================
# Undefined references
# =========================================================================


class TestUndefinedReferences:
    def test_undefined_bearer_character(self):
        source = (
            "Welcome (card:welcome)\n"
            "\tbearer: character:nobody\n"
            "\t> Hi\n"
            "\t* Ok:\n"
        )
        assert_errors(source, "Undefined bearer")

    def test_undefined_bearer_variant(self):
        source = (
            "Advisor (character:advisor)\n"
            "Welcome (card:welcome)\n"
            "\tbearer: character:advisor (variant:nonexistent)\n"
            "\t> Hi\n"
            "\t* Ok:\n"
        )
        assert_errors(source, "Undefined variant")

    def test_undefined_counter_in_command(self):
        source = (
            "Advisor (character:advisor)\n"
            "C (card:c)\n"
            "\tbearer: character:advisor\n"
            "\t> text\n"
            "\t* Go: counter:nonexistent 10\n"
        )
        assert_errors(source, "Undefined counter")

    def test_undefined_flag_set(self):
        source = (
            "Advisor (character:advisor)\n"
            "C (card:c)\n"
            "\tbearer: character:advisor\n"
            "\t> text\n"
            "\t* Go: +flag:nonexistent\n"
        )
        assert_errors(source, "Undefined flag")

    def test_undefined_flag_clear(self):
        source = (
            "Advisor (character:advisor)\n"
            "C (card:c)\n"
            "\tbearer: character:advisor\n"
            "\t> text\n"
            "\t* Go: -flag:nonexistent\n"
        )
        assert_errors(source, "Undefined flag")

    def test_undefined_card_queue(self):
        source = (
            "Advisor (character:advisor)\n"
            "C (card:c)\n"
            "\tbearer: character:advisor\n"
            "\t> text\n"
            "\t* Go: card:nonexistent\n"
        )
        assert_errors(source, "Undefined card")

    def test_undefined_card_timed(self):
        source = (
            "Advisor (character:advisor)\n"
            "C (card:c)\n"
            "\tbearer: character:advisor\n"
            "\t> text\n"
            "\t* Go: card:nonexistent@5\n"
        )
        assert_errors(source, "Undefined card")

    def test_undefined_card_branch(self):
        source = (
            "Advisor (character:advisor)\n"
            "C (card:c)\n"
            "\tbearer: character:advisor\n"
            "\t> text\n"
            "\t* Go: [card:nonexistent_a, card:nonexistent_b]\n"
        )
        assert_errors(source, "Undefined card")

    def test_undefined_flag_in_require(self):
        source = "C (card:c)\n\trequire: flag:nonexistent\n"
        assert_errors(source, "Undefined flag")

    def test_undefined_counter_in_require(self):
        source = "C (card:c)\n\trequire: counter:nonexistent > 50\n"
        assert_errors(source, "Undefined counter")

    def test_undefined_flag_in_weight_condition(self):
        source = "C (card:c)\n\tweight: 0 when flag:nonexistent\n"
        assert_errors(source, "Undefined flag")

    def test_undefined_counter_in_weight_condition(self):
        source = "C (card:c)\n\tweight: 2.0 when counter:nonexistent < 30\n"
        assert_errors(source, "Undefined counter")

    def test_undefined_starting_flag(self):
        source = "S (settings:main)\n\tstarting_flags: flag:nonexistent"
        assert_errors(source, "Undefined flag", "starting_flags")

    def test_undefined_flag_bind_character(self):
        source = "F (flag:f)\n\tbind: character:nonexistent"
        assert_errors(source, "Undefined character")


# =========================================================================
# Ring card rules
# =========================================================================


class TestRingCards:
    def test_ring_without_underscore_prefix(self):
        source = "Battle (card:battle, ring)"
        assert_errors(source, "must start with '_'")

    def test_underscore_without_ring_modifier(self):
        source = "Battle (card:_battle)"
        assert_errors(source, "requires ring modifier")


# =========================================================================
# Snake case enforcement
# =========================================================================


class TestSnakeCase:
    def test_camel_case_counter(self):
        source = "X (counter:myCounter)"
        assert_errors(source, "snake_case")

    def test_camel_case_flag(self):
        source = "X (flag:isActive)"
        assert_errors(source, "snake_case")

    def test_camel_case_character(self):
        source = "X (character:grandVizier)"
        assert_errors(source, "snake_case")

    def test_camel_case_card(self):
        source = "X (card:firstCard)"
        assert_errors(source, "snake_case")

    def test_snake_case_ok(self):
        source = "X (counter:my_counter)"
        result = validate(source)
        snake_errors = [e for e in result.errors if "snake_case" in str(e)]
        assert len(snake_errors) == 0

    def test_single_word_ok(self):
        source = "X (counter:treasury)"
        result = validate(source)
        snake_errors = [e for e in result.errors if "snake_case" in str(e)]
        assert len(snake_errors) == 0


# =========================================================================
# Virtual counter validation
# =========================================================================


class TestVirtualCounterValidation:
    def test_source_without_aggregate_or_track(self):
        source = "X (counter:x)\n\tsource: [counter:a]"
        assert_errors(source, "no aggregate or track")

    def test_aggregate_with_invalid_source(self):
        source = (
            "X (counter:x)\n\tsource: [character:a]\n\taggregate: average\n"
        )
        assert_errors(source, "Aggregate counter source must be counter refs")

    def test_aggregate_with_undefined_counter(self):
        source = (
            "X (counter:x)\n"
            "\tsource: [counter:nonexistent]\n"
            "\taggregate: sum\n"
        )
        assert_errors(source, "Undefined counter")

    def test_tracking_with_invalid_source(self):
        source = "X (counter:x)\n\tsource: [counter:a]\n\ttrack: yes\n"
        assert_errors(source, "Tracking counter source must be character refs")

    def test_tracking_with_undefined_character(self):
        source = (
            "X (counter:x)\n\tsource: [character:nonexistent]\n\ttrack: no\n"
        )
        assert_errors(source, "Undefined character")

    def test_valid_aggregate_counter(self):
        source = (
            "A (counter:a)\n"
            "B (counter:b)\n"
            "Total (counter:total)\n"
            "\tsource: [counter:a, counter:b]\n"
            "\taggregate: sum\n"
        )
        result = validate(source)
        agg_errors = [
            e
            for e in result.errors
            if "aggregate" in str(e).lower() or "source" in str(e).lower()
        ]
        assert len(agg_errors) == 0

    def test_valid_tracking_counter(self):
        source = (
            "Merchant (character:merchant)\n"
            "YesCount (counter:yes_count)\n"
            "\tsource: [character:merchant]\n"
            "\ttrack: yes\n"
        )
        result = validate(source)
        track_errors = [
            e
            for e in result.errors
            if "track" in str(e).lower() or "source" in str(e).lower()
        ]
        assert len(track_errors) == 0


# =========================================================================
# Text interpolation validation
# =========================================================================


class TestTextInterpolation:
    def test_valid_interpolation(self):
        source = (
            "Advisor (character:advisor)\n"
            "C (card:c)\n"
            "\t> Hello {character:advisor}!\n"
            "\t* Ok:\n"
        )
        assert_valid(source)

    def test_undefined_character_in_text(self):
        source = "C (card:c)\n\t> Hello {character:nobody}!\n\t* Ok:\n"
        assert_errors(source, "Undefined character in text")
