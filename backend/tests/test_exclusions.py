import pytest
from app.services.validation import check_exclusions, ExclusionMatch
from app.models.exclusion import Exclusion, ExclusionType


class TestCheckExclusions:
    @pytest.fixture
    def exclusions(self):
        return [
            Exclusion(id=1, value="com", type=ExclusionType.DOMAIN, reason="TLD", is_builtin=True),
            Exclusion(id=2, value="10.0.0.0/8", type=ExclusionType.CIDR, reason="RFC1918", is_builtin=True),
            Exclusion(id=3, value="evil.com", type=ExclusionType.DOMAIN, reason="Test", is_builtin=False),
            Exclusion(id=4, value="*.internal.corp", type=ExclusionType.WILDCARD, reason="Internal", is_builtin=False),
        ]

    def test_matches_tld(self, exclusions):
        result = check_exclusions("com", "domain", exclusions)
        assert result is not None
        assert result.reason == "TLD"

    def test_matches_rfc1918(self, exclusions):
        result = check_exclusions("10.1.2.3", "ip", exclusions)
        assert result is not None
        assert result.reason == "RFC1918"

    def test_matches_exact_domain(self, exclusions):
        result = check_exclusions("evil.com", "domain", exclusions)
        assert result is not None
        assert result.reason == "Test"

    def test_matches_wildcard(self, exclusions):
        result = check_exclusions("server.internal.corp", "domain", exclusions)
        assert result is not None
        assert result.reason == "Internal"

    def test_no_match(self, exclusions):
        result = check_exclusions("safe.example.org", "domain", exclusions)
        assert result is None

    def test_public_ip_not_excluded(self, exclusions):
        result = check_exclusions("8.8.8.8", "ip", exclusions)
        assert result is None
