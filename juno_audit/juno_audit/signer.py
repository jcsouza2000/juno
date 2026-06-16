"""
JUNO Agent ID - Identidade criptografica de agentes (Ed25519 via PyNaCl).

Cada agente (e cada aprovador humano, se desejado) possui um par de chaves.
A chave privada fica em cofre (Railway secrets / variavel de ambiente /
HSM no on-prem). A publica vai para o Agent Registry.
"""
from __future__ import annotations

import base64

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from .canonical import EXCLUDED_FIELDS, canonical_json

PREFIX = "ed25519:"


def generate_keypair() -> tuple[str, str]:
    """Gera (private_b64, public_b64). Guarde a privada em cofre, NUNCA no banco."""
    sk = SigningKey.generate()
    private_b64 = base64.b64encode(bytes(sk)).decode()
    public_b64 = base64.b64encode(bytes(sk.verify_key)).decode()
    return PREFIX + private_b64, PREFIX + public_b64


def _decode(key: str) -> bytes:
    if key.startswith(PREFIX):
        key = key[len(PREFIX):]
    return base64.b64decode(key)


def sign_event(event: dict, private_key: str) -> str:
    """Assina a forma canonica do evento (sem campos de hash/assinatura)."""
    core = {k: v for k, v in event.items() if k not in EXCLUDED_FIELDS}
    sk = SigningKey(_decode(private_key))
    sig = sk.sign(canonical_json(core)).signature
    return PREFIX + base64.b64encode(sig).decode()


def verify_event_signature(event: dict, signature: str, public_key: str) -> bool:
    core = {k: v for k, v in event.items() if k not in EXCLUDED_FIELDS}
    vk = VerifyKey(_decode(public_key))
    try:
        vk.verify(canonical_json(core), _decode(signature))
        return True
    except BadSignatureError:
        return False
