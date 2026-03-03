"""Tests for security validators: SSRF URL validation and Pydantic field validators."""
from __future__ import annotations

import socket
import uuid
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from schemas.pydantic import ApplicationCreate, RegenerateBulletRequest
from services.jd_scraper import _validate_url


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_dns(ip: str):
    """Return a mock getaddrinfo result resolving to the given IP."""
    return [(None, None, None, None, (ip, 0))]


# ── _validate_url() SSRF prevention ──────────────────────────────────────────


class TestValidateUrl:

    def test_valid_https_url_passes(self):
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("93.184.216.34")):
            _validate_url("https://example.com/jobs/123")  # must not raise

    def test_valid_http_url_passes(self):
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("93.184.216.34")):
            _validate_url("http://example.com/job-posting")  # must not raise

    # — Bad schemes —

    def test_ftp_scheme_rejected(self):
        with pytest.raises(ValueError, match="Only http"):
            _validate_url("ftp://example.com/file.txt")

    def test_file_scheme_rejected(self):
        with pytest.raises(ValueError, match="Only http"):
            _validate_url("file:///etc/passwd")

    def test_javascript_scheme_rejected(self):
        with pytest.raises(ValueError, match="Only http"):
            _validate_url("javascript:alert(1)")

    def test_data_scheme_rejected(self):
        with pytest.raises(ValueError, match="Only http"):
            _validate_url("data:text/html,<script>alert(1)</script>")

    # — Missing / unresolvable hostname —

    def test_missing_hostname_rejected(self):
        with pytest.raises(ValueError, match="missing hostname"):
            _validate_url("https://")

    def test_unresolvable_hostname_rejected(self):
        with patch("services.jd_scraper.socket.getaddrinfo") as mock_dns:
            mock_dns.side_effect = socket.gaierror("Name or service not known")
            with pytest.raises(ValueError, match="Could not resolve"):
                _validate_url("https://this-host-definitely-does-not-exist-xyz.invalid")

    # — Private / loopback / reserved addresses —

    def test_localhost_ipv4_rejected(self):
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("127.0.0.1")):
            with pytest.raises(ValueError, match="internal network"):
                _validate_url("http://localhost/admin")

    def test_rfc1918_10_block_rejected(self):
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("10.0.0.1")):
            with pytest.raises(ValueError, match="internal network"):
                _validate_url("http://internal.corp/secret")

    def test_rfc1918_192_168_rejected(self):
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("192.168.1.1")):
            with pytest.raises(ValueError, match="internal network"):
                _validate_url("http://router/config")

    def test_rfc1918_172_16_rejected(self):
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("172.16.0.1")):
            with pytest.raises(ValueError, match="internal network"):
                _validate_url("http://internal.example.com/")

    def test_aws_metadata_endpoint_rejected(self):
        # 169.254.169.254 is the AWS/GCP/Azure instance metadata endpoint
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("169.254.169.254")):
            with pytest.raises(ValueError, match="internal network"):
                _validate_url("http://169.254.169.254/latest/meta-data/")

    def test_ipv6_loopback_rejected(self):
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("::1")):
            with pytest.raises(ValueError, match="internal network"):
                _validate_url("http://[::1]/")

    def test_ipv6_ula_rejected(self):
        # fc00::/7 is IPv6 Unique Local Address (private)
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=_mock_dns("fc00::1")):
            with pytest.raises(ValueError, match="internal network"):
                _validate_url("http://[fc00::1]/")

    def test_multiple_dns_results_all_checked(self):
        # Even if one result is public, a private result in the same DNS response must be blocked
        mixed = [
            (None, None, None, None, ("93.184.216.34", 0)),
            (None, None, None, None, ("10.0.0.1", 0)),
        ]
        with patch("services.jd_scraper.socket.getaddrinfo", return_value=mixed):
            with pytest.raises(ValueError, match="internal network"):
                _validate_url("https://suspicious.example.com/")


# ── ApplicationCreate.jd_url + jd_source validators ──────────────────────────


class TestApplicationCreateValidators:

    def _base(self, **overrides) -> dict:
        return {"company_name": "Acme Corp", "jd_raw": "We are hiring.", **overrides}

    def test_valid_https_jd_url(self):
        app = ApplicationCreate(**self._base(jd_url="https://acme.com/jobs/123"))
        assert app.jd_url == "https://acme.com/jobs/123"

    def test_valid_http_jd_url(self):
        app = ApplicationCreate(**self._base(jd_url="http://acme.com/jobs/123"))
        assert app.jd_url == "http://acme.com/jobs/123"

    def test_null_jd_url_allowed(self):
        app = ApplicationCreate(**self._base(jd_url=None))
        assert app.jd_url is None

    def test_jd_url_omitted_defaults_none(self):
        app = ApplicationCreate(**self._base())
        assert app.jd_url is None

    def test_ftp_jd_url_rejected(self):
        with pytest.raises(ValidationError, match="jd_url must start with http"):
            ApplicationCreate(**self._base(jd_url="ftp://acme.com/jobs.txt"))

    def test_javascript_jd_url_rejected(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(**self._base(jd_url="javascript:alert(1)"))

    def test_data_jd_url_rejected(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(**self._base(jd_url="data:text/html,hello"))

    def test_relative_url_rejected(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(**self._base(jd_url="/jobs/123"))

    # — jd_source Literal —

    def test_jd_source_defaults_to_paste(self):
        app = ApplicationCreate(**self._base())
        assert app.jd_source == "paste"

    def test_jd_source_paste(self):
        app = ApplicationCreate(**self._base(jd_source="paste"))
        assert app.jd_source == "paste"

    def test_jd_source_screenshot(self):
        app = ApplicationCreate(**self._base(jd_source="screenshot"))
        assert app.jd_source == "screenshot"

    def test_jd_source_url(self):
        app = ApplicationCreate(**self._base(jd_source="url"))
        assert app.jd_source == "url"

    def test_jd_source_unknown_rejected(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(**self._base(jd_source="upload"))

    def test_jd_source_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(**self._base(jd_source=""))


# ── RegenerateBulletRequest validators ───────────────────────────────────────


class TestRegenerateBulletRequestValidators:

    def _base(self, **overrides) -> dict:
        return {
            "application_id": str(uuid.uuid4()),
            "experience_id": str(uuid.uuid4()),
            "bullet_index": 0,
            **overrides,
        }

    # — experience_id UUID validation —

    def test_valid_uuid_experience_id(self):
        valid_id = str(uuid.uuid4())
        req = RegenerateBulletRequest(**self._base(experience_id=valid_id))
        assert req.experience_id == valid_id

    def test_uppercase_uuid_accepted(self):
        valid_id = str(uuid.uuid4()).upper()
        req = RegenerateBulletRequest(**self._base(experience_id=valid_id))
        assert req.experience_id == valid_id

    def test_non_uuid_string_rejected(self):
        with pytest.raises(ValidationError, match="valid UUID"):
            RegenerateBulletRequest(**self._base(experience_id="not-a-uuid"))

    def test_sql_injection_rejected(self):
        with pytest.raises(ValidationError, match="valid UUID"):
            RegenerateBulletRequest(**self._base(experience_id="'; DROP TABLE applications; --"))

    def test_path_traversal_rejected(self):
        with pytest.raises(ValidationError, match="valid UUID"):
            RegenerateBulletRequest(**self._base(experience_id="../../etc/passwd"))

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            RegenerateBulletRequest(**self._base(experience_id=""))

    def test_integer_like_string_rejected(self):
        with pytest.raises(ValidationError, match="valid UUID"):
            RegenerateBulletRequest(**self._base(experience_id="12345"))

    # — rejected_variants capping —

    def test_rejected_variants_none_allowed(self):
        req = RegenerateBulletRequest(**self._base(rejected_variants=None))
        assert req.rejected_variants is None

    def test_rejected_variants_omitted_defaults_none(self):
        req = RegenerateBulletRequest(**self._base())
        assert req.rejected_variants is None

    def test_rejected_variants_empty_list_allowed(self):
        req = RegenerateBulletRequest(**self._base(rejected_variants=[]))
        assert req.rejected_variants == []

    def test_rejected_variants_capped_at_10(self):
        variants = [f"variant {i}" for i in range(25)]
        req = RegenerateBulletRequest(**self._base(rejected_variants=variants))
        assert len(req.rejected_variants) == 10
        # First 10 items should be preserved in order
        assert req.rejected_variants == [f"variant {i}" for i in range(10)]

    def test_rejected_variant_text_capped_at_500_chars(self):
        long_text = "x" * 1000
        req = RegenerateBulletRequest(**self._base(rejected_variants=[long_text]))
        assert len(req.rejected_variants[0]) == 500

    def test_rejected_variants_short_text_unchanged(self):
        req = RegenerateBulletRequest(**self._base(rejected_variants=["Implemented feature X"]))
        assert req.rejected_variants == ["Implemented feature X"]

    def test_rejected_variants_exactly_10_unchanged(self):
        variants = [f"v{i}" for i in range(10)]
        req = RegenerateBulletRequest(**self._base(rejected_variants=variants))
        assert len(req.rejected_variants) == 10

    def test_rejected_variants_text_exactly_500_unchanged(self):
        text = "a" * 500
        req = RegenerateBulletRequest(**self._base(rejected_variants=[text]))
        assert req.rejected_variants[0] == text

    def test_both_caps_applied_together(self):
        # 15 items, each 800 chars — should become 10 items of 500 chars each
        variants = ["z" * 800 for _ in range(15)]
        req = RegenerateBulletRequest(**self._base(rejected_variants=variants))
        assert len(req.rejected_variants) == 10
        assert all(len(v) == 500 for v in req.rejected_variants)
