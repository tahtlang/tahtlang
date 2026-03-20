"""Tests for the recursive descent parser."""

import pytest

from tools.parser import ParseError, Parser
from tools.parser.ast import (
    LOCKTURN_DISPOSE,
    LOCKTURN_ONCE,
    AggregateType,
    CardBranch,
    CardQueue,
    CardTimed,
    CounterCondition,
    CounterMod,
    FixedValue,
    FlagClear,
    FlagCondition,
    FlagSet,
    Game,
    RangeValue,
    TrackType,
    Trigger,
)


def parse(source: str) -> Game:
    """Helper: parse source string and return Game AST."""
    return Parser().parse_string(source, "<test>")


# =========================================================================
# Settings
# =========================================================================


class TestSettings:
    def test_basic_settings(self):
        game = parse(
            'Game Settings (settings:main)\n\tdescription: "A great game"'
        )
        assert game.settings is not None
        assert game.settings.id == "main"
        assert game.settings.name == "Game Settings"
        assert game.settings.description == "A great game"

    def test_settings_defaults(self):
        game = parse("My Game (settings:main)")
        assert game.settings.game_over_on_zero is True
        assert game.settings.game_over_on_max is True
        assert game.settings.starting_flags == ()

    def test_settings_starting_flags(self):
        game = parse(
            "S (settings:main)\n\tstarting_flags: [flag:intro, flag:tutorial]"
        )
        assert game.settings.starting_flags == ("intro", "tutorial")

    def test_settings_game_over_false(self):
        game = parse(
            "S (settings:main)\n"
            "\tgame_over_on_zero: false\n"
            "\tgame_over_on_max: false"
        )
        assert game.settings.game_over_on_zero is False
        assert game.settings.game_over_on_max is False


# =========================================================================
# Counters
# =========================================================================


class TestCounters:
    def test_basic_counter(self):
        game = parse("Treasury (counter:treasury)\n\t> 50")
        assert len(game.counters) == 1
        c = game.counters[0]
        assert c.id == "treasury"
        assert c.name == "Treasury"
        assert c.start == 50
        assert c.killer is False
        assert c.keep is False

    def test_counter_killer(self):
        game = parse("Army (counter:army, killer)")
        c = game.counters[0]
        assert c.killer is True

    def test_counter_keep(self):
        game = parse("Legacy (counter:legacy, keep)")
        c = game.counters[0]
        assert c.keep is True

    def test_counter_killer_keep(self):
        game = parse("Gold (counter:gold, killer, keep)")
        c = game.counters[0]
        assert c.killer is True
        assert c.keep is True

    def test_counter_default_start(self):
        game = parse("X (counter:x)")
        assert game.counters[0].start == 50

    def test_counter_icon_and_color(self):
        game = parse('Coin (counter:coin)\n\ticon: coin.png\n\tcolor: "gold"')
        c = game.counters[0]
        assert c.icon == "coin.png"
        assert (
            c.color == '"gold"'
        )  # color value keeps quotes (not auto-stripped)

    def test_virtual_counter_aggregate(self):
        source = (
            "Overall (counter:overall)\n"
            "\tsource: [counter:a, counter:b]\n"
            "\taggregate: average"
        )
        game = parse(source)
        c = game.counters[0]
        assert c.is_virtual
        assert c.source == ("counter:a", "counter:b")
        assert c.aggregate == AggregateType.AVERAGE

    def test_virtual_counter_all_aggregates(self):
        for agg_name, agg_type in [
            ("average", AggregateType.AVERAGE),
            ("sum", AggregateType.SUM),
            ("min", AggregateType.MIN),
            ("max", AggregateType.MAX),
        ]:
            source = (
                f"X (counter:x)\n"
                f"\tsource: [counter:a]\n"
                f"\taggregate: {agg_name}"
            )
            game = parse(source)
            assert game.counters[0].aggregate == agg_type

    def test_virtual_counter_tracking(self):
        source = (
            "Yes Count (counter:yes_merchant)\n"
            "\tsource: [character:merchant]\n"
            "\ttrack: yes"
        )
        game = parse(source)
        c = game.counters[0]
        assert c.is_virtual
        assert c.source == ("character:merchant",)
        assert c.track == TrackType.YES

    def test_virtual_counter_track_no(self):
        source = "N (counter:n)\n\tsource: [character:x]\n\ttrack: no"
        game = parse(source)
        assert game.counters[0].track == TrackType.NO


# =========================================================================
# Flags
# =========================================================================


class TestFlags:
    def test_basic_flag(self):
        game = parse("War Active (flag:war)")
        assert len(game.flags) == 1
        f = game.flags[0]
        assert f.id == "war"
        assert f.name == "War Active"
        assert f.keep is False
        assert f.bind is None

    def test_flag_keep(self):
        game = parse("Persistent (flag:persistent, keep)")
        assert game.flags[0].keep is True

    def test_flag_bind(self):
        game = parse(
            "Advisor (character:advisor)\n"
            "Bound (flag:bound)\n"
            "\tbind: character:advisor"
        )
        f = game.flags[0]
        assert f.bind == "advisor"


# =========================================================================
# Variants
# =========================================================================


class TestVariants:
    def test_basic_variant(self):
        game = parse("Angry (variant:angry)")
        assert len(game.variants) == 1
        v = game.variants[0]
        assert v.id == "angry"
        assert v.name == "Angry"

    def test_variant_with_prompt(self):
        game = parse('Happy (variant:happy)\n\tprompt: "smiling face"')
        assert game.variants[0].prompt == "smiling face"


# =========================================================================
# Characters
# =========================================================================


class TestCharacters:
    def test_basic_character(self):
        game = parse("The Advisor (character:advisor)")
        assert len(game.characters) == 1
        c = game.characters[0]
        assert c.id == "advisor"
        assert c.name == "The Advisor"

    def test_character_with_prompt(self):
        game = parse(
            'Wizard (character:wizard)\n\tprompt: "old man with staff"'
        )
        assert game.characters[0].prompt == "old man with staff"


# =========================================================================
# Cards - Structure
# =========================================================================


class TestCardStructure:
    def test_basic_card(self):
        source = (
            "Advisor (character:advisor)\n"
            "Welcome (card:welcome)\n"
            "\tbearer: character:advisor\n"
            "\tweight: 10\n"
            "\t> Welcome to the kingdom!\n"
            "\t* Thank you: counter:treasury 5\n"
        )
        game = parse(source)
        assert len(game.cards) == 1
        card = game.cards[0]
        assert card.id == "welcome"
        assert card.name == "Welcome"
        assert card.text == "Welcome to the kingdom!"
        assert card.ring is False

    def test_card_bearer_with_variant(self):
        source = (
            "Advisor (character:advisor)\n"
            "Angry (variant:angry)\n"
            "Bad News (card:bad_news)\n"
            "\tbearer: character:advisor (variant:angry)\n"
            "\t> Bad news!\n"
            "\t* Ok:\n"
        )
        game = parse(source)
        card = game.cards[0]
        assert card.bearer is not None
        assert card.bearer.character_id == "advisor"
        assert card.bearer.variant_id == "angry"

    def test_card_bearer_no_variant(self):
        source = (
            "Advisor (character:advisor)\n"
            "News (card:news)\n"
            "\tbearer: character:advisor\n"
            "\t> News!\n"
            "\t* Ok:\n"
        )
        game = parse(source)
        assert game.cards[0].bearer.variant_id is None

    def test_ring_card(self):
        source = "Battle (card:_battle, ring)\n\t> Fight!\n\t* Attack:\n"
        game = parse(source)
        card = game.cards[0]
        assert card.ring is True
        assert card.id == "_battle"

    def test_card_no_text(self):
        source = "Empty (card:empty)\n\t* Go:\n"
        game = parse(source)
        assert game.cards[0].text == ""

    def test_card_no_choices(self):
        source = "Silent (card:silent)\n\t> Text only"
        game = parse(source)
        assert game.cards[0].choices == ()


# =========================================================================
# Cards - Choices and Commands
# =========================================================================


class TestChoicesAndCommands:
    def test_counter_mod_positive(self):
        source = "C (card:c)\n\t* Go: counter:treasury 20"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd, CounterMod)
        assert cmd.counter_id == "treasury"
        assert isinstance(cmd.value, FixedValue)
        assert cmd.value.value == 20

    def test_counter_mod_negative(self):
        source = "C (card:c)\n\t* Go: counter:army -15"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd.value, FixedValue)
        assert cmd.value.value == -15

    def test_counter_mod_range(self):
        source = "C (card:c)\n\t* Go: counter:gold 10?30"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd.value, RangeValue)
        assert cmd.value.min_value == 10
        assert cmd.value.max_value == 30

    def test_counter_mod_negative_range(self):
        source = "C (card:c)\n\t* Go: counter:army -20?-10"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd.value, RangeValue)
        assert cmd.value.min_value == -20
        assert cmd.value.max_value == -10

    def test_counter_mod_mixed_range(self):
        source = "C (card:c)\n\t* Go: counter:luck -5?10"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd.value, RangeValue)
        assert cmd.value.min_value == -5
        assert cmd.value.max_value == 10

    def test_flag_set(self):
        source = "C (card:c)\n\t* Go: +flag:war"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd, FlagSet)
        assert cmd.flag_id == "war"

    def test_flag_clear(self):
        source = "C (card:c)\n\t* Go: -flag:war"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd, FlagClear)
        assert cmd.flag_id == "war"

    def test_card_queue(self):
        source = "C (card:c)\n\t* Go: card:next"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd, CardQueue)
        assert cmd.card_id == "next"

    def test_card_timed(self):
        source = "C (card:c)\n\t* Go: card:event@5"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd, CardTimed)
        assert cmd.card_id == "event"
        assert cmd.delay == 5

    def test_card_branch(self):
        source = "C (card:c)\n\t* Go: [card:_a, card:_b, card:_c]"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd, CardBranch)
        assert cmd.card_ids == ("_a", "_b", "_c")

    def test_trigger_response(self):
        source = 'C (card:c)\n\t* Go: trigger:response "Well done!"'
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd, Trigger)
        assert cmd.trigger_type.value == "response"
        assert cmd.value == "Well done!"

    def test_trigger_sound(self):
        source = 'C (card:c)\n\t* Go: trigger:sound "coin.wav"'
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd, Trigger)
        assert cmd.trigger_type.value == "sound"
        assert cmd.value == "coin.wav"

    def test_multiple_commands(self):
        source = "C (card:c)\n\t* Go: counter:gold 10, +flag:rich, card:next"
        game = parse(source)
        cmds = game.cards[0].choices[0].commands
        assert len(cmds) == 3
        assert isinstance(cmds[0], CounterMod)
        assert isinstance(cmds[1], FlagSet)
        assert isinstance(cmds[2], CardQueue)

    def test_branch_with_other_commands(self):
        source = "C (card:c)\n\t* Go: [card:_a, card:_b], +flag:done"
        game = parse(source)
        cmds = game.cards[0].choices[0].commands
        assert len(cmds) == 2
        assert isinstance(cmds[0], CardBranch)
        assert isinstance(cmds[1], FlagSet)

    def test_choice_no_commands(self):
        source = "C (card:c)\n\t* Just a label"
        game = parse(source)
        choice = game.cards[0].choices[0]
        assert choice.label == "Just a label"
        assert choice.commands == ()

    def test_choice_empty_label(self):
        source = "C (card:c)\n\t* : counter:gold 10"
        game = parse(source)
        choice = game.cards[0].choices[0]
        assert choice.label == ""
        assert len(choice.commands) == 1

    def test_multiple_choices(self):
        source = (
            "C (card:c)\n\t* Yes: counter:gold 10\n\t* No: counter:gold -5"
        )
        game = parse(source)
        assert len(game.cards[0].choices) == 2
        assert game.cards[0].choices[0].label == "Yes"
        assert game.cards[0].choices[1].label == "No"

    def test_unknown_command_raises(self):
        source = "C (card:c)\n\t* Go: gibberish"
        with pytest.raises(ParseError, match="Unknown command"):
            parse(source)


# =========================================================================
# Cards - Conditions (require)
# =========================================================================


class TestConditions:
    def test_flag_condition(self):
        source = "C (card:c)\n\trequire: flag:war"
        game = parse(source)
        conds = game.cards[0].require
        assert len(conds) == 1
        assert isinstance(conds[0], FlagCondition)
        assert conds[0].flag_id == "war"
        assert conds[0].negated is False

    def test_negated_flag(self):
        source = "C (card:c)\n\trequire: !flag:peace"
        game = parse(source)
        cond = game.cards[0].require[0]
        assert isinstance(cond, FlagCondition)
        assert cond.flag_id == "peace"
        assert cond.negated is True

    def test_counter_less_than(self):
        source = "C (card:c)\n\trequire: counter:treasury < 30"
        game = parse(source)
        cond = game.cards[0].require[0]
        assert isinstance(cond, CounterCondition)
        assert cond.counter_id == "treasury"
        assert cond.operator.value == "<"
        assert cond.value == 30

    def test_counter_greater_than(self):
        source = "C (card:c)\n\trequire: counter:army > 70"
        game = parse(source)
        cond = game.cards[0].require[0]
        assert cond.operator.value == ">"
        assert cond.value == 70

    def test_counter_equals(self):
        source = "C (card:c)\n\trequire: counter:x = 50"
        game = parse(source)
        cond = game.cards[0].require[0]
        assert cond.operator.value == "="
        assert cond.value == 50

    def test_counter_less_equal(self):
        source = "C (card:c)\n\trequire: counter:x <= 30"
        game = parse(source)
        cond = game.cards[0].require[0]
        assert cond.operator.value == "<="
        assert cond.value == 30

    def test_counter_greater_equal(self):
        source = "C (card:c)\n\trequire: counter:x >= 70"
        game = parse(source)
        cond = game.cards[0].require[0]
        assert cond.operator.value == ">="
        assert cond.value == 70

    def test_multiple_conditions_and(self):
        source = "C (card:c)\n\trequire: flag:war, counter:army > 50"
        game = parse(source)
        conds = game.cards[0].require
        assert len(conds) == 2
        assert isinstance(conds[0], FlagCondition)
        assert isinstance(conds[1], CounterCondition)

    def test_negated_flag_and_counter(self):
        source = "C (card:c)\n\trequire: !flag:peace, counter:army < 20"
        game = parse(source)
        assert game.cards[0].require[0].negated is True
        assert game.cards[0].require[1].operator.value == "<"


# =========================================================================
# Cards - Weight
# =========================================================================


class TestWeight:
    def test_simple_weight(self):
        source = "C (card:c)\n\tweight: 1.0"
        game = parse(source)
        weights = game.cards[0].weights
        assert len(weights) == 1
        assert weights[0].value == 1.0
        assert weights[0].condition is None

    def test_integer_weight(self):
        source = "C (card:c)\n\tweight: 10"
        game = parse(source)
        assert game.cards[0].weights[0].value == 10.0

    def test_zero_weight(self):
        source = "C (card:c)\n\tweight: 0"
        game = parse(source)
        assert game.cards[0].weights[0].value == 0.0

    def test_conditional_weight_flag(self):
        source = "C (card:c)\n\tweight: 0 when flag:war"
        game = parse(source)
        w = game.cards[0].weights[0]
        assert w.value == 0.0
        assert isinstance(w.condition, FlagCondition)
        assert w.condition.flag_id == "war"

    def test_conditional_weight_counter(self):
        source = "C (card:c)\n\tweight: 2.0 when counter:treasury < 30"
        game = parse(source)
        w = game.cards[0].weights[0]
        assert w.value == 2.0
        assert isinstance(w.condition, CounterCondition)
        assert w.condition.counter_id == "treasury"
        assert w.condition.operator.value == "<"
        assert w.condition.value == 30

    def test_multiple_weights(self):
        source = (
            "C (card:c)\n\tweight: 1.0\n\tweight: 3.0 when counter:gold < 20"
        )
        game = parse(source)
        weights = game.cards[0].weights
        assert len(weights) == 2
        assert weights[0].condition is None
        assert weights[1].condition is not None

    def test_invalid_weight_raises(self):
        source = "C (card:c)\n\tweight: abc"
        with pytest.raises(ParseError, match="Invalid weight value"):
            parse(source)


# =========================================================================
# Cards - Lockturn
# =========================================================================


class TestLockturn:
    def test_numeric_lockturn(self):
        source = "C (card:c)\n\tlockturn: 60"
        game = parse(source)
        assert game.cards[0].lockturn == 60

    def test_lockturn_once(self):
        source = "C (card:c)\n\tlockturn: once"
        game = parse(source)
        assert game.cards[0].lockturn == LOCKTURN_ONCE

    def test_lockturn_dispose(self):
        source = "C (card:c)\n\tlockturn: dispose"
        game = parse(source)
        assert game.cards[0].lockturn == LOCKTURN_DISPOSE

    def test_lockturn_none_by_default(self):
        source = "C (card:c)"
        game = parse(source)
        assert game.cards[0].lockturn is None

    def test_invalid_lockturn_raises(self):
        source = "C (card:c)\n\tlockturn: banana"
        with pytest.raises(ParseError, match="Invalid lockturn value"):
            parse(source)


# =========================================================================
# Value/Range parsing edge cases
# =========================================================================


class TestValueRange:
    def test_shorthand_positive_range(self):
        """'10?' -> RangeValue(0, 10)"""
        source = "C (card:c)\n\t* Go: counter:x 10?"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd.value, RangeValue)
        assert cmd.value.min_value == 0
        assert cmd.value.max_value == 10

    def test_shorthand_negative_range(self):
        """'-10?' -> RangeValue(-10, 0)"""
        source = "C (card:c)\n\t* Go: counter:x -10?"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd.value, RangeValue)
        assert cmd.value.min_value == -10
        assert cmd.value.max_value == 0

    def test_shorthand_right_range(self):
        """'?20' -> RangeValue(0, 20)"""
        source = "C (card:c)\n\t* Go: counter:x ?20"
        game = parse(source)
        cmd = game.cards[0].choices[0].commands[0]
        assert isinstance(cmd.value, RangeValue)
        assert cmd.value.min_value == 0
        assert cmd.value.max_value == 20


# =========================================================================
# Multiple entities
# =========================================================================


class TestMultipleEntities:
    def test_full_game(self):
        source = (
            "Game Settings (settings:main)\n"
            '\tdescription: "Test"\n'
            "\n"
            "Treasury (counter:treasury, killer)\n"
            "\t> 50\n"
            "\n"
            "War (flag:war)\n"
            "\n"
            "Angry (variant:angry)\n"
            "\n"
            "Advisor (character:advisor)\n"
            "\n"
            "Welcome (card:welcome)\n"
            "\tbearer: character:advisor\n"
            "\tweight: 1.0\n"
            "\t> Welcome!\n"
            "\t* Thanks: counter:treasury 10\n"
        )
        game = parse(source)
        assert game.settings is not None
        assert len(game.counters) == 1
        assert len(game.flags) == 1
        assert len(game.variants) == 1
        assert len(game.characters) == 1
        assert len(game.cards) == 1

    def test_comments_and_empty_lines_ignored(self):
        source = (
            "# Header comment\n"
            "\n"
            "X (counter:x)\n"
            "\n"
            "# Another comment\n"
            "Y (counter:y)\n"
        )
        game = parse(source)
        assert len(game.counters) == 2


# =========================================================================
# Error cases
# =========================================================================


class TestParserErrors:
    def test_unexpected_line(self):
        with pytest.raises(ParseError, match="Unexpected line"):
            parse("this is not valid syntax at all")

    def test_unknown_card_property(self):
        source = "C (card:c)\n\tfoobar: something"
        with pytest.raises(ParseError, match="Unknown card property"):
            parse(source)

    def test_unknown_settings_property(self):
        source = "S (settings:main)\n\tfoobar: something"
        with pytest.raises(ParseError, match="Unknown property"):
            parse(source)

    def test_unknown_counter_property(self):
        source = "X (counter:x)\n\tfoobar: something"
        with pytest.raises(ParseError, match="Unknown property"):
            parse(source)

    def test_unknown_flag_property(self):
        source = "F (flag:f)\n\tfoobar: something"
        with pytest.raises(ParseError, match="Unknown property"):
            parse(source)

    def test_unknown_character_property(self):
        source = "C (character:c)\n\tfoobar: something"
        with pytest.raises(ParseError, match="Unknown property"):
            parse(source)

    def test_unknown_variant_property(self):
        source = "V (variant:v)\n\tfoobar: something"
        with pytest.raises(ParseError, match="Unknown property"):
            parse(source)

    def test_unknown_entity_type(self):
        # This won't be recognized as an entity header by the lexer
        # so it will be an unexpected line instead
        with pytest.raises(ParseError):
            parse("Foo (unknown:bar)")
