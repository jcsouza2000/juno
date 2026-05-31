"""
test_user_markings.py - testes end-to-end de grants de markings.

Cobre:
  - grant cria row e audita
  - grant idempotente
  - revoke marca revoked=True
  - revoke audita
  - list filtra revoked/expired
  - UserContext.from_user_with_grants le do banco
  - grant expirado nao concede
  - service rejeita marking invalido / user inexistente
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app import models
from app.ontology.permissions import UserContext
from app.services.marking_grants import (
    MarkingGrantError,
    grant_marking,
    list_active_for_user,
    revoke_marking,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def admin_user(db_session):
    u = models.User(id=1, email="admin@test", full_name="Admin", hashed_password="x", role="admin")
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def regular_user(db_session, admin_user):
    u = models.User(
        id=100, email="user@test", full_name="User", hashed_password="x", role="analista"
    )
    db_session.add(u)
    db_session.commit()
    return u


# =============================================================================
# grant_marking
# =============================================================================


class TestGrant:
    def test_grant_creates_row(self, db_session, regular_user, admin_user):
        result = grant_marking(
            db_session,
            user_id=100,
            marking="ConfidencialComercial",
            granted_by=1,
            reason="auditoria",
        )
        db_session.commit()
        assert result["user_id"] == 100
        assert result["marking"] == "ConfidencialComercial"
        assert result["revoked"] is False

        # Persistiu no banco
        row = db_session.query(models.UserMarking).filter_by(id=result["id"]).one()
        assert row.granted_by == 1
        assert row.reason == "auditoria"

    def test_grant_is_idempotent(self, db_session, regular_user, admin_user):
        g1 = grant_marking(db_session, user_id=100, marking="PII", granted_by=1)
        g2 = grant_marking(db_session, user_id=100, marking="PII", granted_by=1)
        db_session.commit()
        assert g1["id"] == g2["id"]
        # Apenas 1 row no banco
        count = db_session.query(models.UserMarking).filter_by(marking="PII").count()
        assert count == 1

    def test_grant_audits(self, db_session, regular_user, admin_user):
        grant_marking(db_session, user_id=100, marking="PII", granted_by=1, reason="LGPD")
        db_session.commit()
        log = (
            db_session.query(models.AuditLog)
            .filter(models.AuditLog.action == "grant_marking")
            .order_by(models.AuditLog.id.desc())
            .first()
        )
        assert log is not None
        details = json.loads(log.details)
        assert details["marking"] == "PII"
        assert details["target_user_id"] == 100
        assert details["reason"] == "LGPD"

    def test_grant_unknown_user_raises(self, db_session, admin_user):
        with pytest.raises(MarkingGrantError, match="user_id 9999 nao existe"):
            grant_marking(db_session, user_id=9999, marking="PII", granted_by=1)

    def test_grant_with_valid_until(self, db_session, regular_user, admin_user):
        until = datetime.utcnow() + timedelta(days=30)
        result = grant_marking(
            db_session,
            user_id=100,
            marking="PII",
            granted_by=1,
            valid_until=until,
        )
        db_session.commit()
        row = db_session.query(models.UserMarking).filter_by(id=result["id"]).one()
        assert row.valid_until is not None


# =============================================================================
# revoke_marking
# =============================================================================


class TestRevoke:
    def test_revoke_marks_revoked_true(self, db_session, regular_user, admin_user):
        g = grant_marking(db_session, user_id=100, marking="PII", granted_by=1)
        db_session.commit()
        result = revoke_marking(db_session, grant_id=g["id"], revoked_by=1, reason="erro")
        db_session.commit()
        assert result["revoked"] is True
        assert result["revoked_by"] == 1

        row = db_session.query(models.UserMarking).filter_by(id=g["id"]).one()
        assert row.revoked is True
        assert row.revoked_at is not None

    def test_revoke_unknown_raises(self, db_session, admin_user):
        with pytest.raises(MarkingGrantError, match="grant 9999 nao existe"):
            revoke_marking(db_session, grant_id=9999, revoked_by=1)

    def test_revoke_already_revoked_raises(self, db_session, regular_user, admin_user):
        g = grant_marking(db_session, user_id=100, marking="PII", granted_by=1)
        revoke_marking(db_session, grant_id=g["id"], revoked_by=1)
        db_session.commit()
        with pytest.raises(MarkingGrantError, match="ja' revogado"):
            revoke_marking(db_session, grant_id=g["id"], revoked_by=1)


# =============================================================================
# list_active_for_user
# =============================================================================


class TestListActive:
    def test_returns_active_only(self, db_session, regular_user, admin_user):
        grant_marking(db_session, user_id=100, marking="PII", granted_by=1)
        g2 = grant_marking(db_session, user_id=100, marking="ConfidencialComercial", granted_by=1)
        revoke_marking(db_session, grant_id=g2["id"], revoked_by=1)
        db_session.commit()
        active = list_active_for_user(db_session, 100)
        assert active == ["PII"]

    def test_expired_excluded(self, db_session, regular_user, admin_user):
        past = datetime.utcnow() - timedelta(days=1)
        grant_marking(db_session, user_id=100, marking="PII", granted_by=1, valid_until=past)
        db_session.commit()
        active = list_active_for_user(db_session, 100)
        assert active == []


# =============================================================================
# UserContext.from_user_with_grants
# =============================================================================


class TestUserContextWithGrants:
    def test_admin_keeps_wildcard(self, db_session, admin_user):
        ctx = UserContext.from_user_with_grants(admin_user, db_session)
        assert ctx.markings_granted == ["*"]
        assert ctx.has_marking("AnyMarking")

    def test_regular_user_gets_active_grants(self, db_session, regular_user, admin_user):
        grant_marking(db_session, user_id=100, marking="PII", granted_by=1)
        grant_marking(db_session, user_id=100, marking="ConfidencialComercial", granted_by=1)
        db_session.commit()

        ctx = UserContext.from_user_with_grants(regular_user, db_session)
        assert set(ctx.markings_granted) == {"PII", "ConfidencialComercial"}
        assert ctx.has_marking("PII")
        assert ctx.has_marking("ConfidencialComercial")
        assert not ctx.has_marking("FinanceiroConsolidado")

    def test_revoked_not_included(self, db_session, regular_user, admin_user):
        g = grant_marking(db_session, user_id=100, marking="PII", granted_by=1)
        revoke_marking(db_session, grant_id=g["id"], revoked_by=1)
        db_session.commit()

        ctx = UserContext.from_user_with_grants(regular_user, db_session)
        assert ctx.markings_granted == []
        assert not ctx.has_marking("PII")

    def test_expired_not_included(self, db_session, regular_user, admin_user):
        past = datetime.utcnow() - timedelta(hours=1)
        grant_marking(db_session, user_id=100, marking="PII", granted_by=1, valid_until=past)
        db_session.commit()

        ctx = UserContext.from_user_with_grants(regular_user, db_session)
        assert ctx.markings_granted == []


# =============================================================================
# Integracao com runtime: filter_columns respeita grants do banco
# =============================================================================


class TestIntegrationWithRuntime:
    def test_user_with_grant_sees_confidencial(
        self,
        db_session,
        loaded_registry,
        admin_user,
        regular_user,
        seed_data,
    ):
        from app.ontology import runtime

        # company_id=1 vinculado ao regular_user
        grant_marking(db_session, user_id=100, marking="ConfidencialComercial", granted_by=1)
        db_session.commit()

        # Constroi UserContext a partir do banco + vincula a company 1
        ctx = UserContext.from_user_with_grants(regular_user, db_session)
        ctx.company_ids = [1]

        prod = runtime.fetch_by_id(
            "Produto",
            10,
            user=ctx,
            db=db_session,
            registry=loaded_registry,
        )
        assert prod["sale_price"] == 180.0  # grant ConfidencialComercial liberou

    def test_user_without_grant_blocked(
        self,
        db_session,
        loaded_registry,
        admin_user,
        regular_user,
        seed_data,
    ):
        from app.ontology import runtime

        ctx = UserContext.from_user_with_grants(regular_user, db_session)
        ctx.company_ids = [1]

        prod = runtime.fetch_by_id(
            "Produto",
            10,
            user=ctx,
            db=db_session,
            registry=loaded_registry,
        )
        # Sem grant -> sale_price/standard_cost omitidos
        assert "sale_price" not in prod
        assert "standard_cost" not in prod
        # Mas ve outras props
        assert prod["name"] == "Widget Pro"
