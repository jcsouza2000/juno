"""
JUNO Ledger - Arvore de Merkle.

A cada lote (por hora ou N eventos), calcula-se a raiz de Merkle dos hashes
dos eventos. A raiz e o que vai para o carimbo do tempo (ICP-Brasil /
OpenTimestamps). Com a raiz carimbada, qualquer evento do lote tem prova
de existencia e integridade independente do banco de dados do JUNO.
"""
from __future__ import annotations

import hashlib


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _leaf(event_hash: str) -> bytes:
    # prefixo 0x00 para folhas (protecao contra second-preimage)
    return _h(b"\x00" + event_hash.encode())


def _node(left: bytes, right: bytes) -> bytes:
    return _h(b"\x01" + left + right)


def merkle_root(event_hashes: list[str]) -> str:
    """Raiz de Merkle de uma lista de hashes de eventos (ordem da cadeia)."""
    if not event_hashes:
        raise ValueError("lote vazio")
    level = [_leaf(h) for h in event_hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # duplica o ultimo (padrao Bitcoin)
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return "sha256:" + level[0].hex()


def merkle_proof(event_hashes: list[str], index: int) -> list[tuple[str, str]]:
    """Prova de inclusao do evento na posicao `index`.

    Retorna lista de (lado, hash_hex) - lado em {'L','R'} - suficiente para
    o cliente provar que SEU evento esta sob a raiz carimbada, sem precisar
    do lote inteiro.
    """
    if not (0 <= index < len(event_hashes)):
        raise IndexError("index fora do lote")
    proof: list[tuple[str, str]] = []
    level = [_leaf(h) for h in event_hashes]
    idx = index
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        sibling = idx + 1 if idx % 2 == 0 else idx - 1
        side = "R" if idx % 2 == 0 else "L"
        proof.append((side, level[sibling].hex()))
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        idx //= 2
    return proof


def verify_proof(event_hash: str, proof: list[tuple[str, str]], root: str) -> bool:
    cur = _leaf(event_hash)
    for side, sib_hex in proof:
        sib = bytes.fromhex(sib_hex)
        cur = _node(cur, sib) if side == "R" else _node(sib, cur)
    return "sha256:" + cur.hex() == root
