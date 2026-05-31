"""
Testes unitarios para modulo de Seguranca e Compliance
"""

from typing import cast
from unittest.mock import Mock

from app.security.audit_engine import AuditEngine
from app.security.gdpr_engine import GDPREngine
from app.security.middleware import sanitize_input, validate_password_strength
from app.security.rbac_engine import Permission, RBACEngine


class TestRBAC:
    def test_get_user_permissions(self):
        mock_db = Mock()
        engine = RBACEngine(mock_db)

        mock_role = Mock()
        mock_role.permissions = '["product.read", "product.write"]'
        mock_role.expires_at = None

        mock_ur = Mock()
        mock_ur.role = mock_role

        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            mock_ur
        ]

        perms = engine.get_user_permissions(1, 1)
        assert "product.read" in perms
        assert "product.write" in perms

    def test_has_permission(self):
        mock_db = Mock()
        engine = RBACEngine(mock_db)

        mock_role = Mock()
        mock_role.permissions = '["product.read"]'
        mock_role.expires_at = None

        mock_ur = Mock()
        mock_ur.role = mock_role

        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            mock_ur
        ]

        assert engine.has_permission(1, 1, Permission.PRODUCT_READ) == True
        assert engine.has_permission(1, 1, Permission.PRODUCT_DELETE) == False


class TestAudit:
    def test_log_creation(self):
        mock_db = Mock()
        engine = AuditEngine(mock_db)

        engine.log(
            company_id=1,
            user_id=1,
            action="CREATE",
            resource_type="product",
            resource_id=1,
            new_values={"name": "Test"},
            severity="info",
        )

        assert mock_db.add.called
        assert mock_db.commit.called

    def test_sanitize_sensitive_data(self):
        mock_db = Mock()
        engine = AuditEngine(mock_db)

        data = {"name": "Test", "password": "secret123", "api_secret": "key"}
        result = cast(dict[str, str], engine._sanitize_sensitive_data(data))

        assert result["name"] == "Test"
        assert result["password"] == "***REDACTED***"
        assert result["api_secret"] == "***REDACTED***"


class TestGDPR:
    def test_create_dsr(self):
        mock_db = Mock()
        engine = GDPREngine(mock_db)

        dsr = engine.create_data_subject_request(
            company_id=1, request_type="access", data_subject_email="test@example.com"
        )

        assert dsr.request_type == "access"
        assert dsr.data_subject_email == "test@example.com"
        assert dsr.status == "pending"

    def test_check_consent(self):
        mock_db = Mock()
        engine = GDPREngine(mock_db)

        mock_consent = Mock()
        mock_consent.consent_given = True
        mock_consent.withdrawn_at = None

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_consent
        )

        assert engine.check_consent(1, "test@example.com", "marketing") == True


class TestMiddleware:
    def test_validate_password_strength_strong(self):
        result = validate_password_strength("MyStr0ng!Pass")
        assert result["valid"] == True
        assert result["strength"] == "strong"

    def test_validate_password_strength_weak(self):
        result = validate_password_strength("123")
        assert result["valid"] == False
        assert result["strength"] == "weak"

    def test_sanitize_input(self):
        result = sanitize_input('<script>alert("xss")</script>Hello')
        assert "<script>" not in result
        assert "Hello" in result
