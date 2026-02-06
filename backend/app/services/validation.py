import ipaddress
import re
from dataclasses import dataclass
from app.models.ioc import IOCType
from app.models.exclusion import Exclusion, ExclusionType


class ValidationError(Exception):
    """Raised when IOC validation fails."""
    pass


@dataclass
class ExclusionMatch:
    exclusion_id: int
    value: str
    reason: str | None


# Domain regex: allows subdomains, alphanumeric + hyphens, 2-63 char labels
DOMAIN_REGEX = re.compile(
    r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*\.[a-zA-Z]{2,}$"
)

# Wildcard domain regex: *.domain.tld format
WILDCARD_REGEX = re.compile(
    r"^\*\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*\.[a-zA-Z]{2,}$"
)

# Hash regexes for IOC detection
MD5_REGEX = re.compile(r"^[a-fA-F0-9]{32}$")
SHA1_REGEX = re.compile(r"^[a-fA-F0-9]{40}$")
SHA256_REGEX = re.compile(r"^[a-fA-F0-9]{64}$")


def validate_ioc(value: str) -> tuple[str, IOCType]:
    """
    Validate and classify an IOC value.

    Returns:
        Tuple of (normalized_value, ioc_type)

    Raises:
        ValidationError: If value is not a valid IP, domain, or wildcard
    """
    value = value.strip()

    if not value:
        raise ValidationError("Value cannot be empty")

    # Try parsing as IP address or network
    try:
        # Try as single IP
        ip = ipaddress.ip_address(value)
        return str(ip), IOCType.IP
    except ValueError:
        pass

    try:
        # Try as CIDR network
        network = ipaddress.ip_network(value, strict=False)
        return str(network), IOCType.IP
    except ValueError:
        pass

    # Try as hash (check longest first to avoid false matches)
    if SHA256_REGEX.match(value):
        return value.lower(), IOCType.SHA256

    if SHA1_REGEX.match(value):
        return value.lower(), IOCType.SHA1

    if MD5_REGEX.match(value):
        return value.lower(), IOCType.MD5

    # Try as wildcard domain (*.example.com)
    if WILDCARD_REGEX.match(value):
        return value.lower(), IOCType.WILDCARD

    # Try as domain
    if DOMAIN_REGEX.match(value):
        return value.lower(), IOCType.DOMAIN

    raise ValidationError(f"'{value}' is not a valid IP address, CIDR, domain, wildcard, or hash")


def is_ioc_type_allowed(ioc_type: str, list_type: str) -> bool:
    """Check if an IOC type is allowed for a given list type."""
    if list_type == "mixed":
        return True
    if list_type == "ip":
        return ioc_type == "ip"
    if list_type == "domain":
        return ioc_type in ("domain", "wildcard")
    if list_type == "hash":
        return ioc_type in ("md5", "sha1", "sha256")
    return False


def check_exclusions(
    value: str,
    ioc_type: str,
    exclusions: list[Exclusion],
) -> ExclusionMatch | None:
    """
    Check if a value matches any exclusion rule.

    Returns:
        ExclusionMatch if excluded, None if allowed
    """
    value_lower = value.lower()

    for excl in exclusions:
        if _matches_exclusion(value_lower, ioc_type, excl):
            return ExclusionMatch(
                exclusion_id=excl.id,
                value=excl.value,
                reason=excl.reason,
            )

    return None


def _matches_exclusion(value: str, ioc_type: str, exclusion: Exclusion) -> bool:
    """Check if value matches a single exclusion rule."""

    # TLD check - domain exactly matches exclusion value
    if exclusion.type == ExclusionType.DOMAIN:
        if ioc_type == "domain" and value == exclusion.value.lower():
            return True

    # CIDR check - IP falls within network
    if exclusion.type == ExclusionType.CIDR and ioc_type == "ip":
        try:
            network = ipaddress.ip_network(exclusion.value, strict=False)
            # Handle both single IPs and networks
            try:
                ip = ipaddress.ip_address(value)
                if ip in network:
                    return True
            except ValueError:
                # Value might be a CIDR itself
                try:
                    value_network = ipaddress.ip_network(value, strict=False)
                    if value_network.subnet_of(network):
                        return True
                except ValueError:
                    pass
        except ValueError:
            pass

    # Wildcard check - domain ends with pattern
    if exclusion.type == ExclusionType.WILDCARD and ioc_type == "domain":
        pattern = exclusion.value.lower()
        if pattern.startswith("*."):
            suffix = pattern[1:]  # Keep the dot: ".internal.corp"
            if value.endswith(suffix):
                return True

    # Exact IP match
    if exclusion.type == ExclusionType.IP and ioc_type == "ip":
        if value == exclusion.value:
            return True

    return False
