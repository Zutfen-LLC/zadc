"""FIX2-BP-02: Canonical GlobalId acceptance.

Tests that representative canonical URI schemes are accepted by the runtime,
preserving the ID byte-for-byte. Also tests that valid reserved/unreserved
URI characters and valid uppercase percent escapes are accepted.
"""

import pytest

from zadc.types import validate_global_id


class TestCanonicalGlobalIdAcceptance:
    """Accept representative canonical URI schemes."""

    @pytest.mark.parametrize(
        "value",
        [
            # urn:uuid canonical lowercase
            "urn:uuid:00000000-0000-0000-0000-000000000001",
            "urn:uuid:abcdef01-2345-6789-abcd-ef0123456789",
            # zutfen scheme
            "zutfen:human:eric",
            "zutfen:project:zadc",
            # github scheme
            "github:Zutfen-LLC/zadc",
            # https scheme
            "https://example.com/artifact/001",
            # another lowercase custom scheme
            "custom:my-resource-id",
            "custom:path/to/resource",
        ],
    )
    def test_accept_canonical_global_ids(self, value: str) -> None:
        result = validate_global_id(value)
        assert result == value

    def test_direct_runtime_output_preserves_bytes(self) -> None:
        """Direct runtime output preserves the canonical accepted ID byte-for-byte."""
        for value in [
            "urn:uuid:00000000-0000-0000-0000-000000000001",
            "zutfen:human:eric",
            "github:Zutfen-LLC/zadc",
            "https://example.com/artifact/001",
        ]:
            assert validate_global_id(value) == value


class TestValidUriCharactersAccepted:
    """Accept valid reserved/unreserved URI characters and valid uppercase percent escapes."""

    @pytest.mark.parametrize(
        "value",
        [
            # Unreserved characters: A-Za-z0-9 -._~
            "https://example.com/path-with~tilde",
            "custom:resource_name-1.0",
            # Reserved characters: :/?#[]@!$&'()*+,;=
            "https://example.com/path?query=value&other=2",
            "https://user@example.com:8080/path",
            "custom:array[0]",
            "custom:key=value",
            # Percent escapes with uppercase hex
            "https://example.com/path%20with%20spaces",
            "custom:caf%C3%A9",
            "https://example.com/%2Fpath%3F",
        ],
    )
    def test_accept_valid_uri_chars(self, value: str) -> None:
        result = validate_global_id(value)
        assert result == value
