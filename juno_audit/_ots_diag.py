"""Diagnostico de conectividade com calendarios OpenTimestamps."""
from __future__ import annotations

import hashlib
import traceback

from opentimestamps.calendar import RemoteCalendar

URLS = [
    "https://alice.btc.calendar.opentimestamps.org",
    "https://bob.btc.calendar.opentimestamps.org",
    "https://finney.calendar.eternitywall.com",
]

digest = hashlib.sha256(b"teste-juno").digest()
print("digest:", digest.hex())

for url in URLS:
    try:
        RemoteCalendar(url).submit(digest, timeout=15)
        print("OK  ", url)
    except Exception as exc:
        print("FALHA", url, "->", type(exc).__name__, exc)
        traceback.print_exc()
        print("---")
