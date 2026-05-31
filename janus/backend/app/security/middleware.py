"""
JUNO Security Middleware
Rate limiting, brute force protection, security headers, OWASP compliance
"""

import json
import time
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.datetime_utils import utcnow_naive
from app.models import LoginAttempt

# Rate limiter global
limiter = Limiter(key_func=get_remote_address)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware de seguranca para todas as requisicoes.
    """

    def __init__(self, app):
        super().__init__(app)
        self.blocked_ips: dict[str, float] = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        if client_ip in self.blocked_ips:
            if time.time() < self.blocked_ips[client_ip]:
                return Response(
                    content=json.dumps({"detail": "IP bloqueado temporariamente"}),
                    status_code=403,
                    media_type="application/json",
                )
            else:
                del self.blocked_ips[client_ip]

        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers.pop("Server", None)

        return response

    def _get_client_ip(self, request: Request) -> str:
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class BruteForceProtection:
    """
    Protecao contra ataques de forca bruta em login.
    """

    def __init__(self, db=None):
        self.db = db

    def is_blocked(self, username: str, ip_address: str) -> bool:
        """Verifica se usuario/IP esta bloqueado."""
        if not self.db:
            return False

        since = utcnow_naive() - timedelta(minutes=30)

        ip_attempts = (
            self.db.query(LoginAttempt)
            .filter(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.created_at >= since,
                LoginAttempt.success == False,
            )
            .count()
        )

        user_attempts = (
            self.db.query(LoginAttempt)
            .filter(
                LoginAttempt.username == username,
                LoginAttempt.created_at >= since,
                LoginAttempt.success == False,
            )
            .count()
        )

        return ip_attempts >= 5 or user_attempts >= 3

    def record_attempt(
        self,
        username: str,
        ip_address: str,
        success: bool,
        failure_reason: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Registra tentativa de login."""
        if not self.db:
            return

        attempt = LoginAttempt(
            username=username,
            ip_address=ip_address,
            success=success,
            failure_reason=failure_reason,
            user_agent=user_agent,
        )
        self.db.add(attempt)
        self.db.commit()

    def get_remaining_attempts(self, username: str, ip_address: str) -> int:
        """Retorna tentativas restantes antes do bloqueio."""
        if not self.db:
            return 5

        since = utcnow_naive() - timedelta(minutes=30)

        ip_attempts = (
            self.db.query(LoginAttempt)
            .filter(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.created_at >= since,
                LoginAttempt.success == False,
            )
            .count()
        )

        return max(0, 5 - ip_attempts)


class EncryptionService:
    """
    Servico de criptografia para dados sensiveis.
    """

    def __init__(self, key: bytes | None = None):
        from cryptography.fernet import Fernet

        if key:
            self.fernet = Fernet(key)
        else:
            self.fernet = Fernet(Fernet.generate_key())

    def encrypt(self, data: str) -> str:
        """Criptografa string."""
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Descriptografa string."""
        return self.fernet.decrypt(token.encode()).decode()

    def hash_password(self, password: str) -> str:
        """Hash seguro de senha usando Argon2."""
        from argon2 import PasswordHasher

        ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)
        return ph.hash(password)

    def verify_password(self, password: str, hash: str) -> bool:
        """Verifica senha contra hash."""
        from argon2 import PasswordHasher, exceptions

        ph = PasswordHasher()
        try:
            ph.verify(hash, password)
            return True
        except exceptions.VerifyMismatchError:
            return False


def sanitize_input(data: str) -> str:
    """
    Sanitiza input de usuario contra XSS e injecao.
    """
    import bleach

    allowed_tags = ["b", "i", "u", "strong", "em", "p", "br"]
    allowed_attrs: dict[str, list[str]] = {}

    cleaned = bleach.clean(data, tags=allowed_tags, attributes=allowed_attrs, strip=True)
    return cleaned[:1000]


def validate_password_strength(password: str, policy: dict | None = None) -> dict[str, Any]:
    """
    Valida forca da senha conforme politica.
    """
    policy = policy or {
        "min_length": 8,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_numbers": True,
        "require_special": True,
        "max_length": 128,
    }

    errors = []

    if len(password) < policy.get("min_length", 8):
        errors.append(f"Minimo de {policy['min_length']} caracteres")

    if len(password) > policy.get("max_length", 128):
        errors.append(f"Maximo de {policy['max_length']} caracteres")

    if policy.get("require_uppercase") and not any(c.isupper() for c in password):
        errors.append("Pelo menos uma letra maiuscula")

    if policy.get("require_lowercase") and not any(c.islower() for c in password):
        errors.append("Pelo menos uma letra minuscula")

    if policy.get("require_numbers") and not any(c.isdigit() for c in password):
        errors.append("Pelo menos um numero")

    if policy.get("require_special") and not any(
        c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password
    ):
        errors.append("Pelo menos um caractere especial")

    common_passwords = ["123456", "password", "qwerty", "admin", "letmein"]
    if password.lower() in common_passwords:
        errors.append("Senha muito comum")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "strength": "strong" if len(errors) == 0 else "weak" if len(errors) > 2 else "medium",
    }


def require_https(request: Request):
    """
    Verifica se requisicao esta usando HTTPS.
    """
    if request.url.scheme != "https" and request.url.hostname not in ["localhost", "127.0.0.1"]:
        raise HTTPException(status_code=403, detail="HTTPS obrigatorio para esta operacao")
