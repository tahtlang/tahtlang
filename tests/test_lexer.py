"""Tests for the line-based lexer."""

import pytest

from tools.parser.lexer import Lexer, Line, LineType, EntityType, Modifier
from tools.parser.errors import ParseError


def lex(source: str) -> list[Line]:
    """Helper: lex source and return non-empty, non-comment lines."""
    return [l for l in Lexer(source, "<test>")]


def lex_content(source: str) -> list[Line]:
    """Helper: lex source and return only content lines (skip empty/comment)."""
    return [l for l in Lexer(source, "<test>") if l.type not in (LineType.EMPTY, LineType.COMMENT)]


# =========================================================================
# Empty and comment lines
# =========================================================================


class TestEmptyAndComments:
    def test_empty_string_no_lines(self):
        lines = lex("")
        assert len(lines) == 0

    def test_single_empty_line(self):
        lines = lex("\n")
        assert len(lines) == 1
        assert lines[0].type == LineType.EMPTY

    def test_whitespace_only_line(self):
        lines = lex("   ")
        assert lines[0].type == LineType.EMPTY

    def test_comment_at_column_zero(self):
        lines = lex("# This is a comment")
        assert lines[0].type == LineType.COMMENT

    def test_indented_comment(self):
        lines = lex("\t# indented comment")
        assert lines[0].type == LineType.COMMENT

    def test_multiple_lines_mixed(self):
        source = "# comment\n\n# another"
        lines = lex(source)
        assert lines[0].type == LineType.COMMENT
        assert lines[1].type == LineType.EMPTY
        assert lines[2].type == LineType.COMMENT


# =========================================================================
# Import statements
# =========================================================================


class TestImports:
    def test_double_quote_import(self):
        lines = lex_content('import "path/to/file.tahta"')
        assert len(lines) == 1
        assert lines[0].type == LineType.IMPORT
        assert lines[0].import_path == "path/to/file.tahta"

    def test_single_quote_import(self):
        lines = lex_content("import 'other.tahta'")
        assert lines[0].type == LineType.IMPORT
        assert lines[0].import_path == "other.tahta"

    def test_indented_import_not_recognized(self):
        """Import must be at column 0."""
        lines = lex_content("\timport \"file.tahta\"")
        assert lines[0].type != LineType.IMPORT


# =========================================================================
# Entity headers
# =========================================================================


class TestEntityHeaders:
    def test_counter_with_killer(self):
        lines = lex_content("Treasury (counter:treasury, killer)")
        assert len(lines) == 1
        line = lines[0]
        assert line.type == LineType.ENTITY_HEADER
        assert line.entity_name == "Treasury"
        assert line.entity_type == EntityType.COUNTER
        assert line.entity_id == "treasury"
        assert line.entity_modifiers == {Modifier.KILLER}

    def test_counter_with_multiple_modifiers(self):
        lines = lex_content("Gold (counter:gold, killer, keep)")
        line = lines[0]
        assert line.entity_modifiers == {Modifier.KILLER, Modifier.KEEP}

    def test_character_no_modifiers(self):
        lines = lex_content("Grand Vizier (character:vizier)")
        line = lines[0]
        assert line.entity_type == EntityType.CHARACTER
        assert line.entity_id == "vizier"
        assert line.entity_modifiers == set()

    def test_card_with_ring(self):
        lines = lex_content("War Battle (card:_war_battle, ring)")
        line = lines[0]
        assert line.entity_type == EntityType.CARD
        assert line.entity_id == "_war_battle"
        assert line.entity_modifiers == {Modifier.RING}

    def test_settings(self):
        lines = lex_content("Game Settings (settings:main)")
        line = lines[0]
        assert line.entity_type == EntityType.SETTINGS
        assert line.entity_id == "main"

    def test_flag_entity(self):
        lines = lex_content("War Active (flag:war)")
        line = lines[0]
        assert line.entity_type == EntityType.FLAG
        assert line.entity_id == "war"

    def test_variant_entity(self):
        lines = lex_content("Angry (variant:angry)")
        line = lines[0]
        assert line.entity_type == EntityType.VARIANT
        assert line.entity_id == "angry"

    def test_entity_name_with_spaces(self):
        lines = lex_content("The Grand Vizier (character:grand_vizier)")
        assert lines[0].entity_name == "The Grand Vizier"

    def test_unknown_type_not_entity(self):
        """Unknown type prefix should not be recognized as entity."""
        lines = lex_content("Foo (unknown:bar)")
        assert lines[0].type != LineType.ENTITY_HEADER

    def test_entity_must_be_at_column_zero(self):
        """Indented entity headers are not recognized."""
        lines = lex_content("\tTreasury (counter:treasury)")
        assert lines[0].type != LineType.ENTITY_HEADER


# =========================================================================
# Properties
# =========================================================================


class TestProperties:
    def test_simple_property(self):
        lines = lex_content("\tbearer: character:advisor")
        assert len(lines) == 1
        line = lines[0]
        assert line.type == LineType.PROPERTY
        assert line.key == "bearer"
        assert line.value == "character:advisor"

    def test_property_with_spaces(self):
        lines = lex_content("\tdescription: A great game")
        assert lines[0].key == "description"
        assert lines[0].value == "A great game"

    def test_property_must_be_indented(self):
        with pytest.raises(ParseError):
            lex_content("bearer: character:advisor")

    def test_weight_property(self):
        lines = lex_content("\tweight: 1.0")
        assert lines[0].key == "weight"
        assert lines[0].value == "1.0"

    def test_require_property(self):
        lines = lex_content("\trequire: flag:war, counter:army > 50")
        assert lines[0].key == "require"
        assert lines[0].value == "flag:war, counter:army > 50"


# =========================================================================
# Primary values (card text)
# =========================================================================


class TestPrimaryValues:
    def test_card_text(self):
        lines = lex_content("\t> The kingdom needs gold!")
        assert len(lines) == 1
        assert lines[0].type == LineType.PRIMARY_VALUE
        assert lines[0].value == "The kingdom needs gold!"

    def test_card_text_must_be_indented(self):
        with pytest.raises(ParseError):
            lex_content("> Not indented")


# =========================================================================
# Choices
# =========================================================================


class TestChoices:
    def test_choice_with_commands(self):
        lines = lex_content("\t* Accept: counter:treasury -20, +flag:war")
        assert len(lines) == 1
        line = lines[0]
        assert line.type == LineType.CHOICE
        assert line.choice_label == "Accept"
        assert line.choice_commands == "counter:treasury -20, +flag:war"

    def test_choice_no_commands(self):
        lines = lex_content("\t* Let us begin")
        line = lines[0]
        assert line.type == LineType.CHOICE
        assert line.choice_label == "Let us begin"
        assert line.choice_commands == ""

    def test_blind_choice_empty_label(self):
        lines = lex_content("\t* : counter:treasury 10")
        line = lines[0]
        assert line.type == LineType.CHOICE
        assert line.choice_label == ""
        assert line.choice_commands == "counter:treasury 10"

    def test_choice_must_be_indented(self):
        with pytest.raises(ParseError):
            lex_content("* Bad choice: counter:x 10")


# =========================================================================
# Indentation consistency
# =========================================================================


class TestIndentation:
    def test_mixed_tabs_and_spaces_same_line(self):
        with pytest.raises(ParseError, match="Mixed indentation"):
            lex("\t content")

    def test_inconsistent_indent_style(self):
        """First indented line sets the style, different style raises error."""
        with pytest.raises(ParseError, match="Inconsistent indentation"):
            lex("\tfirst\n    second")

    def test_tabs_consistent(self):
        lines = lex("\tfirst\n\tsecond")
        assert lines[0].indent > 0
        assert lines[1].indent > 0

    def test_spaces_consistent(self):
        lines = lex("    first\n    second")
        assert lines[0].indent == 4
        assert lines[1].indent == 4


# =========================================================================
# Line numbers
# =========================================================================


class TestLineNumbers:
    def test_line_numbers_start_at_one(self):
        lines = lex("first\nsecond\nthird")
        assert lines[0].line_number == 1
        assert lines[1].line_number == 2
        assert lines[2].line_number == 3
