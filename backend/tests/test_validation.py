import pytest
from app.services.validation import validate_ioc, ValidationError
from app.models.ioc import IOCType


class TestValidateIOC:
    def test_valid_ipv4(self):
        result = validate_ioc("192.168.1.1")
        assert result == ("192.168.1.1", IOCType.IP)

    def test_valid_ipv4_cidr(self):
        result = validate_ioc("10.0.0.0/24")
        assert result == ("10.0.0.0/24", IOCType.IP)

    def test_valid_ipv6(self):
        result = validate_ioc("2001:db8::1")
        assert result == ("2001:db8::1", IOCType.IP)

    def test_valid_domain(self):
        result = validate_ioc("example.com")
        assert result == ("example.com", IOCType.DOMAIN)

    def test_valid_subdomain(self):
        result = validate_ioc("sub.example.com")
        assert result == ("sub.example.com", IOCType.DOMAIN)

    def test_invalid_value(self):
        with pytest.raises(ValidationError):
            validate_ioc("not valid!")

    def test_empty_value(self):
        with pytest.raises(ValidationError):
            validate_ioc("")

    def test_strips_whitespace(self):
        result = validate_ioc("  example.com  ")
        assert result == ("example.com", IOCType.DOMAIN)

    # Hash IOC tests
    def test_valid_md5(self):
        """Test valid MD5 hash (32 hex chars)."""
        result = validate_ioc("d41d8cd98f00b204e9800998ecf8427e")
        assert result == ("d41d8cd98f00b204e9800998ecf8427e", IOCType.MD5)

    def test_valid_sha1(self):
        """Test valid SHA1 hash (40 hex chars)."""
        result = validate_ioc("da39a3ee5e6b4b0d3255bfef95601890afd80709")
        assert result == ("da39a3ee5e6b4b0d3255bfef95601890afd80709", IOCType.SHA1)

    def test_valid_sha256(self):
        """Test valid SHA256 hash (64 hex chars)."""
        result = validate_ioc("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        assert result == ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", IOCType.SHA256)

    def test_md5_case_normalization(self):
        """Test MD5 uppercase input is normalized to lowercase."""
        result = validate_ioc("D41D8CD98F00B204E9800998ECF8427E")
        assert result == ("d41d8cd98f00b204e9800998ecf8427e", IOCType.MD5)

    def test_sha1_case_normalization(self):
        """Test SHA1 uppercase input is normalized to lowercase."""
        result = validate_ioc("DA39A3EE5E6B4B0D3255BFEF95601890AFD80709")
        assert result == ("da39a3ee5e6b4b0d3255bfef95601890afd80709", IOCType.SHA1)

    def test_sha256_case_normalization(self):
        """Test SHA256 uppercase input is normalized to lowercase."""
        result = validate_ioc("E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855")
        assert result == ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", IOCType.SHA256)

    def test_md5_mixed_case_normalization(self):
        """Test MD5 mixed case input is normalized to lowercase."""
        result = validate_ioc("D41d8Cd98f00B204e9800998ecF8427E")
        assert result == ("d41d8cd98f00b204e9800998ecf8427e", IOCType.MD5)

    def test_invalid_hash_wrong_length(self):
        """Test hash with wrong length raises ValidationError."""
        # 31 chars (too short for MD5)
        with pytest.raises(ValidationError):
            validate_ioc("d41d8cd98f00b204e9800998ecf8427")

    def test_invalid_hash_non_hex_chars(self):
        """Test hash with non-hex characters raises ValidationError."""
        # Contains 'g' which is not a hex char
        with pytest.raises(ValidationError):
            validate_ioc("g41d8cd98f00b204e9800998ecf8427e")

    def test_hash_with_whitespace_stripped(self):
        """Test hash with surrounding whitespace is normalized."""
        result = validate_ioc("  d41d8cd98f00b204e9800998ecf8427e  ")
        assert result == ("d41d8cd98f00b204e9800998ecf8427e", IOCType.MD5)
