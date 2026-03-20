"""Tests for the JSON compiler output."""

import json

from tools.compiler.main import game_to_dict
from tools.parser import Parser


def compile_to_dict(source: str) -> dict:
    """Helper: parse and compile to dict."""
    game = Parser().parse_string(source, "<test>")
    return game_to_dict(game)


# =========================================================================
# Settings serialization
# =========================================================================


class TestSettingsSerialization:
    def test_settings_fields(self):
        source = (
            "Game (settings:main)\n"
            '\tdescription: "Test game"\n'
            "\tstarting_flags: [flag:intro]\n"
            "\tgame_over_on_zero: false\n"
        )
        data = compile_to_dict(source)
        s = data["settings"]
        assert s["name"] == "Game"
        assert s["description"] == "Test game"
        assert s["starting_flags"] == ["intro"]
        assert s["game_over_on_zero"] is False
        assert s["game_over_on_max"] is True

    def test_empty_settings(self):
        data = compile_to_dict("")
        assert data["settings"] == {}


# =========================================================================
# Counter serialization
# =========================================================================


class TestCounterSerialization:
    def test_basic_counter(self):
        data = compile_to_dict("Treasury (counter:treasury, killer)\n\t> 75")
        c = data["counters"]["treasury"]
        assert c["id"] == "treasury"
        assert c["name"] == "Treasury"
        assert c["start"] == 75
        assert c["killer"] is True
        assert c["keep"] is False

    def test_virtual_counter(self):
        source = (
            "A (counter:a)\n"
            "B (counter:b)\n"
            "Total (counter:total)\n"
            "\tsource: [counter:a, counter:b]\n"
            "\taggregate: average\n"
        )
        data = compile_to_dict(source)
        c = data["counters"]["total"]
        assert c["source"] == ["counter:a", "counter:b"]
        assert c["aggregate"] == "average"
        assert c["track"] is None


# =========================================================================
# Flag serialization
# =========================================================================


class TestFlagSerialization:
    def test_basic_flag(self):
        data = compile_to_dict("War (flag:war)")
        f = data["flags"]["war"]
        assert f["id"] == "war"
        assert f["name"] == "War"
        assert f["keep"] is False
        assert f["bind"] is None

    def test_flag_with_keep(self):
        data = compile_to_dict("F (flag:f, keep)")
        assert data["flags"]["f"]["keep"] is True


# =========================================================================
# Card serialization
# =========================================================================


class TestCardSerialization:
    def test_card_basic_fields(self):
        source = (
            "Advisor (character:advisor)\n"
            "C (card:test_card)\n"
            "\tbearer: character:advisor\n"
            "\tweight: 1.0\n"
            "\tlockturn: 60\n"
            "\t> Hello world\n"
            "\t* Yes: counter:x 10\n"
            "\t* No: counter:x -5\n"
        )
        data = compile_to_dict(source)
        c = data["cards"]["test_card"]
        assert c["id"] == "test_card"
        assert c["text"] == "Hello world"
        assert c["lockturn"] == 60
        assert c["bearer"]["character"] == "advisor"
        assert len(c["choices"]) == 2

    def test_ring_field_in_output(self):
        source = "Battle (card:_battle, ring)\n\t> Fight!\n\t* Go:\n"
        data = compile_to_dict(source)
        assert data["cards"]["_battle"]["ring"] is True

    def test_non_ring_card_ring_false(self):
        source = "Normal (card:normal)\n\t> Hi\n\t* Go:\n"
        data = compile_to_dict(source)
        assert data["cards"]["normal"]["ring"] is False

    def test_bearer_with_variant(self):
        source = (
            "Advisor (character:advisor)\n"
            "Angry (variant:angry)\n"
            "C (card:c)\n"
            "\tbearer: character:advisor (variant:angry)\n"
            "\t> text\n\t* ok:\n"
        )
        data = compile_to_dict(source)
        b = data["cards"]["c"]["bearer"]
        assert b["character"] == "advisor"
        assert b["variant"] == "angry"

    def test_lockturn_once(self):
        source = "C (card:c)\n\tlockturn: once"
        data = compile_to_dict(source)
        assert data["cards"]["c"]["lockturn"] == "once"

    def test_lockturn_dispose(self):
        source = "C (card:c)\n\tlockturn: dispose"
        data = compile_to_dict(source)
        assert data["cards"]["c"]["lockturn"] == "dispose"


# =========================================================================
# Command serialization
# =========================================================================


class TestCommandSerialization:
    def _get_cmd(self, cmd_str: str) -> dict:
        source = f"C (card:c)\n\t* Go: {cmd_str}"
        data = compile_to_dict(source)
        return data["cards"]["c"]["choices"][0]["commands"][0]

    def test_counter_mod_fixed(self):
        cmd = self._get_cmd("counter:gold 20")
        assert cmd["type"] == "counter_mod"
        assert cmd["counter"] == "gold"
        assert cmd["value"]["type"] == "fixed"
        assert cmd["value"]["value"] == 20

    def test_counter_mod_range(self):
        cmd = self._get_cmd("counter:gold 10?30")
        assert cmd["value"]["type"] == "range"
        assert cmd["value"]["min"] == 10
        assert cmd["value"]["max"] == 30

    def test_flag_set(self):
        cmd = self._get_cmd("+flag:war")
        assert cmd["type"] == "flag_set"
        assert cmd["flag"] == "war"

    def test_flag_clear(self):
        cmd = self._get_cmd("-flag:war")
        assert cmd["type"] == "flag_clear"
        assert cmd["flag"] == "war"

    def test_card_queue(self):
        cmd = self._get_cmd("card:next")
        assert cmd["type"] == "card_queue"
        assert cmd["card"] == "next"

    def test_card_timed(self):
        cmd = self._get_cmd("card:event@5")
        assert cmd["type"] == "card_timed"
        assert cmd["card"] == "event"
        assert cmd["delay"] == 5

    def test_card_branch(self):
        cmd = self._get_cmd("[card:_a, card:_b]")
        assert cmd["type"] == "card_branch"
        assert cmd["cards"] == ["_a", "_b"]

    def test_trigger_response(self):
        cmd = self._get_cmd('trigger:response "Well done!"')
        assert cmd["type"] == "trigger"
        assert cmd["trigger_type"] == "response"
        assert cmd["value"] == "Well done!"

    def test_trigger_sound(self):
        cmd = self._get_cmd('trigger:sound "coin.wav"')
        assert cmd["type"] == "trigger"
        assert cmd["trigger_type"] == "sound"
        assert cmd["value"] == "coin.wav"


# =========================================================================
# Condition serialization
# =========================================================================


class TestConditionSerialization:
    def test_flag_condition(self):
        source = "C (card:c)\n\trequire: flag:war"
        data = compile_to_dict(source)
        cond = data["cards"]["c"]["require"][0]
        assert cond["type"] == "flag"
        assert cond["flag"] == "war"
        assert cond["negated"] is False

    def test_negated_flag_condition(self):
        source = "C (card:c)\n\trequire: !flag:war"
        data = compile_to_dict(source)
        cond = data["cards"]["c"]["require"][0]
        assert cond["negated"] is True

    def test_counter_condition(self):
        source = "C (card:c)\n\trequire: counter:gold > 50"
        data = compile_to_dict(source)
        cond = data["cards"]["c"]["require"][0]
        assert cond["type"] == "counter"
        assert cond["counter"] == "gold"
        assert cond["operator"] == ">"
        assert cond["value"] == 50

    def test_counter_condition_le(self):
        source = "C (card:c)\n\trequire: counter:gold <= 30"
        data = compile_to_dict(source)
        cond = data["cards"]["c"]["require"][0]
        assert cond["operator"] == "<="

    def test_counter_condition_ge(self):
        source = "C (card:c)\n\trequire: counter:gold >= 70"
        data = compile_to_dict(source)
        cond = data["cards"]["c"]["require"][0]
        assert cond["operator"] == ">="

    def test_weight_with_condition(self):
        source = "C (card:c)\n\tweight: 2.0 when counter:gold < 30"
        data = compile_to_dict(source)
        w = data["cards"]["c"]["weights"][0]
        assert w["value"] == 2.0
        assert w["condition"]["type"] == "counter"
        assert w["condition"]["operator"] == "<"


# =========================================================================
# JSON round-trip
# =========================================================================


class TestJsonRoundTrip:
    def test_json_serializable(self):
        source = (
            "Treasury (counter:treasury, killer)\n"
            "War (flag:war)\n"
            "Angry (variant:angry)\n"
            "Advisor (character:advisor)\n"
            "C (card:c)\n"
            "\tbearer: character:advisor (variant:angry)\n"
            "\trequire: flag:war, counter:treasury > 50\n"
            "\tweight: 1.0\n"
            "\tweight: 2.0 when counter:treasury < 30\n"
            "\tlockturn: once\n"
            "\t> Hello {character:advisor}!\n"
            "\t* Yes: counter:treasury 10, +flag:war, card:c@5\n"
            "\t* No: counter:treasury -5?-1, -flag:war, [card:c]\n"
        )
        data = compile_to_dict(source)
        # Should not raise
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        # Should parse back
        parsed = json.loads(json_str)
        assert parsed["cards"]["c"]["ring"] is False
        assert len(parsed["cards"]["c"]["choices"]) == 2
