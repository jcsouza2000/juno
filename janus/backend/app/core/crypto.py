"""
Criptografia simetrica (Fernet/AES-128) para dados sensiveis no banco.

Uso:
    from app.core.crypto import encrypt, decrypt

    ct = encrypt("minha-senha-de-erp")
    pt = decrypt(ct)

A chave vem de `Settings.ENCRYPTION_KEY` (env var). Em dev, se nao houver
chave, derivamos uma a partir do SECRET_KEY (pratico mas nao ideal para prod).
Em producao, ENCRYPTION_KEY e obrigatoria e deve ser gerada com:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

NUNCA reutilizar a chave entre ambientes. Rotacionar requer re-criptografar
todos os campos persistidos.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Constroi o Fernet singleton."""
    key = getattr(settings, "ENCRYPTION_KEY", None)
    if key:
        # Validar formato — Fernet exige 32 bytes url-safe base64.
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise RuntimeError(
                f"ENCRYPTION_KEY invalida: {e}. Gere com "
                "python -c 'from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())'"
            ) from e

    if settings.is_production:
        raise RuntimeError(
            "ENCRYPTION_KEY e obrigatoria em producao. "
            "Gere com Fernet.generate_key() e configure no .env."
        )

    # Dev fallback: deriva da SECRET_KEY (estavel entre restarts se a
    # SECRET_KEY tambem estiver fixada). Senha de ERP em dev sao usadas
    # apenas para testes; nao colocar dados reais.
    logger.warning(
        "ENCRYPTION_KEY nao definida; usando derivacao de SECRET_KEY (dev only). "
        "Configure ENCRYPTION_KEY no .env antes de subir para staging/prod."
    )
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str | None) -> str | None:
    """
    Criptografa uma string. Retorna None se entrada for None/vazia
    (para nao gravar lixo em campos opcionais).
    """
    if not plaintext:
        return None
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt(ciphertext: str | None) -> str | None:
    """
    Descriptografa uma string. Retorna None se entrada for None/vazia.
    Levanta `ValueError` se o token for invalido ou foi adulterado.
    """
    if not ciphertext:
        return None
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("Token criptografado invalido ou chave incorreta") from e


def reset_cache() -> None:
    """Limpa o cache do Fernet (util em testes que mudam ENCRYPTION_KEY)."""
    _get_fernet.cache_clear()
