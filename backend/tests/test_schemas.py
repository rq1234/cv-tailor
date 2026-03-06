"""Tests for Pydantic schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.pydantic import (
    AcceptChangesRequest,
    ApplicationCreate,
    ApplicationUpdate,
    RegenerateBulletRequest,
    TailorRunRequest,
)


class TestApplicationCreate:
    def test_valid(self):
        app = ApplicationCreate(
            company_name="Acme",
            jd_raw="Looking for a software engineer...",
        )
        assert app.company_name == "Acme"
        assert app.jd_source == "paste"

    def test_jd_raw_too_short(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(company_name="Acme", jd_raw="")

    def test_jd_raw_too_long(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(company_name="Acme", jd_raw="x" * 50_001)

    def test_invalid_jd_source(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(company_name="Acme", jd_raw="Some JD text", jd_source="email")

    def test_invalid_jd_url_scheme(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(company_name="Acme", jd_raw="Some JD text", jd_url="ftp://example.com")

    def test_valid_jd_url(self):
        app = ApplicationCreate(
            company_name="Acme",
            jd_raw="Some JD text",
            jd_url="https://example.com/jobs/123",
        )
        assert app.jd_url == "https://example.com/jobs/123"


class TestApplicationUpdate:
    def test_valid_outcome(self):
        update = ApplicationUpdate(outcome="applied")
        assert update.outcome == "applied"

    def test_null_outcome(self):
        update = ApplicationUpdate(outcome=None)
        assert update.outcome is None

    def test_valid_notes(self):
        update = ApplicationUpdate(notes="Submitted via LinkedIn")
        assert update.notes == "Submitted via LinkedIn"

    def test_notes_too_long(self):
        with pytest.raises(ValidationError):
            ApplicationUpdate(notes="x" * 5001)

    def test_invalid_outcome_rejected(self):
        with pytest.raises(ValidationError):
            ApplicationUpdate(outcome="hired")

    def test_empty_model(self):
        update = ApplicationUpdate()
        assert update.outcome is None
        assert update.notes is None


class TestAcceptChangesRequest:
    def test_valid(self):
        req = AcceptChangesRequest(
            accepted_changes={"exp-1": ["Bullet one", "Bullet two"]},
            rejected_changes={"exp-2": [0, 1]},
        )
        assert "exp-1" in req.accepted_changes
        assert "exp-2" in req.rejected_changes

    def test_empty_dicts(self):
        req = AcceptChangesRequest(accepted_changes={}, rejected_changes={})
        assert req.accepted_changes == {}
        assert req.rejected_changes == {}

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            AcceptChangesRequest(accepted_changes={})


class TestRegenerateBulletRequest:
    def test_valid(self):
        import uuid
        req = RegenerateBulletRequest(
            application_id=uuid.uuid4(),
            experience_id=str(uuid.uuid4()),
            bullet_index=0,
        )
        assert req.bullet_index == 0

    def test_invalid_experience_id(self):
        import uuid
        with pytest.raises(ValidationError):
            RegenerateBulletRequest(
                application_id=uuid.uuid4(),
                experience_id="not-a-uuid",
                bullet_index=0,
            )

    def test_hint_too_long_rejected(self):
        import uuid
        with pytest.raises(ValidationError):
            RegenerateBulletRequest(
                application_id=uuid.uuid4(),
                experience_id=str(uuid.uuid4()),
                bullet_index=0,
                hint="x" * 600,
            )

    def test_rejected_variants_capped(self):
        import uuid
        req = RegenerateBulletRequest(
            application_id=uuid.uuid4(),
            experience_id=str(uuid.uuid4()),
            bullet_index=0,
            rejected_variants=["variant"] * 20,
        )
        assert len(req.rejected_variants) == 10
