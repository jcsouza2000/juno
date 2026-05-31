"""Testes do helper de criptografia (Fernet)."""

import pytest

from app.core.crypto import decrypt, encrypt, reset_cache


def test_roundtrip():
    ct = encrypt("minha-senha-secreta")
    assert ct is not None
    assert ct != "minha-senha-secreta"
    assert decrypt(ct) == "minha-senha-secreta"


def test_empty_string_returns_none():
    assert encrypt("") is None
    assert encrypt(None) is None
    assert decrypt("") is None
    assert decrypt(None) is None


def test_two_encryptions_differ_but_decrypt_same():
    """Fernet inclui IV aleatório — mesma plaintext gera ciphertexts diferentes."""
    a = encrypt("repetido")
    b = encrypt("repetido")
    assert a != b
    assert decrypt(a) == decrypt(b) == "repetido"


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        decrypt("isso-nao-e-fernet-valido")


def test_unicode_handled():
    pt = "senha com áéíóú e 中文 e emoji 🚀"
    assert decrypt(encrypt(pt)) == pt


def test_reset_cache():
    # Apenas confirma que o helper existe e não levanta.
    reset_cache()
    assert encrypt("x") is not None
