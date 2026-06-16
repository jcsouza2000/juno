"""Valida o caminho OTS com a lib real, simulando apenas a rede:
o recibo gerado deve ser um .ots deserializavel com atestado pendente."""
from unittest.mock import patch
from opentimestamps.core.timestamp import Timestamp, DetachedTimestampFile
from opentimestamps.core.notary import PendingAttestation
from opentimestamps.core.serialize import BytesDeserializationContext

from juno_audit.anchors import OpenTimestampsBackend, _root_digest
from juno_audit.merkle import merkle_root

root = merkle_root(["sha256:" + "ab" * 32, "sha256:" + "cd" * 32])
digest = _root_digest(root)

class FakeCalendar:
    def __init__(self, url): self.url = url
    def submit(self, d, timeout=None):
        ts = Timestamp(d)
        ts.attestations.add(PendingAttestation(self.url))
        return ts

with patch("opentimestamps.calendar.RemoteCalendar", FakeCalendar):
    receipt, status = OpenTimestampsBackend().submit(root)

assert status == "SUBMITTED" and receipt and len(receipt) > 50
det = DetachedTimestampFile.deserialize(BytesDeserializationContext(receipt))
atts = list(det.timestamp.all_attestations())
assert det.timestamp.msg == digest
assert len(atts) == 3 and all(isinstance(a, PendingAttestation) for _, a in atts)
print(f"OTS offline: OK — recibo .ots de {len(receipt)} bytes, "
      f"{len(atts)} atestados pendentes, digest confere")
