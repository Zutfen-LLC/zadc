"""A1-BP-003: Golden vectors cover nested ordering, Unicode, escapes,
null/default inclusion, ints, arrays, insertion-order independence,
and round-trip idempotence."""

from __future__ import annotations

import pytest

from zadc import canonical_json_bytes, canonical_json_text


class TestNestedKeyOrdering:
    """Nested object keys are sorted by Unicode code-point order."""

    def test_top_level_keys_sorted(self) -> None:
        data = {"zebra": 1, "apple": 2, "mango": 3}
        result = canonical_json_text(data)
        assert result == '{"apple":2,"mango":3,"zebra":1}'

    def test_nested_keys_sorted(self) -> None:
        data = {"outer": {"zebra": 1, "apple": 2}}
        result = canonical_json_text(data)
        assert result == '{"outer":{"apple":2,"zebra":1}}'

    def test_deeply_nested_keys_sorted(self) -> None:
        data = {"a": {"b": {"d": 1, "c": 2, "a": 3}}}
        result = canonical_json_text(data)
        assert result == '{"a":{"b":{"a":3,"c":2,"d":1}}}'

    def test_keys_sorted_by_codepoint(self) -> None:
        # Uppercase letters sort before lowercase by code point.
        data = {"Z": 1, "a": 2, "A": 3}
        result = canonical_json_text(data)
        assert result == '{"A":3,"Z":1,"a":2}'

    def test_unicode_key_sort(self) -> None:
        data = {"\u00e9": 1, "e": 2, "\u00e8": 3}
        result = canonical_json_text(data)
        # 'e' (U+0065) < '\u00e8' (U+00E8) < '\u00e9' (U+00E9) by code point
        assert result == '{"e":2,"\u00e8":3,"\u00e9":1}'


class TestUnicodeValues:
    """Unicode values are serialized directly (ensure_ascii=False)."""

    def test_unicode_direct(self) -> None:
        result = canonical_json_text("héllo")
        assert result == '"héllo"'

    def test_emoji(self) -> None:
        result = canonical_json_text("test🎉")
        assert "🎉" in result

    def test_cjk(self) -> None:
        result = canonical_json_text("中文")
        assert result == '"中文"'


class TestEscapes:
    """Valid JSON escaping is used for special characters."""

    @pytest.mark.parametrize(
        "char,expected",
        [
            ('"', '\\"'),
            ("\\", "\\\\"),
            ("\n", "\\n"),
            ("\t", "\\t"),
            ("\r", "\\r"),
        ],
    )
    def test_escape_sequences(self, char: str, expected: str) -> None:
        result = canonical_json_text(char)
        assert result == f'"{expected}"'


class TestNullAndDefaults:
    """null/default fields are included."""

    def test_none_serialized_as_null(self) -> None:
        assert canonical_json_text(None) == "null"

    def test_none_value_in_dict(self) -> None:
        result = canonical_json_text({"key": None})
        assert result == '{"key":null}'

    def test_none_preserved_in_nested(self) -> None:
        result = canonical_json_text({"a": {"b": None, "c": 1}})
        assert result == '{"a":{"b":null,"c":1}}'


class TestInts:
    """Integers are serialized correctly."""

    def test_positive_int(self) -> None:
        assert canonical_json_text(42) == "42"

    def test_zero(self) -> None:
        assert canonical_json_text(0) == "0"

    def test_negative_int(self) -> None:
        assert canonical_json_text(-1) == "-1"

    def test_large_int(self) -> None:
        assert canonical_json_text(2**63) == str(2**63)


class TestArrays:
    """Arrays preserve order (not sorted)."""

    def test_array_preserves_order(self) -> None:
        result = canonical_json_text([3, 1, 2])
        assert result == "[3,1,2]"

    def test_nested_arrays(self) -> None:
        result = canonical_json_text([[3, 1], [2, 4]])
        assert result == "[[3,1],[2,4]]"

    def test_empty_array(self) -> None:
        assert canonical_json_text([]) == "[]"

    def test_mixed_array(self) -> None:
        result = canonical_json_text([1, "two", None, True])
        assert result == '[1,"two",null,true]'


class TestInsertionOrderIndependence:
    """Output is independent of dict insertion order."""

    def test_different_insertion_orders_same_output(self) -> None:

        keys = list("abcdefghijklmnopqrstuvwxyz")
        d1 = {k: i for i, k in enumerate(keys)}
        # Reverse the keys
        keys_rev = list(reversed(keys))
        d2 = {k: i for i, k in enumerate(keys_rev)}
        # d2 has different values due to enumerate, so let's make same values
        d2 = {k: keys.index(k) for k in keys_rev}
        assert canonical_json_text(d1) == canonical_json_text(d2)

    def test_complex_nested_insertion_order(self) -> None:
        d1 = {"c": {"y": 1, "x": 2}, "a": {"b": 3}}
        d2 = {"a": {"b": 3}, "c": {"x": 2, "y": 1}}
        assert canonical_json_text(d1) == canonical_json_text(d2)

    def test_randomized_order(self) -> None:
        import random

        keys = [f"key_{i:03d}" for i in range(50)]
        values = {k: i for i, k in enumerate(keys)}

        d1 = dict(values)
        shuffled = list(keys)
        random.shuffle(shuffled)
        d2 = {k: values[k] for k in shuffled}

        assert canonical_json_bytes(d1) == canonical_json_bytes(d2)


class TestRoundTripIdempotence:
    """Canonical output is idempotent (re-serializing produces identical bytes)."""

    def test_idempotent_simple(self) -> None:
        data = {"b": 1, "a": 2}
        once = canonical_json_text(data)
        import json

        twice = canonical_json_text(json.loads(once))
        assert once == twice

    def test_idempotent_complex(self) -> None:
        data = {
            "zebra": [3, 1, 2],
            "apple": {"sub": {"d": 1, "c": 2}},
            "middle": None,
        }
        once = canonical_json_text(data)
        import json

        parsed = json.loads(once)
        twice = canonical_json_text(parsed)
        assert once == twice

    def test_bytes_idempotent(self) -> None:
        data = {"b": [{"y": 1, "x": 2}], "a": "hello"}
        once = canonical_json_bytes(data)
        import json

        parsed = json.loads(once)
        twice = canonical_json_bytes(parsed)
        assert once == twice

    def test_idempotent_nested_unicode(self) -> None:
        data = {"café": {" order": [3, 1], "normal": "héllo"}}
        once = canonical_json_text(data)
        import json

        parsed = json.loads(once)
        twice = canonical_json_text(parsed)
        assert once == twice
