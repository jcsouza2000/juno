"""
JUNO Ledger - Backends de ancoragem da raiz Merkle.

Interface unica (AnchorBackend) com tres implementacoes:

  OpenTimestampsBackend  -> gratuito, dia 1. Submete o digest da raiz aos
                            calendarios publicos OTS e guarda o recibo .ots.
                            O atestado Bitcoin definitivo leva algumas horas;
                            upgrade() promove o recibo quando disponivel.
  ClientExportBackend    -> Opcao C do blueprint: gera um pacote assinado
                            da raiz para o cofre do proprio cliente.
  IcpBrasilTsaBackend    -> stub documentado (RFC 3161 via ACT credenciada:
                            Serpro/Valid/Soluti). Implementar na Fase B.

Todos retornam (receipt_bytes | None, status). None = falha transitoria;
o job tentara de novo na proxima execucao (a ancora fica PENDING_SUBMIT).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Protocol


class AnchorBackend(Protocol):
    anchor_type: str

    def submit(self, merkle_root: str) -> tuple[Optional[bytes], str]:
        """Ancora a raiz. Retorna (recibo, status)."""
        ...

    def upgrade(self, merkle_root: str, receipt: bytes) -> tuple[Optional[bytes], str]:
        """Tenta promover um recibo SUBMITTED para CONFIRMED."""
        ...


def _root_digest(merkle_root: str) -> bytes:
    """Digest de 32 bytes a partir da raiz 'sha256:<hex>'."""
    return bytes.fromhex(merkle_root.split(":", 1)[1])


# --------------------------------------------------------------------------
# OpenTimestamps
# --------------------------------------------------------------------------
DEFAULT_CALENDARS = [
    "https://alice.btc.calendar.opentimestamps.org",
    "https://bob.btc.calendar.opentimestamps.org",
    "https://finney.calendar.eternitywall.com",
]


class OpenTimestampsBackend:
    """Ancoragem via calendarios publicos OpenTimestamps (python-opentimestamps).

    pip install opentimestamps
    """

    anchor_type = "OPENTIMESTAMPS"

    def __init__(self, calendars: Optional[list[str]] = None, timeout: int = 10):
        self.calendars = calendars or DEFAULT_CALENDARS
        self.timeout = timeout

    def submit(self, merkle_root: str) -> tuple[Optional[bytes], str]:
        try:
            from opentimestamps.calendar import RemoteCalendar
            from opentimestamps.core.timestamp import (DetachedTimestampFile,
                                                       Timestamp)
            from opentimestamps.core.op import OpSHA256
            from opentimestamps.core.serialize import (BytesSerializationContext)
        except ImportError:
            return None, "PENDING_SUBMIT"  # lib ausente: tenta na proxima

        digest = _root_digest(merkle_root)
        timestamp = Timestamp(digest)
        ok = 0
        for url in self.calendars:
            try:
                cal_ts = RemoteCalendar(url).submit(digest, timeout=self.timeout)
                timestamp.merge(cal_ts)
                ok += 1
            except Exception:
                continue  # calendario fora do ar: os outros bastam
        if ok == 0:
            return None, "PENDING_SUBMIT"  # sem rede/calendarios: retry

        detached = DetachedTimestampFile(OpSHA256(), timestamp)
        ctx = BytesSerializationContext()
        detached.serialize(ctx)
        return ctx.getbytes(), "SUBMITTED"  # .ots valido; Bitcoin confirma depois

    def upgrade(self, merkle_root: str, receipt: bytes) -> tuple[Optional[bytes], str]:
        """Consulta os calendarios; se o atestado Bitcoin saiu, recibo vira CONFIRMED."""
        try:
            from opentimestamps.calendar import RemoteCalendar
            from opentimestamps.core.notary import (BitcoinBlockHeaderAttestation,
                                                    PendingAttestation)
            from opentimestamps.core.serialize import (BytesDeserializationContext,
                                                       BytesSerializationContext)
            from opentimestamps.core.timestamp import (DetachedTimestampFile,
                                                       Timestamp)
        except ImportError:
            return None, "SUBMITTED"

        try:
            detached = DetachedTimestampFile.deserialize(
                BytesDeserializationContext(receipt))
        except Exception:
            return None, "SUBMITTED"

        ts = detached.timestamp
        upgraded = False
        for sub_ts, attestation in list(ts.all_attestations()):
            if isinstance(attestation, PendingAttestation):
                try:
                    uri = attestation.uri
                    if isinstance(uri, bytes):
                        uri = uri.decode()
                    cal = RemoteCalendar(uri)
                    # get_timestamp pode retornar bytes (commitment) ou Timestamp;
                    # normalizamos para Timestamp antes do merge.
                    result = cal.get_timestamp(sub_ts.msg, timeout=self.timeout)
                    new_ts = result if hasattr(result, "msg") else Timestamp(sub_ts.msg)
                    if not hasattr(result, "msg") and isinstance(result, (bytes, bytearray)):
                        # alguns calendarios devolvem o blob serializado
                        from opentimestamps.core.serialize import BytesDeserializationContext
                        new_ts = Timestamp.deserialize(
                            BytesDeserializationContext(bytes(result)), sub_ts.msg)
                    sub_ts.merge(new_ts)
                    upgraded = True
                except Exception:
                    continue

        has_btc = any(isinstance(a, BitcoinBlockHeaderAttestation)
                      for _, a in ts.all_attestations())
        if not (upgraded or has_btc):
            return None, "SUBMITTED"

        ctx = BytesSerializationContext()
        detached.serialize(ctx)
        return ctx.getbytes(), ("CONFIRMED" if has_btc else "SUBMITTED")


# --------------------------------------------------------------------------
# Export para o cofre do cliente (Opcao C — aumenta confianca na venda)
# --------------------------------------------------------------------------
class ClientExportBackend:
    anchor_type = "CLIENT_EXPORT"

    def __init__(self, agent_private_key: Optional[str] = None):
        self._sk = agent_private_key

    def submit(self, merkle_root: str) -> tuple[Optional[bytes], str]:
        record = {
            "merkle_root": merkle_root,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "issuer": "JUNO Ledger",
            "sha256_of_root": hashlib.sha256(merkle_root.encode()).hexdigest(),
        }
        if self._sk:
            from .signer import sign_event
            record["signature"] = sign_event(record, self._sk)
        return json.dumps(record, ensure_ascii=False).encode(), "EXPORTED"

    def upgrade(self, merkle_root: str, receipt: bytes):
        return receipt, "EXPORTED"


# --------------------------------------------------------------------------
# ICP-Brasil (RFC 3161) — Fase B do blueprint
# --------------------------------------------------------------------------
class IcpBrasilTsaBackend:
    """Stub documentado. Implementacao futura:

    1. Contratar ACT credenciada (Serpro, Valid, Soluti) e obter endpoint TSA.
    2. Montar TimeStampReq (RFC 3161) com o digest da raiz — lib sugerida:
       `rfc3161ng` ou `asn1crypto` + requests.
    3. POST com Content-Type application/timestamp-query.
    4. Guardar o TimeStampResp (DER) em anchor_receipt; status CONFIRMED
       (carimbo ICP-Brasil ja nasce com presuncao de validade juridica).
    """

    anchor_type = "ICP_BRASIL_TSA"

    def __init__(self, tsa_url: Optional[str] = None):
        self.tsa_url = tsa_url

    def submit(self, merkle_root: str) -> tuple[Optional[bytes], str]:
        raise NotImplementedError(
            "ICP-Brasil TSA: implementar na Fase B (ver docstring)")

    def upgrade(self, merkle_root: str, receipt: bytes):
        return receipt, "CONFIRMED"
