"""A1-BP-004: Floats/-0.0/NaN/Infinity, Decimal, bytes, sets, non-string keys,
and arbitrary objects fail with narrow errors."""

from __future__ import annotations

from decimal import Decimal

import pytest

from zadc import canonical_json_bytes, canonical_json_text
from zadc.canonical import CanonicalJSONTypeError


class TestFloatsRejected:
    """All floats are rejected, including -0.0, NaN, and Infinity."""

    def test_positive_float(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text(3.14)

    def test_negative_float(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text(-2.5)

    def test_zero_float(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text(0.0)

    def test_negative_zero(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text(-0.0)

    def test_nan(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text(float("nan"))

    def test_infinity(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text(float("inf"))

    def test_negative_infinity(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text(float("-inf"))

    def test_float_in_dict(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text({"key": 1.5})

    def test_float_in_list(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text([1.0])

    def test_float_nested(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="float"):
            canonical_json_text({"a": {"b": [1, 2.0, 3]}})


class TestDecimalRejected:
    """Decimal objects are rejected."""

    def test_decimal_value(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="Decimal"):
            canonical_json_text(Decimal("3.14"))

    def test_decimal_in_list(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="Decimal"):
            canonical_json_text([Decimal("1.0")])


class TestBytesRejected:
    """bytes and bytearray are rejected."""

    def test_bytes(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="bytes"):
            canonical_json_text(b"hello")

    def test_bytearray(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="bytearray"):
            canonical_json_text(bytearray(b"hello"))


class TestSetsRejected:
    """sets and frozensets are rejected."""

    def test_set(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="set"):
            canonical_json_text({1, 2, 3})

    def test_frozenset(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="set"):
            canonical_json_text(frozenset({1, 2}))


class TestNonStringKeys:
    """Non-string dict keys are rejected."""

    def test_int_key(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="non-string"):
            canonical_json_text({1: "value"})

    def test_float_key(self) -> None:
        # Float is caught first as a value type error during normalization
        with pytest.raises(CanonicalJSONTypeError):
            canonical_json_text({1.0: "value"})

    def test_tuple_key(self) -> None:
        with pytest.raises(CanonicalJSONTypeError):
            canonical_json_text({(1, 2): "value"})


class TestArbitraryObjects:
    """Arbitrary objects are rejected."""

    def test_custom_object(self) -> None:
        class Custom:
            pass

        with pytest.raises(CanonicalJSONTypeError):
            canonical_json_text(Custom())

    def test_object_in_list(self) -> None:
        class Custom:
            pass

        with pytest.raises(CanonicalJSONTypeError):
            canonical_json_text([1, Custom(), 2])


class TestTuplesRejected:
    """Tuples are rejected (must use lists)."""

    def test_tuple_value(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="tuple"):
            canonical_json_text((1, 2, 3))


class TestNoTrailingNewline:
    """Output has no trailing newline."""

    def test_no_trailing_newline_text(self) -> None:
        result = canonical_json_text({"key": "value"})
        assert not result.endswith("\n")

    def test_no_trailing_newline_bytes(self) -> None:
        result = canonical_json_bytes({"key": "value"})
        assert not result.endswith(b"\n")


class TestNoBom:
    """Output bytes have no UTF-8 BOM."""

    def test_no_bom(self) -> None:
        result = canonical_json_bytes({"key": "value"})
        assert not result.startswith(b"\xef\xbb\xbf")
