"""API Key generation service."""

import secrets


def generate_api_key() -> str:
    """Generate a new API key in the format nope_ + 32 hex characters.

    Returns:
        A string like "nope_a1b2c3d4e5f6..." (nope_ prefix + 32 hex chars).
    """
    # Generate 16 random bytes = 32 hex characters
    random_hex = secrets.token_hex(16)
    return f"nope_{random_hex}"
