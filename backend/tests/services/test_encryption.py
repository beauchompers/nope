"""Tests for the API key generation service."""

import re

from app.services.encryption import generate_api_key


class TestGenerateApiKey:
    """Tests for generate_api_key function."""

    def test_generates_key_with_nope_prefix(self):
        """Generated key should start with 'nope_'."""
        key = generate_api_key()
        assert key.startswith("nope_")

    def test_generates_key_with_correct_length(self):
        """Generated key should be nope_ (5 chars) + 32 hex chars = 37 chars."""
        key = generate_api_key()
        assert len(key) == 37

    def test_generates_key_with_valid_hex(self):
        """The portion after nope_ should be valid hexadecimal."""
        key = generate_api_key()
        hex_part = key[5:]  # Remove "nope_" prefix
        assert len(hex_part) == 32
        # Verify it's valid hex by trying to decode it
        int(hex_part, 16)

    def test_generates_key_matches_format(self):
        """Generated key should match the expected format."""
        key = generate_api_key()
        pattern = r"^nope_[a-f0-9]{32}$"
        assert re.match(pattern, key) is not None

    def test_generates_unique_keys(self):
        """Each call should generate a unique key."""
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100
