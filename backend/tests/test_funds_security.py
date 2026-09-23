"""Tests for Ingestion Security & Hostname Validation."""
import pytest

from app.services.financial_sources.base import (
    SecurityValidationError,
    compute_sha256,
    validate_resolved_ip,
    validate_source_url,
)


def test_allowed_government_hostnames():
    """Specific approved government hostnames must pass validation."""
    valid_urls = [
        "https://data.gov.in/resource/budget-outlays",
        "https://finance.maharashtra.gov.in/budget-publications",
        "https://egramswaraj.gov.in/public-reports",
        "https://mahasdb.maharashtra.gov.in/district-data",
        "https://pfms.nic.in/reports",
    ]
    for u in valid_urls:
        assert validate_source_url(u) == u


def test_rejects_non_https():
    """HTTP and other schemes must be rejected."""
    with pytest.raises(SecurityValidationError, match="HTTPS is strictly required"):
        validate_source_url("http://data.gov.in/dataset")

    with pytest.raises(SecurityValidationError, match="HTTPS is strictly required"):
        validate_source_url("ftp://finance.maharashtra.gov.in/doc")


def test_rejects_unapproved_hostnames():
    """Wildcard or unauthorized domains must be blocked."""
    unapproved = [
        "https://evil-hacker.com/fake-budget",
        "https://news.random-site.in/finances",
        "https://fake-gov.in.attacker.org/data",
        "https://unauthorized-domain.com",
    ]
    for u in unapproved:
        with pytest.raises(SecurityValidationError, match="not in the specific approved government allowlist"):
            validate_source_url(u)


def test_ssrf_direct_ip_blocking():
    """Direct IP addresses (IPv4, IPv6, loopback, private) must be blocked."""
    ssrf_urls = [
        "https://127.0.0.1/admin",
        "https://localhost/secret",
        "https://169.254.169.254/latest/meta-data",
        "https://10.0.0.1/private",
        "https://192.168.1.1/router",
    ]
    for u in ssrf_urls:
        with pytest.raises(SecurityValidationError):
            validate_source_url(u)


def test_validate_resolved_ip():
    """Direct IP range check blocks private and loopback IPs."""
    with pytest.raises(SecurityValidationError, match="loopback"):
        validate_resolved_ip("127.0.0.1")

    with pytest.raises(SecurityValidationError, match="private"):
        validate_resolved_ip("10.1.2.3")

    with pytest.raises(SecurityValidationError, match="link-local"):
        validate_resolved_ip("169.254.169.254")


def test_compute_sha256_reproducibility():
    """SHA-256 hash must be deterministic and match expected digest."""
    payload = b'{"test": "payload"}'
    digest1 = compute_sha256(payload)
    digest2 = compute_sha256(payload)
    assert digest1 == digest2
    assert len(digest1) == 64
