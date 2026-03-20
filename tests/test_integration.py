"""Integration tests: parse real example files end-to-end."""

import json
from pathlib import Path

from tools.compiler.main import game_to_dict
from tools.parser import Parser, validate_game
from tools.parser.ast import (
    CardBranch,
    CounterMod,
    FlagClear,
    FlagSet,
    RangeValue,
)

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


# =========================================================================
# Example file parsing
# =========================================================================


class TestExampleFiles:
    def test_minimal_parses(self):
        parser = Parser()
        game = parser.parse_file(str(EXAMPLES_DIR / "minimal.tahta"))
        assert len(game.cards) > 0
        assert len(game.counters) > 0
        assert len(game.characters) > 0

    def test_minimal_validates(self):
        parser = Parser()
        game = parser.parse_file(str(EXAMPLES_DIR / "minimal.tahta"))
        result = validate_game(game)
        assert result.is_valid, f"Validation errors: {result.errors}"

    def test_minimal_compiles_to_json(self):
        parser = Parser()
        game = parser.parse_file(str(EXAMPLES_DIR / "minimal.tahta"))
        data = game_to_dict(game)
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert "cards" in parsed
        assert "counters" in parsed
        assert "characters" in parsed

    def test_tutorial_parses(self):
        parser = Parser()
        game = parser.parse_file(str(EXAMPLES_DIR / "tutorial.tahta"))
        assert len(game.cards) > 0
        assert len(game.counters) > 0

    def test_tutorial_validates(self):
        parser = Parser()
        game = parser.parse_file(str(EXAMPLES_DIR / "tutorial.tahta"))
        result = validate_game(game)
        assert result.is_valid, f"Validation errors: {result.errors}"

    def test_tutorial_compiles_to_json(self):
        parser = Parser()
        game = parser.parse_file(str(EXAMPLES_DIR / "tutorial.tahta"))
        data = game_to_dict(game)
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        parsed = json.loads(json_str)
        assert len(parsed["cards"]) > 10


# =========================================================================
# Specific features from examples
# =========================================================================


class TestMinimalFeatures:
    """Test specific features present in minimal.tahta."""

    def _get_game(self):
        return Parser().parse_file(str(EXAMPLES_DIR / "minimal.tahta"))

    def test_killer_counters(self):
        game = self._get_game()
        killers = [c for c in game.counters if c.killer]
        assert len(killers) >= 4  # treasury, army, people, church

    def test_ring_cards_have_prefix(self):
        game = self._get_game()
        ring_cards = [c for c in game.cards if c.ring]
        for card in ring_cards:
            assert card.id.startswith("_"), (
                f"Ring card {card.id} missing _ prefix"
            )

    def test_non_ring_cards_have_weight(self):
        game = self._get_game()
        pool_cards = [c for c in game.cards if not c.ring]
        for card in pool_cards:
            assert len(card.weights) > 0, f"Pool card {card.id} has no weight"

    def test_conditional_weights_exist(self):
        game = self._get_game()
        conditional = []
        for card in game.cards:
            for w in card.weights:
                if w.condition is not None:
                    conditional.append(w)
        assert len(conditional) > 0, (
            "No conditional weights found in minimal.tahta"
        )


class TestTutorialFeatures:
    """Test specific features present in tutorial.tahta."""

    def _get_game(self):
        return Parser().parse_file(str(EXAMPLES_DIR / "tutorial.tahta"))

    def test_settings_present(self):
        game = self._get_game()
        assert game.settings is not None

    def test_variants_present(self):
        game = self._get_game()
        assert len(game.variants) > 0

    def test_lockturn_dispose_cards(self):
        game = self._get_game()
        dispose_cards = [c for c in game.cards if c.lockturn == "dispose"]
        assert len(dispose_cards) > 0

    def test_lockturn_once_cards(self):
        game = self._get_game()
        once_cards = [c for c in game.cards if c.lockturn == "once"]
        assert len(once_cards) > 0

    def test_flag_operations_in_choices(self):
        """Tutorial should have both flag set and flag clear commands."""
        game = self._get_game()
        has_set = False
        has_clear = False
        for card in game.cards:
            for choice in card.choices:
                for cmd in choice.commands:
                    if isinstance(cmd, FlagSet):
                        has_set = True
                    if isinstance(cmd, FlagClear):
                        has_clear = True
        assert has_set, "No FlagSet commands in tutorial"
        assert has_clear, "No FlagClear commands in tutorial"

    def test_card_branching(self):
        game = self._get_game()
        branches = []
        for card in game.cards:
            for choice in card.choices:
                for cmd in choice.commands:
                    if isinstance(cmd, CardBranch):
                        branches.append(cmd)
        assert len(branches) > 0, "No CardBranch commands in tutorial"

    def test_range_values_in_commands(self):
        game = self._get_game()
        ranges = []
        for card in game.cards:
            for choice in card.choices:
                for cmd in choice.commands:
                    if isinstance(cmd, CounterMod) and isinstance(
                        cmd.value, RangeValue
                    ):
                        ranges.append(cmd)
        assert len(ranges) > 0, "No RangeValue commands in tutorial"


# =========================================================================
# JSON output completeness
# =========================================================================


class TestJsonCompleteness:
    def test_all_operators_in_json(self):
        """Test that all comparison operators serialize correctly."""
        source = (
            "X (counter:x)\n"
            "A (card:a)\n\trequire: counter:x < 30\n"
            "B (card:b)\n\trequire: counter:x > 70\n"
            "C (card:c_eq)\n\trequire: counter:x = 50\n"
            "D (card:d)\n\trequire: counter:x <= 30\n"
            "E (card:e)\n\trequire: counter:x >= 70\n"
        )
        data = game_to_dict(Parser().parse_string(source, "<test>"))
        cards = data["cards"]
        assert cards["a"]["require"][0]["operator"] == "<"
        assert cards["b"]["require"][0]["operator"] == ">"
        assert cards["c_eq"]["require"][0]["operator"] == "="
        assert cards["d"]["require"][0]["operator"] == "<="
        assert cards["e"]["require"][0]["operator"] == ">="

    def test_all_command_types_in_json(self):
        """Test that every command type produces correct JSON."""
        source = (
            "X (counter:x)\n"
            "F (flag:f)\n"
            "Next (card:next)\n\t* go:\n"
            "A (card:_a, ring)\n\t* go:\n"
            "B (card:_b, ring)\n\t* go:\n"
            "C (card:c)\n"
            "\t* Go: counter:x 10, counter:x -5?5, +flag:f, -flag:f, "
            "card:next, card:next@3, [card:_a, card:_b], "
            'trigger:response "hi", trigger:sound "fx.wav"\n'
        )
        data = game_to_dict(Parser().parse_string(source, "<test>"))
        cmds = data["cards"]["c"]["choices"][0]["commands"]
        types = [c["type"] for c in cmds]
        assert "counter_mod" in types
        assert "flag_set" in types
        assert "flag_clear" in types
        assert "card_queue" in types
        assert "card_timed" in types
        assert "card_branch" in types
        assert "trigger" in types

        # Verify trigger fields specifically
        triggers = [c for c in cmds if c["type"] == "trigger"]
        assert len(triggers) == 2
        assert triggers[0]["trigger_type"] == "response"
        assert triggers[1]["trigger_type"] == "sound"
