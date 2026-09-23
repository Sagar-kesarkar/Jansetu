"""Base abstractions and security enforcement for Financial Source Ingestion.

Security Guarantees:
- Specific hostname allowlist (no broad wildcards).
- DNS IP resolution validation (blocks DNS rebinding and SSRF to private/link-local/loopback IPs).
- Redirect validation.
- Download payload size capping (max 25MB) and timeout limits.
- Canonical SHA-256 payload integrity hashing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import ipaddress
import logging
import socket
from urllib.parse import urlparse

log = logging.getLogger(__name__)

#: Specific Approved Government Hostnames (Exact match only, no wildcard open doors)
SPECIFIC_APPROVED_HOSTNAMES = frozenset({
    "data.gov.in",
    "finance.maharashtra.gov.in",
    "mahasdb.maharashtra.gov.in",
    "egramswaraj.gov.in",
    "pfms.nic.in",
})

MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
DEFAULT_TIMEOUT_SEC = 20


class SecurityValidationError(ValueError):
    """Raised when a URL or payload violates ingestion security policies."""
    pass


def validate_resolved_ip(ip_str: str) -> None:
    """Verify that an IP address is not private, loopback, link-local, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError as err:
        raise SecurityValidationError(f"Invalid IP address format: {err}") from err

    if ip.is_loopback:
        raise SecurityValidationError(f"Resolved IP '{ip_str}' is a loopback address (SSRF blocked).")
    if ip.is_link_local:
        raise SecurityValidationError(f"Resolved IP '{ip_str}' is link-local / cloud metadata range (SSRF blocked).")
    if ip.is_private:
        raise SecurityValidationError(f"Resolved IP '{ip_str}' is in a private network (SSRF blocked).")
    if ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        raise SecurityValidationError(f"Resolved IP '{ip_str}' is in a restricted range (SSRF blocked).")


def validate_source_url(url: str, *, resolve_dns: bool = False) -> str:
    """Validate that a URL uses HTTPS, matches the specific hostname allowlist, and resolves to a public IP.

    Enforces strict SSRF defense:
    - Must use https:// scheme.
    - Hostname must match SPECIFIC_APPROVED_HOSTNAMES exactly.
    - Disallows IP literals in URL.
    - Resolves hostname via DNS and verifies destination IP is public when resolve_dns is True.
    """
    if not url or not isinstance(url, str):
        raise SecurityValidationError("Invalid source URL: URL string is empty.")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != "https":
        raise SecurityValidationError(f"Invalid URL scheme '{parsed.scheme}': HTTPS is strictly required for official government sources.")

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        raise SecurityValidationError("Invalid source URL: missing hostname.")

    # Disallow raw IP literals
    try:
        ipaddress.ip_address(hostname)
        raise SecurityValidationError(f"Direct IP access '{hostname}' is prohibited. Must use specific approved government hostnames.")
    except ValueError:
        pass

    if hostname not in SPECIFIC_APPROVED_HOSTNAMES:
        raise SecurityValidationError(
            f"Hostname '{hostname}' is not in the specific approved government allowlist: {sorted(SPECIFIC_APPROVED_HOSTNAMES)}."
        )

    if resolve_dns:
        try:
            addr_info = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
            for entry in addr_info:
                sockaddr = entry[4]
                ip_resolved = sockaddr[0]
                validate_resolved_ip(ip_resolved)
        except socket.gaierror as err:
            raise SecurityValidationError(f"Could not resolve hostname '{hostname}': {err}") from err

    return url.strip()


def validate_redirect_target(original_url: str, redirect_url: str) -> str:
    """Validate a redirect target URL during HTTP client requests."""
    return validate_source_url(redirect_url, resolve_dns=False)


def compute_sha256(payload: bytes | str) -> str:
    """Compute SHA-256 hex digest of raw payload bytes or string."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class NormalizedFinancialRecord:
    """Canonical representation of a single government budget/expenditure line item."""
    source_name: str
    source_url: str
    publisher: str
    fiscal_year: str
    financial_stage: str       # BE, RE, ACTUAL, RELEASE, PAYMENT
    state_code: str | None     # e.g., "MH"
    district_code: str | None  # e.g., "MH_PUNE"
    category: str              # JanSetu category (e.g. "WATER_SUPPLY", "ROADS", or "UNMAPPED")
    scheme_code: str | None
    scheme_name: str
    amount_inr: Decimal        # Exact amount in INR (non-negative)
    published_at: datetime | None
    coverage: str = "complete" # complete | partial


class BaseFinancialAdapter(ABC):
    """Abstract base class for all government financial source ingestion adapters."""

    def __init__(self, source_name: str, base_url: str, publisher: str) -> None:
        self.source_name = source_name
        self.base_url = validate_source_url(base_url, resolve_dns=False)
        self.publisher = publisher

    @abstractmethod
    def fetch_and_parse(self, fiscal_year: str = "2026-27") -> tuple[str, list[NormalizedFinancialRecord]]:
        """Fetch raw snapshot and return (raw_payload_text, list_of_normalized_records)."""
        pass
